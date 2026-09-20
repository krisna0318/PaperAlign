# M4.2 Gold Set 与评测运行器实施报告

日期：2026-09-21。版本：0.10.0。

## 本阶段解决的问题

M4.1 证明了云端模型可以返回合法建议，但合法响应不等于正确结果。M4.2 将“正确答案”从模型与规则中独立出来：只有人工结合原 DOCX、学校规范和 Word 结构确认的标签，才能进入准确率统计。

## 已实现

- `prepare-gold-set` 从审查计划生成无论文原文的标注模板，覆盖可发送审查包和 manual-only 项。
- 每项绑定 block ID 与文本 SHA-256；模板同时绑定文档 SHA-256、内容指纹和计划模式。
- `unassessed` 不允许携带半成品答案；`confirmed` 必须填写角色、标注人和依据，格式范围允许保留未知。
- `evaluate-ai-review` 重新校验计划、Gold Set、模型运行、packet、文本哈希、角色/范围和证据引用。
- 输出 Rules-only 与模型建议的覆盖、角色准确率、Precision/Recall/F1、范围准确率、弃权/缺失、分歧数、Token 和耗时。
- 没有人工标签时，准确率字段输出 null，摘要显示“未评估”；不会根据模型置信度生成正确率。
- JSON Schema 已加入 `gold_set.schema.json` 与 `evaluation_report.schema.json`；仓库测试使用合成 DOCX 和合成标签。

## 真实文档本地运行

- 从现有 Hybrid 计划生成 28 项模板：11 个 cloud_packet，17 个 manual_only。
- 模板保存于 `.paperalign/m4-review/gold-set-v1/`，不进入 Git。
- 使用未标注模板和现有 DeepSeek 运行结果完成零标签烟雾测试；结果为 `no_confirmed_labels`，0/28 进入评测，两个系统的准确率均为“未评估”。
- 基线保存于 `.paperalign/m4-review/evaluations/2026-09-21-no-label-baseline/`。

## 指标口径

- 覆盖：有非弃权角色预测的已标注对象 / 已标注对象。
- 角色准确率：角色正确数 / 已标注对象，缺失与弃权计为未命中。
- Precision：角色正确数 / 有角色预测数；Recall：角色正确数 / 已标注对象；F1 为二者调和平均。
- 范围准确率只统计人工明确填写 expected_scope 的对象。
- 分歧数包含缺失、弃权、角色错误，以及已标注范围时的范围错误。
- 当前模型运行来自 Hybrid 计划，提示中包含规则建议，因此报告名称使用 `model_proposal`，不能冒充 Prompt-only。Prompt-only 需要另建不含规则建议的计划并单独调用。

## 尚未完成

- 真实28项仍未人工标注，当前不能报告准确率或选择自动放行阈值。
- M4.3 需要实现 Hybrid 裁决策略，并在同一 Gold Set 上加入第三组结果。
- 内容保持率属于后续确定性排版验收指标；只读结构分类阶段没有修改 DOCX，因此不在本评测中伪造该指标。

## 验证记录

- 后端132项测试通过；Ruff、mypy严格检查61个源文件、Schema同步与Python依赖检查通过。
- 前端类型检查、1项组件测试、生产构建通过；npm审计0个已知漏洞。
- `git diff --check` 通过；待提交文件未发现形如API密钥的内容；`.env`、真实运行结果和Gold Set模板均经Git忽略规则确认。

## 下一步操作

复制本地 `gold_set.template.json` 为 `gold_set.json`，按同目录 `annotation_instructions.md` 标注。优先确认 `p-0123` 的列表/四级标题争议，以及三个 selected_scope 缺失项。完成部分标签即可运行评测；未完成项会继续保留为未评估。
