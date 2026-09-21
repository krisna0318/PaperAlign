<script setup lang="ts">
import { ref } from "vue";

import type { DeliveryValidationResult } from "../types/diagnosis";

defineProps<{
  busy: boolean;
  validation: DeliveryValidationResult | null;
  checklistUrl: string | null;
  pdfUrl: string | null;
}>();
const emit = defineEmits<{ validate: [renderWithWord: boolean] }>();
const useWord = ref(false);
</script>

<template>
  <section class="validation-card">
    <div>
      <p class="section-kicker">STEP 04 · DELIVERY GATE</p>
      <h2>最终验证与交付</h2>
      <p class="muted">机器复检内容指纹、DOCX 安全性与已应用规则；最终页面仍由你逐项确认。</p>
    </div>
    <template v-if="!validation">
      <label class="word-option">
        <input v-model="useWord" type="checkbox" :disabled="busy" />
        <span><strong>尝试桌面版 Word 探测</strong><small>后台只读打开、重分页并导出 PDF；不会自动判定视觉正确。</small></span>
      </label>
      <button class="primary" type="button" :disabled="busy" @click="emit('validate', useWord)">
        <span v-if="busy" class="spinner" aria-hidden="true" />{{ busy ? "正在执行交付闸门…" : "执行最终验证" }}
      </button>
    </template>
    <template v-else>
      <div class="validation-status" :class="validation.report.static_status">
        <strong>{{ validation.report.static_status === "passed" ? "机器验证通过" : "机器验证未通过" }}</strong>
        <span>内容指纹：{{ validation.report.content_preserved ? "一致" : "不一致" }} · 规则复检：{{ validation.report.rule_rechecks.filter(item => item.passed).length }}/{{ validation.report.rule_rechecks.length }}</span>
        <span>Word 探测：{{ validation.report.word_render.status }}<template v-if="validation.report.word_render.page_count"> · {{ validation.report.word_render.page_count }} 页</template></span>
      </div>
      <div class="delivery-links">
        <a v-if="checklistUrl" :href="checklistUrl">下载人工检查单</a>
        <a v-if="pdfUrl" :href="pdfUrl">下载 Word 预览 PDF</a>
      </div>
      <ol class="manual-list"><li v-for="item in validation.report.manual_checklist" :key="item">{{ item }}</li></ol>
    </template>
  </section>
</template>
