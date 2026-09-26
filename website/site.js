/* ============================================================
   Snapdragon AI Smart Process Manager — Competition Showcase
   Presentation layer. Reads the frozen Python backend when
   reachable, else uses the bundled validation snapshot.
   No AI/safety logic duplicated: every prediction/decision/
   projection comes from backend JSON.
   ============================================================ */
const qs = new URLSearchParams(location.search);
let API = qs.get('api') || localStorage.getItem('snap_api') || 'http://127.0.0.1:8099';
let SNAP = null, MODE = 'live';
let ROWS = [];
let tourIx = -1;
let isLight = false;

const $ = id => document.getElementById(id);

/* ── Theme toggle ── */
function initTheme() {
  const saved = localStorage.getItem('snap_theme');
  if (saved === 'light') {
    document.body.classList.add('light-theme');
    isLight = true;
  }
  // Add theme toggle button
  const btn = document.createElement('div');
  btn.className = 'theme-toggle';
  btn.title = isLight ? 'Switch to dark theme' : 'Switch to light theme';
  btn.textContent = isLight ? '\u263D' : '\u2600';
  btn.onclick = () => {
    isLight = !isLight;
    document.body.classList.toggle('light-theme', isLight);
    localStorage.setItem('snap_theme', isLight ? 'light' : 'dark');
    btn.textContent = isLight ? '\u263D' : '\u2600';
  };
  document.body.appendChild(btn);
}

/* ── Fetch helpers ── */
async function get(path, timeout = 15000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(API + path, { signal: ctl.signal });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } finally { clearTimeout(t); }
}

async function loadSnapshot() {
  if (!SNAP) SNAP = await (await fetch('assets/snapshot.json')).json();
  return SNAP;
}

async function D(path) {
  if (MODE === 'live') return get(path);
  const s = await loadSnapshot();
  const m = {
    '/api/platform': s.platform,
    '/api/stats': s.stats,
    '/api/ai_status': s.ai_status,
    '/api/backends': s.backends,
    '/api/safety': s.safety,
    '/api/npu_validation': s.npu_validation,
  };
  if (m[path]) return m[path];
  if (path.startsWith('/api/processes')) return s.processes;
  if (path.startsWith('/api/decisions')) return { records: s.decisions.records };
  if (path.startsWith('/api/demo')) {
    const set = new URLSearchParams(path.split('?')[1]).get('set');
    return s['demo_' + set] || s.demo_presentation;
  }
  if (path.startsWith('/api/optimization/preview')) {
    const q = new URLSearchParams(path.split('?')[1]);
    const k = 'demo_' + q.get('set') + '_preview' + q.get('index');
    if (s[k]) return s[k];
    const d = s['demo_' + q.get('set')] || s.demo_presentation;
    const r = d.rows[+q.get('index') || 0];
    return {
      simulated: true, simulation: true, process: r.name,
      model_class: r.ai.model_class, safety_state: r.ai.safety_state,
      simulated_action: r.ai.safety_state === 'OPTIMIZATION CANDIDATE' ? 'SIMULATED_ACTION' : 'NO_ACTION',
      labels: ['SIMULATED', 'PROJECTED'], why: r.ai.why || []
    };
  }
  if (path.startsWith('/api/optimization/simulate'))
    return {
      simulated: true,
      stages: ['ANALYZING', 'SAFETY_CHECK', 'SIMULATING', 'PROJECTED_RESULT'],
      note: 'Snapshot fallback: run against the live backend for full simulation.'
    };
  throw new Error('no snapshot for ' + path);
}

