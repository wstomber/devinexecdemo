"use strict";
let E = null, route = "", cmpKey = null, cmpQuery = "", cmpFilter = "all", cmpPage = 0, poll = null, D = null, dpoll = null;
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const money = c => { if (c === null || c === undefined || Number.isNaN(c)) return "—"; const neg = c < 0; c = Math.abs(c);
  const d = Math.floor(c / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","), r = String(c % 100).padStart(2, "0"); return (neg ? "-" : "") + "$" + d + "." + r; };
const cents = c => c === null || c === undefined ? "—" : c.toLocaleString("en-US") + "¢";
const badge = (s, txt) => `<span class="badge ${esc(s)}">${esc(txt || s)}</span>`;
const SAVED = `<span class="badge SAVED">SAVED REHEARSAL</span>`, LIVE = `<span class="badge LIVE">CURRENT LIVE EXECUTION</span>`;
const LIVE_DEVIN = `<span class="badge LIVE">LIVE DEVIN SESSION</span>`;
const raw = (p, label) => p ? `<a href="/raw/${esc(p)}" target="_blank">${esc(label || p)}</a>` : `<span class="muted">not available</span>`;
const gh = p => `https://github.com/wstomber/devinexecdemo/blob/${E.git.head || "main"}/${p}`;
const commit = sha => sha ? `<a href="https://github.com/wstomber/devinexecdemo/commit/${esc(sha)}" target="_blank"><code>${esc(sha.slice(0, 7))}</code></a>` : "UNKNOWN";
const cmd = c => `<div class="cmd"><code>${esc(c)}</code><button class="btn sm" data-copy="${esc(c)}">Copy</button></div>`;
const fileCache = {};
async function file(p) { if (!(p in fileCache)) { const r = await fetch("/raw/" + p); fileCache[p] = r.ok ? await r.text() : null; } return fileCache[p]; }

function md(src) {
  if (src == null) return `<p class="err">Document missing.</p>`;
  const inline = s => esc(s).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) => `<a href="${/^https?:/.test(u) ? u : "#"}" target="_blank">${t}</a>`);
  const out = [], lines = src.split("\n"); let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("```")) { const b = []; i++; while (i < lines.length && !lines[i].startsWith("```")) b.push(lines[i++]); i++; out.push(`<pre>${esc(b.join("\n"))}</pre>`); continue; }
    if (/^#{1,4} /.test(l)) { const n = l.match(/^#+/)[0].length; out.push(`<h${n + 1}>${inline(l.slice(n + 1))}</h${n + 1}>`); i++; continue; }
    if (l.startsWith("|")) { const rows = []; while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
      const cells = r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const body = rows.filter((r, k) => k !== 1 || !/^\|[\s:|-]+\|$/.test(r));
      out.push(`<table><thead><tr>${cells(body[0]).map(c => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body.slice(1).map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`); continue; }
    if (/^\s*([-*]|\d+\.) /.test(l)) { const items = []; while (i < lines.length && /^\s*([-*]|\d+\.) /.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.) /, ""));
      out.push(`<ul>${items.map(t => `<li>${inline(t)}</li>`).join("")}</ul>`); continue; }
    if (!l.trim()) { i++; continue; }
    const p = []; while (i < lines.length && lines[i].trim() && !/^(#|\||```|\s*([-*]|\d+\.) )/.test(lines[i])) p.push(lines[i++]);
    out.push(`<p>${inline(p.join(" "))}</p>`);
  }
  return `<div class="md">${out.join("")}</div>`;
}
async function mdBlock(path, title) { return `<details data-md="${esc(path)}"><summary>${esc(title)}</summary><div class="muted small">Loading…</div></details>`; }

function codeView(text, from, to, path) {
  if (text == null) return `<p class="err">Source file ${esc(path)} is missing.</p>`;
  const lines = text.split("\n"); if (lines[lines.length - 1] === "") lines.pop();
  const a = Math.max(1, from - 3), b = Math.min(lines.length, to + 3);
  return `<div class="small muted">${esc(path)} · lines ${from}–${to} highlighted · ${raw(path, "open full file")} · <a href="${gh(path)}" target="_blank">GitHub</a></div>
  <div class="code">${lines.slice(a - 1, b).map((t, k) => { const n = a + k; return `<div class="ln${n >= from && n <= to ? " mark" : ""}"><span>${n}</span><span>${esc(t)}</span></div>`; }).join("")}</div>`;
}
function findLines(text, startRe, endRe) {
  if (text == null) return [1, 1]; const L = text.split("\n"); const s = L.findIndex(l => startRe.test(l)); if (s < 0) return [1, 1];
  let e = s; for (let k = s + 1; k < L.length; k++) { if (endRe.test(L[k])) { e = k; break; } e = k; } return [s + 1, e + 1];
}
async function codeSnippet(path, startRe, endRe) { const t = await file(path); const [a, b] = findLines(t, startRe, endRe); return codeView(t, a, b, path); }

function testStatus(saved, live, label) {
  return `<div class="card"><h3>${esc(label)}</h3>
   <div>${SAVED} ${badge(saved?.status || "UNKNOWN")} ${saved?.tests != null ? saved.tests + " tests" : ""} · ${raw(saved?.log, "log")}</div>
   <div style="margin-top:6px">${LIVE} ${live ? badge(live.status) + (live.tests != null ? " " + live.tests + " tests" : "") + " · " + raw(live.log, "log") : badge("NOT_RUN") + ' <span class="muted small">press “Run COBOL vs Python now”</span>'}</div></div>`;
}
const liveStep = key => E.live?.steps?.find(s => s.key === key);
function stepLine(key) { const s = liveStep(key); return s ? `${LIVE} ${badge(s.status)} exit ${s.exit_code ?? "—"} · ${raw(s.log, "output")}` : `${LIVE} ${badge("NOT_RUN")}`; }

const ex3Case = () => E.expectations?.cases?.find(c => c.claim_id === "CMS-EX3");
const findRow = (cmp, id) => cmp?.rows?.find(r => r[1] === id);

