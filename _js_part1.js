
/* ─── Live Jobs / Skill Demand ────────────────────────────────────── */
var currentAuthUser = null;
var jobsTabMode = 'live';

async function getAuthUser(force) {
    if (currentAuthUser !== null && !force) return currentAuthUser;
    try {
        var a = await apiCall('/api/auth/check');
        currentAuthUser = a && a.authenticated ? a.user : null;
    } catch (e) { currentAuthUser = null; }
    return currentAuthUser;
}

function promptLogin(message) {
    showToast(message || 'Please log in to use this feature', 'error');
}

function switchJobsTab(tab) {
    jobsTabMode = tab;
    document.getElementById('jobsTabLive').classList.toggle('active', tab === 'live');
    document.getElementById('jobsTabDemand').classList.toggle('active', tab === 'demand');
    document.getElementById('liveSearchControls').style.display = tab === 'live' ? 'block' : 'none';
    document.getElementById('demandControls').style.display = tab === 'demand' ? 'block' : 'none';
    document.getElementById('jobsResultsWrap').style.display = tab === 'live' && document.getElementById('jobResults').children.length ? 'block' : 'none';
    document.getElementById('demandResultsWrap').style.display = tab === 'demand' && document.getElementById('demandResultsWrap').innerHTML ? 'block' : 'none';
}

function initJobsPage() { /* results persist between visits; nothing to prefetch */ }

async function searchLiveJobs() {
    var title = document.getElementById('jobSearchInput').value.trim();
    var loc = document.getElementById('jobSearchLocation').value.trim();
    if (!title) { showToast('Enter a job title to search', 'error'); return; }
    document.getElementById('jobsResultsWrap').style.display = 'none';
    document.getElementById('jobsLoading').style.display = 'flex';
    try {
        var data = await apiCall('/api/jobs/search', {
            method: 'POST',
            body: JSON.stringify({ job_title: title, location: loc, limit: 30, include_slow_sources: true, max_age_days: 30 })
        });
        renderJobResults(data, title);
    } catch (e) {
        showToast('Job search failed: ' + e.message, 'error');
        var wrap = document.getElementById('jobsResultsWrap');
        wrap.style.display = 'block';
        document.getElementById('jobsResultsTitle').textContent = 'Search failed';
        document.getElementById('jobsResultsSubtitle').textContent = '';
        document.getElementById('jobResults').innerHTML = '<div class="empty-state" style="grid-column:1/-1"><i class="fas fa-triangle-exclamation"></i><p>' + escapeHtml(e.message) + '</p><button class="btn btn-outline" onclick="searchLiveJobs()"><i class="fas fa-rotate-right"></i> Retry</button></div>';
    } finally {
        document.getElementById('jobsLoading').style.display = 'none';
    }
}

function freshnessClass(label) {
    if (!label) return 'fresh-old';
    var l = label.toLowerCase();
    if (l.indexOf('today') >= 0 || l === 'new') return 'fresh-new';
    if (l.indexOf('day') >= 0 && parseInt(l) <= 7) return 'fresh-recent';
    if (l.indexOf('week') >= 0 && parseInt(l) <= 1) return 'fresh-recent';
    return 'fresh-old';
}

