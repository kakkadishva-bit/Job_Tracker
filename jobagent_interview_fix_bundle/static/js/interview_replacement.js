/* Replace the existing Adaptive Interview System section in app.js with this. */
var interviewSession = null;
var interviewProcessing = false;

function interviewResumeContext() {
    try {
        var saved = localStorage.getItem('jobagent_last_resume');
        return saved ? JSON.parse(saved) : {};
    } catch (e) { return {}; }
}

function normalizeInterviewQuestion(q) {
    if (!q) return null;
    if (typeof q === 'string') return {question:q, type:'technical', skill:'', source:'fallback'};
    return q.question ? q : null;
}

async function startAdaptiveInterview() {
    var role = document.getElementById('interviewRole').value.trim();
    if (!role) { showToast('Please enter a target role', 'error'); return; }
    var company = document.getElementById('interviewCompany').value.trim();
    var level = document.getElementById('interviewLevel').value;
    var mode = document.getElementById('interviewMode').value;
    var jd = document.getElementById('interviewJD').value.trim();
    var skillsText = document.getElementById('interviewRequiredSkills').value;
    var requiredSkills = skillsText.split(',').map(function(s){return s.trim();}).filter(Boolean);
    var manualResume = document.getElementById('interviewResumeContext').value.trim();
    var resume = manualResume ? {text: manualResume} : interviewResumeContext();
    var btn = document.getElementById('startInterviewBtn');
    btn.disabled = true;
    try {
        var jobContext = jd ? {title: role, company: company, description: jd, required_skills: requiredSkills, analyzed:true} : {};
        var data = await apiCall('/api/interview-prep/start', {
            method:'POST', body:JSON.stringify({role:role, company:company, experience_level:level,
            interview_mode:mode, job_context:jobContext, required_skills:requiredSkills, resume_context:resume})
        });
        var first = normalizeInterviewQuestion(data.question);
        if (!first) throw new Error('Interview server returned no question');
        interviewSession = {sessionId:data.session_id, turn:data.turn || 0, conversation:[]};
        document.getElementById('interviewSetupPanel').style.display='none';
        document.getElementById('interviewChatPanel').style.display='block';
        document.getElementById('interviewReportPanel').style.display='none';
        document.getElementById('interviewChatMessages').innerHTML='';
        document.getElementById('interviewStatus').textContent='Active';
        document.getElementById('interviewTurnCounter').textContent='Turn: 0';
        appendInterviewerMessage(first.question);
        interviewSession.conversation.push({role:'interviewer',content:first.question});
        document.getElementById('interviewAnswerInput').disabled=false;
        document.getElementById('sendAnswerBtn').disabled=false;
        document.getElementById('interviewAnswerInput').focus();
    } catch(e) { showToast('Failed to start interview: '+e.message,'error'); }
    finally { btn.disabled=false; }
}

async function sendInterviewAnswer() {
    if (interviewProcessing || !interviewSession) return;
    var input=document.getElementById('interviewAnswerInput');
    var answer=input.value.trim();
    if (!answer) return;
    interviewProcessing=true;
    var btn=document.getElementById('sendAnswerBtn');
    btn.disabled=true; input.disabled=true;
    appendCandidateMessage(answer);
    try {
        var data=await apiCall('/api/interview-prep/answer',{method:'POST',body:JSON.stringify({session_id:interviewSession.sessionId,answer:answer})});
        interviewSession.turn=data.turn || interviewSession.turn+1;
        document.getElementById('interviewTurnCounter').textContent='Turn: '+interviewSession.turn;
        interviewSession.conversation.push({role:'candidate',content:answer});
        input.value='';
        if (data.evaluation) appendEvaluationBadge(data.evaluation);
        var next=normalizeInterviewQuestion(data.next_question);
        if (data.should_continue && next) {
            appendInterviewerMessage(next.question);
            interviewSession.conversation.push({role:'interviewer',content:next.question});
        } else {
            document.getElementById('interviewStatus').textContent='Completed';
            await endAdaptiveInterview(true);
        }
    } catch(e) {
        showToast('Answer failed: '+e.message,'error');
        input.value=answer;
    } finally {
        interviewProcessing=false;
        if (interviewSession && document.getElementById('interviewStatus').textContent!=='Completed') {
            btn.disabled=false; input.disabled=false; input.focus();
        }
    }
}