const VIEWS = [["overview", "The problem"], ["baseline", "1 · COBOL baseline"], ["explain", "2 · Devin explains COBOL"], ["tests", "3 · Tests came first"],
  ["python", "4 · Python + unit tests"], ["compare", "5 · Old vs new"], ["ex3", "★ CMS-EX3 $500"], ["security", "6 · Security & data"], ["review", "7 · Review & repeat"], ["pilot", "8 · Pilot plan"]];

const R = {};
R.overview = async () => {
  const s = E.saved, c = s.comparisons, total = Object.values(c).reduce((n, x) => n + (x.records?.python || 0), 0);
  const allPassed = Object.values(c).every(x => x.status === "PASSED");
  return `<h1>Can Devin safely modernize code nobody understands anymore?</h1>
  <p class="lede">A synthetic COBOL module that calculates Medicare Secondary Payer payments — when Medicare pays after another insurer. Devin had to understand it, recover the policy behind it, test it, migrate it to Python, and prove the result.</p>
  <div class="flow">
    <div class="card"><h3>1. Run the original</h3>${badge(s.baseline.status)}<div class="small">COBOL baseline kept as the yardstick</div></div><div class="arrow">→</div>
    <div class="card"><h3>2. Explain it</h3><div class="small">Plain-English guide + DeepWiki for new engineers</div></div><div class="arrow">→</div>
    <div class="card"><h3>3. Test first</h3>${badge(E.git.tests_before_python.status)}<div class="small">Hand-derived answers, run on COBOL before any Python existed</div></div><div class="arrow">→</div>
    <div class="card"><h3>4. Migrate &amp; compare</h3>${badge(allPassed ? "PASSED" : "FAILED")}<div class="small">${total.toLocaleString()} claims compared, ${Object.values(c).reduce((n, x) => n + (x.mismatches || 0), 0)} mismatches</div></div>
  </div>
  <h2>Devin, working live</h2><div id="devinslot">${devinCard()}</div>
  <h2>The case that matters</h2>
  <div class="card"><b>CMS-EX3:</b> the provider agreed to accept $13,000 in total. The primary insurer paid $12,500. Medicare owes <b>$500</b> — not $1,500. <a href="#ex3">See the full walkthrough →</a></div>
  <h2>Scope — be honest about it</h2>
  <ul><li>This is a <b>synthetic, educational</b> example based on public CMS manual rules. It is not CMS production code and not a complete Medicare claims system.</li>
  <li>“Match” means old and new behave identically on the batches tested here — not that the rules are complete Medicare policy.</li>
  <li>No speed or cost savings are claimed.</li></ul>`;
};
R.baseline = async () => {
  const b = E.saved.baseline, ct = b.curated_totals, st = b.synthetic_totals, m = b.manifest || {};
  const stat = (n, l) => `<div class="card stat"><div class="n">${n}</div><div class="l">${l}</div></div>`;
  return `<h1>1 · The original COBOL program, run first</h1>
  <p class="lede">The program reads a batch of claims (one fixed-width line each) and writes one result per claim — PAID, ZERO or INVALID with a payment and a reason — plus a totals line.</p>
  <h2>Curated 30-claim batch ${SAVED} ${badge(b.status)}</h2>
  <div class="grid g4">${ct ? stat(ct.records, "claims") + stat(ct.paid, "paid") + stat(ct.zero, "zero (valid, nothing owed)") + stat(ct.invalid, "rejected as malformed") + stat(money(ct.payment_cents), "total paid by COBOL") : `<div class="err">Totals file missing</div>`}</div>
  <h2>1,000-claim synthetic batch ${SAVED}</h2>
  <div class="grid g4">${st ? stat(st.records.toLocaleString(), "claims") + stat(st.paid, "paid") + stat(st.zero, "zero") + stat(st.invalid, "rejected") + stat(money(st.payment_cents), "total paid by COBOL") : `<div class="err">Totals file missing</div>`}</div>
  <h2>Live re-run</h2><div class="card">${stepLine("build")}<br>${stepLine("baseline")}<div class="small muted" style="margin-top:6px">Live runs write to a new folder each time and never change the saved rehearsal.</div></div>
  <details><summary>Technical detail: identity, environment, raw files</summary>
   <p>Starter commit (COBOL only): ${commit(E.git.starter)} · captured ${esc(m.captured_at_utc || "UNKNOWN")} · verifier result ${badge(b.status)} (expected-results check, migration comparison ${esc(b.report?.migration_comparison || "UNKNOWN")})</p>
   <pre>${esc(E.saved.environment || "environment.txt missing")}</pre>
   ${cmd("make doctor && make build baseline generate test capture-baseline")}
   <p>${Object.entries(b.raw).map(([n, p]) => raw(p, n)).join(" · ")} · ${raw(b.log, "baseline log")}</p></details>`;
};
R.explain = async () => {
  const pay = await codeSnippet("cobol/payment.cob", /calculate-prospective-payment\./, /function min/);
  return `<h1>2 · Devin explains the legacy code</h1>
  <p class="lede">Four COBOL files. Devin documented what each does, in plain language, for engineers who have never seen COBOL.</p>
  <div class="grid g4">
   <div class="card"><h3>batch.cob — the driver</h3>Reads the file line by line, checks for duplicate claim IDs, writes each result and the totals. Stops the whole batch on fatal problems.</div>
   <div class="card"><h3>validate.cob — the gatekeeper</h3>Checks each line in a fixed order (length, ID, amounts, contract, flag) and names the first problem it finds.</div>
   <div class="card"><h3>claim.cpy — the record layout</h3>A “copybook”: one shared definition of the 73-character claim line, used by all programs.</div>
   <div class="card"><h3>payment.cob — the money</h3>Works out what Medicare owes as the secondary payer, in exact cents.</div></div>
  <h2>The key rule: the provider's contract replaces the charges</h2>
  <div class="grid g2"><div>${pay}</div><div class="card">
   <p><b>In plain English:</b> start with the provider's charges. <b>If the claim has a contractual amount</b> (<code>claim-has-contract = 1</code>), use that instead (<code>move claim-contract to charge-basis</code>). The payment can never be more than the <b>lower</b> of what Medicare would normally pay and that basis (<code>function min</code>).</p>
   <p>For CMS-EX3 that basis is $13,000, not $15,000 — which is why the answer is $500. <a href="#ex3">Walk through it →</a></p>
   <p class="small muted">COBOL terms: a <i>paragraph</i> (<code>calculate-prospective-payment.</code>) is a named block, like a function. <code>comp-3</code> is packed decimal — exact whole numbers, so no rounding drift.</p></div></div>
  <h2>For new engineers</h2>
  <p><a href="${esc(E.status?.deepwiki || "https://app.devin.ai/wiki/wstomber/devinexecdemo")}" target="_blank">Open the DeepWiki</a> — Devin's generated guide: COBOL for new engineers, each program explained, COBOL→Python mapping.</p>
  ${await mdBlock("docs/migration/03-cobol-primer.md", "COBOL primer (written against this code)")}
  ${await mdBlock("docs/migration/04-legacy-walkthrough.md", "Line-by-line walkthrough")}
  ${await mdBlock("docs/migration/01-cobol-explanation.md", "Stage 1 explanation")}`;
};
R.tests = async () => {
  const x = E.expectations, p = E.git.tests_before_python, s2 = E.git.stages.stage2, s3 = E.git.stages.stage3;
  const cases = x?.cases || [];
  return `<h1>3 · The tests came before the migration</h1>
  <p class="lede">Devin worked out the right answers by hand from the CMS manual — not by copying what the COBOL printed — and checked the COBOL against them before any Python existed.</p>
  <div class="grid g2"><div class="card"><h3>Tests came first ${badge(p.status, p.status === "PASSED" ? "VERIFIED FROM GIT" : p.status)}</h3>
    <p>Tests committed in ${commit(s2?.sha)} (${esc(s2?.date || "")})<br>Python first appears in ${commit(s3?.sha)} (${esc(s3?.date || "")})</p>
    <p class="small">Checked now from git history: <code>python/msp.py</code> ${p.python_absent_at_stage2 ? "did <b>not</b> exist" : "<b>existed</b>"} at the test commit; test commit ${p.stage2_before_stage3 ? "precedes" : "does <b>not</b> precede"} the Python commit.</p></div>
   ${testStatus(E.saved.policy_tests_cobol, E.live?.policy_tests_cobol, "Independent policy tests against COBOL")}</div>
  <h2>The hand-derived ledger: ${cases.length} cases</h2>
  <p class="small muted">${esc(x?.derivation || "")}</p>
  <div class="tablewrap"><table><thead><tr><th>#</th><th>Claim</th><th>Category</th><th>Expected</th><th class="num">Expected payment</th><th>Reason</th><th>Source</th></tr></thead><tbody>
  ${cases.map((c, k) => `<tr class="click${c.claim_id === "CMS-EX3" ? " hl" : ""}" data-case="${k}"><td>${c.record_no}</td><td><code>${esc(c.claim_id)}</code></td><td>${esc(c.category)}</td><td>${badge(c.expected.status === "PAID" ? "PASSED" : c.expected.status === "ZERO" ? "NOT_RUN" : "FAILED", c.expected.status)}</td><td class="num">${money(c.expected.payment_cents)}</td><td><code>${esc(c.expected.reason)}</code></td><td class="small">${esc(c.source || "")}</td></tr>`).join("")}
  </tbody></table></div>
  <p class="small">Ledger totals (hand-derived): ${x?.totals ? `${x.totals.records} records · ${x.totals.paid} paid · ${x.totals.zero} zero · ${x.totals.invalid} invalid · ${money(x.totals.payment_cents)}` : "missing"} · ${raw("tests_policy/expectations.json", "expectations.json")} · ${raw("tests_policy/test_policy.py", "test_policy.py")}</p>
  <h2>Separate: starter infrastructure tests</h2><div class="card small">These came with the starter repo and check the COBOL harness itself; they are not Devin's independent policy tests. ${stepLine("starter-tests")}</div>
  ${cmd("python3 -m unittest discover -s tests_policy -v")}`;
};
R.python = async () => {
  const py = await codeSnippet("python/msp.py", /^def charge_basis/, /SECONDARY_PAYABLE/);
  const pay = await codeSnippet("cobol/payment.cob", /calculate-prospective-payment\./, /SECONDARY_PAYABLE/);
  const u = E.saved.python_unit_tests;
  return `<h1>4 · The new Python, and its own tests</h1>
  <p class="lede">The same rule, now in readable Python. It passed the independent tests on its first run.</p>
  <p>Left: the original COBOL that decides what Medicare pays. Right: Devin's Python doing the same checks in the same order. The highlighted lines are the payment rule in each language.</p>
  <div class="grid g2"><div><h3>COBOL (before)</h3>${pay}</div><div><h3>Python (after)</h3>${py}</div></div>
  <div class="grid g2" style="margin-top:14px">${testStatus(E.saved.policy_tests_python, E.live?.policy_tests_python, "Same independent tests against Python")}${testStatus(u, E.live?.python_unit_tests, "Python unit tests")}</div>
  <p class="small muted">“Same independent tests” = the hand-worked answers from screen 3, now run against the Python. “Unit tests” = smaller checks of each piece of the Python on its own.</p>
  <h2>What had to be preserved</h2><div class="grid g4">
   <div class="card"><h3>Exact cents</h3>Whole-number cents everywhere — never floating point — like COBOL's packed decimal.</div>
   <div class="card"><h3>Optional contract</h3>“----------” means no contract; a number replaces the charges.</div>
   <div class="card"><h3>Same validation order</h3>The first problem found decides the reason code, so the order matters.</div>
   <div class="card"><h3>Valid zero ≠ malformed</h3>A correct claim that owes $0 is ZERO; a broken line is INVALID.</div>
   <div class="card"><h3>Batch rules</h3>Same line framing, duplicate-ID stop, counts, totals, and fatal exit code 2.</div></div>
  <details><summary>Unit tests run (${u.tests ?? "?"})</summary><ul>${(u.cases || []).map(c => `<li>${badge(c.result === "ok" ? "PASSED" : "FAILED", c.result)} <code>${esc(c.name)}</code></li>`).join("")}</ul></details>
  <details data-md="${esc(E.saved.corrections)}"><summary>Corrections Devin made along the way</summary><div class="muted small">Loading…</div></details>
  ${await mdBlock("docs/migration/05-cobol-to-python.md", "COBOL → Python translation guide")}
  <p class="small">Commit ${commit(E.git.stages.stage3?.sha)} · <a href="https://github.com/wstomber/devinexecdemo/commit/${esc(E.git.stages.stage3?.sha || "")}" target="_blank">view the diff</a></p>
  ${cmd("MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v")}${cmd("python3 -m unittest discover -s tests_python -v")}`;
};
const curatedKey = () => E.live?.comparisons?.curated?.rows?.length ? "live:curated" : "saved:curated";
function cmpSources() {
  const out = []; for (const [k, v] of Object.entries(E.saved.comparisons)) out.push(["saved:" + k, v]);
  for (const [k, v] of Object.entries(E.live?.comparisons || {})) out.push(["live:" + k, v]); return out;
}
R.compare = async () => {
  const src = cmpSources(); if (!cmpKey || !src.find(s => s[0] === cmpKey)) cmpKey = (src.find(s => s[0] === "live:synthetic") || src.find(s => s[0] === "saved:synthetic") || src[0])[0];
  const c = src.find(s => s[0] === cmpKey)[1];
  const q = cmpQuery.trim().toUpperCase();
  let rows = c.rows || [];
  if (cmpFilter === "mismatch") rows = rows.filter(r => r[8] !== "MATCH");
  if (cmpFilter === "paid") rows = rows.filter(r => r[2] === "PAID");
  if (cmpFilter === "invalid") rows = rows.filter(r => r[2] === "INVALID");
  if (q) rows = rows.filter(r => r.join(" ").toUpperCase().includes(q));
  const per = 200, pages = Math.max(1, Math.ceil(rows.length / per)); cmpPage = Math.min(cmpPage, pages - 1);
  const shown = rows.slice(cmpPage * per, cmpPage * per + per);
  const stat = (n, l, s) => `<div class="card stat"><div class="n">${n}</div><div class="l">${l}</div>${s || ""}</div>`;
  const t = c.totals || {};
  return `<h1>5 · Old vs new, claim by claim</h1>
  <p class="lede">The original COBOL and the new Python were run on the same input. This table is rebuilt from both programs' raw output files.</p>
  <div class="toolbar">${src.map(([k, v]) => `<button class="btn${k === cmpKey ? " on" : ""}" data-cmp="${k}">${k.startsWith("live") ? "LIVE" : "SAVED"} · ${esc(k.split(":")[1])} (${v.records?.python ?? "?"})</button>`).join("")}</div>
  <div>${c.kind === "live" ? LIVE : SAVED} ${badge(c.status, "OVERALL " + c.status)} <span class="muted small">${esc(c.title)}</span></div>
  ${c.problem ? `<div class="err">${esc(c.problem)}</div>` : ""}
  <div class="grid g4" style="margin-top:10px">
   ${stat((c.rows || []).length.toLocaleString(), "claims compared", `<div class="small">COBOL ${c.records?.cobol ?? "?"} · Python ${c.records?.python ?? "?"}</div>`)}
   ${stat(c.mismatches ?? "?", "mismatches", badge(c.mismatches === 0 ? "MATCH" : "MISMATCH", c.mismatches === 0 ? "NONE" : "INSPECT"))}
   ${stat(money(t.cobol?.payment_cents), "COBOL total paid")}
   ${stat(money(t.python?.payment_cents), "Python total paid", badge(c.totals_match ? "MATCH" : "MISMATCH", c.totals_match ? "TOTALS MATCH" : "TOTALS DIFFER"))}
   ${stat(badge(c.verifier?.status || "UNKNOWN"), "strict verifier (tools/verify.py)", `<div class="small">${c.verifier?.report ? raw(c.verifier.report, "report") : esc(c.verifier?.detail === "not applicable" ? "not run for this batch — table only" : c.verifier?.detail || "")}</div>`)}
   ${stat(c.byte_identical ? "Yes" : "No", "output files byte-identical")}</div>
  ${c.duplicates?.length ? `<div class="err">Duplicate claim IDs: ${esc(c.duplicates.join(", "))}</div>` : ""}
  <div class="toolbar"><input type="search" id="cmpq" placeholder="Search claim ID, status, reason…" value="${esc(cmpQuery)}">
   ${[["all", "All"], ["mismatch", "Mismatches only"], ["paid", "Paid"], ["invalid", "Rejected"]].map(([k, l]) => `<button class="btn${cmpFilter === k ? " on" : ""}" data-f="${k}">${l}</button>`).join("")}
   <button class="btn" data-jump="CMS-EX3">Find CMS-EX3</button><span class="muted small">${rows.length.toLocaleString()} rows${pages > 1 ? ` · page ${cmpPage + 1}/${pages} <button class="btn sm" data-pg="-1">‹</button><button class="btn sm" data-pg="1">›</button>` : ""}</span></div>
  <div class="tablewrap"><table><thead><tr><th>#</th><th>Claim ID</th><th>COBOL</th><th>Python</th><th class="num">COBOL pays</th><th class="num">Python pays</th><th>COBOL reason</th><th>Python reason</th><th>Result</th></tr></thead><tbody>
  ${shown.length ? shown.map(r => `<tr class="click${r[1] === "CMS-EX3" ? " hl" : ""}" data-row="${r[0]}"><td>${r[0]}</td><td><code>${esc(r[1])}</code></td><td>${esc(r[2] ?? "—")}</td><td>${esc(r[3] ?? "—")}</td><td class="num">${money(r[4])}</td><td class="num">${money(r[5])}</td><td><code>${esc(r[6] ?? "—")}</code></td><td><code>${esc(r[7] ?? "—")}</code></td><td>${badge(r[8])}</td></tr>`).join("") : `<tr><td colspan="9" class="muted">${cmpFilter === "mismatch" ? "No mismatches in this batch." : "No rows match."}</td></tr>`}
  </tbody></table></div>
  <details><summary>Technical detail: command, identity, raw files</summary>
   <p>Input <code>${esc(c.input || "UNKNOWN")}</code> · sha256 <code>${esc(c.input_sha256 || "UNKNOWN")}</code></p>
   <p>${c.kind === "live" ? `Live run ${esc(E.live.id)} · started ${esc(E.live.started_at)} · commit ${commit(E.live.commit)}${E.live.dirty ? " (uncommitted changes present)" : ""}` : `Saved in ${commit(E.git.stages.stage4?.sha)} (${esc(E.git.stages.stage4?.date || "")})`}</p>
   <p>${Object.entries(c.raw || {}).map(([n, p]) => raw(p, n)).join(" · ")}${E.saved.fatal_parity ? " · " + raw(E.saved.fatal_parity, "fatal-path parity (duplicate ID, 4,097-byte line, 10,001 records)") : ""}</p>
   ${cmd("make compare CANDIDATE='python3 python/msp.py'")}${cmd("python3 tools/demo_compare.py --input build/synthetic.dat --out build/cmp/synthetic")}
   <p class="small muted">A green table is not the proof on its own — the strict verifier (tools/verify.py) checks every field and the totals independently.</p></details>`;
};
R.ex3 = async () => {
  const c = ex3Case(); if (!c) return `<div class="err">CMS-EX3 is missing from tests_policy/expectations.json.</div>`;
  const i = c.input, L = c.limits_cents || [], low = Math.min(...L);
  const names = ["Gross Medicare payable − primary payment", "Gross Medicare payable − deductible & coinsurance", "Contract amount − primary payment", "Contract amount − deductible & coinsurance"];
  const exprs = [[i.gross, i.primary], [i.gross, i.deductible + i.coinsurance], [i.contract, i.primary], [i.contract, i.deductible + i.coinsurance]];
  const sc = E.saved.comparisons.curated, rowS = findRow(sc, "CMS-EX3"), rowL = findRow(E.live?.comparisons?.curated, "CMS-EX3");
  const noOtaf = E.expectations.cases.find(x => x.claim_id === "EX3-NO-OTAF");
  const pay = await codeSnippet("cobol/payment.cob", /move claim-charges to charge-basis/, /function min/);
  return `<h1>★ CMS-EX3 — the contractual cap</h1>
  <p class="lede">From the CMS manual (${esc(c.source)}). The hospital agreed to accept <b>$13,000 in total</b>. The primary insurer paid $12,500. What does Medicare owe?</p>
  <div class="grid g2"><div class="card"><h3>The claim</h3><table>
   <tr><td>Charges</td><td class="num">${money(i.charges)}</td></tr><tr><td>Gross Medicare payable</td><td class="num">${money(i.gross)}</td></tr>
   <tr><td>Primary insurer paid</td><td class="num">${money(i.primary)}</td></tr><tr><td><b>Provider's contractual amount (OTAF)</b></td><td class="num"><b>${money(i.contract)}</b></td></tr>
   <tr><td>Deductible <span class="badge HIST">HISTORICAL EXAMPLE INPUT</span></td><td class="num">${money(i.deductible)}</td></tr><tr><td>Coinsurance</td><td class="num">${money(i.coinsurance)}</td></tr>
   <tr><td>Primary payment accepted in full?</td><td class="num">${i.full === "N" ? "No" : "Yes"}</td></tr></table>
   <p class="small muted">${esc(c.assumptions)}</p></div>
   <div class="card"><h3>Medicare pays the lowest of four limits</h3>
   ${L.map((v, k) => `<div class="limit${v === low ? " low" : ""}"><span>${names[k]}<br><span class="small muted">${money(exprs[k][0])} − ${money(exprs[k][1])}</span></span><span>${money(v)}</span></div>`).join("")}
   <p style="margin-top:12px">Answer: <span class="big">${money(c.expected.payment_cents)}</span><br>$13,000 − $12,500 = $500</p></div></div>
  <h2>Both programs agree</h2><div class="grid g4">
   <div class="card stat"><div class="n">${money(c.expected.payment_cents)}</div><div class="l">Expected (hand-derived)</div></div>
   <div class="card stat"><div class="n">${money(rowS?.[4])}</div><div class="l">COBOL ${SAVED}</div></div>
   <div class="card stat"><div class="n">${money(rowS?.[5])}</div><div class="l">Python ${SAVED} ${rowS ? badge(rowS[8]) : badge("UNKNOWN")}</div></div>
   <div class="card stat"><div class="n">${rowL ? money(rowL[4]) + " / " + money(rowL[5]) : "—"}</div><div class="l">COBOL / Python ${LIVE} ${rowL ? badge(rowL[8]) : badge("NOT_RUN")}</div></div></div>
  <h2>Why the contract rule matters</h2><div class="warn">Without the contractual cap, the lowest limit would be ${money(i.gross - i.primary)} — so the payment would be <span class="strike">${money(noOtaf?.expected?.payment_cents ?? 150000)}</span>, <b>${money((noOtaf?.expected?.payment_cents ?? 150000) - c.expected.payment_cents)} too much</b>. This is an explanatory counterfactual (test case <code>EX3-NO-OTAF</code>), not a defect found in the COBOL.</div>
  <h2>Where this rule lives</h2><div class="grid g2"><div>${pay}</div><div class="card"><ul>
   <li>Policy: ${raw("docs/cms-example-3.md", "docs/cms-example-3.md")} · ${raw("docs/rules.md", "docs/rules.md")}</li>
   <li>Independent expectation: ledger row 1 in ${raw("tests_policy/expectations.json", "expectations.json")}</li>
   <li>Independent test: <code>test_cms_ex3_pays_500_dollars_not_1500</code> in ${raw("tests_policy/test_policy.py", "test_policy.py")}</li>
   <li>Python tests: <code>test_cms_ex3_contract_replaces_charges_and_pays_500</code>, <code>test_cms_ex3_without_contract_would_pay_1500</code></li>
   <li>Comparison row: <a href="#compare" data-goto-ex3="1">curated batch, CMS-EX3</a></li></ul></div></div>`;
};
R.pilot = async () => `<h1>8 · A four-week pilot</h1>
  <p class="lede">How CMS could try this safely on one real system: security sets the rules first, then tries to break them.</p>
  <div class="card">${md(await file("docs/presentation/pilot-plan.md"))}</div>`;
