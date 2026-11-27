import { icon } from './icons.mjs';
import {
  accounts, dateLabel, defaultScope, fullDate, inbox, infoTypes, nextMorning,
  periods, priorities, readInbox, relative, scenarios, scopeLabel, taskStatus, timeLabel,
} from './mock.mjs';

export const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const attr = (action, value) => `data-action="${action}"${value == null ? '' : ` data-value="${esc(value)}"`}`;
export const button = (label, action, { value, glyph, style = 'secondary', tail, disabled, title } = {}) => `<button type="button" class="btn ${style}" ${attr(action, value)}${disabled ? ' disabled' : ''}${title ? ` title="${esc(title)}"` : ''}>${glyph ? icon(glyph, 17) : ''}<span>${esc(label)}</span>${tail ? icon(tail, 16) : ''}</button>`;
export const iconButton = (label, action, glyph, value) => `<button type="button" class="icon-btn" aria-label="${esc(label)}" title="${esc(label)}" ${attr(action, value)}>${icon(glyph)}</button>`;
export const pill = (label, color, dot = false) => `<span class="pill ${color}">${dot ? '<i></i>' : ''}${esc(label)}</span>`;
const tile = (glyph, tone = 'mint', size = 19) => `<span class="tile ${tone}">${icon(glyph, size)}</span>`;
const taskTitle = (task) => task.kind === 'standup' ? 'Daily Standup' : task.title;
const statusFor = (task) => task.kind === 'standup' && task.status === 'success' ? ['Nộp thành công', 'green']
  : task.kind === 'standup' && task.status === 'running' ? ['Đang nộp', 'blue']
  : task.kind === 'standup' && task.status === 'failed' ? ['Nộp thất bại', 'red'] : taskStatus[task.status];
const stamp = (date) => `${timeLabel(date)} · ${dateLabel(date)}`;
const avatar = (size = '') => `<span class="avatar ${size}" aria-hidden="true">MA</span>`;
export const logo = () => `<span class="logo-mark">${icon('spark', 22)}</span><span>digitalboo<span class="wordmark-dot">.</span></span>`;
const countUnread = (state) => state.notifications.filter((note) => !note.read).length;
const sectionHeading = (title, detail = '') => `<div class="section-title"><h2>${esc(title)}</h2>${detail ? `<p>${esc(detail)}</p>` : ''}</div>`;
const menuItems = [
  ['dashboard', 'grid', 'Tổng quan'], ['chat', 'chat', 'Trò chuyện'],
  ['tasks', 'calendar', 'Tác vụ'], ['notifications', 'bell', 'Thông báo'], ['settings', 'settings', 'Cài đặt'],
];
const pageNames = Object.fromEntries(menuItems.map(([key, , label]) => [key, label]));
const simpleEmpty = (glyph, title, detail, actions = '') => `<div class="empty">${tile(glyph, 'gray', 22)}<h3>${esc(title)}</h3><p>${esc(detail)}</p>${actions}</div>`;
const displayName = { connected: 'Đã kết nối', expired: 'Phiên hết hạn', disconnected: 'Chưa kết nối' };
const providerTone = (name) => name === 'phoenix' ? 'peach' : 'blue';

