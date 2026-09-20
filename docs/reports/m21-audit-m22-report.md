# M2.1 本地审计与 M2.2 规则模型交付报告

> 日期：2026-09-20；应用版本：0.5.0；规则契约：2.0。
> 已完成代码与属性抽查；页面视觉验收待完成。当前改动保留在本地，未推送。

## 一句话说明

系统已能生成可逐段核对的本地格式审计页，并把实际格式转换成带明确单位的规则输入；规则在未经人工确认或实际格式无法确定时，会被阻止进入合规判定。

## 本地审计工具

仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -m paperalign audit-template `
  .\.paperalign\private-test-cases\inputs\scau-official-template.docx `
  --out .\.paperalign\manual-checks\scau-m21 `
  --include-preview
```

双击输出目录中的 `format_audit.html` 即可在本地浏览器查看。每段可展开查看字体、字号、对齐、行距、缩进、生效来源和未解析说明；“原始声明与 JSON”展示段落直接声明及完整快照。段落索引从 0 开始，对应 `word/document.xml` 下正文直接子段落，不能当作 Word 页码或包括表格的 Paragraphs 索引。

`--include-preview` 是显式启用开关，每段最多 20 字。未指定时预览为空；`inspect-template` 仍不输出正文。审计命令限制输出在仓库 `.paperalign` 目录下，该目录被 Git 忽略。HTML 不引用外部资源，模板文本经过转义，并禁止页面执行脚本。

已生成：

- `.paperalign/manual-checks/scau-m21/`：官方模板，249 个正文层段落、4 张表格，含短预览。
- `.paperalign/manual-checks/thesis-m21/`：论文原稿，489 个正文层段落、11 张表格，不含短预览。

## 属性抽查证据

使用本机 Word 16.0，通过独立隐藏实例只读打开官方模板，先验证 OOXML 段落与 Word 段落文字完全一致，再对照对应文字片段及段落属性。原文件前后 SHA-256 保持一致：

`bcac55ef57164ac1c18eeb7a5f563be37cf730947e9fb3c1703e660ba20b8322`

抽取的正文层段落索引：`1, 3, 38, 39, 41, 42, 45, 46, 74, 75, 76, 86, 90`，覆盖封面、中文摘要、关键词、英文题目与摘要、各级标题、正文和表题。

| 核对属性 | 检查数 | 一致数 |
|---|---:|---:|
| 中文字体、ASCII 字体、字号、粗体、斜体 | 65 | 65 |
| 段落对齐 | 13 | 13 |
| 倍数行距 | 11 | 11 |
| 字符首行缩进 | 3 | 3 |
| 合计 | 92 | 92 |

证据位于 `.paperalign/manual-checks/scau-m21/word_crosscheck.json`。可复跑：

```powershell
.\scripts\verify-word-format.ps1 `
  -InputPath .\.paperalign\private-test-cases\inputs\scau-official-template.docx `
  -AuditDirectory .\.paperalign\manual-checks\scau-m21
```

抽查代表项：

| 段落索引 | 用途 | 抽查结果 |
|---|---|---|
| 1 | 封面文档类别 | 36 pt，中文宋体；ASCII 继承 Times New Roman，不能被 hAnsi 的宋体覆盖 |
| 39 | 中文摘要正文 | 12 pt 来自段落样式 50，两端对齐、1.5 倍行距 |
| 74 | 一级标题 | 14 pt 来自文字直接设置，左对齐 |
| 76 | 正文 | 12 pt、宋体、首行 2 字符、1.5 倍行距 |
| 86 | 表题 | 10.5 pt 来自段落样式 1，居中 |
| 90 | 三级标题示例 | 实际中文字体为黑体；与 P0 清单中批注要求的楷体应作为后续规则偏差核对，不能改写观察值 |

这是代理逐项审查结合 Word 对象模型的独立交叉验证，不是用户人工签字，也不等于全部页面、全部 run 或全部属性均已验收。每个抽查段落核对首个可见格式组的样本字符；混合格式的完整覆盖仍需扩展。

