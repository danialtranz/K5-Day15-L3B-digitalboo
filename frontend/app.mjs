import { icon } from './icons.mjs';
import {
  accounts, addMessage, createTask, dateInput, dateLabel, defaultScope, executeTask, id, inbox,
  intent, isUnrelated, log, mailScope, newThread, nextMorning, normalize, notify, parseNotes, sampleNotes,
  scenarios, scopeLabel, seed, timeLabel,
} from './mock.mjs';
import { button, esc, iconButton, logo, renderApp, scopeFields, taskCard } from './views.mjs';

const app = document.querySelector('#app');
const dialog = document.querySelector('#dialog');
const toast = document.querySelector('#toast');
const query = new URLSearchParams(location.search);
const provider = query.get('auth');

if (Object.hasOwn(accounts, provider)) {
  renderAuthWindow(provider);
} else {
  startApp();
}

function renderAuthWindow(name) {
  document.title = `${accounts[name].name} · Đăng nhập mô phỏng`;
  app.innerHTML = `<main class="auth-window"><form class="panel auth-panel"><div class="brand">${logo()}</div><div class="auth-icon">${icon(accounts[name].icon, 27)}</div><h1>${name === 'outlook' ? 'Kết nối Microsoft' : 'Đăng nhập Phoenix'}</h1><p>${esc(accounts[name].address)}</p><div class="callout info">${icon('lock', 19)}${name === 'outlook' ? 'Cho phép Digitalboo đọc email Outlook trong bản mô phỏng.' : 'Xác nhận phiên đăng nhập Phoenix mô phỏng.'}</div><button class="btn primary" type="submit">${name === 'outlook' ? 'Cấp quyền đọc' : 'Hoàn tất đăng nhập'}</button><button class="btn text-btn" type="button" data-close>Hủy</button></form></main>`;
  app.querySelector('form').addEventListener('submit', (event) => {
    event.preventDefault();
    if (!window.opener) {
      app.querySelector('h1').textContent = 'Hãy mở kết nối từ Digitalboo';
      return;
    }
    window.opener.postMessage({ type: 'digitalboo-auth', name, key: query.get('key') }, location.origin);
    window.close();
  });
  app.querySelector('[data-close]').addEventListener('click', () => window.close());
}

