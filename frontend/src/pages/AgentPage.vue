<script>
export const pageMeta = {
  key: 'agent', id: 'D-06', title: 'LiLi 智能助手', placeholder: 'Agent 对话页',
  label: 'AGENT', eyebrow: '', icon: 'agent', accent: 'lavender', nav: 'agent',
  back: false, immersive: true, customHeading: true,
};
</script>

<script setup>
import { useRouter } from 'vue-router';
import { authState } from '../api/auth';
import { registerBackHandler } from '../platform/android-navigation';
import { sessionShuffle } from '../data/session-style';
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { loadAgentSession, rateAgentMessage, sendAgentMessage } from '../api/agent';
import AgentIcon from './agent/AgentIcon.vue';
import LiLiAvatar from './agent/LiLiAvatar.vue';
import UserPlaneAvatar from './agent/UserPlaneAvatar.vue';
import ElasticList from './agent/ElasticList.vue';
import ElasticTextarea from './agent/ElasticTextarea.vue';
import { composerPlacement } from './agent/composer-layout.mjs';

const router = useRouter();
const colors = sessionShuffle('agent-demo-colors', ['mint', 'blue', 'pink', 'lavender', 'yellow']);
const messages = ref([]), session = ref(null), loading = ref(true), sending = ref(false);
const history = computed(() => messages.value.length ? [{
  label: '当前会话',
  title: messages.value.find(message => message.role === 'user')?.text.slice(0, 22) || '新的对话',
  summary: '会话将在 24 小时后过期', current: true,
}] : []);
const historyOpen = ref(false), drawer = ref(null), historyTrigger = ref(null), mounted = ref(false);
const composer = ref(null), draft = ref(''), notice = ref('');
const ready = computed(() => Boolean(draft.value.trim()) && !sending.value && !loading.value);
const conversation = ref(null);
const composerPanel = ref(null), expanded = ref(false), longDraft = ref(false);
const panelBottom = ref(86), panelTop = ref(0), panelInset = ref(17), reservedHeight = ref(140);
let layoutObserver, layoutFrame, restingViewportHeight = 0, inputFocused = false, keyboardWasOpen = false, compactPanelHeight = 140;
function viewportHeight() { return window.visualViewport?.height || window.innerHeight; }
function updateLayout() {
  const shell = document.querySelector('.phone-shell'), nav = shell?.querySelector('.bottom-nav');
  if (!shell || !composerPanel.value) return;
  const rect = shell.getBoundingClientRect(), view = window.visualViewport;
  if (!inputFocused && !keyboardWasOpen) restingViewportHeight = viewportHeight();
  const navHeight = nav?.getBoundingClientRect().height || 0;
  const placement = composerPlacement({
    shellTop: rect.top, shellBottom: rect.bottom, navigationHeight: navHeight,
    viewportTop: view?.offsetTop || 0, viewportHeight: viewportHeight(),
    restingHeight: restingViewportHeight, focused: inputFocused, scale: view?.scale || 1, keyboardWasOpen,
  });
  keyboardWasOpen = placement.keyboardOpen;
  panelBottom.value = placement.bottom; panelTop.value = placement.top;
  panelInset.value = rect.width < 360 ? 10 : 17;
  if (!expanded.value) compactPanelHeight = composerPanel.value.getBoundingClientRect().height;
  reservedHeight.value = compactPanelHeight + Math.max(0, placement.bottom - navHeight);
}
function queueLayout() { cancelAnimationFrame(layoutFrame); layoutFrame = requestAnimationFrame(updateLayout); }
function focusInput() {
  if (!inputFocused && !keyboardWasOpen) restingViewportHeight = viewportHeight();
  inputFocused = true; queueLayout();
}
function blurInput() { inputFocused = false; queueLayout(); }
function toggleExpanded() {
  expanded.value = !expanded.value;
  // Focus synchronously inside the tap, so iOS retains its open keyboard.
  composer.value?.focus(); nextTick(queueLayout);
}
let noticeTimer, previousFocus, inerted = [], activeRequestController = null;
function notify(text) { clearTimeout(noticeTimer); notice.value = text; noticeTimer = setTimeout(() => { notice.value = ''; }, 2400); }
const segments = text => text.split(/(\*\*[^*]+\*\*)/g).map(value => ({ text: value.startsWith('**') ? value.slice(2, -2) : value, bold: value.startsWith('**') }));
function viewMessage(message, index) {
  return {
    id: message.id,
    role: message.role === 'assistant' ? 'agent' : 'user',
    text: message.content,
    status: message.status,
    citations: message.citations || [],
    rating: message.rating || null,
    color: colors[index % colors.length],
    requestId: message.request_id || message.client_request_id,
  };
}
async function loadConversation() {
  const revision = authState.revision;
  loading.value = true;
  try {
    const result = await loadAgentSession();
    if (!mounted.value || revision !== authState.revision) return;
    session.value = result.session;
    messages.value = result.messages.map(viewMessage);
    for (const message of messages.value) if (message.status === 'pending') message.status = 'failed';
    await nextTick(); conversation.value?.scrollToBottom();
  } catch (error) {
    if (error.message === 'authentication_required') { router.replace('/onboarding'); return; }
    if (revision !== authState.revision) return;
    notify('无法连接智能助手，请检查后端和数据库配置。');
  } finally { loading.value = false; }
}
async function copy(message) {
  const text = message.text.replace(/\*\*/g, '');
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else {
      const selection = document.activeElement, area = document.createElement('textarea');
      area.value = text; area.style.cssText = 'position:fixed;opacity:0;pointer-events:none'; document.body.append(area); area.select();
      try { if (!document.execCommand('copy')) throw new Error('COPY_FAILED'); } finally { area.remove(); selection?.focus({ preventScroll: true }); }
    }
    notify('已复制这条消息');
  } catch { notify('复制失败，请长按消息复制'); }
}
async function send(retryMessage = null) {
  if (!session.value || sending.value) return;
  const text = (retryMessage?.text || draft.value).trim();
  if (!text) return;
  let userMessage = retryMessage;
  if (!userMessage) {
    userMessage = { id: crypto.randomUUID(), role: 'user', text, status: 'completed', citations: [], color: colors[messages.value.length % colors.length] };
    messages.value.push(userMessage);
    draft.value = '';
  }
  const assistant = reactive({
    id: crypto.randomUUID(), role: 'agent', text: '', status: 'pending', citations: [],
    color: colors[messages.value.length % colors.length], requestId: crypto.randomUUID(),
  });
  messages.value.push(assistant);
  sending.value = true;
  const controller = new AbortController();
  activeRequestController = controller;
  try {
    await sendAgentMessage(session.value.session_token, text, assistant.requestId, {
      message_start: data => { assistant.id = data.message_id; },
      citation: data => assistant.citations.push(data),
      delta: data => { assistant.text += data.text; },
      usage: () => {},
      done: () => { assistant.status = 'completed'; },
      error: data => { assistant.status = 'failed'; throw new Error(data.code); },
    }, controller.signal);
    assistant.status = 'completed';
    conversation.value?.scrollToBottom();
  } catch (error) {
    assistant.status = 'failed';
    if (!controller.signal.aborted) {
      notify(error.message === 'token_quota_exceeded' ? '你的账号今日的使用额度已用完。' : '回答失败，请点击重试。');
    }
  } finally {
    if (activeRequestController === controller) activeRequestController = null;
    if (mounted.value) {
      sending.value = false;
      await nextTick(); conversation.value?.refresh();
    }
  }
}
function retry(message) {
  const index = messages.value.indexOf(message);
  const previous = messages.value.slice(0, index).reverse().find(item => item.role === 'user');
  if (previous) send(previous);
}
async function rate(message, value) {
  if (!session.value || message.status !== 'completed') return;
  const next = message.rating === value ? null : value;
  try {
    await rateAgentMessage(session.value.session_token, message.id, next);
    message.rating = next;
  } catch { notify('暂时无法保存反馈，请稍后再试。'); }
}
function chooseHistory() { historyOpen.value = false; conversation.value?.scrollToBottom(); }
function keydown(event) {
  if (event.isComposing) return;
  if (event.key === 'Escape') { if (!historyOpen.value && expanded.value) toggleExpanded(); historyOpen.value = false; }
  if (!historyOpen.value || event.key !== 'Tab') return;
  const nodes = [...drawer.value.querySelectorAll('button,a,input,textarea')].filter(node => !node.disabled);
  const first = nodes[0], last = nodes.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
function releaseDrawer() { for (const [node, value] of inerted) node.inert = value; inerted = []; }
watch(historyOpen, async open => {
  if (open) {
    conversation.value?.stop(); previousFocus = document.activeElement; await nextTick();
    if (!mounted.value || !historyOpen.value || !drawer.value) return;
    inerted = [...document.querySelector('.phone-shell').children].filter(node => !node.classList.contains('history-overlay')).map(node => [node, node.inert]);
    for (const [node] of inerted) node.inert = true;
    drawer.value?.querySelector('button')?.focus({ preventScroll: true });
  } else { releaseDrawer(); if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true }); }
});
watch(() => authState.revision, () => {
  activeRequestController?.abort();
  messages.value = []; session.value = null; draft.value = '';
  historyOpen.value = false; sending.value = false; notice.value = '';
  if (mounted.value) router.replace('/onboarding');
}, { flush: 'sync' });
onMounted(async () => {
  void loadConversation();
  restingViewportHeight = viewportHeight(); mounted.value = true;
  document.addEventListener('keydown', keydown);
  window.addEventListener('resize', queueLayout); window.addEventListener('scroll', queueLayout, { passive: true });
  window.visualViewport?.addEventListener('resize', queueLayout); window.visualViewport?.addEventListener('scroll', queueLayout);
  await nextTick(); if (!mounted.value) return;
  layoutObserver = new ResizeObserver(queueLayout);
  for (const node of [composerPanel.value, document.querySelector('.phone-shell'), document.querySelector('.bottom-nav')]) if (node) layoutObserver.observe(node);
  updateLayout();
});
onBeforeUnmount(() => {
  mounted.value = false; clearTimeout(noticeTimer); cancelAnimationFrame(layoutFrame); layoutObserver?.disconnect(); releaseDrawer();
  activeRequestController?.abort(); activeRequestController = null;
  document.removeEventListener('keydown', keydown);
  window.removeEventListener('resize', queueLayout); window.removeEventListener('scroll', queueLayout);
  window.visualViewport?.removeEventListener('resize', queueLayout); window.visualViewport?.removeEventListener('scroll', queueLayout);
});

