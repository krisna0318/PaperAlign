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
      <p class="eyebrow">PaperAlign · M0</p>
      <h1>可解释的论文格式诊断与安全排版</h1>
      <p class="summary">
        当前版本正在搭建工程地基：仓库、开发环境、健康检查和核心数据契约。
        DOCX 分析将在 M1 开始。
      </p>
      <div class="status" :class="{ online: health }" role="status">
        <span class="dot" aria-hidden="true" />
        <span v-if="health">后端已连接 · {{ health.version }} · {{ health.stage }}</span>
        <span v-else>{{ healthError ?? "正在检查后端…" }}</span>
      </div>
    </section>
  </main>
</template>