function renderJobResults(data, title) {
    var wrap = document.getElementById('jobsResultsWrap');
    var jobs = data.jobs || [];
    var sources = data.sources_used || [];

    document.getElementById('jobsResultsTitle').textContent = jobs.length + ' fresh job' + (jobs.length === 1 ? '' : 's') + ' for "' + title + '"';
    var srcTxt = sources.length ? 'Sources: ' + sources.join(', ') : 'No live sources responded';
    document.getElementById('jobsResultsSubtitle').textContent = srcTxt + (data.total && data.total > jobs.length ? ' · showing top ' + jobs.length + ' of ' + data.total : '');

    var notice = document.getElementById('jobsNotice');
    if (data.notice) {
        notice.className = 'notice-banner notice-warn';
        notice.innerHTML = '<i class="fas fa-triangle-exclamation"></i><span>' + escapeHtml(data.notice) + '</span>';
        notice.style.display = 'flex';
    } else if (!sources.length && jobs.length) {
        notice.className = 'notice-banner notice-warn';
        notice.innerHTML = '<i class="fas fa-triangle-exclamation"></i><span>None of the primary job-search APIs responded, so these results come from a limited set of sources and may be incomplete.</span>';
        notice.style.display = 'flex';
    } else {
        notice.style.display = 'none';
    }

    var html = '';
    if (!jobs.length) {
        html = '<div class="empty-state" style="grid-column:1/-1"><i class="fas fa-briefcase"></i><p>No fresh postings found for "' + escapeHtml(title) + '" right now.</p><p>Try a broader title (e.g. "developer"), or check back later.</p></div>';
    } else {
        jobs.forEach(function(j) {
            var fresh = j.freshness_label || '';
            html += '<div class="job-card">';
            html += '<div class="job-card-header"><div><div class="job-title">' + escapeHtml(j.job_title || 'Untitled role') + '</div>';
            html += '<div class="job-company"><i class="fas fa-building"></i> ' + escapeHtml(j.company_name || 'Unknown company') + '</div></div>';
            if (fresh) html += '<span class="freshness-tag ' + freshnessClass(fresh) + '">' + escapeHtml(fresh) + '</span>';
            html += '</div>';
            html += '<div class="job-meta">';
            if (j.location) html += '<span><i class="fas fa-location-dot"></i> ' + escapeHtml(j.location) + '</span>';
            if (j.salary && j.salary !== 'Not specified') html += '<span><i class="fas fa-sack-dollar"></i> ' + escapeHtml(j.salary) + '</span>';
            if (j.source) html += '<span class="badge source-badge">' + escapeHtml(j.source) + '</span>';
            html += '</div>';
            if (j.description) {
                var desc = j.description.length > 220 ? j.description.slice(0, 220) + '…' : j.description;
                html += '<div class="job-description">' + escapeHtml(desc) + '</div>';
            }
            html += '<div class="job-actions">';
            if (j.job_url) html += '<a class="btn btn-outline btn-sm" href="' + escapeHtml(j.job_url) + '" target="_blank" rel="noopener noreferrer"><i class="fas fa-arrow-up-right-from-square"></i> View posting</a>';
            html += '<button class="btn btn-primary btn-sm" onclick="trackApplicationFromJob(this, ' + JSON.stringify(JSON.stringify(j)) + ')"><i class="fas fa-plus"></i> I applied</button>';
            html += '</div></div>';
        });
    }
    document.getElementById('jobResults').innerHTML = html;
    wrap.style.display = 'block';
}

async function trackApplicationFromJob(btn, jobJson) {
    var user = await getAuthUser();
    if (!user) { promptLogin('Log in to track applications'); return; }
    var job = {};
    try { job = JSON.parse(jobJson); } catch (e) { showToast('Could not read this job', 'error'); return; }
    var orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    try {
        await apiCall('/api/applications', {
            method: 'POST',
            body: JSON.stringify({
                company: job.company_name || 'Unknown company',
                role: job.job_title || 'Unknown role',
                location: job.location || '',
                job_url: job.job_url || '',
                salary_range: (job.salary && job.salary !== 'Not specified') ? job.salary : '',
                status: 'applied'
            })
        });
        btn.innerHTML = '<i class="fas fa-check"></i> Tracked';
        showToast('Added to your application tracker', 'success');
    } catch (e) {
        showToast('Could not track application: ' + e.message, 'error');
        btn.disabled = false;
        btn.innerHTML = orig;
    }
}

/* ─── Skill Demand view ───────────────────────────────────────────── */
async function loadSkillDemand() {
    var role = document.getElementById('demandRoleInput').value.trim();
    var loc = document.getElementById('demandLocationInput').value.trim();
    if (!role) { showToast('Enter a role to analyze', 'error'); return; }
    document.getElementById('demandResultsWrap').style.display = 'none';
    document.getElementById('demandLoading').style.display = 'flex';
    try {
        var payload = { job_title: role, location: loc, sample_size: 40 };
        if (currentResumeSkills && currentResumeSkills.length) payload.resume_skills = currentResumeSkills;
        var data = await apiCall('/api/market/skill-demand', { method: 'POST', body: JSON.stringify(payload) });
        renderSkillDemand(data, role);
    } catch (e) {
        showToast('Skill demand analysis failed: ' + e.message, 'error');
        document.getElementById('demandResultsWrap').innerHTML = '<div class="empty-state"><i class="fas fa-triangle-exclamation"></i><p>' + escapeHtml(e.message) + '</p><button class="btn btn-outline" onclick="loadSkillDemand()"><i class="fas fa-rotate-right"></i> Retry</button></div>';
        document.getElementById('demandResultsWrap').style.display = 'block';
    } finally {
        document.getElementById('demandLoading').style.display = 'none';
    }
}

