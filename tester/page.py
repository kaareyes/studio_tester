"""The test page (HTML, CSS and JavaScript in one string). Served by tester/server.py at http://localhost:8765."""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Studio Tester</title><style>
:root{--bg:#f3f5fa;--card:#fff;--ink:#17233c;--muted:#5d6b85;--line:#e1e7f1;--accent:#3b6fd8;--accent-d:#2c58b5;--green:#1f9d62;--green-bg:#e7f6ee;--red:#d6453d;--red-bg:#fdeceb;--orange:#e08a00;--orange-bg:#fff4e1;--blue-bg:#eaf1fe;--navy:#14213d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header.top{position:sticky;top:0;z-index:5;background:linear-gradient(90deg,#14213d,#1f3a6e);color:#fff;display:flex;align-items:center;gap:14px;padding:12px 28px;box-shadow:0 2px 10px rgba(20,33,61,.25)}
.logo{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#5b8cff,#8e6bff);display:grid;place-items:center;font-weight:800}
header h1{margin:0;font-size:19px;font-weight:700;letter-spacing:.2px}.chip{background:rgba(255,255,255,.16);border-radius:20px;padding:2px 11px;font-size:12px}
.upd{margin-left:auto;display:flex;align-items:center;gap:10px;font-size:13px;color:#d6e2ff}
button{font:inherit;border:0;border-radius:9px;color:#fff;background:var(--accent);padding:9px 18px;cursor:pointer;font-weight:600;transition:.15s}
button:hover{background:var(--accent-d)}button:disabled{background:#aab4c8;cursor:not-allowed}
button.go{background:var(--green);font-size:16px;padding:12px 30px}button.go:hover{background:#17804f}button.stop{background:var(--red)}button.stop:hover{background:#b8342d}
button.small{padding:5px 12px;font-size:12px;border-radius:7px}button.ghost{background:#fff;color:var(--accent);border:1px solid var(--line)}button.ghost:hover{background:var(--blue-bg)}
.steps{display:flex;gap:0;max-width:1320px;margin:18px auto 0;padding:0 28px}
.step{flex:1;display:flex;align-items:center;gap:9px;color:var(--muted);font-weight:600;font-size:13px;position:relative;padding:8px 0}
.step .dot{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;background:#dfe5f2;color:#6a7894;font-size:13px;flex:none}
.step.done{color:var(--green)}.step.done .dot{background:var(--green);color:#fff}.step.now{color:var(--accent)}.step.now .dot{background:var(--accent);color:#fff;box-shadow:0 0 0 4px rgba(59,111,216,.18)}
.step.bad{color:var(--red)}.step.bad .dot{background:var(--red);color:#fff}.step:not(:last-child):after{content:"";flex:1;height:2px;background:#dfe5f2;margin:0 12px}.step.done:not(:last-child):after{background:var(--green)}
main{max-width:1320px;margin:6px auto 60px;padding:0 28px;display:grid;grid-template-columns:minmax(440px,560px) 1fr;gap:22px;align-items:start}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-bottom:18px;box-shadow:0 1px 3px rgba(20,33,61,.05)}
.card h2{margin:0 0 4px;font-size:16px;display:flex;align-items:center;gap:9px}.card h2 .n{background:var(--blue-bg);color:var(--accent);border-radius:8px;padding:1px 9px;font-size:13px}
.sub{color:var(--muted);font-size:13px;margin:0 0 12px}small,.muted{color:var(--muted)}
select,input,textarea{font:inherit;width:100%;padding:9px 11px;border:1px solid #cfd8e8;border-radius:9px;background:#fff;color:var(--ink)}select:focus,input:focus,textarea:focus{outline:2px solid rgba(59,111,216,.35);border-color:var(--accent)}
input[type=checkbox],input[type=radio]{width:auto;accent-color:var(--accent)}
.app{display:flex;align-items:center;gap:10px;padding:11px 13px;border:1px solid var(--line);border-radius:12px;margin-top:8px;cursor:pointer;transition:.12s}.app:hover{border-color:#b8c6e6;background:#fafbff}
.app.unsup{opacity:.8;background:#fbf6f5;border:1.5px dashed #e9a7a2;cursor:not-allowed}.app.unsup:hover{background:#fbeeed;border-color:#e9a7a2}
.app.sel{border-color:var(--accent);background:var(--blue-bg);box-shadow:0 0 0 3px rgba(59,111,216,.12)}.app b{font-size:15px}
.kind{color:#fff;border-radius:6px;padding:1px 9px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px}.kind.test{background:var(--green)}.kind.develop{background:var(--accent)}.kind.staging{background:var(--orange)}.kind.production{background:var(--red)}
.note{border-radius:11px;padding:11px 14px;margin-top:10px;font-size:13px}.note.red{background:var(--red-bg);color:#8a1f19;border:1px solid #f4c3bf}.note.orange{background:var(--orange-bg);color:#7a4a00;border:1px solid #f3d9a4}.note.green{background:var(--green-bg);color:#0f6b41;border:1px solid #bfe6d0}.note.blue{background:var(--blue-bg);color:#1f3f8f;border:1px solid #cddcf9}
.login{display:flex;gap:16px;align-items:flex-start}.login .ic{font-size:34px;line-height:1}.login h3{margin:0 0 4px;font-size:16px}
.pulse{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--orange);margin-right:7px;animation:p 1.2s infinite}@keyframes p{50%{opacity:.25}}
.chips{display:flex;flex-wrap:wrap;gap:8px}.cc{display:flex;gap:8px;align-items:flex-start;border-radius:10px;padding:7px 11px;font-size:13px;width:100%}.cc.ok{background:var(--green-bg);color:#0f6b41}.cc.fix{background:var(--red-bg);color:#8a1f19}.cc i{font-style:normal;font-weight:800}
.row2{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.row2 select{width:auto}
.bar{height:8px;background:#e6ecf7;border-radius:6px;overflow:hidden;margin-top:10px}.bar>span{display:block;height:100%;background:linear-gradient(90deg,#3b6fd8,#7aa2ff);border-radius:6px;transition:width .6s}.bar.anim>span{background-size:30px 30px;background-image:linear-gradient(45deg,rgba(255,255,255,.28) 25%,transparent 25%,transparent 50%,rgba(255,255,255,.28) 50%,rgba(255,255,255,.28) 75%,transparent 75%);animation:m 1s linear infinite}@keyframes m{to{background-position:30px 0}}
.tree{max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:12px;padding:6px 10px;margin-top:10px;background:#fbfcff}
.proj{font-weight:700;margin-top:9px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.proj .tag{font-size:10px;font-weight:700;border-radius:5px;padding:1px 7px;color:#fff;background:var(--green)}.proj .tag.no{background:#9aa7bf}
.sess{margin:2px 0 2px 16px;padding:3px 6px;border-radius:7px}.sess:hover{background:#eef3ff}.sess label{display:flex;gap:8px;align-items:center;cursor:pointer}.sess .t{margin-left:auto;font-size:11px;background:#e9eefb;color:#42537a;border-radius:10px;padding:0 8px}.grey{color:#9aa7bf}
.presets{display:grid;grid-template-columns:1fr 1fr;gap:10px}.preset{border:1.5px solid var(--line);border-radius:13px;padding:12px 13px;cursor:pointer;background:#fff;transition:.12s}.preset:hover{border-color:#b8c6e6}.preset.on{border-color:var(--accent);background:var(--blue-bg);box-shadow:0 0 0 3px rgba(59,111,216,.12)}
.preset .e{font-size:22px}.preset b{display:block;font-size:14px}.preset .tm{font-size:12px;color:var(--accent);font-weight:700}.preset p{margin:3px 0 0;font-size:12px;color:var(--muted)}
.est{margin-top:12px;background:#f1f5ff;border:1px solid #d9e4fb;border-radius:11px;padding:9px 13px;font-size:13px}
details{margin-top:12px}summary{cursor:pointer;font-weight:600;color:var(--accent)}.adv{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px;margin-top:10px}.adv label{font-size:12px;font-weight:600;color:var(--muted);display:block;margin-bottom:3px}.adv .w{grid-column:1/-1}
.startbar{position:sticky;bottom:0;background:rgba(243,245,250,.92);backdrop-filter:blur(6px);padding:12px 0 6px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.warn{color:var(--red);font-size:13px;width:100%}
.banner{display:none;background:var(--orange-bg);border:1.5px solid var(--orange);color:#7a4a00;padding:11px 15px;border-radius:12px;font-weight:600;margin-bottom:16px}
.hero{display:flex;align-items:center;gap:18px}.badge{width:84px;height:84px;border-radius:22px;display:grid;place-items:center;font-size:40px;background:#eef2fa;flex:none}.badge.pass{background:var(--green-bg)}.badge.fail{background:var(--red-bg)}.badge.run{background:var(--blue-bg)}
.hero h2{margin:0;font-size:22px}.verdict{font-size:34px;font-weight:800;line-height:1.1}.verdict.pass{color:var(--green)}.verdict.fail{color:var(--red)}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0 6px}.tile{border-radius:12px;padding:10px 12px;background:#f5f7fc}.tile b{display:block;font-size:24px;line-height:1.1}.tile span{font-size:12px;color:var(--muted)}.tile.p b{color:var(--green)}.tile.f b{color:var(--red)}.tile.s b{color:var(--orange)}
.res{display:flex;gap:11px;padding:10px 4px;border-bottom:1px solid #eef2f8;align-items:flex-start}.res:last-child{border:0}
.pill{min-width:78px;text-align:center;color:#fff;border-radius:7px;font-size:11px;font-weight:700;padding:3px 0;letter-spacing:.4px;flex:none;margin-top:1px}.pill.passed{background:var(--green)}.pill.failed{background:var(--red)}.pill.skipped{background:var(--orange)}.pill.running{background:var(--accent);animation:p 1.4s infinite}.pill.waiting{background:#b3bdd1}
.res .nm{flex:1}.res .tm{color:var(--muted);font-size:12px;flex:none}.fmsg{background:var(--red-bg);color:#8a1f19;border-radius:8px;padding:6px 10px;margin-top:5px;font-size:12.5px}.fmsg.sk{background:var(--orange-bg);color:#7a4a00}.fmsg a{color:inherit;font-weight:600;margin-right:10px}
pre{font:12px/1.5 Menlo,monospace;background:#0f172a;color:#d6e0f5;padding:12px;border-radius:10px;overflow:auto;max-height:200px;margin:8px 0 0}
.guide{position:fixed;inset:0;background:rgba(15,23,42,.55);display:none;align-items:flex-start;justify-content:center;z-index:50;overflow:auto;padding:36px 16px}
.gbox{background:#fff;border-radius:18px;max-width:820px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.35)}.ghead{display:flex;align-items:center;gap:12px;padding:20px 26px;border-bottom:1px solid var(--line);position:sticky;top:0;background:#fff;border-radius:18px 18px 0 0}
.ghead h2{margin:0;font-size:20px;flex:1}.gbody{padding:8px 26px 26px}.gbody h3{margin:22px 0 8px;font-size:16px;color:var(--navy)}.gbody p{margin:6px 0}
.gstep{display:flex;gap:14px;padding:12px 14px;border:1px solid var(--line);border-radius:13px;margin:9px 0}.gstep .no{flex:none;width:34px;height:34px;border-radius:50%;background:var(--accent);color:#fff;display:grid;place-items:center;font-weight:800}
.gstep>div>b:first-child{display:block;font-size:15px;margin-bottom:2px}.gtable{width:100%;border-collapse:collapse;font-size:13px}.gtable td{border-bottom:1px solid #eef2f8;padding:7px 8px;vertical-align:top}.gtable td:first-child{white-space:nowrap;font-weight:700;width:200px}
.k{display:inline-block;background:#eef2fa;border:1px solid #d5ddee;border-radius:6px;padding:0 7px;font-size:12px;font-weight:700}
.pausebox{position:fixed;inset:0;background:rgba(15,23,42,.62);display:none;align-items:center;justify-content:center;z-index:70}.pbox{background:#fff;border-radius:20px;max-width:480px;width:92%;padding:30px 32px;text-align:center;box-shadow:0 24px 70px rgba(0,0,0,.4)}
.pbox .pi{font-size:54px;line-height:1}.pbox h2{margin:8px 0 6px;font-size:24px}.pbox .row2{justify-content:center;margin-top:18px}
.quit{position:fixed;right:22px;bottom:22px;z-index:45;background:#fff;color:var(--red);border:1.5px solid #efb8b4;box-shadow:0 4px 14px rgba(20,33,61,.15);padding:9px 16px}.quit:hover{background:var(--red-bg)}
.closed{position:fixed;inset:0;background:var(--bg);z-index:99;display:none;align-items:center;justify-content:center;text-align:center}.closed .cb{max-width:520px;padding:30px}.closed .e{font-size:64px}
.branch{font:13px/1.4 Menlo,monospace;font-weight:700;background:#fff;color:#14213d;border:1.5px solid #e9a7a2;border-radius:9px;padding:8px 11px;margin:6px 0;word-break:break-all;user-select:all}
.app .meta{margin-top:3px;display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center}.app .meta .sup{margin-left:0}
.sup{font-size:11px;font-weight:700;border-radius:6px;padding:1px 8px;margin-left:4px}.sup.ok{background:var(--green-bg);color:#0f6b41}.sup.no{background:var(--red-bg);color:#8a1f19}.sup.wait{background:#eef2fa;color:#5d6b85}
.stale{display:none;background:#fff4e5;border-bottom:2px solid #e08a00;color:#7a4a00;padding:10px 28px;font-weight:600}
.empty{text-align:center;color:var(--muted);padding:26px 10px}.empty .e{font-size:40px}
</style></head><body>
<header class="top"><div class="logo">ST</div><h1>Studio Tester</h1><span class="chip" id="ver">version ...</span>
<button class="small ghost" style="margin-left:14px;background:rgba(255,255,255,.14);color:#fff;border:0" onclick="openGuide()">&#10067; How to use</button>
<div class="upd"><span id="updText"></span><button id="updBtn" class="small" onclick="updateClick()">Update</button></div></header>
<div class="stale" id="staleBar"></div>
<div class="steps" id="steps"></div>
<main>
<div>
<section class="card" id="cApp"><h2><span class="n">1</span>Choose the Studio app<button class="small ghost" id="refreshBtn" onclick="refreshApps()" style="margin-left:auto">&#8635; Refresh</button></h2><p class="sub">These Studio apps are running now. Click the one to test. The list updates by itself; press <b>Refresh</b> to look again, also in other folders.</p>
<div class="muted" id="checkedAt" style="font-size:12px;margin:-6px 0 4px"></div>
<div id="apps"></div><div id="appsNot"></div><div id="unsup" class="note red" style="display:none"></div><div id="appWarn" class="note orange" style="display:none"></div></section>
<section class="card" id="cLogin" style="display:none"><div id="loginBox"></div></section>
<div id="gate" style="display:none">
<section class="card" id="cMac"><h2>This Mac</h2><div class="chips" id="setup"></div></section>
<section class="card" id="cProj"><h2><span class="n">3</span>Projects and sessions</h2><p class="sub">The tester reads the projects from Studio (it only looks, it changes nothing).</p>
<div class="row2"><select id="limit" style="width:auto"><option value="10">First 10 projects</option><option value="20">First 20 projects</option><option value="50">First 50 projects</option><option value="0">All projects (slow)</option></select>
<button onclick="collect()" id="collectBtn">Collect projects from the app</button><button class="stop" onclick="collectStop()">Stop</button></div>
<div class="bar anim" id="collectBar" style="display:none"><span style="width:100%"></span></div>
<div class="muted" id="collectState" style="margin-top:8px">Not collected yet. Studio must be open and signed in with the test account.</div>
<input id="find" placeholder="Search projects and sessions (typos and capital letters are fine)" oninput="search()" style="margin-top:12px">
<div class="row2" style="margin-top:8px"><button class="small ghost" onclick="selectAll(true)">Tick all usable</button><button class="small ghost" onclick="selectAll(false)">Untick all</button><button class="small ghost" onclick="randomN()">Tick 5 random</button></div>
<div id="tree" class="tree"><small>Nothing collected yet.</small></div><div id="picked" class="muted" style="margin-top:6px"></div></section>
<section class="card" id="cHard"><h2><span class="n">4</span>How hard?</h2><div class="presets" id="presets"></div><div id="estimate" class="est"></div>
<details><summary>Advanced</summary><div class="adv">
<div class="w"><label>Test suite</label><select id="suite" onchange="suiteChanged()"></select><small id="suiteText"></small></div>
<div><label>Take length</label><select id="profile"><option value="mixed">Mixed (default)</option><option value="short">Short (30 s to 1 min)</option><option value="normal">Normal (1 to 5 min)</option><option value="long">Long (25 to 50 min)</option></select></div>
<div><label>Mix short / normal / long in %</label><input id="mix" placeholder="50/40/10"></div>
<div><label>Mode</label><select id="mode"><option value="online">Online</option><option value="offline">Offline</option><option value="mixed">Online and offline mixed</option></select></div>
<div><label>Camera</label><select id="camera"></select></div>
<div><label>Auditions per session</label><input id="auditions" placeholder="3"></div><div><label>Chaos scenarios</label><input id="rounds" placeholder="20"></div>
<div><label>Soak hours</label><input id="hours" placeholder="2"></div><div><label>Seed (repeats a run)</label><input id="seed" placeholder="empty = new random"></div>
<div class="w"><label>Network faults to try (Network suite)</label><input id="presetsList" placeholder="empty = the default set, or file names separated by commas"></div>
<div><label>Offline load: small photo</label><input id="sampleImage" placeholder="path"></div><div><label>Offline load: small video</label><input id="sampleVideo" placeholder="path"></div>
<div class="w"><label>Explore: sessions by name (one per line)</label><textarea id="sessions" rows="2"></textarea></div>
<div class="w"><label>Explore: auditions by name (one per line)</label><textarea id="auditions_text" rows="2"></textarea></div>
<div class="w"><label>Test project words (a project with one of these words is a test project)</label><div class="row2"><input id="words" placeholder="qa, test, sim, stress (comma separated)" style="flex:1"><button class="small" onclick="saveWords()">Save words</button></div></div>
</div></details></section>
<div class="startbar"><div id="warn" class="warn"></div><button id="start" class="go" onclick="start()">&#9654; Start</button><button id="pauseBtn" class="ghost" style="display:none" onclick="pauseRun()">&#9208; Pause</button><button id="stopBtn" class="stop" onclick="stop()">&#9632; Stop</button><button id="again" class="ghost" onclick="again()" style="display:none">&#8635; Run again with the same seed</button></div>
</div></div>
<div>
<div class="banner" id="banner">&#9888; A test is running. Do not use the mouse or keyboard on this Mac until it finishes. <u>To pause: hold the <b>Esc</b> key for 3 seconds</u>, or press <b>Pause</b>.</div>
<section class="card" id="runCard"><div class="hero"><div class="badge" id="badge">&#9654;</div><div style="flex:1"><h2 id="title">Ready</h2><div id="verdict"></div><div id="now" class="muted">Choose a Studio app, sign in, tick sessions and press Start.</div></div></div>
<div class="bar" id="runBar" style="display:none"><span style="width:0"></span></div><div class="muted" id="runMeta" style="margin-top:6px"></div>
<div class="tiles" id="tiles" style="display:none"></div>
<div id="results"></div>
<details id="logBox" style="display:none"><summary>Log</summary><pre id="log"></pre></details>
<div class="row2" style="margin-top:14px" id="report"></div>
<div class="row2" style="margin-top:10px"><button class="small ghost" onclick="openReports()">Open the reports folder</button></div></section>
</div></main>
<button class="quit" id="quitBtn" onclick="quitAsk()">&#9211; Quit Studio Tester</button>
<div class="pausebox" id="quitBox"><div class="pbox" style="text-align:left"><div class="pi" style="text-align:center">&#9888;&#65039;</div><h2 style="text-align:center">Close Studio Tester?</h2>
<ul style="margin:10px 0 0;padding-left:20px"><li>The <b>tester script stops</b> and <b>this page stops working</b>. It cannot open again by itself.</li>
<li id="quitBusy" style="display:none;color:#8a1f19;font-weight:700">A test is running right now. It will be <b>cancelled</b> (Studio is left normal and the report is saved).</li>
<li>Your collected projects, settings and reports are <b>kept</b>.</li>
<li>To use it again: double-click <b>Studio Tester.command</b> in the Studio Tester folder on your Desktop.</li></ul>
<div class="row2" style="justify-content:center;margin-top:20px"><button class="stop" onclick="quitNow()">Quit Studio Tester</button><button class="ghost" onclick="quitCancel()">Keep it open</button></div></div></div>
<div class="closed" id="closedBox"><div class="cb"><div class="e">&#128308;</div><h2>Studio Tester is closed</h2><p class="muted">The script has stopped. You can close this browser tab and the Terminal window.<br>To use it again, double-click <b>Studio Tester.command</b> in the Studio Tester folder on your Desktop.</p></div></div>
<div class="pausebox" id="pauseBox"><div class="pbox"><div class="pi">&#9208;</div><h2>Testing is paused</h2><p id="pauseWhy" style="margin:0 0 8px;font-weight:600"></p>
<p class="muted">Nothing more is clicked while it is paused. Studio keeps what it is doing: a take that is already recording keeps recording.</p>
<div class="row2"><button class="go" onclick="resumeRun()">&#9654; Continue</button><button class="stop" onclick="cancelRun()">&#9632; Cancel testing</button></div></div></div>
<div class="guide" id="guide" onclick="if(event.target===this)closeGuide()"><div class="gbox"><div class="ghead"><span style="font-size:26px">&#128214;</span><h2>How to use Studio Tester</h2><a href="/guide.pdf" target="_blank" style="text-decoration:none"><button class="small ghost">Open the PDF guide</button></a><button class="small" onclick="closeGuide()">Close</button></div>
<div class="gbody">
<div class="note blue"><b>What is this?</b> A program that uses the Studio app by itself, like a real casting user: it records auditions, goes Back, loses the internet and tries to break things. After every step it checks that no video, photo or slate was lost or put in the wrong place. You press <b>Start</b> and read <b>PASS</b> or <b>FAIL</b>.</div>
<h3>Step by step</h3>
<div class="gstep"><div class="no">1</div><div><b>Choose the Studio app</b>Click <b>Studio (macOS) - Test</b> in the list. Nothing else shows until you choose one. If it is not in the list, press <b>Refresh</b> (it also searches other folders), or press <b>Open it</b> next to it.</div></div>
<div class="gstep"><div class="no">2</div><div><b>Sign in to Studio</b>If this page says <b>"You need to log in first"</b>, go to the Studio window and sign in with the <b>test account</b>. Press <b>Show the Studio window</b> if you cannot find it. This page continues <b>by itself</b> as soon as you are signed in. The tester never types your password.</div></div>
<div class="gstep"><div class="no">3</div><div><b>Collect the projects</b>Choose <b>First 10 projects</b> (fast) and press <b>Collect projects from the app</b>. The tester reads the projects and sessions. It only looks: it records nothing and changes nothing. Wait until it says <i>Collected ...</i></div></div>
<div class="gstep"><div class="no">4</div><div><b>Tick the sessions to test</b>Tick one or many sessions. Use the search box if the list is long (typing mistakes are fine). Grey projects are protected (not test projects): leave them alone.</div></div>
<div class="gstep"><div class="no">5</div><div><b>Choose how hard</b>Pick a card: <b>Quick check</b> (about 15 min) is the best first try. <b>Break it</b> tries to crash Studio. <b>Overnight</b> runs for hours.</div></div>
<div class="gstep"><div class="no">6</div><div><b>Press Start</b>Then <b>do not touch the mouse or keyboard</b>: the tester clicks for you. You can watch the progress bar and the list of steps. Press <b>Stop</b> to end it safely at any time.</div></div>
<div class="gstep"><div class="no">7</div><div><b>Read the result</b>A big <b>PASS</b> (green) or <b>FAIL</b> (red) shows. Each failed step has a short sentence that says what went wrong, with a screenshot link. To send the result, press <b>Show the zip to share</b>: it is one file with the whole report.</div></div>
<h3>What each button does</h3>
<table class="gtable">
<tr><td>How to use</td><td>Opens this guide.</td></tr>
<tr><td>Update</td><td>Checks for a newer tester right now. If there is one, it turns orange: press it and click OK. Your projects and reports are kept.</td></tr>
<tr><td>Show the Studio window</td><td>Brings Studio to the front, so you can sign in.</td></tr>
<tr><td>Collect projects from the app</td><td>Reads the project and session list from Studio (only looking).</td></tr>
<tr><td>Tick all usable / Untick all / Tick 5 random</td><td>Quick ways to choose sessions.</td></tr>
<tr><td>Start</td><td>Starts the test.</td></tr>
<tr><td>Pause / Esc held</td><td>Pauses the test. A window asks: <b>Continue</b> or <b>Cancel testing</b>.</td></tr>
<tr><td>Quit Studio Tester (bottom right)</td><td>Closes the tester program and this page, after a warning. A running test is cancelled first. Your projects, settings and reports are kept. To use it again, double-click <b>Studio Tester.command</b>.</td></tr>
<tr><td>Cancel testing</td><td>Stops the test at once and leaves Studio normal (no offline mode, no test faults, no camera label).</td></tr>
<tr><td>Run again with the same seed</td><td>Repeats exactly the same random run, to show developers a failure.</td></tr>
<tr><td>Open the report</td><td>A page with every step, the time and screenshots.</td></tr>
<tr><td>Show the zip to share</td><td>After every run the tester makes one zip with the whole report. This button shows it in Finder: drag it into Slack or an email. The zips are kept in the <b>Reports</b> folder next to <b>Studio Tester.command</b>.</td></tr>
<tr><td>Copy report text</td><td>Copies the result as text: paste it in your message.</td></tr>
<tr><td>Open the reports folder</td><td>Opens the <b>Reports</b> folder with the zip of every run.</td></tr></table>
<h3>Before a long or overnight test (do this once)</h3>
<div class="note orange" style="margin-top:0"><b>The display must never turn off and the Mac must never lock</b>, or the clicks stop. The tester keeps the Mac awake, but a screen that turned off or locked can still stop it. So set this in <b>System Settings</b> before you start:
<ol style="margin:6px 0 0"><li><b>Plug the Mac in</b> and keep the <b>lid open</b>.</li>
<li><b>System Settings &rarr; Lock Screen</b>: set <b>Start Screen Saver when inactive</b> to <b>Never</b>, and <b>Turn display off on power adapter when inactive</b> to <b>Never</b>.</li>
<li><b>System Settings &rarr; Battery &rarr; Options</b>: switch ON <b>Prevent automatic sleeping on power adapter when the display is off</b> (if you see it).</li></ol>
You can put the settings back after the test.</div>
<h3>While a test runs</h3>
<ul><li><b>Do not use the mouse or keyboard.</b> Do not close the Terminal window or Studio.</li><li><b>To pause:</b> hold the <b>Esc</b> key for 3 seconds (you hear a sound and this page comes to the front), or press <b>Pause</b>. Then choose <b>Continue</b> or <b>Cancel testing</b>. While paused, nothing more is clicked. A take that is already recording keeps recording.</li><li><b>To cancel:</b> press <b>Cancel testing</b>. It stops at once (not at the end of a long take). The steps not done yet are skipped and Studio is left normal.</li><li>If Studio closes or crashes, the tester <b>opens it again by itself</b> (after about 10 seconds), saves the crash report and writes a line in <b>incidents.txt</b>. The step that was running fails; the next steps carry on.</li><li><b>Overnight:</b> keep the Mac <b>plugged in with the lid open</b>. The tester stops the Mac from going to sleep while a test runs. It <b>cannot sign in for you</b>: if Studio comes back on the login screen, the next steps wait until you sign in.</li><li>Long runs take hours. The Mac must stay plugged in.</li></ul>
<h3>When something fails: what to send the developers</h3>
<ol><li>Press <b>Show the zip to share</b>. Finder shows a zip with the whole report. Send that file (drag it into Slack).</li><li>You can also press <b>Copy report text</b> and paste it in your message.</li><li>Say which card you ran, and the <b>seed</b> (it is in the log).</li></ol>
<h3>Common problems</h3>
<table class="gtable">
<tr><td>"App version not supported for testing"</td><td>An app marked <b>not supported</b> cannot be chosen and has no Open it button: click it to see why. It is an older build without the button names the tester needs. Testing only works with builds <b>starting from the branch merge/metadata-macos-v2-into-v2-offlinemode</b> (that build and every newer one). Install the latest <b>Studio (macOS) - Test</b> build and choose it.</td></tr>
<tr><td>"You need to log in first"</td><td>Sign in to Studio with the test account. This page continues by itself.</td></tr>
<tr><td>No Studio app in the list</td><td>Press <b>Open it</b> next to Studio (macOS) - Test, or open Studio yourself.</td></tr>
<tr><td>Start is grey and a red sentence shows</td><td>Read the sentence: usually no session is ticked, or the disk is too small.</td></tr>
<tr><td>Accessibility is off (red line in "This Mac")</td><td>Press <b>Open the setting</b> and switch ON <b>Terminal</b>.</td></tr>
<tr><td>"This test records auditions and needs the Test build"</td><td>You chose Develop, Staging or Production. Choose <b>Studio (macOS) - Test</b>.</td></tr>
<tr><td>The page does not open</td><td>Go to <span class="k">http://localhost:8765</span> in your browser and keep the Terminal window open.</td></tr>
<tr><td>Anything else</td><td>Send a screenshot of this page and of the Terminal window to the developers.</td></tr></table>
<p class="muted" style="margin-top:16px">Rules: test account and test projects only, never real auditions or customers. Do not share reports outside the team (they contain project names).</p>
</div></div></div>
<script>
const PAGE_VERSION='__PAGE_VERSION__';
let info={},catalog={projects:[]},checked=new Set(),allowReal=new Set(),lastSeed='',active='quick',loginSt={state:'none'},appSel=null;
const $=id=>document.getElementById(id);
const PRESETS={quick:['&#9889;','Quick check','about 15 min','Two short auditions in each ticked session.',{suite:'realistic',auditions:'2',profile:'short',mode:'online'}],
 normal:['&#9881;&#65039;','Normal','about 1 hour','Six auditions per session, mixed take lengths.',{suite:'realistic',auditions:'6',profile:'mixed',mode:'online'}],
 chaos:['&#128165;','Break it','about 1 hour','Random sabotage: bad network, button spam, app killed. Crashes are saved as evidence.',{suite:'chaos',rounds:'25',profile:'short'}],
 overnight:['&#127769;','Overnight','hours','Chaos for hours, all take lengths.',{suite:'chaos',rounds:'120',profile:'mixed'}]};
function drawPresets(){$('presets').innerHTML=Object.entries(PRESETS).map(([k,v])=>'<div class="preset'+(k==active?' on':'')+'" onclick="preset(\''+k+'\')"><span class="e">'+v[0]+'</span><b>'+v[1]+'</b><span class="tm">'+v[2]+'</span><p>'+v[3]+'</p></div>').join('');}
function preset(k){active=k;const v=PRESETS[k][4];$('suite').value=v.suite;$('auditions').value=v.auditions||'';$('rounds').value=v.rounds||'';$('profile').value=v.profile||'mixed';$('mode').value=v.mode||'online';drawPresets();suiteChanged();}
function suiteChanged(){$('suiteText').textContent=info.suites&&info.suites[$('suite').value]?info.suites[$('suite').value][1]:'';estimate();}
let updInfo=null;
function staleNote(u){const sb=$('staleBar');let msg='';
 if(u.loaded&&u.current&&u.current!==u.loaded)msg='The tester files on this Mac are version '+u.current+', but the program that is running is still '+u.loaded+'. Close it (Quit Studio Tester, bottom right) and open Studio Tester.command again.';
 else if(u.loaded&&PAGE_VERSION!=='__PAGE_VERSION__'&&PAGE_VERSION!==u.loaded)msg='This page is from an older version ('+PAGE_VERSION+'); the program is '+u.loaded+'. Reload the page: press Cmd + R.';
 sb.style.display=msg?'block':'none';sb.textContent=msg;}
function updUI(u){updInfo=u;$('ver').textContent='version '+(u.loaded||u.current);staleNote(u);const b=$('updBtn');
 if(u.available){b.textContent='Update to '+u.latest;b.style.background='#e08a00';$('updText').textContent=u.notes?u.notes:'A new version is available';}
 else if(u.error){b.textContent='Update';b.style.background='';$('updText').textContent=u.error;}
 else{b.textContent='Update';b.style.background='';$('updText').textContent='You have the latest version ('+u.current+')';}}
async function checkUpdate(){updUI(await (await fetch('/api/update')).json());}
async function updateClick(){$('updText').textContent='Checking for updates...';await checkUpdate();
 if(updInfo&&updInfo.available&&confirm('Update to '+updInfo.latest+' now? The tester restarts by itself and keeps your collected projects, settings and reports.'))await applyUpdate();}
async function applyUpdate(){$('updText').textContent='Updating...';$('updBtn').disabled=true;
 const r=await (await fetch('/api/update/apply',{method:'POST',body:'{}'})).json();$('updText').textContent=r.message;$('updBtn').disabled=false;if(r.ok)waitForRestart();}
async function waitForRestart(){$('updText').textContent='Updated. Restarting the tester...';$('updBtn').disabled=true;
 for(let i=0;i<120;i++){await new Promise(r=>setTimeout(r,2000));try{const r=await fetch('/api/update',{cache:'no-store'});if(r.ok&&i>=1){location.reload();return;}}catch(e){}}
 $('updText').textContent='The tester did not come back. Close this Terminal window and open Studio Tester.command again.';$('updBtn').disabled=false;}
async function load(){checkUpdate();info=await (await fetch('/api/info')).json();
 $('suite').innerHTML=Object.entries(info.suites).map(([k,v])=>'<option value="'+k+'">'+v[0]+'</option>').join('');
 $('camera').innerHTML='<option value="">Built-in camera (default)</option>'+info.cameras.filter(c=>c.usable&&!c.built_in).map(c=>'<option>'+c.name+'</option>').join('');
 $('setup').innerHTML=info.setup.map(s=>'<div class="cc '+(s[0]?'ok':'fix')+'"><i>'+(s[0]?'&#10003;':'!')+'</i><span>'+esc(s[1])+' '+(s[0]?'':fixButton(s[1]))+'</span></div>').join('');
 $('words').value=(info.words_extra||[]).join(', ');preset('quick');await loadCatalog();}
function fixButton(t){if(/Accessibility/.test(t))return '<button class="small" onclick="fix(\'accessibility\')">Open the setting</button>';if(/camera/i.test(t))return '<button class="small" onclick="fix(\'camera\')">Open the setting</button>';return '';}
async function fix(w){await fetch('/api/fix',{method:'POST',body:JSON.stringify({what:w})});}
async function loadCatalog(){catalog=await (await fetch('/api/catalog')).json();drawTree();}
let found=null;async function search(){const q=$('find').value.trim();if(!q){found=null;drawTree();return;}const r=await (await fetch('/api/search',{method:'POST',body:JSON.stringify({q})})).json();found=new Set(r.ids);drawTree();}
function drawTree(){const q=$('find').value.trim().toLowerCase();const t=$('tree');if(!catalog.projects.length){t.innerHTML='<small>Nothing collected yet.</small>';updatePicked();return;}
 t.innerHTML=catalog.projects.map(p=>{const ss=p.sessions.filter(s=>!q||(found?found.has(s.id):(p.name+' '+s.name).toLowerCase().includes(q)));if(!ss.length)return '';
 const lock=!p.is_test;return '<div class="proj '+(lock?'grey':'')+'">'+esc(p.name)+' <span class="tag '+(lock?'no':'')+'">'+(lock?'not a test project':'test project')+'</span>'+(lock?'<label style="font-weight:400;font-size:12px"><input type="checkbox" '+(allowReal.has(p.id)?'checked':'')+' onchange="allow(\''+p.id+'\',this.checked)"> use anyway</label>':'')+'</div>'+
 ss.map(s=>{const dis=(!s.usable)||(lock&&!allowReal.has(p.id));return '<div class="sess '+(dis?'grey':'')+'"><label><input type="checkbox" '+(dis?'disabled ':'')+(checked.has(s.id)?'checked ':'')+'onchange="tick(\''+s.id+'\',this.checked)"> '+esc(s.name)+' <span class="t">'+(s.usable?(s.talents.length+(s.talents.length==1?' talent':' talents')):'no talents scheduled')+'</span></label></div>'}).join('')}).join('');updatePicked();}
function tick(id,on){on?checked.add(id):checked.delete(id);updatePicked();}
function allow(id,on){on?allowReal.add(id):allowReal.delete(id);if(!on)catalog.projects.filter(p=>p.id==id).forEach(p=>p.sessions.forEach(s=>checked.delete(s.id)));drawTree();}
function selectAll(on){checked.clear();if(on)catalog.projects.forEach(p=>{if(p.is_test||allowReal.has(p.id))p.sessions.forEach(s=>{if(s.usable)checked.add(s.id)})});drawTree();}
async function randomN(){const r=await (await fetch('/api/random',{method:'POST',body:JSON.stringify({count:5})})).json();checked.clear();r.ids.forEach(i=>checked.add(i));drawTree();}
function updatePicked(){$('picked').textContent=checked.size+' session(s) ticked. '+(catalog.collected_at?'Collected '+catalog.collected_at.replace('T',' ')+(catalog.complete?'':' (not complete)'):'');estimate();drawSteps();}
async function saveWords(){await fetch('/api/settings',{method:'POST',body:JSON.stringify({test_words:$('words').value.split(',').map(x=>x.trim()).filter(Boolean)})});await loadCatalog();}
async function collect(){await fetch('/api/collect',{method:'POST',body:JSON.stringify({limit:$('limit').value})});}
async function collectStop(){await fetch('/api/collect-stop',{method:'POST'});}
function options(){return {picked:JSON.stringify([...checked]),allow_real:JSON.stringify([...allowReal]),auditions:$('auditions').value,rounds:$('rounds').value,hours:$('hours').value,profile:$('profile').value,mix:$('mix').value,mode:$('mode').value,seed:$('seed').value,presets:$('presetsList').value,sample_image:$('sampleImage').value,sample_video:$('sampleVideo').value,sessions:$('sessions').value,auditions_text:$('auditions_text').value};}
async function estimate(){if(!info.suites)return;const r=await (await fetch('/api/estimate',{method:'POST',body:JSON.stringify({suite:$('suite').value,options:options()})})).json();
 $('estimate').style.display=r.text?'block':'none';$('estimate').innerHTML=r.text||'';$('warn').textContent=r.problem||'';$('start').disabled=!!r.problem&&r.blocking;}
async function start(){const r=await fetch('/api/start',{method:'POST',body:JSON.stringify({suite:$('suite').value,camera:$('camera').value,options:options()})});
 if(!r.ok){const e=await r.json();$('warn').textContent=e.error||'Could not start';}}
async function openReports(){await fetch('/api/open-reports',{method:'POST',body:'{}'});}
async function stop(){if(window.running&&!confirm('Cancel the test now? It stops at once; the steps not done yet are skipped.'))return;await fetch('/api/cancel',{method:'POST'});}
async function pauseRun(){await fetch('/api/pause',{method:'POST',body:'{}'});}
async function resumeRun(){await fetch('/api/resume',{method:'POST',body:'{}'});}
async function cancelRun(){await fetch('/api/cancel',{method:'POST'});$('pauseBox').style.display='none';}
function again(){$('seed').value=lastSeed;start();}
function openGuide(){$('guide').style.display='flex';document.body.style.overflow='hidden';}
function closeGuide(){$('guide').style.display='none';document.body.style.overflow='';}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeGuide();quitCancel();}});
function quitAsk(){$('quitBusy').style.display=window.running?'list-item':'none';$('quitBox').style.display='flex';}
function quitCancel(){$('quitBox').style.display='none';}
async function quitNow(){$('quitBox').style.display='none';try{await fetch('/api/quit',{method:'POST',body:'{}'});}catch(e){}
 $('closedBox').style.display='flex';try{window.close();}catch(e){}}
function supBadge(x){x=x||{};if(x.state==='ok')return '<span class="sup ok" title="This build has the button names the tester needs">can be tested'+(x.version?' - '+esc(x.version):'')+'</span>';
 if(x.state==='unsupported')return '<span class="sup no">not supported'+(x.version?' - '+esc(x.version):'')+'</span>';if(x.state==='checking')return '<span class="sup wait">checking...</span>';return '';}
let unsupNote=null;
function showUnsup(i){unsupNote=APPS[i];applyGate();}
let APPS=[];
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
async function appsList(){const r=await (await fetch('/api/apps')).json();APPS=r.running.concat(r.installed);appSel=r.selected_row;
 $('checkedAt').textContent='Last checked '+(r.checked_at||'')+(r.searched_at?' - searched the whole Mac at '+r.searched_at:'');
 const row=(a,i,run)=>{const sel=r.selected==a.path;
  const un=(a.support||{}).state==='unsupported';
  return '<div class="app'+(sel?' sel':'')+(un?' unsup':'')+'" '+(un?'onclick="showUnsup('+i+')" title="This app cannot be tested: click to see why"':(run?'onclick="pick('+i+')"':''))+'><input type="radio" '+(sel?'checked ':'')+((run&&!un)?'':'disabled')+'><div style="flex:1;min-width:0"><div><b>'+esc(a.name)+'</b> <span class="kind '+a.kind+'">'+a.label+'</span></div>'+
   '<div class="meta">'+supBadge(a.support).replace('margin-left:4px','')+' <small class="muted">in '+esc(a.where||'')+'</small> '+(run?'<small class="muted">&middot; running (pid '+a.pid+')</small>':'<small class="muted">&middot; not open</small>')+'</div>'+
   (un?'<div class="meta" style="color:#8a1f19;font-size:12px;font-weight:600">&#9940; Cannot be chosen. Click to see why.</div>':'')+'</div>'+
   ((run||un)?'':'<button class="small" onclick="event.stopPropagation();openApp('+i+')">Open it</button>')+'</div>';};
 $('apps').innerHTML=r.running.length?r.running.map((a,i)=>row(a,i,true)).join(''):'<div class="note red">No Studio app is running. Open one below, press <b>Refresh</b> to look again, or open Studio yourself.</div>';
 $('appsNot').innerHTML=r.installed.length?'<p class="sub" style="margin:12px 0 0">Installed, not open:</p>'+r.installed.map((a,i)=>row(a,r.running.length+i,false)).join(''):'';
 const sel=r.selected_row;
 let warn=!sel?'Choose a Studio app to continue.':(!r.selected_running?'The chosen Studio is not open. The tester opens it when you start, and opens it again if it closes during a test.':'');
 if(sel&&sel.kind=='production')warn='Production is chosen: only Collect, Smoke and Explore (they only look) are allowed. Recording tests need the Test build.';
 if(sel&&sel.support&&sel.support.state==='unsupported')warn='';
 $('appWarn').style.display=warn?'block':'none';$('appWarn').textContent=warn;
 if(window.lastSel!==r.selected){window.lastSel=r.selected;loginTick();estimate();}
 applyGate();}
async function refreshApps(){const b=$('refreshBtn');b.disabled=true;b.innerHTML='Searching...';$('checkedAt').textContent='Searching this Mac for Studio apps...';
 try{await fetch('/api/refresh-apps',{method:'POST',body:'{}'});}catch(e){}
 b.disabled=false;b.innerHTML='&#8635; Refresh';await appsList();}
async function pick(i){unsupNote=null;const e=await (await fetch('/api/select-app',{method:'POST',body:JSON.stringify({path:APPS[i].path})})).json();if(e.error){const x=APPS[i];if(x&&x.support&&x.support.state==='unsupported'){unsupNote=x;applyGate();}else{$('appWarn').style.display='block';$('appWarn').textContent=e.error;}}appsList();}
async function openApp(i){await fetch('/api/open-app',{method:'POST',body:JSON.stringify({path:APPS[i].path})});}
async function focusApp(){await fetch('/api/focus-app',{method:'POST',body:'{}'});}
async function loginTick(){if(!appSel){loginSt={state:'none'};applyGate();return;}try{loginSt=await (await fetch('/api/login-state')).json();}catch(e){}applyGate();}
function applyGate(){const sel=!!appSel,st=loginSt.state;$('cLogin').style.display=sel?'block':'none';
 const sup=(appSel&&appSel.support)||{};const unsupported=sel&&sup.state==='unsupported';
 const note=unsupported?appSel:unsupNote;const ns=((note&&note.support)||{});const showNote=!!note&&ns.state==='unsupported';
 $('unsup').style.display=showNote?'block':'none';$('unsup').innerHTML=showNote?'<div style="font-size:16px;font-weight:800">&#9940; App version not supported for testing</div><div style="margin-top:8px">This app: <b>'+esc(note.name)+'</b>'+(ns.version?', version <b>'+esc(ns.version)+'</b>':'')+'</div><div style="margin-top:8px">Testing only works with builds <b>starting from this branch</b> (that build and every newer one):</div><div class="branch">'+esc(ns.branch||'merge/metadata-macos-v2-into-v2-offlinemode')+'</div><div style="margin-top:6px">Older builds do not have the button names the tester needs. Install the latest <b>Studio (macOS) - Test</b> build from that branch and choose it again.</div>':'';
 if(unsupported){$('cLogin').style.display='none';}
 const needLogin=sel&&st==='login';$('gate').style.display=sel&&!needLogin&&!unsupported?'block':'none';
 let h='';
 if(!sel||unsupported){h='';}
 else if(st==='login'){h='<div class="login"><div class="ic">&#128274;</div><div><h3>You need to log in first</h3><div class="muted">Studio is on the <b>login screen</b>. Sign in with the <b>test account</b> in the Studio window. Your projects and sessions appear here by themselves once you are signed in.</div><div class="note orange"><span class="pulse"></span>Waiting for you to sign in to Studio...</div><div class="row2" style="margin-top:10px"><button class="small" onclick="focusApp()">Show the Studio window</button></div></div></div>';}
 else if(st==='closed'){h='<div class="login"><div class="ic">&#128683;</div><div><h3>Studio is not open</h3><div class="muted">The tester opens it when you start. To sign in first, open it with the button.</div></div></div>';}
 else if(st==='signed_in'){h='<div class="note green" style="margin:0"><b>&#10003; Signed in.</b> Studio is open and ready.</div>';}
 else if(st==='unknown'){h='<div class="note blue" style="margin:0">Could not tell if Studio is signed in'+(loginSt.detail?' ('+esc(loginSt.detail)+')':'')+'. Continue if you are signed in with the test account.</div>';}
 $('loginBox').innerHTML=h;drawSteps();}
function drawSteps(){const st=loginSt.state,sel=!!appSel,run=window.running,fin=window.finished;
 const unsupApp=sel&&appSel&&appSel.support&&appSel.support.state==='unsupported';const S=[['Studio app',unsupApp?'bad':(sel?'done':'now')],['Sign in',!sel?'':(st==='login'?'bad':(st==='signed_in'||st==='unknown'?'done':'now'))],['Projects',(!sel||st==='login')?'':(checked.size?'done':'now')],['How hard',(!sel||st==='login'||!checked.size)?'':'now'],['Run',run?'now':(fin?'done':'')]];
 $('steps').innerHTML=S.map((x,i)=>'<div class="step '+x[1]+'"><span class="dot">'+(x[1]==='done'?'&#10003;':(x[1]==='bad'?'!':(i+1)))+'</span>'+x[0]+'</div>').join('');}
function dur(sec){sec=Math.max(0,Math.round(sec));const h=Math.floor(sec/3600),m=Math.floor(sec%3600/60),s=sec%60;return (h?h+' h ':'')+(m||h?m+' min ':'')+s+' s';}
async function tick2(){appsList();
 const c=await (await fetch('/api/collect-state')).json();if(c.text)$('collectState').textContent=c.text;if(c.just_done){await loadCatalog();}
 $('collectBtn').disabled=c.running;$('collectBar').style.display=c.running?'block':'none';
 const s=await (await fetch('/api/state')).json();if(!s.suite){window.running=false;$('pauseBox').style.display='none';return;}
 const running=!s.finished;window.running=running;window.finished=!running;$('banner').style.display=running?'block':'none';
 const ctl=s.control||{};$('pauseBox').style.display=(running&&ctl.paused)?'flex':'none';$('pauseWhy').textContent=ctl.paused?(ctl.reason==='Esc held'?'You held the Esc key.':'Paused from the page.')+' Paused for '+ctl.paused_for+' s.':'';
 $('pauseBtn').style.display=running?'inline-block':'none';$('stopBtn').innerHTML=running?'&#9632; Cancel testing':'&#9632; Stop';
 const total=s.results.length,done=s.counts.passed+s.counts.failed+s.counts.skipped,pct=total?Math.round(done*100/total):0;
 $('title').textContent=(running?'Running: ':'Finished: ')+s.suite;
 const act=s.results.find(r=>r.status=='running');$('now').innerHTML=running?(act?'Now: <b>'+esc(act.name)+'</b>':'Starting...'):('Finished at '+s.finished.replace('T',' '));
 const fail=s.counts.failed>0;$('badge').className='badge '+(running?'run':(fail?'fail':(s.counts.passed?'pass':'')));$('badge').innerHTML=running?'&#9203;':(fail?'&#10060;':(s.counts.passed?'&#9989;':'&#8213;'));
 $('verdict').innerHTML=running?'':(fail?'<div class="verdict fail">FAIL</div>':(s.counts.passed?'<div class="verdict pass">PASS</div>':'<div class="verdict">NOTHING RAN</div>'));
 $('runBar').style.display='block';$('runBar').className='bar'+(running?' anim':'');$('runBar').firstChild.style.width=pct+'%';
 const started=new Date(s.started),endt=s.finished?new Date(s.finished):new Date();
 $('runMeta').textContent=done+' of '+total+' steps ('+pct+'%) - elapsed '+dur((endt-started)/1000)+' - Studio: '+(s.build||'').split('/').pop().replace('.app','')+' - Camera: '+(s.camera||'none');
 $('tiles').style.display='grid';$('tiles').innerHTML='<div class="tile p"><b>'+s.counts.passed+'</b><span>Passed</span></div><div class="tile f"><b>'+s.counts.failed+'</b><span>Failed</span></div><div class="tile s"><b>'+s.counts.skipped+'</b><span>Skipped</span></div><div class="tile"><b>'+(s.counts.waiting+s.counts.running)+'</b><span>To go</span></div>';
 $('results').innerHTML=s.results.map(r=>{const links=(r.files||[]).map(f=>'<a href="/reports/'+s.folder+'/'+f+'" target="_blank">'+esc(f.replace(/^fail_\d+_/,''))+'</a>').join('');
  return '<div class="res"><span class="pill '+r.status+'">'+r.status.toUpperCase()+'</span><div class="nm">'+esc(r.name)+(r.message?'<div class="fmsg '+(r.status=='skipped'?'sk':'')+'">'+esc(r.message)+(links?'<div style="margin-top:4px">'+links+'</div>':'')+'</div>':'')+'</div><span class="tm">'+(r.seconds?dur(r.seconds):'')+'</span></div>';}).join('');
 $('logBox').style.display='block';$('log').textContent=s.log.join('\n');const seedLine=s.log.find(l=>/seed \d+/.test(l));if(seedLine)lastSeed=(seedLine.match(/seed (\d+)/)||[])[1]||lastSeed;
 $('report').innerHTML=s.finished?'<a href="/reports/'+s.folder+'/report.html" target="_blank" style="text-decoration:none"><button class="small">Open the report</button></a><button class="small" onclick="revealReport(\''+s.folder+'\')">'+(s.shared_zip?'Show the zip to share':'Show the report folder')+'</button><button class="small ghost" onclick="copyReport(\''+s.folder+'\')">Copy report text</button>':'';
 $('again').style.display=(s.finished&&lastSeed)?'inline-block':'none';$('start').disabled=running;drawSteps();}
async function revealReport(f){await fetch('/api/reveal-report',{method:'POST',body:JSON.stringify({folder:f})});}
async function copyReport(f){const t=await (await fetch('/reports/'+f+'/results.json')).text();await navigator.clipboard.writeText(t);alert('Copied. Paste it in the message to the developers.');}
load();try{if(!localStorage.getItem('guideSeen')){openGuide();localStorage.setItem('guideSeen','1');}}catch(e){}
setInterval(tick2,1000);setInterval(loginTick,3000);setInterval(checkUpdate,300000);
</script></body></html>"""