async function endAdaptiveInterview(autoEnd) {
    if (!interviewSession) return;
    try {
        var data=await apiCall('/api/interview-prep/end',{method:'POST',body:JSON.stringify({session_id:interviewSession.sessionId})});
        document.getElementById('interviewChatPanel').style.display='none';
        document.getElementById('interviewReportPanel').style.display='block';
        renderInterviewReport(data.summary || {});
    } catch(e) { if(!autoEnd) showToast('Failed to end interview: '+e.message,'error'); }
}

function handleInterviewKeydown(event) {
    if(event.key==='Enter' && !event.shiftKey){event.preventDefault();sendInterviewAnswer();}
}

function appendInterviewerMessage(text) {
    var c=document.getElementById('interviewChatMessages');
    var d=document.createElement('div'); d.className='chat-msg chat-msg-ai';
    d.innerHTML='<div class="msg-avatar"><i class="fas fa-robot"></i></div><div class="msg-content">'+escapeHtml(text)+'</div>';
    c.appendChild(d); c.scrollTop=c.scrollHeight;
}
function appendCandidateMessage(text) {
    var c=document.getElementById('interviewChatMessages');
    var d=document.createElement('div'); d.className='chat-msg chat-msg-user';
    d.innerHTML='<div class="msg-avatar"><i class="fas fa-user"></i></div><div class="msg-content">'+escapeHtml(text)+'</div>';
    c.appendChild(d); c.scrollTop=c.scrollHeight;
}
function appendEvaluationBadge(ev) {
    var c=document.getElementById('interviewChatMessages');
    var d=document.createElement('div'); d.className='interview-evaluation';
    d.textContent='Answer score: '+Math.round(ev.overall_score || 0)+'/100';
    c.appendChild(d); c.scrollTop=c.scrollHeight;
}
function renderInterviewReport(s) {
    var c=document.getElementById('interviewReportContent');
    var html='<div class="report-score-section"><div class="report-score">'+Math.round(s.overall_score||0)+'</div><div class="report-score-label">Overall Interview Score / 100</div></div>';
    html+='<div class="report-section"><h4>Interview Summary</h4><div class="report-grid">';
    html+='<div class="report-stat"><span class="stat-label">Questions</span><span class="stat-value">'+(s.questions_asked||0)+'</span></div>';
    html+='<div class="report-stat"><span class="stat-label">Turns</span><span class="stat-value">'+(s.turn_count||0)+'</span></div>';
    html+='<div class="report-stat"><span class="stat-label">Difficulty</span><span class="stat-value">'+escapeHtml(s.difficulty||'MEDIUM')+'</span></div></div></div>';
    html+=reportTags('Strong Areas',s.strong_areas,'tag-green');
    html+=reportTags('Areas to Improve',s.weak_areas,'tag-red');
    html+=reportTags('Skills Tested',s.skills_covered,'');
    html+=reportTags('Required Skills Not Tested',s.required_skills_not_tested,'tag-red');
    html+='<div style="text-align:center;margin-top:20px"><button class="btn btn-primary" onclick="resetInterview()"><i class="fas fa-redo"></i> Start New Interview</button></div>';
    c.innerHTML=html;
}
function reportTags(title,items,cls){
    if(!items||!items.length)return '';
    return '<div class="report-section"><h4>'+title+'</h4><div class="tag-list">'+items.map(function(x){return '<span class="tag '+cls+'">'+escapeHtml(x)+'</span>';}).join('')+'</div></div>';
}
function resetInterview(){
    interviewSession=null; interviewProcessing=false;
    document.getElementById('interviewSetupPanel').style.display='block';
    document.getElementById('interviewChatPanel').style.display='none';
    document.getElementById('interviewReportPanel').style.display='none';
    document.getElementById('interviewChatMessages').innerHTML='';
    document.getElementById('interviewAnswerInput').value='';
}