/* ── Boot ── */
async function boot() {
  initTheme();

  // SPA navigation
  const sections = document.querySelectorAll('section');
  const navLinks = document.querySelectorAll('#nav a');
  function setActive(hash) {
    sections.forEach(s => s.classList.remove('active'));
    const target = document.querySelector(hash);
    if (target) {
      target.classList.add('active');
      navLinks.forEach(a => {
        a.classList.toggle('active', a.getAttribute('href') === hash);
      });
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }
  navLinks.forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      const hash = a.getAttribute('href');
      history.pushState(null, '', hash);
      setActive(hash);
    });
  });
  window.addEventListener('popstate', () => setActive(location.hash || '#home'));
  setActive(location.hash || '#home');

  try {
    await get('/api/ai_status', 5000);
    MODE = 'live';
  } catch (e) {
    MODE = 'demo';
    await loadSnapshot();
  }
  paintMode();
  await Promise.all([paintBackend(), paintSys(), paintProcs(), paintDecisions(),
    paintEvidence(), paintPhases(), paintPlatform(), paintNpuComparison()]);

  // Event handlers
  $('btn-live').onclick = async () => {
    localStorage.setItem('snap_api', API);
    MODE = 'live';
    try { await get('/api/ai_status', 5000); } catch (e) { MODE = 'demo'; await loadSnapshot(); }
    paintMode(); location.reload();
  };
  $('btn-demo').onclick = async () => { MODE = 'demo'; await loadSnapshot(); paintMode(); location.reload(); };
  $('q').oninput = paintProcs;
  $('fstate').onchange = paintProcs;
  $('dstate').onchange = paintDecisions;
  $('cta-demo').onclick = () => { location.hash = '#dashboard'; setActive('#dashboard'); startTour(); };
  $('tour-start').onclick = startTour;
  $('tour-stop').onclick = stopTour;
  $('tour-next').onclick = tourNext;
  $('simrun').onclick = runSim;

  // Auto-refresh live data
  setInterval(async () => {
    if (MODE === 'live' && $('dashboard').classList.contains('active')) {
      try { await paintSys(); await paintProcs(); } catch (e) {}
    }
  }, 5000);
}

/* ── Mode ── */
function paintMode() {
  $('modebar').hidden = MODE !== 'demo';
  $('dash-src').textContent = MODE === 'live' ? 'LIVE' : 'SNAPSHOT DEMO';
  $('btn-demo').classList.toggle('on', MODE === 'demo');
  $('btn-live').classList.toggle('on', MODE === 'live');
}

/* ── Backend pill ── */
async function paintBackend() {
  try {
    const s = await D('/api/ai_status');
    $('backend-pill').textContent = 'AI: ' + s.selected_backend;
  } catch (e) { $('backend-pill').textContent = 'AI: unknown'; }
}

/* ── System cards ── */
async function paintSys() {
  const s = await D('/api/stats');
  const cards = [
    ['CPU', s.cpu.total_pct + '%'],
    ['RAM', s.memory.used_gb + '/' + s.memory.total_gb + ' GB'],
    ['Disk C:', s.disk.pct + '%'],
    ['Network', '\u2193' + s.net.mb_recv + 'MB \u2191' + s.net.mb_sent + 'MB'],
    ['Battery', s.battery.present ? s.battery.percent + '%' : 'n/a'],
    ['Uptime', Math.floor(s.uptime_s / 3600) + 'h'],
    ['Cores', s.cpu.logical + ' logical'],
  ];
  $('syscards').innerHTML = cards.map(c =>
    `<div class="card"><div class="dim">${c[0]}</div><div class="big">${c[1]}</div></div>`
  ).join('');
}

/* ── Platform info ── */
async function paintPlatform() {
  try {
    const p = await D('/api/platform');
    const cards = [
      ['Operating System', p.os.system + ' ' + p.os.release],
      ['Architecture', p.arch_normalized],
      ['CPU', p.cpu_name],
      ['ARM', p.is_arm ? 'Yes' : 'No'],
      ['Snapdragon', p.is_snapdragon ? 'Yes' : 'No'],
      ['Backend', p.phase_routing ? p.phase_routing.onnx_backend : 'unknown'],
    ];
    $('platform-cards').innerHTML = cards.map(c =>
      `<div class="card"><h4>${c[0]}</h4><p>${c[1]}</p></div>`
    ).join('');
  } catch (e) {}
}

