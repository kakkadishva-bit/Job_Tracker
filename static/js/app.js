/* JobAgent - Frontend (Career Assistant) */
// Configurable API base URL — used when the frontend is hosted separately from the Flask backend.
// Falls back to '' (same-origin relative paths) for local development.
var API_BASE_URL = (function() {
  // 1) explicit env var injected at build time (e.g. NEXT_PUBLIC_API_BASE_URL)
  if (typeof window !== 'undefined' && window.__API_BASE_URL__) return window.__API_BASE_URL__;
  // 2) meta tag in index.html: <meta name="api-base-url" content="...">
  var m = document.querySelector('meta[name="api-base-url"]');
  if (m && m.getAttribute('content')) return m.getAttribute('content').trim();
  return '';
})();

function apiUrl(path) {
  if (API_BASE_URL && !API_BASE_URL.endsWith('/')) API_BASE_URL = API_BASE_URL + '/';
  // relative /api/* stays same-origin; only absolute paths get the prefix
  if (path.match(/^https?:\/\//)) return path;
  return API_BASE_URL + path;
}

var currentGuides=[],selectedRoles=[],currentResumeSkills=[];

function showPage(p){
  document.querySelectorAll('.page').forEach(function(e){e.classList.remove('active')});
  document.querySelectorAll('.nav-link').forEach(function(e){e.classList.remove('active')});
  var el=document.getElementById('page-'+p);if(el)el.classList.add('active');
  var nl=document.querySelector('.nav-link[data-page="'+p+'"]');if(nl)nl.classList.add('active');
  document.getElementById('navLinks').classList.remove('open');
  window.scrollTo(0,0);
  if(p==='dashboard')loadDashboard();
  if(p==='chat')loadChatPage();
  if(p==='applications')loadApplicationsPage();
}
function toggleNav(){document.getElementById('navLinks').classList.toggle('open')}

function showToast(msg,type){
  type=type||'success';var ex=document.querySelector('.toast');if(ex)ex.remove();
  var t=document.createElement('div');t.className='toast toast-'+type;
  var ic=type==='success'?'fa-check-circle':'fa-exclamation-circle';
  t.innerHTML='<i class="fas '+ic+'"></i> '+msg;document.body.appendChild(t);
  setTimeout(function(){t.remove()},3000);
}

async function apiCall(url,opts){
  opts=opts||{};
  var fullUrl=apiUrl(url);
  var r=await fetch(fullUrl,{headers:Object.assign({'Content-Type':'application/json'},opts.headers||{}),method:opts.method||'GET',body:opts.body||undefined});
  if(!r.ok){var e=await r.json().catch(function(){return{error:'Failed'}});throw new Error(e.error||'Failed');}
  return await r.json();
}

function heroSearch(){var q=document.getElementById('heroSearchInput').value.trim();if(!q)return;document.getElementById('searchInput').value=q;showPage('search');performSearch()}
function quickSearch(r){document.getElementById('heroSearchInput').value=r;heroSearch()}

async function performSearch(){
  var q=document.getElementById('searchInput').value.trim();
  if(!q){showToast('Enter a search query','error');return;}
  document.getElementById('searchLoading').style.display='flex';
  document.getElementById('resultsHeader').style.display='none';
  document.getElementById('guideGrid').innerHTML='';
  document.getElementById('roleExpansionPanel').style.display='none';
  document.getElementById('platformButtonsContainer').style.display='none';
  try{
    var rd=await apiCall('/api/expand-roles',{method:'POST',body:JSON.stringify({role:q})});
    selectedRoles=rd.related_roles;showRoleExpansion(rd.related_roles);
    var sd=await apiCall('/api/search',{method:'POST',body:JSON.stringify({query:q,roles:selectedRoles})});
    currentGuides=sd;renderGuides(sd);
  }catch(e){showToast('Search failed: '+e.message,'error');}
  finally{document.getElementById('searchLoading').style.display='none';}
}

function showRoleExpansion(roles){
  document.getElementById('roleExpansionPanel').style.display='block';
  document.getElementById('roleCount').textContent=roles.length;
  document.getElementById('roleTags').innerHTML=roles.map(function(r){
    return '<span class="role-tag" onclick="exploreRole(this.getAttribute(\'data-role\'))" data-role="'+r.replace(/"/g,'"')+'">'+r+'</span>';
  }).join('');
}

function exploreRole(role){
  document.getElementById('searchInput').value=role;
  performSearch();
}

function renderGuides(data){
  document.getElementById('resultsHeader').style.display='block';
  document.getElementById('resultsTitle').textContent='Role Guide: '+data.primary_guide.role_title;
  document.getElementById('resultsSubtitle').textContent='Showing role insights for "'+data.query+'" with '+data.total+' related roles';
  renderPlatformButtons(data.platform_urls, data.query);
  var grid=document.getElementById('guideGrid');
  var html='';
  if(data.primary_guide.guide_available===false){
    html+='<div class="notice-banner notice-warn"><i class="fas fa-triangle-exclamation"></i><span>'+data.primary_guide.overview+'</span></div>';
    if(data.primary_guide.available_roles&&data.primary_guide.available_roles.length){
      html+='<div class="guide-card"><div class="guide-section"><h4><i class="fas fa-list-check"></i> Roles with accurate guides</h4><div class="skill-tags">';
      data.primary_guide.available_roles.forEach(function(r){html+='<span class="skill-tag skill-tag-required" style="cursor:pointer" onclick="exploreRole(\''+r.replace(/'/g,"\\'")+'\')">'+r+'</span>';});
      html+='</div></div></div>';
    }
  } else {
    html+=renderGuideCard(data.primary_guide, true);
  }
  if(data.related_guides && data.related_guides.length > 0){
    html+='<div class="related-guides-header"><h3><i class="fas fa-layer-group"></i> Related Role Guides</h3></div>';
    data.related_guides.forEach(function(g){
      html+=renderGuideCard(g, false);
    });
  }
  grid.innerHTML=html;
}

function renderGuideCard(guide, isPrimary){
  var cls=isPrimary?'guide-card guide-card-primary':'guide-card';
  var badge=isPrimary?'<span class="guide-badge-primary">Role Guide</span>':'';
  var salary=guide.salary_estimate||{};
  var html='<div class="'+cls+'">';
  html+='<div class="guide-card-header">';
  html+='<div><div class="guide-title">'+guide.role_title+'</div>'+badge+'</div>';
  html+='</div>';
  html+='<div class="guide-section"><h4><i class="fas fa-info-circle"></i> Overview</h4>';
  html+='<p class="guide-text">'+guide.overview+'</p></div>';
  html+='<div class="guide-section"><h4><i class="fas fa-tasks"></i> Key Responsibilities</h4>';
  html+='<ul class="guide-list">';
  (guide.responsibilities||[]).forEach(function(r){html+='<li>'+r+'</li>';});
  html+='</ul></div>';
  html+='<div class="guide-section"><h4><i class="fas fa-code"></i> Required Skills</h4>';
  html+='<div class="skill-tags">';
  (guide.required_skills||[]).forEach(function(s){html+='<span class="skill-tag skill-tag-required">'+s+'</span>';});
  html+='</div></div>';
  html+='<div class="guide-section"><h4><i class="fas fa-star"></i> Preferred Skills</h4>';
  html+='<div class="skill-tags">';
  (guide.preferred_skills||[]).forEach(function(s){html+='<span class="skill-tag skill-tag-preferred">'+s+'</span>';});
  html+='</div></div>';
  html+='<div class="guide-section"><h4><i class="fas fa-dollar-sign"></i> Estimated Salary Range</h4>';
  html+='<div class="salary-grid">';
  if(salary.usd) html+='<div class="salary-item"><span class="salary-label">USD</span><span class="salary-value">'+salary.usd+'</span></div>';
  if(salary.inr) html+='<div class="salary-item"><span class="salary-label">INR</span><span class="salary-value">'+salary.inr+'</span></div>';
  if(salary.eur) html+='<div class="salary-item"><span class="salary-label">EUR</span><span class="salary-value">'+salary.eur+'</span></div>';
  html+='</div>';
  if(salary.note) html+='<p class="salary-note"><i class="fas fa-info-circle"></i> '+salary.note+'</p>';
  html+='</div>';
  if(guide.experience_levels){
    html+='<div class="guide-section"><h4><i class="fas fa-layer-group"></i> Experience Levels</h4>';
    html+='<ul class="guide-list">';
    guide.experience_levels.forEach(function(l){html+='<li>'+l+'</li>';});
    html+='</ul></div>';
  }
  html+='<div class="guide-section"><h4><i class="fas fa-arrow-trend-up"></i> Career Growth Path</h4>';
  html+='<ul class="guide-list">';
  (guide.career_growth||[]).forEach(function(c){html+='<li>'+c+'</li>';});
  html+='</ul></div>';
  html+='<div class="guide-section"><h4><i class="fas fa-comments"></i> Interview Preparation Topics</h4>';
  html+='<ul class="guide-list">';
  (guide.interview_topics||[]).forEach(function(t){html+='<li>'+t+'</li>';});
  html+='</ul></div>';
  if(guide.industry_demand){
    html+='<div class="guide-section"><h4><i class="fas fa-fire"></i> Industry Demand</h4>';
    html+='<p class="guide-text"><strong>'+guide.industry_demand+'</strong></p></div>';
  }
  if(guide.growth_outlook){
    html+='<div class="guide-section"><h4><i class="fas fa-rocket"></i> Growth Outlook</h4>';
    html+='<p class="guide-text">'+guide.growth_outlook+'</p></div>';
  }
  html+='<div class="guide-actions">';
  html+='<button class="btn btn-primary btn-sm" onclick=\'saveGuide('+JSON.stringify(JSON.stringify(guide))+')\'><i class="fas fa-bookmark"></i> Save Guide</button>';
  html+='</div>';
  html+='</div>';
  return html;
}

/* Shared platform catalog - general + remote-focused groups.
   Keys must match PLATFORM_SEARCH_URLS in app.py. */
var PLATFORM_GROUPS=[
 {title:'Top Platforms',items:[
  {key:'linkedin',label:'LinkedIn',icon:'fab fa-linkedin',color:'#0077B5'},
  {key:'indeed',label:'Indeed',icon:'fas fa-search',color:'#2164F3'},
  {key:'glassdoor',label:'Glassdoor',icon:'fas fa-building',color:'#0CAA41'},
  {key:'naukri',label:'Naukri',icon:'fas fa-briefcase',color:'#FF6B35'},
  {key:'wellfound',label:'Wellfound',icon:'fas fa-rocket',color:'#FF5A5F'},
  {key:'upwork',label:'Upwork',icon:'fas fa-laptop-code',color:'#14A800'},
  {key:'ziprecruiter',label:'ZipRecruiter',icon:'fas fa-file-alt',color:'#FF4E00'},
  {key:'monster',label:'Monster',icon:'fas fa-user-tie',color:'#00467A'}
 ]},
 {title:'Remote Jobs',items:[
  {key:'remoteok',label:'RemoteOK',icon:'fas fa-globe',color:'#FF4F4F',remote:true},
  {key:'weworkremotely',label:'WeWorkRemotely',icon:'fas fa-house-laptop',color:'#1B8A5A',remote:true},
  {key:'remotive',label:'Remotive',icon:'fas fa-satellite-dish',color:'#4C6FFF',remote:true},
  {key:'workingnomads',label:'Working Nomads',icon:'fas fa-suitcase-rolling',color:'#F2994A',remote:true},
  {key:'flexjobs',label:'FlexJobs',icon:'fas fa-clock',color:'#2F4F8F',remote:true},
  {key:'remoteco',label:'Remote.co',icon:'fas fa-earth-americas',color:'#0F9D8F',remote:true},
  {key:'himalayas',label:'Himalayas',icon:'fas fa-mountain',color:'#6C5CE7',remote:true},
  {key:'jobspresso',label:'Jobspresso',icon:'fas fa-mug-hot',color:'#B8562D',remote:true},
  {key:'skipthedrive',label:'SkipTheDrive',icon:'fas fa-car-side',color:'#2D9CDB',remote:true},
  {key:'justremote',label:'JustRemote',icon:'fas fa-circle-nodes',color:'#27AE60',remote:true},
  {key:'europeremotely',label:'EuropeRemotely',icon:'fas fa-earth-europe',color:'#1E6FBA',remote:true},
  {key:'arcdev',label:'Arc.dev',icon:'fas fa-bow-arrow',color:'#EB5757',remote:true},
  {key:'virtualvocations',label:'Virtual Vocations',icon:'fas fa-house-circle-check',color:'#9B51E0',remote:true},
  {key:'wfh',label:'WFH Jobs',icon:'fas fa-house',color:'#219653',remote:true},
  {key:'turing',label:'Turing',icon:'fas fa-microchip',color:'#8E44AD',remote:true},
  {key:'hired',label:'Hired',icon:'fas fa-handshake',color:'#7B61FF',remote:true}
 ]},
 {title:'India-Specific',items:[
  {key:'foundit',label:'Foundit',icon:'fas fa-briefcase',color:'#5C5CFF'},
  {key:'internshala',label:'Internshala',icon:'fas fa-graduation-cap',color:'#00A5EC'},
  {key:'freshersworld',label:'Freshersworld',icon:'fas fa-user-graduate',color:'#FF6D1F'},
  {key:'shine',label:'Shine',icon:'fas fa-certificate',color:'#F5A623'},
  {key:'timesjobs',label:'TimesJobs',icon:'fas fa-newspaper',color:'#0057A8'},
  {key:'apna',label:'Apna',icon:'fas fa-mobile-screen',color:'#E8425A'},
  {key:'cutshort',label:'Cutshort',icon:'fas fa-scissors',color:'#2F6BFF'},
  {key:'hirist',label:'Hirist',icon:'fas fa-id-badge',color:'#0A66C2'},
  {key:'instahyre',label:'Instahyre',icon:'fas fa-bolt',color:'#00C853'},
  {key:'iimjobs',label:'IIMjobs',icon:'fas fa-chess-knight',color:'#084C94'},
  {key:'placementindia',label:'PlacementIndia',icon:'fas fa-map-pin',color:'#FF7043'}
 ]},
 {title:'Freelancing',items:[
  {key:'fiverr',label:'Fiverr',icon:'fas fa-bolt',color:'#1DBF73'},
  {key:'freelancer',label:'Freelancer',icon:'fas fa-list-check',color:'#29B2FE'},
  {key:'guru',label:'Guru',icon:'fas fa-hat-wizard',color:'#49A010'},
  {key:'peopleperhour',label:'PeoplePerHour',icon:'fas fa-hourglass-half',color:'#F33F49'},
  {key:'toptal',label:'Toptal',icon:'fas fa-gem',color:'#204ECF'}
 ]},
 {title:'More Platforms',items:[
  {key:'simplyhired',label:'SimplyHired',icon:'fas fa-search-dollar',color:'#1EBEBA'},
  {key:'careerbuilder',label:'CareerBuilder',icon:'fas fa-building-columns',color:'#0066A1'},
  {key:'dice',label:'Dice',icon:'fas fa-dice',color:'#0073B7'},
  {key:'greenhouse',label:'Greenhouse',icon:'fas fa-seedling',color:'#24A47F'},
  {key:'lever',label:'Lever',icon:'fas fa-bars-progress',color:'#5B8F4B'},
  {key:'talent',label:'Talent.com',icon:'fas fa-award',color:'#FF6B6B'},
  {key:'jooble',label:'Jooble',icon:'fas fa-magnifying-glass-chart',color:'#3F51B5'},
  {key:'xing',label:'XING',icon:'fab fa-xing',color:'#026466'},
  {key:'theladders',label:'The Ladders',icon:'fas fa-stairs',color:'#0B7B75'},
  {key:'snagajob',label:'Snagajob',icon:'fas fa-clipboard-list',color:'#F76B1C'},
  {key:'adzuna',label:'Adzuna',icon:'fas fa-calculator',color:'#32B44A'},
  {key:'usajobs',label:'USAJobs',icon:'fas fa-flag-usa',color:'#112E51'},
  {key:'idealist',label:'Idealist',icon:'fas fa-heart',color:'#2A7DE1'},
  {key:'builtin',label:'Built In',icon:'fas fa-city',color:'#FF5C35'},
  {key:'jobrapido',label:'Jobrapido',icon:'fas fa-gauge-high',color:'#E4002B'}
 ]}
];
var PLATFORMS_ALL=(function(){var a=[];PLATFORM_GROUPS.forEach(function(g){g.items.forEach(function(p){p.remote=!!p.remote;a.push(p)})});return a})();

function renderPlatformButtons(platformUrls, query){
  var container=document.getElementById('platformButtonsContainer');
  if(!container)return;
  container.style.display='block';
  var html='<div class="platform-buttons-card">';
  html+='<h3><i class="fas fa-external-link-alt"></i> Find Opportunities On</h3>';
  html+='<p class="platform-buttons-subtitle">Search for <strong>'+query+'</strong> on '+PLATFORMS_ALL.length+' platforms</p>';
  PLATFORM_GROUPS.forEach(function(group){
    html+='<div class="platform-group-title">'+group.title+(group.title==='Remote Jobs'?' <span class="remote-flag">home-office friendly</span>':'')+'</div>';
    html+='<div class="platform-buttons-grid">';
    group.items.forEach(function(p){
      var url=platformUrls[p.key]||'#';
      html+='<a href="'+url+'" target="_blank" rel="noopener noreferrer" class="platform-btn" style="--platform-color:'+p.color+'">';
      html+='<i class="'+p.icon+'"></i><span>'+p.label+'</span>';
      if(p.remote)html+='<i class="fas fa-house remote-dot" title="Remote jobs"></i>';
      html+='</a>';
    });
    html+='</div>';
  });
  html+='</div>';
  container.innerHTML=html;
}

function renderHomePagePlatforms(){
  var container=document.getElementById('platformsGrid');
  if(!container) return;
  var html='';
  PLATFORM_GROUPS.forEach(function(group){
    html+='<div class="platform-group-title">'+group.title+'</div>';
    html+='<div class="platforms-grid">';
    group.items.forEach(function(p){
      html+='<a href="#" class="platform-pill" onclick="searchOnPlatform(\''+p.key+'\',\''+p.label+'\')" style="--platform-color:'+p.color+'">';
      html+='<i class="'+p.icon+'"></i> '+p.label;
      if(p.remote)html+=' <i class="fas fa-house remote-dot" title="Remote jobs"></i>';
      html+='</a>';
    });
    html+='</div>';
  });
  container.innerHTML=html;
}
function searchOnPlatform(platformKey, platformLabel){
  var query=document.getElementById('heroSearchInput').value.trim();
  if(!query){
    showToast('Please enter a job role first','error');
    document.getElementById('heroSearchInput').focus();
    return;
  }
  showToast('Opening '+platformLabel+' for "'+query+'"...','success');
  // Fetch platform URLs and redirect
  apiCall('/api/search',{method:'POST',body:JSON.stringify({query:query})}).then(function(data){
    var url=data.platform_urls[platformKey];
    if(url){
      window.open(url,'_blank');
    }else{
      showToast('Platform URL not available','error');
    }
  }).catch(function(){
    showToast('Failed to get platform URL','error');
  });
}

function sortGuides(){
  if(currentGuides && currentGuides.related_guides){
    renderGuides(currentGuides);
  }
}

// Initialize home page platforms on load
if(document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', renderHomePagePlatforms);
} else {
  renderHomePagePlatforms();
}

function saveGuide(guideStr){
  var guide=JSON.parse(guideStr);
  apiCall('/api/dashboard/save-job',{method:'POST',body:JSON.stringify({guide:guide})}).then(function(){
    showToast('Guide saved!');
  }).catch(function(){showToast('Failed to save','error');});
}

/* ─── Resume Analysis ─────────────────────────────────────────────── */
var uploadedFile=null;
function handleFileUpload(input){
  if(input.files&&input.files[0]){
    uploadedFile=input.files[0];
    showToast('File "'+uploadedFile.name+'" selected');
  }
}

var ua=document.getElementById('uploadArea');
if(ua){
  ua.addEventListener('dragover',function(e){e.preventDefault();ua.classList.add('dragover');});
  ua.addEventListener('dragleave',function(){ua.classList.remove('dragover');});
  ua.addEventListener('drop',function(e){
    e.preventDefault();ua.classList.remove('dragover');
    if(e.dataTransfer.files.length){uploadedFile=e.dataTransfer.files[0];showToast('File "'+uploadedFile.name+'" selected');}
  });
  ua.addEventListener('click',function(){document.getElementById('resumeFile').click();});
}

async function analyzeResume(){
  var text=document.getElementById('resumeText').value.trim();
  var targetRole=document.getElementById('targetRole').value.trim();
  if(!text&&!uploadedFile){showToast('Please paste resume text or upload a file','error');return;}
  document.getElementById('resumeLoading').style.display='flex';
  document.getElementById('resumeResults').style.display='none';
  try{
    var fd=new FormData();
    if(uploadedFile)fd.append('resume_file',uploadedFile);
    if(text)fd.append('resume_text',text);
    if(targetRole)fd.append('target_role',targetRole);
        var r=await fetch(apiUrl('/api/analyze-resume'),{method:'POST',body:fd});
    var data=await r.json();
    if(data.error)throw new Error(data.error);
    currentResumeSkills=data.resume_skills||[];
    renderResumeResults(data,targetRole);
  }catch(e){showToast('Analysis failed: '+e.message,'error');}
  finally{document.getElementById('resumeLoading').style.display='none';}
}

function renderResumeResults(data,targetRole){
  var el=document.getElementById('resumeResults');
  el.style.display='block';
  var scoreColor=data.ats_score>=70?'var(--success)':data.ats_score>=40?'var(--warning)':'var(--danger)';
  var html='<div class="ats-score-section">'+
    '<div class="ats-score-circle" style="--score:'+data.ats_score+'">'+
    '<span class="ats-score-value" style="color:'+scoreColor+'">'+data.ats_score+'</span></div>'+
    '<div class="ats-score-label">Overall ATS Score / 100</div></div>';
  html+='<div class="analysis-grid"><div class="analysis-card"><h3><i class="fas fa-check-circle" style="color:var(--success)"></i> Strengths</h3><ul class="analysis-list">';
  (data.strengths||[]).forEach(function(s){html+='<li>'+s+'</li>';});
  html+='</ul></div>';
  html+='<div class="analysis-card"><h3><i class="fas fa-exclamation-triangle" style="color:var(--warning)"></i> Missing Items</h3><ul class="analysis-list">';
  (data.missing_items||[]).forEach(function(s){html+='<li>'+s+'</li>';});
  html+='</ul></div>';
  html+='<div class="analysis-card"><h3><i class="fas fa-code"></i> Skills Detected ('+data.resume_skills.length+')</h3><div class="skill-tags">';
  (data.resume_skills||[]).forEach(function(s){html+='<span class="skill-tag" style="background:rgba(99,102,241,0.15);color:var(--primary-light);border:1px solid rgba(99,102,241,0.2)">'+s+'</span>';});
  html+='</div></div>';
  html+='<div class="analysis-card"><h3><i class="fas fa-lightbulb" style="color:var(--accent)"></i> Improvement Suggestions</h3><ul class="analysis-list">';
  (data.suggestions||[]).forEach(function(s){html+='<li><strong>['+s.priority+'] '+s.section+':</strong> '+s.improvement+'</li>';});
  html+='</ul></div></div>';
  if(data.skill_gap&&data.skill_gap.target_role){
    var sg=data.skill_gap;
    html+='<div class="analysis-card" style="margin-bottom:24px"><h3><i class="fas fa-chart-bar"></i> Skill Gap for '+sg.target_role+'</h3>'+
      '<p style="margin-bottom:8px">Match: <strong>'+sg.match_percentage+'%</strong></p>'+
      '<div class="progress-bar"><div class="progress-fill" style="width:'+sg.match_percentage+'%"></div></div>'+
      '<h4 style="margin:12px 0 8px;font-size:0.9rem">Possessed:</h4><div class="skill-tags">';
    (sg.possessed||[]).forEach(function(s){html+='<span class="skill-tag" style="background:rgba(16,185,129,0.15);color:var(--success);border:1px solid rgba(16,185,129,0.2)">'+s+'</span>';});
    html+='</div><h4 style="margin:12px 0 8px;font-size:0.9rem">Missing:</h4><div class="skill-tags">';
    (sg.missing||[]).forEach(function(s){html+='<span class="skill-tag" style="background:rgba(239,68,68,0.15);color:var(--danger);border:1px solid rgba(239,68,68,0.2)">'+s+'</span>';});
    html+='</div></div>';
  }
  html+='<div class="analysis-card" style="margin-bottom:24px"><h3><i class="fas fa-list-check"></i> Sections Detected</h3><ul class="analysis-list">';
  Object.keys(data.sections_detected||{}).forEach(function(k){
    var v=data.sections_detected[k];
    html+='<li style="color:'+(v?'var(--success)':'var(--danger)')+'">'+(v?'✓':'✗')+' '+k.charAt(0).toUpperCase()+k.slice(1)+'</li>';
  });
  html+='</ul></div>';
  el.innerHTML=html;
  showToast('Resume analyzed! ATS Score: '+data.ats_score+'/100');
}

/* ─── Adaptive Interview System (chat-style) ────────────────────── */
var interviewSession = null;
var interviewProcessing = false;

function interviewQuestionText(q) {
    if (!q) return 'Please tell me more about yourself and your background.';
    if (typeof q === 'string') return q;
    return q.question || 'Please tell me more about yourself and your background.';
}

async function startAdaptiveInterview() {
    var role = document.getElementById('interviewRole').value.trim();
    if (!role) { showToast('Please enter a target role', 'error'); return; }
    var company = document.getElementById('interviewCompany').value.trim();
    var level = document.getElementById('interviewLevel').value;
    var mode = document.getElementById('interviewMode').value;
    var jd = document.getElementById('interviewJD').value.trim();
    var requiredSkills = document.getElementById('interviewRequiredSkills').value.split(',').map(function(s){return s.trim()}).filter(Boolean);
    var btn = document.getElementById('startInterviewBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
    try {
        var inputField = document.getElementById('interviewResumeContext');
        var resumeText = inputField.value.trim();
        var resumeContext = {};
        if (resumeText) {
            resumeContext = { text: resumeText };
        } else {
            var autoResume = document.getElementById('resumeText');
            if (autoResume && autoResume.value && autoResume.value.trim()) {
                resumeContext = { text: autoResume.value.trim() };
            }
        }
        var jobContext = {};
        if (jd) jobContext = { title: role, description: jd, analyzed: true };
        var payload = { role: role, company: company, experience_level: level, interview_mode: mode, job_context: jobContext, required_skills: requiredSkills, resume_context: resumeContext };
        var data = await apiCall('/api/interview-prep/start', { method: 'POST', body: JSON.stringify(payload) });
        interviewSession = { sessionId: data.session_id, turn: data.turn || 0, conversation: [] };
        document.getElementById('interviewSetupPanel').style.display = 'none';
        document.getElementById('interviewChatPanel').style.display = 'block';
        document.getElementById('interviewReportPanel').style.display = 'none';
        document.getElementById('interviewChatMessages').innerHTML = '';
        document.getElementById('interviewTurnCounter').textContent = 'Turn: ' + (interviewSession.turn);
        document.getElementById('interviewStatus').textContent = 'Active';
        document.getElementById('interviewStatus').className = 'chat-status';
        var first = interviewQuestionText(data.question);
        appendInterviewerMessage(first);
        interviewSession.conversation.push({ role: 'interviewer', content: first });
        inputField.disabled = false;
        document.getElementById('interviewAnswerInput').disabled = false;
        document.getElementById('interviewAnswerInput').focus();
        if (data.llm_available) { showToast('Local LLM connected', 'success'); }
    } catch (e) {
        showToast('Failed to start interview: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-play-circle"></i> Start Interview';
    }
}
function appendInterviewerMessage(text) {
    var c = document.getElementById('interviewChatMessages');
    var d = document.createElement('div');
    d.className = 'chat-msg chat-msg-ai';
    d.innerHTML = '<div class="msg-avatar"><i class="fas fa-robot"></i></div><div class="msg-content">' + escapeHtml(text || '') + '</div>';
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}

function appendCandidateMessage(text) {
    var c = document.getElementById('interviewChatMessages');
    var d = document.createElement('div');
    d.className = 'chat-msg chat-msg-user';
    d.innerHTML = '<div class="msg-avatar"><i class="fas fa-user"></i></div><div class="msg-content">' + escapeHtml(text) + '</div>';
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}

function appendEvaluationCard(ev) {
    // Numbers stay in the final report; here we surface the LLM's
    // answer-specific feedback (reason/strengths/weaknesses) so the chat
    // never repeats the same boilerplate ack on every turn.
    if (!ev) return;
    var reason = (ev.reason || ev.reasoning || '').trim();
    var strengths = ev.strengths || [];
    var weaknesses = ev.weaknesses || ev.missing_topics || [];
    var html = '';
    if (reason) { html += '<div class="eval-reason">' + escapeHtml(reason) + '</div>'; }
    if (strengths.length) {
        html += '<div class="eval-tags">' + strengths.slice(0, 3).map(function(s) {
            return '<span class="tag tag-green">' + escapeHtml(String(s)) + '</span>';
        }).join('') + '</div>';
    }
    if (weaknesses.length) {
        html += '<div class="eval-tags">' + weaknesses.slice(0, 3).map(function(s) {
            return '<span class="tag tag-red">' + escapeHtml(String(s)) + '</span>';
        }).join('') + '</div>';
    }
    if (!html) { return; }
    var c = document.getElementById('interviewChatMessages');
    var d = document.createElement('div');
    d.className = 'chat-msg chat-msg-ai';
    d.innerHTML = '<div class="msg-avatar"><i class="fas fa-clipboard-check"></i></div><div class="msg-content eval-ack">' + html + '</div>';
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}
function appendThinkingBubble() {
    var c = document.getElementById('interviewChatMessages');
    var d = document.createElement('div');
    d.id = 'interviewThinking';
    d.className = 'chat-msg chat-msg-ai';
    d.innerHTML = '<div class="msg-avatar"><i class="fas fa-robot"></i></div><div class="msg-content"><i class="fas fa-spinner fa-spin"></i> Thinking...</div>';
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}

function removeThinkingBubble() {
    var t = document.getElementById('interviewThinking');
    if (t) t.remove();
}

async function sendInterviewAnswer() {
    if (interviewProcessing || !interviewSession) { return; }
    var input = document.getElementById('interviewAnswerInput');
    var answer = input.value.trim();
    if (!answer) { showToast('Please enter an answer', 'error'); return; }
    var btn = document.getElementById('sendAnswerBtn');
    interviewProcessing = true;
    btn.disabled = true;
    input.disabled = true;
    appendCandidateMessage(answer);
    interviewSession.conversation.push({ role: 'candidate', content: answer });
    input.value = '';
    appendThinkingBubble();
    try {
        var payload = { session_id: interviewSession.sessionId, answer: answer };
        var data = await apiCall('/api/interview-prep/answer', { method: 'POST', body: JSON.stringify(payload) });
        removeThinkingBubble();
        interviewSession.turn = data.turn;
        document.getElementById('interviewTurnCounter').textContent = 'Turn: ' + data.turn;
        appendEvaluationCard(data.evaluation);
        if (data.next_question && data.next_question.question) {
            appendInterviewerMessage(data.next_question.question);
            interviewSession.conversation.push({ role: 'interviewer', content: data.next_question.question });
        }
        if (data.should_continue === false) {
            document.getElementById('interviewStatus').textContent = 'Completed';
            showToast('Interview complete. Click End to see your report.', 'success');
        }
    } catch (e) {
        removeThinkingBubble();
        showToast('Send failed: ' + e.message + '. Your answer was kept - please retry.', 'error');
        input.value = answer;
    } finally {
        interviewProcessing = false;
        btn.disabled = false;
        input.disabled = false;
        input.focus();
    }
}
async function endAdaptiveInterview() {
    if (!interviewSession) { showToast('No active interview', 'error'); return; }
    var btn = document.querySelector('.interview-chat-header .btn-danger');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; }
    try {
        var data = await apiCall('/api/interview-prep/end', { method: 'POST', body: JSON.stringify({ session_id: interviewSession.sessionId }) });
        document.getElementById('interviewChatPanel').style.display = 'none';
        document.getElementById('interviewReportPanel').style.display = 'block';
        renderInterviewReport(data.summary || {});
    } catch (e) {
        showToast('Failed to end interview: ' + e.message, 'error');
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-stop"></i> End'; }
    }
}

function handleInterviewKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendInterviewAnswer();
    }
}

function renderInterviewReport(summary) {
    var container = document.getElementById('interviewReportContent');
    summary = summary || {};
    var score = summary.overall_score || 0;
    var scoreClass = score >= 70 ? 'score-high' : score >= 40 ? 'score-medium' : 'score-low';
    var html = '<div class="report-score-section">';
    html += '<div class="report-score ' + scoreClass + '">' + score + '</div>';
    html += '<div class="report-score-label">Overall Score</div></div>';
    html += '<div class="report-section"><h4>Interview Stats</h4><div class="report-grid">';
    html += '<div class="report-stat"><span class="stat-label">Questions Asked</span><span class="stat-value">' + (summary.questions_asked || 0) + '</span></div>';
    html += '<div class="report-stat"><span class="stat-label">Turns</span><span class="stat-value">' + (summary.turn_count || 0) + '</span></div>';
    html += '<div class="report-stat"><span class="stat-label">Difficulty</span><span class="stat-value">' + (summary.difficulty || 'N/A') + '</span></div>';
    html += '<div class="report-stat"><span class="stat-label">Average Score</span><span class="stat-value">' + (summary.average_score != null ? summary.average_score : 'N/A') + '</span></div>';
    html += '</div></div>';
    if (summary.skills_covered && summary.skills_covered.length) {
        html += '<div class="report-section"><h4>Skills Tested</h4><div class="tag-list">';
        (summary.skills_covered || []).forEach(function(s) { html += '<span class="tag">' + escapeHtml(s) + '</span>'; });
        html += '</div></div>';
    }
    var strengths = summary.strengths || summary.strong_areas || [];
    if (strengths.length) {
        html += '<div class="report-section"><h4>Strong Areas</h4><div class="tag-list">';
        strengths.forEach(function(s) { html += '<span class="tag tag-green">' + escapeHtml(s) + '</span>'; });
        html += '</div></div>';
    }
    var weaknesses = summary.weaknesses || summary.weak_areas || [];
    if (weaknesses.length) {
        html += '<div class="report-section"><h4>Areas to Improve</h4><div class="tag-list">';
        weaknesses.forEach(function(s) { html += '<span class="tag tag-red">' + escapeHtml(s) + '</span>'; });
        html += '</div></div>';
    }
    var recs = summary.recommendations || summary.preparation_recommendations || [];
    if (recs.length) {
        html += '<div class="report-section"><h4>Preparation Recommendations</h4><ul class="report-list" style="padding-left:20px;line-height:1.9">';
        recs.forEach(function(r) { html += '<li>' + escapeHtml(r) + '</li>'; });
        html += '</ul></div>';
    }
    html += '<div class="report-section" style="text-align:center;margin-top:20px">';
    html += '<button class="btn btn-primary" onclick="resetInterview()"><i class="fas fa-redo"></i> Start New Interview</button>';
    html += '</div>';
    container.innerHTML = html;
}

function resetInterview() {
    interviewSession = null;
    interviewProcessing = false;
    document.getElementById('interviewSetupPanel').style.display = 'block';
    document.getElementById('interviewChatPanel').style.display = 'none';
    document.getElementById('interviewReportPanel').style.display = 'none';
    document.getElementById('interviewChatMessages').innerHTML = '';
    document.getElementById('interviewAnswerInput').value = '';
    var endBtn = document.querySelector('.interview-chat-header .btn-danger');
    if (endBtn) { endBtn.disabled = false; endBtn.innerHTML = '<i class="fas fa-stop"></i> End'; }
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ─── Career Insights ─────────────────────────────────────────────── *//* ─── Career Insights ─────────────────────────────────────────────── */
async function loadCareerInsights(){
  var role=document.getElementById('careerRoleInput').value.trim();
  if(!role){showToast('Enter a role','error');return;}
  document.getElementById('careerLoading').style.display='flex';
  document.getElementById('careerResults').style.display='none';
  try{
    var data=await apiCall('/api/career-insights',{method:'POST',body:JSON.stringify({role:role})});
    renderCareerInsights(data);
  }catch(e){showToast('Failed: '+e.message,'error');}
  finally{document.getElementById('careerLoading').style.display='none';}
}

function renderCareerInsights(data){
  var el=document.getElementById('careerResults');
  el.style.display='block';
  var ins=data.insights;
  var html='<h2 style="margin-bottom:24px">Career Insights: '+data.role+'</h2><div class="insights-grid">';
  html+='<div class="insight-card"><h3><i class="fas fa-dollar-sign"></i> Average Salary (USD)</h3><div class="insight-value">$'+ins.avg_salary_usd.toLocaleString()+'</div><div class="insight-label">Per year (US market)</div></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-rupee-sign"></i> Salary Range (INR)</h3><div class="insight-value">'+ins.avg_salary_inr+'</div><div class="insight-label">Per year (India)</div></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-fire"></i> Demand Level</h3><div class="insight-value">'+ins.demand_level+'</div><div class="insight-label">Current market demand</div></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-arrow-trend-up"></i> Growth Rate</h3><div class="insight-value">'+ins.growth_rate+'</div><div class="insight-label">Projected growth</div></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-chart-line"></i> Hiring Trend</h3><div class="insight-value" style="font-size:1rem">'+ins.hiring_trend+'</div></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-rocket"></i> Future Outlook</h3><div class="insight-value" style="font-size:1rem">'+ins.future_outlook+'</div></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-building"></i> Top Companies</h3><ul class="insight-list">';
  (ins.top_companies||[]).forEach(function(c){html+='<li>'+c+'</li>';});html+='</ul></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-industry"></i> Key Industries</h3><ul class="insight-list">';
  (ins.key_industries||[]).forEach(function(i){html+='<li>'+i+'</li>';});html+='</ul></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-graduation-cap"></i> Entry Level</h3><div class="insight-value" style="font-size:1.1rem">'+ins.entry_level_salary+'</div></div>';
  html+='<div class="insight-card"><h3><i class="fas fa-star"></i> Senior Level</h3><div class="insight-value" style="font-size:1.1rem">'+ins.senior_level_salary+'</div></div>';
  html+='</div>';
  el.innerHTML=html;
}

/* ─── Community Chat ─────────────────────────────────────────────── */
var chatPolicyData=null,chatPollTimer=null,chatFeedbackRating=0,chatFeedbackTag='';

async function loadChatPage(){
  document.getElementById('chatFeedbackBanner').style.display='block';
  try{
    var data=await apiCall('/api/chat/policy');
    chatPolicyData=data;
    if(data.is_banned){
      document.getElementById('chatPolicyScreen').style.display='block';
      document.getElementById('chatInterface').style.display='none';
      var pc=document.getElementById('policyContent');
      pc.innerHTML='<div class="chat-banned-message"><i class="fas fa-ban"></i><h3>Access Denied</h3><p>'+(data.ban_reason||'You have been banned from the community chat.')+'</p></div>';
      document.getElementById('policyDisclaimer').innerHTML='';
      document.getElementById('acceptPolicyBtn').style.display='none';
      return;
    }
    if(data.has_accepted){
      showChatInterface();
    }else{
      renderChatPolicy(data.policy);
      document.getElementById('chatPolicyScreen').style.display='block';
      document.getElementById('chatInterface').style.display='none';
    }
  }catch(e){
    document.getElementById('chatPolicyScreen').style.display='block';
    document.getElementById('chatInterface').style.display='none';
    var pc=document.getElementById('policyContent');
    pc.innerHTML='<div class="chat-banned-message"><i class="fas fa-exclamation-triangle"></i><h3>Login Required</h3><p>Please <a href="/login" style="color:var(--primary-light);text-decoration:underline">login</a> or <a href="/signup" style="color:var(--primary-light);text-decoration:underline">create an account</a> to access the community chat.</p></div>';
    document.getElementById('policyDisclaimer').innerHTML='';
    document.getElementById('acceptPolicyBtn').style.display='none';
  }
}

function renderChatPolicy(policy){
  var pc=document.getElementById('policyContent');
  if(!pc)return;
  var html='';
  (policy.sections||[]).forEach(function(s){
    html+='<div class="policy-item"><div class="policy-item-icon"><i class="fas '+s.icon+'"></i></div><div class="policy-item-body"><h4>'+s.title+'</h4><p>'+s.content+'</p></div></div>';
  });
  pc.innerHTML=html;
  var pd=document.getElementById('policyDisclaimer');
  if(pd&&policy.disclaimer)pd.innerHTML='<i class="fas fa-exclamation-circle"></i> '+policy.disclaimer;
}

async function acceptChatPolicy(){
  var btn=document.getElementById('acceptPolicyBtn');
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Accepting...';
  try{
    await apiCall('/api/chat/accept-policy',{method:'POST'});
    showToast('Welcome to the JobAgent Community!');
    showChatInterface();
  }catch(e){
    showToast('Failed to accept policy: '+e.message,'error');
    btn.disabled=false;btn.innerHTML='<i class="fas fa-check-circle"></i> I Agree & Accept';
  }
}

function showChatInterface(){
  document.getElementById('chatPolicyScreen').style.display='none';
  document.getElementById('chatInterface').style.display='block';
  loadChatMessages();
  loadChatMembers();
  startChatPolling();
}

function showPolicyAgain(){
  if(chatPolicyData&&chatPolicyData.policy){
    renderChatPolicy(chatPolicyData.policy);
  }
  document.getElementById('chatPolicyScreen').style.display='block';
  document.getElementById('chatInterface').style.display='none';
  stopChatPolling();
}

async function loadChatMessages(){
  try{
    var data=await apiCall('/api/chat/messages');
    if(data.success){
      document.getElementById('chatMessages').innerHTML='';
      data.messages.forEach(function(m){appendChatMessage(m,false);});
      var oc=document.getElementById('chatOnlineCount');
      if(oc)oc.textContent=data.online_count||0;
      scrollChatToBottom();
    }
  }catch(e){console.error('Failed to load messages:',e);}
}

function appendChatMessage(m,isNew){
  var box=document.getElementById('chatMessages');
  if(!box)return;
  var isOwn=m.user_id===undefined?false:false;
  // Check if current user's message via auth check
  apiCall('/api/auth/check').then(function(auth){
    isOwn=auth.authenticated&&auth.user.id===m.user_id;
    renderMessage(m,isOwn,box);
  }).catch(function(){
    renderMessage(m,false,box);
  });
}

function renderMessage(m,isOwn,box){
  var msgClass=isOwn?'chat-message chat-message-own':'chat-message';
  var typeClass=m.message_type==='system'?'chat-message-system':m.message_type==='feedback'?'chat-message-feedback':'';
  var time=m.created_at?new Date(m.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'';
  var initials=(m.username||'?').charAt(0).toUpperCase();
  var html='<div class="'+msgClass+' '+typeClass+'">';
  if(m.message_type!=='system'){
    html+='<div class="chat-avatar" style="background:'+getAvatarColor(m.username||'')+'">'+initials+'</div>';
    html+='<div class="chat-message-content"><div class="chat-message-meta"><span class="chat-message-username">'+escHtml(m.username||'Unknown')+'</span><span class="chat-message-time">'+time+'</span></div>';
    html+='<div class="chat-message-bubble">'+escHtml(m.message)+'</div></div>';
  }else{
    html+='<div class="chat-system-message"><i class="fas fa-bell"></i> '+escHtml(m.message)+'</div>';
  }
  html+='</div>';
  box.insertAdjacentHTML('beforeend',html);
  scrollChatToBottom();
}

function getAvatarColor(name){
  var colors=['#6366f1','#06b6d4','#f59e0b','#10b981','#ef4444','#8b5cf6','#ec4899'];
  var hash=0;
  for(var i=0;i<name.length;i++)hash=name.charCodeAt(i)+((hash<<5)-hash);
  return colors[Math.abs(hash)%colors.length];
}

function escHtml(str){
  var div=document.createElement('div');
  div.textContent=str;
  return div.innerHTML;
}

async function sendChatMessage(){
  var input=document.getElementById('chatMessageInput');
  var msg=input.value.trim();
  if(!msg){showToast('Type a message first','error');return;}
  if(msg.length>1000){showToast('Message too long (max 1000 chars)','error');return;}
  var btn=document.getElementById('sendChatBtn');
  btn.disabled=true;
  try{
    var data=await apiCall('/api/chat/send',{method:'POST',body:JSON.stringify({message:msg})});
    if(data.success){
      input.value='';
      // Re-fetch messages to show in context
      loadChatMessages();
      showToast('Message sent!');
    }
  }catch(e){
    showToast('Failed to send: '+e.message,'error');
  }
  finally{btn.disabled=false;}
}

function insertQuickTag(tag){
  var input=document.getElementById('chatMessageInput');
  if(!input)return;
  var current=input.value.trim();
  input.value=current?(current+' '+tag+' '):(tag+' ');
  input.focus();
}

async function loadChatMembers(){
  try{
    var data=await apiCall('/api/chat/users');
    if(data.success){
      var list=document.getElementById('chatMembersList');
      var count=document.getElementById('chatMemberCount');
      if(count)count.textContent=data.count||0;
      if(list){
        if(!data.users.length){
          list.innerHTML='<div class="chat-empty-members"><i class="fas fa-users"></i><p>No members yet</p></div>';
        }else{
          list.innerHTML=data.users.map(function(u){
            var initials=(u.username||'?').charAt(0).toUpperCase();
            return '<div class="chat-member"><div class="chat-avatar chat-avatar-sm" style="background:'+getAvatarColor(u.username)+'">'+initials+'</div><div class="chat-member-info"><div class="chat-member-name">'+escHtml(u.username)+'</div><div class="chat-member-status">Online</div></div></div>';
          }).join('');
        }
      }
    }
  }catch(e){console.error('Failed to load members:',e);}
}

function startChatPolling(){
  stopChatPolling();
  chatPollTimer=setInterval(function(){
    if(document.getElementById('page-chat').classList.contains('active')){
      loadChatMessages();
      loadChatMembers();
    }
  },5000);
}

function stopChatPolling(){
  if(chatPollTimer){clearInterval(chatPollTimer);chatPollTimer=null;}
}

function scrollChatToBottom(){
  var box=document.getElementById('chatMessages');
  if(box)box.scrollTop=box.scrollHeight;
}

/* Feedback Modal */
function openFeedbackModal(){
  document.getElementById('feedbackModal').style.display='flex';
}
function closeFeedbackModal(){
  document.getElementById('feedbackModal').style.display='none';
}
function setFeedbackRating(r){
  chatFeedbackRating=r;
  var stars=document.querySelectorAll('#feedbackRatingStars i');
  stars.forEach(function(s){
    if(parseInt(s.getAttribute('data-rating'))<=r){
      s.classList.add('active');
    }else{
      s.classList.remove('active');
    }
  });
}
function setFeedbackTag(el,tag){
  chatFeedbackTag=tag;
  document.querySelectorAll('.feedback-tag').forEach(function(t){t.classList.remove('active');});
  el.classList.add('active');
}
async function submitChatFeedback(){
  var comment=document.getElementById('feedbackComment').value.trim();
  if(!comment){showToast('Please write your feedback','error');return;}
  var btn=document.getElementById('submitFeedbackBtn');
  btn.disabled=true;btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> Submitting...';
  try{
    var data=await apiCall('/api/chat/feedback',{method:'POST',body:JSON.stringify({feedback:comment})});
    if(data.success){
      closeFeedbackModal();
      document.getElementById('feedbackComment').value='';
      chatFeedbackRating=0;chatFeedbackTag='';
      document.querySelectorAll('#feedbackRatingStars i').forEach(function(s){s.classList.remove('active');});
      document.querySelectorAll('.feedback-tag').forEach(function(t){t.classList.remove('active');});
      showToast(data.message||'Thank you for your feedback!');
      loadChatMessages();
    }
  }catch(e){
    showToast('Failed to submit: '+e.message,'error');
  }finally{
    btn.disabled=false;btn.innerHTML='<i class="fas fa-paper-plane"></i> Submit Feedback';
  }
}

/* ─── Dashboard ───────────────────────────────────────────────────── */
async function loadDashboard(){
  try{
    var data=await apiCall('/api/dashboard');
    renderDashboard(data);
  }catch(e){console.error('Dashboard error:',e);}
}

var savedGuidesCache=[],searchHistoryCache=[];
function renderDashboard(data){
  var stats=document.getElementById('dashboardStats');
  var grid=document.getElementById('dashboardGrid');
  savedGuidesCache=data.saved_jobs||[];
  var hist=data.search_history||[];
  searchHistoryCache=hist.slice(-10).reverse();
  var ats=data.ats_scores||[];
  stats.innerHTML=[
    {icon:'fa-bookmark',color:'var(--primary)',val:savedGuidesCache.length,label:'Saved Guides'},
    {icon:'fa-file-alt',color:'var(--secondary)',val:ats.length,label:'Resumes Analyzed'},
    {icon:'fa-chart-line',color:'var(--accent)',val:Object.keys(data.skill_progress||{}).length,label:'Skills Tracked'},
    {icon:'fa-search',color:'var(--success)',val:hist.length,label:'Searches'}
  ].map(function(s){
    return '<div class="stat-card"><div class="stat-icon" style="background:'+s.color+'22;color:'+s.color+'"><i class="fas '+s.icon+'"></i></div><div class="stat-value">'+s.val+'</div><div class="stat-label">'+s.label+'</div></div>';
  }).join('');

  /* Saved role guides - click to reopen the full guide on the Role Guide page */
  var html='<div class="dashboard-section"><h3><i class="fas fa-bookmark"></i> Saved Role Guides</h3>';
  if(!savedGuidesCache.length)html+='<div class="empty-state"><i class="fas fa-bookmark"></i><p>No saved guides yet</p></div>';
  else savedGuidesCache.forEach(function(j,i){
    html+='<div class="dashboard-job-item clickable" title="Click to reopen this guide" onclick="openSavedGuide('+i+')"><div class="dashboard-job-info"><div class="dashboard-job-title">'+(j.role_title||'')+'</div><div class="dashboard-job-company">Saved '+(j.saved_date||'')+' &middot; click to reopen</div></div><i class="fas fa-arrow-right item-arrow"></i></div>';
  });
  html+='</div>';

  /* ATS history - click to open the Resume analyzer */
  html+='<div class="dashboard-section"><h3><i class="fas fa-chart-line"></i> ATS Score History</h3>';
  if(!ats.length)html+='<div class="empty-state"><i class="fas fa-chart-line"></i><p>No analyses yet</p></div>';
  else ats.forEach(function(a){
    html+='<div class="dashboard-job-item clickable" title="Click to open the Resume Analyzer" onclick="showPage(\'resume\')"><div class="dashboard-job-info"><div class="dashboard-job-title">Score: '+a.score+'/100</div><div class="dashboard-job-company">'+a.role+' - '+a.date+'</div></div><span class="match-badge '+(a.score>=70?'match-high':a.score>=40?'match-medium':'match-low')+'">'+a.score+'</span></div>';
  });
  html+='</div>';

  /* Search history - click to run the search again */
  html+='<div class="dashboard-section"><h3><i class="fas fa-search"></i> Search History</h3>';
  if(!hist.length)html+='<div class="empty-state"><i class="fas fa-search"></i><p>No searches yet</p></div>';
  else searchHistoryCache.forEach(function(s,i){
    html+='<div class="dashboard-job-item clickable" title="Click to run this search again" onclick="reopenSearch('+i+')"><div class="dashboard-job-info"><div class="dashboard-job-title">'+s.query+'</div><div class="dashboard-job-company">'+s.date+' &middot; click to search again</div></div><i class="fas fa-arrow-right item-arrow"></i></div>';
  });
  html+='</div>';

  /* Skill progress - click to open Career insights */
  html+='<div class="dashboard-section"><h3><i class="fas fa-lightbulb"></i> Skill Progress</h3>';
  var sp=Object.keys(data.skill_progress||{});
  if(!sp.length)html+='<div class="empty-state"><i class="fas fa-lightbulb"></i><p>No skills tracked yet</p></div>';
  else sp.forEach(function(s){
    var p=data.skill_progress[s];
    html+='<div class="dashboard-job-item clickable" title="Click to open Career insights" onclick="showPage(\'career\')"><div class="dashboard-job-info"><div style="display:flex;justify-content:space-between;font-size:0.9rem;margin-bottom:4px"><span>'+s+'</span><span>'+p+'%</span></div><div class="progress-bar"><div class="progress-fill" style="width:'+p+'%"></div></div></div></div>';
  });
  html+='</div>';
  grid.innerHTML=html;
}

function openSavedGuide(i){
  var g=savedGuidesCache[i];if(!g)return;
  showPage('search');
  document.getElementById('resultsHeader').style.display='block';
  document.getElementById('resultsTitle').textContent='Saved Role Guide: '+(g.role_title||'');
  document.getElementById('resultsSubtitle').textContent='Reopened from your saved guides'+(g.saved_date?' (saved '+g.saved_date+')':'');
  var pc=document.getElementById('platformButtonsContainer');if(pc)pc.style.display='none';
  document.getElementById('guideGrid').innerHTML=renderGuideCard(g,true);
}

function reopenSearch(i){
  var s=searchHistoryCache[i];if(!s)return;
  showPage('search');
  document.getElementById('searchInput').value=s.query;
  performSearch();
}
/* ─── SPA deep-link routing ─────────────────────────────────────────
   Open the correct section when the app is loaded directly at a URL
   like /chat, /dashboard, /resume, etc. (client-side sections live in
   index.html served as a single-page app). */
(function initPageFromUrl(){
  var seg = window.location.pathname.replace(/^\/+|\/+$/g, '').split('/')[0];
  var valid = ['home','search','resume','interview','career','dashboard','chat'];
  if (seg && valid.indexOf(seg) !== -1 && seg !== 'home') {
    showPage(seg);
  }
})();

var currentAuthUser = null;

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
    setTimeout(function() { window.location.href = '/login'; }, 900);
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
        var read = !!n.is_read;
        html += '<div class="notif-item"' + (read ? ' style="opacity:0.55"' : '') + ' onclick="markNotificationRead(' + n.id + ', ' + JSON.stringify(JSON.stringify(n.link_url || '')) + ', this)">';
        html += '<div class="notif-icon ' + notifIconClass(n.type) + '"><i class="fas ' + notifIcon(n.type) + '"></i></div>';
        html += '<div class="notif-body"><div class="notif-title">' + escapeHtml(n.title || '') + '</div>';
        html += '<div class="notif-message">' + escapeHtml(n.message || '') + '</div>';
        html += '<div class="notif-time">' + escapeHtml(when) + '</div></div>';
        if (!read) html += '<span class="notif-dot"></span>';
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
