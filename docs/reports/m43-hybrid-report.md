# M4.3 Hybrid 语义裁决实施报告

日期：2026-09-21。版本：0.11.0。

## 模块边界

Hybrid 模块只消费 `AiReviewPlan` 和 `AiReviewRun`，输出独立的 `HybridReview`。它不修改审查计划、模型结果、结构报告或 DOCX，也不授权格式化。

## Policy v1

语义自动接受必须同时满足：规则角色已解析、模型角色已解析、角色一致、规则与模型范围已解析且一致、模型未弃权、置信度达到配置阈值。角色只有一个合法范围时可以确定性补全范围，并记录推导原因。

模型缺失、弃权、低置信、角色/范围冲突、规则未知、范围未知和 manual-only 对象均进入人工复核。阈值默认0.90，但在真实 Gold Set 完成前状态固定为 `provisional_not_accuracy_validated`。

## 真实运行结果

- 输入：现有28项 Hybrid 计划与11项 DeepSeek 有效建议。
- 阈值：0.90。
- 语义自动接受：5项。
- 人工复核：23项，其中包含17个 manual-only 对象。
- 输出：`.paperalign/m4-review/hybrid/2026-09-21-policy-v1/`。
- 使用同一未标注 Gold Set 完成三系统烟雾测试；Rules-only、model_proposal、hybrid 均保持“未评估”。

## 解耦设计

- `HybridDecision` 保存规则与模型各自角色、范围、模型置信度和原因，不覆盖原始判断。
- `HybridReview` 绑定文档哈希、内容指纹、计划模式、Provider、模型、策略版本和阈值。
- M4.2 评测通过可选 `--hybrid` 参数加入第三组指标；没有 Hybrid 文件时原两系统流程不变。
- `hybrid_review.schema.json` 作为模块间契约。

## 验收边界

当前5项“自动接受”只表示策略条件满足，不表示人工证明正确，也不能进入排版。最终阈值、5项结果和人工复核量都要在真实 Gold Set 上确认。

## 验证记录

后端136项测试、Ruff、mypy严格检查63个源文件、Schema同步和diff检查通过。M4.3 没有新增前端行为，前端沿用上一模块已通过的类型检查、组件测试、生产构建和依赖审计。
