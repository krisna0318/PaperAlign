<script setup lang="ts">
import { computed, ref } from "vue";
import type { DiagnosticSummary } from "../types/diagnosis";

const props = defineProps<{ summary: DiagnosticSummary }>();
const view = ref<"review" | "issues">("review");
const visibleIssues = computed(() => props.summary.issues.slice(0, 100));

function locatorLabel(locator: DiagnosticSummary["review_items"][number]["locator"]): string {
  if (locator.paragraph_index != null) return `段落 ${locator.paragraph_index}`;
  if (locator.table_index != null) return `表格 ${locator.table_index}`;
  return locator.part_name;
}
</script>

<template>
  <section class="review-card" aria-labelledby="review-title">
    <div class="tabs" role="tablist" aria-label="诊断详情">
      <button :class="{ active: view === 'review' }" type="button" @click="view = 'review'">
        待确认结构 <span>{{ summary.review_root_count }}</span>
      </button>
      <button :class="{ active: view === 'issues' }" type="button" @click="view = 'issues'">
        格式证据 <span>{{ summary.issue_count }}</span>
      </button>
    </div>
    <div v-if="view === 'review'" class="item-list">
      <div class="panel-intro">
        <h2 id="review-title">优先确认这些结构入口</h2>
        <p>表格作为一个入口展示，避免父表与单元格重复计数。启发式分数不是准确率。</p>
      </div>
      <article v-for="item in summary.review_items" :key="item.block_id" class="review-item">
        <div class="item-index">{{ item.block_id }}</div>
        <div class="item-body">
          <div class="item-title"><strong>{{ item.role }}</strong><span>{{ locatorLabel(item.locator) }}</span></div>
          <blockquote v-if="item.preview">“{{ item.preview }}”</blockquote>
          <p>{{ item.reasons.join("；") }}</p>
        </div>
        <div class="confidence">{{ Math.round(item.confidence * 100) }}<small>/100</small></div>
      </article>
      <p v-if="!summary.review_items.length" class="empty">当前没有需要人工确认的结构入口。</p>
    </div>
    <div v-else class="item-list">
      <div class="panel-intro">
        <h2>已定位的格式证据</h2>
        <p>明确不一致优先展示；接口最多返回前 100 条，完整记录保存在本地任务目录。</p>
      </div>
      <article v-for="item in visibleIssues" :key="`${item.rule_id}-${JSON.stringify(item.locator)}`" class="issue-item">
        <span class="issue-state" :class="item.status">{{ item.status === "fail" ? "不一致" : "证据不足" }}</span>
        <div><strong>{{ item.rule_id }}</strong><p>{{ item.property_path }} · {{ item.reason }}</p><small>{{ locatorLabel(item.locator) }}</small></div>
      </article>
      <p v-if="summary.issues_truncated" class="empty">还有 {{ summary.issue_count - summary.issues.length }} 条未在页面展开，请查看本地结构报告。</p>
      <p v-if="!visibleIssues.length" class="empty">没有可展示的不一致或证据不足项。</p>
    </div>
  </section>
</template>
