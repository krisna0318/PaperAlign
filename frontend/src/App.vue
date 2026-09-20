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
        当前版本支持 DOCX 只读分析、模板证据提取、有效格式解析和单模板规则配置。
        已定位样本可通过命令行验证；未确认规则保留审查状态，尚不进行整篇自动排版。
      </p>
      <div class="status" :class="{ online: health }" role="status">
        <span class="dot" aria-hidden="true" />
        <span v-if="health">后端已连接 · {{ health.version }} · {{ health.stage }}</span>
        <span v-else>{{ healthError ?? "正在检查后端…" }}</span>
      </div>
    </section>
  </main>
</template>
