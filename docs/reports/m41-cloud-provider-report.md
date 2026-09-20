# M4.1 云端模型 Provider 实施报告

日期：2026-09-21。版本：0.9.0。

## 已实现

- DeepSeek 原生 Responses API 与 OpenAI Responses API 两套适配器，共用 JSON Schema 约束结构角色、规则范围、置信度、弃权、理由和证据引用。
- DeepSeek 请求使用其无服务端会话状态的 Responses 接口且不发送未声明的 `store` 字段；OpenAI 请求固定 `store=false`。两者都不上传整个 DOCX、不使用工具调用。
- DeepSeek 官方说明默认开启思考，且 `max_output_tokens` 同时包含思考与可见输出；当前短分类任务显式设置 `reasoning.effort=none`，避免 500 Token 上限被思考过程占用。是否启用低强度思考留到 M4.2 Gold Set 对照，不凭感觉切换。
- 两道发送闸门：`.env` 中的 `PAPERALIGN_AI_MODE` 必须开启，命令还必须显式包含 `--confirm-send-cloud`。
- 上下文自适应选择：目标段必选，再从父标题、前文和后文中选择最有用的两段；总数不超过 3 段，每段不超过 240 字。
- 截断策略：目标段保留首尾；前文保留尾部；后文保留头部；短文本完整发送，空段不为凑数量而发送。
- 响应绑定 packet、block 和目标文本 SHA-256；越权角色、错误范围、上下文外证据、过期内容和非法 JSON 均拒绝。
- 429、超时和 5xx 可有限重试；最终失败写入脱敏失败码并保留 Rules-only 回退。
- 运行报告记录模型、真实 Token、耗时和可选成本估算，不保存原始 API 响应，不允许 AI 直接排版。
- 结构契约增加 `list_item` 角色，并把 Word 编号存在性、编号层级和绘图存在性作为显式元数据发送，避免只凭文本把列表项误判为标题。

## 为什么不是固定发送 720 字

“最多 3 段、每段 240 字”是安全上限，不是固定配额。标题或题注通常很短，完整文本最有价值；长正文需要首尾语义；相邻空段没有信息价值；当前章节父标题往往比距离更近但无关的段落更能消除歧义。因此上下文按结构信号选择，并将选择原因写入审查包，后续通过 Gold Set 比较误判率。

## 使用顺序

1. 运行 `prepare-ai-review`，人工检查本地 `ai_review_plan.json`。
2. 在仓库根目录的 `.env` 配置 Provider、API Key、模型 ID 和 `PAPERALIGN_AI_MODE=ambiguous_only`。
3. 明确确认计划中不含敏感信息后运行 `run-ai-review --confirm-send-cloud`。
4. 检查 `ai_review_run.json` 的失败、弃权、Token 和耗时；模型建议仍需进入 Hybrid/人工裁决，不能直接修改 DOCX。

## 尚未完成

- DeepSeek 真实联调已于 2026-09-21 完成，详见 [实际测试报告](m41-deepseek-live-test.md)。OpenAI 适配器仍只做了模拟测试。
- 28 个真实歧义入口尚未形成完整人工 Gold Set，不能发布准确率或“最优上下文字数”结论。
- M4.2 仍需实现 Gold Set 评测和 Rules-only、Prompt-only、Hybrid 对照。

## 真实论文本地准备结果

- M3 给出 28 个优先歧义入口。
- 文本证据闸门只为其中 11 个生成云端审查包；17 个空段或纯视觉对象标记为 `manual_review`，不发送给文本模型。
- 11 个审查包合计包含 756 个正文字符；每包最多 3 段，实际单段最长 68 字，未为了达到上限而补充无关内容。
- 本节为准备阶段记录，准备命令没有云端请求；后续已完成付费 API 实测，其用量另见实际测试报告。

## 当前模型定性复核

- 在不调用用户密钥的前提下，使用当前对话模型人工式复核 11 个本地审查包，只记录角色分布，不复制论文片段到报告。
- 结果为 6 个列表项候选、5 个表题候选。该结果暴露出旧契约没有 `list_item`、且没有向模型提供 Word 编号元数据的问题；本轮已补齐这两项。
- 这只是提示词与上下文充分性的定性检查，不是 DeepSeek 实测，也不是人工 Gold Set，不能据此声称准确率。

## 规范依据

- DeepSeek Responses API 文档说明其端点为无服务端会话状态，支持 `text.format=json_schema`，并返回输入、输出与总 Token 用量。
- OpenAI Responses 适配器仍保留严格 Schema 与 `store=false` 行为，便于后续做同一 Gold Set 的 Provider 对照。

## 验证记录

- 后端：127 项测试通过；Ruff 通过；mypy 严格检查 59 个源文件通过；Schema 同步检查通过；Python 依赖检查通过。
- 前端：类型检查通过；1 项组件测试通过；生产构建通过；依赖审计 0 个已知漏洞。
- Provider 模拟测试：使用 MockTransport 验证 DeepSeek 请求路径、鉴权、JSON Schema 请求体、结构化输出解析、Token 统计与失败降级；模拟测试不联网。真实测试另见 [联调报告](m41-deepseek-live-test.md)。
