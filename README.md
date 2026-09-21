# PaperAlign

PaperAlign 是一个面向学术论文的可解释格式诊断与安全排版工具。

当前阶段是 **M7：验证与交付**。系统可以上传 DOCX、展示诊断证据，在用户批准后只对已确认的英文缩略词表三线表规则生成新副本，并执行内容指纹、规则复检与可选 Word 探测。其余 244 条暂定规则不会自动修改。

2026-09-21 已完成 DeepSeek 实际联调：11 个审查包全部返回有效建议，使用 16,427 Token；发现 1 个与前次定性复核有分歧的低置信标题候选，尚未进行人工准确率验收。见 [本次测试报告](docs/reports/m41-deepseek-live-test.md)。

文档入口：[文档导航](docs/README.md) · [开发上下文](CONTEXT.md) · [M4 执行方案](docs/implementation/m4-execution-plan.md)。

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
{"status":"ok","service":"paperalign-api","version":"0.14.0","stage":"M7"}
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

内置 Profile 1.1.0 含 248 条原子规则和 46 项 P0 覆盖记录，其中 4 条已确认并接入确定性适配器、244 条暂定且保持只读。第一条命令导出配置与覆盖报告；第二条命令仅用于本地已导入的官方模板，其哈希必须与配置一致。不附带私有模板的干净检出仍可导出 Profile 并运行合成测试。不要把 `verify-template` 当作任意论文诊断命令。

可给 `inspect-profile` 增加 `--school "华南农业大学" --education-level undergraduate --college "软件学院" --cohort current_graduates_at_2026-09-20`，得到适用范围判断。届别标识锚定本次用户确认日期，不自动推断毕业年份。外国语学院及研究生明确不适用；缺少信息或未来届别需复核。不传身份参数时仅导出配置，不猜测用户身份。

模板样本验证输出 `template_rule_checks.json` 和 Markdown 报告，明确 `full_document_evaluated=false`。缩略词表分隔线实际 0.5 pt、批注要求 1 pt，应如实失败；未确认规则返回证据不足。完整实施说明见 [M2.3 报告](docs/reports/m23-profile-report.md)。

## 论文结构识别与人工纠正（M3）

```powershell
.\.venv\Scripts\python.exe -m paperalign classify `
  .\.paperalign\private-test-cases\inputs\private-thesis-before-formatting.docx `
  --out .\.paperalign\m3-review\thesis `
  --include-preview
```

命令生成以下本地产物：

```text
.paperalign/m3-review/thesis/
├─ structure_report.json
├─ structure_summary.md
├─ structure_review.html
├─ manual_review_guide.json
├─ manual_review_guide.md
└─ corrections.template.json
```

双击 `structure_review.html`，先检查“待确认定位”。识别结果保留 Word 定位、角色、规则范围、父级、判断来源与依据；`confidence` 是启发式分数，不是准确率。默认不输出原文，`--include-preview` 只在本地报告中加入每项最多 20 字。报告还会按实际文档对象生成 Word 最终人工复核步骤；系统不能可靠证明的分页问题不会伪装成“已通过”。

如需纠正，复制 `corrections.template.json` 为 `corrections.json`，填写 `reviewer` 和 `decisions`，再运行：

```powershell
.\.venv\Scripts\python.exe -m paperalign classify `
  .\.paperalign\private-test-cases\inputs\private-thesis-before-formatting.docx `
  --out .\.paperalign\m3-review\thesis-corrected `
  --overrides .\.paperalign\m3-review\thesis\corrections.json `
  --include-preview
```

纠正文件绑定输入 SHA-256。未知块、重复纠正、错误角色/对象类型以及角色与规则范围不匹配都会被拒绝；纠正理由保留在 JSON 报告中。系统会重新计算后续分区与标题父级，原 DOCX 和内容指纹保持不变。实现与真实样本结果见 [M3 报告](docs/reports/m3-structure-report.md)。

## 受控 AI 审查（M4.0 / M4.1）

```powershell
.\.venv\Scripts\python.exe -m paperalign prepare-ai-review `
  .\.paperalign\private-test-cases\inputs\private-thesis-before-formatting.docx `
  --out .\.paperalign\m4-review\thesis-hybrid `
  --mode hybrid
```

