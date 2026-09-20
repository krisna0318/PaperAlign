# Evaluation

M4 将在同一套脱敏或合成数据上比较：

- Prompt-only；
- Rules-only；
- Hybrid。

首批指标包括结构分类 Precision/Recall/F1、unknown 比例、用户确认数量、Token、延迟和内容保持率。

M4.2 已实现 Gold Set 模板和评测运行器。真实论文标签及报告保存在 Git 忽略的 `.paperalign/m4-review/`；仓库只提交 Schema、合成测试和汇总文档。人工未确认项不参与准确率。

当前评测输出覆盖 Rules-only 和一次模型运行。Prompt-only 必须用不含规则建议的独立计划和运行结果；Hybrid 裁决将在 M4.3 加入，不能把当前 `hybrid` 审查包的模型输出误称为 Prompt-only。
