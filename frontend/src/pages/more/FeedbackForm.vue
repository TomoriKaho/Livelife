<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue';
import { onAuthSessionChange, readAuthToken } from '../../api/auth';
import { submitFeedback } from '../../api/feedback';
import { createFeedbackForm, feedbackRequestId } from './feedback-core';

const loggedIn = ref(Boolean(readAuthToken()));
const form = createFeedbackForm({ token: readAuthToken, request: submitFeedback, uuid: feedbackRequestId, reactive });
const { state } = form;
const length = computed(() => Array.from(state.content.trim()).length);
const unsubscribe = onAuthSessionChange(() => { form.clear(); loggedIn.value = Boolean(readAuthToken()); });
onBeforeUnmount(() => { unsubscribe(); form.clear(); });
</script>

<template>
  <form class="feedback-form" aria-label="提交用户反馈" @submit.prevent="form.submit">
    <p class="feedback-note">反馈将关联你的账号，供维护者排查和处理，保留至注销账号。请勿填写密码等敏感信息；不会自动附带聊天、定位或日志。</p>
    <p v-if="!loggedIn" class="feedback-note"><RouterLink to="/login">登录后提交反馈</RouterLink></p>
    <label class="form-field"><span class="sr-only">反馈内容</span>
      <div v-sketch class="field-outline sketch" data-sketch-key="more-feedback">
        <textarea v-model="state.content" rows="4" maxlength="1000" aria-label="反馈内容" aria-describedby="feedback-length" :disabled="state.busy || !loggedIn" placeholder="遇到了什么问题，或有什么新想法？"></textarea>
      </div>
    </label>
    <p id="feedback-length" class="feedback-note">{{ length }} / 500 字 · 草稿仅在当前页面保留</p>
    <p v-if="state.error" class="feedback-error" role="alert">{{ state.error }}</p>
    <div v-if="state.receipt" v-sketch class="feedback-receipt sketch" data-pencil="mint" role="status">
      <strong>反馈已提交，谢谢你的建议！</strong>
      <p>反馈编号：<span class="feedback-id">{{ state.receipt.id }}</span></p>
      <p>请保存编号以便联系维护者。首期暂不提供处理进度查询。</p>
    </div>
    <button v-sketch class="primary-button sketch" data-pencil="yellow" type="submit" :disabled="!loggedIn || state.busy || !length || length > 500">{{ state.busy ? '正在提交…' : state.error ? '重试提交' : '提交反馈' }}</button>
  </form>
</template>

<style scoped>
.feedback-note, .feedback-error, .feedback-receipt { font-size: 13px; line-height: 1.8; }
.feedback-note { color: var(--muted); }
.feedback-error { color: #9d3445; }
.feedback-receipt { padding: 12px; background: transparent; }
.feedback-receipt p { margin: 6px 0 0; }
.feedback-id { overflow-wrap: anywhere; user-select: text; }
.field-outline { padding: 12px; }
textarea { display: block; box-sizing: border-box; width: 100%; padding: 0; border: 0; background: transparent; font: inherit; font-size: 16px; line-height: 1.8; resize: vertical; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
.primary-button { width: 100%; min-height: 48px; margin-top: 14px; padding: 12px 16px; background: transparent; font: inherit; }
.primary-button:disabled { opacity: .5; }
</style>
