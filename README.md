# PaperAlign

PaperAlign 是一个面向学术论文的可解释格式诊断与安全排版工具。

当前阶段是 **M1：DOCX 只读分析**。项目可以生成文档画像、内容指纹、不支持对象报告和分析摘要，**尚不能判断论文格式是否合规，也不会修改或排版 DOCX**。

## MVP 边界

- 首个 Profile：华南农业大学本科毕业论文；
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
{"status":"ok","service":"paperalign-api","version":"0.2.0","stage":"M1"}
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
