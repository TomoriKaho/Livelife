// Run in an isolated Vite tab at each target viewport.
import router from '../src/router/index.ts';
import { nextTick } from 'vue';

export async function verifyAccountLayout() {
  const originalRoute = router.currentRoute.value.fullPath;
  const root = document.documentElement;
  const savedTop = root.style.getPropertyValue('--safe-area-inset-top');
  const savedBottom = root.style.getPropertyValue('--safe-area-inset-bottom');
  const results = [];
  const check = (ok, message) => { if (!ok) throw new Error(message); results.push(message); };
  const settled = async () => { await nextTick(); await new Promise(resolve => requestAnimationFrame(resolve)); };
  try {
    await router.push('/calendar');
    await router.push('/onboarding');
    await document.fonts.ready;
    for (const safe of [false, true]) {
      root.style.setProperty('--safe-area-inset-top', safe ? '24px' : '0px');
      root.style.setProperty('--safe-area-inset-bottom', safe ? '34px' : '0px');
      for (const mode of ['登录', '注册']) {
        [...document.querySelectorAll('.mode-tab')].find(button => button.textContent === mode).click();
        await settled();
        const body = document.querySelector('.onboarding-body');
        const button = document.querySelector('.enter');
        const fits = window.innerWidth >= 360 && window.innerHeight >= 640;
        if (fits) check(body.scrollHeight <= body.clientHeight + 1, mode + ': one screen, safe area=' + safe);
        body.scrollTop = body.scrollHeight;
        await settled();
        check(button.getBoundingClientRect().bottom <= body.getBoundingClientRect().bottom + 1, mode + ': submit reachable');
        check(body.scrollWidth <= body.clientWidth, mode + ': no horizontal scrolling');
      }
    }
    // Real form error; required inputs remain usable.
    for (const [selector, value] of [['#account-email', 'synthetic@stu.pku.edu.cn'], ['#account-code', '123456'], ['#account-password', 'synthetic-password'], ['#account-confirm', 'different-password']]) {
      const input = document.querySelector(selector);
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    document.querySelector('.account').requestSubmit();
    await settled();
    check(document.querySelector('[role="alert"]')?.textContent.includes('不一致'), 'password mismatch remains visible');
    // Simulate enlarged text without hiding overflow.
    for (const element of document.querySelectorAll('.account label, .account p, .account button, .account input')) {
      element.style.fontSize = parseFloat(getComputedStyle(element).fontSize) * 1.5 + 'px';
    }
    await settled();
    const body = document.querySelector('.onboarding-body');
    body.scrollTop = body.scrollHeight;
    await settled();
    check(document.querySelector('.enter').getBoundingClientRect().bottom <= body.getBoundingClientRect().bottom + 1, 'enlarged text and error: submit reachable');
    return results;
  } finally {
    root.style.setProperty('--safe-area-inset-top', savedTop);
    root.style.setProperty('--safe-area-inset-bottom', savedBottom);
    await router.push('/calendar');
    await router.push(originalRoute);
  }
}
