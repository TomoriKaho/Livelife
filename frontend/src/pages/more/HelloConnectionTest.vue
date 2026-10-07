<script setup lang="ts">
import { computed, ref } from 'vue';
import { fetchHello } from '../../api/hello';
import { getApiBaseUrl } from '../../platform/web';
import { previewState, loadPreviewConfig } from '../../platform/runtime-config';

const available = computed(() => !previewState.enabled || !!previewState.config);
const apiBaseUrl = computed(() => available.value ? getApiBaseUrl() : '配置不可用');
const state = ref<'idle' | 'loading' | 'success' | 'error'>('idle');
const message = ref('');

async function testConnection() {
  if (state.value === 'loading' || !available.value) return;
  state.value = 'loading';
  message.value = '';
  const result = await fetchHello();
  if (result.ok) {
    state.value = 'success';
    message.value = result.data.message;
  } else {
    state.value = 'error';
    message.value = result.error;
  }
}
</script>

<template>
  <section class="connection-test" aria-labelledby="connection-test-title" :aria-busy="state === 'loading'">
    <h2 id="connection-test-title">接口连通性测试</h2>
    <p class="connection-note">点击按钮，检查能否连接后端。此处展示实际请求结果。</p>
    <p class="connection-address">后端地址：<span>{{ apiBaseUrl }}</span></p>
    <div v-if="previewState.enabled" class="preview-version">
      <template v-if="previewState.config">
        <p>测试环境：{{ previewState.config.environment }}</p>
        <p>前端 SHA：{{ previewState.config.frontend_sha }}</p>
        <p>构建：{{ previewState.config.build_id }}</p>
        <p>后端模式：{{ { staging: '共享 main 测试服', own: '本分支配套后端', fixed: '固定版本' }[previewState.config.backend_mode] }}</p>
        <p>加载时后端 SHA：{{ previewState.config.backend_sha }}</p>
        <p>实际响应后端 SHA：{{ previewState.observedBackendSha || '尚未请求' }}</p>
      </template>
      <template v-else>
        <p role="alert">{{ previewState.error || '正在读取测试配置…' }}</p>
        <button type="button" :disabled="previewState.loading" @click="loadPreviewConfig()">重新读取配置</button>
      </template>
    </div>
    <button v-sketch class="connection-button sketch" data-pencil="blue" type="button" :disabled="state === 'loading' || !available" @click="testConnection">
      {{ state === 'loading' ? '连接中…' : state === 'error' ? '重试连接' : '测试连接' }}
    </button>
    <p class="connection-result" role="status" aria-live="polite">
      <template v-if="state === 'loading'">正在连接后端…</template>
      <template v-else-if="state === 'success'">连接成功：{{ message }}</template>
      <template v-else-if="state === 'error'">连接失败：{{ message }}</template>
      <template v-else>尚未测试连接。</template>
    </p>
  </section>
</template>

<style scoped>
.connection-test { margin-top: 29px; padding: 16px 4px; border-block: 1px solid #20304b22; }
h2 { margin: 0 0 10px; font-size: 15px; font-weight: 400; }
.connection-note, .connection-address, .connection-result { margin: 10px 0; font-size: 12px; line-height: 1.8; }
.connection-note { color: var(--muted); }
.connection-address span { overflow-wrap: anywhere; }
.connection-button { width: 100%; min-height: 46px; padding: 12px 8px; background: transparent; font-size: 13px; }
.connection-button:disabled { opacity: .5; cursor: default; }
.connection-result { overflow-wrap: anywhere; }
.preview-version { font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
</style>
