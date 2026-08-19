let activityRows = [];
let meetingTrendChart = null;
let lastMeetingTrend = null;

function statusBadge(status) {
  const cls = status === 'Meeting Scheduled' ? 'meeting' : status === 'Needs Follow-Up' ? 'follow' : '';
  return `<span class="badge-status ${cls}">${EngageAI.escapeHtml(status || 'Visitor')}</span>`;
}

function renderMetrics(summary) {
  const metrics = [
    { label: 'Total Visitors', value: summary.total_visitors, icon: 'bi-people' },
    { label: 'Conversations', value: summary.total_conversations, icon: 'bi-chat-square-text' },
    { label: 'Needs Follow-Up', value: summary.needs_follow_up, icon: 'bi-person-exclamation' },
    { label: 'Meetings Scheduled', value: summary.meetings_scheduled, icon: 'bi-calendar2-check' },
  ];
  document.getElementById('cards').innerHTML = metrics.map(item => `
    <div class="col">
      <div class="surface-card metric-card hover-lift">
        <div class="metric-top"><span class="metric-icon"><i class="bi ${item.icon}"></i></span><i class="bi bi-arrow-up-right text-secondary"></i></div>
        <div class="metric-label">${EngageAI.escapeHtml(item.label)}</div>
        <div class="metric-value">${Number(item.value || 0).toLocaleString()}</div>
      </div>
    </div>`).join('');
}

function renderActivity(filter = 'all') {
  const rows = filter === 'all' ? activityRows : activityRows.filter(row => row.status === filter);
  const tbody = document.getElementById('activity');
  const empty = document.getElementById('activityEmpty');
  tbody.innerHTML = rows.map(row => `
    <tr>
      <td><strong>${EngageAI.escapeHtml(row.visitor_name || 'Anonymous visitor')}</strong></td>
      <td>${EngageAI.escapeHtml(row.visitor_email || '—')}</td>
      <td>${EngageAI.escapeHtml(row.interested_service || '—')}</td>
      <td>${statusBadge(row.status)}</td>
      <td>${row.last_activity ? new Date(row.last_activity).toLocaleString() : '—'}</td>
    </tr>`).join('');
  empty.classList.toggle('d-none', rows.length > 0);
}

function cssValue(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function formatMeetingDate(dateText, options = {}) {
  if (!dateText) return '—';
  const [year, month, day] = dateText.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, options);
}

function rangeDisplayLabel(data) {
  const start = formatMeetingDate(data.start_date, { month: 'short', day: 'numeric', year: 'numeric' });
  const end = formatMeetingDate(data.end_date, { month: 'short', day: 'numeric', year: 'numeric' });
  return start === end ? start : `${start} – ${end}`;
}

function meetingChartColors() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    primary: cssValue('--primary', '#2786e8'),
    text: cssValue('--text', dark ? '#f3f7fb' : '#13233a'),
    muted: cssValue('--muted', dark ? '#9fb0c4' : '#6e7f92'),
    grid: dark ? 'rgba(159,176,196,.15)' : 'rgba(66,96,126,.11)',
    fill: dark ? 'rgba(39,134,232,.16)' : 'rgba(39,134,232,.10)',
    pointBorder: cssValue('--surface', dark ? '#101a26' : '#ffffff'),
  };
}

function chartDateLabel(dateText, totalPoints) {
  const options = totalPoints > 120
    ? { month: 'short', day: 'numeric' }
    : { month: 'short', day: 'numeric' };
  return formatMeetingDate(dateText, options);
}

function buildMeetingChart(data) {
  if (typeof Chart === 'undefined') {
    EngageAI.toast('Meeting chart library could not load. Check your internet connection and refresh.', 'danger');
    return;
  }

  lastMeetingTrend = data;
  const canvas = document.getElementById('meetingTrendChart');
  const empty = document.getElementById('meetingChartEmpty');
  const hasMeetings = Number(data.total || 0) > 0;
  empty.classList.toggle('d-none', hasMeetings);
  canvas.classList.toggle('chart-muted', !hasMeetings);

  const colors = meetingChartColors();
  const labels = data.points.map(point => chartDateLabel(point.date, data.points.length));
  const values = data.points.map(point => Number(point.count || 0));
  const pointRadius = data.points.length > 95 ? 0 : data.points.length > 45 ? 2 : 3;

  if (meetingTrendChart) meetingTrendChart.destroy();
  meetingTrendChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Meetings scheduled',
        data: values,
        borderColor: colors.primary,
        backgroundColor: colors.fill,
        borderWidth: 2.4,
        fill: true,
        tension: 0.32,
        pointRadius,
        pointHoverRadius: 5,
        pointBackgroundColor: colors.primary,
        pointBorderColor: colors.pointBorder,
        pointBorderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      animation: { duration: 450 },
      plugins: {
        legend: { display: false },
        tooltip: {
          displayColors: false,
          callbacks: {
            title(items) {
              const point = data.points[items[0].dataIndex];
              return formatMeetingDate(point.date, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
            },
            label(context) {
              const count = Number(context.raw || 0);
              return `${count} meeting${count === 1 ? '' : 's'} scheduled`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: colors.muted,
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: window.innerWidth < 768 ? 6 : 12,
            font: { size: 11, weight: '600' },
          },
          border: { color: colors.grid },
        },
        y: {
          beginAtZero: true,
          suggestedMax: Math.max(4, ...values) + 1,
          ticks: {
            color: colors.muted,
            precision: 0,
            stepSize: 1,
            font: { size: 11, weight: '600' },
          },
          grid: { color: colors.grid },
          border: { display: false },
        },
      },
    },
  });
}