const removeNativeBack = registerBackHandler(() => {
  if (historyOpen.value || expanded.value) {
    if (historyOpen.value) historyOpen.value = false;
    else if (expanded.value) toggleExpanded();
    return true;
  }
  return false;
});
onBeforeUnmount(removeNativeBack);
</script>

<template>
  <section class="agent-page" aria-label="LiLi 智能助手对话">
    <header class="chat-heading">
      <button ref="historyTrigger" v-sketch class="sketch history-button" type="button" aria-label="打开历史对话" aria-controls="lili-history" :aria-expanded="historyOpen" @click="historyOpen = true"><AgentIcon name="menu" /></button>
      <div class="heading-title"><h1>LiLi<span>智能助手</span></h1></div>
    </header>

    <ElasticList ref="conversation" class="conversation" role="region" aria-label="当前对话">
      <p v-if="loading" class="conversation-date">正在连接 LiLi…</p>
      <p v-else-if="!messages.length" class="conversation-date">校园里的事情，可以问问 LiLi</p>
      <article v-for="message in messages" :key="message.id" class="message" :class="`message-${message.role}`" :aria-label="message.role === 'user' ? '你的消息' : 'LiLi 的消息'">
        <div class="message-avatar" aria-hidden="true"><LiLiAvatar v-if="message.role === 'agent'" /><UserPlaneAvatar v-else /></div>
        <div class="message-content">
          <div v-sketch class="sketch pencil-fill message-bubble" :data-pencil="message.color">
            <div v-if="message.status === 'pending' && !message.text" class="thinking-message" role="status" aria-label="LiLi 正在准备回答"><span class="thinking-orbit" aria-hidden="true"><i></i><i></i><i></i></span><span>正在准备回答<span class="thinking-dots" aria-hidden="true"><i>·</i><i>·</i><i>·</i></span></span></div>
            <p v-else class="message-text"><template v-for="(part, i) in segments(message.text)" :key="i"><strong v-if="part.bold">{{ part.text }}</strong><template v-else>{{ part.text }}</template></template></p>
          </div>
          <div class="message-actions" :aria-label="message.role === 'agent' ? '助手消息操作' : '你的消息操作'">
            <button type="button" :disabled="!message.text" aria-label="复制消息" @click="copy(message)"><AgentIcon name="copy" /><span>复制</span></button>
            <button v-if="message.role === 'agent' && message.status === 'failed'" type="button" @click="retry(message)"><AgentIcon name="regenerate" /><span>重试</span></button>
            <template v-if="message.role === 'agent' && message.status === 'completed'"><button type="button" class="rating-action" :class="{ selected: message.rating === 'like' }" :aria-pressed="message.rating === 'like'" aria-label="点赞回答" @click="rate(message, 'like')"><AgentIcon name="like" /></button><button type="button" class="rating-action" :class="{ selected: message.rating === 'dislike' }" :aria-pressed="message.rating === 'dislike'" aria-label="点踩回答" @click="rate(message, 'dislike')"><AgentIcon name="dislike" /></button></template>
          </div>
          <div v-if="message.role === 'agent' && message.citations.length" class="citation-list" aria-label="回答来源">
            <a v-for="citation in message.citations" :key="citation.information_id" class="citation-link" :href="citation.source_url || undefined" :target="citation.source_url ? '_blank' : undefined" :rel="citation.source_url ? 'noopener noreferrer' : undefined">
              <AgentIcon name="file" /><span><strong>[S{{ citation.rank }}] {{ citation.title || citation.platform + ' 信息' }}</strong><small>{{ citation.published_at ? new Date(citation.published_at).toLocaleDateString('zh-CN') : citation.platform }} · {{ citation.snippet }}</small></span>
            </a>
          </div>
        </div>
      </article>
    </ElasticList>

    <div class="composer-reservation" :style="{ height: `${reservedHeight}px` }" aria-hidden="true"></div>
    <Teleport v-if="mounted" to=".phone-shell">
    <section ref="composerPanel" class="composer-section" :class="{ 'is-expanded': expanded }" :style="{ bottom: `${panelBottom}px`, top: expanded ? `${panelTop}px` : undefined, '--composer-inset': `${panelInset}px` }" aria-label="消息输入区">
      <div v-sketch class="sketch composer-box">
        <ElasticTextarea ref="composer" v-model="draft" :expanded="expanded" @overflow="longDraft = $event" @focus="focusInput" @blur="blurInput" @send="send" />
        <button v-if="longDraft || expanded" class="composer-expand" type="button" :aria-label="expanded ? '取消全屏输入' : '全屏输入'" :title="expanded ? '取消全屏' : '全屏输入'" aria-controls="lili-draft-editor" :aria-expanded="expanded" @pointerdown.prevent @click="toggleExpanded"><AgentIcon :name="expanded ? 'contract' : 'expand'" /></button>
        <div class="composer-tools">
          <span class="composer-hint">回答基于公开信息</span>
          <button v-sketch class="sketch composer-tool send-button" data-pencil="yellow" type="button" :disabled="!ready" aria-label="发送消息" @click="send()"><AgentIcon name="send" /></button>
        </div>
      </div>
    </section>
    </Teleport>

    <Transition name="chat-toast"><p v-if="notice" v-sketch class="sketch chat-notice" data-pencil="yellow" role="status">{{ notice }}</p></Transition>

    <Teleport v-if="mounted" to=".phone-shell"><Transition name="history-slide"><div v-if="historyOpen" class="history-overlay" @click.self="historyOpen = false"><aside id="lili-history" ref="drawer" v-sketch class="sketch history-drawer" data-pencil="mint" role="dialog" aria-modal="true" aria-labelledby="lili-history-title"><header><div><p>和 LiLi 的</p><h2 id="lili-history-title">小小对话簿</h2></div><button type="button" class="drawer-close" aria-label="关闭历史对话" @click="historyOpen = false"><AgentIcon name="close" /></button></header><ElasticList class="history-list" role="region" aria-label="历史对话列表"><p v-if="!history.length" class="history-empty">这里还没有对话</p><template v-for="(item, index) in history" :key="index"><h3>{{ item.label }}</h3><button v-sketch class="sketch history-item" data-pencil="yellow" type="button" aria-current="true" @click="chooseHistory"><AgentIcon name="chat" /><span><strong>{{ item.title }}</strong><small>{{ item.summary }}</small></span></button></template></ElasticList><footer><div class="drawer-avatar"><LiLiAvatar /></div><p>校园生活，慢慢聊。</p></footer></aside></div></Transition></Teleport>
  </section>