/* ── Process table ── */
async function paintProcs() {
  const p = await D('/api/processes?limit=50&sort=cpu');
  ROWS = p.rows;
  const q = ($('q').value || '').toLowerCase(), fs = $('fstate').value;
  const rows = ROWS.filter(r =>
    (!q || r.name.toLowerCase().includes(q)) &&
    (!fs || ((r.ai || {}).safety_state === fs))
  );
  $('pcount').textContent = p.count + ' processes';
  $('procs').innerHTML = rows.map((r, i) => {
    const ai = r.ai || {};
    return `<tr data-i="${ROWS.indexOf(r)}">
      <td>${r.name}</td>
      <td>${r.pid}</td>
      <td>${r.cpu_pct}</td>
      <td>${r.mem_pct}</td>
      <td>${r.arch || '?'}</td>
      <td>${ai.ai_class || '\u2026'}</td>
      <td>${ai.final_confidence == null ? '\u2026' : (ai.final_confidence * 100).toFixed(0) + '%'}</td>
      <td>${ai.familiarity_level || '\u2026'}</td>
      <td><b>${ai.safety_state || '\u2026'}</b> \u2014 ${ai.recommendation || ''}</td>
    </tr>`;
  }).join('');
  document.querySelectorAll('#procs tr').forEach(tr =>
    tr.onclick = () => trace(ROWS[+tr.dataset.i])
  );
}

