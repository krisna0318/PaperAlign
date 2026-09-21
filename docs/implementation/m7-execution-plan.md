# M7 执行方案：Word 验证与交付

日期：2026-09-21。状态：已完成。

## 一句总结

把“机器可以证明的安全性”“桌面 Word 可以打开和渲染”“用户确认最终页面”拆成三个独立结论，再交付 DOCX、报告和检查单。

## 三层验证

1. 静态闸门：重新解析原稿和输出，核对文件哈希、内容指纹、包安全、排版报告身份和所有已应用规则。
2. Word 探测：用户选择后，Windows 适配器以只读方式打开输出、重分页并导出 PDF；失败或未安装时返回 `unavailable/failed`，不影响静态证据，但不能声称已完成 Word 验证。
3. 人工验收：无论 Word 探测是否成功，始终生成最终页面检查单。目录域、分页、字体替换、浮动图表和打印效果只有人工确认后才算完成。

## 交付产物

- `PaperAlign-formatted.docx`：新副本，永不覆盖原文。
- `formatting_plan.json` / `formatting_report.json`：批准规则、定位和变更证据。
- `delivery_validation.json`：机器闸门和 Word 探测状态。
- `delivery_checklist.md`：用户逐项确认清单。
- `PaperAlign-word-preview.pdf`：仅在 Word 探测成功时生成。

## 错误语义

Word 不可用不是静态验证失败；静态验证失败则 `delivery_ready=false`。成功导出 PDF 也只表示文件能由 Word 渲染，不表示视觉布局已经人工验收。
