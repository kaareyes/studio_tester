"""The test page. Runs on this Mac only (http://localhost:8765): pick the Studio build and a suite, press Start, watch, open the report."""
import datetime
import glob
import json
import os
import random
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import ax, cameras, catalog, collect, matcher, profiles, runner, setup_check, updater

PORT = int(os.environ.get("STUDIO_TESTER_PORT", "8765"))     # a different port lets a second copy run side by side (tests)
sys.path.insert(0, runner.ROOT)
import suites  # noqa: E402

current = {"run": None}
OPTION_KEYS = ("picked", "allow_real", "auditions", "rounds", "hours", "profile", "mix", "mode", "seed", "presets", "sample_image",
               "sample_video", "sessions", "auditions_text")


class CollectJob:
    """The Collect button: opens the app (if needed) and reads every project, session and talent. Read only."""

    def __init__(self):
        self.running = False
        self.text = ""
        self.stop = False
        self.just_done = False

    def start(self, build_path):
        self.running, self.stop, self.just_done = True, False, False
        self.text = "Starting..."
        threading.Thread(target=self._run, args=(build_path,), daemon=True).start()

    def _run(self, build_path):
        try:
            run_dir = os.path.join(runner.REPORTS, datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_collect")
            os.makedirs(run_dir, exist_ok=True)
            context = runner.Context(build_path, None, run_dir, lambda t: None)
            app = context.launch()
            if app.exists("login.signIn"):
                self.text = "Studio is on the login screen. Sign in with the test account in Studio, then press Collect again."
                return
            data = collect.run(app, context.log, progress=lambda t: setattr(self, "text", t), stop=lambda: self.stop)
            count = sum(len(p["sessions"]) for p in data["projects"])
            self.text = f"Collected {len(data['projects'])} projects and {count} sessions." + ("" if data["complete"] else " The list is not complete (stopped or some sessions could not be read).")
            self.just_done = True
        except Exception as error:
            self.text = f"Could not collect: {error}. Is Studio installed and open? Is the test account signed in?"
        finally:
            self.running = False


collect_job = CollectJob()


def estimate_text(suite, options):
    """(text, problem sentence or None, blocking) for the page: how long, how much disk, and what is missing."""
    problem = suite_problem(suite)
    if problem:
        return "", problem, True
    try:
        picked = json.loads(options.get("picked") or "[]")
    except ValueError:
        picked = []
    profile = options.get("profile") or "mixed"
    mix = options.get("mix")
    try:
        per = int(options.get("auditions") or 3)
        rounds = int(options.get("rounds") or 20)
        hours = float(options.get("hours") or 2)
    except ValueError:
        return "", "A count on the page is not a number.", True
    needs_sessions = suite in suites.RECORDING
    if needs_sessions and not picked:
        return "", "Tick at least one session first (collect the projects, then tick sessions).", True
    if suite in ("realistic", "long_video"):
        takes = len(picked) * per * 2.2
        e = profiles.estimate(takes, "long" if suite == "long_video" and profile not in ("long", "mixed") else profile, mix)
    elif suite in ("chaos", "network", "recovery", "friday"):
        e = profiles.estimate(rounds if suite == "chaos" else 12, "short", mix)
    elif suite == "soak":
        e = {"seconds": int(hours * 3600), "disk_mb": int(hours * 3600 * 0.55 * 0.5)}
    elif suite == "offline_load":
        e = {"seconds": 3600, "disk_mb": 2000}
    else:
        return "Takes a few minutes. Nothing is recorded.", None, False
    text = f"About <b>{profiles.describe(e['seconds'])}</b> and <b>{e['disk_mb'] / 1024:.1f} GB</b> of disk (free: {profiles.free_disk_mb() / 1024:.0f} GB). {len(picked)} session(s) ticked."
    problem = profiles.disk_problem(max(1, e["disk_mb"] // 1000), "short") if e["disk_mb"] + 5000 > profiles.free_disk_mb() else None
    return text, problem, bool(problem)

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Studio Tester</title><style>
body{font-family:-apple-system,Helvetica,Arial,sans-serif;margin:0;color:#1f3a5f;background:#f7f9fc}
header{background:#1f3a5f;color:#fff;padding:14px 24px;font-size:20px;font-weight:600}
main{display:grid;grid-template-columns:minmax(420px,520px) 1fr;gap:24px;padding:24px}
section{background:#fff;border:1px solid #c5d0dc;border-radius:10px;padding:18px;margin-bottom:18px}
h2{font-size:15px;margin:14px 0 6px}h2:first-child{margin-top:0}select,input,textarea{width:100%;padding:8px;font-size:14px;box-sizing:border-box}
button{padding:10px 18px;font-size:15px;border:0;border-radius:8px;color:#fff;background:#2e8b57;cursor:pointer;margin-top:10px}
button.stop{background:#c0392b}button.small{padding:5px 10px;font-size:12px;margin:0 4px 0 0;background:#2f6fb0}button:disabled{background:#999}
.row{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid #eef3f9;font-size:14px}
.tag{min-width:70px;text-align:center;color:#fff;border-radius:5px;font-size:12px;padding:2px 0;height:18px}
.passed{background:#2e8b57}.failed{background:#c0392b}.skipped{background:#b9770e}.running{background:#2f6fb0}.waiting{background:#aaa}
.fix{color:#c0392b}.ok{color:#2e8b57}small{color:#555}pre{font-size:12px;background:#f1f4f8;padding:10px;overflow:auto;max-height:180px}
.banner{background:#fff4e5;border:2px solid #e08a00;color:#7a4a00;padding:10px 14px;border-radius:8px;font-weight:600;margin-bottom:14px;display:none}
.big{font-size:34px;font-weight:800}.tree{max-height:340px;overflow:auto;border:1px solid #dde6ef;border-radius:6px;padding:6px}
.proj{font-weight:600;margin-top:6px}.sess{margin-left:22px;font-weight:400;font-size:13px}.grey{color:#999}
.presets button{background:#2f6fb0;margin-right:8px}.presets button.on{background:#1f3a5f}.app{padding:8px;border:1px solid #dde6ef;border-radius:6px;margin-top:6px;cursor:pointer}.app.sel{border-color:#2f6fb0;background:#eef6ff}.kind{color:#fff;border-radius:4px;padding:1px 7px;font-size:12px}.kind.test{background:#2e8b57}.kind.develop{background:#2f6fb0}.kind.staging{background:#b9770e}.kind.production{background:#c0392b}details{margin-top:10px}
</style></head><body><header>Studio Tester <small id="ver" style="font-weight:400;color:#cfe"></small><span id="upd" style="float:right;font-size:14px;font-weight:400"></span></header><main>
<div>
<section><h2>1. Choose the Studio app</h2><small>These Studio apps are running now. Click the one to test.</small>
<div id="apps"></div><div id="appsNot"></div><div id="appWarn" class="fix"></div></section>
<div id="gate" style="display:none">
<section><h2>This Mac</h2><div id="setup"></div></section>
<section><h2>2. Projects and sessions</h2>
<button onclick="collect()" id="collectBtn" style="margin-top:0">Collect projects from the app</button> <button class="stop" onclick="collectStop()">Stop</button>
<div><small id="collectState">Not collected yet. Studio must be open and signed in with the test account.</small></div>
<input id="find" placeholder="Search (typos and capital letters are fine)" oninput="search()" style="margin-top:8px">
<div style="margin-top:6px"><button class="small" onclick="selectAll(true)">Tick all usable</button><button class="small" onclick="selectAll(false)">Untick all</button>
<button class="small" onclick="randomN()">Tick 5 random</button></div>
<div id="tree" class="tree"><small>Nothing collected yet.</small></div>
<small id="picked"></small></section>
<section><h2>3. How hard?</h2><div class="presets" id="presets"></div><small id="presetText"></small><div id="estimate" style="margin-top:8px"></div>
<details><summary>Advanced</summary>

<h2>Test suite</h2><select id="suite" onchange="suiteChanged()"></select><small id="suiteText"></small>
<h2>Take length</h2><select id="profile"><option value="mixed">Mixed (default)</option><option value="short">Short (30 s to 1 min)</option><option value="normal">Normal (1 to 5 min)</option><option value="long">Long (25 to 50 min)</option></select>
<input id="mix" placeholder="Mix short/normal/long in % (default 50/40/10)" style="margin-top:6px">
<h2>Mode</h2><select id="mode"><option value="online">Online</option><option value="offline">Offline</option><option value="mixed">Online and offline mixed</option></select>
<h2>Counts</h2><div style="display:flex;gap:8px"><input id="auditions" placeholder="Auditions per session (3)"><input id="rounds" placeholder="Chaos scenarios (20)"><input id="hours" placeholder="Soak hours (2)"></div>
<h2>Seed</h2><input id="seed" placeholder="Empty = new random. Type a seed from a report to repeat that run">
<h2>Network faults to try (Network suite)</h2><input id="presetsList" placeholder="Empty = the default set; or file names, comma separated">
<h2>Offline load: small test media</h2><input id="sampleImage" placeholder="Path of a small photo"><input id="sampleVideo" placeholder="Path of a small video" style="margin-top:6px">
<h2>Explore: sessions and auditions by name</h2><textarea id="sessions" rows="2" placeholder="Sessions, one per line"></textarea><textarea id="auditions_text" rows="2" style="margin-top:6px" placeholder="Auditions, one per line"></textarea>
<h2>Camera</h2><select id="camera"></select>
<h2>Test project words</h2><input id="words" placeholder="Extra words that mark a project as a test project, comma separated"><button class="small" onclick="saveWords()" style="margin-top:6px">Save words</button>
</details></section>
<div id="warn" class="fix"></div>
<div><button id="start" onclick="start()" style="font-size:18px">Start</button> <button class="stop" onclick="stop()">Stop</button> <button id="again" onclick="again()" style="display:none;background:#2f6fb0">Run again with the same seed</button></div>
</div></div>
<div>
<div class="banner" id="banner">A test is running. Do not use the mouse or keyboard on this Mac until it finishes.</div>
<section><h2 id="title">No test is running</h2><div id="verdict" class="big"></div><div id="now"></div><div id="summary"></div><div id="results"></div>
<h2>Log</h2><pre id="log"></pre><div id="report"></div><button class="small" onclick="openReports()" style="margin-top:10px">Open the reports folder</button></section></div>
</main><script>
let info={},catalog={projects:[]},checked=new Set(),allowReal=new Set(),presets={},lastSeed='',active='quick';
const $=id=>document.getElementById(id);
const PRESETS={quick:['Quick check (about 15 min)','Two short auditions in each ticked session.',{suite:'realistic',auditions:'2',profile:'short',mode:'online'}],
 normal:['Normal (about 1 hour)','Six auditions per session, mixed take lengths.',{suite:'realistic',auditions:'6',profile:'mixed',mode:'online'}],
 chaos:['Break it (about 1 hour)','Random sabotage: bad network, button spam, app killed. Crashes are saved as evidence.',{suite:'chaos',rounds:'25',profile:'short'}],
 overnight:['Overnight','Chaos for hours, all take lengths.',{suite:'chaos',rounds:'120',profile:'mixed'}]};
function preset(k){active=k;const v=PRESETS[k][2];$('suite').value=v.suite;$('auditions').value=v.auditions||'';$('rounds').value=v.rounds||'';$('profile').value=v.profile||'mixed';$('mode').value=v.mode||'online';
 $('presetText').textContent=PRESETS[k][1];document.querySelectorAll('#presets button').forEach(b=>b.classList.toggle('on',b.dataset.k==k));suiteChanged();}
function suiteChanged(){$('suiteText').textContent=info.suites&&info.suites[$('suite').value]?info.suites[$('suite').value][1]:'';estimate();}
async function checkUpdate(){const u=await (await fetch('/api/update')).json();$('ver').textContent='version '+u.current;
 if(u.available){$('upd').innerHTML=`Update available: <b>${u.latest}</b> ${u.notes?'('+u.notes+')':''} <button class="small" style="background:#e08a00" onclick="applyUpdate()">Update now</button>`;}
 else if(u.error){$('upd').textContent=u.error;}else{$('upd').textContent='Up to date';}}
async function applyUpdate(){if(!confirm('Update the tester now? It restarts by itself and keeps your catalog, settings and reports.'))return;$('upd').textContent='Updating...';
 const r=await (await fetch('/api/update/apply',{method:'POST',body:'{}'})).json();$('upd').textContent=r.message;if(r.ok){setTimeout(()=>location.reload(),6000);}}
async function load(){checkUpdate();info=await (await fetch('/api/info')).json();

 $('suite').innerHTML=Object.entries(info.suites).map(([k,v])=>`<option value="${k}">${v[0]}</option>`).join('');
 $('camera').innerHTML='<option value="">Built-in camera (default)</option>'+info.cameras.filter(c=>c.usable&&!c.built_in).map(c=>`<option>${c.name}</option>`).join('');
 $('presets').innerHTML=Object.entries(PRESETS).map(([k,v])=>`<button data-k="${k}" onclick="preset('${k}')">${v[0]}</button>`).join('');
 $('setup').innerHTML=info.setup.map(s=>`<div class="${s[0]?'ok':'fix'}">${s[0]?'OK':'FIX'}: ${s[1]} ${s[0]?'':fixButton(s[1])}</div>`).join('');
 $('words').value=(info.words_extra||[]).join(', ');preset('quick');await loadCatalog();}
function fixButton(t){if(/Accessibility/.test(t))return `<button class="small" onclick="fix('accessibility')">Open the setting</button>`;if(/camera/i.test(t))return `<button class="small" onclick="fix('camera')">Open the setting</button>`;return '';}
async function fix(w){await fetch('/api/fix',{method:'POST',body:JSON.stringify({what:w})});}
async function loadCatalog(){catalog=await (await fetch('/api/catalog')).json();drawTree();}
let found=null;async function search(){const q=$('find').value.trim();if(!q){found=null;drawTree();return;}const r=await (await fetch('/api/search',{method:'POST',body:JSON.stringify({q})})).json();found=new Set(r.ids);drawTree();}
function drawTree(){const q=$('find').value.trim().toLowerCase();const t=$('tree');if(!catalog.projects.length){t.innerHTML='<small>Nothing collected yet.</small>';updatePicked();return;}
 t.innerHTML=catalog.projects.map(p=>{const ss=p.sessions.filter(s=>!q||(found?found.has(s.id):(p.name+' '+s.name).toLowerCase().includes(q)));if(!ss.length)return '';
 const lock=!p.is_test;return `<div class="proj ${lock?'grey':''}">${p.name} ${lock?`<small>(not a test project) <label><input type="checkbox" ${allowReal.has(p.id)?'checked':''} onchange="allow('${p.id}',this.checked)" style="width:auto"> use anyway</label></small>`:''}</div>`+
 ss.map(s=>{const dis=(!s.usable)||(lock&&!allowReal.has(p.id));return `<div class="sess ${dis?'grey':''}"><label><input type="checkbox" style="width:auto" ${dis?'disabled':''} ${checked.has(s.id)?'checked':''} onchange="tick('${s.id}',this.checked)"> ${s.name} <small>${s.usable?(s.talents.length+(s.talents.length==1?' talent':' talents')):'no talents scheduled'}</small></label></div>`}).join('')}).join('');updatePicked();}
function fuzzy(q,text){let i=0;for(const c of text){if(c===q[i])i++;if(i===q.length)return true;}return false;}
function tick(id,on){on?checked.add(id):checked.delete(id);updatePicked();}
function allow(id,on){on?allowReal.add(id):allowReal.delete(id);if(!on)catalog.projects.filter(p=>p.id==id).forEach(p=>p.sessions.forEach(s=>checked.delete(s.id)));drawTree();}
function selectAll(on){checked.clear();if(on)catalog.projects.forEach(p=>{if(p.is_test||allowReal.has(p.id))p.sessions.forEach(s=>{if(s.usable)checked.add(s.id)})});drawTree();}
async function randomN(){const r=await (await fetch('/api/random',{method:'POST',body:JSON.stringify({count:5})})).json();checked.clear();r.ids.forEach(i=>checked.add(i));drawTree();}
function updatePicked(){$('picked').textContent=checked.size+' session(s) ticked. '+(catalog.collected_at?'Collected '+catalog.collected_at.replace('T',' ')+(catalog.complete?'':' (not complete)'):'');estimate();}
async function saveWords(){await fetch('/api/settings',{method:'POST',body:JSON.stringify({test_words:$('words').value.split(',').map(x=>x.trim()).filter(Boolean)})});await loadCatalog();}
async function collect(){await fetch('/api/collect',{method:'POST',body:'{}'});}
async function collectStop(){await fetch('/api/collect-stop',{method:'POST'});}
function options(){return {picked:JSON.stringify([...checked]),allow_real:JSON.stringify([...allowReal]),auditions:$('auditions').value,rounds:$('rounds').value,hours:$('hours').value,profile:$('profile').value,mix:$('mix').value,mode:$('mode').value,seed:$('seed').value,presets:$('presetsList').value,sample_image:$('sampleImage').value,sample_video:$('sampleVideo').value,sessions:$('sessions').value,auditions_text:$('auditions_text').value};}
async function estimate(){if(!info.suites)return;const r=await (await fetch('/api/estimate',{method:'POST',body:JSON.stringify({suite:$('suite').value,options:options()})})).json();
 $('estimate').innerHTML=r.text||'';$('warn').textContent=r.problem||'';$('start').disabled=!!r.problem&&r.blocking;}
async function start(){const r=await fetch('/api/start',{method:'POST',body:JSON.stringify({suite:$('suite').value,camera:$('camera').value,options:options()})});
 if(!r.ok){const e=await r.json();$('warn').textContent=e.error||'Could not start';}}
async function openReports(){await fetch('/api/open-reports',{method:'POST',body:'{}'});}
async function stop(){await fetch('/api/stop',{method:'POST'});}
function again(){$('seed').value=lastSeed;start();}
let APPS=[];
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
async function appsList(){const r=await (await fetch('/api/apps')).json();APPS=r.running.concat(r.installed);
 const row=(a,i,run)=>{const sel=r.selected==a.path;
  return '<div class="app'+(sel?' sel':'')+'" '+(run?'onclick="pick('+i+')"':'')+'><input type="radio" style="width:auto" '+(sel?'checked ':'')+(run?'':'disabled')+'> <b>'+esc(a.name)+'</b> <span class="kind '+a.kind+'">'+a.label+'</span> '+
   (run?'<small>running (pid '+a.pid+')</small>':'<small>not open</small> <button class="small" onclick="event.stopPropagation();openApp('+i+')">Open it</button>')+'</div>';};
 $('apps').innerHTML=r.running.length?r.running.map((a,i)=>row(a,i,true)).join(''):'<div class="fix">No Studio app is running. Open one below, or open Studio yourself.</div>';
 $('appsNot').innerHTML=r.installed.length?'<small>Installed, not open:</small>'+r.installed.map((a,i)=>row(a,r.running.length+i,false)).join(''):'';
 const sel=r.selected_row;$('gate').style.display=sel?'block':'none';
 let warn=!sel?'Choose a Studio app to continue.':(!r.selected_running?'The chosen Studio is not open. The tester opens it when you start, and opens it again if it closes during a test.':'');
 if(sel&&sel.kind=='production')warn='Production is chosen: only Collect, Smoke and Explore (they only look) are allowed. Recording tests need the Test build.';
 $('appWarn').textContent=warn;
 if(window.lastSel!==r.selected){window.lastSel=r.selected;estimate();}}
async function pick(i){const e=await (await fetch('/api/select-app',{method:'POST',body:JSON.stringify({path:APPS[i].path})})).json();if(e.error)$('appWarn').textContent=e.error;appsList();}
async function openApp(i){await fetch('/api/open-app',{method:'POST',body:JSON.stringify({path:APPS[i].path})});}
async function tick2(){appsList();
 const c=await (await fetch('/api/collect-state')).json();if(c.text)$('collectState').textContent=c.text;if(c.just_done){await loadCatalog();}
 $('collectBtn').disabled=c.running;
 const s=await (await fetch('/api/state')).json();if(!s.suite)return;
 const running=!s.finished;$('banner').style.display=running?'block':'none';
 $('title').textContent=(running?'Running: ':'Finished: ')+s.suite;
 const active=s.results.find(r=>r.status=='running');$('now').innerHTML=active?`Now: <b>${active.name}</b>`:'';
 $('verdict').innerHTML=running?'':(s.counts.failed?'<span style="color:#c0392b">FAIL</span>':(s.counts.passed?'<span style="color:#2e8b57">PASS</span>':'NOTHING RAN'));
 $('summary').innerHTML=`<b>${s.counts.passed}</b> passed, <b>${s.counts.failed}</b> failed, <b>${s.counts.skipped}</b> skipped, ${s.counts.waiting+s.counts.running} to go<br><small>Camera: ${s.camera||'none'} (${s.camera_reason})</small>`;
 $('results').innerHTML=s.results.map(r=>`<div class="row"><span class="tag ${r.status}">${r.status.toUpperCase()}</span><span>${r.name}<br><small>${r.message||''}</small></span></div>`).join('');
 $('log').textContent=s.log.join('\\n');const seedLine=s.log.find(l=>/seed \\d+/.test(l));if(seedLine)lastSeed=(seedLine.match(/seed (\\d+)/)||[])[1]||lastSeed;
 $('report').innerHTML=s.finished?`<a href="/reports/${s.folder}/report.html" target="_blank">Open the report</a> &nbsp; <button class="small" onclick="copyReport('${s.folder}')">Copy report for developers</button>`:'';
 $('again').style.display=(s.finished&&lastSeed)?'inline-block':'none';$('start').disabled=running;}
async function copyReport(f){const t=await (await fetch('/reports/'+f+'/results.json')).text();await navigator.clipboard.writeText(t);alert('Copied. Paste it in the message to the developers.');}
load();setInterval(tick2,1000);
</script></body></html>"""


KIND_LABEL = {"test": "Test", "develop": "Develop", "staging": "Staging", "production": "Production"}
READ_ONLY_SUITES = {"build_check", "smoke", "explore"}      # these only look; every other suite records and needs the Test build's test tools
chosen = {"path": None}


def app_row(path, pid=None):
    kind = runner.kind_of(path)
    return {"path": path, "name": os.path.basename(path)[:-4], "kind": kind, "label": KIND_LABEL[kind], "pid": pid}


def apps_info():
    """What the page lists first: the Studio apps running now, the installed ones that are not open, and the one chosen."""
    running = [app_row(path, pid) for pid, path in ax.list_apps(runner.PROCESS_PATTERN)]
    running_paths = {r["path"] for r in running}
    installed = [app_row(p) for p in find_builds() if p not in running_paths]
    seen, unique = set(), []
    for row in installed:                         # one row per app name (several copies of one build are not a choice)
        if row["name"] not in seen and row["name"] not in {r["name"] for r in running}:
            seen.add(row["name"])
            unique.append(row)
    path = chosen["path"]
    return {"running": running, "installed": unique[:8], "selected": path,
            "selected_row": app_row(path) if path else None,
            "selected_running": bool(path and path in running_paths)}


def select_app(path):
    """Remembers the chosen Studio and points every driver at it. Returns an error sentence or None."""
    info = apps_info()
    known = {r["path"] for r in info["running"] + info["installed"]}
    if path not in known:
        return "That Studio app is not running and was not found on this Mac."
    chosen["path"] = path
    ax.TARGET_PATH = path
    return None


def suite_problem(suite):
    """A plain sentence when the chosen app cannot run this suite, else None."""
    path = chosen["path"]
    if not path:
        return "Choose a Studio app first (step 1)."
    kind = runner.kind_of(path)
    if suite not in READ_ONLY_SUITES and kind != "test":
        return (f"This test records auditions and needs the Test build's test tools. You chose Studio ({KIND_LABEL[kind]}). "
                "Choose 'Studio (macOS) - Test' in step 1, or pick Smoke or Explore, which only look.")
    return None


def find_builds():
    """Studio .app builds on this Mac, newest first: Xcode's DerivedData, /Applications, and the folders the team uses."""
    patterns = ["~/Library/Developer/Xcode/DerivedData/*/Build/Products/*/Studio*.app", "/Applications/Studio*.app",
                "/private/tmp/claude-501/*/Build/Products/*/Studio*.app", "~/Desktop/Studio*.app", "~/Downloads/Studio*.app"]
    found = []
    for pattern in patterns:
        found += glob.glob(os.path.expanduser(pattern))
    return sorted(set(found), key=lambda path: os.path.getmtime(path), reverse=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, body, kind="application/json", code=200):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            return self.send(PAGE, "text/html; charset=utf-8")
        if self.path == "/api/info":
            return self.send(json.dumps({"builds": find_builds(), "cameras": cameras.list_cameras(),
                                         "suites": {key: [value[0], value[1]] for key, value in suites.SUITES.items()},
                                         "setup": setup_check.checks(), "words_extra": catalog.load_settings().get("test_words", [])}))
        if self.path == "/api/apps":
            return self.send(json.dumps(apps_info()))
        if self.path == "/api/update":
            return self.send(json.dumps(updater.check(catalog.load_settings().get("update_repo"))))
        if self.path == "/api/catalog":
            return self.send(json.dumps(catalog.decorate(catalog.load())))
        if self.path == "/api/collect-state":
            flag = collect_job.just_done
            collect_job.just_done = False
            return self.send(json.dumps({"running": collect_job.running, "text": collect_job.text, "just_done": flag}))
        if self.path == "/api/state":
            return self.send(json.dumps(current["run"].state() if current["run"] else {}))
        if self.path.startswith("/reports/"):
            path = os.path.normpath(os.path.join(runner.ROOT, self.path.lstrip("/")))
            if path.startswith(runner.REPORTS) and os.path.isfile(path):
                kind = "text/html; charset=utf-8" if path.endswith(".html") else ("image/png" if path.endswith(".png") else "text/plain")
                with open(path, "rb") as handle:
                    return self.send(handle.read(), kind)
        self.send("not found", "text/plain", 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/start":
            run = current["run"]
            if run and not run.finished:
                return self.send(json.dumps({"error": "a run is already in progress"}), code=409)
            suite = suites.SUITES.get(body.get("suite"))
            body["build"] = chosen["path"]
            if not suite or not body.get("build"):
                return self.send(json.dumps({"error": "Choose a Studio app first (step 1)."}), code=400)
            options = {key: str(value)[:20000] for key, value in (body.get("options") or {}).items() if key in OPTION_KEYS}
            _, problem, blocking = estimate_text(body["suite"], options)
            if blocking:
                return self.send(json.dumps({"error": problem}), code=400)
            try:
                new_run = runner.Run(body["suite"], suite[2], body["build"], body.get("camera") or None, options)
            except Exception as error:
                return self.send(json.dumps({"error": f"This suite could not be prepared: {error}"}), code=400)
            current["run"] = new_run
            new_run.start()
            return self.send("{}")
        if self.path == "/api/update/apply":
            busy = lambda: bool(collect_job.running or (current["run"] and not current["run"].finished))
            result = updater.apply(catalog.load_settings().get("update_repo"), busy=busy)
            if result["ok"]:
                def restart_soon():
                    if result.get("packages_changed"):
                        updater.install_packages()
                    updater.restart()
                threading.Timer(2.0, restart_soon).start()
            return self.send(json.dumps(result))
        if self.path == "/api/collect":
            if collect_job.running or (current["run"] and not current["run"].finished):
                return self.send(json.dumps({"error": "something is already running"}), code=409)
            build = chosen["path"]
            if not build:
                return self.send(json.dumps({"error": "Choose a Studio app first (step 1)."}), code=400)
            collect_job.start(build)
            return self.send("{}")
        if self.path == "/api/collect-stop":
            collect_job.stop = True
            return self.send("{}")
        if self.path == "/api/estimate":
            text, problem, blocking = estimate_text(body.get("suite", ""), body.get("options") or {})
            return self.send(json.dumps({"text": text, "problem": problem, "blocking": blocking}))
        if self.path == "/api/random":
            data = catalog.load()
            return self.send(json.dumps({"ids": catalog.pick_random(data, int(body.get("count") or 5), random.Random())}))
        if self.path == "/api/search":
            data = catalog.load()
            query = str(body.get("q") or "")
            ids = []
            for project, session in catalog.flatten(data):
                text = project["name"] + " " + session["name"]
                if matcher.normalize(query) in matcher.normalize(text) or matcher.score(query, text) >= matcher.MIN_SCORE or matcher.score(query, session["name"]) >= matcher.MIN_SCORE:
                    ids.append(session["id"])
            return self.send(json.dumps({"ids": ids}))
        if self.path == "/api/settings":
            words = [str(w)[:40] for w in (body.get("test_words") or [])][:50]
            values = catalog.load_settings()
            values["test_words"] = words
            catalog.save_settings(values)
            return self.send("{}")
        if self.path == "/api/select-app":
            if collect_job.running or (current["run"] and not current["run"].finished):
                # the drivers follow the chosen app: changing it in the middle of a run would make the run drive another Studio
                return self.send(json.dumps({"error": "A test is running. Wait until it finishes (or press Stop) before choosing another Studio app."}), code=409)
            error = select_app(body.get("path") or "")
            return self.send(json.dumps({"error": error}), code=400 if error else 200)
        if self.path == "/api/open-app":
            path = body.get("path") or ""
            if path in {r["path"] for r in apps_info()["installed"]}:
                subprocess.run(["/usr/bin/open", path])
            return self.send("{}")
        if self.path == "/api/open-reports":
            os.makedirs(runner.REPORTS, exist_ok=True)
            subprocess.run(["/usr/bin/open", runner.REPORTS])
            return self.send("{}")
        if self.path == "/api/fix":
            target = {"accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
                      "camera": "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"}.get(body.get("what"))
            if target:
                subprocess.run(["/usr/bin/open", target])
            return self.send("{}")
        if self.path == "/api/stop":
            if current["run"]:
                current["run"].stop_requested = True
            return self.send("{}")
        self.send("not found", "text/plain", 404)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Studio Tester is running. The page: http://localhost:{PORT}\nKeep this window open while testing. Close it to stop.")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