R.security = async () => `<h1>6 · Security &amp; data</h1>
  <p class="lede">What this demo touched, what Cognition publishes about how data is protected, and straight answers to the questions a CIO, VP of Engineering or security engineer is likely to ask. Anything not in public documentation is marked <b>Confirm with Cognition</b>.</p>
  <div class="card">${md(await file("docs/presentation/security-and-data.md"))}</div>`;
R.review = async () => {
  const st = E.status || {}, ev = E.session_events || [];
  return `<h1>7 · Reviewable, and repeatable</h1>
  <p class="lede">Everything a human reviewer needs is in one pull request, and the process is saved as Playbooks so Devin can do it again — or keep maintaining the code.</p>
  ${E.status_problem ? `<div class="err">demo/status.json ${esc(E.status_problem)}</div>` : `<p class="small muted">PR / Playbook status recorded ${esc(st.recorded_at)} — click through for the current state.</p>`}
  <h2>Pull requests</h2><div class="grid g2">${(st.pull_requests || []).map(p => `<div class="card"><h3><a href="${esc(p.url)}" target="_blank">#${p.number}</a> ${badge(p.state)}</h3>${esc(p.title)}<div class="small muted">${esc(p.role)}</div>${p.commits_url ? `<a class="small" href="${esc(p.commits_url)}" target="_blank">See the commit-by-commit order</a>` : ""}</div>`).join("")}</div>
  <h2>Commit history (this checkout)</h2><table><tbody>${E.git.commits.slice(0, 10).map(c => `<tr><td>${commit(c.sha)}</td><td class="small">${esc(c.date)}</td><td>${esc(c.subject)}</td></tr>`).join("")}</tbody></table>
  <h2>Playbooks — Devin can repeat this</h2><div class="grid g2">${(st.playbooks || []).map(p => `<div class="card"><h3><a href="${esc(p.url)}" target="_blank">${esc(p.title)}</a></h3><div class="small"><code>${esc(p.id)}</code> · starts from <code>${esc(p.start_ref)}</code> · source ${raw(p.source)}</div>
   <p>Rehearsal run: ${badge(p.fresh_run?.status || "UNKNOWN")} <a href="${esc(p.fresh_run?.session || "#")}" target="_blank">session</a>${p.fresh_run?.pr ? ` · <a href="${esc(p.fresh_run.pr)}" target="_blank">PR</a>` : ""}</p></div>`).join("")}</div>
  <h2>Watch Devin do it again, live</h2><div id="devinslot">${devinCard()}</div>
  <h2>Assumptions &amp; limits</h2><ul><li>Synthetic, educational module based on public CMS rules — not CMS production code, not complete Medicare policy.</li><li>Parity is proven for the tested batches (curated 30, synthetic 1,000, edge 24, fatal paths) — not for every possible input.</li><li>Both versions stop on lines over 4,096 bytes or more than 10,000 claims, deliberately identical.</li><li>No performance or cost claims.</li></ul>
  ${(E.expectations?.interface_assumptions) ? `<details><summary>Interface assumptions Devin recorded</summary><pre>${esc(JSON.stringify(E.expectations.interface_assumptions, null, 1))}</pre></details>` : ""}
  ${await mdBlock("docs/migration/02-rule-map.md", "Rule map: policy → COBOL → test → Python")}
  <details><summary>Human interventions and review time (${ev.length} events)</summary><table><thead><tr><th>When</th><th>Who</th><th>What</th><th>Human time</th></tr></thead><tbody>${ev.map(e => `<tr><td class="small">${esc(e.timestamp_utc)}</td><td>${esc(e.actor)}</td><td>${esc(e.event)}</td><td>${esc(e.human_intervention_seconds)}</td></tr>`).join("")}</tbody></table><p class="small muted">UNKNOWN means not measured — it is not zero. No efficiency claim is made.</p></details>`;
};

const MANUAL = "Run this on wstomber/devinexecdemo starting from branch demo/starter-37ceca1.";
const manualSteps = () => `<ol><li>Open <a href="https://app.devin.ai" target="_blank">app.devin.ai</a> and start a new session.</li><li>In the Playbook picker, choose <b>MSP COBOL to Python with evidence</b>.</li>
   <li>Paste: <div class="cmd"><code>${MANUAL}</code><button class="btn sm" data-copy="${MANUAL}">Copy</button></div></li></ol>`;
function devinLabel(s) {
  if (s.status === "running") return ({waiting_for_user: ["Waiting for input", "UNKNOWN"], waiting_for_approval: ["Waiting for approval", "UNKNOWN"], finished: ["Finished", "PASSED"]})[s.status_detail] || ["Working", "RUNNING"];
  return ({new: ["Starting", "RUNNING"], claimed: ["Starting", "RUNNING"], resuming: ["Resuming", "RUNNING"], suspended: ["Paused", "UNKNOWN"], exit: ["Finished", "PASSED"], error: ["Error", "FAILED"]})[s.status] || ["Unknown", "UNKNOWN"];
}
const devinActive = s => s && ["new", "claimed", "running", "resuming", "suspended"].includes(s.status) && s.status_detail !== "finished";
function devinCard() {
  const intro = `<p>Starts a brand-new Devin session with the saved Playbook <b>MSP COBOL to Python with evidence</b>. It begins from the COBOL-only starter branch and has never seen the finished migration.</p>`;
  if (!D) return `<div class="card">${intro}<p class="muted">Checking Devin…</p></div>`;
  const err = D.error ? `<div class="err">${esc(D.error)}</div>` : "";
  if (!D.configured) return `<div class="card">${intro}${err}<p class="small muted">This copy of the app has no Devin API key, so start it by hand:</p>${manualSteps()}</div>`;
  const s = D.session, startBtn = label => `<button class="btn primary" data-devin-start="1">${label}</button>`;
  if (!s) return `<div class="card">${intro}${err}<p>${startBtn("▶ Start Devin live")}</p><p class="small muted">A full migration takes longer than a meeting. Start it early, then come back to it at the end.</p></div>`;
  const [label, cls] = devinLabel(s), started = s.started_at ? new Date(s.started_at).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"}) : "";
  const prs = (s.pull_requests || []).map(p => `<a href="${esc(p.url)}" target="_blank">Pull request ${esc(p.url.split("/").pop())}</a> ${badge((p.state || "open").toUpperCase())}`).join(" · ");
  return `<div class="card">${intro}${err}
   <p>${LIVE_DEVIN} ${badge(cls, label)} <span class="small">started ${esc(started)}</span></p>
   <p><a class="btn primary" href="${esc(s.url)}" target="_blank">Open Devin's session ↗</a> ${prs ? `&nbsp; ${prs}` : devinActive(s) ? `<span class="small muted">&nbsp; Its pull request appears here once Devin opens it.</span>` : `<span class="small muted">&nbsp; No pull request was opened.</span>`}</p>
   ${s.problem ? `<p class="small muted">Last status check: ${esc(s.problem)}</p>` : ""}
   ${s.status === "suspended" ? `<p class="small muted">Devin paused this session. Open it and send a message to resume it.</p>` : devinActive(s) ? `<p class="small muted">Status updates every 10 seconds.</p>` : `<p>${startBtn("▶ Start another live run")}</p>`}</div>`;
}
async function refreshDevin() {
  if (!$("#devinslot")) { clearInterval(dpoll); dpoll = null; return; }
  try { const r = await fetch("/api/devin-run"); D = await r.json(); } catch (e) { D = {configured: true, error: "Could not reach this app's server."}; }
  const slot = $("#devinslot"); if (slot) slot.innerHTML = devinCard();
  if (!devinActive(D?.session)) { clearInterval(dpoll); dpoll = null; } else if (!dpoll) dpoll = setInterval(refreshDevin, 10000);
}

function renderLive() {
  const L = E.live, running = E.live_running || L?.status === "RUNNING";
  $("#live").innerHTML = `${L ? `${LIVE} ${badge(L.status)} <span>${esc(L.started_at || "")}</span> <a href="#" style="color:#cfe0ff" data-steps="1">steps</a>` : `<span class="badge NOT_RUN">NO LIVE RUN YET</span>`}
   <button class="btn primary" id="runlive" ${running ? "disabled" : ""}>${running ? "Running COBOL and Python…" : "▶ Run COBOL vs Python now"}</button>${L && !running ? ' <button class="btn" id="resetlive" title="Clear live results; saved rehearsal evidence is untouched">Reset</button>' : ""}`;
  if (running && !poll) poll = setInterval(refresh, 1500);
  if (!running && poll) { clearInterval(poll); poll = null; }
}
function showSteps() {
  const L = E.live; if (!L) return;
  $("#drawer").hidden = false;
  $("#drawer").innerHTML = `<button class="btn" data-close="1" style="float:right">Close</button><h2>Live run ${esc(L.id)}</h2>
   <p>${LIVE} ${badge(L.status)}<br><span class="small">Started ${esc(L.started_at)} · finished ${esc(L.finished_at || "—")} · commit ${commit(L.commit)}${L.dirty ? " (uncommitted changes present)" : ""}<br>Folder <code>${esc(L.folder)}</code></span></p>
   <ul class="steps">${(L.steps || []).map(s => `<li>${badge(s.status)}<span><b>${esc(s.title)}</b><br><code class="small">${esc(s.command)}</code><br><span class="small">exit ${s.exit_code ?? "—"} · ${raw(s.log, "full output")}</span></span></li>`).join("")}</ul>
   <p class="small muted">If a step fails, the saved rehearsal evidence stays on screen, labeled SAVED REHEARSAL.</p>`;
}
function showCase(k) {
  const c = E.expectations.cases[k]; $("#drawer").hidden = false;
  $("#drawer").innerHTML = `<button class="btn" data-close="1" style="float:right">Close</button><h2><code>${esc(c.claim_id)}</code></h2><p>${esc(c.category)} · ${esc(c.source || "")}</p>
   <h3>Input</h3><pre>${esc(JSON.stringify(c.input, null, 1))}</pre><h3>Hand-derived arithmetic</h3><p>${esc(c.arithmetic || "—")}</p>
   ${c.assumptions ? `<h3>Assumptions</h3><p>${esc(c.assumptions)}</p>` : ""}<h3>Expected</h3><p>${esc(c.expected.status)} · ${money(c.expected.payment_cents)} · <code>${esc(c.expected.reason)}</code></p>`;
}
function showRow(no) {
  const c = cmpSources().find(s => s[0] === cmpKey)[1], r = c.rows.find(x => x[0] === no); if (!r) return;
  const ex = E.expectations?.cases?.find(x => x.claim_id === r[1]);
  $("#drawer").hidden = false;
  $("#drawer").innerHTML = `<button class="btn" data-close="1" style="float:right">Close</button><h2>Record ${r[0]} · <code>${esc(r[1])}</code></h2><p>${badge(r[8])} ${c.kind === "live" ? LIVE : SAVED}</p>
   <table><thead><tr><th></th><th>COBOL (original)</th><th>Python (new)</th></tr></thead><tbody>
   <tr><td>Status</td><td>${esc(r[2] ?? "—")}</td><td>${esc(r[3] ?? "—")}</td></tr><tr><td>Payment</td><td class="num">${money(r[4])}<br><span class="small">${cents(r[4])}</span></td><td class="num">${money(r[5])}<br><span class="small">${cents(r[5])}</span></td></tr>
   <tr><td>Reason</td><td><code>${esc(r[6] ?? "—")}</code></td><td><code>${esc(r[7] ?? "—")}</code></td></tr></tbody></table>
   ${ex ? `<h3>Independent expectation</h3><p>${esc(ex.expected.status)} · ${money(ex.expected.payment_cents)} · <code>${esc(ex.expected.reason)}</code> ${badge(ex.expected.payment_cents === r[5] && ex.expected.status === r[3] ? "MATCH" : "MISMATCH")}</p><p class="small">${esc(ex.arithmetic || "")}</p>` : ""}
   ${r[1] === "CMS-EX3" ? `<p><a href="#ex3">Open the CMS-EX3 walkthrough →</a></p>` : ""}`;
}

async function render() {
  route = (location.hash.slice(1) || "overview"); if (!R[route]) route = "overview";
  $("#nav").innerHTML = VIEWS.map(([k, l]) => `<a href="#${k}" class="${k === route ? "on" : ""}${k === "ex3" ? " ex3" : ""}">${l}</a>`).join("");
  $("#view").innerHTML = await R[route]();
  const idx = VIEWS.findIndex(v => v[0] === route);
  $("#foot").innerHTML = `<span>${idx > 0 ? `<a class="btn" href="#${VIEWS[idx - 1][0]}">← ${esc(VIEWS[idx - 1][1])}</a>` : ""}</span>
   <span class="muted">Checkout ${commit(E.git.head)} on <code>${esc(E.git.branch)}</code> · evidence read ${esc(E.generated_at)}</span>
   <span>${idx < VIEWS.length - 1 ? `<a class="btn primary" href="#${VIEWS[idx + 1][0]}">${esc(VIEWS[idx + 1][1])} →</a>` : ""}</span>`;
  renderLive();
  if ($("#devinslot")) refreshDevin();
}
async function load() {
  const r = await fetch("/api/evidence"); if (!r.ok) throw new Error("evidence " + r.status); E = await r.json();
}
async function refresh() { const wasRunning = E?.live_running; await load(); renderLive(); if (!$("#drawer").hidden && $("#drawer h2")?.textContent.startsWith("Live run")) showSteps();
  if (wasRunning && !E.live_running) openFresh(); }
function openFresh() { $("#drawer").hidden = true; cmpKey = curatedKey(); cmpQuery = ""; cmpFilter = "all"; cmpPage = 0;
  if (location.hash === "#compare") render(); else location.hash = "#compare"; }

document.addEventListener("click", async ev => {
  const t = ev.target.closest("[data-copy],[data-cmp],[data-f],[data-pg],[data-row],[data-case],[data-close],[data-steps],[data-jump],[data-goto-ex3],[data-devin-start],#runlive,#resetlive");
  if (!t) return;
  if (t.dataset.copy) { navigator.clipboard?.writeText(t.dataset.copy); t.textContent = "Copied"; return; }
  if (t.dataset.devinStart) { t.disabled = true; t.textContent = "Starting Devin…"; try { const r = await fetch("/api/devin-run", {method: "POST"}); D = await r.json(); } catch (e) { D = {...(D || {}), error: "Could not reach this app's server."}; } const slot = $("#devinslot"); if (slot) slot.innerHTML = devinCard(); if (devinActive(D?.session) && !dpoll) dpoll = setInterval(refreshDevin, 10000); return; }
  if (t.id === "runlive") { t.disabled = true; t.textContent = "Starting…"; const r = await fetch("/api/live-run", {method: "POST"}); await load(); if (r.ok && !E.live_running) return openFresh(); renderLive(); showSteps(); return; }
  if (t.id === "resetlive") { t.disabled = true; await fetch("/api/live-reset", {method: "POST"}); await load(); cmpKey = null; cmpQuery = ""; cmpFilter = "all"; cmpPage = 0; $("#drawer").hidden = true; return render(); }
  if (t.dataset.steps) { ev.preventDefault(); showSteps(); return; }
  if (t.dataset.close) { $("#drawer").hidden = true; return; }
  if (t.dataset.case) return showCase(+t.dataset.case);
  if (t.dataset.row) return showRow(+t.dataset.row);
  if (t.dataset.cmp) { cmpKey = t.dataset.cmp; cmpPage = 0; return render(); }
  if (t.dataset.f) { cmpFilter = t.dataset.f; cmpPage = 0; return render(); }
  if (t.dataset.pg) { cmpPage = Math.max(0, cmpPage + +t.dataset.pg); return render(); }
  if (t.dataset.jump || t.dataset.gotoEx3) { cmpQuery = "CMS-EX3"; cmpFilter = "all"; cmpPage = 0; cmpKey = curatedKey(); if (t.dataset.gotoEx3) return; return render(); }
});
document.addEventListener("input", ev => { if (ev.target.id === "cmpq") { cmpQuery = ev.target.value; cmpPage = 0; clearTimeout(window._q); window._q = setTimeout(async () => { await render(); const i = $("#cmpq"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }, 200); } });
document.addEventListener("toggle", async ev => { const d = ev.target; if (d.dataset?.md && d.open && !d.dataset.loaded) { d.dataset.loaded = 1; d.querySelector("div").outerHTML = md(await file(d.dataset.md)); } }, true);
document.addEventListener("keydown", ev => { if (ev.target.tagName === "INPUT") return; const idx = VIEWS.findIndex(v => v[0] === route);
  if (ev.key === "ArrowRight" && idx < VIEWS.length - 1) location.hash = VIEWS[idx + 1][0]; if (ev.key === "ArrowLeft" && idx > 0) location.hash = VIEWS[idx - 1][0];
  if (ev.key === "Escape") $("#drawer").hidden = true; });
window.addEventListener("hashchange", () => { $("#drawer").hidden = true; render(); window.scrollTo(0, 0); });
load().then(render).catch(e => { $("#view").innerHTML = `<div class="err">Could not load evidence: ${esc(e.message)}. Is <code>make demo</code> running?</div>`; });
