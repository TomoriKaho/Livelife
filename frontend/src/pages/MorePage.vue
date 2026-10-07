<script>
export const pageMeta = {
  key: 'more', id: 'D-07', title: '我的', placeholder: '个人资料、兴趣与设置',
  label: 'MORE', eyebrow: '', icon: 'user', accent: 'yellow', nav: 'more',
  back: false, heading: false, footer: false, immersive: true,
};
</script>

<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ElasticList from './agent/ElasticList.vue';
import FavoritesList from './more/FavoritesList.vue';
import { savedActivities, activityStatus } from '../data/favorites.js';
import { interests, genders } from './onboarding/options.js';
import OnboardingIcon from './onboarding/OnboardingIcon.vue';
import ProfileAvatar from './more/ProfileAvatar.vue';
import MoreIcon from './more/MoreIcon.vue';
import PreferenceSwitch from './more/PreferenceSwitch.vue';
import InterestPreferences from './more/InterestPreferences.vue';
import { initialProfile, initialInterests, menuItems, titles } from './more/demo.js';

const showInternalTools = import.meta.env.VITE_INTERNAL_TOOLS === 'true';
const HelloConnectionTest = showInternalTools
  ? defineAsyncComponent(() => import('./more/HelloConnectionTest.vue'))
  : null;

const router = useRouter(), route = useRoute(), root = ref(null), pane = ref(route.query.pane === 'favorites' ? 'favorites' : 'home');
const paneTrail = [];
const profile = reactive({ ...initialProfile }), profileDraft = reactive({ ...initialProfile });
const selectedInterests = ref([...initialInterests]);
const pickedInterests = computed(() => interests.filter(item => selectedInterests.value.includes(item.id)));
const prefs = reactive({ personalized: true, reminders: true, recommendations: false, location: true, useIdentity: true, useInterests: true, quiet: false });
const advance = ref('30分钟'), recommendationMode = ref('interest');
const password = ref(''), confirmPassword = ref(''), passwordChanged = ref(false);
const feedback = ref(''), notice = ref('');
let noticeTimer;
const favoritesSummary = computed(() => `收藏 ${savedActivities.value.length} 个活动 · ${savedActivities.value.filter(item => activityStatus(item) === 'upcoming').length} 个待开始`);
function notify(text) { clearTimeout(noticeTimer); notice.value = text; noticeTimer = setTimeout(() => { notice.value = ''; }, 2400); }
function open(id) {
  if (id === pane.value) return;
  paneTrail.push(pane.value);
  if (id === 'profile') Object.assign(profileDraft, profile);
  if (id === 'password') { password.value = ''; confirmPassword.value = ''; }
  pane.value = id;
  if (id === 'favorites') router.replace({ path: '/more', query: { pane: 'favorites' } });
}
function goBack() { pane.value = paneTrail.pop() || 'home'; if (route.query.pane) router.replace('/more'); }
function saveProfile() {
  if (!profileDraft.nickname.trim()) return;
  Object.assign(profile, profileDraft, { nickname: profileDraft.nickname.trim(), bio: profileDraft.bio.trim() });
  paneTrail.length = 0; pane.value = 'home'; notify('资料已保存');
}
function saveInterests(value) { selectedInterests.value = [...value.selected]; prefs.personalized = value.personalized; recommendationMode.value = value.mode; paneTrail.length = 0; pane.value = 'home'; notify('兴趣与推荐设置已保存'); }
function savePassword() {
  if (!password.value || !confirmPassword.value) return;
  if (password.value !== confirmPassword.value) { notify('两次输入的密码不一致'); return; }
  passwordChanged.value = true; password.value = ''; confirmPassword.value = ''; goBack(); notify('已演示密码更新');
}
function sendFeedback() { if (feedback.value.trim()) notify('谢谢你的建议！提交功能将在后续开放'); }
watch(pane, async () => {
  await nextTick();
  root.value?.querySelector('h1')?.focus({ preventScroll: true });
});
onBeforeUnmount(() => { clearTimeout(noticeTimer); password.value = ''; confirmPassword.value = ''; });
</script>