</template>

<style scoped>
.agent-page { position: relative; display: flex; flex: 1; flex-direction: column; min-height: 0; overflow: hidden; padding: 0 17px; }
.chat-heading { display: flex; flex: none; align-items: center; gap: 12px; padding: 2px 0 6px; }
.history-button { display: grid; place-items: center; width: 44px; height: 44px; padding: 8px; flex: none; background: transparent; }
.heading-title { display: flex; align-items: center; flex: 1; min-width: 0; height: 44px; }.heading-title h1 { margin: 0; line-height: 1; font-size: 28px; display: flex; align-items: baseline; gap: 10px; }.heading-title h1 span { font-size: 13px; letter-spacing: 0; -webkit-text-stroke: 0; color: var(--muted); }
.conversation { flex: 1; min-height: 0; padding: 0 2px; outline-offset: -3px; }
.conversation :deep(.elastic-list-content) { padding-bottom: 18px; }
.conversation,.attachments,.history-list,.edit-message { scrollbar-width: none; -ms-overflow-style: none; }
.conversation::-webkit-scrollbar,.attachments::-webkit-scrollbar,.history-list::-webkit-scrollbar,.edit-message::-webkit-scrollbar { display: none; width: 0; height: 0; }
.conversation-date { text-align: center; color: var(--muted); font-size: 10px; margin: 0 0 12px; letter-spacing: 2px; }.message { display: flex; gap: 6px; margin-bottom: 10px; }.message:last-child { margin-bottom: 0; }.message-user { flex-direction: row-reverse; }
.message-avatar { width: 43px; height: 47px; flex: none; margin-top: 3px; }.message-user .message-avatar { width: 43px; height: 47px; margin-top: 3px; }
.message-content { max-width: calc(100% - 49px); min-width: 0; }.message-user .message-content { max-width: calc(100% - 49px); }
.message-bubble { padding: 11px 16px 12px; min-height: 49px; background: transparent; }.message-text { margin: 0; font-size: 14px; line-height: 1.85; overflow-wrap: anywhere; white-space: pre-wrap; }.message-text strong { font-weight: 400; -webkit-text-stroke: .35px var(--ink); text-decoration: underline; text-decoration-color: #20304b44; text-decoration-thickness: 3px; text-underline-offset: 3px; }
.message-actions { display: flex; align-items: center; gap: 0; margin: 1px 1px 0; min-height: 34px; }.message-user .message-actions { justify-content: flex-end; }.message-actions button { display: inline-flex; align-items: center; justify-content: center; gap: 3px; padding: 7px 6px; min-height: 34px; border: 0; background: transparent; color: var(--muted); font-size: 10px; white-space: nowrap; }.message-actions .agent-icon { width: 14px; height: 14px; stroke-width: 1.8; }.message-actions .rating-action { min-width: 34px; }.message-actions .rating-action .agent-icon { width: 16px; height: 16px; }.message-actions .selected { color: #245888; }.message-actions .selected .agent-icon { fill: #9ac8f244; stroke-width: 2.2; }.message-actions button:disabled { opacity: .35; cursor: default; }
.citation-list { display: grid; gap: 6px; margin: 6px 2px 2px; }.citation-link { display: flex; align-items: flex-start; gap: 7px; padding: 8px 10px; border: 1px solid #7c9eb433; border-radius: 10px; color: var(--ink); text-decoration: none; background: #fff8; }.citation-link .agent-icon { width: 16px; height: 16px; flex: none; margin-top: 1px; }.citation-link span { min-width: 0; }.citation-link strong,.citation-link small { display: block; }.citation-link strong { font-size: 11px; font-weight: 600; }.citation-link small { margin-top: 3px; color: var(--muted); font-size: 10px; line-height: 1.4; }.citation-link:hover { background: #fff; }
.thinking-message { display: flex; align-items: center; gap: 8px; min-height: 24px; font-size: 13px; white-space: nowrap; }.thinking-orbit { position: relative; display: block; width: 22px; height: 22px; flex: none; }.thinking-orbit i { position: absolute; width: 5px; height: 5px; background: var(--ink); border-radius: 45% 55% 50% 48%; opacity: .6; }.thinking-orbit i:nth-child(1) { left: 8px; top: 1px; }.thinking-orbit i:nth-child(2) { left: 1px; top: 13px; }.thinking-orbit i:nth-child(3) { right: 1px; top: 13px; }.thinking-dots { display: inline-flex; margin-left: 2px; }.thinking-dots i { font-style: normal; margin: 0 1px; }
.withdrawn-message { font-size: 11px; color: var(--muted); margin: 14px 8px; }.is-withdrawn .message-avatar { opacity: .45; }
.edit-message { display: block; width: 100%; resize: vertical; min-height: 60px; border: 0; background: transparent; font: inherit; font-size: 14px; line-height: 1.8; color: var(--ink); outline-offset: 2px; }.edit-actions { display: flex; gap: 15px; justify-content: flex-end; margin-top: 8px; }.edit-actions button { padding: 6px; background: transparent; border: 0; font-size: 12px; }.edit-actions button:last-child { color: #245888; }
.composer-reservation { flex: none; max-height: 100%; }
.composer-section { position: absolute; z-index: 60; left: 0; right: 0; display: flex; flex-direction: column; padding: 8px var(--composer-inset, 17px) 11px; background: #f8f4ea; }
.composer-box { position: relative; display: flex; align-items: flex-end; padding: 9px 9px 9px 15px; gap: 6px; background: transparent; }
.composer-box:focus-within { outline: 2px solid #456e9955; outline-offset: 1px; border-radius: 15px; }
.composer-tools { display: flex; flex: none; align-items: center; gap: 2px; }
.composer-hint { padding: 0 8px; color: var(--muted); font-size: 10px; white-space: nowrap; }
.composer-tool { display: grid; place-items: center; width: 44px; height: 44px; padding: 9px; background: transparent; }
.send-button .agent-icon { width: 24px; height: 24px; }.send-button:disabled { opacity: .65; cursor: default; }
.composer-expand { position: absolute; top: 8px; right: 10px; display: grid; place-items: center; width: 44px; height: 44px; padding: 11px; border: 0; background: transparent; color: var(--ink); }
.composer-expand .agent-icon { width: 22px; height: 22px; }
.composer-section.is-expanded { padding-top: calc(10px + var(--safe-top)); }
.is-expanded .attachments { display: none; }
.is-expanded .composer-box { flex: 1; min-height: 0; flex-direction: column; align-items: stretch; }
.is-expanded .composer-tools { align-self: flex-end; }
.composer-more { position: relative; }.attachment-menu { position: absolute; right: -42px; bottom: 52px; width: 154px; padding: 10px; z-index: 4; background: transparent; backdrop-filter: blur(15px); border-radius: 15px; transform-origin: 70% 100%; }.attachment-menu button { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 8px; min-height: 44px; background: transparent; border: 0; font-size: 13px; }.attachment-menu .agent-icon { width: 22px; height: 22px; }
.attachments { display: flex; flex-wrap: nowrap; gap: 8px; overflow-x: auto; overflow-y: hidden; overscroll-behavior-x: contain; padding: 0 1px 2px; max-height: 65px; }.attachment { display: flex; flex: none; align-items: center; gap: 6px; padding: 9px 8px 9px 11px; max-width: 210px; font-size: 11px; background: transparent; }.attachment>span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.attachment img { display: block; width: 30px; height: 30px; object-fit: cover; border-radius: 5px; }.attachment>.agent-icon { width: 24px; height: 24px; }.attachment button { display: grid; place-items: center; width: 28px; height: 28px; padding: 5px; flex: none; background: transparent; border: 0; }.attachment button .agent-icon { width: 16px; height: 16px; }
.chat-notice { position: absolute; z-index: 70; left: 50%; bottom: 90px; transform: translateX(-50%); width: max-content; max-width: calc(100% - 34px); padding: 13px 18px; font-size: 12px; text-align: center; background: transparent; backdrop-filter: blur(12px); border-radius: 15px; }
.history-overlay { position: absolute; inset: 0; z-index: 80; background: #20304b28; }.history-drawer { display: flex; flex-direction: column; width: 66.6667%; height: 100%; margin: 0; padding: calc(24px + var(--safe-top)) 15px calc(24px + var(--safe-bottom)); background: transparent; backdrop-filter: blur(22px); border-radius: 15px; overflow: hidden; }.history-drawer header { display: flex; align-items: center; justify-content: space-between; gap: 3px; margin-bottom: 22px; }.history-drawer header p { font-size: 11px; margin: 0 0 6px; color: var(--muted); }.history-drawer h2 { margin: 0; font-size: 22px; font-weight: 400; white-space: nowrap; }.drawer-close { display: grid; place-items: center; flex: none; width: 38px; height: 44px; padding: 8px; background: transparent; border: 0; }.drawer-close .agent-icon { width: 22px; height: 22px; }.history-list { min-height: 0; flex: 1; }.history-list h3 { font-size: 11px; color: var(--muted); font-weight: 400; margin: 15px 8px 8px; }.history-list h3:first-child { margin-top: 0; }.history-item { display: flex; gap: 7px; align-items: flex-start; width: 100%; padding: 15px 10px; margin-bottom: 10px; background: transparent; text-align: left; }.history-item>.agent-icon { width: 19px; height: 19px; margin-top: 2px; }.history-item>span { min-width: 0; flex: 1; }.history-item strong { font-size: 13px; font-weight: 400; display: block; line-height: 1.6; }.history-item small { display: block; font-size: 10px; color: var(--muted); margin-top: 5px; line-height: 1.6; }.history-drawer footer { display: flex; align-items: center; gap: 7px; margin-top: 12px; flex: none; }.drawer-avatar { width: 48px; height: 52px; }.history-drawer footer p { font-size: 11px; margin: 0; color: var(--muted); }
.history-empty { padding: 14px 8px; color: var(--muted); font-size: 12px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.history-slide-enter-active,.history-slide-leave-active { transition: background-color .35s ease; }.history-slide-enter-active .history-drawer,.history-slide-leave-active .history-drawer { transition: transform .38s cubic-bezier(.22,1,.36,1); }.history-slide-enter-from,.history-slide-leave-to { background: transparent; }.history-slide-enter-from .history-drawer,.history-slide-leave-to .history-drawer { transform: translateX(-102%); }
.attachment-pop-enter-active,.attachment-pop-leave-active { transition: transform .18s ease, opacity .18s ease; }.attachment-pop-enter-from,.attachment-pop-leave-to { opacity: 0; transform: translateY(6px) scale(.97); }.chat-toast-enter-active,.chat-toast-leave-active { transition: opacity .2s ease; }.chat-toast-enter-from,.chat-toast-leave-to { opacity: 0; }
@media(prefers-reduced-motion:no-preference) { .thinking-orbit { animation: lili-think 2.8s linear infinite; }.thinking-dots i { animation: lili-dot 1.4s ease-in-out infinite; }.thinking-dots i:nth-child(2) { animation-delay: .18s; }.thinking-dots i:nth-child(3) { animation-delay: .36s; } }
@keyframes lili-think { to { transform: rotate(360deg); } }@keyframes lili-dot { 0%,70%,100% { opacity: .3; transform: translateY(0); }35% { opacity: 1; transform: translateY(-2px); } }
@media(max-width:359px) { .agent-page { padding: 0 10px; }.chat-heading { gap: 8px; }.heading-title h1 { font-size: 25px; }.message-avatar { width: 36px; height: 40px; }.message-user .message-avatar { width: 36px; height: 40px; }.message-content,.message-user .message-content { max-width: calc(100% - 41px); }.message-bubble { padding: 12px 13px; }.message-text { font-size: 13px; }.message-actions button { padding-left: 5px; padding-right: 5px; }.message-actions .rating-action { min-width: 29px; }.composer-box { padding-left: 12px; gap: 3px; }.composer-tools { gap: 0; }.history-drawer { padding-left: 10px; padding-right: 10px; }.history-drawer h2 { font-size: 19px; }.history-item { padding-left: 8px; padding-right: 8px; }.history-item strong { font-size: 12px; } }
@media(prefers-reduced-motion:reduce) { .history-slide-enter-active,.history-slide-leave-active,.history-slide-enter-active .history-drawer,.history-slide-leave-active .history-drawer,.attachment-pop-enter-active,.attachment-pop-leave-active,.chat-toast-enter-active,.chat-toast-leave-active { transition: none; } }
</style>