function shell(state, content, ui) {
  const unread = countUnread(state);
  return `<div class="shell">
    <aside class="sidebar ${ui.menu ? 'sidebar-open' : ''}" aria-label="Điều hướng">
      <button class="brand plain" ${attr('nav', 'dashboard')}>${logo()}</button>
      <div class="sidebar-main">
        ${button('Cuộc trò chuyện mới', 'new', { glyph: 'plus', style: 'new-chat' })}
        <div class="nav-label">KHÔNG GIAN LÀM VIỆC</div>
        <nav>${menuItems.map(([key, glyph, label]) => `<button class="nav-item ${state.page === key ? 'selected' : ''}" ${attr('nav', key)}${state.page === key ? ' aria-current="page"' : ''}>${icon(glyph, 19)}<span>${label}</span>${key === 'notifications' && unread ? `<small>${unread}</small>` : ''}</button>`).join('')}</nav>
        <div class="nav-label history-label">TRÒ CHUYỆN GẦN ĐÂY</div>
        <div class="history">${state.threads.slice(0, 12).map((thread) => `<button class="history-item ${state.page === 'chat' && state.active === thread.id ? 'selected' : ''}" ${attr('thread', thread.id)} title="${esc(thread.title)}">${icon('chat', 15)}<span>${esc(thread.title)}</span></button>`).join('') || '<p>Chưa có cuộc trò chuyện.</p>'}</div>
      </div>
      <div class="sidebar-bottom">
        <button class="demo-button" ${attr('demo')}>${tile('beaker', 'demo-tile', 17)}<span><strong>Chế độ demo</strong><small>${esc(scenarios[state.scenario].name)}</small></span>${icon('down', 15)}</button>
        <button class="profile plain" ${attr('nav', 'settings')}>${avatar()}<span><strong>Minh Anh</strong><small>Không gian cá nhân</small></span>${icon('chevron', 15)}</button>
      </div>
    </aside>
    ${ui.menu ? '<button type="button" data-action="menu" class="scrim" aria-label="Đóng điều hướng"></button>' : ''}
    <main class="main">
      <header class="topbar">
        <div class="breadcrumbs">${iconButton('Mở điều hướng', 'menu', 'menu')}<span class="breadcrumb-home">Không gian làm việc</span><span class="breadcrumb-home">${icon('chevron', 13)}</span><strong>${pageNames[state.page]}</strong></div>
        <div class="top-tools"><span class="demo-tag"><i></i>Dữ liệu mô phỏng</span><button class="top-bell icon-btn" ${attr('nav', 'notifications')} aria-label="${unread ? `${unread} thông báo chưa đọc` : 'Thông báo'}">${icon('bell', 20)}${unread ? '<i></i>' : ''}</button>${avatar('small')}</div>
      </header>
      ${content}
    </main>
  </div>`;
}

function connection(state, name, compact = false) {
  const account = accounts[name];
  const current = state.accounts[name];
  const status = pill(displayName[current], current === 'connected' ? 'green' : current === 'expired' ? 'amber' : 'gray', true);
  return `<div class="connection">${tile(account.icon, providerTone(name))}<div class="row-text"><strong>${account.name}</strong><small>${compact ? account.detail : account.address}</small></div>${status}${compact ? '' : current === 'connected' ? button('Ngắt kết nối', 'disconnect', { value: name, style: 'secondary' }) : button('Kết nối', 'auth', { value: name, glyph: 'link' })}</div>`;
}

const metric = (glyph, tone, title, number, caption, action, value, tag = '') => `<button class="metric panel" ${attr(action, value)}>${tile(glyph, tone)}<span class="metric-copy"><span class="metric-title">${title}</span><strong>${number}</strong><small>${caption}</small></span>${tag || `<span class="metric-arrow">${icon('arrow', 17)}</span>`}</button>`;

