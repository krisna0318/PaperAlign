<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getHealth, type HealthResponse } from "./api/health";

const health = ref<HealthResponse | null>(null);
const healthError = ref<string | null>(null);

onMounted(async () => {
  try {
    health.value = await getHealth();
  } catch {
    healthError.value = "后端尚未启动";
  }
});
</script>

<template>
  <main class="shell">
    <section class="hero">
      <p class="eyebrow">PaperAlign · M2</p>
      <h1>可解释的论文格式诊断与安全排版</h1>
      <p class="summary">
        当前版本已完成 DOCX 只读分析，并开始从模板内容中提取页面、样式和表格边框证据。
        格式观察值需要人工确认后才会成为学校规则。
      </p>
      <div class="status" :class="{ online: health }" role="status">
        <span class="dot" aria-hidden="true" />
        <span v-if="health">后端已连接 · {{ health.version }} · {{ health.stage }}</span>
        <span v-else>{{ healthError ?? "正在检查后端…" }}</span>
      </div>
    </section>
  </main>
</template>
