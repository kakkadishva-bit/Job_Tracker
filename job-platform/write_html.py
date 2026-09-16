import os

html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PreciousMetals AI</title>
<script src="https://cdn.tailwindcss.com"><\/script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"><\/script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Inter,sans-serif;background:#0a0b0e;color:#e9ecef;min-height:100vh}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:#121318}::-webkit-scrollbar-thumb{background:#343a40;border-radius:3px}
.glass{background:rgba(26,28,35,0.7);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.05)}
.glass2{background:rgba(34,38,48,0.5);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.08)}
.btn{background:linear-gradient(135deg,#d4a017,#b8860b);color:#fff;border:none;cursor:pointer;padding:8px 16px;border-radius:8px;font-size:13px}
.btn:hover{background:linear-gradient(135deg,#ffc107,#d4a017)}
input,select{background:#1a1c23;border:1px solid #343a40;color:#e9ecef;border-radius:8px;padding:8px 12px}
input:focus,select:focus{outline:none;border-color:#d4a017}
.tab{padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;background:transparent;border:none;color:#adb5bd;transition:all .2s}
.tab.active{background:rgba(212,160,23,0.2);color:#ffc107}
.tab:hover:not(.active){background:rgba(255,255,255,0.05);color:#e9ecef}
.card{transition:transform .2s,box-shadow .2s}.card:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,0,0,0.3)}
.spin{border:3px solid #1a1c23;border-top:3px solid #ffc107;border-radius:50%;width:40px;height:40px;animation:sp 1s linear infinite;margin:80px auto}
@keyframes sp{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.fade{animation:fadeIn .3s ease}
@keyframes pulse{0%,100%{box-shadow:0 0 5px rgba(212,160,23,0.3)}50%{box-shadow:0 0 20px rgba(212,160,23,0.6)}}
.pulse{animation:pulse 2s infinite}
.nav-btn{display:flex;align-items:center;gap:10px;width:100%;padding:12px 16px;font-size:14px;background:transparent;border:none;color:#adb5bd;cursor:pointer;transition:all .2s;text-align:left}
.nav-btn:hover{background:rgba(212,160,23,0.1);color:#fff}
.nav-btn.active{background:rgba(212,160,23,0.15);border-right:3px solid #ffc107;color:#ffc107}
select option{background:#1a1c23;color:#e9ecef}
</style>
</head>
<body>
<div id="app"></div>
<script>
var PAGE="dashboard",ASSET=null,ASSETS=[],OVERVIEW=null,ASSET_DATA=null,CHART_DATA=null,INSIGHT=null,PORTFOLIOS=[],WATCHLISTS=[],NEWS=[],CONFIG=null,STATS=null,CHART_TYPE="line",TIME_RANGE="1Y",TAB="all",FILTER="",COMPARE_SEL=[],COMPARE_DATA=null,LOADING=false,ASSET_TAB="overview",NEWS_FILTER="",TYPE_FILTER="",RISK_FILTER="";

function $(s){return document.querySelector(s)}
function api(url,opts){var o={headers:{"Content-Type":"application/json"}};if(opts){for(var k in opts)o[k]=opts[k]}return fetch(url,o).then(function(r){return r.json()}).catch(function(e){console.error(e);return null})}
function fmtC(v){return v!=null?"\\u20B9"+Number(v).toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2}):"-"}
function fmtP(v){return v!=null?(v>=0?"+":"")+Number(v).toFixed(2)+"%":"-"}
function fmtV(v){if(v==null)return"-";if(v>=10000000)return(v/10000000).toFixed(2)+" Cr";if(v>=100000)return(v/100000).toFixed(2)+" L";if(v>=1000)return(v/1000).toFixed(1)+" K";return String(v)}
function fmtD(v){return v?new Date(v).toLocaleString("en-IN"):"-"}
function cC(v){return v>0?"color:#4ade80":v<0?"color:#f87171":"color:#9ca3af"}
function rC(v){return v<4?"color:#4ade80":v<6?"color:#facc15":"color:#f87171"}
function rB(v){return v<4?"background:rgba(34,197,94,0.1);color:#4ade80":v<6?"background:rgba(250,204,21,0.1);color:#facc15":"background:rgba(248,113,113,0.1);color:#f87171"}
function tL(t){var m={gold_etf:"Gold ETF",silver_etf:"Silver ETF",commodity_etf:"Commodity ETF",mining_stock:"Mining Stock",special_stock:"Special Stock"};return m[t]||t}
function tB(t){var m={gold_etf:"background:rgba(250,204,21,0.1);color:#facc15",silver_etf:"background:rgba(156,163,175,0.1);color:#d1d5db",commodity_etf:"background:rgba(249,115,22,0.1);color:#fb923c",mining_stock:"background:rgba(59,130,246,0.1);color:#60a5fa",special_stock:"background:rgba(168,85,247,0.1);color:#c084fc"};return m[t]||""}
function rL(v){return v<4?"Low Risk":v<6?"Moderate Risk":"High Risk"}

var charts={};
function killCharts(){for(var k in charts){try{charts[k].destroy()}catch(e){}}charts={}}

function nav(p){PAGE=p;ASSET=null;render();loadData()}
function viewA(s){ASSET=s;PAGE="detail";render();loadAsset(s)}

function loadData(){
LOADING=true;render();
switch(PAGE){
case"dashboard":
Promise.all([api("/api/insights/market-overview"),api("/api/assets")]).then(function(d){OVERVIEW=d[0];ASSETS=d[1]?d[1].assets:[];LOADING=false;render()});break;
case"portfolio":
Promise.all([api("/api/portfolios"),api("/api/assets")]).then(function(d){PORTFOLIOS=d[0]?d[0].portfolios:[];ASSETS=d[1]?d[1].assets:[];LOADING=false;render()});break;
case"watchlist":
Promise.all([api("/api/watchlists"),api("/api/assets")]).then(function(d){WATCHLISTS=d[0]?d[0].watchlists:[];ASSETS=d[1]?d[1].assets:[];LOADING=false;render()});break;
case"news":
api("/api/news").then(function(d){NEWS=d?d.news:[];LOADING=false;render()});break;
case"search":case"compare":
api("/api/assets").then(function(d){ASSETS=d?d.assets:[];LOADING=false;render()});break;
case"admin":
Promise.all([api("/api/admin/stats"),api("/api/admin/assets")]).then(function(d){STATS=d[0];ASSETS=d[1]?d[1].assets:[];LOADING=false;render()});break;
case"settings":
api("/api/config").then(function(d){CONFIG=d;LOADING=false;render()});break;
default:LOADING=false;render();
}}

function loadAsset(s){
LOADING=true;render();
Promise.all([api("/api/assets/"+s),api("/api/assets/"+s+"/chart-data?range="+TIME_RANGE),api("/api/insights/"+s)]).then(function(d){ASSET_DATA=d[0];CHART_DATA=d[1];INSIGHT=d[2];LOADING=false;render();initCharts()});
}

function render(){
killCharts();
var a=$("#app");a.innerHTML="";
var wrap=document.createElement("div");wrap.style.display="flex";wrap.style.minHeight="100vh";
wrap.appendChild(mkSidebar());
var main=document.createElement("div");main.style.flex="1";main.style.marginLeft="256px";main.style.minHeight="100vh";
main.appendChild(mkHeader());
var content=document.createElement("div");content.style.padding="24px";
if(LOADING){var sp=document.createElement("div");sp.className="spin";content.appendChild(sp)}
else{content.appendChild(mkPage())}
main.appendChild(content);main.appendChild(mkFooter());
wrap.appendChild(main);a.appendChild(wrap);
}

function el(tag,cls,style,text){
var e=document.createElement(tag);
if(cls)e.className=cls;
if(style)Object.assign(e.style,typeof style==="string"?parseS(style):style);
if(text)e.textContent=text;
return e;
}
function parseS(s){var o={};s.split(";").forEach(function(p){var kv=p.split(":");if(kv.length>=2)o[kv[0].trim()]=kv.slice(1).join(":").trim()});return o}

function mkSidebar(){
var items=[["dashboard","\\uD83D\\uDCCA","Dashboard"],["search","\\uD83D\\uDD0D","Search"],["portfolio","\\uD83D\\uDCBC","Portfolio"],["watchlist","\\u2B50","Watchlist"],["compare","\\u2696\\uFE0F","Compare"],["news","\\uD83D\\uDCF0","News"],["admin","\\u2699\\uFE0F","Admin"],["settings","\\u2139\\uFE0F","Settings"]];
var aside=el("aside","glass");
Object.assign(aside.style,{width:"256px",minHeight:"100vh",position:"fixed",left:"0",top:"0",zIndex:"40",display:"flex",flexDirection:"column",borderRight:"1px solid rgba(255,255,255,0.05)"});
var logo=el("div","",{padding:"16px",borderBottom:"1px solid rgba(255,255,255,0.05)"});
var logoInner=el("div","",{display:"flex",alignItems:"center",gap:"10px"});
var pm=el("div","",{width:"32px",height:"32px",background:"linear-gradient(135deg,#d4a017,#ffc107)",borderRadius:"8px",display:"flex",alignItems:"center",justifyContent:"center",color:"#000",fontWeight:"700",fontSize:"12px"},"PM");
var txt=el("div");txt.appendChild(el("div","",{fontSize:"13px",fontWeight:"700",color:"#fff"},"PreciousMetals"));txt.appendChild(el("div","",{fontSize:"11px",color:"#ffc107"},"AI Platform"));
logoInner.appendChild(pm);logoInner.appendChild(txt);logo.appendChild(logoInner);aside.appendChild(logo);
var nav2=el("nav","",{flex:"1",padding:"8px 0"});
items.forEach(function(item){
var btn=document.createElement("button");btn.className="nav-btn"+(PAGE===item[0]?" active":"");
btn.onclick=(function(id){return function(){nav(id)}})(item[0]);
btn.appendChild(el("span","",{fontSize:"18px"},item[1]));btn.appendChild(el("span","",{},item[2]));
nav2.appendChild(btn);
});
aside.appendChild(nav2);
aside.appendChild(el("div","",{padding:"12px",borderTop:"1px solid rgba(255,255,255,0.05)",textAlign:"center",fontSize:"11px",color:"#6c757d"},"v1.0.0 \\u2022 PreciousMetals AI"));
return aside;
}

function mkHeader(){
var hd=el("header","glass");
Object.assign(hd.style,{position:"sticky",top:"0",zIndex:"30",padding:"12px 24px",display:"flex",alignItems:"center",justifyContent:"space-between",borderBottom:"1px solid rgba(255,255,255,0.05)"});
var si=document.createElement("div");si.style.flex="1";si.style.maxWidth="400px";si.style.margin="0 16px";
var inp=document.createElement("input");inp.type="text";inp.placeholder="Search assets...";inp.style.width="100%";inp.style.fontSize="13px";
inp.oninput=function(){if(this.value){PAGE="search";FILTER=this.value;render();api("/api/assets?search="+this.value).then(function(d){ASSETS=d?d.assets:[];render()})}};
si.appendChild(inp);hd.appendChild(si);
var right=el("div","",{display:"flex",alignItems:"center",gap:"12px"});
right.appendChild(el("span","",{fontSize:"12px",color:"#6c757d"},new Date().toLocaleDateString("en-IN",{weekday:"short",month:"short",day:"numeric"})));
var dot=el("div","",{width:"8px",height:"8px",borderRadius:"50%",background:"#4ade80"});dot.className="pulse";right.appendChild(dot);
hd.appendChild(right);return hd;
}

function mkFooter(){
var f=el("footer","",{padding:"16px 24px",borderTop:"1px solid rgba(255,255,255,0.05)"});
f.appendChild(el("p","",{fontSize:"11px",color:"#6c757d",textAlign:"center",maxWidth:"800px",margin:"0 auto"},"\\u26A0\\uFE0F This platform provides educational and informational content only and does not constitute financial advice. Investment decisions should be made after consulting a qualified financial advisor."));
return f;
}

function mkPage(){
switch(PAGE){
case"dashboard":return mkDashboard();
case"detail":return mkDetail();
case"portfolio":return mkPortfolio();
case"watchlist":return mkWatchlist();
case"news":return mkNews();
case"search":return mkSearch();
case"compare":return mkCompare();
case"admin":return mkAdmin();
case"settings":return mkSettings();
default:return mkDashboard();
}}

function mkLoader(){var d=el("div","",{textAlign:"center",padding:"80px 0"});d.appendChild(el("div","spin"));d.appendChild(el("p","",{color:"#adb5bd",fontSize:"13px",marginTop:"12px"},"Loading..."));return d}

function statCard(label,value,change,icon){
var d=el("div","glass card",{borderRadius:"12px",padding:"16px"});
var top=el("div","",{display:"flex",justifyContent:"space-between",marginBottom:"8px"});
top.appendChild(el("span","",{color:"#adb5bd",fontSize:"13px"},label));top.appendChild(el("span","",{fontSize:"18px"},icon));
d.appendChild(top);d.appendChild(el("div","",{fontSize:"20px",fontWeight:"700",color:"#fff"},String(value)));
if(change!=null)d.appendChild(el("div","",{fontSize:"13px",marginTop:"4px",color:change>0?"#4ade80":change<0?"#f87171":"#9ca3af"},fmtP(change)));
return d;
}

function aCard(a){
var d=el("div","glass card",{borderRadius:"12px",padding:"16px",cursor:"pointer"});
d.onclick=function(){viewA(a.symbol)};
var top=el("div","",{display:"flex",justifyContent:"space-between",marginBottom:"12px"});
var left=el("div");var sym=el("div","",{display:"flex",alignItems:"center",gap:"8px"});
sym.appendChild(el("span","",{fontWeight:"700",color:"#fff"},a.symbol));
sym.appendChild(el("span","",{fontSize:"11px",padding:"2px 8px",borderRadius:"12px",display:"inline-block"},tL(a.symbol===a.symbol?"":a.type)).outerHTML?el("span","",{},tL(a.type)):el("span"));
var tb=el("span","",{},tL(a.type));tb.style.cssText=tB(a.type);tb.style.fontSize="11px";tb.style.padding="2px 8px";tb.style.borderRadius="12px";
sym.appendChild(tb);
left.appendChild(sym);left.appendChild(el("p","",{color:"#adb5bd",fontSize:"12px",marginTop:"2px",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",maxWidth:"200px"},a.name));
top.appendChild(left);
var mid=el("div","",{display:"flex",justifyContent:"space-between",alignItems:"flex-end"});
var priceDiv=el("div");priceDiv.appendChild(el("div","",{fontSize:"22px",fontWeight:"700",color:"#fff"},fmtC(a.current_price)));
var chg=el("div","",{fontSize:"13px",fontWeight:"500"},fmtP(a.daily_change_pct));chg.style.cssText=cC(a.daily_change_pct);
priceDiv.appendChild(chg);mid.appendChild(priceDiv);
var right=el("div","",{textAlign:"right"});
var risk=el("span","",{fontSize:"11px",padding:"3px 8px",borderRadius:"12px",display:"inline-block"},rL(a.risk_score));risk.style.cssText=rB(a.risk_score);
right.appendChild(risk);right.appendChild(el("div","",{fontSize:"11px",color:"#6c757d",marginTop:"4px"},"Vol: "+fmtV(a.volume)));
mid.appendChild(right);top.appendChild(mid);d.appendChild(top);
var bar=el("div","",{marginTop:"12px"});
var barTop=el("div","",{display:"flex",justifyContent:"space-between",fontSize:"11px",color:"#6c757d",marginBottom:"4px"});
barTop.appendChild(el("span","",{},"52W Low: "+fmtC(a.week_52_low)));barTop.appendChild(el("span","",{},"52W High: "+fmtC(a.week_52_high)));
bar.appendChild(barTop);
var track=el("div","",{height:"6px",background:"#1a1c23",borderRadius:"3px",overflow:"hidden"});
var fill=el("div","",{height:"100%",background:"linear-gradient(135deg,#d4a017,#ffc107)",borderRadius:"3px",width:(a.price_position_52w||50)+"%"});
track.appendChild(fill);bar.appendChild(track);d.appendChild(bar);
return d;
}

function mkDashboard(){
if(!OVERVIEW)return mkLoader();
var o=OVERVIEW;var filtered=TAB==="all"?ASSETS:ASSETS.filter(function(a){return a.type===TAB});
var wrap=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
var hdr=el("div","",{display:"flex",alignItems:"center",justifyContent:"space-between"});
var hdrL=el("div");hdrL.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},"Dashboard"));
hdrL.appendChild(el("p","",{color:"#adb5bd",fontSize:"13px"},"Precious Metals & ETF Market Overview"));
hdr.appendChild(hdrL);
var ms=el("div","",{display:"flex",alignItems:"center",gap:"8px"});
var dot=el("div","",{width:"8px",height:"8px",borderRadius:"50%",background:o.market_status==="open"?"#4ade80":"#f87171"});
if(o.market_status==="open")dot.className="pulse";
ms.appendChild(dot);ms.appendChild(el("span","",{fontSize:"13px",color:"#adb5bd"},"Market "+(o.market_status==="open"?"Open":"Closed")));
hdr.appendChild(ms);wrap.appendChild(hdr);
var grid=el("div","",{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:"16px"});
grid.appendChild(statCard("Total Assets",o.summary.total_assets,null,"\\uD83D\\uDCCA"));
grid.appendChild(statCard("Gold ETF Avg",fmtP(o.summary.avg_gold_change),o.summary.avg_gold_change,"\\uD83E\\uDD47"));
grid.appendChild(statCard("Silver ETF Avg",fmtP(o.summary.avg_silver_change),o.summary.avg_silver_change,"\\uD83E\\uDD48"));
grid.appendChild(statCard("Mining Avg",fmtP(o.summary.avg_mining_change),o.summary.avg_mining_change,"\\u26CF\\uFE0F"));
wrap.appendChild(grid);
var lists=el("div","",{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:"16px"});
lists.appendChild(mkMiniList("\\uD83D\\uDCC8 Top Gainers",o.top_gainers,"#4ade80",true));
lists.appendChild(mkMiniList("\\uD83D\\uDCC9 Top Losers",o.top_losers,"#f87171",true));
lists.appendChild(mkMiniList("\\uD83D\\uDD25 Most Active",o.most_active,"#60a5fa",false));
wrap.appendChild(lists);
var tabs=el("div","",{display:"flex",gap:"8px",flexWrap:"wrap"});
[["all","All"],["gold_etf","Gold ETFs"],["silver_etf","Silver ETFs"],["commodity_etf","Commodity ETFs"],["mining_stock","Mining Stocks"],["special_stock","Special"]].forEach(function(t){
var b=document.createElement("button");b.className="tab"+(TAB===t[0]?" active":"");
b.onclick=(function(id){return function(){TAB=id;render()}})(t[0]);b.textContent=t[1];tabs.appendChild(b);
});
wrap.appendChild(tabs);
var ag=el("div","",{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(280px,1fr))",gap:"16px"});
filtered.forEach(function(a){ag.appendChild(aCard(a))});
wrap.appendChild(ag);
return wrap;
}

function mkMiniList(title,items,color,isChange){
var d=el("div","glass",{borderRadius:"12px",padding:"16px"});
d.appendChild(el("h3","",{fontSize:"13px",fontWeight:"600",color:color,marginBottom:"12px"},title));
if(items)items.forEach(function(a){
var row=el("div","",{display:"flex",justifyContent:"space-between",padding:"8px 0",borderBottom:"1px solid rgba(255,255,255,0.05)",cursor:"pointer"});
row.onclick=function(){viewA(a.symbol)};
row.appendChild(el("span","",{fontWeight:"600",color:"#fff",fontSize:"13px"},a.symbol));
var val=isChange?fmtP(a.change):fmtV(a.volume);
row.appendChild(el("span","",{fontSize:"13px",fontWeight:"500",color:color},val));
d.appendChild(row);
});
return d;
}

function mkDetail(){
if(!ASSET_DATA)return mkLoader();
var a=ASSET_DATA.asset,ti=ASSET_DATA.technical_indicators,f=ASSET_DATA.forecast;
var wrap=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
var hdr=el("div","",{display:"flex",alignItems:"center",gap:"16px"});
var back=document.createElement("button");back.textContent="\\u2190";back.style.cssText="background:none;border:none;color:#adb5bd;cursor:pointer;font-size:24px;padding:8px";
back.onclick=function(){PAGE="dashboard";ASSET=null;ASSET_TAB="overview";render();loadData()};
hdr.appendChild(back);
var info=el("div","",{flex:"1"});
var symRow=el("div","",{display:"flex",alignItems:"center",gap:"10px"});
symRow.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},a.symbol));
var tb=el("span","",{fontSize:"12px",padding:"3px 10px",borderRadius:"12px",display:"inline-block"},tL(a.type));tb.style.cssText=tB(a.type);
symRow.appendChild(tb);info.appendChild(symRow);info.appendChild(el("p","",{color:"#adb5bd"},a.name));
hdr.appendChild(info);
var pd=el("div","",{textAlign:"right"});
pd.appendChild(el("div","",{fontSize:"28px",fontWeight:"700",color:"#fff"},fmtC(a.current_price)));
var chg=el("div","",{fontSize:"18px",fontWeight:"500"},fmtP(a.daily_change_pct));chg.style.cssText=cC(a.daily_change_pct);
pd.appendChild(chg);hdr.appendChild(pd);wrap.appendChild(hdr);
var tabs2=el("div","",{display:"flex",gap:"8px",borderBottom:"1px solid rgba(255,255,255,0.05)",paddingBottom:"8px"});
["overview","risk","forecast","insights","news"].forEach(function(s){
var b=document.createElement("button");b.className="tab"+(ASSET_TAB===s?" active":"");b.style.textTransform="capitalize";b.textContent=s;
b.onclick=(function(sec){return function(){ASSET_TAB=sec;render();if(sec==="overview")setTimeout(initCharts,50)}})(s);
tabs2.appendChild(b);
});
wrap.appendChild(tabs2);
if(ASSET_TAB==="overview")wrap.appendChild(mkOverview(a,ti));
else if(ASSET_TAB==="risk")wrap.appendChild(mkRisk(a));
else if(ASSET_TAB==="forecast")wrap.appendChild(mkForecast(f));
else if(ASSET_TAB==="insights")wrap.appendChild(mkInsights());
else wrap.appendChild(mkRelatedNews());
return wrap;
}

function mkOverview(a,ti){
var w=el("div","",{display:"flex",flexDirection:"column",gap:"24px"});
var ctrl=el("div","",{display:"flex",justifyContent:"space-between",marginBottom:"8px",flexWrap:"wrap",gap:"8px"});
var types=el("div","",{display:"flex",gap:"4px"});
["line","candle","volume"].forEach(function(t){
var b=document.createElement("button");b.className="tab"+(CHART_TYPE===t?" active":"");b.style.fontSize="12px";b.textContent=t.charAt(0).toUpperCase()+t.slice(1);
b.onclick=(function(tp){return function(){CHART_TYPE=tp;render();setTimeout(initCharts,50)}})(t);types.appendChild(b);
});
ctrl.appendChild(types);w.appendChild(ctrl);
var chartWrap=el("div","glass",{borderRadius:"8px",padding:"8px",height:"320px",position:"relative"});
var canvas=document.createElement("canvas");canvas.id="priceChart";chartWrap.appendChild(canvas);w.appendChild(chartWrap);
var rsiWrap=el("div","glass",{borderRadius:"8px",padding:"8px",height:"80px",marginTop:"4px",position:"relative"});
rsiWrap.appendChild(el("div","",{fontSize:"11px",color:"#6c757d",marginBottom:"4px"},"RSI (14)"));
var rc=document.createElement("canvas");rc.id="rsiChart";rsiWrap.appendChild(rc);w.appendChild(rsiWrap);
var mg=el("div","",{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(150px,1fr))",gap:"12px"});
var metrics=[["52W High",fmtC(a.week_52_high)],["52W Low",fmtC(a.week_52_low)],["Volume",fmtV(a.volume)],["Min Investment",fmtC(a.min_investment)],["SIP Eligible",a.sip_eligible?"Yes":"No"],["Liquidity",a.liquidity_score+"/10"],["Horizon",a.recommended_horizon]];
if(a.nav)metrics.unshift(["NAV",fmtC(a.nav)]);if(a.aum)metrics.unshift(["AUM",fmtC(a.aum)]);
if(a.expense_ratio)metrics.push(["Expense Ratio",a.expense_ratio+"%"]);
metrics.forEach(function(m){
var c=el("div","glass2",{borderRadius:"8px",padding:"12px"});
c.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},m[0]));c.appendChild(el("div","",{fontSize:"14px",fontWeight:"600",color:"#fff",marginTop:"4px"},m[1]));
mg.appendChild(c);
});
w.appendChild(mg);
var tiWrap=el("div","glass",{borderRadius:"12px",padding:"16px"});
tiWrap.appendChild(el("h3","",{fontSize:"14px",fontWeight:"600",color:"#ced4da",marginBottom:"12px"},"Technical Indicators"));
var tiGrid=el("div","",{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:"12px"});
tiGrid.appendChild(tiCard("RSI (14)",ti.rsi,ti.rsi>70?"#f87171":ti.rsi<30?"#4ade80":"#fff",ti.rsi>70?"Overbought":ti.rsi<30?"Oversold":"Neutral"));
tiGrid.appendChild(tiCard("SMA 20",ti.sma_20?fmtC(ti.sma_20):"-","#fff"));
tiGrid.appendChild(tiCard("SMA 50",ti.sma_50?fmtC(ti.sma_50):"-","#fff"));
var macdVal=ti.macd&&ti.macd.line?ti.macd.line.toFixed(2):"0";
var macdSig=ti.macd&&ti.macd.signal?ti.macd.signal.toFixed(2):"0";
tiGrid.appendChild(tiCard("MACD",macdVal,ti.macd&&ti.macd.histogram>0?"#4ade80":"#f87171","Signal: "+macdSig));
tiWrap.appendChild(tiGrid);
if(ti.bollinger_bands&&ti.bollinger_bands.upper){
var bb=el("div","glass2",{borderRadius:"8px",padding:"12px",marginTop:"12px"});
bb.appendChild(el("div","",{fontSize:"11px",color:"#6c757d",marginBottom:"8px"},"Bollinger Bands"));
var bbRow=el("div","",{display:"flex",justifyContent:"space-between",fontSize:"13px"});
bbRow.appendChild(el("span","",{color:"#f87171"},"Upper: "+fmtC(ti.bollinger_bands.upper)));
bbRow.appendChild(el("span","",{color:"#facc15"},"Middle: "+fmtC(ti.bollinger_bands.middle)));
bbRow.appendChild(el("span","",{color:"#4ade80"},"Lower: "+fmtC(ti.bollinger_bands.lower)));
bb.appendChild(bbRow);tiWrap.appendChild(bb);
}
w.appendChild(tiWrap);
return w;
}

function tiCard(label,value,color,sub){
var d=el("div","glass2",{borderRadius:"8px",padding:"12px"});
d.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},label));
d.appendChild(el("div","",{fontSize:"18px",fontWeight:"700",color:color||"#fff"},String(value)));
if(sub)d.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},sub));
return d;
}

function mkRisk(a){
var w=el("div","glass",{borderRadius:"12px",padding:"24px"});
w.appendChild(el("h3","",{fontSize:"18px",fontWeight:"600",color:"#fff",marginBottom:"16px"},"Risk Analysis"));
var mg=el("div","",{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:"16px"});
var ms=[["Risk Score",a.risk_score+"/10",rL(a.risk_score),rC(a.risk_score)],["Volatility",a.volatility+"%",null,null],["Beta",String(a.beta),null,null],["Sharpe Ratio",String(a.sharpe_ratio),null,null],["Max Drawdown",a.max_drawdown+"%",null,"#f87171"],["Std Deviation",a.standard_deviation+"%",null,null],["Liquidity",a.liquidity_score+"/10",null,null],["Min Investment",fmtC(a.min_investment),null,null]];
ms.forEach(function(m){
var c=el("div","glass2",{borderRadius:"12px",padding:"16px",textAlign:"center"});
c.appendChild(el("div","",{fontSize:"28px",fontWeight:"700",color:m[3]||"#fff"},m[1]));
c.appendChild(el("div","",{fontSize:"13px",color:"#adb5bd",marginTop:"4px"},m[0]));
if(m[2])c.appendChild(el("div","",{fontSize:"12px",marginTop:"4px",fontWeight:"500"},m[2]));
mg.appendChild(c);
});
w.appendChild(mg);
var warn=el("div","",{marginTop:"16px",padding:"16px",background:"rgba(250,204,21,0.05)",border:"1px solid rgba(250,204,21,0.2)",borderRadius:"8px"});
warn.appendChild(el("p","",{fontSize:"12px",color:"#facc15"},"\\u26A0\\uFE0F Risk scores are calculated based on historical volatility, beta, and other technical indicators. Past performance does not guarantee future results."));
w.appendChild(warn);return w;
}

function mkForecast(f){
if(!f)return el("div","glass",{padding:"24px",borderRadius:"12px"},"No forecast data");
var w=el("div","glass",{borderRadius:"12px",padding:"24px"});
w.appendChild(el("h3","",{fontSize:"18px",fontWeight:"600",color:"#fff",marginBottom:"8px"},"Probability-Based Forecast"));
w.appendChild(el("span","",{fontSize:"12px",padding:"4px 10px",borderRadius:"12px",background:"rgba(59,130,246,0.1)",color:"#60a5fa",display:"inline-block"},"Confidence: "+f.confidence+"%"));
var g=el("div","",{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:"16px",margin:"24px 0"});
var b1=el("div","glass2",{borderRadius:"12px",padding:"16px",textAlign:"center"});
b1.appendChild(el("div","",{fontSize:"32px",fontWeight:"700",color:"#4ade80"},f.bullish+"%"));
b1.appendChild(el("div","",{fontSize:"14px",color:"#4ade80",marginTop:"4px"},"\\uD83D\\uDCC8 Bullish"));g.appendChild(b1);
var b2=el("div","glass2",{borderRadius:"12px",padding:"16px",textAlign:"center"});
b2.appendChild(el("div","",{fontSize:"32px",fontWeight:"700",color:"#facc15"},f.neutral+"%"));
b2.appendChild(el("div","",{fontSize:"14px",color:"#facc15",marginTop:"4px"},"\\u27A1\\uFE0F Neutral"));g.appendChild(b2);
var b3=el("div","glass2",{borderRadius:"12px",padding:"16px",textAlign:"center"});
b3.appendChild(el("div","",{fontSize:"32px",fontWeight:"700",color:"#f87171"},f.bearish+"%"));
b3.appendChild(el("div","",{fontSize:"14px",color:"#f87171",marginTop:"4px"},"\\uD83D\\uDCC9 Bearish"));g.appendChild(b3);
w.appendChild(g);
var meth=el("div","glass2",{borderRadius:"8px",padding:"16px",marginBottom:"16px"});
meth.appendChild(el("h4","",{fontSize:"13px",fontWeight:"600",color:"#ced4da",marginBottom:"8px"},"Methodology"));
meth.appendChild(el("p","",{fontSize:"13px",color:"#adb5bd"},f.methodology));w.appendChild(meth);
var lim=el("div","",{padding:"16px",background:"rgba(248,113,113,0.05)",border:"1px solid rgba(248,113,113,0.2)",borderRadius:"8px"});
lim.appendChild(el("h4","",{fontSize:"13px",fontWeight:"600",color:"#f87171",marginBottom:"4px"},"Limitations"));
lim.appendChild(el("p","",{fontSize:"12px",color:"#adb5bd"},f.limitations));w.appendChild(lim);
return w;
}

function mkInsights(){
if(!INSIGHT||!INSIGHT.insight)return mkLoader();
var i=INSIGHT.insight;
var w=el("div","glass",{borderRadius:"12px",padding:"24px"});
w.appendChild(el("h3","",{fontSize:"18px",fontWeight:"600",color:"#fff",marginBottom:"16px"},"\\uD83E\\uDD16 AI Market Insights"));
w.appendChild(mkIBlock("Today's Movement",i.today_movement,"#ffc107"));
w.appendChild(mkIBlock("Key Drivers",null,"#ffc107",i.key_drivers));
w.appendChild(mkIBlock("Market Sentiment",i.market_sentiment,"#ffc107"));
w.appendChild(mkIBlock("Long-Term Outlook",i.historical_trends,"#ffc107"));
var rr=el("div","",{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"16px",marginTop:"16px"});
var rk=el("div","glass2",{borderRadius:"8px",padding:"16px"});
rk.appendChild(el("h4","",{fontSize:"13px",fontWeight:"600",color:"#f87171",marginBottom:"8px"},"\\u26A0\\uFE0F Key Risks"));
(i.risks||[]).forEach(function(r){rk.appendChild(el("p","",{fontSize:"12px",color:"#adb5bd",marginBottom:"4px"},"\\u2022 "+r))});
rr.appendChild(rk);
var op=el("div","glass2",{borderRadius:"8px",padding:"16px"});
op.appendChild(el("h4","",{fontSize:"13px",fontWeight:"600",color:"#4ade80",marginBottom:"8px"},"\\uD83D\\uDCA1 Opportunities"));
(i.opportunities||[]).forEach(function(o){op.appendChild(el("p","",{fontSize:"12px",color:"#adb5bd",marginBottom:"4px"},"\\u2022 "+o))});
rr.appendChild(op);w.appendChild(rr);
var disc=el("div","",{marginTop:"16px",padding:"12px",background:"rgba(250,204,21,0.05)",border:"1px solid rgba(250,204,21,0.2)",borderRadius:"8px"});
disc.appendChild(el("p","",{fontSize:"12px",color:"#facc15"},"\\u26A0\\uFE0F "+i.disclaimer));w.appendChild(disc);
return w;
}

function mkIBlock(title,text,color,items){
var d=el("div","glass2",{borderRadius:"8px",padding:"16px",marginBottom:"12px"});
d.appendChild(el("h4","",{fontSize:"13px",fontWeight:"600",color:color,marginBottom:"8px"},title));
if(items){items.forEach(function(x){d.appendChild(el("p","",{fontSize:"13px",color:"#ced4da",marginBottom:"4px"},"\\u2022 "+x))})}
else{d.appendChild(el("p","",{fontSize:"13px",color:"#ced4da"},text))}
return d;
}

function mkRelatedNews(){
var news=INSIGHT&&INSIGHT.related_news?INSIGHT.related_news:[];
var w=el("div","glass",{borderRadius:"12px",padding:"24px"});
w.appendChild(el("h3","",{fontSize:"18px",fontWeight:"600",color:"#fff",marginBottom:"16px"},"Related News"));
if(news.length===0){w.appendChild(el("p","",{color:"#6c757d"},"No related news"));return w}
news.forEach(function(n){
var nd=el("div","glass2",{borderRadius:"8px",padding:"16px",marginBottom:"12px"});
var tags=el("div","",{display:"flex",gap:"8px",marginBottom:"8px",flexWrap:"wrap"});
var sn=el("span","",{fontSize:"11px",padding:"2px 8px",borderRadius:"12px"},n.sentiment);
sn.style.cssText=n.sentiment==="positive"?"background:rgba(34,197,94,0.1);color:#4ade80":n.sentiment==="negative"?"background:rgba(248,113,113,0.1);color:#f87171":"background:rgba(156,163,175,0.1);color:#9ca3af";
tags.appendChild(sn);tags.appendChild(el("span","",{fontSize:"11px",color:"#6c757d"},n.source));
nd.appendChild(tags);nd.appendChild(el("h4","",{fontWeight:"600",color:"#fff",marginBottom:"4px"},n.title));
nd.appendChild(el("p","",{fontSize:"13px",color:"#adb5bd"},n.summary));w.appendChild(nd);
});
return w;
}

function mkPortfolio(){
var w=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
var hdr=el("div","",{display:"flex",justifyContent:"space-between",alignItems:"center"});
hdr.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},"Portfolio"));
var btn=document.createElement("button");btn.className="btn";btn.textContent="+ New Portfolio";
btn.onclick=function(){var name=prompt("Portfolio name:");if(name){api("/api/portfolios",{method:"POST",body:JSON.stringify({name:name})}).then(function(){loadData()})}};
hdr.appendChild(btn);w.appendChild(hdr);
PORTFOLIOS.forEach(function(p){
var pd=el("div","glass",{borderRadius:"12px",padding:"20px"});
pd.appendChild(el("h3","",{fontSize:"18px",fontWeight:"700",color:"#fff",marginBottom:"12px"},p.name));
var sg=el("div","",{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:"12px",marginBottom:"16px"});
sg.appendChild(el("div","glass2",{borderRadius:"8px",padding:"12px"},null));
sg.lastChild.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},"Total Invested"));
sg.lastChild.appendChild(el("div","",{fontSize:"18px",fontWeight:"700",color:"#fff"},fmtC(p.total_invested)));
sg.appendChild(el("div","glass2",{borderRadius:"8px",padding:"12px"},null));
sg.lastChild.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},"Current Value"));
sg.lastChild.appendChild(el("div","",{fontSize:"18px",fontWeight:"700",color:"#fff"},fmtC(p.current_value)));
var pnlBox=el("div","glass2",{borderRadius:"8px",padding:"12px"});
pnlBox.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},"P&L"));
var pnlTxt=el("div","",{fontSize:"18px",fontWeight:"700"},fmtC(p.pnl)+" ("+fmtP(p.pnl_pct)+")");pnlTxt.style.cssText=cC(p.pnl);
pnlBox.appendChild(pnlTxt);sg.appendChild(pnlBox);
sg.appendChild(el("div","glass2",{borderRadius:"8px",padding:"12px"},null));
sg.lastChild.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},"Holdings"));
sg.lastChild.appendChild(el("div","",{fontSize:"18px",fontWeight:"700",color:"#fff"},String(p.holdings_count)));
pd.appendChild(sg);w.appendChild(pd);
});
return w;
}

