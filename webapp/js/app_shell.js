(function () {
  const adminLink = document.getElementById('admin-link');
  const loginSection = document.getElementById('telegram-login-section');
  const authStatus = document.getElementById('auth-status');
  const authUsername = document.getElementById('auth-username');
  const switchUserBtn = document.getElementById('switch-user-btn');
  const loginButton = document.getElementById('btn-login-telegram');
  const loginButtonDefaultText = loginButton?.textContent || 'Войти через Telegram';

  const setAdminVisibility = (profile) => {
    if (!adminLink) return;
    adminLink.style.display = profile?.is_admin ? '' : 'none';
  };

  const renderAuthState = (profile) => {
    if (profile) {
      loginSection?.style.setProperty('display', 'none');
      authStatus?.style.setProperty('display', 'block');
      const displayName = profile.full_name || (profile.telegram_username ? '@' + profile.telegram_username : profile.telegram_id);
      if (authUsername && displayName) {
        authUsername.textContent = `Вы вошли как ${displayName}`;
      }
    } else {
      loginSection?.style.setProperty('display', 'block');
      authStatus?.style.setProperty('display', 'none');
      if (loginButton) {
        loginButton.style.setProperty('display', 'inline-flex');
        loginButton.textContent = isTelegramWebApp ? 'Повторить авторизацию' : loginButtonDefaultText;
      }
    }
  };

  const logout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {
      console.warn('Failed to call logout', e);
    } finally {
      window.location.reload();
    }
  };

  const loadSession = async () => {
    try {
      const user = await getCurrentUserProfile();
      setAdminVisibility(user);
      renderAuthState(user);
    } catch (e) {
      console.error('Failed to load auth status', e);
      setAdminVisibility(null);
      renderAuthState(null);
    }
  };

  const initAuthShell = async () => {
    switchUserBtn?.addEventListener('click', logout);

    loginButton?.addEventListener('click', async () => {
      if (isTelegramWebApp) {
        loginButton.disabled = true;
        try {
          await loadSession();
        } finally {
          loginButton.disabled = false;
        }
        return;
      }

      startTelegramOAuthFlow();
    });

    await processTelegramAuthFromUrl().catch((error) => {
      console.error('Telegram auth via browser failed', error);
      showToast(error?.message || 'Не удалось авторизоваться через Telegram');
    });

    await loadSession();
  };

  document.addEventListener('DOMContentLoaded', () => {
    initAuthShell();
  });
})();
