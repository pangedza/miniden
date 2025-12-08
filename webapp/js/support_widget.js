(function () {
  'use strict';

  const TELEGRAM_BOT_URL = 'https://t.me/YOUR_BOT_USERNAME?start=help_from_site'; // TODO: Замените на реальный username бота
  const SESSION_STORAGE_KEY = 'support_widget_session_key';
  const POLL_INTERVAL_MS = 4000;
  const CHAT_ERROR_MESSAGE = 'Сбой связи с сервером, попробуйте ещё раз.';
  const STATE = {
    faqs: [],
    faqsByCategory: new Map(),
    questionsCache: new Map(),
    loaded: false,
    loading: false,
    error: null,
    currentCategory: null,
    currentQuestionId: null,
    mode: 'faq',
    sessionKey: null,
    sessionId: null,
    chatStatus: 'open',
    chatMessages: [],
    chatTimer: null,
    chatError: null,
    chatElements: null,
  };

  const createElement = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) {
      el.className = className;
    }
    if (text) {
      el.textContent = text;
    }
    return el;
  };

  const body = document.body;
  if (!body) {
    return;
  }

  function renderChatMessages() {
    if (!STATE.chatElements || !STATE.chatElements.messages) {
      return;
    }

    const messagesWrap = STATE.chatElements.messages;
    messagesWrap.innerHTML = '';

    const statusEl = STATE.chatElements.status;
    if (statusEl) {
      if (STATE.chatStatus === 'waiting_manager') {
        statusEl.textContent = 'Менеджер ответит вам здесь, как только будет свободен.';
      } else if (STATE.chatStatus === 'closed') {
        statusEl.textContent = 'Чат закрыт.';
      } else {
        statusEl.textContent = 'Мы на связи. Менеджер ответит в этом окне.';
      }
    }

    if (STATE.chatError && STATE.chatElements.error) {
      STATE.chatElements.error.textContent = STATE.chatError;
      STATE.chatElements.error.style.display = '';
    } else if (STATE.chatElements.error) {
      STATE.chatElements.error.textContent = '';
      STATE.chatElements.error.style.display = 'none';
    }

    STATE.chatMessages.forEach((msg) => {
      const sender = msg.sender || 'user';
      const item = createElement('div', `support-chat-message support-chat-${sender}`);
      const text = createElement('div', 'support-chat-text');
      text.textContent = msg.text || '';
      item.appendChild(text);

      if (msg.created_at) {
        const meta = createElement('div', 'support-chat-meta');
        try {
          meta.textContent = new Date(msg.created_at).toLocaleString();
        } catch (e) {
          meta.textContent = msg.created_at;
        }
        item.appendChild(meta);
      }

      messagesWrap.appendChild(item);
    });

    messagesWrap.scrollTop = messagesWrap.scrollHeight;
  }

  function renderChat() {
    STATE.mode = 'chat';
    bodyContainer.innerHTML = '';

    const title = createElement('h4', null, 'Чат с менеджером');
    const helper = createElement('p', null, 'Менеджер ответит вам здесь, как только будет свободен.');
    const statusEl = createElement('div', 'support-chat-status');

    const messagesWrap = createElement('div', 'support-chat-messages');
    const errorEl = createElement('div', 'support-chat-error');
    errorEl.style.display = 'none';

    const input = createElement('textarea', 'support-chat-input');
    input.setAttribute('rows', '3');
    input.placeholder = 'Напишите сообщение менеджеру...';

    const sendButton = createElement('button', 'support-widget-action-btn', 'Отправить');
    sendButton.type = 'button';

    const backBtn = createElement('button', 'support-widget-action-btn', 'Назад к FAQ');
    backBtn.type = 'button';

    const buttons = createElement('div', 'support-widget-nav');
    buttons.appendChild(sendButton);
    buttons.appendChild(backBtn);

    const form = createElement('div', 'support-chat-form');
    form.appendChild(input);
    form.appendChild(buttons);

    bodyContainer.appendChild(title);
    bodyContainer.appendChild(helper);
    bodyContainer.appendChild(statusEl);
    bodyContainer.appendChild(messagesWrap);
    bodyContainer.appendChild(errorEl);
    bodyContainer.appendChild(form);

    STATE.chatElements = {
      messages: messagesWrap,
      input,
      status: statusEl,
      error: errorEl,
    };

    function submitMessage() {
      const value = input.value.trim();
      if (!value) return;
      input.value = '';
      const now = new Date().toISOString();
      STATE.chatMessages.push({ sender: 'user', text: value, created_at: now });
      renderChatMessages();
      sendChatMessage(value)?.then(fetchAndRenderMessages);
    }

    sendButton.addEventListener('click', submitMessage);
    backBtn.addEventListener('click', () => {
      STATE.mode = 'faq';
      stopChatPolling();
      renderCategories();
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        submitMessage();
      }
    });

    renderChatMessages();
  }

  function switchToChat() {
    ensureSessionKey();
    startChatSession();
    renderChat();
    startChatPolling();
  }

  function generateSessionKey() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function ensureSessionKey() {
    if (STATE.sessionKey) {
      return STATE.sessionKey;
    }
    let key = null;
    try {
      key = localStorage.getItem(SESSION_STORAGE_KEY);
    } catch (e) {
      // ignore
    }
    if (!key) {
      key = generateSessionKey();
      try {
        localStorage.setItem(SESSION_STORAGE_KEY, key);
      } catch (e) {
        // ignore
      }
    }
    STATE.sessionKey = key;
    return key;
  }

  function stopChatPolling() {
    if (STATE.chatTimer) {
      clearInterval(STATE.chatTimer);
      STATE.chatTimer = null;
    }
  }

  function startChatPolling() {
    stopChatPolling();
    STATE.chatTimer = setInterval(fetchAndRenderMessages, POLL_INTERVAL_MS);
    fetchAndRenderMessages();
  }

  function startChatSession() {
    const session_key = ensureSessionKey();
    return fetch('/api/webchat/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_key, page: window.location.href }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Request failed');
        }
        return response.json();
      })
      .then((data) => {
        STATE.sessionId = data?.session_id || null;
        STATE.chatStatus = data?.status || 'open';
        STATE.chatError = null;
        return data;
      })
      .catch((err) => {
        console.error('Support widget: failed to start chat', err);
        STATE.chatError = CHAT_ERROR_MESSAGE;
      });
  }

  function fetchAndRenderMessages() {
    const session_key = ensureSessionKey();
    fetch(`/api/webchat/messages?session_key=${encodeURIComponent(session_key)}&limit=50`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Request failed');
        }
        return response.json();
      })
      .then((data) => {
        STATE.chatStatus = data?.status || 'open';
        STATE.chatMessages = Array.isArray(data?.messages) ? data.messages : [];
        STATE.chatError = null;
        renderChatMessages();
      })
      .catch((err) => {
        console.error('Support widget: failed to fetch messages', err);
        STATE.chatError = CHAT_ERROR_MESSAGE;
        renderChatMessages();
      });
  }

  function sendChatMessage(text) {
    const session_key = ensureSessionKey();
    return fetch('/api/webchat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_key, text }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Request failed');
        }
        STATE.chatError = null;
        return response.json();
      })
      .catch((err) => {
        console.error('Support widget: failed to send message', err);
        STATE.chatError = CHAT_ERROR_MESSAGE;
        renderChatMessages();
      });
  }

  const floatingButton = createElement('button', 'support-widget-floating-button', '❔');
  floatingButton.type = 'button';
  floatingButton.setAttribute('aria-label', 'Помощник MiniDeN');

  const panel = createElement('div', 'support-widget-panel');
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-hidden', 'true');
  panel.setAttribute('aria-label', 'Виджет помощника MiniDeN');

  const header = createElement('div', 'support-widget-header');
  const headerTexts = createElement('div');
  const title = createElement('div', 'support-widget-title', 'Помощник MiniDeN');
  const subtitle = createElement('div', 'support-widget-subtitle', 'FAQ и быстрые ответы');
  headerTexts.appendChild(title);
  headerTexts.appendChild(subtitle);

  const closeButton = createElement('button', 'support-widget-close', '×');
  closeButton.type = 'button';
  closeButton.setAttribute('aria-label', 'Закрыть помощника');

  header.appendChild(headerTexts);
  header.appendChild(closeButton);

  const bodyContainer = createElement('div', 'support-widget-body');

  const footer = createElement('div', 'support-widget-footer');
  const telegramButton = createElement('a', 'support-widget-telegram', 'Открыть чат в Telegram');
  telegramButton.href = TELEGRAM_BOT_URL;
  telegramButton.target = '_blank';
  telegramButton.rel = 'noopener';

  footer.appendChild(telegramButton);

  panel.appendChild(header);
  panel.appendChild(bodyContainer);
  panel.appendChild(footer);

  body.appendChild(panel);
  body.appendChild(floatingButton);

  function togglePanel() {
    const isOpen = panel.classList.toggle('open');
    panel.setAttribute('aria-hidden', String(!isOpen));
    floatingButton.setAttribute('aria-expanded', String(isOpen));

    if (isOpen) {
      ensureFaqLoaded();
      if (STATE.mode === 'chat') {
        switchToChat();
      } else {
        renderCategories();
      }
    }
  }

  function closePanel() {
    if (panel.classList.contains('open')) {
      panel.classList.remove('open');
      panel.setAttribute('aria-hidden', 'true');
      floatingButton.setAttribute('aria-expanded', 'false');
      stopChatPolling();
    }
  }

  floatingButton.addEventListener('click', togglePanel);
  closeButton.addEventListener('click', closePanel);

  function setLoading() {
    bodyContainer.innerHTML = '';
    const loading = createElement('div', 'support-widget-loading', 'Загружаем подсказки...');
    bodyContainer.appendChild(loading);
  }

  function setError(message) {
    bodyContainer.innerHTML = '';
    const error = createElement('div', 'support-widget-error');
    const strong = createElement('strong', null, 'Не удалось загрузить подсказки');
    const info = createElement('div', null, message || 'Попробуйте позже или напишите нам в Telegram.');
    error.appendChild(strong);
    error.appendChild(info);

    const nav = createElement('div', 'support-widget-nav');
    const telegram = createElement('a', 'support-widget-telegram', 'Открыть чат в Telegram');
    telegram.href = TELEGRAM_BOT_URL;
    telegram.target = '_blank';
    telegram.rel = 'noopener';
    nav.appendChild(telegram);

    bodyContainer.appendChild(error);
    bodyContainer.appendChild(nav);
  }

  function ensureFaqLoaded() {
    if (STATE.loaded || STATE.loading) {
      return;
    }

    STATE.loading = true;
    setLoading();
    fetch('/api/faq')
      .then((response) => {
        if (!response.ok) {
          throw new Error('Request failed');
        }
        return response.json();
      })
      .then((data) => {
        cacheFaqItems(Array.isArray(data) ? data : []);
        STATE.loaded = true;
        STATE.error = null;
        renderCategories();
      })
      .catch((err) => {
        console.error('Support widget: failed to load FAQ', err);
        STATE.error = err;
        setError('Попробуйте позже или напишите нам в Telegram.');
      })
      .finally(() => {
        STATE.loading = false;
      });
  }

  function cacheFaqItems(items) {
    STATE.faqs = items;
    STATE.faqsByCategory = new Map();
    STATE.questionsCache = new Map();

    items.forEach((item) => {
      if (!item || !item.category) return;
      const category = item.category;
      const current = STATE.faqsByCategory.get(category) || [];
      current.push(item);
      STATE.faqsByCategory.set(category, current);
      if (item.id != null) {
        STATE.questionsCache.set(item.id, item);
      }
    });
  }

  function renderCategories() {
    bodyContainer.innerHTML = '';

    STATE.mode = 'faq';
    stopChatPolling();

    const introTitle = createElement('h4', null, 'Здравствуйте! Чем я могу помочь?');
    const introText = createElement('p', null, 'Выберите категорию, чтобы увидеть популярные вопросы. Все ответы собраны в базе знаний MiniDeN.');
    const contactManager = createElement('button', 'support-widget-action-btn', 'Нужна помощь менеджера');
    contactManager.type = 'button';
    contactManager.addEventListener('click', () => {
      switchToChat();
    });
    bodyContainer.appendChild(introTitle);
    bodyContainer.appendChild(introText);
    bodyContainer.appendChild(contactManager);

    if (STATE.loading) {
      const loading = createElement('div', 'support-widget-loading', 'Загружаем подсказки...');
      bodyContainer.appendChild(loading);
      return;
    }

    if (STATE.error) {
      setError('Попробуйте позже или напишите нам в Telegram.');
      return;
    }

    const categories = Array.from(STATE.faqsByCategory.keys());

    if (!categories.length) {
      const empty = createElement('div', 'support-widget-empty', 'Пока нет готовых подсказок, но мы всегда на связи в Telegram.');
      bodyContainer.appendChild(empty);
      return;
    }

    const list = createElement('div', 'support-widget-list');
    categories.forEach((category) => {
      const pill = createElement('button', 'support-widget-pill', category);
      pill.type = 'button';
      pill.addEventListener('click', () => handleCategorySelect(category));
      list.appendChild(pill);
    });

    bodyContainer.appendChild(list);
    const helper = createElement('div', 'support-widget-helper-text', 'Нажмите на категорию, чтобы увидеть список вопросов.');
    bodyContainer.appendChild(helper);
  }

  function handleCategorySelect(category) {
    STATE.currentCategory = category;
    if (STATE.loaded && STATE.faqsByCategory.has(category)) {
      renderQuestions(category);
      return;
    }

    setLoading();
    fetch(`/api/faq?category=${encodeURIComponent(category)}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Request failed');
        }
        return response.json();
      })
      .then((data) => {
        const items = Array.isArray(data) ? data : [];
        const merged = [...STATE.faqs];
        items.forEach((item) => {
          merged.push(item);
        });
        cacheFaqItems(merged);
        renderQuestions(category);
      })
      .catch((err) => {
        console.error('Support widget: failed to load category', err);
        setError('Не удалось загрузить список вопросов. Попробуйте позже.');
      });
  }

  function renderQuestions(category) {
    bodyContainer.innerHTML = '';

    const title = createElement('h4', null, category);
    const helper = createElement('p', null, 'Выберите вопрос, чтобы посмотреть ответ.');

    bodyContainer.appendChild(title);
    bodyContainer.appendChild(helper);

    const questions = STATE.faqsByCategory.get(category) || [];
    if (!questions.length) {
      const empty = createElement('div', 'support-widget-empty', 'Здесь пока нет вопросов. Напишите нам в Telegram — мы поможем.');
      bodyContainer.appendChild(empty);
      return;
    }

    const list = createElement('div', 'support-widget-list');
    questions.forEach((item) => {
      const questionBtn = createElement('button', 'support-widget-question', item.question || 'Вопрос');
      questionBtn.type = 'button';
      questionBtn.addEventListener('click', () => {
        if (item?.id == null) {
          renderAnswer(item);
          return;
        }
        handleQuestionSelect(item.id);
      });
      list.appendChild(questionBtn);
    });

    bodyContainer.appendChild(list);

    const nav = createElement('div', 'support-widget-nav');
    const backToCategories = createElement('button', 'support-widget-action-btn', 'Назад к категориям');
    backToCategories.type = 'button';
    backToCategories.addEventListener('click', renderCategories);
    nav.appendChild(backToCategories);

    bodyContainer.appendChild(nav);
  }

  function handleQuestionSelect(questionId) {
    STATE.currentQuestionId = questionId;
    if (STATE.questionsCache.has(questionId)) {
      renderAnswer(STATE.questionsCache.get(questionId));
      return;
    }

    setLoading();
    fetch(`/api/faq/${encodeURIComponent(questionId)}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Request failed');
        }
        return response.json();
      })
      .then((item) => {
        if (item && item.id != null) {
          STATE.questionsCache.set(item.id, item);
        }
        renderAnswer(item);
      })
      .catch((err) => {
        console.error('Support widget: failed to load FAQ item', err);
        setError('Не удалось загрузить ответ. Попробуйте позже или напишите нам в Telegram.');
      });
  }

  function renderAnswer(item) {
    bodyContainer.innerHTML = '';
    if (!item) {
      const empty = createElement('div', 'support-widget-empty', 'Ответ недоступен. Попробуйте другой вопрос или напишите нам в Telegram.');
      bodyContainer.appendChild(empty);
      return;
    }

    const answerBlock = createElement('div', 'support-widget-answer');
    const questionTitle = createElement('h5', null, item.question || 'Вопрос');
    const answerText = createElement('p');
    answerText.textContent = item.answer || 'Ответ пока не добавлен. Пожалуйста, напишите нам в Telegram.';
    answerBlock.appendChild(questionTitle);
    answerBlock.appendChild(answerText);

    bodyContainer.appendChild(answerBlock);

    const nav = createElement('div', 'support-widget-nav');

    const backToQuestions = createElement('button', 'support-widget-action-btn', 'Назад к вопросам');
    backToQuestions.type = 'button';
    backToQuestions.addEventListener('click', () => {
      if (STATE.currentCategory) {
        renderQuestions(STATE.currentCategory);
      } else {
        renderCategories();
      }
    });
    nav.appendChild(backToQuestions);

    const backToCategories = createElement('button', 'support-widget-action-btn', 'Назад к категориям');
    backToCategories.type = 'button';
    backToCategories.addEventListener('click', renderCategories);
    nav.appendChild(backToCategories);

    const openChat = createElement('button', 'support-widget-action-btn', 'Нужна помощь менеджера');
    openChat.type = 'button';
    openChat.addEventListener('click', () => {
      switchToChat();
    });
    nav.appendChild(openChat);

    const openTelegram = createElement('a', 'support-widget-telegram', 'Открыть чат в Telegram');
    openTelegram.href = TELEGRAM_BOT_URL;
    openTelegram.target = '_blank';
    openTelegram.rel = 'noopener';
    nav.appendChild(openTelegram);

    bodyContainer.appendChild(nav);
  }
})();
