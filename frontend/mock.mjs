export const ZONE = 'Asia/Ho_Chi_Minh';
const HOUR = 3_600_000;
const DAY = 24 * HOUR;
export const id = () => globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
export const normalize = (value = '') => value.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').replace(/đ/g, 'd');
const formatter = (options) => new Intl.DateTimeFormat('vi-VN', { timeZone: ZONE, ...options });
export const timeLabel = (date) => formatter({ hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date);
const isoDate = formatter({ year: 'numeric', month: '2-digit', day: '2-digit' });
export const dateInput = (date) => {
  const { year, month, day } = Object.fromEntries(isoDate.formatToParts(date).map(({ type, value }) => [type, value]));
  return `${year}-${month}-${day}`;
};
export const dateLabel = (date) => dateInput(date).split('-').slice(1).reverse().join('/');
export const fullDate = (date) => formatter({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(date);
export const at = (date, time) => Date.parse(`${dateInput(date)}T${time}:00+07:00`);
export const nextMorning = (now) => at(now + DAY, '08:30');
export const relative = (date, now) => {
  const minutes = Math.ceil((date - now) / 60_000);
  if (minutes <= 0) return 'Đã qua';
  if (minutes < 60) return `Còn ${minutes} phút`;
  if (minutes < 24 * 60) return `Còn ${Math.ceil(minutes / 60)} giờ`;
  return `Còn ${Math.ceil(minutes / (24 * 60))} ngày`;
};

export const accounts = {
  phoenix: { name: 'Phoenix', detail: 'Cổng Daily Standup', address: 'portal-cohort5.edufun.ai', icon: 'flame' },
  outlook: { name: 'Outlook', detail: 'Hộp thư Microsoft', address: 'minh.anh@example.com', icon: 'mail' },
};

export const scenarios = {
  overview: { name: 'Tổng quan', group: 'Chung', description: 'Dashboard có sẵn email, bản nháp và lịch sắp tới.' },
  standup: { name: 'Standup · Thành công', group: 'Daily Standup', description: 'Dùng ghi chú mẫu, duyệt bản nháp, đặt lịch và mô phỏng nộp.' },
  standupMissing: { name: 'Standup · Thiếu thông tin', group: 'Daily Standup', description: 'Bổ sung việc hôm qua và chọn cách lập kế hoạch ngày mai.' },
  phoenixExpired: { name: 'Standup · Phiên hết hạn', group: 'Daily Standup', description: 'Mở cửa sổ đăng nhập mô phỏng và tiếp tục đúng bước đang dở.' },
  standupNetwork: { name: 'Standup · Lỗi mạng', group: 'Daily Standup', description: 'Lần nộp đầu thất bại, lần thử lại thành công.' },
  standupSite: { name: 'Standup · Lỗi Phoenix', group: 'Daily Standup', description: 'Phoenix báo lỗi khi nộp lần đầu. Có thể thử lại.' },
  standupSession: { name: 'Standup · Phiên hết hạn khi nộp', group: 'Daily Standup', description: 'Nhận thông báo, đăng nhập lại và tiếp tục lần nộp.' },
  standupUnknown: { name: 'Standup · Lỗi chưa xác định', group: 'Daily Standup', description: 'Lần nộp đầu thất bại với lỗi chưa xác định.' },
  outlook: { name: 'Outlook · Thành công', group: 'Outlook', description: 'Tổng hợp email, công việc, deadline và lịch hẹn.' },
  outlookExpired: { name: 'Outlook · Phiên hết hạn', group: 'Outlook', description: 'Kết nối lại Microsoft rồi tự động tiếp tục phạm vi đã chọn.' },
  outlookEmpty: { name: 'Outlook · Không có email mới', group: 'Outlook', description: 'Truy xuất thành công và trả về hộp thư trống trong phạm vi.' },
  outlookQuiet: { name: 'Outlook · Không có email quan trọng', group: 'Outlook', description: 'Có thư mới nhưng chưa phát hiện mục cần ưu tiên.' },
  outlookUnclear: { name: 'Outlook · Thiếu hạn và mâu thuẫn', group: 'Outlook', description: 'Giữ nguyên hạn chưa rõ và nêu hai thời điểm chưa được xác nhận.' },
  outlookPartial: { name: 'Outlook · Phân tích một phần', group: 'Outlook', description: 'Vẫn hiển thị kết quả đọc được khi một email hoặc tệp gặp lỗi.' },
  outlookError: { name: 'Outlook · Lỗi truy xuất', group: 'Outlook', description: 'Lần đọc đầu gặp lỗi mạng. Có thể thử lại trong chat.' },
};

export const taskStatus = {
  missing: ['Chờ bổ sung', 'amber'], pending: ['Chờ xác nhận', 'blue'],
  scheduled: ['Đã lên lịch', 'green'], running: ['Đang thực hiện', 'blue'],
  success: ['Hoàn thành', 'green'], failed: ['Thất bại', 'red'], cancelled: ['Đã hủy', 'gray'],
};
export const priorities = {
  urgent: ['Khẩn cấp', 'red'], important: ['Quan trọng', 'amber'],
  info: ['Thông tin', 'blue'], low: ['Không quan trọng', 'gray'],
};
export const sampleNotes = {
  yesterday: 'Hoàn thiện giao diện danh sách tác vụ.\nKiểm tra luồng đăng nhập và ghi lại 2 lỗi cần xử lý.',
  tomorrow: 'Sửa các lỗi đăng nhập đã ghi nhận.\nChạy lại bản demo và cập nhật checklist bàn giao.',
};
const failReasons = {
  standupNetwork: 'Mất kết nối mạng khi gửi bản Daily Standup.',
  standupSite: 'Phoenix trả về lỗi trong lúc tiếp nhận bản Daily Standup.',
  standupSession: 'Phiên đăng nhập Phoenix đã hết hạn khi bắt đầu nộp.',
  standupUnknown: 'Không xác định được kết quả nộp trong mô phỏng.',
};
const overdue = (now, days, time) => at(now + days * DAY, time);

export function inbox(now, scenario) {
  const rows = [
    { id: 'review', thread: 'review', subject: 'Cập nhật hạn gửi tài liệu Sprint Review', sender: 'Linh Nguyễn', address: 'linh@example.com', minutes: 40, unread: true, priority: 'urgent', summary: 'Hạn gửi slide và đường dẫn demo đã được dời sang ' + timeLabel(overdue(now, 1, '16:00')) + ' ngày ' + dateLabel(overdue(now, 1, '16:00')) + '.', reason: 'Hạn bàn giao đã đổi và cần gửi đủ hai tài liệu.', action: 'Gửi slide và đường dẫn demo', kind: 'deadline', event: 'Hạn gửi tài liệu Sprint Review', due: overdue(now, 1, '16:00') },
    { id: 'sync', thread: 'sync', subject: 'Lịch họp đồng bộ dự án', sender: 'Hoàng Trần', address: 'hoang@example.com', minutes: 115, unread: true, priority: 'important', summary: 'Nhóm sẽ rà lại tiến độ và các phần đang vướng trong buổi họp ' + timeLabel(overdue(now, 1, '10:00')) + ' ngày ' + dateLabel(overdue(now, 1, '10:00')) + '.', reason: 'Thư mời yêu cầu xác nhận có tham gia buổi họp.', action: 'Xác nhận tham gia cuộc họp', kind: 'meeting', event: 'Họp đồng bộ dự án', due: overdue(now, 1, '10:00'), reply: true },
    { id: 'figma', thread: 'figma', subject: 'Nhờ xác nhận quyền truy cập Figma', sender: 'Vy Phạm', address: 'vy@example.com', minutes: 200, unread: true, priority: 'important', summary: 'Vy cần bạn xác nhận đã mở được file thiết kế của nhóm. Email chưa ghi thời hạn phản hồi.', reason: 'Nhóm thiết kế cần xác nhận để bàn giao.', action: 'Xác nhận đã mở được file thiết kế', reply: true, noDeadline: true },
    { id: 'review-old', thread: 'review', subject: 'Lịch gửi tài liệu Sprint Review', sender: 'Linh Nguyễn', address: 'linh@example.com', minutes: 315, unread: false, priority: 'urgent', summary: 'Thông báo ban đầu yêu cầu gửi slide và demo trước ' + timeLabel(overdue(now, 2, '17:00')) + ' ngày ' + dateLabel(overdue(now, 2, '17:00')) + '.', reason: 'Có thời hạn bàn giao.', action: 'Gửi slide và đường dẫn demo', kind: 'deadline', event: 'Hạn gửi tài liệu Sprint Review', due: overdue(now, 2, '17:00') },
    { id: 'retro', thread: 'retro', subject: 'Ghi chú buổi retrospective', sender: 'Khánh Lê', address: 'khanh@example.com', minutes: 440, unread: false, priority: 'info', summary: 'Tổng hợp các ý kiến về cách chia việc trong sprint vừa qua.' },
    { id: 'release', thread: 'release', subject: 'Bản tin cập nhật công cụ tháng này', sender: 'Bản tin Sản phẩm', address: 'news@example.com', minutes: 600, unread: true, priority: 'low', summary: 'Bản tin giới thiệu các tính năng mới trong bộ công cụ cộng tác.' },
    { id: 'document', thread: 'document', subject: 'Tài liệu giới thiệu API nội bộ', sender: 'Nam Đỗ', address: 'nam@example.com', minutes: 1660, unread: false, priority: 'info', summary: 'Tài liệu tham khảo về định dạng dữ liệu của API nội bộ.' },
  ];
  const conflict = [
    { id: 'handoff-a', thread: 'handoff', subject: 'Trao đổi giờ demo bàn giao', sender: 'Hoàng Trần', address: 'hoang@example.com', minutes: 95, unread: true, priority: 'important', summary: 'Hoàng đề xuất bàn giao lúc 09:30 ngày ' + dateLabel(now + DAY) + '.', kind: 'meeting', event: 'Demo bàn giao', due: overdue(now, 1, '09:30'), conflict: true },
    { id: 'handoff-b', thread: 'handoff', subject: 'Re: Trao đổi giờ demo bàn giao', sender: 'Vy Phạm', address: 'vy@example.com', minutes: 45, unread: true, priority: 'important', summary: 'Vy ghi lịch lúc 14:00 ngày ' + dateLabel(now + DAY) + '. Chuỗi email chưa có xác nhận của người tổ chức.', reason: 'Hai email đề cập hai thời điểm khác nhau.', action: 'Xác nhận giờ demo với người tổ chức', kind: 'meeting', event: 'Demo bàn giao', due: overdue(now, 1, '14:00'), conflict: true, reply: true },
  ];
  const dataset = {
    outlookEmpty: [],
    outlookQuiet: rows.filter((row) => ['info', 'low'].includes(row.priority)),
    outlookUnclear: [rows[2], ...conflict],
    outlookPartial: [...rows, {
      id: 'locked', thread: 'locked', subject: 'File bàn giao tuần này', sender: 'Nam Đỗ', address: 'nam@example.com',
      minutes: 20, unread: true, unavailable: 'Không thể mở tài liệu đính kèm do tệp được bảo vệ.',
    }, {
      id: 'unreadable', thread: 'unreadable', subject: 'Cập nhật từ nhóm vận hành', sender: 'Khánh Lê', address: 'khanh@example.com',
      minutes: 50, unread: true, unavailable: 'Nội dung email không thể truy xuất trong lượt đọc này.',
    }],
  };
  return (dataset[scenario] ?? rows)
    .map((row) => ({ ...row, received: now - row.minutes * 60_000 }))
    .sort((first, second) => second.received - first.received);
}

export const defaultScope = { period: '24h', sender: '', topic: '', type: 'all', unread: false, eventDay: '', priority: 'all' };
export const periods = { '24h': '24 giờ gần nhất', today: 'Hôm nay', yesterday: 'Hôm qua', '3d': '3 ngày gần nhất', '7d': '7 ngày gần nhất', week: 'Tuần này' };
export const infoTypes = { all: 'Tất cả nội dung', deadlines: 'Deadline', meetings: 'Lịch hẹn', actions: 'Việc cần làm', replies: 'Cần phản hồi' };
const startOfWeek = (now) => {
  const weekday = new Date(at(now, '12:00') + 7 * HOUR).getUTCDay();
  return at(now - ((weekday + 6) % 7) * DAY, '00:00');
};
const bounds = (now, period) => {
  if (period === 'today') return [at(now, '00:00'), now];
  if (period === 'yesterday') return [at(now - DAY, '00:00'), at(now, '00:00') - 1];
  if (period === 'week') return [startOfWeek(now), now];
  const days = /^([1-9][0-9]*)d$/.exec(period);
  return [now - (days ? Number(days[1]) * DAY : DAY), now];
};
export const scopeLabel = (scope) => [
  periods[scope.period] ?? `${parseInt(scope.period, 10)} ngày gần nhất`,
  scope.unread && 'Thư chưa đọc', scope.sender && `Từ ${scope.sender}`, scope.topic && `Chủ đề: ${scope.topic}`,
  scope.type !== 'all' && infoTypes[scope.type], scope.eventDay === 'tomorrow' && 'Diễn ra ngày mai',
  scope.eventDay === 'week' && 'Diễn ra tuần này', scope.priority !== 'all' && priorities[scope.priority]?.[0],
].filter(Boolean).join(' · ');

export function readInbox(now, scenario, scope = defaultScope) {
  const [start, end] = bounds(now, scope.period);
  const matches = inbox(now, scenario).filter((mail) => (
    mail.received >= start && mail.received <= end
    && (!scope.unread || mail.unread)
    && normalize(mail.sender + ' ' + mail.address).includes(normalize(scope.sender))
    && normalize(mail.subject).includes(normalize(scope.topic))
  ));
  const unavailable = matches.filter((mail) => mail.unavailable);
  const readable = matches.filter((mail) => !mail.unavailable);
  const groups = new Map();
  for (const mail of readable) {
    if (!groups.has(mail.thread)) groups.set(mail.thread, []);
    groups.get(mail.thread).push(mail);
  }
  const consolidated = [...groups.values()].map((thread) => {
    const [latest] = thread;
    return { ...latest, threadMails: thread, conflict: latest.conflict && new Set(thread.map((mail) => mail.due)).size > 1 };
  });
  const relevant = consolidated.filter((mail) => {
    if (scope.priority !== 'all' && mail.priority !== scope.priority) return false;
    if (scope.type === 'deadlines' && mail.kind !== 'deadline' && !mail.noDeadline) return false;
    if (scope.type === 'meetings' && mail.kind !== 'meeting') return false;
    if (scope.type === 'actions' && !mail.action) return false;
    if (scope.type === 'replies' && !mail.reply) return false;
    const dates = mail.conflict ? mail.threadMails.map((item) => item.due) : [mail.due];
    if (scope.eventDay === 'tomorrow') return dates.some((date) => date && dateInput(date) === dateInput(now + DAY));
    if (scope.eventDay === 'week') {
      const start = startOfWeek(now);
      return dates.some((date) => date && date >= start && date < start + 7 * DAY);
    }
    return true;
  });
  return {
    scope, analyzed: readable.length, unavailable, relevant,
    important: relevant.filter((mail) => ['urgent', 'important'].includes(mail.priority)),
    actions: relevant.filter((mail) => mail.action),
    events: relevant.filter((mail) => mail.due && !mail.conflict).sort((a, b) => a.due - b.due),
  };
}

export function isUnrelated(text) {
  return /\b(du bao thoi tiet|thoi tiet|viet code|viet tho|mua ve|dat ve|dau tu|chuyen tien|ke chuyen|tinh toan)\b/.test(normalize(text));
}

export function intent(text, context) {
  const query = normalize(text);
  if (isUnrelated(text)) return 'outside';
  if (/\b(stand[ -]?up|phoenix|bao cao tien do|bao cao hang ngay)\b/.test(query)) return 'standup';
  if (/\b(outlook|e-?mail|hop thu|thu den|deadline|thoi han|lich hop|lich hen|lich phong van|lich su kien|thu chua doc)\b/.test(query)) return 'outlook';
  if (context === 'outlook' && /\b(loc|chi hien thi|chi xem|giai thich|chi tiet|hoan thanh|da lam xong|chuoi|dat loi nhac|nhac toi|can phan hoi|viec can lam|ngay gan (nhat|day)|khan cap|quan trong|24 gio|hom nay|hom qua|tuan nay|chua doc)\b/.test(query)) return 'outlook';
  return /\b(giup|kiem tra|tong hop|tom tat|muon|cho toi|lam|xin chao|chao)\b/.test(query) || query.split(/\s+/).length <= 2 ? 'clarify' : 'outside';
}

export function mailScope(text, previous = defaultScope) {
  const query = normalize(text);
  const next = { ...previous };
  const days = /(?:trong\s+)?(\d{1,2}|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi) ngay (?:gan nhat|gan day|qua)/.exec(query);
  const numberWords = ['mot', 'hai', 'ba', 'bon', 'nam', 'sau', 'bay', 'tam', 'chin', 'muoi'];
  if (days) next.period = `${Math.max(1, Number(days[1]) || numberWords.indexOf(days[1]) + 1)}d`;
  else if (/\btuan nay\b/.test(query)) next.period = 'week';
  else if (/\bhom nay\b/.test(query)) next.period = 'today';
  else if (/\bhom qua\b/.test(query)) next.period = 'yesterday';
  else if (/24 gio/.test(query)) next.period = '24h';
  if (/\b(chua doc|unread)\b/.test(query)) next.unread = true;
  if (/\b(ca thu da doc|tat ca (email|thu))\b/.test(query)) next.unread = false;
  if (/\b(phan hoi|tra loi|xac nhan qua)\b/.test(query)) next.type = 'replies';
  else if (/\b(lich hop|lich hen|phong van|su kien)\b/.test(query)) next.type = 'meetings';
  else if (/\b(deadline|thoi han|han nop)\b/.test(query)) next.type = 'deadlines';
  else if (/\b(viec can lam|cong viec)\b/.test(query)) next.type = 'actions';
  if (next.type === 'meetings' || next.type === 'deadlines') {
    if (/\bngay mai\b/.test(query)) next.eventDay = 'tomorrow';
    else if (/\btuan nay\b/.test(query)) next.eventDay = 'week';
  } else next.eventDay = '';
  if (/\b(tat ca|bo loc|bo gioi han)\b/.test(query)) next.priority = 'all';
  if (/\bkhong quan trong\b/.test(query)) next.priority = 'low';
  else if (/\bkhan cap\b/.test(query)) next.priority = 'urgent';
  else if (/\b(?:loc|chi|muc do)\b.*\bquan trong\b/.test(query)) next.priority = 'important';
  else if (/\b(?:loc|chi|muc do)\b.*\bthong tin\b/.test(query)) next.priority = 'info';
  const sender = /(?:người gửi|gửi từ|email từ|thư từ|outlook từ)\s+["“]?(.+?)(?=\s+(?:về|trong|hôm nay|hôm qua|chưa đọc|có)\s|["”?!]|[.](?:\s|$)|$)/iu.exec(text);
  const topic = /(?:chủ đề|\bvề)\s+["“]?(.+?)(?=\s+(?:từ|trong|hôm nay|hôm qua|chưa đọc)\s|["”?!]|[.](?:\s|$)|$)/iu.exec(text);
  if (sender) next.sender = sender[1].trim();
  if (topic) next.topic = topic[1].trim();
  return next;
}

export function parseNotes(text) {
  const markers = [...text.matchAll(/(?:^|[\n.!?;,]\s*|\s+và\s+)(hôm qua|ngày mai|việc đã làm|kế hoạch(?: ngày mai)?)(?:\s*[:：–—-]\s*|\s+(?=(?:tôi|mình|em|đã|sẽ|dự định|không|chưa)\s))/gimu)];
  return Object.fromEntries(markers.map((match, index) => {
    const next = markers[index + 1];
    const end = next && next.index + (/^[.!?]/.test(next[0]) ? 1 : 0);
    return [
      /hôm qua|đã làm/i.test(match[1]) ? 'yesterday' : 'tomorrow',
      text.slice(match.index + match[0].length, end).trim(),
    ];
  }).filter(([, value]) => value));
}

export function newThread(title = 'Trò chuyện mới', flow = '') {
  return { id: id(), title, flow, messages: [], draft: { yesterday: '', tomorrow: '' }, taskId: '', scope: null };
}
export function addMessage(thread, role, text, card) {
  thread.messages.push({ id: id(), role, text, card });
}
export function createTask(state, fields) {
  const task = { id: id(), created: Date.now(), attempts: 0, ...fields };
  state.tasks.unshift(task);
  return task;
}
export function notify(state, { title, detail, taskId = '', threadId = '', tone = 'info' }) {
  state.notifications.unshift({ id: id(), title, detail, taskId, threadId, tone, time: Date.now(), read: false });
}
export function log(state, title, detail, taskId = '', threadId = '') {
  state.activity.unshift({ id: id(), title, detail, taskId, threadId, time: Date.now() });
}
export function seed(scenario = 'overview', now = Date.now()) {
  const state = {
    version: 1, scenario, now, page: 'dashboard', active: '', filter: 'all',
    accounts: { phoenix: scenario === 'phoenixExpired' ? 'expired' : 'connected', outlook: scenario === 'outlookExpired' ? 'expired' : 'connected' },
    threads: [], tasks: [], notifications: [], activity: [], completed: {}, inboxAttempts: 0, lastInbox: null,
  };
  if (scenario !== 'overview') return state;
  const draft = newThread('Chuẩn bị Daily Standup', 'standup');
  const email = newThread('Tổng hợp email sáng nay', 'outlook');
  const reminder = newThread('Nhắc lịch họp đồng bộ', 'outlook');
  draft.draft = { ...sampleNotes };
  draft.step = 'preview';
  const pending = createTask(state, { kind: 'standup', title: 'Daily Standup', status: 'pending', draft: { ...sampleNotes }, threadId: draft.id });
  draft.taskId = pending.id;
  addMessage(draft, 'user', 'Giúp tôi chuẩn bị Daily Standup.');
  addMessage(draft, 'agent', 'Bản nháp đã sẵn sàng. Bạn có thể chỉnh sửa nội dung trước khi xác nhận và đặt lịch.', { type: 'draft', taskId: pending.id });
  email.scope = { ...defaultScope };
  addMessage(email, 'user', 'Tóm tắt các email quan trọng gần đây.');
  addMessage(email, 'agent', 'Mình đã kiểm tra Outlook và tổng hợp các mục cần chú ý.', { type: 'mail', scope: email.scope });
  reminder.scope = { ...defaultScope };
  const sync = inbox(now, scenario).find((mail) => mail.id === 'sync');
  const task = createTask(state, { kind: 'reminder', title: sync.event, status: 'scheduled', at: sync.due - 30 * 60_000, mailId: sync.id, threadId: reminder.id });
  addMessage(reminder, 'agent', 'Lời nhắc họp đồng bộ đã được lên lịch.', { type: 'task', taskId: task.id });
  state.threads = [draft, email, reminder];
  state.lastInbox = { threadId: email.id, scope: { ...defaultScope } };
  notify(state, { title: 'Daily Standup đang chờ duyệt', detail: 'Bản nháp đã sẵn sàng để bạn xem lại.', taskId: pending.id, threadId: draft.id, tone: 'warning' });
  notify(state, { title: 'Đã tổng hợp Outlook', detail: 'Có 3 email cần chú ý trong 24 giờ gần nhất.', threadId: email.id });
  log(state, 'Đã chuẩn bị bản nháp Daily Standup', 'Chờ bạn duyệt và đặt lịch.', pending.id, draft.id);
  log(state, 'Đã tạo lời nhắc họp đồng bộ', 'Nhắc trước 30 phút.', task.id, reminder.id);
  return state;
}

export function executeTask(state, task) {
  if (task.status !== 'running') return;
  const scenarioError = task.kind === 'standup' && task.attempts === 1 && failReasons[state.scenario];
  if (state.scenario === 'standupSession' && scenarioError) state.accounts.phoenix = 'expired';
  const error = scenarioError || (task.kind === 'standup' && state.accounts.phoenix !== 'connected' && 'Cần đăng nhập lại Phoenix để nộp Standup.');
  task.status = error ? 'failed' : 'success';
  task.error = error || '';
  const title = error ? 'Nộp Daily Standup thất bại' : task.kind === 'standup' ? 'Đã nộp Daily Standup' : `Đến giờ nhắc: ${task.title}`;
  const detail = error || (task.kind === 'standup' ? 'Phoenix đã tiếp nhận bản nộp mô phỏng.' : 'Lời nhắc đã được gửi trong ứng dụng.');
  const thread = state.threads.find((item) => item.id === task.threadId);
  if (thread) addMessage(thread, 'agent', detail, { type: 'task', taskId: task.id });
  notify(state, { title, detail, taskId: task.id, threadId: task.threadId, tone: error ? 'error' : 'success' });
  log(state, title, detail, task.id, task.threadId);
}
