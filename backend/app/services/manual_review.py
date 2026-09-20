# ruff: noqa: E501
"""Generate honest Word completion instructions for checks OOXML cannot prove."""

from app.domain.enums import SemanticRole
from app.domain.manual_review import ManualReviewGuide, ManualReviewItem, ManualReviewStep
from app.domain.structure import StructureReport


def _step(order: int, instruction: str, expected: str) -> ManualReviewStep:
    return ManualReviewStep(order=order, instruction=instruction, expected_result=expected)


def build_manual_review_guide(report: StructureReport) -> ManualReviewGuide:
    """Create only applicable manual checks, plus the mandatory final page review."""

    roles: dict[SemanticRole, list[str]] = {}
    for decision in report.decisions:
        roles.setdefault(decision.role, []).append(decision.block_id)

    items = [
        ManualReviewItem(
            id="final-layout-visual-check",
            category="final_layout",
            title="使用 Microsoft Word 完成最终页面检查",
            customer_notice=(
                "PaperAlign 可以检查和修改 DOCX 中的结构化格式，但当前不能保证不同 Word 版本、"
                "字体环境和打印机驱动下的最终分页完全一致。提交前必须在目标电脑的 Word 中复核。"
            ),
            reason="OOXML 保存格式规则，不保存一份跨环境固定不变的最终分页结果。",
            steps=[
                _step(1, "先另存排版副本，不在原稿上直接操作。", "原稿和排版副本同时保留。"),
                _step(
                    2,
                    "在目标电脑安装学校要求的字体，再用桌面版 Microsoft Word 打开副本。",
                    "Word 不显示缺失字体或字体替换提示。",
                ),
                _step(
                    3,
                    "按 Ctrl+A 全选，再按 F9 更新全部域；如出现目录提示，选择“更新整个目录”。",
                    "目录、页码和交叉引用显示为最新结果。",
                ),
                _step(
                    4,
                    "切换到“视图→打印布局”，从封面逐页检查到文末。",
                    "没有意外空白页、孤立标题、遮挡、溢出或页边距异常。",
                ),
                _step(
                    5,
                    "使用“文件→另存为”导出 PDF，并再次核对总页数和关键页。",
                    "DOCX 与 PDF 的章节起始、图表位置和页码一致。",
                ),
            ],
            acceptance_checks=[
                "论文能正常打开且 Word 未报告修复内容",
                "标题没有单独落在页尾",
                "正文、图表、公式没有被裁切或遮挡",
                "最终 PDF 与 Word 页码一致",
            ],
        )
    ]

    toc_ids = roles.get(SemanticRole.TABLE_OF_CONTENTS, [])
    if toc_ids:
        items.append(
            ManualReviewItem(
                id="toc-and-fields-update",
                category="toc_and_fields",
                title="更新目录、页码和交叉引用",
                customer_notice="目录和页码属于 Word 动态域，静态 XML 检查不能确认更新后的页码是否正确。",
                reason="正文重排会改变分页，只有 Word 排版引擎更新域后才能得到最终结果。",
                related_block_ids=toc_ids,
                steps=[
                    _step(
                        1,
                        "在目录内单击，然后选择“引用→更新目录→更新整个目录”。",
                        "目录标题和页码同时刷新。",
                    ),
                    _step(
                        2,
                        "按 Ctrl+A 后按 F9，更新正文中的交叉引用、编号和其他域。",
                        "域不再显示旧页码或“错误!未找到引用源”。",
                    ),
                    _step(
                        3,
                        "逐项点击目录中的一级标题并与正文起始页比对。",
                        "目录页码与正文页面一致。",
                    ),
                ],
                acceptance_checks=[
                    "目录无缺项或重复项",
                    "目录页码与正文逐项对应",
                    "没有域错误提示",
                ],
            )
        )

    figure_ids = roles.get(SemanticRole.FIGURE, []) + roles.get(SemanticRole.FIGURE_CAPTION, [])
    if figure_ids:
        items.append(
            ManualReviewItem(
                id="figure-caption-pagination",
                category="figure_pagination",
                title="检查图片与图题是否同页",
                customer_notice="PaperAlign 当前不能自动承诺浮动图片、环绕方式和图题在最终分页中始终同页。",
                reason="浮动锚点和可用页面空间由 Word 在打开文档时重新计算。",
                related_block_ids=figure_ids,
                steps=[
                    _step(
                        1,
                        "打开“开始→¶ 显示/隐藏编辑标记”，定位图片所在段落和紧随其后的图题段落。",
                        "能够看清图片锚点及两个段落的边界。",
                    ),
                    _step(
                        2,
                        "优先将图片设置为“与文字在一行”；确需浮动时，固定锚点并检查文字环绕。",
                        "图片不会因正文增减跳到其他章节。",
                    ),
                    _step(
                        3,
                        "选中图片所在段落，打开“段落→换行和分页”，勾选“与下段同页”。",
                        "图片段落会与后面的图题一起移动。",
                    ),
                    _step(
                        4,
                        "选中图题段落，勾选“段中不分页”，再检查前后页。",
                        "图题完整显示且不与图片分离。",
                    ),
                ],
                acceptance_checks=["每幅图和对应图题位于同一页", "图题编号连续", "图片未覆盖正文"],
            )
        )

    table_ids = roles.get(SemanticRole.TABLE, []) + roles.get(SemanticRole.ABBREVIATION_TABLE, [])
    if table_ids:
        items.append(
            ManualReviewItem(
                id="table-pagination",
                category="table_pagination",
                title="检查表格跨页与重复表头",
                customer_notice="表格在不同页面剩余空间中的拆分结果需要在 Word 打印布局中人工确认。",
                reason="行高、单元格内容和页面剩余空间共同决定跨页位置。",
                related_block_ids=table_ids,
                steps=[
                    _step(1, "选中表格，打开“表格属性→行”。", "显示当前行的跨页设置。"),
                    _step(
                        2,
                        "对不允许拆开的数据行取消“允许跨页断行”；不要给整张超长表设置固定行高。",
                        "单行内容不会被截到两页。",
                    ),
                    _step(
                        3,
                        "选中首行，在“表格布局”中启用“重复标题行”。",
                        "跨页后的每页顶部都出现表头。",
                    ),
                    _step(
                        4,
                        "逐页检查续表标题、表头、边框和表后正文位置。",
                        "续页语义清楚且没有空白页。",
                    ),
                ],
                acceptance_checks=[
                    "数据行未被异常拆分",
                    "跨页表格有重复表头",
                    "表题及续表标识符合学校要求",
                ],
            )
        )

    if len({d.section_id for d in report.decisions if d.section_id}) > 1 or toc_ids:
        items.append(
            ManualReviewItem(
                id="section-page-numbering",
                category="section_page_numbering",
                title="检查分节符与页码起始值",
                customer_notice="页眉页脚的节间链接和页码起始值必须结合最终页面人工核对。",
                reason="同一页眉页脚可继承前一节，错误链接通常不会在纯文本诊断中显现。",
                steps=[
                    _step(
                        1,
                        "开启“¶ 显示/隐藏编辑标记”，确认封面、目录和正文边界使用分节符，而不是连续空行。",
                        "关键区域之间存在正确的分节符。",
                    ),
                    _step(
                        2,
                        "双击页眉或页脚，逐节检查“链接到前一节”是否符合模板要求。",
                        "各节页眉页脚不会被意外联动修改。",
                    ),
                    _step(
                        3,
                        "打开“页码→设置页码格式”，检查罗马数字/阿拉伯数字及起始页码。",
                        "目录和正文采用正确编号体系与起始值。",
                    ),
                ],
                acceptance_checks=[
                    "封面不出现不应有的页码",
                    "目录与正文页码体系正确",
                    "正文第一页起始值正确",
                ],
            )
        )

    if report.unsupported_object_counts:
        items.append(
            ManualReviewItem(
                id="unsupported-object-preservation",
                category="unsupported_objects",
                title="复核系统未安全处理的复杂对象",
                customer_notice="文档包含 PaperAlign 不会自动修改的复杂 Word 对象；系统会保留并要求人工复核。",
                reason="文本框、修订、嵌入对象等结构的编辑可能破坏内容或版面。",
                steps=[
                    _step(
                        1,
                        "根据 unsupported_objects.json 的部件和对象类型定位原稿中的复杂对象。",
                        "每个报告对象都能在原稿或 Word 导航窗格中找到。",
                    ),
                    _step(
                        2,
                        "并排打开原稿和排版副本，比较对象内容、位置、大小和可编辑性。",
                        "对象未丢失、未替换、未移动。",
                    ),
                    _step(
                        3,
                        "若对象异常，保留原稿中的该对象并手工完成附近排版，不继续自动修改。",
                        "异常范围被隔离且原始内容可恢复。",
                    ),
                ],
                acceptance_checks=[
                    "复杂对象数量与原稿一致",
                    "对象仍可打开或编辑",
                    "对象附近正文未丢失",
                ],
            )
        )

    return ManualReviewGuide(
        input_sha256=report.input_sha256,
        content_fingerprint=report.content_fingerprint,
        scope_statement=(
            "本指南仅覆盖系统无法从 DOCX 静态结构可靠证明的最终页面事项；"
            "它不是学校格式合格证明，也不会修改原始论文。"
        ),
        word_desktop_required=True,
        items=items,
    )


def render_manual_review_markdown(guide: ManualReviewGuide) -> str:
    lines = [
        "# PaperAlign 最终人工复核指南",
        "",
        f"> {guide.scope_statement}",
        "",
        "## 给用户的统一说明",
        "",
        "PaperAlign 会自动处理能够被明确规则描述和安全验证的格式。对于最终分页、动态域、"
        "浮动对象和复杂 Word 对象，系统不会伪造“已通过”结论，而是列出必须完成的人工步骤。",
    ]
    for item in guide.items:
        lines.extend(
            [
                "",
                f"## {item.title}",
                "",
                f"**注意事项：** {item.customer_notice}",
                "",
                f"**为什么需要人工处理：** {item.reason}",
                "",
                "### 操作步骤",
                "",
            ]
        )
        lines.extend(
            f"{step.order}. {step.instruction} 预期结果：{step.expected_result}"
            for step in item.steps
        )
        lines.extend(["", "### 验收检查", ""])
        lines.extend(f"- [ ] {check}" for check in item.acceptance_checks)
    lines.append("")
    return "\n".join(lines)
