param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$AuditDirectory,
    [int[]]$ParagraphIndexes = @(1, 3, 38, 39, 41, 42, 45, 46, 74, 75, 76, 86, 90)
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$auditPath = (Resolve-Path -LiteralPath $AuditDirectory).Path
$privateRoot = Join-Path $repo '.paperalign'
if (-not $auditPath.StartsWith($privateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Word audit must be stored under repository .paperalign'
}
$source = (Resolve-Path -LiteralPath $InputPath).Path
$before = (Get-FileHash -LiteralPath $source).Hash
$evidence = Get-Content -LiteralPath (Join-Path $auditPath 'template_evidence.json') -Raw | ConvertFrom-Json
if ($before.ToLowerInvariant() -ne $evidence.input_sha256) { throw 'Audit belongs to a different input' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($source)
try {
    $reader = [IO.StreamReader]::new($zip.GetEntry('word/document.xml').Open())
    try { $xml = [xml]$reader.ReadToEnd() } finally { $reader.Dispose() }
} finally { $zip.Dispose() }
$ns = [Xml.XmlNamespaceManager]::new($xml.NameTable)
$ns.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
$xmlParagraphs = $xml.SelectNodes('/w:document/w:body/w:p', $ns)
$application = $null
$document = $null
$rows = [Collections.Generic.List[object]]::new()
try {
    $application = New-Object -ComObject Word.Application
    $application.Visible = $false
    $application.DisplayAlerts = 0
    $application.AutomationSecurity = 3
    $document = $application.Documents.Open($source, $false, $true, $false)
    $wordParagraphs = @($document.Paragraphs | Where-Object { -not $_.Range.Information(12) })
    foreach ($index in $ParagraphIndexes) {
        if ($index -ge $xmlParagraphs.Count -or $index -ge $wordParagraphs.Count) {
            $rows.Add(@{paragraph_index=$index; status='not_evaluated'; reason='index_out_of_range'})
            continue
        }
        $xp = $xmlParagraphs[$index]
        $wp = $wordParagraphs[$index]
        $xmlText = ($xp.SelectNodes('.//w:t | .//w:br | .//w:tab', $ns) | ForEach-Object {
            if ($_.LocalName -eq 't') { $_.InnerText }
            elseif ($_.LocalName -eq 'tab') { [string][char]9 }
            elseif ($_.GetAttribute('type', $ns.LookupNamespace('w')) -eq 'page') { [string][char]12 }
            else { [string][char]11 }
        }) -join ''
        $wordText = $wp.Range.Text.TrimEnd([char[]]@([char]13,[char]7,[char]12))
        if ($xmlText -ne $wordText) {
            $rows.Add(@{paragraph_index=$index; status='not_evaluated'; reason='paragraph_mapping_mismatch'})
            continue
        }
        $snapshot = $evidence.effective_formats[$index]
        if ($snapshot.runs.Count -eq 0) { continue }
        $group = $snapshot.runs[0]
        $runIndex = $group.sample_run_indexes[0]
        $runs = $xp.SelectNodes('.//w:r', $ns)
        $offset = 0
        for ($i=0; $i -lt $runIndex; $i++) {
            $offset += (($runs[$i].SelectNodes('.//w:t', $ns) | ForEach-Object { $_.InnerText }) -join '').Length
            $offset += $runs[$i].SelectNodes('.//w:br | .//w:tab', $ns).Count
        }
        $charRange = $document.Range($wp.Range.Start + $offset, $wp.Range.Start + $offset + 1)
        $actual = @{
            size_pt=[double]$charRange.Font.Size
            font_east_asia=[string]$charRange.Font.NameFarEast
            font_latin=[string]$charRange.Font.NameAscii
            bold=($charRange.Font.Bold -eq -1)
            italic=($charRange.Font.Italic -eq -1)
        }
        foreach ($property in @('size_pt','font_east_asia','font_latin','bold','italic')) {
            $expected = $group.properties.$property
            if ($null -eq $expected) { continue }
            $rows.Add(@{paragraph_index=$index; run_index=$runIndex; property=$property;
                parser_value=$expected; word_value=$actual[$property];
                status=$(if ($expected -eq $actual[$property]) {'match'} else {'mismatch'})})
        }
        $alignmentNames = @{0='left';1='center';2='right';3='both';4='distribute'}
        $expectedAlignment = $snapshot.paragraph.alignment
        if ($null -ne $expectedAlignment) {
            $actualAlignment = $alignmentNames[[int]$wp.Format.Alignment]
            $rows.Add(@{paragraph_index=$index; property='alignment'; parser_value=$expectedAlignment;
                word_value=$actualAlignment; status=$(if ($expectedAlignment -eq $actualAlignment) {'match'} else {'mismatch'})})
        }
        if ($snapshot.paragraph.line_rule -eq 'auto' -and $null -ne $snapshot.paragraph.line_value) {
            $expectedLines = $snapshot.paragraph.line_value / 240.0
            $actualLines = switch ([int]$wp.Format.LineSpacingRule) {
                0 {1.0}; 1 {1.5}; 2 {2.0}; 5 {$wp.Format.LineSpacing / $application.LinesToPoints(1)}
                default {$null}
            }
            $rows.Add(@{paragraph_index=$index; property='line_spacing_multiple'; parser_value=$expectedLines;
                word_value=$actualLines; status=$(if ($null -ne $actualLines -and [Math]::Abs($expectedLines-$actualLines) -lt 0.001) {'match'} else {'mismatch'})})
        }
        if ($null -ne $snapshot.paragraph.first_line_indent_chars) {
            $expectedChars = $snapshot.paragraph.first_line_indent_chars / 100.0
            $actualChars = [double]$wp.Format.CharacterUnitFirstLineIndent
            $rows.Add(@{paragraph_index=$index; property='first_line_indent_chars'; parser_value=$expectedChars;
                word_value=$actualChars; status=$(if ([Math]::Abs($expectedChars-$actualChars) -lt 0.001) {'match'} else {'mismatch'})})
        }
    }
    $result = @{
        input_sha256=$before.ToLowerInvariant(); word_version=$application.Version;
        readonly=$document.ReadOnly; xml_body_paragraphs=$xmlParagraphs.Count;
        word_non_table_paragraphs=$wordParagraphs.Count; checks=$rows.ToArray();
        note='Word object-model cross-check; not a human visual sign-off'
    }
} finally {
    if ($null -ne $document) { $document.Close(0) }
    if ($null -ne $application) { $application.Quit(0) }
}
if ((Get-FileHash -LiteralPath $source).Hash -ne $before) { throw 'Source hash changed' }
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $auditPath 'word_crosscheck.json') -Encoding utf8
$rows | Group-Object status | Select-Object Name,Count | Format-Table
