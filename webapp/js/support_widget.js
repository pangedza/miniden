(function () {
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
    const bodyContainer = panel.querySelector('.support-widget-body');
    const input = panel.querySelector('.support-widget-input');
    const sendBtn = panel.querySelector('.support-widget-send-btn');

    body.appendChild(fab);
    body.appendChild(panel);

    let initialized = false;

    const ensureGreeting = () => {
      if (initialized || !bodyContainer) return;
      const greeting = document.createElement('div');
      greeting.className = 'support-widget-msg support-widget-msg--manager';
      greeting.textContent =
        'Здравствуйте! Я тестовый помощник. Если вы меня видите, значит виджет подключен правильно.';
      bodyContainer.appendChild(greeting);
      initialized = true;
    };

    const togglePanel = () => {
      const isOpen = panel.classList.toggle('support-widget-panel--open');
      if (isOpen) {
        console.log('Support widget: panel opened');
        ensureGreeting();
      }
    };

    const appendUserMessage = (text) => {
      if (!bodyContainer) return;
      const msg = document.createElement('div');
      msg.className = 'support-widget-msg support-widget-msg--user';
      msg.textContent = text;
      bodyContainer.appendChild(msg);
      bodyContainer.scrollTop = bodyContainer.scrollHeight;
    };

    const handleSend = () => {
      const value = (input?.value || '').trim();
      if (!value) return;

      console.log('Support widget: sending message', value);
      appendUserMessage(value);
      if (input) {
        input.value = '';
      }
      // TODO: отправить сообщение в /api/webchat/message
    };

    fab.addEventListener('click', togglePanel);
    closeBtn?.addEventListener('click', () => {
      panel.classList.remove('support-widget-panel--open');
    });
    sendBtn?.addEventListener('click', handleSend);
    input?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        handleSend();
      }
    });
  };

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', initWidget);
  } else {
    initWidget();
  }
})();
