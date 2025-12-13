(function () {
  const state = {
    chats: [],
    activeSessionId: null,
    activeChat: null,
    lastMessageId: 0,
    filter: 'all',
    search: '',
    pollingTimers: { list: null, messages: null },
    viewActive: false,
  };

  const elements = {};
  let onError;
  let onStatus;
  let searchTimer;

  function qs(id) {
    return document.getElementById(id);
  }

  function init(options = {}) {
    onError = options.onError;
    onStatus = options.onStatus;

    elements.sidebar = qs('chat-sidebar');
    elements.sidebarToggle = qs('chat-sidebar-toggle');
    elements.searchInput = qs('chat-search-input');
    elements.statusFilter = qs('chat-status-filter');
    elements.refreshButton = qs('chat-refresh-button');
    elements.chatList = qs('chat-list');
    elements.chatHeader = qs('chat-header');
    elements.chatTitle = qs('chat-title');
    elements.chatSubtitle = qs('chat-subtitle');
    elements.chatStatusBadge = qs('chat-status-badge');
    elements.chatHeaderRefresh = qs('chat-header-refresh');
    elements.closeButton = qs('chat-close-button');
    elements.reopenButton = qs('chat-reopen-button');
    elements.messagesBox = qs('chat-messages');
    elements.newIndicator = qs('chat-new-indicator');
    elements.textarea = qs('chat-input');
    elements.sendButton = qs('chat-send-button');
    elements.closedHint = qs('chat-closed-hint');
    elements.composer = qs('chat-composer');

    bindEvents();
  }

  function bindEvents() {
    elements.sidebarToggle?.addEventListener('click', () => {
      elements.sidebar?.classList.toggle('open');
    });

    elements.searchInput?.addEventListener('input', () => {
      const value = elements.searchInput.value.trim();
      clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        state.search = value;
        if (state.viewActive) {
          loadChats();
        }
      }, 250);
    });

    elements.statusFilter?.addEventListener('change', () => {
      state.filter = elements.statusFilter.value || 'all';
      if (state.viewActive) {
        loadChats();
      }
    });

    elements.refreshButton?.addEventListener('click', () => {
      refreshAll();
    });

    elements.chatHeaderRefresh?.addEventListener('click', () => {
      refreshActive();
    });

    elements.sendButton?.addEventListener('click', sendMessage);
    elements.textarea?.addEventListener('input', updateSendAvailability);
    elements.textarea?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });

    elements.closeButton?.addEventListener('click', closeChat);
    elements.reopenButton?.addEventListener('click', reopenChat);

    elements.messagesBox?.addEventListener('scroll', () => {
      if (!elements.messagesBox) return;
      if (isNearBottom()) {
        hideNewIndicator();
      }
    });

    elements.newIndicator?.addEventListener('click', () => {
      scrollToBottom();
    });
  }

  function activate() {
    state.viewActive = true;
    loadChats();
    startListPolling();
    if (state.activeSessionId) {
      startMessagePolling();
    }
  }

  function deactivate() {
    state.viewActive = false;
    stopPolling();
  }

  async function loadChats() {
    if (!elements.chatList) return;
    try {
      const params = { status: state.filter || 'all', limit: 100 };
      if (state.search) params.search = state.search;
      const data = await apiGet('/admin/webchat/sessions', params);
      state.chats = data?.items || [];
      renderChatList();
      syncActiveChat();
    } catch (error) {
      handleError('Не удалось загрузить чаты', error);
    }
  }

  function renderChatList() {
    elements.chatList.innerHTML = '';
    if (!state.chats.length) {
      const empty = document.createElement('div');
      empty.className = 'chat-empty muted';
      empty.textContent = 'Чатов не найдено';
      elements.chatList.appendChild(empty);
      return;
    }

    state.chats.forEach((chat) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'chat-item';
      item.setAttribute('role', 'option');
      if (Number(chat.session_id) === Number(state.activeSessionId)) {
        item.classList.add('active');
      }

      const avatar = document.createElement('div');
      avatar.className = 'chat-avatar';
      avatar.textContent = getAvatarLetter(chat);

      const top = document.createElement('div');
      top.className = 'chat-item__top';

      const name = document.createElement('div');
      name.className = 'chat-name';
      name.textContent = getDisplayName(chat);

      const meta = document.createElement('div');
      meta.className = 'chat-meta';

      const statusDot = document.createElement('span');
      statusDot.className = `status-dot ${chat.status || 'open'}`;
      statusDot.title = chat.status || 'open';
      meta.appendChild(statusDot);

      if (chat.unread_for_manager) {
        const unread = document.createElement('span');
        unread.className = 'unread-badge';
        unread.textContent = Number(chat.unread_for_manager) > 99 ? '99+' : chat.unread_for_manager;
        meta.appendChild(unread);
      }

      const time = document.createElement('div');
      time.className = 'chat-time';
      time.textContent = formatTime(chat.last_message_at || chat.updated_at || chat.created_at);

      top.appendChild(name);
      top.appendChild(time);

      const preview = document.createElement('div');
      preview.className = 'chat-preview';
      preview.textContent = chat.last_message || 'Без сообщений';

      const footer = document.createElement('div');
      footer.className = 'chat-meta';
      footer.innerHTML = `<span>${chat.session_key || chat.session_id}</span>`;
      footer.appendChild(meta);

      item.appendChild(avatar);
      item.appendChild(top);
      item.appendChild(preview);
      item.appendChild(footer);

      item.addEventListener('click', () => {
        openChat(chat.session_id);
        elements.sidebar?.classList.remove('open');
      });

      elements.chatList.appendChild(item);
    });
  }

  function getDisplayName(chat) {
    if (!chat) return 'Гость';
    if (chat.user_identifier) {
      return chat.user_identifier.split('|')[1] || chat.user_identifier || 'Гость';
    }
    return 'Гость';
  }

  function getAvatarLetter(chat) {
    const name = getDisplayName(chat);
    return (name || 'Г')[0].toUpperCase();
  }

  function formatTime(value) {
    if (!value) return '';
    const date = new Date(value);
    const now = new Date();
    const sameDay =
      date.getFullYear() === now.getFullYear() &&
      date.getMonth() === now.getMonth() &&
      date.getDate() === now.getDate();
    const options = sameDay ? { hour: '2-digit', minute: '2-digit' } : { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' };
    return date.toLocaleString('ru-RU', options);
  }

  async function openChat(sessionId) {
    state.activeSessionId = sessionId;
    state.lastMessageId = 0;
    syncActiveChat();
    await refreshActive();
    startMessagePolling();
  }

  function syncActiveChat() {
    state.activeChat = state.chats.find((c) => Number(c.session_id) === Number(state.activeSessionId)) || null;
    renderHeader();
  }

  async function refreshActive() {
    if (!state.activeSessionId) return;
    await Promise.all([loadMessages(), loadChats()]);
  }

  async function refreshAll() {
    await Promise.all([loadChats(), loadMessages({ append: false, skipIfNoActive: true })]);
  }

  function renderHeader() {
    if (!state.activeChat) {
      elements.chatTitle.textContent = 'Выберите чат';
      elements.chatSubtitle.textContent = 'Чтобы увидеть переписку, выберите диалог слева.';
      elements.chatStatusBadge.textContent = '—';
      elements.closeButton.disabled = true;
      elements.reopenButton.disabled = true;
      toggleComposer(false, true);
      updateSendAvailability();
      return;
    }

    const chat = state.activeChat;
    elements.chatTitle.textContent = getDisplayName(chat);
    elements.chatSubtitle.textContent = `${chat.user_identifier || 'Гость'} · ${chat.session_key || chat.session_id || ''}`;
    elements.chatStatusBadge.textContent = getStatusLabel(chat.status);
    elements.closeButton.disabled = chat.status === 'closed';
    elements.reopenButton.disabled = chat.status !== 'closed';
    toggleComposer(chat.status !== 'closed', chat.status === 'closed');
    updateSendAvailability();
  }

  function getStatusLabel(status) {
    switch (status) {
      case 'closed':
        return 'Закрыт';
      case 'waiting_manager':
        return 'Ожидает ответа';
      default:
        return 'Открыт';
    }
  }

  function toggleComposer(enabled, isClosed) {
    if (elements.textarea) {
      elements.textarea.disabled = !enabled;
      if (!enabled) {
        elements.textarea.value = '';
      }
    }
    if (elements.sendButton) {
      elements.sendButton.disabled = !enabled;
    }
    if (elements.closedHint) {
      elements.closedHint.hidden = !isClosed;
    }
    updateSendAvailability();
  }

  function updateSendAvailability() {
    if (!elements.sendButton) return;
    const hasText = Boolean(elements.textarea && elements.textarea.value.trim());
    const isClosed = state.activeChat?.status === 'closed';
    elements.sendButton.disabled = !state.activeSessionId || !hasText || isClosed;
  }

  async function loadMessages(options = {}) {
    const { append = false, skipIfNoActive = false } = options;
    if (!state.activeSessionId) {
      if (!skipIfNoActive && elements.messagesBox) {
        elements.messagesBox.innerHTML = '';
      }
      return;
    }

    try {
      const params = { session_id: state.activeSessionId, after_id: append ? state.lastMessageId : 0 };
      const data = await apiGet('/admin/webchat/messages', params);
      const items = data?.items || [];
      if (!append) {
        state.lastMessageId = 0;
        elements.messagesBox.innerHTML = '';
      }
      renderMessages(items, { append });
      if (state.activeChat) {
        state.activeChat.unread_for_manager = 0;
      }
    } catch (error) {
      handleError('Не удалось загрузить сообщения', error);
    }
  }

  function renderMessages(messages, { append }) {
    if (!elements.messagesBox) return;
    if (!append && !messages.length) {
      elements.messagesBox.innerHTML = '<div class="chat-empty muted">Сообщений пока нет</div>';
      return;
    }

    const shouldStickToBottom = isNearBottom();

    messages.forEach((msg) => {
      const wrapper = document.createElement('div');
      wrapper.className = `chat-message ${msg.sender || 'system'}`;
      wrapper.textContent = msg.text || '';

      const meta = document.createElement('div');
      meta.className = 'message-meta';
      meta.textContent = msg.created_at ? formatTime(msg.created_at) : '';
      wrapper.appendChild(meta);

      if (msg.id) {
        state.lastMessageId = Math.max(state.lastMessageId, Number(msg.id));
      }

      elements.messagesBox.appendChild(wrapper);
    });

    if (shouldStickToBottom) {
      scrollToBottom();
    } else if (messages.length) {
      showNewIndicator();
    }
  }

  async function sendMessage() {
    if (!state.activeSessionId || !elements.textarea) return;
    const text = elements.textarea.value.trim();
    if (!text) return;
    elements.sendButton.disabled = true;
    try {
      await apiPost('/admin/webchat/send', { session_id: state.activeSessionId, text });
      elements.textarea.value = '';
      await Promise.all([loadMessages({ append: true }), loadChats()]);
      scrollToBottom();
    } catch (error) {
      handleError('Не удалось отправить сообщение', error);
    } finally {
      updateSendAvailability();
    }
  }

  async function closeChat() {
    if (!state.activeSessionId) return;
    try {
      elements.closeButton.disabled = true;
      await apiPost('/admin/webchat/close', { session_id: state.activeSessionId });
      await loadChats();
      syncActiveChat();
    } catch (error) {
      handleError('Не удалось закрыть чат', error);
    }
  }

  async function reopenChat() {
    if (!state.activeSessionId) return;
    try {
      elements.reopenButton.disabled = true;
      await apiPost('/admin/webchat/reopen', { session_id: state.activeSessionId });
      await loadChats();
      syncActiveChat();
      await loadMessages();
    } catch (error) {
      handleError('Не удалось открыть чат заново', error);
    } finally {
      elements.reopenButton.disabled = state.activeChat?.status !== 'closed';
    }
  }

  function isNearBottom() {
    if (!elements.messagesBox) return true;
    const { scrollTop, scrollHeight, clientHeight } = elements.messagesBox;
    return scrollHeight - (scrollTop + clientHeight) < 120;
  }

  function scrollToBottom() {
    if (!elements.messagesBox) return;
    elements.messagesBox.scrollTop = elements.messagesBox.scrollHeight;
    hideNewIndicator();
  }

  function showNewIndicator() {
    elements.newIndicator?.classList.remove('hidden');
  }

  function hideNewIndicator() {
    elements.newIndicator?.classList.add('hidden');
  }

  function startListPolling() {
    stopListPolling();
    state.pollingTimers.list = window.setInterval(loadChats, 3000);
  }

  function startMessagePolling() {
    stopMessagePolling();
    if (!state.activeSessionId) return;
    state.pollingTimers.messages = window.setInterval(() => loadMessages({ append: true }), 2500);
  }

  function stopListPolling() {
    if (state.pollingTimers.list) {
      clearInterval(state.pollingTimers.list);
      state.pollingTimers.list = null;
    }
  }

  function stopMessagePolling() {
    if (state.pollingTimers.messages) {
      clearInterval(state.pollingTimers.messages);
      state.pollingTimers.messages = null;
    }
  }

  function stopPolling() {
    stopListPolling();
    stopMessagePolling();
  }

  function handleError(message, error) {
    console.error(error);
    if (typeof onError === 'function') {
      onError(error, message);
    }
    if (typeof onStatus === 'function') {
      onStatus(message || 'Ошибка', true);
    }
  }

  window.adminChats = { init, activate, deactivate };
})();
