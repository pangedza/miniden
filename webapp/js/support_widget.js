(function () {
  'use strict';

  const body = document.body;
  if (!body || body.querySelector('.support-widget-fab')) {
    return;
  }

  function createMessageElement(text, role) {
    const msg = document.createElement('div');
    msg.className = `support-widget-msg support-widget-msg--${role}`;
    msg.textContent = text;
    return msg;
  }

  const fab = document.createElement('button');
  fab.className = 'support-widget-fab';
  fab.type = 'button';
  fab.setAttribute('aria-label', 'Открыть помощник MiniDeN');
  fab.textContent = '?';

  const panel = document.createElement('div');
  panel.className = 'support-widget-panel';

  const header = document.createElement('div');
  header.className = 'support-widget-header';

  const title = document.createElement('span');
  title.textContent = 'Помощник MiniDeN';

  const closeBtn = document.createElement('button');
  closeBtn.className = 'support-widget-close-btn';
  closeBtn.type = 'button';
  closeBtn.textContent = '×';

  header.appendChild(title);
  header.appendChild(closeBtn);

  const bodyContainer = document.createElement('div');
  bodyContainer.className = 'support-widget-body';

  const footer = document.createElement('div');
  footer.className = 'support-widget-footer';

  const input = document.createElement('input');
  input.className = 'support-widget-input';
  input.placeholder = 'Напишите вопрос...';

  const sendBtn = document.createElement('button');
  sendBtn.className = 'support-widget-send-btn';
  sendBtn.type = 'button';
  sendBtn.textContent = '▶';

  footer.appendChild(input);
  footer.appendChild(sendBtn);

  panel.appendChild(header);
  panel.appendChild(bodyContainer);
  panel.appendChild(footer);

  let greeted = false;

  function togglePanel(forceOpen) {
    const isOpen = panel.classList.contains('support-widget-panel--open');
    const nextState = typeof forceOpen === 'boolean' ? forceOpen : !isOpen;
    panel.classList.toggle('support-widget-panel--open', nextState);
    if (nextState && !greeted) {
      bodyContainer.appendChild(
        createMessageElement(
          'Здравствуйте! Здесь вы можете задать вопрос. Я скоро научусь писать менеджеру 🙂',
          'manager'
        )
      );
      greeted = true;
    }
  }

  function addUserMessage() {
    const value = input.value.trim();
    if (!value) {
      return;
    }
    bodyContainer.appendChild(createMessageElement(value, 'user'));
    bodyContainer.scrollTop = bodyContainer.scrollHeight;
    input.value = '';
    // TODO: отправить сообщение в /api/webchat, когда появится бэкенд
  }

  fab.addEventListener('click', () => togglePanel());
  closeBtn.addEventListener('click', () => togglePanel(false));
  sendBtn.addEventListener('click', addUserMessage);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addUserMessage();
    }
  });

  body.appendChild(fab);
  body.appendChild(panel);
})();