<template>
  <ElasticList :key="pane" class="more-page" aria-label="个人资料与设置内容"><div ref="root" class="more-content">
    <template v-if="pane === 'home'">
      <section class="profile-header" aria-label="个人资料">
        <ProfileAvatar :kind="profile.avatar" />
        <div class="profile-copy"><h1 tabindex="-1">{{ profile.nickname }}</h1><p class="profile-identity">北京大学 · {{ profile.identity }}</p><p class="profile-bio">{{ profile.bio || '在燕园，遇见更多有趣的事。' }}</p></div>
        <button class="edit-profile" type="button" aria-label="编辑个人资料" @click="open('profile')"><MoreIcon name="edit" /></button>
      </section>
      <section v-sketch class="interest-card sketch sketch-white" aria-labelledby="home-interest-title">
        <header class="section-heading"><h2 id="home-interest-title">兴趣小档案</h2><button type="button" @click="open('interests')">调整 <MoreIcon name="chevron" /></button></header>
        <div v-if="pickedInterests.length" class="interest-tags" :class="{ muted: !prefs.personalized }"><span v-for="item in pickedInterests" :key="item.id" v-sketch class="interest-tag sketch pencil-fill" :data-pencil="item.pencil"><OnboardingIcon :name="item.icon" />{{ item.label }}</span></div>
        <p v-else class="empty-interests">还没圈定兴趣？点击“调整”，找到喜欢的事。</p>
        <p class="card-footnote">{{ prefs.personalized ? '把喜欢的事，留一点位置。' : '个性化推荐已关闭，点击调整可重新开启。' }}</p>
      </section>
      <button v-sketch class="favorites-entry sketch pencil-fill" data-pencil="yellow" type="button" @click="open('favorites')"><MoreIcon name="heart" /><span><strong>收藏列表</strong><small>{{ favoritesSummary }}</small></span><MoreIcon class="row-chevron" name="chevron" /></button>
      <section class="settings-menu" aria-label="个人设置">
        <button v-for="item in menuItems" :key="item.id" class="menu-row" type="button" @click="open(item.id)"><span v-sketch class="menu-icon sketch" :data-pencil="item.color"><MoreIcon :name="item.icon" /></span><span class="menu-copy"><strong>{{ item.label }}</strong><small>{{ item.note }}</small></span><MoreIcon class="row-chevron" name="chevron" /><svg class="row-divider" viewBox="0 0 360 6" preserveAspectRatio="none" aria-hidden="true"><path d="M4 3 Q85 2 174 3 T356 3" /></svg></button>
      </section>
    </template>
    <template v-else>
      <header class="pane-heading"><button type="button" class="back-button" aria-label="返回" @click="goBack"><MoreIcon name="back" /></button><h1 tabindex="-1">{{ titles[pane] }}</h1></header>
      <form v-if="pane === 'profile'" class="profile-form" @submit.prevent="saveProfile">
        <p class="pane-lede">让这张小名片，更像你一点。</p>
        <div class="avatar-options" role="group" aria-label="选择头像"><button v-for="item in [{ id: 'student', label: '燕园同学' }, { id: 'star', label: '小星星' }, { id: 'leaf', label: '小树叶' }]" :key="item.id" type="button" :aria-label="`选择${item.label}头像`" :aria-pressed="profileDraft.avatar === item.id" @click="profileDraft.avatar = item.id"><ProfileAvatar :kind="item.id" /><span>{{ item.label }}</span><MoreIcon v-if="profileDraft.avatar === item.id" name="check" /></button></div>
        <label class="form-field"><span>昵称</span><div v-sketch class="field-outline sketch"><input v-model="profileDraft.nickname" maxlength="16" autocomplete="nickname" required aria-label="昵称" /></div></label>
        <div class="form-two-columns"><label class="form-field"><span>校园身份</span><div v-sketch class="field-outline sketch"><select v-model="profileDraft.identity" aria-label="校园身份"><option>本科生</option><option>研究生</option><option>教职工</option><option>校友</option><option>访客</option></select></div></label><label class="form-field"><span>性别</span><div v-sketch class="field-outline sketch"><select v-model="profileDraft.gender" aria-label="性别"><option v-for="item in genders" :key="item.id" :value="item.id">{{ item.label }}</option></select></div></label></div>
        <label class="form-field"><span>院系</span><div v-sketch class="field-outline sketch"><input v-model="profileDraft.school" maxlength="30" aria-label="院系" placeholder="也可以暂时不填" /></div></label>
        <label class="form-field"><span>一句话介绍自己</span><div v-sketch class="field-outline sketch"><textarea v-model="profileDraft.bio" rows="2" maxlength="60" aria-label="个人介绍" placeholder="最近想探索些什么？"></textarea></div></label>
        <button v-sketch class="primary-button sketch" data-pencil="yellow" type="submit" :disabled="!profileDraft.nickname.trim()">保存资料 <MoreIcon name="check" /></button>
      </form>
      <InterestPreferences v-else-if="pane === 'interests'" :selected="selectedInterests" :personalized="prefs.personalized" :mode="recommendationMode" @save="saveInterests" />
      <FavoritesList v-else-if="pane === 'favorites'" @remove="notify" />
      <section v-else-if="pane === 'permissions'" aria-label="通知与定位设置">
        <h2 class="field-heading">活动通知</h2>
        <div class="switch-row"><span><strong>活动提醒</strong><small>提醒已收藏活动的开始时间</small></span><PreferenceSwitch v-model="prefs.reminders" label="活动提醒" /></div>
        <div class="switch-row"><span><strong>兴趣推荐通知</strong><small>有新的相关活动时提醒我</small></span><PreferenceSwitch v-model="prefs.recommendations" label="兴趣推荐通知" /></div>
        <div class="switch-row"><span><strong>夜间免打扰</strong><small>22:00—08:00 不发送活动通知</small></span><PreferenceSwitch v-model="prefs.quiet" label="夜间免打扰" /></div>
        <h2 class="field-heading">提前多久提醒？</h2>
        <div class="time-choices" role="group" aria-label="活动提醒提前时间"><button v-for="time in ['15分钟', '30分钟', '1小时']" :key="time" v-sketch class="sketch" :data-pencil="advance === time ? 'blue' : undefined" type="button" :aria-pressed="advance === time" :disabled="!prefs.reminders" @click="advance = time">{{ time }}</button></div>
        <h2 class="field-heading spaced-heading">定位</h2>
        <div class="switch-row"><span><strong>使用定位发现附近活动</strong><small>开启后，以当前位置寻找附近信息</small></span><PreferenceSwitch v-model="prefs.location" label="使用定位发现附近活动" /></div>
        <p class="small-note">当前校区：北京大学燕园校区</p>
      </section>
      <section v-else-if="pane === 'account'" aria-label="账户与隐私设置">
        <h2 class="field-heading">账户信息</h2>
        <dl class="account-info"><div><dt>账户 ID</dt><dd>LL · 20260018</dd></div><div><dt>登录邮箱</dt><dd>yan***@pku.edu.cn</dd></div></dl>
        <button class="plain-setting" type="button" @click="open('password')"><span>登录密码<small>{{ passwordChanged ? '刚刚更新 · 界面预览' : '已设置' }}</small></span><span>修改 <MoreIcon name="chevron" /></span></button>
        <h2 class="field-heading spaced-heading">推荐数据偏好</h2><p class="small-note">你来决定，推荐可以参考哪些信息。</p>
        <div class="switch-row"><span><strong>使用校园身份</strong><small>根据学生、教职工等身份筛选信息</small></span><PreferenceSwitch v-model="prefs.useIdentity" label="推荐使用校园身份" /></div>
        <div class="switch-row"><span><strong>使用兴趣标签</strong><small>根据你圈选的兴趣调整推荐</small></span><PreferenceSwitch v-model="prefs.useInterests" label="推荐使用兴趣标签" /></div>
        <p class="preview-note">当前为界面预览，账户和设置均为示例。</p>
        <button v-sketch class="secondary-button sketch" type="button" @click="router.push('/onboarding')"><MoreIcon name="logout" />退出登录</button>
      </section>
      <form v-else-if="pane === 'password'" @submit.prevent="savePassword">
        <p class="pane-lede">为账户换一个新的密码。</p>
        <label class="form-field"><span>新密码</span><div v-sketch class="field-outline sketch"><input v-model="password" type="password" autocomplete="new-password" required aria-label="新密码" /></div></label>
        <label class="form-field"><span>再次输入新密码</span><div v-sketch class="field-outline sketch"><input v-model="confirmPassword" type="password" autocomplete="new-password" required aria-label="确认新密码" /></div></label>
        <p class="preview-note">仅演示修改流程，不更改真实账户。</p>
        <button v-sketch class="primary-button sketch" data-pencil="yellow" type="submit" :disabled="!password || !confirmPassword">确认修改</button>
      </form>
      <section v-else-if="pane === 'appearance'" aria-label="界面风格选择">
        <p class="pane-lede">用喜欢的颜色，打开校园生活。</p>
        <div v-sketch class="style-preview sketch" data-pencil="yellow"><div v-sketch class="mini-ui sketch" aria-hidden="true"><div v-sketch class="mini-header sketch" data-pencil="blue"></div><div class="mini-tags"><i v-sketch class="sketch" data-pencil="mint"></i><i v-sketch class="sketch" data-pencil="pink"></i></div><div v-sketch class="mini-nav sketch" data-pencil="yellow"></div></div><div><h2>彩铅手绘</h2><p>黑铅勾线 · 彩铅平涂 · 小赖字体</p><span class="current-style"><MoreIcon name="check" />正在使用</span></div></div>
        <button v-sketch class="future-style sketch" type="button" disabled><MoreIcon name="palette" /><span>更多界面风格<small>正在准备中</small></span></button>
      </section>
      <section v-else-if="pane === 'help'" aria-label="帮助与反馈">
        <h2 class="field-heading">一点小帮助</h2>
        <details class="help-question"><summary>想换一换推荐的活动？</summary><p>从兴趣小档案调整标签，也可以在兴趣小档案的最后选择“多些新发现”。</p></details>
        <details class="help-question"><summary>在哪里看近期活动？</summary><p>活动日历按日期整理校园活动；活动地图可以查看地点、建筑与楼层。</p></details>
        <div class="help-links"><button v-sketch class="sketch" data-pencil="blue" type="button" @click="router.push('/calendar')">去看活动日历</button><button v-sketch class="sketch" data-pencil="mint" type="button" @click="router.push('/agent')">和 LiLi 聊聊</button></div>
        <HelloConnectionTest v-if="showInternalTools" />
        <h2 class="field-heading spaced-heading">想对我们说</h2>
        <label class="form-field"><span class="sr-only">反馈内容</span><div v-sketch class="field-outline sketch"><textarea v-model="feedback" rows="4" maxlength="500" aria-label="反馈内容" placeholder="遇到了什么问题，或有什么新想法？"></textarea></div></label>
        <button v-sketch class="primary-button sketch" data-pencil="yellow" type="button" :disabled="!feedback.trim()" @click="sendFeedback">提交反馈</button>
        <p class="home-note">LiveLife<span>发现校园生活的每一种颜色。<br />界面预览 · v0.1</span></p>
      </section>
    </template>
    <Teleport to=".phone-shell" defer><Transition name="more-toast"><p v-if="notice" v-sketch class="more-notice sketch" data-pencil="yellow" role="status">{{ notice }}</p></Transition></Teleport>
  </div></ElasticList>