/* ── AI Pipeline trace ── */
function trace(r) {
  if (!r || !r.ai) return;
  const ai = r.ai;
  document.querySelectorAll('.pstep').forEach((el, i) => {
    el.classList.remove('lit');
    setTimeout(() => el.classList.add('lit'), 250 * (i + 1));
  });
  $('trace-title').textContent = `${r.name} (pid ${r.pid}, ${r.arch || 'unknown arch'})`;
  $('trace').innerHTML =
    `<p><b>MODEL PREDICTION:</b> ${ai.model_class} (raw ${(ai.raw_confidence * 100).toFixed(1)}%) \u2014 what the neural network thinks.</p>` +
    `<p><b>CALIBRATED CONFIDENCE:</b> ${(ai.final_confidence * 100).toFixed(1)}% (final) \u2014 raw softmax \u00d7 familiarity.</p>` +
    `<p><b>FAMILIARITY:</b> ${ai.familiarity_level || ai.familiarity} \u2014 ${ai.ood ? 'OUT-OF-DISTRIBUTION' : 'KNOWN'}.</p>` +
    `<p><b>SAFETY DECISION:</b> ${ai.safety_state} \u2192 ${ai.recommendation} \u2014 whether the system allows optimization.</p>` +
    `<p><b>WHY:</b> ${(ai.why || []).join(' + ')}</p>` +
    `<p class="dim">AI predicts. Safety policy decides.</p>`;

  // Scroll to trace card
  document.querySelector('.trace-card')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ── Decision history ── */
async function paintDecisions() {
  const d = await D('/api/decisions?limit=60');
  const fs = $('dstate').value;
  const rows = d.records.filter(r => !fs || r.safety_state === fs).slice(-30).reverse();
  $('dcount').textContent = d.records.length + ' logged';
  $('decrows').innerHTML = rows.map(r =>
    `<tr>
      <td>${(r.timestamp || '').slice(11) || (r.timestamp || '')}</td>
      <td>${r.process}</td>
      <td>${r.model_class || ''}</td>
      <td>${r.final_confidence == null ? '' : (r.final_confidence * 100).toFixed(0) + '%'}</td>
      <td>${r.familiarity_level || r.familiarity || ''}</td>
      <td><b>${r.safety_state}</b></td>
      <td>${r.recommendation || ''}</td>
      <td>${r.simulation ? '<span class="tag tag-orange">SIMULATED</span>' : 'observed'}</td>
    </tr>`
  ).join('');
}

/* ── Evidence grid ── */
async function paintEvidence() {
  const facts = [
    ['74 / 74 tests passed', 'Unit + integration suites'],
    ['1.9 KB ONNX model', 'MLP 11\u219216\u21928\u21924'],
    ['11-feature model', 'Documented order + scaler'],
    ['Temperature scaling T=2.0', 'Calibrated confidence'],
    ['OOD familiarity detection', 'Centroid-distance model'],
    ['Snapdragon X Elite CRD validation', 'Hosted reference platform'],
    ['10/10 profiled nodes on NPU', 'Job jpxlrj1lp'],
    ['4/4 CPU/NPU agreement', 'Job j5wlrew3p, diff 0.0015'],
    ['0 destructive operations', 'Audited; guard enforced'],
    ['0 secrets in package', 'Scanned and verified'],
    ['~1% monitoring CPU', 'Development observation'],
    ['~70 MB RAM', 'Development observation'],
  ];
  $('evgrid').innerHTML = facts.map(f =>
    `<div class="card"><h3>${f[0]}</h3><p class="dim">${f[1]}</p></div>`
  ).join('');
}

/* ── NPU comparison table ── */
async function paintNpuComparison() {
  const cpu = {
    'protected': [0.8387, 0, 0.0147, 0.1465],
    'foreground': [0, 1, 0, 0],
    'flexible': [0, 0.0191, 0.9809, 0],
    'deferrable': [0.0009, 0, 0.0051, 0.994]
  };
  const S = await loadSnapshot().catch(() => null);
  $('cmp').innerHTML = ['protected', 'foreground', 'flexible', 'deferrable'].map(k => {
    const nv = S && S.npu_comparison && S.npu_comparison[k];
    return `<tr>
      <td>${k}</td>
      <td>${cpu[k].indexOf(Math.max(...cpu[k]))}</td>
      <td>${nv ? nv.label : 'pending live backend'}</td>
      <td>${nv ? nv.maxdiff : '\u2014'}</td>
      <td>${nv ? (nv.agree ? '\u2705' : '\u274C') : '\u2014'}</td>
    </tr>`;
  }).join('');
}

/* ── Project phases (for status section) ── */
async function paintPhases() {
  const rows = [
    ['Phase 1 \u2014 System observation', 'VERIFIED'],
    ['Phase 2 \u2014 AI model', 'VERIFIED'],
    ['Phase 2.5 \u2014 Calibration / OOD / safety', 'VERIFIED'],
    ['Phase 2.7 \u2014 Low-overhead monitoring', 'VERIFIED'],
    ['Phase 3 \u2014 Safe optimization simulator', 'VERIFIED'],
    ['Phase 4 \u2014 Qualcomm NPU model validation', 'VERIFIED (model level; HP app requires hardware)'],
  ];
  const el = $('phases');
  if (el) el.innerHTML = rows.map(r =>
    `<tr><td>${r[0]}</td><td><b>${r[1]}</b></td></tr>`
  ).join('');
}

/* ── Simulator ── */
async function runSim() {
  const set = $('simset').value;
  const d = await D('/api/demo?set=' + set);
  const out = $('simout');
  out.innerHTML = `<p><span class="tag tag-orange">SIMULATED / PROJECTED</span> ${d.description} \u2014 synthetic processes, real model.</p>`;
  for (let i = 0; i < d.rows.length; i++) {
    const pv = await D(`/api/optimization/preview?set=${set}&index=${i}`);
    const r = d.rows[i];
    out.innerHTML += `<div class="card"><h3>${r.name}</h3>` +
      `<p>AI: <b>${pv.model_class}</b> (${(pv.raw_confidence * 100).toFixed(0)}%) \u00b7 ` +
      `Safety: <b>${pv.safety_state}</b> \u00b7 Proposed: <b>${(pv.simulated_action || '').replaceAll('_', ' ')}</b> ` +
      `<span class="tag tag-orange">SIMULATED</span></p>` +
      `<p class="dim">WHY? ${(pv.why || []).slice(0, 3).join(' + ')}</p>` +
      `<button data-i="${i}" class="btn-small">SIMULATE</button><div class="simres"></div></div>`;
  }
  out.querySelectorAll('button').forEach(b => b.onclick = async () => {
    const s = await D(`/api/optimization/simulate?set=${set}&index=${b.dataset.i}`);
    b.parentElement.querySelector('.simres').innerHTML =
      `<div class="sim-result">` +
      `<p>${(s.stages || []).map((st, i) => `<span class="sim-stage ${i < 3 ? 'done' : 'active'}">${st}</span>`).join(' \u2192 ')}</p>` +
      `<p>Result: <b>${(s.simulated_action || '').replaceAll('_', ' ')}</b> \u00b7 ${s.projected_effect || ''} <span class="tag tag-orange">PROJECTED</span></p>` +
      `</div>`;
  });
}

/* ── Guided Tour ── */
const TOUR = [
  ['#dashboard', 'System overview \u2014 real telemetry cards and the process table.'],
  ['#dashboard', 'Process intelligence \u2014 filter by state; click any row to trace it.'],
  ['#ai', 'AI classification \u2014 watch the pipeline light up for the selected process.'],
  ['#ai', 'Confidence \u00d7 familiarity decides; raw softmax never rules alone.'],
  ['#safety', 'Safety decision \u2014 PROTECT is the default under uncertainty.'],
  ['#simulator', 'Optimization simulator \u2014 SIMULATED badges on every projection.'],
  ['#decisions', 'Decision history \u2014 model vote vs safety decision, with reasons.'],
  ['#npu', 'Snapdragon NPU evidence \u2014 real Qualcomm job IDs and 4/4 agreement.'],
  ['#architecture', 'Full architecture \u2014 from telemetry to safe recommendation.'],
];

function startTour() {
  tourIx = -1;
  $('tourbar').hidden = false;
  tourNext();
}
function stopTour() {
  $('tourbar').hidden = true;
  tourIx = -1;
}
function tourNext() {
  tourIx++;
  if (tourIx >= TOUR.length) { stopTour(); return; }
  const hash = TOUR[tourIx][0];
  location.hash = hash;
  setActive(hash);
  $('tourtitle').textContent = `Demo ${tourIx + 1}/${TOUR.length}`;
  $('tourtext').textContent = TOUR[tourIx][1];
  $('tour-progress').style.width = `${((tourIx + 1) / TOUR.length) * 100}%`;
}

/* ── Start ── */
boot();

/* ============================================================
   INTERACTIVE TECHNOLOGY ENVIRONMENT
   Cursor-based particle system + scene transitions
   ============================================================ */

const InteractiveEngine = (() => {
  const nodes = document.querySelectorAll('.inode');
  const scenes = document.querySelectorAll('.scene');
  const contextPanel = document.getElementById('context-panel');
  const canvas = document.getElementById('cursor-canvas');
  const sceneContainer = document.getElementById('scene-container');

  let activeScene = null;
  let mouseX = 0, mouseY = 0;
  let particles = [];
  let rafId = null;
  let isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Context data for each technology node
  const contextData = {
    windows: {
      title: 'Windows 11',
      badge: 'WORKLOAD ENVIRONMENT',
      badgeClass: 'tag-blue',
      description: 'Windows 11 on Arm is the workload environment being observed. The system monitors running applications, background processes, and system services — all without taking destructive actions.',
      connections: ['Feeds workloads to Snapdragon platform', 'Provides process telemetry data', 'Foreground app detection', 'Architecture and emulation signals']
    },
    snapdragon: {
      title: 'Snapdragon Platform',
      badge: 'HARDWARE ACCELERATION',
      badgeClass: 'tag-green',
      description: 'The Snapdragon platform provides heterogeneous computing: CPU for general workloads, GPU for graphics, and Hexagon NPU for AI inference. On supported hardware, the NPU accelerates AI classification. On unsupported hardware (like the local Dell Intel machine), the system uses CPU fallback.',
      connections: ['Receives Windows workloads', 'Hexagon NPU executes AI inference', 'CPU fallback when NPU unavailable', 'Validated on Snapdragon X Elite CRD']
    },
    ai: {
      title: 'AI Workload Intelligence',
      badge: 'NEURAL NETWORK',
      badgeClass: 'tag-purple',
      description: 'An 11-feature neural network (11→16→8→4, ReLU, Softmax, ArgMax) classifies workloads. The model is 1.9 KB ONNX with temperature scaling T=2.0. Output classes: PROTECTED, USER_IMPORTANT, FLEXIBLE, DEFERRABLE.',
      connections: ['Receives 11 process features', 'Outputs 4-class prediction', 'Calibrated confidence score', 'Familiarity / OOD assessment']
    },
    safety: {
      title: 'Safety Engine',
      badge: 'DECISION GATE',
      badgeClass: 'tag-orange',
      description: 'The safety engine sits between AI prediction and any action. It applies deterministic rules: protected-process allowlist, foreground protection, confidence floors, and OOD unfamiliarity checks. AI predicts — safety decides.',
      connections: ['Receives AI prediction + confidence', 'Applies deterministic safety rules', 'Outputs PROTECT / OBSERVE / REVIEW / CANDIDATE', 'Cannot be bypassed by the AI']
    },
    optimization: {
      title: 'Optimization Recommendation',
      badge: 'SIMULATION ONLY',
      badgeClass: 'tag-green',
      description: 'Only after safety approval does the system generate recommendations. Every action is SIMULATED or PROJECTED — never executed. Possible outputs: REDUCE_BACKGROUND_ACTIVITY, DEFER_BACKGROUND_WORK, PROTECT_FOREGROUND_ACTIVITY, PROTECT_SYSTEM_CRITICAL_PROCESS.',
      connections: ['Only runs after safety approval', 'Non-destructive simulation', 'Projected effects only', 'Zero process-control operations']
    }
  };

  // Particle configurations per scene
  const particleConfigs = {
    windows: { count: 12, color: '#58a6ff', size: 3, speed: 0.8, shape: 'square' },
    snapdragon: { count: 16, color: '#e4002b', size: 2, speed: 1.2, shape: 'circle' },
    ai: { count: 14, color: '#bc8cff', size: 3, speed: 1.0, shape: 'circle' },
    safety: { count: 10, color: '#d29922', size: 4, speed: 0.6, shape: 'diamond' },
    optimization: { count: 8, color: '#3fb950', size: 3, speed: 0.7, shape: 'circle' }
  };

  // Scene descriptions for connected path highlighting
  const scenePaths = {
    windows: ['windows'],
    snapdragon: ['windows', 'snapdragon'],
    ai: ['snapdragon', 'ai'],
    safety: ['ai', 'safety'],
    optimization: ['safety', 'optimization']
  };

  function init() {
    if (isReducedMotion) return;

    // Track mouse position
    document.addEventListener('mousemove', onMouseMove, { passive: true });
    document.addEventListener('mouseleave', onMouseLeave);

    // Node interactions
    nodes.forEach(node => {
      const scene = node.dataset.scene;
      node.addEventListener('mouseenter', () => activateScene(scene));
      node.addEventListener('click', () => activateScene(scene));
      node.addEventListener('focus', () => activateScene(scene));
      node.addEventListener('blur', () => deactivateScene());
      node.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          activateScene(scene);
        }
      });
    });

    // Click outside to deactivate
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.interactive-layout')) {
        deactivateScene();
      }
    });

    // Handle visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stopParticles();
      } else if (activeScene) {
        startParticles();
      }
    });

    // Handle scroll - pause when off-screen
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) {
          stopParticles();
        } else if (activeScene) {
          startParticles();
        }
      });
    }, { threshold: 0.1 });
    observer.observe(document.getElementById('interactive'));
  }

  function onMouseMove(e) {
    mouseX = e.clientX;
    mouseY = e.clientY;
    updateParticles();
  }

  function onMouseLeave() {
    stopParticles();
  }

  function activateScene(sceneName) {
    if (activeScene === sceneName) return;
    activeScene = sceneName;

    // Update nodes
    nodes.forEach(n => n.classList.toggle('active', n.dataset.scene === sceneName));

    // Update scenes
    scenes.forEach(s => s.classList.toggle('active', s.dataset.scene === sceneName));

    // Highlight connected path
    const path = scenePaths[sceneName] || [];
    nodes.forEach(n => {
      const isConnected = path.includes(n.dataset.scene);
      n.style.opacity = isConnected ? '1' : '.5';
    });

    // Update context panel
    updateContext(sceneName);

    // Start particles
    startParticles();
  }

  function deactivateScene() {
    activeScene = null;
    nodes.forEach(n => {
      n.classList.remove('active');
      n.style.opacity = '1';
    });
    scenes.forEach(s => s.classList.remove('active'));
    stopParticles();
    contextPanel.innerHTML = '<div class="context-placeholder"><p>Select a technology node to explore its role in the system.</p></div>';
  }

  function updateContext(sceneName) {
    const data = contextData[sceneName];
    if (!data) return;
    contextPanel.innerHTML = `
      <div class="context-content">
        <span class="context-badge ${data.badgeClass}">${data.badge}</span>
        <h4>${data.title}</h4>
        <p>${data.description}</p>
        <div class="context-connections">
          <h5>Connects to:</h5>
          <ul>${data.connections.map(c => `<li>${c}</li>`).join('')}</ul>
        </div>
      </div>
    `;
  }

  // Particle system
  function startParticles() {
    if (isReducedMotion || !activeScene || rafId) return;
    const config = particleConfigs[activeScene];
    if (!config) return;

    // Create canvas
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // Create particles
    particles = [];
    for (let i = 0; i < config.count; i++) {
      particles.push(createParticle(config));
    }

    // Start animation loop
    rafId = requestAnimationFrame(animateParticles);
  }

  function stopParticles() {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    particles = [];
    canvas.width = 0;
    canvas.height = 0;
  }

  function createParticle(config) {
    return {
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * config.speed,
      vy: (Math.random() - 0.5) * config.speed,
      size: config.size * (0.5 + Math.random()),
      color: config.color,
      shape: config.shape,
      opacity: 0.3 + Math.random() * 0.7
    };
  }

  function animateParticles() {
    if (!activeScene || document.hidden) {
      stopParticles();
      return;
    }

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const config = particleConfigs[activeScene];
    if (!config) {
      stopParticles();
      return;
    }

    particles.forEach(p => {
      // Move toward mouse slightly
      const dx = mouseX - p.x;
      const dy = mouseY - p.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 200 && dist > 0) {
        p.vx += (dx / dist) * 0.02;
        p.vy += (dy / dist) * 0.02;
      }

      // Apply velocity with damping
      p.vx *= 0.98;
      p.vy *= 0.98;
      p.x += p.vx;
      p.y += p.vy;

      // Wrap around screen
      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;

      // Draw particle
      ctx.save();
      ctx.globalAlpha = p.opacity;
      ctx.fillStyle = p.color;

      if (p.shape === 'circle') {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      } else if (p.shape === 'square') {
        ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
      } else if (p.shape === 'diamond') {
        ctx.beginPath();
        ctx.moveTo(p.x, p.y - p.size);
        ctx.lineTo(p.x + p.size, p.y);
        ctx.lineTo(p.x, p.y + p.size);
        ctx.lineTo(p.x - p.size, p.y);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();
    });

    // Draw cursor ring
    if (mouseX > 0 && mouseY > 0) {
      ctx.save();
      ctx.globalAlpha = 0.15;
      ctx.strokeStyle = config.color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(mouseX, mouseY, 30, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    rafId = requestAnimationFrame(animateParticles);
  }

  function updateParticles() {
    // Mouse position is tracked via onMouseMove
  }

  // Handle window resize
  window.addEventListener('resize', () => {
    if (rafId) {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
  });

  // Initialize
  init();

  return { activateScene, deactivateScene };
})();

