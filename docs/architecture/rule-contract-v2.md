# M2.2 原子规则契约 2.0

一句话：每条规则只描述一个已定位对象的一项属性，用明确单位保存期望值，用独立状态表达证据是否足够。

## 最小示例

```json
{
  "schema_version": "2.0",
  "id": "SCAU-P0-BODY-SIZE",
  "profile_id": "scau_undergraduate_2026_v1",
  "scope": "body",
  "property_path": "run.size_pt",
  "expected_value": {"kind": "number", "value": 12.0, "unit": "pt"},
  "display_alias": "小四",
  "comparison": "eq",
  "tolerance": 0.0,
  "status": "provisional",
  "confidence": 0.9,
  "source": {
    "type": "school_comment",
    "document": "scau-official-template.docx",
    "evidence": "正文小四号",
    "locator": "template_comment:23",
    "document_sha256": "bcac55ef57164ac1c18eeb7a5f563be37cf730947e9fb3c1703e660ba20b8322"
  },
  "implementation": "read_only",
  "validator": "numeric_equal",
  "priority": "P0",
  "auto_fixable": false
}
```

这是模型示例，尚未作为已确认规则装载；validator 是后续 M2.4 实现的标识。

## 单位和比较

| 对象 | 规范单位 | 解析层转换 |
|---|---|---|
| 页面尺寸与页边距 | mm | twip × 25.4 / 1440 |
| 字号、段距、长度缩进、表格线宽 | pt | 段距等 twip / 20；边框 eighth-point / 8 |
| 字符缩进 | chars | OOXML 百分之一字符 / 100 |
| 倍数行距 | lines | auto 模式 line / 240 |
| 固定/最小行距 | pt | exact/atLeast 模式 line / 20 |
| 字符数、关键词数、起始页码 | count | 整数 |
| 大纲层级 | level | 0 为一级、8 为九级、9 为正文 |

数字期望支持 eq、gte、lte；区间拆成两条原子规则。tolerance 的单位与期望一致，默认 0，不擅自为学校规定容差。文本和布尔只允许 eq，且容差为 0。未知的行距模式或缺失实际值返回未解析，不能将未知转换为 0。

现阶段登记核心格式与少量数量属性；复杂内容关系、段内标签/正文选择、跨页图表要求要在后续 Profile/语义定位中进一步建模，不用自由字符串绕过未支持边界。

## 证据与确认

- school_comment 与 written_spec 同级，优先于 template_observation。
- 同级要求不一致则 needs_review；明确要求与观察不一致时选明确要求，同时保留观察候选。
- 没有明确要求时，观察值只能形成 provisional 候选。
- confirmed 要求 confirmation：reviewer、confirmed_at、reference。该记录是可审计的人工决策来源，不是身份认证机制。
- 对未确认规则禁止 auto_fixable=true。M2 整体仍只读；布尔字段本身不会触发排版操作。

候选必须在同一语义目标和同一属性内收集，数值先转成规范单位，再交给 `select_evidence`；该函数不负责跨章节语义匹配。

## 规则状态与执行结果分离

| 前置条件 | 返回 |
|---|---|
| 规则 provisional 或 needs_review | evidence_insufficient |
| confirmed，但实际值缺失、不支持、格式来源不完整或单位不兼容 | not_evaluated |
| confirmed，目标已定位且实际值可用 | 交给 M2.4 比较器，尚不是 pass |
| M2.4 比较一致/不一致 | pass / fail |

优先报告规则证据不足；即使实际值也缺失，前置检查仍先返回 evidence_insufficient。来源、期望、实际、定位与原因都保存在结果契约中。

## 从旧契约迁移

1. v1 自由 scope/property_path 转为登记枚举。
2. 裸 expected_value 转为带 kind 和 unit 的对象。
3. 把一条复合规则拆成字体、字号、对齐等原子规则。
4. source.type 转为明确来源类型，补 locator。
5. 原 confirmed 条目补可追溯确认记录；没有记录就保留 provisional，不能编造确认时间。
6. 显式标记 schema_version=2.0。旧的 v1 数据会被拒绝，不静默解释。

M1 报告和命令保持原契约。当前仓库尚无正式 Profile，因此没有批量迁移用户规则。