</template>

<style scoped>
.more-page { flex: 1; min-height: 0; width: 100%; }
.more-content { padding: 8px 17px 18px; }
.interest-tags.muted { opacity: .5; }
.profile-header { position: relative; display: flex; align-items: center; gap: 13px; margin: 2px 0 21px; padding: 7px 3px; min-height: 106px; }
.profile-copy { flex: 1; min-width: 0; padding-right: 23px; }.profile-copy h1 { margin: 0 0 9px; font-size: 24px; line-height: 1.35; letter-spacing: 0; overflow-wrap: anywhere; -webkit-text-stroke: 0; }
.profile-identity { margin: 0; font-size: 12px; color: var(--muted); }.profile-bio { margin: 9px 0 0; font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
.edit-profile { position: absolute; right: -3px; top: 1px; display: grid; place-items: center; width: 44px; height: 44px; padding: 11px; border: 0; background: transparent; }.edit-profile .more-icon { width: 21px; height: 21px; }
.interest-card { padding: 12px 15px 13px; margin-bottom: 13px; background: transparent; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 4px; }h2 { font-size: 16px; font-weight: 400; }.section-heading h2 { margin: 0; }.section-heading button { display: flex; align-items: center; gap: 2px; min-height: 36px; padding: 7px 0 7px 10px; background: transparent; border: 0; font-size: 12px; color: var(--muted); }.section-heading .more-icon { width: 14px; height: 14px; }
.interest-tags { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 7px 9px; }.interest-tag { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 35px; padding: 7px; font-size: 12px; background: transparent; }.interest-tag .ob-icon { width: 17px; height: 17px; }.card-footnote { margin: 10px 2px 0; font-size: 11px; color: var(--muted); }.empty-interests { margin: 12px 0; font-size: 13px; line-height: 1.7; color: var(--muted); }
.favorites-entry { display: flex; align-items: center; gap: 11px; width: 100%; min-height: 78px; padding: 14px 17px; margin: 0 0 16px; background: transparent; text-align: left; }.favorites-entry>span { min-width: 0; flex: 1; }.favorites-entry strong,.menu-copy strong { display: block; font-size: 15px; font-weight: 400; }.favorites-entry small { display: block; margin-top: 6px; font-size: 11px; line-height: 1.6; }.row-chevron { margin-left: auto; width: 17px; height: 17px; flex: none; color: var(--muted); }
.settings-menu { padding: 0 4px; }.menu-row { position: relative; display: flex; align-items: center; gap: 11px; width: 100%; min-height: 65px; padding: 10px 6px; background: transparent; border: 0; text-align: left; }.menu-icon { display: grid; place-items: center; width: 39px; height: 39px; flex: none; }.menu-icon .more-icon { width: 23px; height: 23px; }.menu-copy { flex: 1; min-width: 0; }.menu-copy small { display: block; margin-top: 5px; font-size: 11px; color: var(--muted); line-height: 1.4; }.row-divider { position: absolute; bottom: -1px; left: 51px; width: calc(100% - 51px); height: 5px; fill: none; stroke: var(--ink); stroke-opacity: .22; stroke-width: .9; stroke-linecap: round; }.menu-row:last-child .row-divider { display: none; }
.home-note { margin: 24px 0 5px; text-align: center; font-size: 12px; line-height: 1.7; color: var(--muted); }.home-note span { display: block; margin-top: 5px; font-size: 10px; }
.pane-heading { display: flex; align-items: center; gap: 7px; margin: 0 0 18px; min-height: 44px; }.pane-heading .back-button { display: grid; place-items: center; width: 42px; height: 44px; margin-left: -6px; padding: 9px; background: transparent; border: 0; }.pane-heading h1 { font-size: 23px; font-weight: 400; -webkit-text-stroke: 0; }.pane-lede { margin: 3px 2px 23px; color: var(--muted); font-size: 14px; line-height: 1.9; }
.form-field { display: block; margin: 0 0 18px; }.form-field>span { display: block; margin: 0 4px 7px; font-size: 13px; }.field-outline { padding: 10px 13px; background: transparent; }.field-outline input,.field-outline select,.field-outline textarea { display: block; width: 100%; min-height: 28px; padding: 3px 0; margin: 0; font: inherit; font-size: 16px; line-height: 1.7; border: 0; color: var(--ink); background: transparent; outline: none; }.field-outline select { padding-right: 4px; }.field-outline textarea { resize: vertical; max-height: 180px; }.field-outline:focus-within { outline: 2px solid #456e9977; outline-offset: -2px; border-radius: 14px; }.field-outline input::placeholder,.field-outline textarea::placeholder { color: var(--muted); }.form-two-columns { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
.avatar-options { display: flex; justify-content: space-around; gap: 8px; margin: 3px 0 25px; }.avatar-options button { position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 4px; background: transparent; border: 0; font-size: 12px; }.avatar-options .more-icon { position: absolute; right: 0; top: 58px; width: 23px; height: 23px; stroke-width: 2.5; }.avatar-options :deep(.profile-avatar) { width: 74px; height: 74px; }.avatar-options :deep(.profile-avatar .avatar-art) { width: 65px; height: 65px; }
.primary-button,.secondary-button { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 52px; width: 100%; padding: 12px; margin-top: 23px; font-size: 16px; background: transparent; }.primary-button .more-icon,.secondary-button .more-icon { width: 20px; height: 20px; }.primary-button:disabled,button:disabled { opacity: .5; cursor: default; }
.switch-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 81px; padding: 13px 3px; border-bottom: 1px solid #20304b16; }.switch-row>span { min-width: 0; flex: 1; }.switch-row strong { display: block; font-size: 14px; line-height: 1.6; font-weight: 400; }.switch-row small { display: block; margin-top: 6px; font-size: 12px; line-height: 1.7; color: var(--muted); }.field-heading { margin: 16px 3px 9px; font-size: 15px; }.spaced-heading { margin-top: 29px; }.time-choices { display: flex; gap: 8px; margin-top: 14px; }.time-choices button { flex: 1; padding: 12px 5px; min-height: 44px; background: transparent; font-size: 13px; }.small-note { margin: 12px 4px; color: var(--muted); font-size: 12px; line-height: 1.9; }.preview-note { margin: 22px 4px; font-size: 11px; line-height: 1.8; color: var(--muted); }
.account-info { margin: 4px 3px; font-size: 14px; }.account-info>div { display: flex; gap: 15px; justify-content: space-between; padding: 17px 0; border-bottom: 1px solid #20304b16; }.account-info dt { color: var(--muted); font-size: 13px; }.account-info dd { margin: 0; overflow-wrap: anywhere; text-align: right; }.plain-setting { display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 17px 3px; border: 0; border-bottom: 1px solid #20304b16; background: transparent; font-size: 14px; text-align: left; }.plain-setting>span:last-child { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--muted); }.plain-setting small { display: block; margin-top: 7px; color: var(--muted); font-size: 11px; }.plain-setting .more-icon { width: 15px; height: 15px; }
.style-preview { padding: 22px 20px; background: transparent; }.style-preview h2 { margin: 20px 0 9px; font-size: 20px; }.style-preview p { margin: 0; font-size: 12px; line-height: 1.8; }.current-style { display: inline-flex; align-items: center; gap: 5px; margin-top: 14px; font-size: 12px; }.current-style .more-icon { width: 16px; height: 16px; }.mini-ui { width: 118px; margin: 0 auto; padding: 12px 9px 7px; background: transparent; }.mini-header { height: 23px; }.mini-tags { display: flex; gap: 4px; margin: 10px 0; }.mini-tags i { display: block; flex: 1; height: 32px; }.mini-nav { height: 20px; }.future-style { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 82px; margin-top: 16px; padding: 17px; text-align: left; background: transparent; }.future-style span { font-size: 14px; }.future-style small { display: block; font-size: 11px; margin-top: 8px; }
.help-question { padding: 17px 4px; border-bottom: 1px solid #20304b22; font-size: 14px; }.help-question summary { cursor: pointer; line-height: 1.7; }.help-question p { margin: 12px 0 0; font-size: 13px; color: var(--muted); line-height: 1.9; }.help-links { display: flex; gap: 9px; margin-top: 18px; }.help-links button { flex: 1; padding: 12px 8px; background: transparent; font-size: 13px; min-height: 46px; }
.more-notice { position: absolute; z-index: 75; bottom: calc(105px + env(safe-area-inset-bottom,0px)); left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100% - 40px); margin: 0; padding: 13px 18px; font-size: 13px; text-align: center; background: transparent; backdrop-filter: blur(10px); }.more-toast-enter-active,.more-toast-leave-active { transition: opacity .2s ease; }.more-toast-enter-from,.more-toast-leave-to { opacity: 0; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
@media(max-width:359px) { .profile-header { gap: 10px; padding-inline: 0; }.profile-header :deep(.profile-avatar) { width: 69px; height: 73px; }.profile-header :deep(.profile-avatar .avatar-art) { width: 64px; height: 64px; }.profile-copy h1 { font-size: 21px; }.profile-bio { font-size: 11px; }.interest-card { padding-inline: 12px; }.interest-tag { gap: 5px; font-size: 11px; }.favorites-entry { padding-inline: 14px; gap: 9px; }.favorites-entry small { font-size: 10px; }.avatar-options { gap: 4px; }.avatar-options :deep(.profile-avatar) { width: 66px; height: 68px; }.avatar-options :deep(.profile-avatar .avatar-art) { width: 60px; height: 60px; } }
@media(prefers-reduced-motion:reduce) { .more-toast-enter-active,.more-toast-leave-active { transition: none; } }
</style>