function dashboard(state) {
  const scope = state.lastInbox?.scope ?? (state.scenario === 'overview' ? defaultScope : null);
  const result = state.accounts.outlook === 'connected' && scope ? readInbox(state.now, state.scenario, scope) : null;
  const latestScope = result ? esc(scopeLabel(result.scope)) : '';
  const pending = state.tasks.filter((task) => task.status === 'pending');
  const standup = state.tasks.filter((task) => task.kind === 'standup' && task.status === 'scheduled')
    .sort((first, second) => first.at - second.at)[0];
  const displayedStandup = standup ?? state.tasks.find((task) => task.kind === 'standup');
  const predicted = standup?.at ?? nextMorning(state.now);
  const dayDisplay = dateLabel(predicted) === dateLabel(nextMorning(state.now)) ? 'Ngày mai' : dateLabel(predicted);
  return `<div class="content dashboard">
    <div class="welcome">
      <div><h1>Xin chào, Minh Anh<span class="greeting-dot">.</span></h1><p>Đây là những việc bạn cần chú ý hôm nay.</p></div>
      <span class="today">${icon('calendar', 16)}${esc(fullDate(state.now))}</span>
    </div>
    <section class="hero">
      <div class="hero-content">
        <div class="hero-kicker">${icon('spark', 16)} TRỢ LÝ CÔNG VIỆC</div>
        <h2>Bắt đầu cùng Digitalboo</h2>
        <p>Chuẩn bị Daily Standup và nắm bắt những việc<br class="hero-break"> quan trọng từ Outlook, ngay trong một cuộc trò chuyện.</p>
        <div class="hero-actions">${button('Chuẩn bị Standup', 'start', { value: 'standup', glyph: 'clipboard', style: 'hero-primary' })}${button('Tóm tắt Outlook', 'start', { value: 'outlook', glyph: 'mail', style: 'hero-secondary' })}</div>
      </div>
      <div class="hero-art" aria-hidden="true"><div class="orbit-grid"></div><div class="orbit orbit-a"></div><div class="orbit orbit-b"></div><div class="orbit orbit-c"></div><div class="orbit-axis"></div><div class="orbit-core">${icon('spark', 93)}</div><i class="satellite sat-a"></i><i class="satellite sat-b"></i><i class="satellite sat-c"></i><i class="satellite sat-d"></i><i class="satellite sat-e"></i></div>
    </section>
    <div class="metrics">
      ${metric('clipboard', 'mint', 'Daily Standup', standup ? timeLabel(predicted) : displayedStandup ? esc(statusFor(displayedStandup)[0]) : 'Chưa có bản nháp', standup ? `${dayDisplay}, ${dateLabel(predicted)} · Lịch nộp` : displayedStandup?.status === 'pending' ? `${dayDisplay}, ${dateLabel(predicted)} · Gợi ý ${timeLabel(predicted)}` : 'Chuẩn bị hoặc xem tác vụ', displayedStandup ? 'task' : 'start', displayedStandup?.id ?? 'standup')}
      ${metric('mail', 'blue', 'Email quan trọng', result?.important.length ?? '—', result ? latestScope : 'Chưa có lượt tổng hợp', 'start', 'outlook')}
      ${metric('clock', 'peach', 'Chờ xác nhận', pending.length, pending.length ? 'Tác vụ cần bạn duyệt' : 'Không có tác vụ chờ duyệt', 'task-filter', 'pending')}
    </div>
    <div class="dash-grid">
      <section class="panel dash-panel mail-panel">
        <div class="panel-heading">${sectionHeading('Email cần chú ý', result ? 'Từ Outlook · ' + scopeLabel(result.scope) : 'Cập nhật từ hộp thư Outlook')}${button('Xem tổng hợp', 'dashboard-mail', { style: 'link-btn', tail: 'arrow' })}</div>
        ${result?.important.length ? `<div class="mail-list">${result.important.map((mail) => `<button class="mail-row" ${attr('original', mail.id)}>${tile(mail.kind === 'deadline' ? 'clipboard' : mail.kind === 'meeting' ? 'calendar' : 'mail', mail.priority === 'urgent' ? 'peach' : mail.kind === 'meeting' ? 'violet' : 'blue', 18)}<span class="row-text"><strong>${esc(mail.subject)}</strong><small>${esc(mail.sender)} <b>·</b> ${timeLabel(mail.received)}</small></span>${pill(...priorities[mail.priority])}</button>`).join('')}</div>` : simpleEmpty('mail', result ? result.unavailable.length ? 'Chưa đủ dữ liệu để kết luận' : 'Chưa có email cần chú ý' : 'Chưa có bản tổng hợp', result ? 'Xem lượt tổng hợp để kiểm tra phạm vi và kết quả.' : 'Bắt đầu một lượt kiểm tra để xem các email cần chú ý.', button(result ? 'Xem kết quả' : 'Kiểm tra Outlook', 'dashboard-mail', { glyph: 'arrow' }))}
      </section>
      <section class="panel dash-panel agenda-panel">
        <div class="panel-heading">${sectionHeading('Sắp tới', 'Deadline và lịch hẹn')}${button('Xem tác vụ', 'nav', { value: 'tasks', style: 'link-btn', tail: 'arrow' })}</div>
        ${result?.events.length ? `<div class="agenda-list">${result.events.map((mail) => `<button class="agenda-row" ${attr('original', mail.id)}><span class="agenda-date ${mail.kind === 'meeting' ? 'violet' : 'peach'}"><strong>${dateLabel(mail.due).split('/')[0]}</strong><small>THG ${Number(dateLabel(mail.due).split('/')[1])}</small></span><span class="row-text"><strong>${esc(mail.event)}</strong><small>${timeLabel(mail.due)} <b>·</b> ${mail.kind === 'meeting' ? 'Lịch họp' : 'Deadline'}</small></span>${icon('chevron', 15)}</button>`).join('')}</div>` : simpleEmpty('calendar', 'Chưa có lịch sắp tới', 'Lịch hẹn và deadline sẽ xuất hiện sau khi tổng hợp Outlook.')}
      </section>
      <section class="panel dash-panel accounts-panel">
        <div class="panel-heading">${sectionHeading('Tài khoản kết nối', 'Quản lý quyền truy cập của trợ lý')}${button('Quản lý', 'nav', { value: 'settings', style: 'link-btn', tail: 'arrow' })}</div>
        <div class="connections">${Object.keys(accounts).map((name) => connection(state, name, true)).join('')}</div>
      </section>
      <section class="panel dash-panel"><div class="panel-heading">${sectionHeading('Cần bạn xác nhận', 'Xem lại trước khi đặt lịch')}${button('Xem tất cả', 'task-filter', { value: 'pending', style: 'link-btn', tail: 'arrow' })}</div>
        ${pending.length ? pending.slice(0, 3).map((task) => `<button class="agenda-row" ${attr('task', task.id)}>${tile(task.kind === 'standup' ? 'clipboard' : 'bell', 'mint')}<span class="row-text"><strong>${esc(taskTitle(task))}</strong><small>${task.kind === 'standup' ? 'Bản nháp đã sẵn sàng' : 'Chọn thời điểm nhận lời nhắc'}</small></span>${icon('chevron', 15)}</button>`).join('') : simpleEmpty('check', 'Bạn đã xem hết', 'Hiện không có tác vụ cần xác nhận.')}
      </section>
    </div>
  </div>`;
}

