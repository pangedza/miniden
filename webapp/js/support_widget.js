(function () {
  const WEBCHAT_API_BASE = '/api/webchat';
  const WEBCHAT_STORAGE_KEY = 'support_widget_session_key';
  const WEBCHAT_POLL_INTERVAL = 4000; // мс

  let sessionKey = null;
  let isSessionInitialized = false;
  let pollTimer = null;
  let isPolling = false;

  console.log('Support widget script loaded');

  const initWidget = () => {
    const body = document.body;
    if (!body) {
      console.warn('Support widget: document.body is missing');
      return;
    }

    if (body.querySelector('.support-widget-fab')) {
      console.log('Support widget: already initialized');
      return;
    }

    console.log('Support widget: creating FAB');
    const fab = document.createElement('div');
    fab.className = 'support-widget-fab';
    fab.title = 'Помощник';
    fab.textContent = '?';

    const panel = document.createElement('div');
    panel.className = 'support-widget-panel';
    panel.innerHTML = `
      <div class="support-widget-header">
        <span>Помощник MiniDeN</span>
        <button class="support-widget-close-btn" type="button">×</button>
      </div>
      <div class="support-widget-body"></div>
      <div class="support-widget-footer">
        <input class="support-widget-input" type="text" placeholder="Напишите вопрос..." />
        <button class="support-widget-send-btn" type="button">▶</button>
      </div>
    `;

    const closeBtn = panel.querySelector('.support-widget-close-btn');
    const bodyEl = panel.querySelector('.support-widget-body');
    const inputEl = panel.querySelector('.support-widget-input');
    const sendBtnEl = panel.querySelector('.support-widget-send-btn');

    body.appendChild(fab);
    body.appendChild(panel);

    const faqButtons = bodyEl ? bodyEl.querySelectorAll('button') : [];

    function initSessionKey() {
      if (sessionKey) return;
      const fromStorage = window.localStorage ? window.localStorage.getItem(WEBCHAT_STORAGE_KEY) : null;
      if (fromStorage) {
        sessionKey = fromStorage;
      } else {
        sessionKey = 'wcs_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2);
        try {
          window.localStorage && window.localStorage.setItem(WEBCHAT_STORAGE_KEY, sessionKey);
        } catch (e) {
          console.warn('Cannot access localStorage for webchat session', e);
        }
      }
    }

    async function ensureWebchatSessionStarted() {
      if (isSessionInitialized) return;
      initSessionKey();
      try {
        const resp = await fetch(WEBCHAT_API_BASE + '/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_key: sessionKey,
            page: window.location.pathname || null
          })
        });
        if (!resp.ok) {
          console.error('Failed to start webchat session', resp.status);
          return;
        }
        const data = await resp.json().catch(() => ({}));
        console.log('Webchat session started', data);
        isSessionInitialized = true;
      } catch (err) {
        console.error('Error starting webchat session', err);
      }
    }

    function appendMessageToUI(sender, text) {
      if (!bodyEl) return;
      const msg = document.createElement('div');
      msg.classList.add('support-widget-msg', 'msg');

      if (sender === 'user') {
        msg.classList.add('support-widget-msg--user', 'user');
      } else {
        msg.classList.add('support-widget-msg--manager', 'manager');
      }

      msg.textContent = text;
      bodyEl.appendChild(msg);
      bodyEl.scrollTop = bodyEl.scrollHeight;
    }

    async function sendUserMessage() {
      if (!inputEl) return;
      const text = inputEl.value.trim();
      if (!text) return;

      appendMessageToUI('user', text);
      inputEl.value = '';

      await ensureWebchatSessionStarted();

      try {
        const resp = await fetch(WEBCHAT_API_BASE + '/message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_key: sessionKey,
            text: text
          })
        });
        if (!resp.ok) {
          console.error('Failed to send webchat message', resp.status);
          appendMessageToUI('system', 'Не удалось отправить сообщение. Попробуйте ещё раз.');
        }
      } catch (err) {
        console.error('Error sending webchat message', err);
        appendMessageToUI('system', 'Ошибка соединения с сервером.');
      }
    }

    async function fetchMessagesFromServer() {
      if (!sessionKey) {
        initSessionKey();
      }
      try {
        const url = WEBCHAT_API_BASE + '/messages?session_key=' + encodeURIComponent(sessionKey);
        const resp = await fetch(url, { method: 'GET' });
        if (!resp.ok) {
          console.error('Failed to fetch webchat messages', resp.status);
          return;
        }
        const data = await resp.json().catch(() => null);
        if (!data || !Array.isArray(data.messages)) {
          return;
        }
        renderMessages(data.messages);
      } catch (err) {
        console.error('Error fetching webchat messages', err);
      }
    }

    function renderMessages(messages) {
      if (!bodyEl) return;
      bodyEl.innerHTML = '';
      messages.forEach(function (m) {
        const sender = m && m.sender ? m.sender : 'manager';
        appendMessageToUI(sender, m && m.text ? m.text : '');
      });
    }

    function startPollingMessages() {
      if (isPolling) return;
      isPolling = true;
      fetchMessagesFromServer();
      pollTimer = window.setInterval(fetchMessagesFromServer, WEBCHAT_POLL_INTERVAL);
    }

    function stopPollingMessages() {
      if (!isPolling) return;
      isPolling = false;
      if (pollTimer) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    const togglePanel = () => {
      const isOpen = panel.classList.toggle('support-widget-panel--open');
      if (isOpen) {
        console.log('Support widget: panel opened');
        ensureWebchatSessionStarted();
        startPollingMessages();
      }
    };

    fab.addEventListener('click', togglePanel);
    closeBtn?.addEventListener('click', () => {
      panel.classList.remove('support-widget-panel--open');
      stopPollingMessages();
    });
    if (sendBtnEl) {
      sendBtnEl.addEventListener('click', function () {
        sendUserMessage();
      });
    }
    if (inputEl) {
      inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendUserMessage();
        }
      });
    }

    faqButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (inputEl) {
          inputEl.value = this.textContent.trim();
        }
        sendUserMessage();
      });
    });
  };

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', initWidget);
  } else {
    initWidget();
  }
})();