function mkWatchlist(){
var w=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
w.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},"Watchlist"));
WATCHLISTS.forEach(function(wl){
var wd=el("div","glass",{borderRadius:"12px",padding:"20px"});
wd.appendChild(el("h3","",{fontSize:"18px",fontWeight:"700",color:"#fff",marginBottom:"12px"},wl.name));
if(wl.items&&wl.items.length>0){
var tb=document.createElement("table");tb.style.cssText="width:100%;font-size:13px;border-collapse:collapse";
var thd=document.createElement("thead");thd.innerHTML='<tr style="color:#6c757d;font-size:11px;border-bottom:1px solid rgba(255,255,255,0.05)"><th style="text-align:left;padding:8px 0">Symbol</th><th style="text-align:left">Name</th><th style="text-align:right">Price</th><th style="text-align:right">Change</th></tr>';
tb.appendChild(thd);var tbd=document.createElement("tbody");
wl.items.forEach(function(item){
var tr=document.createElement("tr");tr.style.cssText="border-bottom:1px solid rgba(255,255,255,0.05);cursor:pointer";
tr.onclick=(function(s){return function(){viewA(s)}})(item.symbol);
tr.innerHTML='<td style="padding:8px 0;font-weight:600;color:#fff">'+item.symbol+'</td><td style="color:#ced4da">'+item.name+'</td><td style="text-align:right;color:#fff">'+fmtC(item.current_price)+'</td><td style="text-align:right" class="'+(item.daily_change_pct>0?"text-green-400":"text-red-400")+'">'+fmtP(item.daily_change_pct)+'</td>';
tbd.appendChild(tr);
});tb.appendChild(tbd);wd.appendChild(tb);
}else{wd.appendChild(el("p","",{color:"#6c757d",fontSize:"13px",textAlign:"center",padding:"16px"},"No assets in watchlist"))}
w.appendChild(wd);
});
return w;
}

