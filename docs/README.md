# PaperAlign 文档导航

更新：2026-09-21。当前阶段 M5 已完成本地只读诊断界面，下一开发模块是 M6 确定性安全排版；真实 Gold Set 人工标注仍是验收项。

## 从这里开始

| 目的 | 入口 |
| --- | --- |
| 启动、测试与调用方式 | [仓库 README](../README.md) |
| 接续开发，了解已经确认的决策 | [CONTEXT](../CONTEXT.md) |
| 查看本次真实调用结果与待解决问题 | [DeepSeek 联调报告](reports/m41-deepseek-live-test.md) |
| 查看 Gold Set 和评测运行器 | [M4.2 评测报告](reports/m42-gold-set-report.md) |
| 查看 Hybrid 裁决策略 | [M4.3 裁决报告](reports/m43-hybrid-report.md) |
| 查看三模式收口边界 | [M4.4 收口报告](reports/m44-evaluation-closeout.md) |
| 查看本地诊断界面 | [M5 实施报告](reports/m5-diagnostic-ui-report.md) |
| 了解下一步开发顺序 | [M4 执行方案](implementation/m4-execution-plan.md) |
| 查看范围与里程碑 | [MVP 范围](product/mvp-scope.md) |

## 目录职责

| 目录 | 内容 |
| --- | --- |
| `product/` | 产品定义、用户流程、范围、华农 P0 规则清单 |
| `architecture/` | 系统概览、数据模型、规则契约及早期架构决策 |
| `decisions/` | 单模板等产品决策记录 |
| `implementation/` | 各阶段执行方案 |
| `reports/` | 各阶段实施与验收证据；以日期和报告范围为准 |
| `interview/` | 面试讲解材料 |
| `research/` | 外部调研资料 |
| `../evaluation/` | 评测设计；后续加入脱敏/合成 Gold Set 与运行器 |

## 已有阶段证据

- M1：[只读解析报告](reports/m1-implementation-report.md)。
- M2：[模板证据](reports/m2-template-evidence-report.md)、[有效格式](reports/m2-effective-format-report.md)、[审计与规则契约](reports/m21-audit-m22-report.md)、[规则 Profile](reports/m23-profile-report.md)。
- M3：[结构识别报告](reports/m3-structure-report.md)。
- M4：[人工复核与隐私边界](reports/m40-review-safety-report.md)、[Provider 实施](reports/m41-cloud-provider-report.md)、[DeepSeek 实际联调](reports/m41-deepseek-live-test.md)、[Gold Set 与评测运行器](reports/m42-gold-set-report.md)、[Hybrid 裁决](reports/m43-hybrid-report.md)。

早期报告保留当时的测试记录；最新开发状态以 CONTEXT 和最新测试报告为准。

## 本地文件约定

真实 DOCX、含论文片段的计划和模型建议保存在 Git 忽略的 `.paperalign/`；密钥仅在 `.env`。本次结果放在 `.paperalign/m4-review/runs/2026-09-21-deepseek-live/`，历史资料保留原路径，避免已有测试命令失效。`.paperalign/README.md` 提供本机导航。