function taskButtons(state, task, location = 'card') {
  if (task.status === 'missing') return button('Bổ sung trong chat', 'thread', { value: task.threadId, glyph: 'chat' });
  if (task.status === 'pending') return [
    location === 'list' ? button('Xem bản nháp', 'task', { value: task.id, glyph: 'clipboard' }) : button(task.kind === 'standup' ? 'Xác nhận và đặt lịch' : 'Xác nhận lời nhắc', 'schedule', { value: task.id, glyph: 'calendar', style: 'primary' }),
    location === 'list' || task.kind !== 'standup' ? '' : button('Chỉnh sửa', 'edit-draft', { value: task.id, glyph: 'pencil' }),
    location === 'list' || task.kind !== 'standup' ? '' : button('Tự nộp thủ công', 'manual', { value: task.id, style: 'link-btn' }),
    button('Hủy', 'confirm-cancel', { value: task.id, style: 'text-btn' }),
  ].join('');
  if (task.status === 'scheduled') return [
    button('Chạy mô phỏng', 'run-task', { value: task.id, glyph: 'play', style: location === 'list' ? 'secondary' : 'primary' }),
    button('Sửa lịch', 'schedule', { value: task.id, glyph: 'pencil' }),
    location === 'list' || task.kind !== 'standup' ? '' : button('Sửa nội dung', 'edit-draft', { value: task.id, glyph: 'clipboard' }),
    button('Hủy', 'confirm-cancel', { value: task.id, style: 'text-btn' }),
  ].join('');
  if (task.status === 'failed') return button(state.accounts.phoenix !== 'connected' && task.kind === 'standup' ? 'Đăng nhập và thử lại' : 'Thử lại', 'retry-task', { value: task.id, glyph: 'refresh', style: 'primary' });
  return '';
}

export function taskCard(state, task, { preview = true } = {}) {
  if (!task) return '';
  const [status, color] = statusFor(task);
  return `<div class="chat-card task-card"><div class="card-head">${tile(task.kind === 'standup' ? 'clipboard' : 'bell', 'mint')}<div><h3>${task.kind === 'standup' && task.status === 'pending' ? 'Bản nháp Daily Standup' : esc(taskTitle(task))}</h3><p>${task.at ? esc(stamp(task.at) + ' · giờ Việt Nam') : task.kind === 'standup' ? 'Xem lại nội dung trước khi xác nhận' : 'Chọn thời điểm nhận lời nhắc'}</p></div>${pill(status, color, true)}</div>
  ${preview && task.draft?.yesterday && task.draft?.tomorrow && ['pending', 'scheduled', 'success', 'failed'].includes(task.status) ? `<div class="draft-grid"><div><h4>Việc đã làm hôm qua</h4><p>${esc(task.draft.yesterday)}</p></div><div><h4>Kế hoạch ngày mai</h4><p>${esc(task.draft.tomorrow)}</p></div></div>` : ''}
  ${task.error ? `<div class="callout error">${icon('alert', 17)}${esc(task.error)}</div>` : ''}
  ${task.status === 'running' ? '<div class="working"><i></i><i></i><i></i><span>Đang xử lý tác vụ…</span></div>' : ''}
  <div class="card-actions">${taskButtons(state, task)}</div></div>`;
}