function mkNews(){
var w=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
w.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},"News & Alerts"));
var cats=el("div","",{display:"flex",gap:"8px",flexWrap:"wrap"});
["All","Gold","Silver","Mining","Commodities","Financial","Regulatory"].forEach(function(c){
var b=document.createElement("button");b.className="tab"+((c==="All"&&!NEWS_FILTER)||(NEWS_FILTER===c)?" active":"");b.textContent=c;
b.onclick=function(){NEWS_FILTER=c==="All"?"":c;LOADING=true;render();api("/api/news"+(NEWS_FILTER?"?category="+NEWS_FILTER:"")).then(function(d){NEWS=d?d.news:[];LOADING=false;render()})};
cats.appendChild(b);
});
w.appendChild(cats);
NEWS.forEach(function(n){
var nd=el("div","glass card",{borderRadius:"12px",padding:"20px"});
var tags=el("div","",{display:"flex",gap:"8px",marginBottom:"8px",flexWrap:"wrap"});
var sn=el("span","",{fontSize:"11px",padding:"2px 8px",borderRadius:"12px"},n.sentiment);
sn.style.cssText=n.sentiment==="positive"?"background:rgba(34,197,94,0.1);color:#4ade80":n.sentiment==="negative"?"background:rgba(248,113,113,0.1);color:#f87171":"background:rgba(156,163,175,0.1);color:#9ca3af";
tags.appendChild(sn);tags.appendChild(el("span","",{fontSize:"11px",color:"#6c757d"},n.source));
nd.appendChild(tags);nd.appendChild(el("h3","",{fontWeight:"600",color:"#fff",marginBottom:"8px"},n.title));
nd.appendChild(el("p","",{fontSize:"13px",color:"#adb5bd",marginBottom:"12px"},n.summary));
w.appendChild(nd);
});
return w;
}

