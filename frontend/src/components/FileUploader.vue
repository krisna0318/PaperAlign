<script setup lang="ts">
import { ref } from "vue";

defineProps<{ busy: boolean }>();
const emit = defineEmits<{ submit: [file: File] }>();
const file = ref<File | null>(null);
const input = ref<HTMLInputElement | null>(null);
const localError = ref<string | null>(null);
const dragging = ref(false);

function accept(candidate: File | null): void {
  localError.value = null;
  if (!candidate) return;
  if (!candidate.name.toLowerCase().endsWith(".docx")) {
    file.value = null;
    localError.value = "请选择 .docx 文件，旧版 .doc 暂不支持。";
    return;
  }
  if (candidate.size > 50 * 1024 * 1024) {
    file.value = null;
    localError.value = "文件不能超过 50 MB。";
    return;
  }
  file.value = candidate;
}

function pick(event: Event): void {
  accept((event.target as HTMLInputElement).files?.[0] ?? null);
}
function drop(event: DragEvent): void {
  dragging.value = false;
  accept(event.dataTransfer?.files[0] ?? null);
}
function submit(): void {
  if (file.value) emit("submit", file.value);
}
</script>

<template>
  <section class="upload-card" aria-labelledby="upload-title">
    <div>
      <p class="section-kicker">STEP 01 · LOCAL ANALYSIS</p>
      <h2 id="upload-title">上传论文原稿</h2>
      <p class="muted">系统会创建只读副本进行分析，不覆盖你上传的文件。</p>
    </div>
    <button
      class="drop-zone" :class="{ dragging }" type="button" :disabled="busy"
      @click="input?.click()" @dragenter.prevent="dragging = true" @dragover.prevent
      @dragleave.prevent="dragging = false" @drop.prevent="drop"
    >
      <span class="upload-icon" aria-hidden="true">↥</span>
      <strong>{{ file ? file.name : "拖入 DOCX，或点击选择文件" }}</strong>
      <small>{{ file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "最大 50 MB · 原文仅保存在本机" }}</small>
    </button>
    <input ref="input" class="visually-hidden" type="file" accept=".docx" @change="pick" />
    <p v-if="localError" class="inline-error" role="alert">{{ localError }}</p>
    <button class="primary" type="button" :disabled="busy || !file" @click="submit">
      <span v-if="busy" class="spinner" aria-hidden="true" />
      {{ busy ? "正在建立文档画像…" : "开始只读诊断" }}
    </button>
  </section>
</template>