function tasksPage(state) {
  const labels = { all: 'Tất cả', missing: 'Chờ bổ sung', pending: 'Chờ xác nhận', scheduled: 'Đã lên lịch', running: 'Đang xử lý', success: 'Hoàn thành', failed: 'Thất bại', cancelled: 'Đã hủy', activity: 'Lịch sử hoạt động' };
  const rows = state.tasks.filter((task) => state.filter === 'all' || task.status === state.filter);
  return `<div class="content page-content"><div class="welcome"><div><h1>Tác vụ</h1><p>Quản lý Daily Standup và lời nhắc từ email.</p></div>${button('Chuẩn bị Standup', 'start', { value: 'standup', glyph: 'plus', style: 'primary' })}</div>
    <div class="tabs" role="group" aria-label="Lọc tác vụ">${Object.entries(labels).map(([key, label]) => `<button ${attr('task-filter', key)} aria-pressed="${state.filter === key}" class="${state.filter === key ? 'on' : ''}">${label}</button>`).join('')}</div>
    <section class="panel list-panel">${state.filter === 'activity'
      ? state.activity.map((item) => `<button class="notice-row" ${attr('activity', item.id)}>${tile('activity', 'mint')}<span class="row-text"><strong>${esc(item.title)}</strong><small>${esc(item.detail)}</small></span><time>${stamp(item.time)}</time>${icon('chevron', 16)}</button>`).join('') || simpleEmpty('activity', 'Chưa có hoạt động', 'Hoạt động của Digitalboo sẽ hiện ở đây.')
      : rows.map((task) => `<article class="task-row"><button class="task-open" ${attr('task', task.id)}>${tile(task.kind === 'standup' ? 'clipboard' : 'bell', task.kind === 'standup' ? 'mint' : 'violet')}<span class="row-text"><strong>${esc(taskTitle(task))}</strong><small>${task.at ? stamp(task.at) + ' · giờ Việt Nam' : task.kind === 'standup' ? 'Daily Standup' : 'Lời nhắc Outlook'}</small></span></button>${pill(...statusFor(task), true)}<div class="task-row-actions">${taskButtons(state, task, 'list')}</div></article>`).join('') || simpleEmpty('calendar', 'Chưa có tác vụ ở trạng thái này', 'Bạn có thể tạo bản nháp từ chat hoặc đặt lời nhắc từ email.')}</section>
  </div>`;
}

function noticesPage(state) {
  return `<div class="content page-content"><div class="welcome"><div><h1>Thông báo</h1><p>Theo dõi kết quả và phản hồi cho các tác vụ của bạn.</p></div>${button('Đánh dấu tất cả đã đọc', 'read-all', { glyph: 'check', disabled: !countUnread(state) })}</div>
    <section class="panel list-panel">${state.notifications.map((note) => `<button class="notice-row ${note.read ? '' : 'unread'}" ${attr('notification', note.id)}>${tile(note.tone === 'error' ? 'alert' : note.tone === 'success' ? 'check' : 'bell', note.tone === 'error' ? 'peach' : note.tone === 'success' ? 'mint' : 'blue')}<span class="row-text"><strong>${esc(note.title)}</strong><small>${esc(note.detail)}</small></span><time>${stamp(note.time)}</time>${note.read ? '' : '<i class="unread-dot"></i>'}${icon('chevron', 16)}</button>`).join('') || simpleEmpty('bell', 'Bạn chưa có thông báo', 'Kết quả tác vụ và cập nhật quan trọng sẽ xuất hiện tại đây.')}</section></div>`;
}

function settingsPage(state) {
  return `<div class="content page-content"><div class="welcome"><div><h1>Cài đặt</h1><p>Quản lý tài khoản kết nối và dữ liệu demo.</p></div></div>
    <section class="panel settings-panel"><div class="panel-heading">${sectionHeading('Tài khoản kết nối', 'Phoenix dùng để mô phỏng nộp Standup. Outlook chỉ được cấp quyền đọc.')}</div><div class="connections">${Object.keys(accounts).map((name) => connection(state, name)).join('')}</div></section>
    <section class="panel settings-panel"><div class="panel-heading">${sectionHeading('Chế độ demo', scenarios[state.scenario].description)}${button('Đổi kịch bản', 'demo', { glyph: 'beaker' })}</div></section>
  </div>`;
}