该命令默认只为 M3 的优先歧义入口准备上下文，最多 3 段、每段最多 240 字。目标段必选，剩余位置优先选择父标题和有信息量的相邻段；短文本不会补齐到 240 字。输出受输入与文本哈希约束，且只能保存在 `.paperalign`。此步骤不连接模型。

确认计划后，在本地 `.env` 配置以下字段；不要把真实 Key 写入命令、聊天、截图或 Git：

```dotenv
PAPERALIGN_AI_MODE=ambiguous_only
PAPERALIGN_AI_PROVIDER=deepseek_responses
PAPERALIGN_AI_BASE_URL=https://api.deepseek.com
PAPERALIGN_AI_API_KEY=your-local-secret
PAPERALIGN_AI_MODEL=deepseek-flash
```

然后显式确认发送：

```powershell
.\.venv\Scripts\python.exe -m paperalign run-ai-review `
  .\.paperalign\m4-review\thesis-hybrid\ai_review_plan.json `
  --out .\.paperalign\m4-review\thesis-cloud-run `
  --confirm-send-cloud
```

DeepSeek 适配器调用其原生、无服务端会话状态的 Responses 接口，并为当前短分类任务设置 `reasoning.effort=none`，避免默认思考过程占用 500 Token 输出上限；OpenAI 适配器则显式设置 `store=false`。这些设置都不能替代对服务商数据政策和账户设置的评估。运行结果只保存校验后的建议、Token、耗时、失败码和可选成本估算，不保存原始 API 响应；任何建议都不能直接触发排版。完整说明见 [M4 执行方案](docs/implementation/m4-execution-plan.md) 和 [M4.1 报告](docs/reports/m41-cloud-provider-report.md)。

## 人工 Gold Set 与评测（M4.2）

先从同一个审查计划生成不含论文原文的标注模板：

```powershell
.\.venv\Scripts\python.exe -m paperalign prepare-gold-set `
  .\.paperalign\m4-review\thesis-hybrid\ai_review_plan.json `
  --out .\.paperalign\m4-review\gold-set-v1
```

复制 `gold_set.template.json` 为 `gold_set.json`，按同目录说明人工填写。未确认项保持 `unassessed`，不会进入准确率。完成部分或全部标注后运行：

```powershell
.\.venv\Scripts\python.exe -m paperalign evaluate-ai-review `
  .\.paperalign\m4-review\thesis-hybrid\ai_review_plan.json `
  .\.paperalign\m4-review\gold-set-v1\gold_set.json `
  .\.paperalign\m4-review\runs\2026-09-21-deepseek-live\ai_review_run.json `
  --out .\.paperalign\m4-review\evaluations\human-v1
```

评测会校验输入哈希、文本哈希、角色与范围、证据引用以及运行身份，分别报告 Rules-only 和模型建议的覆盖、角色/范围准确率、分歧、Token 与耗时。模型建议不能反向生成 Gold Set。详见 [M4.2 报告](docs/reports/m42-gold-set-report.md)。

## Hybrid 语义裁决（M4.3）

```powershell
.\.venv\Scripts\python.exe -m paperalign adjudicate-review `
  .\.paperalign\m4-review\thesis-hybrid\ai_review_plan.json `
  .\.paperalign\m4-review\runs\2026-09-21-deepseek-live\ai_review_run.json `
  --out .\.paperalign\m4-review\hybrid\policy-v1 `
  --confidence-threshold 0.9
```

规则和模型必须在角色与范围上完全一致，模型未弃权且达到阈值，系统才会自动接受语义；其余结果进入人工复核。唯一范围可由角色确定性补全，例如 `list_item → body`。策略状态始终记录为尚未通过 Gold Set 校准，输出也固定 `formatting_allowed=false`。实现说明见 [M4.3 报告](docs/reports/m43-hybrid-report.md)。

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
3. M2：华农规则 Profile（核心配置已完成，规则确认持续进行）；
4. M3：Rules-only 结构识别（核心流程已完成）；
5. M4：Prompt-only 与 Hybrid 对照（M4.3 Hybrid 裁决已完成，真实人工标注和策略校准待完成）；
6. M5–M7：诊断界面、安全排版与 Word 最终验证。

## License

MIT