function startApp() {
  const storageKey = 'digitalboo-demo-v1';
  let state = restore();
  const ui = { menu: false, loading: new Map(), attachments: new Map(), composers: new Map(), auth: new Map(), busyFile: new Set(), fileThread: '' };
  let modal = null;
  let revision = 0;
  let toastTimer;

  function restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey));
      if (saved?.version === 1 && Object.hasOwn(scenarios, saved.scenario)) return saved;
    } catch {
      // A blocked or invalid local store can use a fresh session.
    }
    return seed();
  }

  function persist() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
    } catch {
      // Keep the session available when browser storage is blocked or full.
    }
  }

  function render(scroll = 'keep') {
    const old = document.querySelector('#chat-scroll');
    const previousTop = old?.scrollTop ?? 0;
    const previousHeight = old?.scrollHeight ?? 0;
    const focused = document.activeElement?.id === 'message-input';
    const selection = focused ? document.activeElement.selectionStart : 0;
    const sidebarTop = app.querySelector('.sidebar-main')?.scrollTop ?? 0;
    app.innerHTML = renderApp(state, ui);
    app.querySelector('.sidebar-main').scrollTop = sidebarTop;
    const chat = document.querySelector('#chat-scroll');
    if (chat) {
      const message = chat.querySelector('.chat-log > .message:last-child');
      if (scroll === 'new' && message && message.offsetHeight > chat.clientHeight) {
        chat.scrollTop = message.getBoundingClientRect().top - chat.getBoundingClientRect().top + chat.scrollTop - 18;
      } else {
        chat.scrollTop = scroll === 'keep' && previousHeight ? previousTop : chat.scrollHeight;
      }
    }
    if (focused) {
      const input = document.querySelector('#message-input');
      if (input && !input.disabled) {
        input.focus({ preventScroll: true });
        input.setSelectionRange(selection, selection);
      }
    }
    persist();
  }

  function flash(message) {
    clearTimeout(toastTimer);
    toast.innerHTML = `${icon('check', 18)}<span>${esc(message)}</span>`;
    toast.classList.add('visible');
    toastTimer = setTimeout(() => toast.classList.remove('visible'), 2800);
  }

  const activeThread = () => state.threads.find((thread) => thread.id === state.active);
  const getTask = (taskId) => state.tasks.find((task) => task.id === taskId);
  const getMail = (mailId) => inbox(state.now, state.scenario).find((mail) => mail.id === mailId);
  const taskThread = (task) => state.threads.find((thread) => thread.id === task.threadId);

  function navigate(page) {
    state.page = page;
    ui.menu = false;
    if (page === 'chat' && !activeThread()) {
      if (state.threads.length) state.active = state.threads[0].id;
      else makeThread();
    }
    render(page === 'chat' ? 'new' : 'keep');
    window.scrollTo(0, 0);
  }

  function openThread(threadId) {
    if (!state.threads.some((thread) => thread.id === threadId)) return;
    state.active = threadId;
    navigate('chat');
  }

  function makeThread(title, flow) {
    const thread = newThread(title, flow);
    state.threads.unshift(thread);
    state.active = thread.id;
    state.page = 'chat';
    ui.menu = false;
    return thread;
  }

  function setBusy(thread, label, callback) {
    if (ui.loading.has(thread.id)) return;
    ui.loading.set(thread.id, label);
    render('end');
    const generation = revision;
    setTimeout(() => {
      if (generation !== revision) return;
      ui.loading.delete(thread.id);
      callback();
      render(state.active === thread.id ? 'new' : 'keep');
    }, 520);
  }

  function startFlow(flow, existing = null) {
    if (existing && ui.loading.has(existing.id)) return;
    const workingDraft = flow === 'standup' && state.tasks.find((task) => task.kind === 'standup' && ['missing', 'pending', 'scheduled', 'running'].includes(task.status));
    if (!existing && workingDraft) {
      openThread(workingDraft.threadId);
      return;
    }
    const thread = existing ?? makeThread(flow === 'standup' ? 'Chuẩn bị Daily Standup' : 'Tổng hợp Outlook', flow);
    const message = flow === 'standup' ? 'Giúp tôi chuẩn bị Daily Standup.' : 'Tóm tắt các email quan trọng gần đây.';
    addMessage(thread, 'user', message);
    process(thread, message);
  }

  function ensureStandup(thread) {
    const existing = getTask(thread.taskId);
    if (existing && ['missing', 'pending'].includes(existing.status)) return existing;
    const task = createTask(state, { kind: 'standup', title: 'Daily Standup', status: 'missing', threadId: thread.id, draft: { ...thread.draft } });
    thread.taskId = task.id;
    return task;
  }

  function requireAuth(thread, name, pending) {
    thread.resume = pending;
    addMessage(thread, 'agent', state.accounts[name] === 'expired'
      ? `Phiên ${accounts[name].name} đã hết hạn. Kết nối lại để mình tiếp tục yêu cầu đang dở.`
      : `Bạn cần kết nối ${accounts[name].name} để mình tiếp tục yêu cầu này.`, { type: 'auth', name });
  }

  function collect(thread, notes = {}) {
    const task = ensureStandup(thread);
    Object.assign(thread.draft, notes);
    task.draft = { ...thread.draft };
    const missingYesterday = !thread.draft.yesterday;
    const missingTomorrow = !thread.draft.tomorrow;
    if (missingYesterday || missingTomorrow) {
      task.status = 'missing';
      const message = missingYesterday && missingTomorrow
        ? 'Bạn đã làm những việc gì hôm qua và dự định làm gì ngày mai? Bạn có thể nhắn, đính kèm tài liệu hoặc thêm ghi chú.'
        : missingYesterday ? 'Mình đã lưu kế hoạch ngày mai. Bạn bổ sung giúp mình các việc đã làm hôm qua nhé.'
          : 'Mình đã lưu các việc hôm qua. Bạn dự định làm gì ngày mai?';
      addMessage(thread, 'agent', message, { type: 'collect', taskId: task.id });
      thread.step = 'collect';
      return;
    }
    task.status = 'pending';
    thread.step = 'preview';
    addMessage(thread, 'agent', 'Mình đã chuẩn bị bản nháp từ nội dung bạn cung cấp. Bạn có thể chỉnh sửa trước khi đặt lịch.', { type: 'draft', taskId: task.id });
    log(state, 'Đã chuẩn bị bản nháp Daily Standup', 'Chờ bạn xác nhận và chọn thời điểm nộp.', task.id, thread.id);
  }

  function noYesterday(thread) {
    const task = ensureStandup(thread);
    thread.draft.yesterday = '';
    task.draft = { ...thread.draft };
    task.status = 'missing';
    thread.step = 'collect';
    addMessage(thread, 'agent', 'Mình chưa thể hoàn thành Daily Standup khi chưa có công việc đã thực hiện. Bạn có thể bổ sung thông tin nếu cần tiếp tục.', { type: 'collect', taskId: task.id });
  }

  function noPlan(thread) {
    const task = ensureStandup(thread);
    thread.draft.tomorrow = '';
    task.draft = { ...thread.draft };
    task.status = 'missing';
    if (!thread.draft.yesterday) {
      collect(thread);
      return;
    }
    thread.step = 'suggest';
    addMessage(thread, 'agent', 'Bạn có muốn mình gợi ý kế hoạch ngày mai dựa trên những việc đã làm hôm qua?', { type: 'suggest', taskId: task.id });
  }

  function suggestPlan(thread) {
    if (!thread.draft.yesterday) return collect(thread);
    const items = thread.draft.yesterday.split(/\n+|;\s+/).map((item) => item.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim()).filter(Boolean);
    const tomorrow = items.map((item) => `Rà soát kết quả và ghi lại bước tiếp theo cho: ${item}`).join('\n');
    addMessage(thread, 'agent', 'Dưới đây là kế hoạch gợi ý. Bạn có thể sửa từng mục hoặc hủy bản nháp nếu chưa muốn dùng.');
    collect(thread, { tomorrow });
  }

  const noWork = (value) => /\b(?:khong (?:lam|co|thuc hien)\s+(?:(?:cong )?viec(?: gi| nao)?|gi)|nghi ca ngay)\b/.test(normalize(value));
  const noPlanYet = (value) => /(?:chua (?:co )?(?:ke hoach|biet|du dinh)|khong co ke hoach)/.test(normalize(value));

  function standupInput(thread, text, documents = '') {
    const queryText = normalize(text);
    const notes = parseNotes([text, documents].filter(Boolean).join('\n'));
    const explicitlyNoWork = notes.yesterday ? noWork(notes.yesterday) : (/hom qua/.test(queryText) || thread.step === 'collect' && !thread.draft.yesterday) && noWork(text);
    const explicitlyNoPlan = notes.tomorrow ? noPlanYet(notes.tomorrow) : noPlanYet(text);
    if (!notes.yesterday && !notes.tomorrow && thread.step === 'collect'
      && !isUnrelated(text) && !explicitlyNoWork && !explicitlyNoPlan) {
      const content = documents || text;
      const generic = /^(?:giup|chuan bi|lam|nop|soan|bat dau|tiep tuc|ghi chu).*(?:stand.?up|bao cao)\s*[.!?]?$/.test(queryText) || /^(?:ok|co|vang|dong y|khong|chua)[.!?]?$/.test(queryText);
      if (content && (documents || !generic)) {
        if (!thread.draft.yesterday) notes.yesterday = content;
        else if (!thread.draft.tomorrow) notes.tomorrow = content;
      }
    }
    if (explicitlyNoWork) {
      if (notes.tomorrow && !explicitlyNoPlan) thread.draft.tomorrow = notes.tomorrow;
      noYesterday(thread);
    } else if (explicitlyNoPlan) {
      if (notes.yesterday) thread.draft.yesterday = notes.yesterday;
      noPlan(thread);
    } else {
      collect(thread, notes);
    }
  }

  function runInbox(thread, scope) {
    thread.scope = { ...scope };
    if (state.accounts.outlook !== 'connected') {
      requireAuth(thread, 'outlook', { flow: 'outlook', scope });
      return;
    }
    state.inboxAttempts++;
    if (state.scenario === 'outlookError' && state.inboxAttempts === 1) {
      addMessage(thread, 'agent', 'Lượt kiểm tra Outlook gặp sự cố.', { type: 'mail-error' });
      log(state, 'Truy xuất Outlook thất bại', 'Lượt đọc đầu gặp lỗi mạng.', '', thread.id);
      return;
    }
    state.lastInbox = { threadId: thread.id, scope: { ...scope } };
    addMessage(thread, 'agent', 'Đây là kết quả kiểm tra Outlook trong phạm vi bạn chọn.', { type: 'mail', scope: { ...scope } });
    log(state, 'Đã kiểm tra Outlook', scopeLabel(scope), '', thread.id);
  }

  function matchMail(text) {
    const prompt = normalize(text);
    return inbox(state.now, state.scenario).find((mail) => {
      const names = [mail.subject, mail.event, mail.action, mail.sender].filter(Boolean);
      return names.some((name) => prompt.includes(normalize(name))) || (mail.id === 'figma' && prompt.includes('figma'));
    });
  }

  function mailFollowup(thread, text) {
    const request = normalize(text);
    const mail = matchMail(text) ?? getMail(thread.lastMail);
    if (/\b(dat loi nhac|nhac toi)\b/.test(request) && mail) {
      thread.lastMail = mail.id;
      createReminder(thread, mail);
      return true;
    }
    if (/\b(hoan thanh|da lam xong)\b/.test(request) && mail?.action) {
      setComplete(mail.thread, true, thread.id);
      addMessage(thread, 'agent', `Đã đánh dấu hoàn thành trong ứng dụng: ${mail.action}.`);
      return true;
    }
    if (/\b(giai thich|chi tiet|chuoi)\b/.test(request) && mail) {
      thread.lastMail = mail.id;
      addMessage(thread, 'agent', 'Đây là email liên quan. Bạn có thể xem nội dung gốc và những thư trong cùng chuỗi.', { type: 'mail-detail', mailId: mail.id });
      return true;
    }
    if (/\b(dat loi nhac|nhac toi|hoan thanh|da lam xong|giai thich|chi tiet|chuoi)\b/.test(request)) {
      addMessage(thread, 'agent', 'Bạn đang nói đến email hoặc công việc nào? Bạn có thể dùng nút trên kết quả tổng hợp hoặc nhắn tên email.');
      return true;
    }
    return false;
  }

  function process(thread, text, documents = '', unreadable = []) {
    const previousFlow = thread.flow;
    const normalized = normalize(text);
    const editing = thread.flow === 'standup' && ['collect', 'suggest', 'preview'].includes(thread.step);
    const suppliedNotes = editing && Object.keys(parseNotes([text, documents].join('\n'))).length;
    const requested = suppliedNotes ? 'standup' : intent(text, thread.flow);
    const noExternalMailWrite = /\b(?:gui|xoa|luu tru|tra loi)\s+(?:thu|e-?mail|outlook)\b|\bdanh dau\s+(?:thu|e-?mail).*\b(?:da doc|chua doc)\b/.test(normalized);
    setBusy(thread, requested === 'outlook' ? 'Đang kiểm tra Outlook…' : 'Đang đọc yêu cầu…', () => {
      if (unreadable.length) addMessage(thread, 'agent', `Mình không đọc được nội dung từ ${unreadable.join(', ')}. Bạn có thể dùng tệp văn bản hoặc dán phần cần dùng vào ghi chú.`);
      if (noExternalMailWrite) {
        addMessage(thread, 'agent', 'Mình có thể đọc, phân tích và gợi ý việc cần làm từ Outlook. Hãy mở email gốc để thực hiện thao tác gửi, trả lời hoặc thay đổi email.', { type: 'choices' });
        return;
      }
      if (requested === 'standup' || (editing && requested !== 'outlook' && !isUnrelated(text))) {
        thread.flow = 'standup';
        thread.title = 'Chuẩn bị Daily Standup';
        if (state.accounts.phoenix !== 'connected') requireAuth(thread, 'phoenix', { flow: 'standup', text, documents });
        else if (thread.step === 'suggest' && /(?:^|\b)(?:co|dong y|goi y)(?:[.!?\s]|$)/.test(normalized) && !/\b(khong|chua)\b/.test(normalized)) suggestPlan(thread);
        else if (thread.step === 'suggest' && /\b(khong|bo sung sau|chua can)\b/.test(normalized)) declinePlan(thread);
        else if (thread.step === 'preview' && /\b(xac nhan|dat lich|hen gio)\b/.test(normalized)) showSchedule(getTask(thread.taskId));
        else if (thread.step === 'preview' && /\b(huy|khong (?:muon |can )?(?:tu dong )?nop|tu nop)\b/.test(normalized)) {
          const task = getTask(thread.taskId);
          if (/\btu nop\b/.test(normalized)) actions.manual(task?.id);
          else cancelTask(task);
        }
        else standupInput(thread, text, documents);
      } else if (requested === 'outlook') {
        thread.flow = 'outlook';
        if (previousFlow !== 'outlook' || thread.title === 'Trò chuyện mới') thread.title = 'Tổng hợp Outlook';
        if (state.accounts.outlook === 'connected' && mailFollowup(thread, text)) return;
        runInbox(thread, mailScope(text, thread.scope ?? defaultScope));
      } else if (requested === 'outside') {
        addMessage(thread, 'agent', 'Yêu cầu này nằm ngoài phạm vi mình hỗ trợ. Mình có thể giúp chuẩn bị Daily Standup hoặc tổng hợp Outlook.', { type: 'choices' });
      } else {
        addMessage(thread, 'agent', 'Bạn muốn chuẩn bị Daily Standup hay kiểm tra email Outlook?', { type: 'choices' });
      }
    });
  }

  function formDialog({ title, detail = '', fields, submit = '', form, buttons = '', value = '' }) {
    modal = { form, value };
    dialog.innerHTML = `<div class="dialog-head"><div><h2 id="dialog-title">${esc(title)}</h2>${detail ? `<p>${esc(detail)}</p>` : ''}</div>${iconButton('Đóng cửa sổ', 'close', 'close')}</div>
      <form data-form="${form ?? 'none'}"><div class="dialog-body">${fields}</div><div class="dialog-actions">${buttons}${submit ? '<button type="submit" class="btn primary">' + esc(submit) + '</button>' : ''}</div></form>`;
    if (!dialog.open) dialog.showModal();
  }

  function closeDialog() {
    if (modal?.form === 'auth') {
      const entry = ui.auth.get(modal.value);
      entry?.popup?.close();
      ui.auth.delete(modal.value);
    }
    modal = null;
    if (dialog.open) dialog.close();
  }

  function auth(name, resume = null) {
    if (!Object.hasOwn(accounts, name)) return;
    const key = id();
    const url = new URL('./', location.href);
    url.search = new URLSearchParams({ auth: name, key });
    const popup = window.open(url, `digitalboo-${name}`, 'popup,width=490,height=560');
    ui.auth.set(name, { name, key, popup, taskId: resume });
    formDialog({ title: `Kết nối ${accounts[name].name}`, detail: popup
      ? 'Hoàn tất trong cửa sổ xác thực mô phỏng. Nếu cửa sổ không hiện, bạn có thể tiếp tục ở đây.'
      : 'Trình duyệt đã chặn cửa sổ riêng. Tiếp tục xác thực mô phỏng tại đây.', form: 'auth', value: name,
      fields: `<div class="callout info">${icon('lock', 18)}${name === 'outlook' ? 'Cấp quyền đọc email Outlook.' : 'Xác nhận phiên đăng nhập Phoenix.'}</div>`, submit: popup ? 'Tiếp tục tại đây' : 'Hoàn tất kết nối', buttons: button('Hủy', 'close') });
  }

  function finishAuth(name) {
    const pending = ui.auth.get(name);
    ui.auth.delete(name);
    if (pending?.popup && !pending.popup.closed) pending.popup.close();
    state.accounts[name] = 'connected';
    closeDialog();
    flash(`Đã kết nối ${accounts[name].name}.`);
    const flow = name === 'phoenix' ? 'standup' : 'outlook';
    const waiting = state.threads.filter((thread) => thread.resume?.flow === flow);
    for (const thread of waiting) {
      const resume = thread.resume;
      delete thread.resume;
      addMessage(thread, 'agent', `Đã kết nối ${accounts[name].name}. Mình tiếp tục yêu cầu của bạn.`);
      setBusy(thread, 'Đang tiếp tục yêu cầu…', () => {
        if (resume.flow === 'outlook') runInbox(thread, resume.scope);
        else standupInput(thread, resume.text, resume.documents);
      });
    }
    if (pending?.taskId) {
      const task = getTask(pending.taskId);
      if (task?.status === 'failed') runTask(task);
    }
    render('new');
  }

  function showNotes(task, editing = false) {
    const thread = task ? taskThread(task) : activeThread();
    if (!thread) return;
    const draft = task?.draft ?? thread.draft;
    const fields = `<label>Việc đã làm hôm qua<textarea name="yesterday" rows="4" placeholder="Nhập công việc đã thực hiện hôm qua"${editing ? ' required' : ''}>${esc(draft?.yesterday)}</textarea></label>
      <label>Kế hoạch ngày mai<textarea name="tomorrow" rows="4" placeholder="Nhập các việc dự định thực hiện ngày mai"${editing ? ' required' : ''}>${esc(draft?.tomorrow)}</textarea></label>`;
    formDialog({ title: editing ? 'Chỉnh sửa Daily Standup' : 'Thêm ghi chú', detail: editing ? 'Nội dung cập nhật sẽ được lưu vào tác vụ này.' : 'Bạn có thể lưu từng phần khi có thông tin.', fields, submit: 'Lưu ghi chú',
      form: editing ? 'edit' : 'notes', value: task?.id ?? thread.id, buttons: button('Hủy', 'close') });
  }

  function scopeDialog() {
    const thread = activeThread();
    if (!thread) return;
    formDialog({ title: 'Phạm vi Outlook', detail: 'Chọn những email và thông tin bạn muốn tổng hợp.', fields: scopeFields(thread.scope ?? defaultScope), form: 'scope', value: thread.id, submit: 'Kiểm tra Outlook', buttons: button('Hủy', 'close') });
  }

  function showSchedule(task) {
    if (!task || !['pending', 'scheduled'].includes(task.status)) return;
    const proposed = task.at ?? (task.kind === 'standup' ? nextMorning(Date.now()) : getMail(task.mailId)?.due - 30 * 60_000);
    const date = Number.isFinite(proposed) ? proposed : Date.now() + 3_600_000;
    formDialog({ title: task.kind === 'standup' ? 'Đặt lịch nộp Standup' : 'Xác nhận lời nhắc', detail: task.title + ' · Giờ Việt Nam (UTC+7)',
      fields: `<div class="form-grid"><label>Ngày <input name="date" type="date" value="${dateInput(date)}" min="${dateInput(Date.now())}" required></label><label>Giờ <input name="time" type="time" value="${timeLabel(date)}" required></label></div><p class="field-error" role="alert"></p>`,
      form: 'schedule', value: task.id, buttons: button('Quay lại', 'close'), submit: task.status === 'scheduled' ? 'Lưu lịch mới' : 'Xác nhận lịch' });
  }

  function scheduleTask(task, form) {
    if (!task || !['pending', 'scheduled'].includes(task.status)) return;
    const at = Date.parse(`${form.get('date')}T${form.get('time')}:00+07:00`);
    const error = dialog.querySelector('.field-error');
    if (!Number.isFinite(at) || at <= Date.now()) {
      error.textContent = 'Vui lòng chọn thời điểm trong tương lai.';
      return;
    }
    if (task.kind === 'standup' && state.tasks.some((item) => item.id !== task.id && item.kind === 'standup' && item.at && dateInput(item.at) === dateInput(at) && ['scheduled', 'running', 'success', 'failed'].includes(item.status))) {
      error.textContent = 'Ngày này đã có lượt nộp Standup. Vui lòng quản lý tác vụ hiện có.';
      return;
    }
    const mail = task.kind === 'reminder' ? getMail(task.mailId) : null;
    if (mail?.due && at >= mail.due) {
      error.textContent = 'Chọn thời điểm nhắc trước thời gian diễn ra sự kiện.';
      return;
    }
    const updated = task.status === 'scheduled';
    task.at = at;
    task.status = 'scheduled';
    const thread = taskThread(task);
    const detail = `Đã ${updated ? 'cập nhật' : 'đặt'} lịch vào ${timeLabel(at)} ngày ${dateLabel(at)} theo giờ Việt Nam.`;
    if (thread) {
      if (task.kind === 'standup') thread.step = 'scheduled';
      addMessage(thread, 'agent', detail, { type: 'task', taskId: task.id });
    }
    log(state, updated ? 'Đã cập nhật lịch' : 'Đã đặt lịch', task.title + ' · ' + detail, task.id, task.threadId);
    closeDialog();
    flash(detail);
    render('new');
  }

  function cancelTask(task, manual = false) {
    if (!task || !['missing', 'pending', 'scheduled', 'failed'].includes(task.status)) return;
    task.status = 'cancelled';
    task.error = '';
    const thread = taskThread(task);
    const detail = task.kind === 'standup' ? 'Daily Standup sẽ không được agent tự động nộp.' : 'Lời nhắc đã được hủy.';
    if (thread) {
      if (task.kind === 'standup') thread.step = '';
      addMessage(thread, 'agent', manual ? 'Đã hủy tự động nộp. Bạn có thể chép bản nháp và tự nộp trên Phoenix khi sẵn sàng.' : detail, { type: 'task', taskId: task.id });
    }
    log(state, 'Đã hủy tác vụ', task.title + ' · ' + detail, task.id, task.threadId);
    closeDialog();
    flash('Đã hủy tác vụ.');
    render('new');
  }

  function runTask(task) {
    if (!['scheduled', 'failed'].includes(task.status)) return;
    task.status = 'running';
    task.attempts++;
    task.error = '';
    task.finishAt = Date.now() + 1150;
    log(state, 'Đang thực hiện tác vụ', task.title, task.id, task.threadId);
    render();
  }

  function tick() {
    const now = Date.now();
    let changed = false;
    for (const task of state.tasks) {
      if (task.status === 'scheduled' && task.at <= now) {
        runTask(task);
        changed = true;
      }
      if (task.status === 'running' && (task.finishAt ?? 0) <= now) {
        executeTask(state, task);
        changed = true;
      }
    }
    if (changed) {
      render('new');
      if (modal?.form === 'task-detail') showTask(getTask(modal.value));
    }
  }

  function showTask(task) {
    if (!task) return;
    formDialog({ title: 'Chi tiết tác vụ', form: 'task-detail', value: task.id, fields: taskCard(state, task), buttons: button('Mở cuộc trò chuyện', 'thread', { value: task.threadId, glyph: 'chat' }) });
  }

  function createReminder(thread, mail) {
    if (!mail?.due || mail.conflict || mail.due <= Date.now()) {
      addMessage(thread, 'agent', mail?.due && mail.due <= Date.now()
        ? 'Sự kiện này đã qua. Hãy chọn một lịch hẹn hoặc deadline sắp tới.'
        : 'Email chưa cung cấp thời điểm đã xác nhận để đặt lời nhắc. Hãy kiểm tra chuỗi thư hoặc hỏi người tổ chức.');
      render('new');
      return;
    }
    const existing = state.tasks.find((task) => task.kind === 'reminder' && task.mailId === mail.id && ['pending', 'scheduled', 'running', 'success'].includes(task.status));
    if (existing) {
      addMessage(thread, 'agent', 'Lời nhắc cho sự kiện này đã có trong Tác vụ.');
      render('new');
      showTask(existing);
      return;
    }
    const task = createTask(state, { kind: 'reminder', title: mail.event, status: 'pending', mailId: mail.id, threadId: thread.id });
    addMessage(thread, 'agent', 'Kiểm tra nội dung và chọn thời điểm bạn muốn nhận lời nhắc.', { type: 'task', taskId: task.id });
    thread.lastMail = mail.id;
    render('new');
    showSchedule(task);
  }

  function setComplete(threadKey, completed, threadId) {
    const mail = inbox(state.now, state.scenario).find((item) => item.thread === threadKey);
    if (!mail) return;
    state.completed[threadKey] = completed;
    log(state, completed ? 'Đã hoàn thành việc từ email' : 'Đã mở lại việc từ email', mail.action, '', threadId);
    flash(completed ? 'Đã đánh dấu hoàn thành.' : 'Đã mở lại công việc.');
  }

  function original(mailId) {
    const mail = getMail(mailId);
    if (!mail) return;
    if (state.page === 'chat' && activeThread()?.flow === 'outlook') {
      activeThread().lastMail = mail.id;
      persist();
    }
    formDialog({ title: mail.subject, detail: 'Outlook · Email gốc mô phỏng',
      fields: `<dl class="mail-original"><dt>Người gửi</dt><dd>${esc(mail.sender)} &lt;${esc(mail.address)}&gt;</dd><dt>Thời gian</dt><dd>${timeLabel(mail.received)} · ${dateLabel(mail.received)}</dd><dt>Trạng thái</dt><dd>${mail.unread ? 'Chưa đọc' : 'Đã đọc'}</dd></dl>
        <div class="original-body"><p>Chào Minh Anh,</p><p>${esc(mail.summary ?? mail.unavailable)}</p>${mail.action ? `<p>Nhờ bạn: ${esc(mail.action.toLowerCase())}.</p>` : ''}<p>Cảm ơn bạn,</p><p>${esc(mail.sender)}</p></div>`,
      buttons: button('Đóng', 'close') + button('Xem chuỗi thư', 'mail-thread', { value: mail.thread, glyph: 'chat' }) });
  }

  function mailThread(threadKey) {
    const mails = inbox(state.now, state.scenario).filter((mail) => mail.thread === threadKey);
    if (!mails.length) return;
    formDialog({ title: 'Chuỗi email liên quan', detail: 'Các email mới nhất được xếp trước.',
      fields: mails.map((mail) => `<div class="thread-preview"><strong>${esc(mail.subject)}</strong><small>${esc(mail.sender)} · ${timeLabel(mail.received)} · ${dateLabel(mail.received)}</small><p>${esc(mail.summary ?? mail.unavailable)}</p>${button('Mở email gốc', 'original', { value: mail.id, style: 'link-btn', tail: 'external' })}</div>`).join(''), buttons: button('Đóng', 'close') });
  }

  function showDemo() {
    const groups = ['Chung', 'Daily Standup', 'Outlook'];
    formDialog({ title: 'Chế độ demo', detail: 'Chọn kịch bản để mở một phiên mới với dữ liệu mẫu tương ứng.',
      fields: `<label>Kịch bản<select name="scenario">${groups.map((group) => `<optgroup label="${group}">${Object.entries(scenarios).filter(([, item]) => item.group === group).map(([key, item]) => `<option value="${key}"${key === state.scenario ? ' selected' : ''}>${esc(item.name)}</option>`).join('')}</optgroup>`).join('')}</select></label>
      <div class="callout info demo-description">${icon('beaker', 18)}<span>${esc(scenarios[state.scenario].description)}</span></div>`,
      form: 'demo', buttons: button('Đặt lại dữ liệu', 'confirm-reset', { glyph: 'refresh' }), submit: 'Bắt đầu kịch bản' });
  }

  function resetDemo(scenario, launch) {
    if (!Object.hasOwn(scenarios, scenario)) return;
    revision++;
    ui.loading.clear();
    ui.attachments.clear();
    ui.composers.clear();
    ui.busyFile.clear();
    ui.fileThread = '';
    for (const entry of ui.auth.values()) entry.popup?.close();
    ui.auth.clear();
    state = seed(scenario);
    closeDialog();
    navigate('dashboard');
    if (launch && scenario !== 'overview') startFlow(scenario.startsWith('outlook') ? 'outlook' : 'standup');
    flash('Đã nạp dữ liệu demo.');
  }

  function declinePlan(thread) {
    thread.step = 'collect';
    addMessage(thread, 'agent', 'Mình vẫn cần kế hoạch ngày mai để hoàn thành Daily Standup. Bạn có thể bổ sung sau.', { type: 'collect', taskId: thread.taskId });
    render('new');
  }

  async function attachFiles(input) {
    const thread = state.threads.find((item) => item.id === ui.fileThread);
    const files = [...input.files];
    input.value = '';
    ui.fileThread = '';
    if (!thread || !files.length || ui.busyFile.has(thread.id)) return;
    const existing = ui.attachments.get(thread.id) ?? [];
    const generation = revision;
    ui.busyFile.add(thread.id);
    const read = await Promise.all(files.map(async (file) => {
      const supported = /\.(txt|md|csv|json)$/i.test(file.name) || file.type.startsWith('text/');
      try {
        return { name: file.name, text: supported && file.size <= 500_000 ? (await file.text()).trim() : '' };
      } catch {
        return { name: file.name, text: '' };
      }
    }));
    if (generation !== revision) return;
    ui.busyFile.delete(thread.id);
    ui.attachments.set(thread.id, [...existing, ...read]);
    render();
  }

  function submitChat(form) {
    const thread = activeThread();
    if (!thread || ui.loading.has(thread.id) || ui.busyFile.has(thread.id)) return;
    const text = String(form.get('message') ?? '').trim();
    const files = ui.attachments.get(thread.id) ?? [];
    if (!text && !files.length) return;
    const display = [text, ...files.map((file) => 'Đính kèm: ' + file.name)].filter(Boolean).join('\n');
    const documents = files.filter((file) => file.text).map((file) => file.text).join('\n');
    ui.composers.delete(thread.id);
    ui.attachments.delete(thread.id);
    addMessage(thread, 'user', display);
    process(thread, text || (thread.flow === 'standup' ? 'Ghi chú Daily Standup' : ''), documents, files.filter((file) => !file.text).map((file) => file.name));
  }

  function submit(event) {
    const target = event.target;
    if (!target.matches('[data-form]')) return;
    event.preventDefault();
    const form = new FormData(target);
    if (target.dataset.form === 'chat') return submitChat(form);
    const { form: kind, value } = modal ?? {};
    if (kind === 'auth') return finishAuth(value);
    if (kind === 'demo') return resetDemo(form.get('scenario'), true);
    if (kind === 'reset') return resetDemo(state.scenario, false);
    if (kind === 'schedule') return scheduleTask(getTask(value), form);
    if (kind === 'scope') {
      const thread = state.threads.find((item) => item.id === value);
      if (!thread || ui.loading.has(thread.id)) return;
      const scope = { ...defaultScope, ...Object.fromEntries(form), unread: form.has('unread') };
      closeDialog();
      thread.flow = 'outlook';
      addMessage(thread, 'user', `Kiểm tra Outlook · ${scopeLabel(scope)}`);
      setBusy(thread, 'Đang kiểm tra Outlook…', () => runInbox(thread, scope));
      return;
    }
    if (kind === 'notes' || kind === 'edit') {
      const task = kind === 'edit' ? getTask(value) : null;
      const thread = task ? taskThread(task) : state.threads.find((item) => item.id === value);
      const notes = { yesterday: form.get('yesterday').trim(), tomorrow: form.get('tomorrow').trim() };
      if (!thread || !notes.yesterday && !notes.tomorrow) return;
      closeDialog();
      if (task && ['pending', 'scheduled'].includes(task.status)) {
        if (!notes.yesterday || !notes.tomorrow || noWork(notes.yesterday) || noPlanYet(notes.tomorrow)) {
          flash('Cần có nội dung cho cả hai phần.');
          return;
        }
        task.draft = { ...notes };
        thread.draft = { ...notes };
        log(state, 'Đã sửa nội dung Standup', task.title, task.id, task.threadId);
        flash('Đã lưu thay đổi.');
        render();
      } else if (!task) {
        const message = [notes.yesterday && `Hôm qua: ${notes.yesterday}`, notes.tomorrow && `Ngày mai: ${notes.tomorrow}`].filter(Boolean).join('\n');
        addMessage(thread, 'user', message);
        process(thread, `Ghi chú Daily Standup\n${message}`);
      }
    }
  }

  const actions = {
    nav: navigate,
    menu: () => { ui.menu = !ui.menu; render(); },
    new: () => { makeThread(); navigate('chat'); document.querySelector('#message-input')?.focus(); },
    thread: (value) => { closeDialog(); openThread(value); },
    start: (value) => startFlow(value),
    'start-here': (value, thread) => startFlow(value, thread),
    'dashboard-mail': () => {
      const thread = state.lastInbox?.threadId ?? state.threads.find((item) => item.flow === 'outlook' && item.messages.some((message) => message.card?.type === 'mail'))?.id;
      if (thread && state.accounts.outlook === 'connected') openThread(thread);
      else startFlow('outlook');
    },
    'task-filter': (value) => { state.filter = value; navigate('tasks'); },
    task: (value) => showTask(getTask(value)),
    'run-task': (value) => { const task = getTask(value); if (task) { closeDialog(); runTask(task); } },
    'retry-task': (value) => {
      const task = getTask(value);
      if (!task || task.status !== 'failed') return;
      closeDialog();
      if (task.kind === 'standup' && state.accounts.phoenix !== 'connected') auth('phoenix', task.id);
      else runTask(task);
    },
    'edit-draft': (value) => { const task = getTask(value); if (task) showNotes(task, true); },
    schedule: (value) => showSchedule(getTask(value)),
    'confirm-cancel': (value) => {
      const task = getTask(value);
      if (task) formDialog({ title: 'Hủy tác vụ này?', detail: task.title, fields: '<p>Tác vụ sẽ chuyển sang trạng thái Đã hủy.</p>', buttons: button('Quay lại', 'task', { value }) + button('Hủy tác vụ', 'cancel-task', { value, style: 'danger' }) });
    },
    'cancel-task': (value) => cancelTask(getTask(value)),
    manual: (value) => {
      const task = getTask(value);
      if (!task?.draft) return;
      formDialog({ title: 'Tự nộp Daily Standup', detail: 'Bạn có thể chép nội dung dưới đây để tự nộp trên Phoenix.', fields: `<textarea aria-label="Bản nháp để sao chép" readonly rows="7">${esc('Hôm qua:\n' + task.draft.yesterday + '\n\nNgày mai:\n' + task.draft.tomorrow)}</textarea><p><a href="https://portal-cohort5.edufun.ai/dashboard" target="_blank" rel="noopener noreferrer">Mở Phoenix ↗</a></p>`, buttons: button('Giữ bản nháp', 'task', { value }) + button('Chọn tự nộp', 'manual-confirm', { value, style: 'primary' }) });
    },
    'manual-confirm': (value) => cancelTask(getTask(value), true),
    notes: () => showNotes(),
    sample: (_, thread) => {
      if (!thread) return;
      addMessage(thread, 'user', 'Dùng ghi chú mẫu.');
      if (state.accounts.phoenix !== 'connected') {
        requireAuth(thread, 'phoenix', { flow: 'standup', text: `Hôm qua: ${sampleNotes.yesterday}\nNgày mai: ${sampleNotes.tomorrow}`, documents: '' });
        render('new');
        return;
      }
      collect(thread, { yesterday: thread.draft.yesterday || sampleNotes.yesterday, tomorrow: thread.draft.tomorrow || sampleNotes.tomorrow });
      render('new');
    },
    'no-yesterday': (_, thread) => { if (thread) { addMessage(thread, 'user', 'Hôm qua mình không có công việc nào.'); noYesterday(thread); render('new'); } },
    'no-plan': (_, thread) => { if (thread) { addMessage(thread, 'user', 'Mình chưa có kế hoạch ngày mai.'); noPlan(thread); render('new'); } },
    suggest: (_, thread) => { if (thread) { addMessage(thread, 'user', 'Mình muốn xem gợi ý.'); suggestPlan(thread); render('new'); } },
    'decline-plan': (_, thread) => { if (thread) { addMessage(thread, 'user', 'Mình sẽ bổ sung sau.'); declinePlan(thread); } },
    scope: scopeDialog,
    'retry-mail': (_, thread) => { if (thread) setBusy(thread, 'Đang thử đọc lại Outlook…', () => runInbox(thread, thread.scope)); },
    reminder: (value, thread) => { if (thread) createReminder(thread, getMail(value)); },
    original,
    'mail-thread': mailThread,
    auth,
    disconnect: (value) => {
      if (!Object.hasOwn(accounts, value)) return;
      state.accounts[value] = 'disconnected';
      flash(`Đã ngắt kết nối ${accounts[value].name}.`);
      render();
    },
    notification: (value) => {
      const note = state.notifications.find((item) => item.id === value);
      if (!note) return;
      note.read = true;
      if (note.threadId) openThread(note.threadId);
      else render();
      if (note.taskId) showTask(getTask(note.taskId));
    },
    'read-all': () => { state.notifications.forEach((note) => { note.read = true; }); render(); },
    activity: (value) => {
      const entry = state.activity.find((item) => item.id === value);
      if (entry?.threadId) openThread(entry.threadId);
      if (entry?.taskId) showTask(getTask(entry.taskId));
    },
    'pick-file': () => {
      if (!activeThread() || ui.busyFile.has(state.active)) return;
      ui.fileThread = state.active;
      document.querySelector('#file-input').click();
    },
    'remove-file': (value) => { ui.attachments.get(state.active)?.splice(Number(value), 1); render(); },
    demo: showDemo,
    'confirm-reset': () => formDialog({ title: 'Đặt lại dữ liệu demo?', detail: 'Cuộc trò chuyện, tác vụ và thông báo của phiên hiện tại sẽ được đặt lại.', fields: '', buttons: button('Quay lại', 'demo'), form: 'reset', submit: 'Đặt lại' }),
    close: closeDialog,
  };

  document.addEventListener('click', (event) => {
    const target = event.target.closest('button[data-action]');
    if (target && !target.disabled && Object.hasOwn(actions, target.dataset.action)) {
      const { action, value } = target.dataset;
      if (action === 'auth') auth(value);
      else actions[action](value, activeThread());
      return;
    }
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeDialog();
    }
  });
  document.addEventListener('input', (event) => {
    if (event.target.id === 'message-input') ui.composers.set(state.active, event.target.value);
  });
  document.addEventListener('change', (event) => {
    if (event.target.id === 'file-input') attachFiles(event.target);
    if (event.target.dataset.action === 'complete') {
      const { value } = event.target.dataset;
      setComplete(value, event.target.checked, state.active);
      for (const input of app.querySelectorAll('[data-action="complete"]')) {
        if (input.dataset.value === value) input.checked = event.target.checked;
      }
      persist();
    }
    if (modal?.form === 'demo' && event.target.name === 'scenario') {
      dialog.querySelector('.demo-description span').textContent = scenarios[event.target.value].description;
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.target.id === 'message-input' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      event.target.form.requestSubmit();
    }
  });
  document.addEventListener('submit', submit);
  dialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeDialog();
  });
  window.addEventListener('message', (event) => {
    if (event.origin !== location.origin || event.data?.type !== 'digitalboo-auth') return;
    const entry = ui.auth.get(event.data.name);
    if (entry && entry.popup === event.source && entry.key === event.data.key) finishAuth(entry.name);
  });
  setInterval(tick, 650);
  render('end');
}
