# M4.0 人工复核与 AI 审查包实施报告

日期：2026-09-20。版本：0.8.0。

## 本轮交付

- `classify` 新增 `manual_review_guide.json` 和 `manual_review_guide.md`，结构审查 HTML 直接展示客户注意事项与 Word 操作步骤。
- 指南按文档实际对象生成：最终打印布局为必检项；目录/域、图与图题、跨页表格、分节页码、复杂对象按需出现。
- 新增 `prepare-ai-review`，可生成 Hybrid 或 Prompt-only 的本地审查包；当前不连接模型。
- 新增 AI 请求与响应 Schema。响应必须绑定 packet、block 和文本哈希，只能使用允许的角色/范围并引用已提供上下文。
- 文档正文被视为不可信数据；提示指令要求忽略论文中可能出现的命令式文本。

## 当前命令

```powershell
.\.venv\Scripts\python.exe -m paperalign prepare-ai-review `
  .\.paperalign\private-test-cases\inputs\private-thesis-before-formatting.docx `
  --out .\.paperalign\m4-review\thesis-hybrid `
  --mode hybrid
```

输出 `ai_review_plan.json`。文件含少量论文片段，必须保留在 Git 已忽略的 `.paperalign` 目录。控制台必须显示 `No model was contacted`。

## 明确未完成

- 未选择或调用真实模型 Provider。
- 未把 AI 建议合并回结构结果。
- 未完成 Rules-only、Prompt-only、Hybrid 的准确率对照。
- 未生成排版后的 DOCX。
- 人工复核指南不能替代学校或导师的最终验收。

## 下一步

先用真实论文的 28 个优先入口完成人工 Gold Set，再接 Provider 适配器和离线 Mock，记录 Token、耗时与失败降级。真实 API 调用需要用户先确认隐私边界和模型来源。
