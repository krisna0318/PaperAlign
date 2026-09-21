<script setup lang="ts">
import { ref } from "vue";

import type { DiagnosticJobView, FormatJobResult } from "../types/diagnosis";

defineProps<{
  result: DiagnosticJobView;
  busy: boolean;
  formatted: FormatJobResult | null;
  downloadUrl: string | null;
}>();
const emit = defineEmits<{ format: [] }>();
const approved = ref(false);
</script>

<template>
  <section v-if="result.summary?.formatting_candidate_count" class="format-card">
    <div>
      <p class="section-kicker">STEP 03 · DETERMINISTIC FORMAT</p>
      <h2>生成安全排版副本</h2>
      <p class="muted">检测到 {{ result.summary.formatting_candidate_count }} 个已确认的缩略词表。当前只处理学校批注明确确认的三线表边框。</p>
    </div>
    <label class="approval-box">
      <input v-model="approved" type="checkbox" :disabled="busy || !!formatted" />
      <span><strong>我已核对本次 4 条规则</strong><small>顶线 1.5 磅、表头分隔线 1 磅、底线 1.5 磅、无竖线；输出为新文件。</small></span>
    </label>
    <button v-if="!formatted" class="primary" type="button" :disabled="!approved || busy" @click="emit('format')">
      <span v-if="busy" class="spinner" aria-hidden="true" />{{ busy ? "正在验证内容指纹…" : "生成新副本" }}
    </button>
    <div v-else class="format-success">
      <strong>内容指纹一致，已生成新副本</strong>
      <span>{{ formatted.report.operations.length }} 条可追踪变更 · 原文件未覆盖</span>
      <a v-if="downloadUrl" class="download" :href="downloadUrl">下载排版副本</a>
    </div>
  </section>
</template>