function mkSearch(){
var w=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
w.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},"Search & Discover"));
var sf=el("div","glass",{borderRadius:"12px",padding:"16px"});
var inp=document.createElement("input");inp.type="text";inp.placeholder="Search by symbol, name, or category...";inp.style.cssText="width:100%;font-size:16px;margin-bottom:12px";
inp.oninput=function(){FILTER=this.value;api("/api/assets?search="+this.value).then(function(d){ASSETS=d?d.assets:[];render()})};
sf.appendChild(inp);w.appendChild(sf);
w.appendChild(el("p","",{color:"#6c757d",fontSize:"13px"},ASSETS.length+" assets found"));
var ag=el("div","",{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(280px,1fr))",gap:"16px"});
ASSETS.forEach(function(a){ag.appendChild(aCard(a))});w.appendChild(ag);
return w;
}

function mkCompare(){
var w=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
w.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},"Compare Assets"));
var sel=el("div","glass",{borderRadius:"12px",padding:"16px"});
var btns=el("div","",{display:"flex",flexWrap:"wrap",gap:"8px",marginBottom:"16px"});
ASSETS.forEach(function(a){
var b=document.createElement("button");b.textContent=a.symbol;b.style.cssText="font-size:12px;padding:4px 12px;border-radius:8px;border:1px solid "+(COMPARE_SEL.indexOf(a.symbol)>=0?"rgba(212,160,23,0.3)":"rgba(255,255,255,0.1)")+";background:"+(COMPARE_SEL.indexOf(a.symbol)>=0?"rgba(212,160,23,0.2)":"rgba(255,255,255,0.05)")+";color:"+(COMPARE_SEL.indexOf(a.symbol)>=0?"#ffc107":"#adb5bd")+";cursor:pointer";
b.onclick=(function(sym){return function(){var idx=COMPARE_SEL.indexOf(sym);if(idx>=0)COMPARE_SEL.splice(idx,1);else if(COMPARE_SEL.length<5)COMPARE_SEL.push(sym);render()}})(a.symbol);
btns.appendChild(b);
});
sel.appendChild(btns);w.appendChild(sel);
if(COMPARE_DATA&&COMPARE_DATA.assets&&COMPARE_DATA.assets.length>0){
var tb=document.createElement("table");tb.style.cssText="width:100%;font-size:13px;border-collapse:collapse";
var thd=document.createElement("thead");thd.innerHTML='<tr style="color:#6c757d;font-size:11px"><th style="text-align:left;padding:12px 0">Metric</th>'+COMPARE_DATA.assets.map(function(a){return'<th style="text-align:center;padding:12px;color:#ffc107;font-weight:600">'+a.symbol+'</th>'}).join("")+'</tr>';
tb.appendChild(thd);
var tbd=document.createElement("tbody");
[["Price",function(a){return fmtC(a.current_price)}],["Change %",function(a){return fmtP(a.daily_change_pct)}],["Risk Score",function(a){return String(a.risk_score)}],["Volatility",function(a){return a.volatility+"%"}],["Beta",function(a){return String(a.beta)}],["Sharpe",function(a){return String(a.sharpe_ratio)}],["Max DD",function(a){return a.max_drawdown+"%"}],["Volume",function(a){return fmtV(a.volume)}]].forEach(function(r){
var tr=document.createElement("tr");tr.style.cssText="border-bottom:1px solid rgba(255,255,255,0.05)";
tr.innerHTML='<td style="padding:8px 0;color:#adb5bd">'+r[0]+'</td>'+COMPARE_DATA.assets.map(function(a){return'<td style="text-align:center;padding:8px;color:#fff">'+r[1](a)+'</td>'}).join("");
tbd.appendChild(tr);
});
tb.appendChild(tbd);var wrap=el("div","glass",{borderRadius:"12px",padding:"16px",overflowX:"auto"});wrap.appendChild(tb);w.appendChild(wrap);
}
return w;
}

