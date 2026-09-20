<script setup lang="ts">
import type { DiagnosticJobView } from "../types/diagnosis";

defineProps<{ result: DiagnosticJobView }>();
function statusCount(counts: Record<string, number>, key: string): number {
  return counts[key] ?? 0;
}
</script>

<template>
  <section v-if="result.summary" class="result-stack" aria-labelledby="result-title">
    <div class="result-heading">
      <div>
        <p class="section-kicker">STEP 02 · EVIDENCE FIRST</p>
        <h2 id="result-title">诊断概览</h2>
        <p class="muted">{{ result.job.input_filename }} · 规则模式 · 未调用云端模型</p>
      </div>
      <span class="status-pill">等待人工确认</span>
    </div>
    <div class="notice neutral">
      <strong>当前结论：只读诊断，不是整篇论文合规证明。</strong>
      <span>页面呈现、分页和域更新仍需在桌面版 Word 中复核；此阶段不会生成排版文件。</span>
    </div>
    <div class="metrics">
      <article><span>文档块</span><strong>{{ result.summary.total_blocks }}</strong></article>
      <article><span>待确认入口</span><strong>{{ result.summary.review_root_count }}</strong></article>
      <article><span>明确不一致</span><strong>{{ statusCount(result.summary.validation_counts, "fail") }}</strong></article>
      <article><span>证据不足</span><strong>{{ result.summary.evidence_insufficient_count }}</strong></article>
    </div>
    <div v-if="result.summary.warnings.length" class="notice warning">
      <strong>分析提醒</strong>
      <ul><li v-for="warning in result.summary.warnings" :key="warning">{{ warning }}</li></ul>
    </div>
    <div v-if="Object.keys(result.summary.unsupported_object_counts).length" class="object-strip">
      <span>需要 Word 复核的特殊对象</span>
      <div>
        <span v-for="(count, category) in result.summary.unsupported_object_counts" :key="category" class="chip">
          {{ category }} · {{ count }}
        </span>
      </div>
    </div>
    <details class="trace">
      <summary>查看本次分析的追踪信息</summary>
      <dl>
        <div><dt>任务编号</dt><dd>{{ result.job.id }}</dd></div>
        <div><dt>输入指纹</dt><dd>{{ result.summary.input_sha256 }}</dd></div>
        <div><dt>内容指纹</dt><dd>{{ result.summary.content_fingerprint }}</dd></div>
      </dl>
    </details>
  </section>
</template>