function emailCard(mail) {
  return `<article class="email-card"><div class="email-head">${tile('mail', mail.priority === 'urgent' ? 'peach' : 'blue', 17)}<div class="row-text"><strong>${esc(mail.subject)}</strong><small>${esc(mail.sender)} · ${stamp(mail.received)}</small></div>${pill(...priorities[mail.priority])}</div>
  <p>${esc(mail.summary)}</p>${mail.reason ? `<p class="email-meta"><strong>Vì sao đáng chú ý</strong> ${esc(mail.reason)}</p>` : ''}${mail.action ? `<p class="email-meta"><strong>Việc đề xuất</strong> ${esc(mail.action)}</p>` : ''}<div class="card-actions">${button('Mở email gốc', 'original', { value: mail.id, style: 'link-btn', tail: 'external' })}${mail.threadMails.length > 1 ? button(`Xem chuỗi thư (${mail.threadMails.length})`, 'mail-thread', { value: mail.thread, style: 'link-btn' }) : ''}</div></article>`;
}

function emailResult(state, scope) {
  const result = readInbox(state.now, state.scenario, scope);
  const incomplete = result.unavailable.length > 0;
  const listing = scope.priority === 'all' ? result.important : result.relevant;
  const stats = [
    [result.analyzed, 'Email đã phân tích'], [result.important.length, 'Email quan trọng'],
    [result.actions.length, 'Việc cần làm'], [result.events.length, 'Deadline / lịch hẹn'],
  ];
  return `<div class="mail-result">
    <div class="chat-card"><div class="card-head">${tile('mail', 'blue')}<div><h3>Tổng hợp Outlook</h3><p>${esc(scopeLabel(scope))}</p></div>${button('Bộ lọc', 'scope', { glyph: 'filter' })}</div><div class="report-stats">${stats.map(([number, label]) => `<div><strong>${number}</strong><span>${label}</span></div>`).join('')}</div></div>
    ${incomplete ? `<div class="callout warning"><div>${icon('alert', 17)} <strong>Chỉ phân tích được một phần</strong><ul>${result.unavailable.map((mail) => `<li>${esc(mail.subject)}. ${esc(mail.unavailable)}</li>`).join('')}</ul></div></div>` : ''}
    ${!result.analyzed && !incomplete ? simpleEmpty('inbox', 'Không có email trong phạm vi đã chọn', 'Outlook đã được kiểm tra thành công.', button('Đổi phạm vi', 'scope', { glyph: 'filter' })) : ''}
    ${result.analyzed && !listing.length && !incomplete ? simpleEmpty('mail', scope.priority === 'all' && scope.type === 'all' ? 'Không có email quan trọng' : 'Không có kết quả khớp bộ lọc', scope.priority === 'all' && scope.type === 'all' ? 'Có email mới, nhưng chưa phát hiện nội dung cần bạn ưu tiên.' : 'Điều chỉnh phạm vi hoặc xem tất cả nội dung.', button('Đổi bộ lọc', 'scope', { glyph: 'filter' })) : ''}
    ${listing.length && scope.type !== 'actions' ? `<div class="report-section"><h3>${scope.priority === 'all' ? 'Email cần chú ý' : 'Email theo mức độ ưu tiên'}</h3>${listing.map(emailCard).join('')}</div>` : ''}
    ${result.relevant.filter((mail) => mail.conflict).map((mail) => `<div class="callout warning"><div><strong>Giờ hẹn chưa được xác nhận</strong><p>${esc(mail.event)}. Chuỗi thư đề cập ${mail.threadMails.map((item) => esc(stamp(item.due))).join(' và ')}. Hãy xác nhận với người tổ chức.</p>${button('Xem chuỗi thư', 'mail-thread', { value: mail.thread, style: 'link-btn' })}</div></div>`).join('')}
    ${result.events.length && scope.type !== 'actions' ? `<div class="report-section chat-card"><h3>Deadline và lịch hẹn</h3><div class="table-wrap"><table><thead><tr><th>Sự kiện</th><th>Thời điểm</th><th>Lời nhắc</th></tr></thead><tbody>${result.events.map((mail) => {
      const task = state.tasks.find((item) => item.kind === 'reminder' && item.mailId === mail.id && ['scheduled', 'running', 'success', 'pending'].includes(item.status));
      return `<tr><td><strong>${esc(mail.event)}</strong>${button('Email nguồn', 'original', { value: mail.id, style: 'link-btn', tail: 'external' })}</td><td>${stamp(mail.due)}<small>${relative(mail.due, state.now)}</small></td><td>${task ? button(statusFor(task)[0], 'task', { value: task.id, style: 'link-btn' }) : button('Đặt nhắc', 'reminder', { value: mail.id, glyph: 'bell' })}</td></tr>`;
    }).join('')}</tbody></table></div></div>` : ''}
    ${result.actions.length ? `<div class="report-section chat-card"><h3>Việc cần làm</h3>${result.actions.map((mail) => `<div class="action-row"><label><input type="checkbox" data-action="complete" data-value="${esc(mail.thread)}"${state.completed[mail.thread] ? ' checked' : ''}><span><strong>${esc(mail.action)}</strong><small>${mail.conflict ? 'Giờ hẹn chưa xác định' : mail.due ? stamp(mail.due) : 'Email chưa nêu thời hạn'}</small></span></label>${pill(...priorities[mail.priority])}${button('Email nguồn', 'original', { value: mail.id, style: 'link-btn', tail: 'external' })}</div>`).join('')}</div>` : ''}
  </div>`;
}

