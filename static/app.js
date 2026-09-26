const $ = id => document.getElementById(id);
const j = async p => (await fetch(p)).json();
const clsColor = c => ({ PROTECTED: '#3fb950', USER_IMPORTANT: '#58a6ff',
  FLEXIBLE: '#d29922', DEFERRABLE: '#8b949e', UNKNOWN: '#f85149' }[c] || '#e6edf3');
const stateDot = s => ({ PROTECT: '🔴', REVIEW: '🟡', OBSERVE: '🔵',
  'OPTIMIZATION CANDIDATE': '🟢' }[s] || '⚪');
let lastSummary = null;

function aiRow(r) {
  const ai = r.ai;
  const arch = r.arch || 'Unknown';
  const cpu = (r.cpu_pct === null || r.cpu_pct === undefined) ? '–' : r.cpu_pct;
  if (!ai) return `<tr><td>${r.name}</td><td>${arch}</td><td>${cpu}</td>` +
    `<td colspan="3" style="color:#8b949e">AI warming up…</td><td></td></tr>`;
  const why = ai.why.join(' • ');
  const fam = ai.ood ? `UNKNOWN (${ai.familiarity})`
    : `${ai.familiarity_level} (${ai.familiarity})`;
  return `<tr><td>${r.pid == null ? '' : r.pid + ' '}${r.name}${r.demo ? ' (demo)' : ''}</td>` +
    `<td>${arch}</td><td>${cpu}</td>` +
    `<td style="color:${clsColor(ai.model_class)}">${ai.model_class} <span style="color:#8b949e">${(ai.raw_confidence * 100).toFixed(0)}%</span></td>` +
    `<td>${fam}</td>` +
    `<td>${stateDot(ai.safety_state)} <b>${ai.safety_state}</b> — ${ai.recommendation}</td>` +
    `<td class="why" title="${why.replace(/"/g, '')}">${ai.why[0] || ''} …</td></tr>`;
}

