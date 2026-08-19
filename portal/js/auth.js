document.addEventListener('DOMContentLoaded', () => {
  EngageAI.applyTheme();
});

async function signup(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('signupBtn');
  const payload = Object.fromEntries(new FormData(form));
  if (payload.password !== payload.confirm_password) {
    EngageAI.toast('Password and confirm password must match.', 'warning');
    return;
  }
  EngageAI.setBusy(button, true, 'Creating account...');
  try {
    const data = await EngageAI.request('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    EngageAI.flash(data.message || 'Account created successfully. Please log in.', 'success');
    location.href = 'login.html';
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  } finally {
    EngageAI.setBusy(button, false);
  }
}

async function login(event) {
  event.preventDefault();
  const button = document.getElementById('loginBtn');
  const payload = Object.fromEntries(new FormData(event.currentTarget));
  EngageAI.setBusy(button, true, 'Signing in...');
  try {
    const data = await EngageAI.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    localStorage.setItem('access_token', data.access_token || '');
    localStorage.setItem('token_type', data.token_type || 'bearer');
    localStorage.setItem('user_id', data.user_id || '');
    if (data.organization_id) localStorage.setItem('organization_id', data.organization_id);
    else localStorage.removeItem('organization_id');
    localStorage.setItem('onboarding_completed', String(Boolean(data.onboarding_completed)));
    EngageAI.flash(data.onboarding_completed ? 'Welcome back to your workspace.' : 'Welcome back. Continue your onboarding from where you left off.', 'success');
    location.href = data.onboarding_completed ? 'dashboard.html' : 'onboarding.html';
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  } finally {
    EngageAI.setBusy(button, false);
  }
}