function mkAdmin(){
var w=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
w.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:"#fff"},"Admin Panel"));
var sg=el("div","",{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:"12px"});
[["Active Assets",STATS?STATS.active_assets:0,"\\uD83D\\uDCCA"],["Portfolios",STATS?STATS.portfolios:0,"\\uD83D\\uDCBC"],["Watchlist Items",STATS?STATS.watchlist_items:0,"\\u2B50"],["News Items",STATS?STATS.news_items:0,"\\uD83D\\uDCF0"],["Active Alerts",STATS?STATS.active_alerts:0,"\\uD83D\\uDD14"],["Audit Entries",STATS?STATS.audit_entries:0,"\\uD83D\\uDCDD"]].forEach(function(s){
var c=el("div","glass",{borderRadius:"12px",padding:"12px",textAlign:"center"});
c.appendChild(el("div","",{fontSize:"18px",marginBottom:"4px"},s[2]));c.appendChild(el("div","",{fontSize:"20px",fontWeight:"700",color:"#fff"},String(s[1])));c.appendChild(el("div","",{fontSize:"11px",color:"#6c757d"},s[0]));
sg.appendChild(c);
});
w.appendChild(sg);return w;
}

function mkSettings(){
var w=el("div","fade",{display:"flex",flexDirection:"column",gap:"24px"});
w.appendChild(el("h1","",{fontSize:"24px",fontWeight:"700",color:#fff},"Settings & Information"));
var disc=el("div","glass",{borderRadius:"12px",padding:"24px",border:"1px solid rgba(250,204,21,0.2)"});
disc.appendChild(el("h3","",{fontSize:"18px",fontWeight:"600",color:"#facc15",marginBottom:"12px"},"\\u26A0\\uFE0F Disclaimer"));
disc.appendChild(el("p","",{color:"#ced4da",fontSize:"14px",lineHeight:"1.6"},CONFIG?CONFIG.disclaimer:""));w.appendChild(disc);
if(CONFIG&&CONFIG.data_sources){
var ds=el("div","glass",{borderRadius:"12px",padding:"24px"});
ds.appendChild(el("h3","",{fontSize:"18px",fontWeight:"600",color:"#fff",marginBottom:"16px"},"Data Sources"));
var dsg=el("div","",{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(250px,1fr))",gap:"12px"});
for(var k in CONFIG.data_sources){
var src=CONFIG.data_sources[k];var sd=el("div","glass2",{borderRadius:"12px",padding:"16px"});
sd.appendChild(el("div","",{fontWeight:"500",color:"#fff"},src.name));sd.appendChild(el("p","",{fontSize:"12px",color:"#ffc107"},src.url));
dsg.appendChild(sd);
}
ds.appendChild(dsg);w.appendChild(ds);
}
var sc=el("div","glass",{borderRadius:"12px",padding:"24px"});
sc.appendChild(el("h3","",{fontSize:"18px",fontWeight:"600",color:"#fff",marginBottom:"16px"},"Keyboard Shortcuts"));
[["D","Dashboard"],["S","Search"],["P","Portfolio"],["W","Watchlist"],["N","News"],["C","Compare"],["A","Admin"],["Esc","Go back"]].forEach(function(s){
var r=el("div","",{display:"flex",alignItems:"center",gap:"12px",marginBottom:"8px"});
r.appendChild(el("kbd","",{padding:"4px 8px",background:"#2a2d35",borderRadius:"4px",fontSize:"12px",color:"#ced4da",fontFamily:"monospace",minWidth:"40px",textAlign:"center"},s[0]));
r.appendChild(el("span","",{color:"#adb5bd",fontSize:"14px"},s[1]));sc.appendChild(r);
});
w.appendChild(sc);return w;
}

function initCharts(){
if(!CHART_DATA||!CHART_DATA.prices||!CHART_DATA.prices.length)return;
var prices=CHART_DATA.prices;
var pc=document.getElementById("priceChart");
if(pc){
var ds=[];
if(CHART_TYPE==="volume"){ds=[{label:"Volume",data:prices.map(function(p){return p.volume}),backgroundColor:"rgba(34,197,94,0.4)",borderRadius:2}]}
else if(CHART_TYPE==="candle"){ds=[{label:"OHLC",data:prices.map(function(p){return[p.open,p.high,p.low,p.close]}),backgroundColor:"rgba(34,197,94,0.6)",borderWidth:1}]}
else{
ds.push({label:ASSET||"Price",data:prices.map(function(p){return p.close}),borderColor:"#ffc107",backgroundColor:"rgba(255,193,7,0.1)",fill:true,tension:0.4,pointRadius:0,borderWidth:2});
if(CHART_DATA.sma_20)ds.push({label:"SMA 20",data:CHART_DATA.sma_20.map(function(s){return s.value}),borderColor:"#22d3ee",borderWidth:1,pointRadius:0,borderDash:[5,5],fill:false});
if(CHART_DATA.sma_50)ds.push({label:"SMA 50",data:CHART_DATA.sma_50.map(function(s){return s.value}),borderColor:"#f472b6",borderWidth:1,pointRadius:0,borderDash:[5,5],fill:false});
}
charts.price=new Chart(pc.getContext("2d"),{type:CHART_TYPE==="line"?"line":"bar",data:{labels:prices.map(function(p){return p.date}),datasets:ds},options:{responsive:true,maintainAspectRatio:false,interaction:{intersect:false,mode:"index"},plugins:{legend:{display:CHART_TYPE==="line",labels:{color:"#adb5bd",font:{size:11}}},tooltip:{backgroundColor:"#1a1c23",borderColor:"#343a40",borderWidth:1,titleColor:"#ffc107",bodyColor:"#e9ecef"}},scales:{x:{ticks:{color:"#6c757d",maxTicksLimit:8,font:{size:10}},grid:{color:"rgba(255,255,255,0.03)"}},y:{ticks:{color:"#6c757d",font:{size:10}},grid:{color:"rgba(255,255,255,0.03)"}}}}});
}
var rc=document.getElementById("rsiChart");
if(rc&&CHART_DATA.rsi){
charts.rsi=new Chart(rc.getContext("2d"),{type:"line",data:{labels:CHART_DATA.rsi.map(function(r){return r.date}),datasets:[{data:CHART_DATA.rsi.map(function(r){return r.value}),borderColor:"#a78bfa",borderWidth:1.5,pointRadius:0,fill:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{display:false},y:{min:0,max:100,ticks:{color:"#6c757d",font:{size:9},stepSize:25},grid:{color:"rgba(255,255,255,0.03)"}}}}});
}
}

document.addEventListener("DOMContentLoaded",function(){loadData()});
<\\/script>
</body>
</html>'''

os.makedirs('static/app', exist_ok=True)
with open('static/app/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('HTML file written: ' + str(len(html)) + ' chars')
print('Optional chaining: ' + str(html.count('?.')))
print('Arrow functions: ' + str(html.count('=>')))