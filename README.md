# PaperAlign

PaperAlign 是一个面向学术论文的可解释格式诊断与安全排版工具。

当前阶段是 **M2：格式模板证据与规则 Profile**。M1 的 DOCX 只读分析已经完成；项目现在可以在不依赖批注的情况下提取模板页面、样式、表格边框证据，并解析正文段落的有效格式及来源。当前仍不会修改或排版 DOCX。

## MVP 边界

- 首个 Profile：现有华南农业大学模板，适用于当前应届本科生，排除外国语学院和研究生；不扩展学院定制；
- 用户稿件：仅 `.docx`；
- AI：用于语义识别和歧义处理，不直接修改 Word；
- 格式修改：由确定性规则引擎执行；
- 安全原则：不覆盖原文件，真实论文不进入 Git，所有结论保留来源。

## 仓库结构

```text
frontend/    Vue 3 + TypeScript + Vite 本地界面
backend/     FastAPI、领域模型与后续文档流水线
schemas/     对外稳定的 JSON Schema
docs/        产品、架构、决策与研究文档
evaluation/  Prompt-only、Rules-only、Hybrid 的统一评测
scripts/     Windows 本地开发和测试脚本
data/        本地数据说明；真实数据不会进入 Git
```

## 环境要求

- Git
- Python 3.12 或 3.13
- Node.js 20 或更新兼容版本
- npm 10 或更新兼容版本

## 后端启动

在仓库根目录执行：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

打开 `http://127.0.0.1:8000/health`，应返回：

```json
{"status":"ok","service":"paperalign-api","version":"0.6.0","stage":"M2"}
```

## DOCX 只读分析

```powershell
.\.venv\Scripts\python.exe -m paperalign analyze `
  .\path\to\anonymized-thesis.docx `
  --out .\.artifacts\sample
```

输出：

```text
.artifacts/sample/
├─ document_profile.json
├─ content_fingerprint.json
├─ unsupported_objects.json
└─ analysis_summary.md
```

分析器会验证 DOCX 包完整性和安全上限，读取段落、表格、样式、图片、字段、分节、页眉页脚及脚注等结构，并在分析前后比对输入文件 SHA-256。宏、ActiveX、OLE、嵌入包、altChunk、外部关系、文本框、公式、修订等对象会被显式报告。

## 格式模板证据提取

```powershell
.\.venv\Scripts\python.exe -m paperalign inspect-template `
  .\path\to\official-template.docx `
  --out .\.artifacts\template-evidence
```

输出 `template_evidence.json` 和 `template_evidence_summary.md`。命令不要求模板含有批注，会从 DOCX 的分节、样式使用、直接格式和表格边框中提取观察值；同时按“文档默认值 → 基础样式 → 派生段落样式 → 字符样式 → 直接格式”解析正文段落的有效格式，并为每个属性保留来源。观察值不会自动升级为学校规则，也不会复制模板正文。表格边框同时保留 OOXML 原始值，并将 `w:sz` 按 1/8 pt 换算为磅。

## 本地逐段审计（M2.1）

```powershell
.\.venv\Scripts\python.exe -m paperalign audit-template `
  .\path\to\official-template.docx `
  --out .\.paperalign\manual-checks\template `
  --include-preview
```

本地双击 `format_audit.html`，展开段落查看实际值、来源和未解析原因。预览默认关闭，指定开关后每段最多展示 20 字；审计产物只允许放在被 Git 忽略的 `.paperalign` 目录。标准 `inspect-template` 报告仍不包含正文。

M2.2 已完成单位、类型、证据优先级和判定前置条件建模，规则契约升级为 2.0。完整说明见 [审计与 M2.2 报告](docs/reports/m21-audit-m22-report.md) 和 [规则契约](docs/architecture/rule-contract-v2.md)。此时仍没有整篇论文合规比较器或自动排版。

## 单模板规则配置与样本验证（M2.3 / M2.4 基础）

```powershell
.\.venv\Scripts\python.exe -m paperalign inspect-profile `
  --out .\.paperalign\profile-review

.\.venv\Scripts\python.exe -m paperalign verify-template `
  .\.paperalign\private-test-cases\inputs\scau-official-template.docx `
  --out .\.paperalign\profile-review\scau-template
```

内置 Profile 1.0.0 含 248 条原子规则和 46 项 P0 覆盖记录，其中 4 条已确认、244 条暂定。第一条命令导出配置与覆盖报告；第二条命令仅用于本地已导入的官方模板，其哈希必须与配置一致。不附带私有模板的干净检出仍可导出 Profile 并运行合成测试。不要把 `verify-template` 当作任意论文诊断命令。

可给 `inspect-profile` 增加 `--school "华南农业大学" --education-level undergraduate --college "软件学院" --cohort current_graduates_at_2026-09-20`，得到适用范围判断。届别标识锚定本次用户确认日期，不自动推断毕业年份。外国语学院及研究生明确不适用；缺少信息或未来届别需复核。不传身份参数时仅导出配置，不猜测用户身份。

模板样本验证输出 `template_rule_checks.json` 和 Markdown 报告，明确 `full_document_evaluated=false`。缩略词表分隔线实际 0.5 pt、批注要求 1 pt，应如实失败；未确认规则返回证据不足。完整实施说明见 [M2.3 报告](docs/reports/m23-profile-report.md)。

## 前端启动

```powershell
Set-Location .\frontend
npm install
npm run dev
```

默认访问 `http://127.0.0.1:5173`。

## 测试与检查

```powershell
.\scripts\test.ps1
```

也可以分别执行：

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests
.\.venv\Scripts\python.exe -m ruff check .\backend
.\.venv\Scripts\python.exe -m mypy .\backend\app

Set-Location .\frontend
npm run typecheck
npm run test
npm run build
```

## 数据安全

- 不要将真实论文放入仓库；
- `data/` 只保留说明文件，实际内容会被忽略；
- `.paperalign/`、`.artifacts/` 和 `outputs/` 是本地任务产物；
- `.env` 和 API Key 不得提交；
- 测试文档必须是合成数据或经过人工脱敏。

## 近期路线

1. M0：仓库、环境、健康检查、数据模型（已完成）；
2. M1：DOCX 只读画像、内容指纹、不支持对象报告（已完成）；
3. M2：华农规则 Profile；
4. M3：Rules-only 结构识别；
5. M4：Prompt-only 与 Hybrid 对照；
6. M5–M7：诊断界面、安全排版与 Word 最终验证。

## License

MIT