async function aiengine() {
  const [s, p] = await Promise.all([j('/api/ai_status'), j('/api/platform')]);
  const cur = s.selected_backend === 'HEXAGON NPU';
  $('aiengine').innerHTML =
    `<div style="color:#8b949e">SNAPDRAGON AI ENGINE</div>` +
    `<div>Development Host<br><b>${p.os.system} ${p.os.release} · ${p.arch_normalized} · ${p.cpu_name}</b></div>` +
    `<div style="margin-top:6px">Current Inference<br><b>${s.selected_backend}</b> (${s.provider})</div>` +
    `<div style="margin-top:6px">Snapdragon Target<br><b>Hexagon NPU</b> (Snapdragon X Elite Windows)</div>` +
    `<div style="margin-top:6px">QNN<br><b>${s.qnn}</b> ${cur ? '' : '(target path; unavailable here)'}</div>` +
    `<div style="margin-top:6px">Model<br><b>Process Priority Classifier</b> (${s.model_format})</div>` +
    `<div>Model Size<br><b>${s.model_size_kb || '?'} KB</b> · loaded: <b>${s.model_loaded ? 'YES' : 'NO'}</b></div>` +
    `<div style="margin-top:6px">NPU: <b>${s.npu}</b> · AI Runtime: ONNX Runtime ${s.ort_version || '?'} · Inference: LOCAL</div>` +
    `<div>Current: <b>${s.selected_backend}</b> · Target: ${s.target_backend}</div>` +
    (cur ? '' : `<div style="color:#8b949e">CPU fallback is correct here; ` +
    `the QNN/Hexagon path activates on Snapdragon hardware.</div>`) +
    `<div style="color:#8b949e">Calibrated (T=${s.temperature}) · ` +
    `final = model × familiarity · OOD threshold ${s.ood_threshold} · ` +
    `action threshold ${(s.confidence_threshold * 100) | 0}% · ` +
    `last latency ${s.last_latency_ms == null ? '–' : s.last_latency_ms + ' ms'} · ` +
    `source: ${s.ai_source}</div>` +
    `<div style="color:#8b949e">Uncertainty → protect. The model advises; the safety layer decides.</div>`;
}
function trustStatus(sum) {
  const st = sum.safety_states || {};
  const prot = (st.PROTECT || 0) + (st.REVIEW || 0);
  const total = sum.analyzed || 1;
  if ((st['OPTIMIZATION CANDIDATE'] || 0) > total * 0.3)
    return '● PERMISSIVE — many candidates (unexpected on live data)';
  if (prot / total > 0.8) return '● CONSERVATIVE — uncertainty → protect';
  if ((st.REVIEW || 0) > 0) return '● CAUTIOUS — several under review';
  return '● HIGH — familiar workloads, high confidence';
}
function renderSummary(sum, backend) {
  const c = sum.counts || {};
  const st = sum.safety_states || {};
  $('summary').innerHTML =
    `<div>AI trust status: <b>${trustStatus(sum)}</b></div>` +
    `<div>Processes analyzed: <b>${sum.analyzed}</b> · OOD: ${sum.ood_count || 0}</div>` +
    `<div>Model votes — Protected: ${c.PROTECTED || 0} · Important: ${c.USER_IMPORTANT || 0} · ` +
    `Flexible: ${c.FLEXIBLE || 0} · Deferrable: ${c.DEFERRABLE || 0}</div>` +
    `<div>Safety — PROTECT: ${st.PROTECT || 0} · REVIEW: ${st.REVIEW || 0} · ` +
    `OBSERVE: ${st.OBSERVE || 0} · Candidates: ${st['OPTIMIZATION CANDIDATE'] || 0}</div>` +
    `<div>Average final confidence: ${(sum.avg_confidence * 100).toFixed(1)}% · ` +
    `inference ${sum.latency_ms} ms</div>` +
    `<div>Execution: <b>${backend || ''}</b> · Target: Snapdragon Hexagon NPU</div>` +
    `<div style="color:#8b949e">Model votes are advisory only — the safety layer decides. Nothing was modified.</div>`;
}
async function platform() {
  const p = await j('/api/platform');
  $('platform').innerHTML =
    `<div>Arch: <b>${p.arch_normalized}</b> (${p.machine_raw})</div>` +
    `<div>CPU: ${p.cpu_name}</div>` +
    `<div>ARM: ${p.is_arm} · Snapdragon: ${p.is_snapdragon}</div>` +
    `<div style="color:#8b949e">ONNX route: ${p.phase_routing.onnx_backend} · QNN: ${p.phase_routing.qnn_backend}</div>`;
}
async function stats() {
  const s = await j('/api/stats');
  $('cpuBig').textContent = s.cpu.total_pct + '% CPU';
  $('cpuBar').style.width = Math.min(100, s.cpu.total_pct) + '%';
  $('memLine').textContent = `RAM ${s.memory.used_gb}/${s.memory.total_gb} GB (${s.memory.pct}%)`;
  $('memBar').style.width = Math.min(100, s.memory.pct) + '%';
  const b = s.battery.present ? `${s.battery.percent}%${s.battery.plugged ? ' (plugged)' : ''}` : 'no battery reported';
  $('misc').innerHTML =
    `Cores: ${s.cpu.physical}P/${s.cpu.logical}L · Disk C: ${s.disk.pct}% · ` +
    `Net ↓${s.net.mb_recv}MB ↑${s.net.mb_sent}MB · Batt: ${b} · Up: ${Math.floor(s.uptime_s / 3600)}h`;
  $('clock').textContent = new Date(s.timestamp * 1000).toLocaleTimeString();
}
async function backends() {
  const b = await j('/api/backends');
  $('backends').innerHTML =
    `<div>ONNX: <b>${b.onnx.backend}</b> — ${b.onnx.detail}</div>` +
    `<div>QNN/Hexagon: <b>${b.qnn.state}</b> — ${b.qnn.reason}</div>` +
    `<div>Selected: <b>${b.selected.selected_backend}</b> (${b.selected.provider})</div>` +
    `<div style="color:#8b949e">${b.selected.note}</div>`;
}
async function safety() {
  const s = await j('/api/safety');
  const e = await j('/api/emergency');
  const v = await j('/api/npu_validation');
  const h = (v && v.hub_detail) || {};
  $('npuval').innerHTML =
    `<div>Development Host: <b>Intel x64 — CPU FALLBACK</b></div>` +
    `<div>Local Dell CPU Validation: <b>${v.local_dell_cpu}</b></div>` +
    `<div>Target: <b>Snapdragon X Elite CRD</b> (Windows 11, hexagon v73)</div>` +
    `<div>Compile: <b>${(h.compile && h.compile.job_id) || '—'}</b> ` +
    `· Profile: <b>${(h.profile && h.profile.job_id) || '—'}</b> ` +
    `· Compute: <b>${(h.profile && h.profile.compute_unit) || '—'}</b></div>` +
    `<div>Inference: <b>${(h.inference && h.inference.job_id) || v.inference}</b> ` +
    `· CPU vs NPU: <b>${(h.inference && h.inference.argmax_agreement) || '—'}</b></div>` +
    `<div>Status: <b>${v.snapdragon_model_npu}</b></div>` +
    `<div>Full Application on Snapdragon: <b>${v.full_application_on_snapdragon}</b></div>` +
    `<div>HP Full-System Validation: <b>${v.hp_full_application}</b></div>` +
    `<div style="color:#8b949e">CRD evidence proves NPU execution, never HP hardware. Local Intel NPU stays UNAVAILABLE.</div>`;
  $('safety').innerHTML =
    `<div>Mode: <b>${s.mode}</b></div><div>${s.process_termination}</div>` +
    `<div style="color:#8b949e">AI has no authority to terminate/suspend/reprioritize.</div>` +
    `<div>Emergency stop: <b>${e.emergency_stop ? 'ON (monitor only)' : 'OFF'}</b> ` +
    `<button id="estop2">${e.emergency_stop ? 'RESUME' : 'STOP AI OPTIMIZATION'}</button></div>`;
  $('aistatus').textContent = e.emergency_stop ? '● MONITOR ONLY' : '● AI OPTIMIZATION ACTIVE';
  $('aistatus').style.color = e.emergency_stop ? '#d29922' : '#3fb950';
  $('stopbanner').hidden = !e.emergency_stop;
  $('estop').textContent = e.emergency_stop ? 'RESUME AI OPTIMIZATION' : 'STOP AI OPTIMIZATION';
  const t2 = $('estop2');
  if (t2) t2.onclick = estopToggle;
}
async function estopToggle() {
  const e = await j('/api/emergency');
  await j(`/api/emergency?state=${e.emergency_stop ? 'off' : 'on'}`);
  await safety();
}
async function statusstrip() {
  const [s, p, st] = await Promise.all([
    j('/api/stats'), j('/api/processes?limit=200&sort=cpu'), j('/api/ai_status')]);
  const sum = p.ai_summary || { analyzed: 0, counts: {}, safety_states: {} };
  const c = sum.counts || {}, sst = sum.safety_states || {};
  const fg = (p.rows || []).find(r => r.ai && r.ai.why &&
    r.ai.why.some(w => w.includes('foreground window'))) || {};
  const bg = (p.rows || []).filter(r => !(r.ai && r.ai.why &&
    r.ai.why.some(w => w.includes('foreground window'))))
    .reduce((a, r) => a + (r.cpu_pct || 0), 0);
  const press = s.cpu.total_pct >= 70 ? 'HIGH' : (s.cpu.total_pct >= 30 ? 'MEDIUM' : 'LOW');
  $('strip').innerHTML =
    `Foreground: <b>${fg.name || '—'}</b> · System Stability: <b style="color:#3fb950">● PROTECTED</b> · ` +
    `CPU Pressure: <b>${press} (${s.cpu.total_pct}%)</b> · Background Work: <b>${bg.toFixed(1)}%</b> · ` +
    `Protected: <b>${c.PROTECTED || 0}</b> · AI Candidates: <b>${sst['OPTIMIZATION CANDIDATE'] || 0} DEMO</b> · ` +
    `AI Engine: <b>${st.selected_backend}</b>`;
}
async function procs() {
  const demoSet = $('demo').value;
  $('demoBanner').hidden = !demoSet;
  if (demoSet) {
    const d = await j(`/api/demo?set=${demoSet}`);
    $('pcount').textContent = `DEMO DATA — ${d.description}`;
    $('procs').innerHTML = d.rows.map(aiRow).join('');
    const st = await j('/api/ai_status');
    renderSummary(d.summary, st.selected_backend);
    lastSummary = null;
    return;
  }
  const sort = $('sort').value, limit = $('limit').value;
  const p = await j(`/api/processes?sort=${sort}&limit=${limit}`);
  $('pcount').textContent = `${p.count} processes (cache ${p.cache_age_s || 0}s old)`;
  $('procs').innerHTML = p.rows.map(aiRow).join('');
  if (p.ai_summary) {
    lastSummary = p.ai_summary;
    const st = await j('/api/ai_status');
    renderSummary(p.ai_summary, st.selected_backend);
  }
}
async function plan() {
  const p = await j('/api/plan');
  $('plan').innerHTML = p.suggestions.length
    ? `<div>Executed: none (dry-run). Suggestions from live data:</div><ul>` +
      p.suggestions.map(s => `<li>${s.name} (pid ${s.pid}): ${s.reason} → ${s.proposed}</li>`).join('') + `</ul>`
    : `<div>Executed: none (dry-run). No high-CPU processes right now. (${p.note})</div>`;
}
async function decisions() {
  const d = await j('/api/decisions?limit=12');
  if (!d.records.length) { $('decisions').textContent = 'No decisions logged yet.'; return; }
  $('decisions').innerHTML = `<table><thead><tr><th>Time</th><th>Process</th>` +
    `<th>Model vote</th><th>Final confidence</th><th>Safety decision</th><th>Reason</th></tr></thead><tbody>` +
    d.records.slice().reverse().map(r =>
      `<tr><td>${r.timestamp.slice(11)}</td><td>${r.process}</td>` +
      `<td style="color:${clsColor(r.model_class)}">${r.model_class} <span style="color:#8b949e">${(r.raw_confidence * 100).toFixed(0)}%</span></td>` +
      `<td>${(r.final_confidence * 100).toFixed(0)}% (fam ${r.familiarity_level || r.familiarity})</td>` +
      `<td>${stateDot(r.safety_state)} <b>${r.safety_state}</b> — ${r.recommendation}</td>` +
      `<td class="why">${r.reason || ''}</td></tr>`).join('') + `</tbody></table>` +
    `<div style="color:#8b949e">Model prediction vs final safety decision — from ${d.source}. Nothing was modified.</div>`;
}
const levelW = l => ({ HIGH: 100, MEDIUM: 55, LOW: 20, UNKNOWN: 5 }[l] ?? 10);
const bar = (tag, level) =>
  `<div class="barwrap"><span class="tag">${tag} (${level})</span>` +
  `<div class="bar" style="flex:1"><div style="width:${levelW(level)}%"></div></div>` +
  `<span class="badge sim">PROJECTED</span></div>`;