function messageCard(state, thread, card) {
  if (!card) return '';
  const task = state.tasks.find((item) => item.id === card.taskId);
  const latestFlowCard = thread.messages.findLast((message) => message.card);
  const current = latestFlowCard?.card === card;
  switch (card.type) {
    case 'choices': return current ? `<div class="card-actions">${button('Daily Standup', 'start-here', { value: 'standup', glyph: 'clipboard' })}${button('Tổng hợp Outlook', 'start-here', { value: 'outlook', glyph: 'mail' })}</div>` : '';
    case 'auth': return current && state.accounts[card.name] !== 'connected' ? `<div class="chat-card"><div class="card-head">${tile(accounts[card.name].icon, providerTone(card.name))}<div><h3>Kết nối ${accounts[card.name].name}</h3><p>${card.name === 'outlook' ? 'Cấp quyền đọc email trong cửa sổ riêng' : 'Đăng nhập trong cửa sổ Phoenix mô phỏng'}</p></div></div>${button(card.name === 'outlook' ? 'Kết nối Microsoft' : 'Đăng nhập Phoenix', 'auth', { value: card.name, style: 'primary', tail: 'external' })}</div>` : '';
    case 'collect': return current && task?.status === 'missing' ? `<div class="chat-card"><div class="card-head">${tile('note', 'mint')}<div><h3>Ghi chú Daily Standup</h3><p>${thread.draft.yesterday ? 'Đã có việc hôm qua' : 'Cần việc đã làm hôm qua'} · ${thread.draft.tomorrow ? 'Đã có kế hoạch ngày mai' : 'Cần kế hoạch ngày mai'}</p></div></div><div class="card-actions">${button('Nhập ghi chú', 'notes', { glyph: 'note', style: 'primary' })}${button('Dùng ghi chú mẫu', 'sample', { glyph: 'spark' })}${!thread.draft.yesterday ? button('Hôm qua không có việc', 'no-yesterday', { style: 'text-btn' }) : ''}${!thread.draft.tomorrow ? button('Chưa có kế hoạch ngày mai', 'no-plan', { style: 'text-btn' }) : ''}</div></div>` : '';
    case 'suggest': return current && task?.status === 'missing' ? `<div class="card-actions">${button('Gợi ý từ công việc hôm qua', 'suggest', { glyph: 'spark', style: 'primary' })}${button('Tôi sẽ bổ sung sau', 'decline-plan', { style: 'text-btn' })}</div>` : '';
    case 'draft':
    case 'task': return thread.messages.findLast((message) => message.card?.taskId === card.taskId && ['draft', 'task'].includes(message.card.type))?.card === card ? taskCard(state, task) : '';
    case 'mail': return current ? emailResult(state, card.scope) : `<details class="archived-result"><summary>Xem lượt tổng hợp · ${esc(scopeLabel(card.scope))}</summary>${emailResult(state, card.scope)}</details>`;
    case 'mail-error': return `<div class="callout error">${icon('alert', 17)}<span>Không thể kiểm tra Outlook do lỗi mạng. Chưa xác định được có email quan trọng hay không.</span>${current ? button('Thử lại', 'retry-mail', { glyph: 'refresh' }) : ''}</div>`;
    case 'mail-detail': {
      const mail = inbox(state.now, state.scenario).find((item) => item.id === card.mailId);
      return mail ? emailCard({ ...mail, threadMails: inbox(state.now, state.scenario).filter((item) => item.thread === mail.thread) }) : '';
    }
    default: return '';
  }
}