function renderSkillDemand(data, role) {
    var skills = data.in_demand_skills || [];
    var html = '<div class="demand-card">';
    html += '<div class="demand-head"><h3><i class="fas fa-fire"></i> In-demand skills for ' + escapeHtml(data.job_title || role) + '</h3>';
    html += '<span class="tag tag-blue">' + (data.sample_size || 0) + ' postings sampled</span></div>';

    if (data.sources_used && data.sources_used.length) {
        html += '<p class="hint" style="margin-bottom:12px"><i class="fas fa-database"></i> Sources: ' + escapeHtml(data.sources_used.join(', ')) + '</p>';
    }
    if (data.warning) {
        html += '<div class="notice-banner notice-warn" style="margin-bottom:16px"><i class="fas fa-triangle-exclamation"></i><span>' + escapeHtml(data.warning) + '</span></div>';
    }
    if (!skills.length) {
        html += '<div class="empty-state"><i class="fas fa-chart-simple"></i><p>No demand data available for this role right now.</p><p>Try a more common role title, or check that job sources are configured.</p></div>';
    } else {
        var max = skills[0].demand_pct || 100;
        skills.slice(0, 15).forEach(function(s) {
            var w = Math.max(4, Math.round(100 * (s.demand_pct / (max || 100))));
            html += '<div class="demand-row">';
            html += '<span class="demand-skill" title="' + escapeHtml(s.skill) + '">' + escapeHtml(s.skill) + '</span>';
            html += '<span class="demand-bar"><span class="demand-fill" style="width:' + w + '%"></span></span>';
            html += '<span class="demand-pct">' + s.demand_pct + '%</span>';
            html += '<span class="demand-meta">in ' + s.postings_mentioning + ' posting' + (s.postings_mentioning === 1 ? '' : 's') + '</span>';
            html += '</div>';
        });
        if (data.resume_comparison) {
            var rc = data.resume_comparison;
            var have = rc.skills_you_have || [];
            var missing = rc.missing_in_demand_skills || [];
            if (have.length || missing.length) {
                html += '<div style="margin-top:20px"><h4><i class="fas fa-user-check"></i> You vs the market</h4>';
                if (have.length) {
                    html += '<p class="hint" style="margin:8px 0 4px"><i class="fas fa-check"></i> You already have:</p><div class="tag-list">';
                    have.forEach(function(s) { html += '<span class="tag tag-green">' + escapeHtml(s.skill) + ' (' + s.demand_pct + '%)</span>'; });
                    html += '</div>';
                }
                if (missing.length) {
                    html += '<p class="hint" style="margin:12px 0 4px"><i class="fas fa-xmark"></i> In demand but missing from your resume:</p><div class="tag-list">';
                    missing.forEach(function(s) { html += '<span class="tag tag-red">' + escapeHtml(s.skill) + ' (' + s.demand_pct + '%)</span>'; });
                    html += '</div>';
                }
                html += '</div>';
            }
        }
    }
    html += '</div>';
    var wrap = document.getElementById('demandResultsWrap');
    wrap.innerHTML = html;
    wrap.style.display = 'block';
}

/* ─── Application tracker board ───────────────────────────────────── */
var APP_COLUMNS = [
    ['applied', 'Applied', 'fa-paper-plane'],
    ['screening', 'Screening', 'fa-filter'],
    ['interview', 'Interview', 'fa-comments'],
    ['offer', 'Offer', 'fa-gift'],
    ['accepted', 'Accepted', 'fa-trophy'],
    ['rejected', 'Rejected', 'fa-circle-xmark']
];

async function loadApplicationsPage() {
    var auth = await getAuthUser(true);
    var prompt = document.getElementById('applicationsLoginPrompt');
    var content = document.getElementById('applicationsContent');
    if (!auth) {
        prompt.style.display = 'block';
        content.style.display = 'none';
        updateNotifBellVisibility(false);
        return;
    }
    prompt.style.display = 'none';
    content.style.display = 'block';
    await loadApplications();
}

async function loadApplications() {
    var board = document.getElementById('appBoard');
    document.getElementById('appBoardLoading').style.display = 'flex';
    try {
        var data = await apiCall('/api/applications');
        renderApplicationsBoard(data.board || {}, data.total || 0);
    } catch (e) {
        board.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><i class="fas fa-triangle-exclamation"></i><p>' + escapeHtml(e.message) + '</p><button class="btn btn-outline" onclick="loadApplications()"><i class="fas fa-rotate-right"></i> Retry</button></div>';
    } finally {
        document.getElementById('appBoardLoading').style.display = 'none';
    }
}