function renderMeetingStats(data) {
  document.getElementById('meetingTodayCount').textContent = Number(data.today_count || 0).toLocaleString();
  document.getElementById('meetingTodayDate').textContent = formatMeetingDate(data.today, { month: 'short', day: 'numeric', year: 'numeric' });
  document.getElementById('meetingPeriodTotal').textContent = Number(data.total || 0).toLocaleString();
  document.getElementById('meetingPeriodLabel').textContent = rangeDisplayLabel(data);
  document.getElementById('meetingPeakCount').textContent = Number(data.peak_count || 0).toLocaleString();
  document.getElementById('meetingPeakDay').textContent = data.peak_day
    ? formatMeetingDate(data.peak_day, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
    : 'No meetings yet';
  document.getElementById('meetingChartFootnote').textContent = `Showing daily scheduled meetings from ${rangeDisplayLabel(data)}.`;
}

function defaultCustomDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 29);
  const localIso = date => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };
  const startInput = document.getElementById('meetingStartDate');
  const endInput = document.getElementById('meetingEndDate');
  if (!startInput.value) startInput.value = localIso(start);
  if (!endInput.value) endInput.value = localIso(end);
}

async function loadMeetingTrend(period = null) {
  const org = localStorage.getItem('organization_id');
  const select = document.getElementById('meetingRange');
  const selectedPeriod = period || select.value || '30d';
  const params = new URLSearchParams({
    period: selectedPeriod,
    tz_offset_minutes: String(new Date().getTimezoneOffset()),
  });

  if (selectedPeriod === 'custom') {
    const start = document.getElementById('meetingStartDate').value;
    const end = document.getElementById('meetingEndDate').value;
    if (!start || !end) {
      EngageAI.toast('Select both From and To dates for the meeting graph.', 'warning');
      return;
    }
    if (start > end) {
      EngageAI.toast('From date cannot be after To date.', 'warning');
      return;
    }
    params.set('start_date', start);
    params.set('end_date', end);
  }

  try {
    const data = await EngageAI.request(`/dashboard/${org}/meeting-trend?${params.toString()}`);
    renderMeetingStats(data);
    buildMeetingChart(data);
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  }
}

function setupMeetingRangeControls() {
  const select = document.getElementById('meetingRange');
  const custom = document.getElementById('meetingCustomRange');
  defaultCustomDates();

  select.addEventListener('change', () => {
    const isCustom = select.value === 'custom';
    custom.classList.toggle('d-none', !isCustom);
    if (!isCustom) loadMeetingTrend(select.value);
  });

  document.getElementById('applyMeetingRange').addEventListener('click', () => loadMeetingTrend('custom'));
}

async function loadDashboard() {
  const org = localStorage.getItem('organization_id');
  try {
    const [summary, activity, organization] = await Promise.all([
      EngageAI.request(`/dashboard/${org}/summary`),
      EngageAI.request(`/dashboard/${org}/recent-activity`),
      EngageAI.request(`/organizations/${org}`),
    ]);
    renderMetrics(summary);
    activityRows = activity;
    renderActivity();
    document.getElementById('dashboardSubtitle').textContent = `${organization.organization_name} · A live view of customer engagement across your organization.`;
  } catch (error) {
    EngageAI.toast(error.message, 'danger');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!EngageAI.requireAuth()) return;
  EngageAI.renderHeader();
  document.querySelectorAll('#activityFilters [data-filter]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('#activityFilters [data-filter]').forEach(btn => btn.classList.remove('active'));
      button.classList.add('active');
      renderActivity(button.dataset.filter);
    });
  });
  setupMeetingRangeControls();
  loadMeetingTrend('30d');
  loadDashboard();
});

document.addEventListener('engageai:themechange', () => {
  if (lastMeetingTrend) buildMeetingChart(lastMeetingTrend);
});