function chatPage(state, ui) {
  const thread = state.threads.find((item) => item.id === state.active);
  const busy = thread && ui.loading.has(thread.id);
  const items = thread?.messages ?? [];
  const attachments = ui.attachments.get(state.active) ?? [];
  const title = thread?.title || 'Trò chuyện mới';
  return `<div class="chat-page">
    <div class="chat-top"><div>${tile('spark', 'mint')}<div><h1>${esc(title)}</h1><p>${busy ? 'Agent đang xử lý…' : 'Trợ lý Digitalboo'}</p></div></div>${thread?.flow === 'outlook' ? button('Phạm vi Outlook', 'scope', { glyph: 'filter' }) : ''}</div>
    <div class="chat-scroll" id="chat-scroll" aria-label="Nội dung trò chuyện"><div class="chat-log">
      ${items.length ? items.map((message) => message.role === 'user'
        ? `<div class="message user"><div>${message.text ? `<div class="bubble">${esc(message.text)}</div>` : ''}</div>${avatar('small')}</div>`
        : `<div class="message agent">${tile('spark', 'agent-mark', 19)}<div class="message-content"><div class="message-author">Digitalboo</div>${message.text ? `<p class="agent-text">${esc(message.text)}</p>` : ''}${messageCard(state, thread, message.card)}</div></div>`).join('')
        : `<div class="chat-empty">${tile('spark', 'agent-mark', 26)}<h2>Mình có thể giúp gì cho bạn?</h2><p>Chuẩn bị Daily Standup hoặc xem các việc quan trọng từ Outlook.</p><div class="card-actions">${button('Chuẩn bị Standup', 'start-here', { value: 'standup', glyph: 'clipboard' })}${button('Tóm tắt Outlook', 'start-here', { value: 'outlook', glyph: 'mail' })}</div></div>`}
      ${busy ? `<div class="message agent">${tile('spark', 'agent-mark', 19)}<div class="working" role="status"><i></i><i></i><i></i><span>${esc(busy)}</span></div></div>` : ''}
    </div></div>
    <div class="composer-wrap"><form class="composer" data-form="chat">
      ${attachments.length ? `<div class="attachments">${attachments.map((file, i) => `<span>${icon('attach', 15)}${esc(file.name)}${iconButton(`Gỡ ${file.name}`, 'remove-file', 'close', i)}</span>`).join('')}</div>` : ''}
      <textarea name="message" id="message-input" rows="2" aria-label="Yêu cầu gửi Digitalboo" placeholder="Nhắn Digitalboo…" ${busy ? 'disabled' : ''}>${esc(ui.composers.get(state.active) ?? '')}</textarea>
      <div class="composer-controls"><div>${iconButton('Đính kèm tài liệu', 'pick-file', 'attach')}${iconButton('Thêm ghi chú', 'notes', 'note')}</div><button type="submit" class="send-btn" aria-label="Gửi yêu cầu" ${busy ? 'disabled' : ''}>${icon('send', 20)}</button></div>
    </form><p class="composer-help">Dữ liệu mô phỏng · Tác vụ cần bạn xác nhận trước khi lên lịch.</p></div>
  </div>`;
}

export function renderApp(state, ui) {
  const pages = { dashboard, chat: chatPage, tasks: tasksPage, notifications: noticesPage, settings: settingsPage };
  return shell(state, pages[state.page](state, ui), ui);
}

export const select = (name, values, current, label) => `<label>${esc(label)}<select name="${name}">${Object.entries(values).map(([key, value]) => `<option value="${esc(key)}"${key === current ? ' selected' : ''}>${esc(value)}</option>`).join('')}</select></label>`;
export function scopeFields(scope = defaultScope) {
  return `<div class="form-grid">${select('period', { ...periods, ...(!periods[scope.period] ? { [scope.period]: `${parseInt(scope.period, 10)} ngày gần nhất` } : {}) }, scope.period, 'Khoảng thời gian nhận thư')}${select('type', infoTypes, scope.type, 'Loại thông tin')}${select('priority', { all: 'Tất cả mức độ', ...Object.fromEntries(Object.entries(priorities).map(([key, value]) => [key, value[0]])) }, scope.priority, 'Mức độ ưu tiên')}${select('eventDay', { '': 'Mọi thời điểm', tomorrow: 'Ngày mai', week: 'Tuần này' }, scope.eventDay, 'Thời điểm sự kiện')}<label>Người gửi<input name="sender" value="${esc(scope.sender)}" placeholder="Tên hoặc email"></label><label>Chủ đề<input name="topic" value="${esc(scope.topic)}" placeholder="Ví dụ: Sprint Review"></label></div><label class="check-control"><input type="checkbox" name="unread"${scope.unread ? ' checked' : ''}> Chỉ email chưa đọc</label>`;
}