## 抽查中发现并修复的问题

1. **ASCII 与 hAnsi 混用**：旧解析器用 hAnsi 补 ASCII，真实封面首次核对出现差异。现分别输出 `font_latin` 与 `font_high_ansi`，保留各自继承来源。
2. **样式 toggle 属性**：样式内粗斜体按反转语义叠加，直接格式仍是绝对开关；新增合成继承链回归。
3. **不能确定的属性**：主题字体、按行计段距/自动段距、悬挂缩进分别标记未解析，不再把低优先级数值显示为已确定。
4. **英文题目前分页符**：Word 核对脚本计入分页符，避免把正确段落误报为映射失败。
5. **验收脚本可靠性**：显式检查每个外部命令退出码；Schema 与当前模型比较，而非与 Git 提交比较；每次使用仓库内独立临时目录，避免不同运行身份造成旧缓存权限冲突。

## M2.2 已交付能力

- `FormatRule` 升为 `schema_version=2.0`，`scope` 与 `property_path` 限定为已登记值。
- `expected_value` 使用数值、文本、布尔、行距四类带类型数据；限制字号、页面尺寸、整数计数等的取值范围。
- 页面用 mm、字号和段距用 pt、字符缩进用 chars；解析层保留 OOXML 原始单位。
- 倍数行距使用 `mode=multiple, unit=lines`；固定或最小行距使用 `mode=exact/at_least, unit=pt`。
- 保留 `display_alias` 展示中文字号，别名不参与运算。
- 每条规则保留来源文件、定位器、可选文件哈希；confirmed 必须附带人工确认记录。
- 学校批注/文字要求优先于实际模板观察；同级证据冲突返回 needs_review，保留全部候选；选择证据不会自动确认规则。
- 预检函数：暂定规则返回 evidence_insufficient；已确认规则但实际值缺失、不支持或单位不兼容时返回 not_evaluated。
- 预检返回空仅代表“可以交给后续属性验证器”，绝不等于 pass。
- 有效格式到原子观察值的适配器已接入，保留来源；遇到多个文字格式组必须明确指定目标组，不擅自选第一组。
- JSON Schema 与前端类型同步；测试同时检查 Pydantic 与 JSON Schema 对错误单位、类型、状态及字段的拒绝行为。

`pass/fail` 的最终比较器属于 M2.4，当前只建立数据契约与判定前置条件。跨页图表关系、文献顺序等复合要求尚未编码为 P0 规则，不属于本次模型完成声明。

## 验收结果与限制

`scripts/test.ps1` 已完整执行成功：后端 52 项测试，Ruff、严格 mypy、依赖一致性、Schema 校验全部通过；前端类型检查、1 项测试、生产构建通过；npm audit 报告 0 个漏洞。

浏览器工具的 URL 安全策略禁止打开本地 `file://` 审计页，因此未取得浏览器截图或视觉通过结论。HTML 的结构、转义、预览开关和确定性有自动测试。用户可以本地双击页面进行视觉复核。

尚未覆盖完整的表格单元格、页眉页脚、脚注、复杂编号/条件样式级联及 Word 分页布局。真实样本运行成功不是“论文格式全部正确”的结论。

## 下一阶段与待确认项

M2.3 建立版本化 Profile、manifest、原子规则及证据索引；M2.4 才实现属性比较；M2.5 建立已定位真实样本的正反例。

正式启用 confirmed 学校规则前，需要用户确认当前模板适用的届别和学院、有无学院补充要求。页码分节、标题粗体、上下空行的等价实现等未确定项继续留在 P0 待确认清单中；不妨碍建立 provisional Profile。

## 技术依据

- [Microsoft Open XML：Bold](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.bold?view=openxml-3.0.1)：粗体的继承与 toggle 属性说明。
- [Microsoft Open XML：SpacingBetweenLines.Line](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.spacingbetweenlines.line?view=openxml-3.0.1)：倍数行距的 1/240 单位解释。