async function optcenter() {
  const [p, st, b] = await Promise.all([
    j('/api/processes?limit=200&sort=cpu'), j('/api/ai_status'), j('/api/backends')]);
  const sum = p.ai_summary || { analyzed: 0, safety_states: {} };
  const sst = sum.safety_states || {};
  const chain = [['ONNX model', true], ['ONNX Runtime (CPU)', true],
    ['Windows ML path', false], ['Qualcomm QNN', b.qnn.available],
    ['Hexagon NPU', st.npu === 'AVAILABLE']];
  $('optcenter').innerHTML =
    `<div class="simgrid">` +
    `<div class="simcard"><h3>Real processes</h3><div class="big">${sum.analyzed}</div>` +
    `<div>Candidates: <b>${sst['OPTIMIZATION CANDIDATE'] || 0}</b> (live is conservative by design)</div></div>` +
    `<div class="simcard"><h3>System stability</h3><div class="ring">● PROTECTED</div>` +
    `<div>Windows Critical — PROTECT<br>Foreground App — PROTECT<br>` +
    `Unknown Workload — PROTECT<br>Low Confidence — PROTECT</div></div>` +
    `<div class="simcard"><h3>Inference route</h3>` +
    chain.map(([n, ok]) => `<div>${ok ? '●' : '○'} ${n}</div>`).join('') +
    `<div style="margin-top:6px">Backend: <b>${st.selected_backend}</b> · Target: Snapdragon Hexagon NPU</div></div>` +
    `</div>` +
    `<div style="color:#8b949e;margin-top:8px">Observe → Understand → Predict → Protect → Simulate. ` +
    `Never Kill / Suspend / Disable. No process is modified — simulations are DEMO projections.</div>`;
}
async function simcards() {
  const set = $('scenario').value;
  const d = await j(`/api/demo?set=${set}`);
  const wrap = $('simcards');
  wrap.innerHTML = `<div style="color:#ffd77a;margin-top:8px">DEMO SIMULATION — ${d.description}. ` +
    `Synthetic processes, real model, projected effects only.</div>`;
  for (let i = 0; i < d.rows.length; i++) {
    const pv = await j(`/api/optimization/preview?set=${set}&index=${i}`);
    const r = d.rows[i];
    const card = document.createElement('div');
    card.className = 'simcard';
    card.innerHTML =
      `<h3>AI Optimization Preview — ${r.name}</h3>` +
      `<div>Arch: ${r.arch} · CPU: ${r.cpu_pct}% (demo)</div>` +
      `<div>AI: <b style="color:${clsColor(pv.model_class)}">${pv.model_class}</b> ` +
      `(${(pv.raw_confidence * 100).toFixed(0)}%) · Fam: ${pv.familiarity} · ` +
      `Safety: <b>${pv.safety_state}</b></div>` +
      `<div>Proposed: <b>${pv.simulated_action.replaceAll('_', ' ')}</b> ` +
      `<span class="badge sim">SIMULATED</span></div>` +
      `<div class="why">WHY? ${(pv.why || []).slice(0, 3).join(' + ')}</div>` +
      `<div style="margin-top:8px"><button data-set="${set}" data-i="${i}">SIMULATE</button></div>` +
      `<div class="simout"></div>`;
    card.querySelector('button').onclick = ev => simulate(ev.target.dataset.set, +ev.target.dataset.i, card.querySelector('.simout'));
    wrap.appendChild(card);
  }
}
async function simulate(set, i, out) {
  const s = await j(`/api/optimization/simulate?set=${set}&index=${i}`);
  if (s.disabled) {
    out.innerHTML = `<div style="color:#d29922"><b>STOP AI OPTIMIZATION is ON</b> — ${s.note}</div>`;
    return;
  }  out.innerHTML = s.stages.map((g, k) => `<div class="stage" id="st${k}">${g.replaceAll('_', ' ')}</div>`).join('');
  for (let k = 0; k < s.stages.length; k++) {
    await new Promise(r => setTimeout(r, 350));
    out.querySelector(`#st${k}`).className = 'stage on';
    if (k > 0) out.querySelector(`#st${k - 1}`).className = 'stage done';
  }
  out.querySelector(`#st${s.stages.length - 1}`).className = 'stage done';
  const lv = lvl => (lvl || '').split('_').pop();
  out.innerHTML += bar('Background pressure before', lv(s.before)) +
    bar('Background pressure after', lv(s.after)) +
    `<div>${s.explanation} <span class="badge sim">ILLUSTRATIVE</span></div>`;
}
async function startdemo() {
  $('scenario').value = 'presentation';
  await optcenter();
  const d = await j('/api/demo?set=presentation');
  const cands = [];
  for (let i = 0; i < d.rows.length; i++) {
    const pv = await j(`/api/optimization/preview?set=presentation&index=${i}`);
    if (pv.safety_state === 'OPTIMIZATION CANDIDATE') cands.push([i, d.rows[i].name]);
  }
  const cards = [...document.querySelectorAll('#simcards .simcard')];
  $('simstage').innerHTML =
    `<div class="simcard" style="margin-top:12px"><h3>Competition demo — presenting with PowerPoint (SIMULATED PROCESSES)</h3>` +
    `<div>PowerPoint → PROTECTED · CloudSync / Indexer → candidates: ${cands.map(c => c[1]).join(', ') || 'none'} (${cands.length})</div>` +
    `<div style="color:#8b949e">Foreground stays PROTECTED. Simulating first candidate…</div></div>`;
  if (cands.length && cards[cands[0][0]]) {
    await simulate('presentation', cands[0][0], cards[cands[0][0]].querySelector('.simout'));
  }
}
async function all() { try { await Promise.all([aiengine(), platform(), stats(), backends(), safety(), procs(), plan(), decisions(), optcenter(), simcards(), statusstrip()]); } catch (e) { /* transient at load: intervals retry */ } }
$('refresh').onclick = all; $('sort').onchange = procs;
$('limit').onchange = procs; $('demo').onchange = procs;
$('scenario').onchange = simcards; $('startdemo').onclick = startdemo;
$('estop').onclick = estopToggle;
all(); setInterval(async () => { try { await stats(); await procs(); await statusstrip(); } catch (e) { /* transient: next poll retries */ } }, 5000);
setInterval(async () => { try { await aiengine(); await backends(); await safety(); await plan(); await decisions(); await optcenter(); } catch (e) { /* transient: next poll retries */ } }, 15000);
