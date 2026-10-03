// 页面元数据是后续扩展的唯一入口；此阶段不实现业务内容。
const pages = {
  system: { id: 'D-00', title: '设计规范', placeholder: '设计规范 & 组件库', label: 'DESIGN SYSTEM', eyebrow: 'A LITTLE DESIGN LANGUAGE', icon: 'pencil', accent: 'lavender' },
  onboarding: { id: 'D-01', title: '初次见面', placeholder: '授权、兴趣引导页', label: 'WELCOME', eyebrow: 'HELLO, CAMPUS LIFE', icon: 'spark', accent: 'pink' },
  map: { id: 'D-02', title: '活动地图', placeholder: '地图主页', label: 'MAP', eyebrow: 'EXPLORE THE CAMPUS', icon: 'map', accent: 'blue', nav: 'map' },
  detail: { id: 'D-03', title: '活动详情', placeholder: '信息详情页', label: 'DETAIL', eyebrow: 'A CLOSER LOOK', icon: 'pencil', accent: 'mint', nav: 'map' },
  calendar: { id: 'D-04', title: '活动日历', placeholder: '日历 / 活动列表页', label: 'CALENDAR', eyebrow: 'MAKE ROOM FOR GOOD DAYS', icon: 'calendar', accent: 'mint', nav: 'calendar' },
  interests: { id: 'D-05', title: '兴趣广场', placeholder: '兴趣推荐列表页', label: 'INTERESTS', eyebrow: 'FOLLOW YOUR CURIOSITY', icon: 'star', accent: 'pink', nav: 'interests' },
  agent: { id: 'D-06', title: '智能助手', placeholder: 'Agent 对话页', label: 'AGENT', eyebrow: 'A LITTLE HELP, A LOT OF IDEAS', icon: 'agent', accent: 'lavender', nav: 'agent' },
  more: { id: 'D-07', title: '我的', placeholder: '其他功能页', label: 'MORE', eyebrow: 'YOUR CORNER OF CAMPUS', icon: 'user', accent: 'yellow', nav: 'more' },
};

const directory = document.querySelector('#page-directory');
const directoryLinks = document.querySelector('#directory-links');
const main = document.querySelector('#main-content');
const pageTitle = document.querySelector('#page-title');
const outlet = document.querySelector('#page-outlet');
const backButton = document.querySelector('#back-button');
let currentRoute = null;
// 为本原型的历史记录标记序号，首次直接打开详情页也能安全回到地图。
let historyIndex = history.state?.livelifeDesignIndex ?? 0;
let toastTimer;

Object.entries(pages).forEach(([route, page]) => {
  const link = document.createElement('a');
  link.className = 'directory-link';
  link.href = `#/${route}`;
  link.dataset.route = route;
  // 元数据均为本地静态字符串。
  link.innerHTML = `<span class="route-code">${page.id}</span><span>${page.placeholder}</span><svg class="icon" aria-hidden="true"><use href="#icon-chevron"/></svg>`;
  link.addEventListener('click', () => {
    directory.close();
    if (route === currentRoute) pageTitle.focus({ preventScroll: true });
  });
  directoryLinks.append(link);
});

function renderPage() {
  const requested = location.hash.replace(/^#\/?/, '');
  const route = Object.hasOwn(pages, requested) ? requested : 'map';
  if (requested !== route) {
    // 未知链接和首次打开都归一到默认地图页，不添加多余历史记录。
    history.replaceState(history.state, '', `${location.pathname}${location.search}#/${route}`);
  }
  const page = pages[route];
  const isNavigation = currentRoute !== null && currentRoute !== route;
  if (history.state?.livelifeDesignIndex === undefined) {
    if (isNavigation) historyIndex += 1;
    history.replaceState({ livelifeDesignIndex: historyIndex }, '', location.href);
  } else {
    historyIndex = history.state.livelifeDesignIndex;
  }
  currentRoute = route;
  document.title = `${page.title} · PKU LiveLife`;
  pageTitle.textContent = page.title;
  document.querySelector('#page-eyebrow').textContent = page.eyebrow;
  document.querySelector('#page-code').textContent = `${page.id} / ${page.label}`;
  document.querySelector('#placeholder-title').textContent = page.placeholder;
  document.querySelector('#placeholder-icon').setAttribute('href', `#icon-${page.icon}`);
  outlet.style.setProperty('--page-accent', `var(--${page.accent})`);
  document.querySelector('.art-paper').dataset.pencil = page.accent;
  outlet.dataset.page = route;
  backButton.hidden = !['system', 'onboarding', 'detail'].includes(route);
  document.querySelectorAll('[data-nav]').forEach(link => {
    if (link.dataset.nav === page.nav) {
      link.setAttribute('aria-current', 'page');
      link.dataset.pencil = 'blue';
    } else {
      link.removeAttribute('aria-current');
      delete link.dataset.pencil;
    }
  });
  document.querySelectorAll('[data-route]').forEach(link => {
    if (link.dataset.route === route) {
      link.setAttribute('aria-current', 'page');
      link.dataset.pencil = 'blue';
    } else {
      link.removeAttribute('aria-current');
      delete link.dataset.pencil;
    }
  });
  window.HandDrawn.refresh();
  main.scrollTop = 0;
  if (isNavigation) pageTitle.focus({ preventScroll: true });
}

document.querySelector('#directory-button').addEventListener('click', () => directory.showModal());
document.querySelector('#close-directory').addEventListener('click', () => directory.close());
directory.addEventListener('click', event => {
  const bounds = directory.getBoundingClientRect();
  if (event.target === directory && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) directory.close();
});
backButton.addEventListener('click', () => {
  if (historyIndex > 0) history.back();
  else location.hash = '/map';
});
document.querySelector('[data-notification]').addEventListener('click', () => {
  const toast = document.querySelector('#toast');
  clearTimeout(toastTimer);
  toast.textContent = '消息通知区域待设计';
  toast.hidden = false;
  window.HandDrawn.refresh();
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2600);
});
window.addEventListener('hashchange', renderPage);
renderPage();
