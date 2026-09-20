<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getHealth, type HealthResponse } from "./api/health";
import { createDiagnosticJob, DiagnosticApiError } from "./api/jobs";
import DiagnosisSummary from "./components/DiagnosisSummary.vue";
import FileUploader from "./components/FileUploader.vue";
import ReviewPanel from "./components/ReviewPanel.vue";
import type { DiagnosticJobView } from "./types/diagnosis";

const health = ref<HealthResponse | null>(null);
const healthError = ref<string | null>(null);
const busy = ref(false);
const error = ref<string | null>(null);
const result = ref<DiagnosticJobView | null>(null);

onMounted(async () => {
  try {
    health.value = await getHealth();
  } catch {
    healthError.value = "后端尚未启动";
  }
});

async function analyze(file: File): Promise<void> {
  busy.value = true;
  error.value = null;
  result.value = null;
  try {
    result.value = await createDiagnosticJob(file);
  } catch (caught) {
    error.value = caught instanceof DiagnosticApiError ? caught.message : "分析失败，请稍后重试。";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <a class="brand" href="#top" aria-label="PaperAlign 首页"><span>PA</span><strong>PaperAlign</strong></a>
      <div class="connection" :class="{ online: health }" role="status">
        <span class="dot" aria-hidden="true" />
        {{ health ? `${health.version} · ${health.stage}` : healthError ?? "连接中…" }}
      </div>
    </header>

    <main id="top">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">THESIS FORMAT INTELLIGENCE</p>
          <h1>先看懂论文，<br /><em>再安全排版。</em></h1>
          <p>PaperAlign 把语义结构识别、规则证据与确定性排版拆开处理。你先确认系统是否理解正确，再决定是否生成新副本。</p>
          <div class="safety-row"><span>✓ 原文不覆盖</span><span>✓ 证据可追踪</span><span>✓ 无密钥可运行</span></div>
        </div>
        <div class="hero-mark" aria-hidden="true">
          <div class="paper-sheet"><i /><i /><i /><i /></div>
          <span class="align-line line-one" /><span class="align-line line-two" />
        </div>
      </section>

      <FileUploader :busy="busy" @submit="analyze" />
      <div v-if="error" class="notice error" role="alert"><strong>无法完成分析</strong><span>{{ error }}</span></div>
      <DiagnosisSummary v-if="result" :result="result" />
      <ReviewPanel v-if="result?.summary" :summary="result.summary" />
    </main>

    <footer><span>PaperAlign 本地 MVP</span><span>诊断结果用于辅助复核，不替代学校最终审核。</span></footer>
  </div>
</template>