function renderApplicationsBoard(board, total) {
    var html = '';
    APP_COLUMNS.forEach(function(col) {
        var key = col[0], label = col[1], icon = col[2];
        var items = board[key] || [];
        html += '<div class="app-col">';
        html += '<div class="app-col-header"><span><i class="fas ' + icon + '"></i> ' + label + '</span><span class="app-col-count">' + items.length + '</span></div>';
        html += '<div class="app-col-body">';
        if (!items.length) html += '<div class="notif-empty" style="padding:16px">Nothing here yet</div>';
        items.forEach(function(app) {
            html += '<div class="app-card" id="app-card-' + app.id + '">';
            html += '<div class="app-card-title">' + escapeHtml(app.company || 'Unknown') + '</div>';
            html += '<div class="app-card-role">' + escapeHtml(app.role || '') + '</div>';
            html += '<div class="app-card-meta">';
            if (app.location) html += '<span><i class="fas fa-location-dot"></i> ' + escapeHtml(app.location) + '</span>';
            if (app.salary_range) html += '<span><i class="fas fa-sack-dollar"></i> ' + escapeHtml(app.salary_range) + '</span>';
            if (app.applied_date) html += '<span><i class="fas fa-calendar"></i> ' + escapeHtml((app.applied_date || '').slice(0, 10)) + '</span>';
            html += '</div>';
            if (app.notes) html += '<div class="app-note">' + escapeHtml(app.notes) + '</div>';
            html += '<div class="app-card-actions">';
            html += '<select class="app-status-select" onchange="changeApplicationStatus(' + app.id + ', this)">';
            APP_COLUMNS.forEach(function(c2) {
                html += '<option value="' + c2[0] + '"' + (c2[0] === app.status ? ' selected' : '') + '>' + c2[1] + '</option>';
            });
            html += '</select>';
            if (app.job_url) html += '<a class="app-icon-btn" href="' + escapeHtml(app.job_url) + '" target="_blank" rel="noopener noreferrer" title="Open posting"><i class="fas fa-arrow-up-right-from-square"></i></a>';
            html += '<button class="app-icon-btn" onclick="deleteApplication(' + app.id + ')" title="Remove"><i class="fas fa-trash"></i></button>';
            html += '</div></div>';
        });
        html += '</div></div>';
    });
    document.getElementById('appBoard').innerHTML = html;
}

