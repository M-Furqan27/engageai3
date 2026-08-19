const EngageAI = (() => {
  const API = localStorage.getItem('apiBase') || 'https://engageai-backend-zhki.onrender.com';
  const SESSION_KEYS = ['access_token', 'token_type', 'user_id', 'organization_id', 'onboarding_completed'];
  const THEME_KEY = 'engageai_theme';

  const escapeHtml = (value = '') => String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  function getTheme() {
    return localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light';
  }

  function updateThemeControls(theme) {
    const dark = theme === 'dark';
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-pressed', dark ? 'true' : 'false');
      button.setAttribute('title', dark ? 'Switch to Light mode' : 'Switch to Black mode');
      button.setAttribute('aria-label', dark ? 'Switch to Light mode' : 'Switch to Black mode');
      const icon = button.querySelector('[data-theme-icon]');
      const label = button.querySelector('[data-theme-label]');
      if (icon) icon.className = `bi ${dark ? 'bi-sun-fill' : 'bi-moon-stars-fill'}`;
      if (label) label.textContent = dark ? 'Light' : 'Black';
    });
  }

  function applyTheme(theme = getTheme()) {
    const safeTheme = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', safeTheme);
    updateThemeControls(safeTheme);
    return safeTheme;
  }

  function setTheme(theme) {
    const safeTheme = theme === 'dark' ? 'dark' : 'light';
    localStorage.setItem(THEME_KEY, safeTheme);
    applyTheme(safeTheme);
    document.dispatchEvent(new CustomEvent('engageai:themechange', { detail: { theme: safeTheme } }));
  }

  function toggleTheme() {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
  }

  function renderAuthThemeSwitcher() {
    const host = document.querySelector('.auth-form-side');
    if (!host || host.querySelector('.auth-theme-toggle')) return;
    const controls = document.createElement('div');
    controls.className = 'auth-theme-toggle';
    controls.innerHTML = `
      <button class="theme-toggle-button" type="button" data-theme-toggle aria-pressed="false">
        <span class="theme-toggle-track"><span class="theme-toggle-knob"><i data-theme-icon class="bi bi-moon-stars-fill"></i></span></span>
        <span data-theme-label>Black</span>
      </button>`;
    controls.querySelector('[data-theme-toggle]').addEventListener('click', toggleTheme);
    host.appendChild(controls);
    updateThemeControls(getTheme());
  }

  async function request(path, options = {}) {
    const isForm = options.body instanceof FormData;
    const headers = { ...(options.headers || {}) };
    if (!isForm && options.body != null && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const token = localStorage.getItem('access_token');
    if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`;

    let response;
    try {
      response = await fetch(API + path, { ...options, headers });
    } catch (error) {
      throw new Error('Unable to reach the server. Please check that the backend is running.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || 'Request failed.');
    return data;
  }

  function ensureToastHost() {
    if (document.getElementById('toastHost')) return;
    const host = document.createElement('div');
    host.id = 'toastHost';
    host.className = 'engage-toast-host';
    document.body.appendChild(host);
  }

  function toast(message, type = 'success', title = '') {
    ensureToastHost();
    const icons = {
      success: 'bi-check-circle-fill',
      danger: 'bi-exclamation-octagon-fill',
      warning: 'bi-exclamation-triangle-fill',
      info: 'bi-info-circle-fill',
    };
    const defaultTitles = { success: 'Success', danger: 'Something went wrong', warning: 'Attention', info: 'Update' };
    const item = document.createElement('div');
    item.className = `engage-toast toast-${type}`;
    item.innerHTML = `
      <div class="engage-toast-icon"><i class="bi ${icons[type] || icons.info}"></i></div>
      <div class="engage-toast-copy">
        <strong>${escapeHtml(title || defaultTitles[type] || 'Update')}</strong>
        <span>${escapeHtml(message)}</span>
      </div>
      <button class="engage-toast-close" type="button" aria-label="Close"><i class="bi bi-x-lg"></i></button>`;
    item.querySelector('.engage-toast-close').addEventListener('click', () => item.remove());
    document.getElementById('toastHost').appendChild(item);
    requestAnimationFrame(() => item.classList.add('show'));
    setTimeout(() => {
      item.classList.remove('show');
      setTimeout(() => item.remove(), 260);
    }, 4500);
  }

  function flash(message, type = 'success') {
    sessionStorage.setItem('engageai_flash', JSON.stringify({ message, type }));
  }

  function consumeFlash() {
    const raw = sessionStorage.getItem('engageai_flash');
    if (!raw) return;
    sessionStorage.removeItem('engageai_flash');
    try {
      const data = JSON.parse(raw);
      toast(data.message, data.type || 'success');
    } catch (_) { /* no-op */ }
  }

  function confirmAction({ title = 'Confirm action', message = 'Are you sure?', confirmText = 'Confirm', danger = false } = {}) {
    return new Promise(resolve => {
      let modalEl = document.getElementById('engageConfirmModal');
      if (!modalEl) {
        modalEl = document.createElement('div');
        modalEl.id = 'engageConfirmModal';
        modalEl.className = 'modal fade';
        modalEl.tabIndex = -1;
        modalEl.innerHTML = `
          <div class="modal-dialog modal-dialog-centered modal-sm">
            <div class="modal-content app-modal">
              <div class="modal-header border-0 pb-0">
                <h5 class="modal-title"></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body pt-2"><p class="mb-0 text-secondary confirm-copy"></p></div>
              <div class="modal-footer border-0 pt-0">
                <button type="button" class="btn btn-soft" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn confirm-button"></button>
              </div>
            </div>
          </div>`;
        document.body.appendChild(modalEl);
      }
      modalEl.querySelector('.modal-title').textContent = title;
      modalEl.querySelector('.confirm-copy').textContent = message;
      const button = modalEl.querySelector('.confirm-button');
      button.textContent = confirmText;
      button.className = `btn confirm-button ${danger ? 'btn-danger' : 'btn-primary'}`;
      const instance = bootstrap.Modal.getOrCreateInstance(modalEl);
      let settled = false;
      const finish = value => {
        if (settled) return;
        settled = true;
        resolve(value);
      };
      button.onclick = () => { finish(true); instance.hide(); };
      modalEl.addEventListener('hidden.bs.modal', () => finish(false), { once: true });
      instance.show();
    });
  }

  function pageName() {
    const file = location.pathname.split('/').pop() || '';
    return file.replace('.html', '') || 'dashboard';
  }

  function renderHeader({ onboarding = false } = {}) {
    const mount = document.getElementById('appHeader');
    if (!mount) return;
    const active = pageName();

    const workspaceMenu = onboarding ? `
      <div class="onboarding-lock-note d-none d-md-flex">
        <i class="bi bi-lock-fill"></i>
        <span>Complete onboarding to unlock your workspace</span>
      </div>` : `
      <div class="dropdown">
        <button class="header-action workspace-menu-button dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
          <i class="bi bi-grid-fill"></i><span>Workspace</span>
        </button>
        <div class="dropdown-menu dropdown-menu-end workspace-dropdown shadow-lg">
          <div class="workspace-dropdown-title">Workspace</div>
          <a class="dropdown-item ${active === 'dashboard' ? 'active' : ''}" href="dashboard.html"><i class="bi bi-speedometer2"></i><span><strong>Dashboard</strong><small>Overview and activity</small></span></a>
          <a class="dropdown-item ${active === 'profile' ? 'active' : ''}" href="profile.html"><i class="bi bi-building-gear"></i><span><strong>Business Profile</strong><small>Services, policies and knowledge</small></span></a>
          <a class="dropdown-item ${active === 'conversations' ? 'active' : ''}" href="conversations.html"><i class="bi bi-chat-square-text"></i><span><strong>Conversations</strong><small>Visitor history and sessions</small></span></a>
        </div>
      </div>`;

    mount.innerHTML = `
      <div class="app-header-inner">
        <a class="header-brand" href="${onboarding ? 'onboarding.html' : 'dashboard.html'}" aria-label="EngageAI home">
          <span class="brand-mark"><i class="bi bi-stars"></i></span>
          <span class="header-brand-copy"><strong>EngageAI</strong><small>${onboarding ? 'Business Onboarding' : 'Business Portal'}</small></span>
        </a>
        <div class="header-actions">
          ${workspaceMenu}
          <button class="theme-toggle-button header-theme-toggle" type="button" data-theme-toggle aria-pressed="false" onclick="EngageAI.toggleTheme()">
            <span class="theme-toggle-track"><span class="theme-toggle-knob"><i data-theme-icon class="bi bi-moon-stars-fill"></i></span></span>
            <span data-theme-label>Black</span>
          </button>
          <button class="header-action logout-header-button" type="button" onclick="EngageAI.logout()" title="Log out">
            <i class="bi bi-box-arrow-right"></i><span class="d-none d-sm-inline">Log out</span>
          </button>
        </div>
      </div>`;
    applyTheme();
  }

  // Backward-compatible alias for page scripts created before the top-header layout.
  function renderSidebar(options = {}) { renderHeader(options); }

  function requireAuth({ allowIncomplete = false } = {}) {
    if (!localStorage.getItem('user_id')) {
      flash('Please log in to continue.', 'info');
      location.href = 'login.html';
      return false;
    }
    if (!allowIncomplete && localStorage.getItem('onboarding_completed') !== 'true') {
      location.href = 'onboarding.html';
      return false;
    }
    return true;
  }

  async function logout() {
    try { await request('/auth/logout', { method: 'POST' }); } catch (_) { /* local logout still proceeds */ }
    SESSION_KEYS.forEach(key => localStorage.removeItem(key));
    flash('You have been logged out safely. Your saved onboarding data and local drafts are preserved.', 'info');
    location.href = 'login.html';
  }

  function setBusy(button, busy, busyText = 'Working...') {
    if (!button) return;
    if (busy) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>${escapeHtml(busyText)}`;
    } else {
      button.disabled = false;
      if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
    }
  }

  function draftKey(name) {
    return `engageai_draft_${name}_${localStorage.getItem('user_id') || 'guest'}`;
  }

  function saveFormDraft(form, name) {
    if (!form) return;
    const values = {};
    new FormData(form).forEach((value, key) => {
      if (!(value instanceof File)) values[key] = value;
    });
    localStorage.setItem(draftKey(name), JSON.stringify(values));
  }

  function restoreFormDraft(form, name) {
    if (!form) return;
    const raw = localStorage.getItem(draftKey(name));
    if (!raw) return;
    try {
      const values = JSON.parse(raw);
      Object.entries(values).forEach(([key, value]) => {
        const field = form.elements[key];
        if (field && field.type !== 'file') field.value = value ?? '';
      });
    } catch (_) { /* no-op */ }
  }

  function clearFormDraft(name) { localStorage.removeItem(draftKey(name)); }

  function bindDraft(form, name) {
    if (!form) return;
    restoreFormDraft(form, name);
    form.addEventListener('input', () => saveFormDraft(form, name));
    form.addEventListener('change', () => saveFormDraft(form, name));
  }

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme();
    renderAuthThemeSwitcher();
    consumeFlash();
  });

  return {
    API,
    request,
    toast,
    flash,
    confirmAction,
    renderSidebar,
    renderHeader,
    requireAuth,
    logout,
    applyTheme,
    setTheme,
    toggleTheme,
    setBusy,
    escapeHtml,
    bindDraft,
    saveFormDraft,
    restoreFormDraft,
    clearFormDraft,
    draftKey,
  };
})();
