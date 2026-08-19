let visitorRows = [];
let activeVisitorId = null;

function initials(name) {
  const parts = String(name || 'Visitor').trim().split(/\s+/).slice(0, 2);
  return parts.map(part => part[0]?.toUpperCase() || '').join('') || 'V';
}

function timeLabel(value) {
  if (!value) return '';
  const date = new Date(value);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function fullTime(value) {
  if (!value) return 'Unknown';
  return new Date(value).toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function statusClass(status) {
  if (status === 'Meeting Scheduled') return 'meeting';
  if (status === 'Needs Follow-Up') return 'follow';
  return '';
}

function renderList(rows = visitorRows) {
  const list = document.getElementById('list');
  document.getElementById('conversationCount').textContent = rows.length;

  if (!rows.length) {
    list.innerHTML = '<div class="empty-state m-3"><i class="bi bi-people"></i>No visitor conversations found.</div>';
    return;
  }

  list.innerHTML = rows.map(row => {
    const name = row.visitor_name || row.visitor_email || 'Anonymous visitor';
    const secondary = row.visitor_name
      ? (row.visitor_email || row.anonymous_label)
      : (row.visitor_email || row.anonymous_label);
    const preview = row.last_message_preview || 'No messages yet';
    const sessions = `${row.conversation_count || 0} conversation${row.conversation_count === 1 ? '' : 's'}`;

    return `
      <button class="visitor-conversation-item ${activeVisitorId === row.visitor_id ? 'active' : ''}" type="button" onclick="openVisitor('${row.visitor_id}')">
        <div class="visitor-card-avatar">${EngageAI.escapeHtml(initials(name))}</div>
        <div class="visitor-card-copy min-w-0">
          <div class="conversation-name-row">
            <span class="conversation-name">${EngageAI.escapeHtml(name)}</span>
            <span class="conversation-time">${EngageAI.escapeHtml(timeLabel(row.last_message_at))}</span>
          </div>
          <div class="visitor-card-secondary">${EngageAI.escapeHtml(secondary)}</div>
          <div class="conversation-preview">${EngageAI.escapeHtml(preview)}</div>
          <div class="visitor-card-meta">
            <span><i class="bi bi-chat-square-text"></i>${EngageAI.escapeHtml(sessions)}</span>
            ${row.status ? `<span class="mini-status ${statusClass(row.status)}">${EngageAI.escapeHtml(row.status)}</span>` : ''}
          </div>
        </div>
      </button>`;
  }).join('');
}

async function load() {
  const org = localStorage.getItem('organization_id');
  try {
    visitorRows = await EngageAI.request(`/conversations/organization/${org}/visitors`);
    renderList();
    if (visitorRows.length && !activeVisitorId) openVisitor(visitorRows[0].visitor_id);
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  }
}

function renderMessage(message) {
  const role = message.sender === 'visitor' ? 'visitor' : 'agent';
  const body = EngageAI.escapeHtml(message.message || '').replaceAll('\n', '<br>');
  const when = message.created_at ? new Date(message.created_at).toLocaleString() : '';
  return `
    <div class="message-row ${role}">
      <div class="message-bubble">
        ${body}
        <span class="message-time">${EngageAI.escapeHtml(when)}</span>
      </div>
    </div>`;
}

function renderSession(conversation, index, total) {
  const messages = conversation.messages || [];
  const sessionDate = conversation.started_at ? fullTime(conversation.started_at) : `Conversation ${index + 1}`;
  const lastTime = conversation.last_message_at ? fullTime(conversation.last_message_at) : sessionDate;
  const label = `Conversation ${index + 1}`;
  const isLatest = index === total - 1;

  return `
    <section class="conversation-session" id="session-${conversation.conversation_id}">
      <div class="session-divider">
        <span class="session-number"><i class="bi bi-chat-square-dots"></i>${EngageAI.escapeHtml(label)}</span>
        <span class="session-date">${EngageAI.escapeHtml(sessionDate)}</span>
      </div>
      <div class="session-messages">
        ${messages.length
          ? messages.map(renderMessage).join('')
          : '<div class="session-empty">No messages were recorded in this conversation.</div>'}
      </div>
      <div class="conversation-boundary">
        <span>
          <i class="bi bi-pause-circle me-1"></i>
          ${isLatest ? 'Latest conversation paused here' : 'Conversation paused here'} · ${EngageAI.escapeHtml(lastTime)}
        </span>
      </div>
    </section>`;
}

async function openVisitor(id) {
  activeVisitorId = id;
  renderList();

  const chat = document.getElementById('chat');
  chat.innerHTML = '<div class="chat-empty"><div><div class="spinner-border spinner-border-sm text-primary mb-2"></div><div class="small">Loading visitor history...</div></div></div>';

  try {
    const data = await EngageAI.request(`/conversations/visitor/${id}`);
    const name = data.visitor_name || data.visitor_email || 'Anonymous visitor';
    const identityLine = data.visitor_email || data.anonymous_label || 'No contact details captured yet';
    const serviceLine = data.interested_service ? `Interested in ${data.interested_service}` : null;
    const conversations = data.conversations || [];
    const totalMessages = data.message_count || 0;
    const sessionSummary = `${data.conversation_count || 0} conversation${data.conversation_count === 1 ? '' : 's'} · ${totalMessages} message${totalMessages === 1 ? '' : 's'}`;

    chat.innerHTML = `
      <div class="chat-head visitor-history-head">
        <div class="chat-person">
          <div class="avatar">${EngageAI.escapeHtml(initials(name))}</div>
          <div class="min-w-0">
            <strong>${EngageAI.escapeHtml(name)}</strong>
            <small>${EngageAI.escapeHtml(identityLine)}${serviceLine ? ` · ${EngageAI.escapeHtml(serviceLine)}` : ''}</small>
          </div>
        </div>
        <div class="d-flex align-items-center gap-2 flex-wrap justify-content-end">
          ${data.status ? `<span class="badge-status ${statusClass(data.status)}">${EngageAI.escapeHtml(data.status)}</span>` : ''}
          <a class="btn btn-soft btn-sm" href="${EngageAI.API}/conversations/visitor/${id}/download?format=txt" title="Download all conversation history">
            <i class="bi bi-download me-1"></i><span class="d-none d-xl-inline">History</span>
          </a>
        </div>
      </div>
      <div class="visitor-history-summary">
        <span><i class="bi bi-collection"></i>${EngageAI.escapeHtml(sessionSummary)}</span>
        <span><i class="bi bi-clock-history"></i>Last active ${EngageAI.escapeHtml(fullTime(data.last_message_at))}</span>
      </div>
      <div class="chat-body visitor-history-body" id="chatBody">
        ${conversations.length
          ? conversations.map((conversation, index) => renderSession(conversation, index, conversations.length)).join('')
          : '<div class="chat-empty"><div><i class="bi bi-chat-dots"></i>No conversations for this visitor.</div></div>'}
      </div>
      <div class="chat-footer">
        <span><i class="bi bi-shield-check me-1"></i>All sessions for this visitor are grouped in one history.</span>
        <span>${EngageAI.escapeHtml(sessionSummary)}</span>
      </div>`;

    const body = document.getElementById('chatBody');
    if (body) body.scrollTop = body.scrollHeight;
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
    chat.innerHTML = '<div class="chat-empty"><div><i class="bi bi-exclamation-circle"></i>Unable to load this visitor history.</div></div>';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!EngageAI.requireAuth()) return;
  EngageAI.renderHeader();

  document.getElementById('conversationSearch').addEventListener('input', event => {
    const term = event.target.value.trim().toLowerCase();
    const filtered = !term ? visitorRows : visitorRows.filter(row =>
      [
        row.visitor_name,
        row.visitor_email,
        row.anonymous_label,
        row.interested_service,
        row.last_message_preview,
        row.status,
      ]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(term))
    );
    renderList(filtered);
  });

  load();
});