async function createApplication() {
    var user = await getAuthUser();
    if (!user) { promptLogin('Log in to track applications'); return; }
    var company = document.getElementById('appCompany').value.trim();
    var role = document.getElementById('appRole').value.trim();
    if (!company || !role) { showToast('Company and role are required', 'error'); return; }
    var btn = document.getElementById('addAppBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    try {
        await apiCall('/api/applications', {
            method: 'POST',
            body: JSON.stringify({
                company: company,
                role: role,
                location: document.getElementById('appLocation').value.trim(),
                job_url: document.getElementById('appUrl').value.trim(),
                salary_range: document.getElementById('appSalary').value.trim(),
                status: document.getElementById('appStatus').value
            })
        });
        ['appCompany', 'appRole', 'appLocation', 'appUrl', 'appSalary'].forEach(function(id) { document.getElementById(id).value = ''; });
        showToast('Application added to the board', 'success');
        await loadApplications();
    } catch (e) {
        showToast('Could not add application: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus"></i> Add to board';
    }
}

async function changeApplicationStatus(id, select) {
    try {
        await apiCall('/api/applications/' + id, { method: 'PATCH', body: JSON.stringify({ status: select.value }) });
        showToast('Moved to ' + select.value, 'success');
        await loadApplications();
    } catch (e) {
        showToast('Could not update status: ' + e.message, 'error');
        await loadApplications();
    }
}

async function deleteApplication(id) {
    if (!window.confirm('Remove this application from the tracker?')) return;
    try {
        await apiCall('/api/applications/' + id, { method: 'DELETE' });
        showToast('Application removed', 'success');
        await loadApplications();
    } catch (e) {
        showToast('Could not remove application: ' + e.message, 'error');
    }
}

/* ─── Notification bell ───────────────────────────────────────────── */
function updateNotifBellVisibility(authenticated) {
    var wrap = document.getElementById('navBellWrap');
    if (!wrap) return;
    wrap.style.display = authenticated ? 'block' : 'none';
    if (!authenticated) updateNotifBadge(0);
}

function updateNotifBadge(count) {
    var badge = document.getElementById('notifBadge');
    if (!badge) return;
    if (count > 0) {
        badge.style.display = 'inline-block';
        badge.textContent = count > 99 ? '99+' : count;
    } else {
        badge.style.display = 'none';
    }
}

async function initNotifications() {
    var user = await getAuthUser(true);
    updateNotifBellVisibility(!!user);
    if (user) await refreshNotifications();
}

function toggleNotifPanel(ev) {
    if (ev) ev.stopPropagation();
    var panel = document.getElementById('notifPanel');
    if (!panel) return;
    var opening = panel.style.display === 'none' || !panel.style.display;
    panel.style.display = opening ? 'block' : 'none';
    if (opening) refreshNotifications();
}

function closeNotifPanel() {
    var panel = document.getElementById('notifPanel');
    if (panel) panel.style.display = 'none';
}

async function refreshNotifications() {
    try {
        var data = await apiCall('/api/notifications');
        updateNotifBadge(data.unread_count || 0);
        renderNotifList(data.notifications || []);
    } catch (e) {
        console.error('Notifications failed:', e);
    }
}

function notifIconClass(type) {
    if (type === 'new_job_match') return 'notif-icon-type-job';
    if (type === 'interview_reminder') return 'notif-icon-type-interview';
    return 'notif-icon-type-job';
}

function notifIcon(type) {
    if (type === 'new_job_match') return 'fa-briefcase';
    if (type === 'interview_reminder') return 'fa-calendar-check';
    return 'fa-bell';
}

function renderNotifList(notifs) {
    var list = document.getElementById('notifList');
    if (!list) return;
    if (!notifs.length) {
        list.innerHTML = '<div class="notif-empty"><i class="fas fa-check-circle" style="font-size:1.4rem;display:block;margin-bottom:8px;color:var(--success)"></i>You are all caught up!</div>';
        return;
    }
    var html = '';
    notifs.forEach(function(n) {
        var when = n.created_at ? new Date(n.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
        html += '<div class="notif-item" onclick="markNotificationRead(' + n.id + ', ' + JSON.stringify(JSON.stringify(n.link_url || '')) + ', this)">';
        html += '<div class="notif-icon ' + notifIconClass(n.type) + '"><i class="fas ' + notifIcon(n.type) + '"></i></div>';
        html += '<div class="notif-body"><div class="notif-title">' + escapeHtml(n.title || '') + '</div>';
        html += '<div class="notif-message">' + escapeHtml(n.message || '') + '</div>';
        html += '<div class="notif-time">' + escapeHtml(when) + '</div></div>';
        html += '<span class="notif-dot"></span>';
        html += '</div>';
    });
    list.innerHTML = html;
}

function openNotificationLink(link) {
    if (!link) return;
    if (/^https?:\/\//i.test(link)) { window.open(link, '_blank', 'noopener'); return; }
    if (link.indexOf('/interview-prep') === 0) { showPage('interview'); return; }
    if (link.charAt(0) === '/') { window.location.href = link; }
}

async function markNotificationRead(id, linkJson, el) {
    try {
        await apiCall('/api/notifications/' + id + '/read', { method: 'POST' });
        if (el) {
            var dot = el.querySelector('.notif-dot');
            if (dot) dot.remove();
            el.style.opacity = '0.55';
        }
    } catch (e) { /* keep going - opening the link matters more */ }
    refreshNotifications();
    var link = '';
    try { link = JSON.parse(linkJson); } catch (err) { link = ''; }
    openNotificationLink(link);
}

async function markAllNotificationsRead(ev) {
    if (ev) ev.stopPropagation();
    try {
        await apiCall('/api/notifications/read-all', { method: 'POST' });
        showToast('All notifications marked as read', 'success');
        await refreshNotifications();
    } catch (e) {
        showToast('Could not mark all as read: ' + e.message, 'error');
    }
}

document.addEventListener('click', function(ev) {
    var panel = document.getElementById('notifPanel');
    var bell = document.getElementById('notifBell');
    if (!panel || panel.style.display === 'none') return;
    if (panel.contains(ev.target) || (bell && bell.contains(ev.target))) return;
    closeNotifPanel();
});

/* ─── Boot: auth-aware notification bell ──────────────────────────── */
document.addEventListener('DOMContentLoaded', function() {
    initNotifications();
});