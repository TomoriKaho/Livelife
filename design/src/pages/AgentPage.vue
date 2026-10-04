<script>
export const pageMeta = {
  key: 'agent', id: 'D-06', title: 'LiLi 智能助手', placeholder: 'Agent 对话页',
  label: 'AGENT', eyebrow: '', icon: 'agent', accent: 'lavender', nav: 'agent',
  back: false, immersive: true, customHeading: true,
};
</script>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import AgentIcon from './agent/AgentIcon.vue';
import LiLiAvatar from './agent/LiLiAvatar.vue';

const originals = [
  { id: 1, role: 'user', text: '哈喽哈喽LiLi，百讲人好多啊，现在有什么活动吗' },
  { id: 2, role: 'agent', text: '百周年纪念讲堂今天和明天的上午和下午都有**百团大战**社团招新活动，你有喜欢的社团活动可以和我分享吗，我可以为你推荐一些' },
  { id: 3, role: 'user', text: '好啊，我对苏协的掼蛋比赛很感兴趣' },
  { id: 4, role: 'agent', text: '', thinking: true },
];
// Randomize the semantic color assignment once, without redrawing the pencil texture on interaction.
const colors = ['mint', 'blue', 'pink', 'lavender', 'yellow'];
for (let i = colors.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [colors[i], colors[j]] = [colors[j], colors[i]]; }
const messages = ref(originals.map((message, i) => ({ ...message, color: colors[i], rating: null, withdrawn: false })));
const history = [
  { label: '今天', title: '百讲的百团大战', summary: '一起找找感兴趣的社团', current: true },
  { label: '昨天', title: '周末，去看一场展览', summary: '校园和附近的展览活动' },
  { label: '', title: '想找人一起打羽毛球', summary: '运动场上的新朋友' },
  { label: '更早', title: '第一次来燕园逛逛', summary: '从未名湖开始的校园漫游' },
];
const historyOpen = ref(false), drawer = ref(null), historyTrigger = ref(null), mounted = ref(false);
const moreOpen = ref(false), imageInput = ref(null), fileInput = ref(null), composer = ref(null);
const draft = ref(''), attachments = ref([]), editingId = ref(null), editText = ref(''), notice = ref('');
const ready = computed(() => draft.value.trim() || attachments.value.length);
let noticeTimer, previousFocus, inerted = [], attachmentId = 0;
function notify(text) { clearTimeout(noticeTimer); notice.value = text; noticeTimer = setTimeout(() => { notice.value = ''; }, 2400); }
const segments = text => text.split(/(\*\*[^*]+\*\*)/g).map(value => ({ text: value.startsWith('**') ? value.slice(2, -2) : value, bold: value.startsWith('**') }));
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
async function edit(message) {
  editingId.value = message.id; editText.value = message.text;
  await nextTick(); document.querySelector(`#lili-edit-${message.id}`)?.focus();
}
function saveEdit(message) { if (!editText.value.trim()) return; message.text = editText.value.trim(); editingId.value = null; notify('消息已编辑'); }
function withdraw(message) { message.withdrawn = true; if (editingId.value === message.id) editingId.value = null; notify('消息已撤回'); }
function rate(message, value) { message.rating = message.rating === value ? null : value; }
function pick(kind) { moreOpen.value = false; (kind === 'image' ? imageInput.value : fileInput.value)?.click(); }
function addFiles(event, kind) {
  for (const file of event.target.files || []) {
    if (kind === 'image' && !file.type.startsWith('image/')) { notify('请选择图片文件'); continue; }
    attachments.value.push({ id: ++attachmentId, name: file.name, file, kind, preview: kind === 'image' ? URL.createObjectURL(file) : '' });
  }
  event.target.value = ''; nextTick(() => composer.value?.focus());
}
function removeFile(item) { if (item.preview) URL.revokeObjectURL(item.preview); attachments.value = attachments.value.filter(row => row.id !== item.id); }
function resizeInput() { if (!composer.value) return; composer.value.style.height = 'auto'; composer.value.style.height = `${Math.min(100, composer.value.scrollHeight)}px`; }
function send() { if (ready.value) notify('发送功能将在后续开放'); }
function chooseHistory(item) { historyOpen.value = false; if (!item.current) notify('这是一条历史对话示例'); }
function outside(event) { if (!event.target.closest('.composer-more')) moreOpen.value = false; }
function keydown(event) {
  if (event.key === 'Escape') { historyOpen.value = false; moreOpen.value = false; editingId.value = null; }
  if (!historyOpen.value || event.key !== 'Tab') return;
  const nodes = [...drawer.value.querySelectorAll('button,a,input,textarea')].filter(node => !node.disabled);
  const first = nodes[0], last = nodes.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
function releaseDrawer() { for (const [node, value] of inerted) node.inert = value; inerted = []; }
watch(historyOpen, async open => {
  if (open) {
    moreOpen.value = false; previousFocus = document.activeElement; await nextTick();
    if (!mounted.value || !historyOpen.value || !drawer.value) return;
    inerted = [...document.querySelector('.phone-shell').children].filter(node => !node.classList.contains('history-overlay')).map(node => [node, node.inert]);
    for (const [node] of inerted) node.inert = true;
    drawer.value?.querySelector('button')?.focus({ preventScroll: true });
  } else { releaseDrawer(); if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true }); }
});
onMounted(() => { mounted.value = true; document.addEventListener('pointerdown', outside); document.addEventListener('keydown', keydown); });
onBeforeUnmount(() => { mounted.value = false; clearTimeout(noticeTimer); releaseDrawer(); document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', keydown); for (const file of attachments.value) if (file.preview) URL.revokeObjectURL(file.preview); });
</script>

<template>
  <section class="agent-page" aria-label="LiLi 智能助手对话">
    <header class="chat-heading">
      <button ref="historyTrigger" v-sketch class="sketch history-button" type="button" aria-label="打开历史对话" aria-controls="lili-history" :aria-expanded="historyOpen" @click="historyOpen = true"><AgentIcon name="menu" /></button>
      <div class="heading-title"><h1>LiLi<span>智能助手</span></h1><p>和我聊聊校园里的新鲜事</p></div>
      <span class="heading-doodle" aria-hidden="true"><svg viewBox="0 0 44 34"><path d="m8 20 6-12 M21 16l2-12 M30 21l8-7" /></svg></span>
    </header>

    <div class="conversation" role="region" aria-label="当前对话" tabindex="0">
      <p class="conversation-date">今天</p>
      <article v-for="message in messages" :key="message.id" class="message" :class="[`message-${message.role}`, { 'is-withdrawn': message.withdrawn }]" :aria-label="message.role === 'user' ? '你的消息' : 'LiLi 的消息'">
        <div class="message-avatar" aria-hidden="true"><LiLiAvatar v-if="message.role === 'agent'" :thinking="message.thinking" /><svg v-else class="user-avatar" viewBox="0 0 48 48"><g stroke="#20304b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path fill="#c4eed7" d="M5 42q1-14 19-15 18 1 19 15Z" /><path fill="#fff1d7" d="M13 13q11-7 22 0l-1 13q-3 9-10 9t-11-9Z" /><path fill="#20304b" d="M11 18q-2-17 13-17 15 0 13 17l-6-7-4 4-6-3-10 6Z" /><path fill="none" d="M16 23h6v5h-6Z M26 23h6v5h-6Z M22 25h4 M22 30q2 2 4 0" /></g></svg></div>
        <div class="message-content">
          <p v-if="message.withdrawn" class="withdrawn-message">你撤回了一条消息</p>
          <div v-else v-sketch class="sketch pencil-fill message-bubble" :data-pencil="message.color">
            <template v-if="editingId === message.id"><textarea :id="`lili-edit-${message.id}`" v-model="editText" class="edit-message" rows="3" aria-label="编辑消息内容"></textarea><div class="edit-actions"><button type="button" @click="editingId = null">取消</button><button type="button" :disabled="!editText.trim()" @click="saveEdit(message)">保存</button></div></template>
            <div v-else-if="message.thinking" class="thinking-message" role="status" aria-label="LiLi 正在准备回答"><span class="thinking-orbit" aria-hidden="true"><i></i><i></i><i></i></span><span>正在准备回答<span class="thinking-dots" aria-hidden="true"><i>·</i><i>·</i><i>·</i></span></span></div>
            <p v-else class="message-text"><template v-for="(part, i) in segments(message.text)" :key="i"><strong v-if="part.bold">{{ part.text }}</strong><template v-else>{{ part.text }}</template></template></p>
          </div>
          <div v-if="!message.withdrawn && editingId !== message.id" class="message-actions" :aria-label="message.role === 'agent' ? '助手消息操作' : '你的消息操作'">
            <button type="button" :disabled="message.thinking" aria-label="复制消息" @click="copy(message)"><AgentIcon name="copy" /><span>复制</span></button>
            <template v-if="message.role === 'user'"><button type="button" @click="edit(message)"><AgentIcon name="edit" /><span>编辑</span></button><button type="button" @click="withdraw(message)"><AgentIcon name="withdraw" /><span>撤回</span></button></template>
            <template v-else><button type="button" :disabled="message.thinking" @click="notify('重新生成将在后续开放')"><AgentIcon name="regenerate" /><span>重新生成</span></button><button type="button" class="rating-action" :disabled="message.thinking" :class="{ selected: message.rating === 'like' }" :aria-pressed="message.rating === 'like'" aria-label="点赞这条回答" title="点赞" @click="rate(message, 'like')"><AgentIcon name="like" /><span class="sr-only">点赞</span></button><button type="button" class="rating-action" :disabled="message.thinking" :class="{ selected: message.rating === 'dislike' }" :aria-pressed="message.rating === 'dislike'" aria-label="点踩这条回答" title="点踩" @click="rate(message, 'dislike')"><AgentIcon name="dislike" /><span class="sr-only">点踩</span></button></template>
          </div>
        </div>
      </article>
    </div>

    <section class="composer-section" aria-label="消息输入区">
      <div v-if="attachments.length" class="attachments" aria-label="已选择的附件"><div v-for="item in attachments" :key="item.id" v-sketch class="sketch attachment" :data-pencil="item.kind === 'image' ? 'pink' : 'mint'"><img v-if="item.preview" :src="item.preview" :alt="item.name" /><AgentIcon v-else name="file" /><span>{{ item.name }}</span><button type="button" :aria-label="`移除 ${item.name}`" @click="removeFile(item)"><AgentIcon name="close" /></button></div></div>
      <div v-sketch class="sketch composer-box">
        <textarea ref="composer" v-model="draft" rows="1" placeholder="想聊点什么？" aria-label="输入给 LiLi 的消息" @input="resizeInput" @keydown.ctrl.enter.prevent="send" @keydown.meta.enter.prevent="send"></textarea>
        <div class="composer-tools">
          <div class="composer-more"><button v-sketch class="sketch composer-tool" type="button" :data-pencil="moreOpen ? 'blue' : undefined" aria-label="添加图片或文件" aria-controls="lili-attachments-menu" :aria-expanded="moreOpen" @click="moreOpen = !moreOpen"><AgentIcon name="plus" /></button><Transition name="attachment-pop"><div v-if="moreOpen" id="lili-attachments-menu" v-sketch class="sketch attachment-menu" data-pencil="mint" role="group" aria-label="添加附件"><button type="button" @click="pick('image')"><AgentIcon name="image" /><span>上传图片</span></button><button type="button" @click="pick('file')"><AgentIcon name="file" /><span>上传文件</span></button></div></Transition></div>
          <button v-sketch class="sketch composer-tool send-button" data-pencil="yellow" type="button" :disabled="!ready" aria-label="发送消息（设计占位）" @click="send"><AgentIcon name="send" /></button>
        </div>
      </div>
      <input ref="imageInput" class="sr-only" type="file" accept="image/*" multiple tabindex="-1" aria-label="选择图片" @change="addFiles($event, 'image')" /><input ref="fileInput" class="sr-only" type="file" multiple tabindex="-1" aria-label="选择文件" @change="addFiles($event, 'file')" />
    </section>

    <Transition name="chat-toast"><p v-if="notice" v-sketch class="sketch chat-notice" data-pencil="yellow" role="status">{{ notice }}</p></Transition>

    <Teleport v-if="mounted" to=".phone-shell"><Transition name="history-slide"><div v-if="historyOpen" class="history-overlay" @click.self="historyOpen = false"><aside id="lili-history" ref="drawer" v-sketch class="sketch history-drawer" data-pencil="mint" role="dialog" aria-modal="true" aria-labelledby="lili-history-title"><header><div><p>和 LiLi 的</p><h2 id="lili-history-title">小小对话簿</h2></div><button type="button" class="drawer-close" aria-label="关闭历史对话" @click="historyOpen = false"><AgentIcon name="close" /></button></header><div class="history-list"><template v-for="(item, index) in history" :key="index"><h3 v-if="item.label">{{ item.label }}</h3><button v-sketch class="sketch history-item" :data-pencil="item.current ? 'yellow' : undefined" type="button" :aria-current="item.current ? 'true' : undefined" @click="chooseHistory(item)"><AgentIcon name="chat" /><span><strong>{{ item.title }}</strong><small>{{ item.summary }}</small></span></button></template></div><footer><div class="drawer-avatar"><LiLiAvatar /></div><p>校园生活，慢慢聊。</p></footer></aside></div></Transition></Teleport>
  </section>
</template>

<style scoped>
.agent-page { position: relative; display: flex; flex: 1; flex-direction: column; min-height: 0; overflow: hidden; padding: 0 17px; }
.chat-heading { display: flex; flex: none; align-items: center; gap: 12px; padding: 7px 0 15px; }
.history-button { display: grid; place-items: center; width: 44px; height: 44px; padding: 8px; flex: none; background: transparent; }
.heading-title { flex: 1; min-width: 0; }.heading-title h1 { font-size: 28px; display: flex; align-items: baseline; gap: 10px; }.heading-title h1 span { font-size: 13px; letter-spacing: 0; -webkit-text-stroke: 0; color: var(--muted); }.heading-title p { margin: 3px 0 0; font-size: 11px; color: var(--muted); }
.heading-doodle { width: 33px; color: #d5b729; }.heading-doodle svg { width: 100%; fill: none; stroke: currentColor; stroke-width: 2.4; stroke-linecap: round; }
.conversation { flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; overscroll-behavior: contain; scrollbar-width: thin; padding: 0 2px 18px; outline-offset: -3px; }
.conversation-date { text-align: center; color: var(--muted); font-size: 10px; margin: 0 0 12px; letter-spacing: 2px; }.message { display: flex; gap: 6px; margin-bottom: 10px; }.message:last-child { margin-bottom: 0; }.message-user { flex-direction: row-reverse; }
.message-avatar { width: 43px; height: 47px; flex: none; margin-top: 3px; }.message-user .message-avatar { width: 34px; height: 38px; margin-top: 6px; }.user-avatar { width: 100%; height: 100%; display: block; }
.message-content { max-width: calc(100% - 49px); min-width: 0; }.message-user .message-content { max-width: calc(100% - 48px); }
.message-bubble { padding: 11px 16px 12px; min-height: 49px; background: transparent; }.message-text { margin: 0; font-size: 14px; line-height: 1.85; overflow-wrap: anywhere; white-space: pre-wrap; }.message-text strong { font-weight: 400; -webkit-text-stroke: .35px var(--ink); text-decoration: underline; text-decoration-color: #20304b44; text-decoration-thickness: 3px; text-underline-offset: 3px; }
.message-actions { display: flex; align-items: center; gap: 0; margin: 1px 1px 0; min-height: 34px; }.message-user .message-actions { justify-content: flex-end; }.message-actions button { display: inline-flex; align-items: center; justify-content: center; gap: 3px; padding: 7px 6px; min-height: 34px; border: 0; background: transparent; color: var(--muted); font-size: 10px; white-space: nowrap; }.message-actions .agent-icon { width: 14px; height: 14px; stroke-width: 1.8; }.message-actions .rating-action { min-width: 34px; }.message-actions .rating-action .agent-icon { width: 16px; height: 16px; }.message-actions .selected { color: #245888; }.message-actions .selected .agent-icon { fill: #9ac8f244; stroke-width: 2.2; }.message-actions button:disabled { opacity: .35; cursor: default; }
.thinking-message { display: flex; align-items: center; gap: 8px; min-height: 24px; font-size: 13px; white-space: nowrap; }.thinking-orbit { position: relative; display: block; width: 22px; height: 22px; flex: none; }.thinking-orbit i { position: absolute; width: 5px; height: 5px; background: var(--ink); border-radius: 45% 55% 50% 48%; opacity: .6; }.thinking-orbit i:nth-child(1) { left: 8px; top: 1px; }.thinking-orbit i:nth-child(2) { left: 1px; top: 13px; }.thinking-orbit i:nth-child(3) { right: 1px; top: 13px; }.thinking-dots { display: inline-flex; margin-left: 2px; }.thinking-dots i { font-style: normal; margin: 0 1px; }
.withdrawn-message { font-size: 11px; color: var(--muted); margin: 14px 8px; }.is-withdrawn .message-avatar { opacity: .45; }
.edit-message { display: block; width: 100%; resize: vertical; min-height: 60px; border: 0; background: transparent; font: inherit; font-size: 14px; line-height: 1.8; color: var(--ink); outline-offset: 2px; }.edit-actions { display: flex; gap: 15px; justify-content: flex-end; margin-top: 8px; }.edit-actions button { padding: 6px; background: transparent; border: 0; font-size: 12px; }.edit-actions button:last-child { color: #245888; }
.composer-section { position: relative; flex: none; padding: 8px 0 11px; }.composer-box { display: flex; align-items: flex-end; padding: 9px 9px 9px 15px; gap: 6px; background: transparent; }.composer-box>textarea { width: 0; flex: 1; min-height: 44px; max-height: 100px; resize: none; border: 0; background: transparent; font: inherit; font-size: 14px; color: var(--ink); line-height: 24px; padding: 10px 0; outline: none; }.composer-box:focus-within { outline: 2px solid #456e9955; outline-offset: 1px; border-radius: 15px; }.composer-box>textarea::placeholder { color: var(--muted); }.composer-tools { display: flex; align-items: center; gap: 2px; }.composer-tool { display: grid; place-items: center; width: 44px; height: 44px; padding: 9px; background: transparent; }.send-button .agent-icon { width: 24px; height: 24px; }.send-button:disabled { opacity: .65; cursor: default; }
.composer-more { position: relative; }.attachment-menu { position: absolute; right: -42px; bottom: 52px; width: 154px; padding: 10px; z-index: 4; background: transparent; backdrop-filter: blur(15px); border-radius: 15px; transform-origin: 70% 100%; }.attachment-menu button { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 8px; min-height: 44px; background: transparent; border: 0; font-size: 13px; }.attachment-menu .agent-icon { width: 22px; height: 22px; }
.attachments { display: flex; gap: 8px; overflow-x: auto; padding: 0 1px 8px; max-height: 65px; scrollbar-width: thin; }.attachment { display: flex; flex: none; align-items: center; gap: 6px; padding: 9px 8px 9px 11px; max-width: 210px; font-size: 11px; background: transparent; }.attachment>span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.attachment img { display: block; width: 30px; height: 30px; object-fit: cover; border-radius: 5px; }.attachment>.agent-icon { width: 24px; height: 24px; }.attachment button { display: grid; place-items: center; width: 28px; height: 28px; padding: 5px; flex: none; background: transparent; border: 0; }.attachment button .agent-icon { width: 16px; height: 16px; }
.chat-notice { position: absolute; z-index: 7; left: 50%; bottom: 90px; transform: translateX(-50%); width: max-content; max-width: calc(100% - 34px); padding: 13px 18px; font-size: 12px; text-align: center; background: transparent; backdrop-filter: blur(12px); border-radius: 15px; }
.history-overlay { position: absolute; inset: 0; z-index: 80; background: #20304b28; }.history-drawer { display: flex; flex-direction: column; width: 66.6667%; height: 100%; margin: 0; padding: calc(24px + env(safe-area-inset-top, 0px)) 15px 24px; background: transparent; backdrop-filter: blur(22px); border-radius: 15px; overflow: hidden; }.history-drawer header { display: flex; align-items: center; justify-content: space-between; gap: 3px; margin-bottom: 22px; }.history-drawer header p { font-size: 11px; margin: 0 0 6px; color: var(--muted); }.history-drawer h2 { margin: 0; font-size: 22px; font-weight: 400; white-space: nowrap; }.drawer-close { display: grid; place-items: center; flex: none; width: 38px; height: 44px; padding: 8px; background: transparent; border: 0; }.drawer-close .agent-icon { width: 22px; height: 22px; }.history-list { min-height: 0; overflow-y: auto; flex: 1; scrollbar-width: thin; }.history-list h3 { font-size: 11px; color: var(--muted); font-weight: 400; margin: 15px 8px 8px; }.history-list h3:first-child { margin-top: 0; }.history-item { display: flex; gap: 7px; align-items: flex-start; width: 100%; padding: 15px 10px; margin-bottom: 10px; background: transparent; text-align: left; }.history-item>.agent-icon { width: 19px; height: 19px; margin-top: 2px; }.history-item>span { min-width: 0; flex: 1; }.history-item strong { font-size: 13px; font-weight: 400; display: block; line-height: 1.6; }.history-item small { display: block; font-size: 10px; color: var(--muted); margin-top: 5px; line-height: 1.6; }.history-drawer footer { display: flex; align-items: center; gap: 7px; margin-top: 12px; flex: none; }.drawer-avatar { width: 48px; height: 52px; }.history-drawer footer p { font-size: 11px; margin: 0; color: var(--muted); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.history-slide-enter-active,.history-slide-leave-active { transition: background-color .35s ease; }.history-slide-enter-active .history-drawer,.history-slide-leave-active .history-drawer { transition: transform .38s cubic-bezier(.22,1,.36,1); }.history-slide-enter-from,.history-slide-leave-to { background: transparent; }.history-slide-enter-from .history-drawer,.history-slide-leave-to .history-drawer { transform: translateX(-102%); }
.attachment-pop-enter-active,.attachment-pop-leave-active { transition: transform .18s ease, opacity .18s ease; }.attachment-pop-enter-from,.attachment-pop-leave-to { opacity: 0; transform: translateY(6px) scale(.97); }.chat-toast-enter-active,.chat-toast-leave-active { transition: opacity .2s ease; }.chat-toast-enter-from,.chat-toast-leave-to { opacity: 0; }
@media(prefers-reduced-motion:no-preference) { .thinking-orbit { animation: lili-think 2.8s linear infinite; }.thinking-dots i { animation: lili-dot 1.4s ease-in-out infinite; }.thinking-dots i:nth-child(2) { animation-delay: .18s; }.thinking-dots i:nth-child(3) { animation-delay: .36s; } }
@keyframes lili-think { to { transform: rotate(360deg); } }@keyframes lili-dot { 0%,70%,100% { opacity: .3; transform: translateY(0); }35% { opacity: 1; transform: translateY(-2px); } }
@media(max-width:359px) { .agent-page { padding: 0 10px; }.chat-heading { gap: 8px; }.heading-title h1 { font-size: 25px; }.heading-title p { font-size: 10px; }.heading-doodle { width: 25px; }.message-avatar { width: 36px; height: 40px; }.message-user .message-avatar { width: 30px; height: 34px; }.message-content,.message-user .message-content { max-width: calc(100% - 41px); }.message-bubble { padding: 12px 13px; }.message-text { font-size: 13px; }.message-actions button { padding-left: 5px; padding-right: 5px; }.message-actions .rating-action { min-width: 29px; }.composer-box { padding-left: 12px; gap: 3px; }.composer-tools { gap: 0; }.history-drawer { padding-left: 10px; padding-right: 10px; }.history-drawer h2 { font-size: 19px; }.history-item { padding-left: 8px; padding-right: 8px; }.history-item strong { font-size: 12px; } }
@media(prefers-reduced-motion:reduce) { .history-slide-enter-active,.history-slide-leave-active,.history-slide-enter-active .history-drawer,.history-slide-leave-active .history-drawer,.attachment-pop-enter-active,.attachment-pop-leave-active,.chat-toast-enter-active,.chat-toast-leave-active { transition: none; } }
</style>
