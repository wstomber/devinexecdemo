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

const when = t => t ? new Date(t).toLocaleString([], {month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"}) : "unknown time";
const BATCH = {
  curated: ["curated", "Hand-picked policy examples: two worked examples from the CMS manual, plus claims built to test each payment rule, each CWF rejection and each kind of malformed line."],
  synthetic: ["synthetic", "1,000 random, everyday-looking claims."],
  edge: ["broken-input test", "The answer-key claims plus 2,000 deliberately damaged records (bytes changed, fields garbled, lines cut short): both versions must give the same result on every one, including the same error for each line they reject."],
};
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

function testStatus(saved, live, label, cases) {
  const n = (t, st) => t != null ? `${t} tests${cases && st === "PASSED" ? ` · all ${cases} answer-key cases` : ""}` : "";
  return `<div class="card"><h3>${esc(label)}</h3>
   <div>${SAVED} ${badge(saved?.status || "UNKNOWN")} ${saved?.tests != null ? saved.tests + " tests" : ""} · ${raw(saved?.log, "log")}</div>
   <div style="margin-top:6px">${LIVE} ${live ? badge(live.status) + (live.tests != null ? " " + n(live.tests, live.status) : "") + " · " + raw(live.log, "log") : badge("NOT_RUN") + ' <span class="muted small">press “Run COBOL vs Python now” on <a href="#compare">screen 5</a></span>'}</div></div>`;
}
const liveStep = key => E.live?.steps?.find(s => s.key === key);
function stepLine(key) { const s = liveStep(key); return s ? `${LIVE} ${badge(s.status)} exit ${s.exit_code ?? "—"} · ${raw(s.log, "output")}` : `${LIVE} ${badge("NOT_RUN")}`; }

const findRow = (cmp, id) => cmp?.rows?.find(r => r[1] === id);
const cwfBadge = (d, why) => d ? `${badge(d === "ACCEPTED" ? "PASSED" : d === "REJECTED" ? "FAILED" : "NOT_RUN", d === "NOT_SENT" ? "NOT SENT" : d)}${why && d !== "NOT_SENT" ? ` <code class="small">${esc(why)}</code>` : ""}` : "—";

const VIEWS = [["overview", "The problem"], ["baseline", "1 · COBOL baseline"], ["explain", "2 · Devin explains COBOL"], ["tests", "3 · Tests came first"],
  ["python", "4 · Python + unit tests"], ["compare", "5 · Old vs new"], ["review", "6 · Review & repeat"], ["security", "7 · Security FAQ"], ["pilot", "8 · Pilot plan"]];

const R = {};
R.overview = async () => {
  const s = E.saved, c = s.comparisons, total = Object.values(c).reduce((n, x) => n + (x.records?.python || 0), 0);
  const allPassed = Object.values(c).every(x => x.status === "PASSED");
  return `<h1>Can Devin safely modernize code that few engineers still understand?</h1>
  <p class="lede">A synthetic COBOL module that follows a Medicare Secondary Payer claim — when Medicare pays after another insurer — the way CMS documents it: first it <b>calculates</b> what Medicare owes, then a <b>CWF check</b> approves or rejects the claim, and only an approved claim's payment is released. Devin had to understand it, recover the policy behind it, test it, migrate it to Python, and prove the result.</p>
  <div class="flow">
    <div class="card"><h3>1. Run the original</h3>${badge(s.baseline.status)}<div class="small">COBOL baseline kept as the yardstick</div></div><div class="arrow">→</div>
    <div class="card"><h3>2. Explain it</h3><div class="small">Plain-English guide + DeepWiki for new engineers</div></div><div class="arrow">→</div>
    <div class="card"><h3>3. Test first</h3>${badge(E.git.tests_before_python.status)}<div class="small">Hand-derived answers, run on COBOL before any Python existed</div></div><div class="arrow">→</div>
    <div class="card"><h3>4. Migrate &amp; compare</h3>${badge(allPassed ? "PASSED" : "FAILED")}<div class="small">${total.toLocaleString()} claims compared, ${Object.values(c).reduce((n, x) => n + (x.mismatches || 0), 0)} mismatches</div></div>
  </div>
  <h2>Devin, working live</h2><div id="devinslot">${devinCard()}</div>`;
};
const CLAIM_FIELDS = [["claim ID", 12], ["charges", 10], ["approved", 10], ["primary", 10], ["deduct", 10], ["coins", 10], ["contract", 10], ["F", 1], ["MBI", 11], ["svc date", 8]];
const ymd = t => /^\d{8}$/.test(t) ? `${t.slice(0, 4)}-${t.slice(4, 6)}-${t.slice(6)}` : esc(t);
const dollars = t => /^\d{10}$/.test(t) ? $$(+t) : t.trim() === "" ? "(blank)" : /^-+$/.test(t) ? "none" : esc(t);
function claimLine(l) {
  let o = 0; return CLAIM_FIELDS.map(([, w], k) => { const t = l.slice(o, o + w); o += w; return `<span class="f${k % 2}">${esc(t)}</span>`; }).join("") + esc(l.slice(o));
}
async function baselineTerminal(b) {
  const [dat, res, tot, log, cwf] = await Promise.all([file(b.raw["curated.dat"]), file(b.raw["curated-results.csv"]), file(b.raw["curated-totals.csv"]), file(b.raw["commands.log"]), b.raw["cwf.dat"] ? file(b.raw["cwf.dat"]) : null]);
  if (dat == null || res == null) return `<p class="err">Saved baseline files are missing.</p>`;
  const lines = t => { const a = t.split("\n"); if (a[a.length - 1] === "") a.pop(); return a; };
  const SHOWN = 15, more = (n, path) => n > SHOWN ? L("c", `# … first ${SHOWN} of ${n} claims shown · ${raw(path, "full file")}`) : "";
  const L = (cls, html) => `<div class="${cls}">${html}</div>`;
  const run = (log || "").split("\n"), at = run.findIndex(l => /^\$ build\/msp-batch \S*curated\.dat/.test(l));
  const cmdText = at >= 0 ? run[at].slice(2) : "build/msp-batch curated.dat cwf.dat curated-results.csv curated-totals.csv";
  const exit = at >= 0 ? (run.slice(at + 1, at + 5).find(l => /^\[exit/.test(l)) || "") : "";
  const ruler = CLAIM_FIELDS.map(([n, w], k) => `<span class="f${k % 2}">${esc(n.padEnd(w).slice(0, w))}</span>`).join("");
  const ex3 = lines(dat)[0];
  const ex3out = lines(res).map(l => l.split(","))[1];
  let decode = ""; if (ex3) { let o = 0; decode = CLAIM_FIELDS.map(([n, w]) => { const t = ex3.slice(o, o + w); o += w; return n === "claim ID" ? `<b>${esc(t.trim())}</b>` : n === "F" ? `paid in full: ${esc(t)}` : n === "MBI" ? `beneficiary ${esc(t)}` : n === "svc date" ? `service date ${ymd(t)}` : `${n} ${dollars(t)}`; }).join(" · "); }
  return `<div class="term">${L("p", "$ cat curated.dat")}${L("c", "# the input: one claim per line, fixed-width, 92 characters, amounts in cents")}${L("ruler", ruler)}
  ${lines(dat).slice(0, SHOWN).map(l => L("ln", claimLine(l))).join("")}${more(lines(dat).length, b.raw["curated.dat"])}
  ${cwf != null ? `${L("p", "$ cat cwf.dat")}${L("c", "# CWF reference data: B = beneficiary (entitled from/to, MSP period), H = a claim already paid")}${lines(cwf).map(l => L("ln", esc(l))).join("")}` : ""}
  ${L("p", "$ " + esc(cmdText))}${exit ? L("c", esc(exit)) : ""}
  ${L("p", "$ cat curated-results.csv")}${L("c", "# the output: one result per claim, in the same order")}
  ${lines(res).slice(0, SHOWN + 1).map(l => L("ln", esc(l))).join("")}${more(lines(res).length - 1, b.raw["curated-results.csv"])}
  ${L("p", "$ cat curated-totals.csv")}${tot ? lines(tot).map(l => L("ln", esc(l))).join("") : L("err", "curated-totals.csv is missing from the saved run")}</div>
  ${decode ? `<p class="small">The first input line, decoded: ${decode}. ${ex3out ? ` The COBOL's answer for it: calculated <b>${esc(ex3out[2])} ${$$(+ex3out[3])}</b> (${esc(ex3out[4])}); CWF <b>${esc(ex3out[5] || "?")}</b> (${esc(ex3out[6] || "?")}); released <b>${$$(+(ex3out[7] || 0))}</b>.` : ""}</p>` : ""}`;
}
R.baseline = async () => {
  const b = E.saved.baseline, ct = b.curated_totals, st = b.synthetic_totals, m = b.manifest || {};
  const stat = (n, l) => `<div class="card stat"><div class="n">${n}</div><div class="l">${l}</div></div>`;
  return `<h1>1 · The original COBOL program, run first</h1>
  <p class="lede">The program reads a batch of claims (one fixed-width line each) and Medicare's CWF reference file. For each claim it calculates the payment (PAID, ZERO or INVALID, with a reason), then runs the CWF check (ACCEPTED or REJECTED, with a reason), and writes the amount released — plus a totals line.</p>
  <p>This is the real terminal session from the saved run: the claims that went in, the CWF reference data, the command, and exactly what the old COBOL wrote out.</p>
  ${await baselineTerminal(b)}
  <h2>Curated ${ct?.records ?? ""}-claim batch, summarised ${SAVED} ${badge(b.status)}</h2>
  <div class="grid g4">${ct ? stat(ct.records, "claims") + stat(ct.paid, "paid") + stat(ct.zero, "zero (valid, nothing owed)") + stat(ct.invalid, "malformed, never sent to CWF") + stat(money(ct.payment_cents), "calculated by COBOL") + stat(ct.accepted, "approved by CWF") + stat(ct.rejected, "rejected by CWF") + stat(money(ct.released_cents), "released after CWF") : `<div class="err">Totals file missing</div>`}</div>
  <h2>1,000-claim synthetic batch ${SAVED}</h2>
  <div class="grid g4">${st ? stat(st.records.toLocaleString(), "claims") + stat(st.paid, "paid") + stat(st.zero, "zero") + stat(st.invalid, "malformed") + stat(money(st.payment_cents), "calculated by COBOL") + stat(st.accepted, "approved by CWF") + stat(st.rejected, "rejected by CWF") + stat(money(st.released_cents), "released after CWF") : `<div class="err">Totals file missing</div>`}</div>
  <h2>Live re-run</h2><div class="card">${stepLine("build")}<br>${stepLine("baseline")}<div class="small muted" style="margin-top:6px">Live runs write to a new folder each time and never change the saved rehearsal.</div></div>
  <details><summary>Technical detail: identity, environment, raw files</summary>
   <p>Starter commit (COBOL only): ${commit(E.git.starter)} · captured ${esc(m.captured_at_utc || "UNKNOWN")} · verifier result ${badge(b.status)} (expected-results check, migration comparison ${esc(b.report?.migration_comparison || "UNKNOWN")})</p>
   <pre>${esc(E.saved.environment || "environment.txt missing")}</pre>
   ${cmd("make doctor && make build baseline generate test capture-baseline")}
   <p>${Object.entries(b.raw).map(([n, p]) => raw(p, n)).join(" · ")} · ${raw(b.log, "baseline log")}</p></details>`;
};
R.explain = async () => {
  const pay = await codeSnippet("cobol/payment.cob", /calculate-prospective-payment\./, /function min/);
  const cwf = await codeSnippet("cobol/cwf.cob", /^check-claim\./, /move claim-payment to claim-released/);
  return `<h1>2 · Devin explains the legacy code</h1>
  <p class="lede">Six COBOL files. Devin documented what each does, in plain language, for engineers who have never seen COBOL.</p>
  <div class="grid g3">
   <div class="card"><h3>batch.cob — the driver</h3>Loads the CWF reference file, reads the claims line by line, checks for duplicate claim IDs, calls the payment step and then the CWF check, writes each result and the totals. Stops the whole batch on fatal problems.</div>
   <div class="card"><h3>validate.cob — the gatekeeper</h3>Checks each line in a fixed order (length, ID, amounts, contract, flag, beneficiary ID, service date) and names the first problem it finds.</div>
   <div class="card"><h3>claim.cpy — the record layout</h3>A “copybook”: one shared definition of the 92-character claim line and its results, used by all programs.</div>
   <div class="card"><h3>payment.cob — the money</h3>Works out what Medicare owes as the secondary payer, in exact cents.</div>
   <div class="card"><h3>cwf.cob — the CWF check</h3>After the payment is calculated: is the person entitled on the service date, was this claim already paid, and if another insurer pays first, did they pay? Only an approved claim releases its payment.</div>
   <div class="card"><h3>cwf.cpy — Medicare's reference data</h3>Tables of beneficiaries (entitlement and MSP periods) and claims already paid, loaded once from the CWF file.</div></div>
  <h2>The key rule: the provider's contract replaces the charges</h2>
  <div class="grid g2"><div>${pay}</div><div class="card">
   <p><b>In plain English:</b> start with the provider's charges. <b>If the claim has a contractual amount</b> (<code>claim-has-contract = 1</code>), use that instead (<code>move claim-contract to charge-basis</code>). The payment can never be more than the <b>lower</b> of what Medicare would normally pay and that basis (<code>function min</code>).</p>
   <p class="small muted">COBOL terms: a <i>paragraph</i> (<code>calculate-prospective-payment.</code>) is a named block, like a function. <code>comp-3</code> is packed decimal — exact whole numbers, so no rounding drift.</p></div></div>
  <h2>Then the CWF check decides whether it is paid</h2>
  <div class="grid g2"><div>${cwf}</div><div class="card">
   <p><b>In plain English:</b> CMS's claims manual (Pub. 100-04, Ch. 27 §20) says the contractor prices the claim first, then sends it to the Common Working File for pre-payment validation. This program does three of those checks, in order, and the first failure wins: <b>not entitled</b> on the service date, <b>duplicate</b> of a claim already paid, or <b>MSP primary not billed</b> (Medicare's file says another insurer pays first, but the claim shows nothing paid by them).</p>
   <p>If none fail, CWF accepts it as is (disposition 01) and the calculated payment is released. Otherwise the calculation is kept for review, but <b>$0</b> is released. The reject codes are this demo's own; only "accepted as is" (01) is a CWF code.</p>
   <p class="small muted">COBOL terms: <code>perform varying … until</code> is a loop; <code>goback</code> returns to the caller, here as soon as one check fails.</p></div></div>
  <h2>For new engineers</h2>
  <p><a href="${esc(E.status?.deepwiki || "https://app.devin.ai/wiki/wstomber/devinexecdemo")}" target="_blank">Open the DeepWiki</a> — Devin's generated guide: COBOL for new engineers, each program explained, COBOL→Python mapping.</p>
  ${await mdBlock("docs/migration/03-cobol-primer.md", "COBOL primer (written against this code)")}
  ${await mdBlock("docs/migration/01-cobol-explanation.md", "Stage 1 explanation")}
  ${await mdBlock("docs/migration/04-legacy-walkthrough.md", "Line-by-line walkthrough")}`;
};
R.tests = async () => {
  const x = E.expectations, p = E.git.tests_before_python, s2 = E.git.stages.stage2, s3 = E.git.stages.stage3;
  const cases = x?.cases || [];
  return `<h1>3 · The tests came before the migration</h1>
  <p class="lede">Devin worked out the right answers by hand from the CMS manuals — the payment, the CWF decision and the amount released — not by copying what the COBOL printed, and checked the COBOL against them before any Python existed.</p>
  <div class="grid g2"><div class="card"><h3>Tests came first ${badge(p.status, p.status === "PASSED" ? "VERIFIED FROM GIT" : p.status)}</h3>
    <p>Tests committed in ${commit(s2?.sha)} (${esc(s2?.date || "")})<br>Python first appears in ${commit(s3?.sha)} (${esc(s3?.date || "")})</p>
    <p class="small">Checked now from git history: <code>python/msp.py</code> ${p.python_absent_at_stage2 ? "did <b>not</b> exist" : "<b>existed</b>"} at the test commit; test commit ${p.stage2_before_stage3 ? "precedes" : "does <b>not</b> precede"} the Python commit.</p></div>
   ${testStatus(E.saved.policy_tests_cobol, E.live?.policy_tests_cobol, "Answer key, run on COBOL", E.expectations?.cases?.length)}</div>
  <h2>The hand-derived ledger: ${cases.length} cases</h2>
  <p class="small muted">${esc(x?.derivation || "")}</p>
  <div class="tablewrap"><table><thead><tr><th>#</th><th>Claim</th><th>Category</th><th>Expected</th><th class="num">Expected payment</th><th>Reason</th><th>CWF</th><th class="num">Released</th><th>Source</th></tr></thead><tbody>
  ${cases.map((c, k) => `<tr class="click" data-case="${k}"><td>${c.record_no}</td><td><code>${esc(c.claim_id)}</code></td><td>${esc(c.category)}</td><td>${badge(c.expected.status === "PAID" ? "PASSED" : c.expected.status === "ZERO" ? "NOT_RUN" : "FAILED", c.expected.status)}</td><td class="num">${money(c.expected.payment_cents)}</td><td><code>${esc(c.expected.reason)}</code></td><td>${cwfBadge(c.expected.cwf, c.expected.cwf_reason)}</td><td class="num">${money(c.expected.released_cents)}</td><td class="small">${esc(c.source || "")}</td></tr>`).join("")}
  </tbody></table></div>
  <p class="small">Ledger totals (hand-derived): ${x?.totals ? `${x.totals.records} records · ${x.totals.paid} paid · ${x.totals.zero} zero · ${x.totals.invalid} invalid · ${money(x.totals.payment_cents)} calculated · CWF ${x.totals.accepted} approved, ${x.totals.rejected} rejected · ${money(x.totals.released_cents)} released` : "missing"} · ${raw("tests_policy/expectations.json", "expectations.json")} · ${raw("tests_policy/test_policy.py", "test_policy.py")}</p>
  <h2>Separate: starter infrastructure tests</h2><div class="card small">These came with the starter repo and check the COBOL harness itself; they are not Devin's independent policy tests. ${stepLine("starter-tests")}</div>
  ${cmd("python3 -m unittest discover -s tests_policy -v")}`;
};
const RULE_STEPS = [
  {say: "Was the bill already paid in full? Then Medicare pays $0.",
   cob: [[/if raw-full = "Y"/, /end-if/]], py: [[/if claim\.paid_in_full:/, /PAYMENT_IN_FULL/]],
   ex: c => c.full === "Y" ? "Yes → $0" : "No → keep going"},
  {say: "If the provider agreed to a contract amount, use it instead of the full charges.",
   cob: [[/move claim-charges to charge-basis/, /end-if/]], py: [[/return claim\.charges if claim\.contract/, /./]],
   ex: c => c.contract == null ? `No contract → ${$$(c.charges)}` : `Contract ${$$(c.contract)} replaces charges ${$$(c.charges)}`},
  {say: "The limit is the smaller of the approved amount and that step-2 amount.",
   cob: [[/compute payment-cap/, /./]], py: [[/return min\(claim\.gross, charge_basis/, /./], [/cap = payment_cap\(claim\)/, /./]],
   ex: c => `smaller of ${$$(c.gross)} and ${$$(c.contract ?? c.charges)} = ${$$(Math.min(c.gross, c.contract ?? c.charges))}`},
  {say: "Did the other insurer already pay the limit or more? Then Medicare pays $0.",
   cob: [[/if claim-primary >= payment-cap/, /end-if/]], py: [[/if claim\.primary >= cap:/, /PRIMARY_AT_CAP/]],
   ex: c => `paid ${$$(c.primary)}: ${c.primary >= capOf(c) ? "yes → $0" : "less than the limit → keep going"}`},
  {say: "Do the patient's deductible + coinsurance reach the limit? Then Medicare pays $0.",
   cob: [[/compute deductions =/, /end-if/]], py: [[/deductions = claim\.deductible/, /DEDUCTIONS_AT_CAP/]],
   ex: c => `${$$(c.deductible + c.coinsurance)}: ${c.deductible + c.coinsurance >= capOf(c) ? "yes → $0" : "less than the limit → keep going"}`},
  {say: "Otherwise Medicare pays the limit minus the bigger of those two amounts.",
   cob: [[/compute reduction-amount/, /SECONDARY_PAYABLE/]], py: [[/return Result\(claim\.claim_id, "PAID"/, /./]],
   ex: c => `${$$(capOf(c))} − ${$$(Math.max(c.primary, c.deductible + c.coinsurance))} = <b>${$$(capOf(c) - Math.max(c.primary, c.deductible + c.coinsurance))}</b>`},
  {say: "CWF check 1: is the person entitled to Medicare on the service date? If not, reject.", file: "cwf",
   cob: [[/if bene-found = 0 goback/, /./], [/if claim-dos < bene-from/, /end-if/]], py: [[/beneficiary = reference\.beneficiaries\.get/, /NOT_ENTITLED/]],
   ex: (c, b) => b ? `${esc(c.mbi)} entitled ${ymd(b.entitled_from)} to ${b.entitled_to === "99999999" ? "open-ended" : ymd(b.entitled_to)}; service ${ymd(c.dos)} → yes` : "not on file → reject"},
  {say: "CWF check 2: was this exact claim already paid? Then reject it as a duplicate.", file: "cwf",
   cob: [[/perform varying hist-index/, /end-perform/]], py: [[/if \(claim\.mbi, claim\.dos, claim\.charges\) in reference\.history/, /DUPLICATE/]],
   ex: (c, b, h) => h.some(x => x.mbi === c.mbi && x.dos === c.dos && x.charges === c.charges) ? "already paid → reject" : "not in the paid-claims history → keep going"},
  {say: "CWF check 3: if Medicare's MSP file says another insurer pays first, did they pay something? If not, reject.", file: "cwf",
   cob: [[/if bene-has-msp\(bene-found\) = 1/, /end-if/]], py: [[/msp = beneficiary\.msp_period/, /MSP_PRIMARY_NOT_BILLED/]],
   ex: (c, b) => b?.msp_from ? `MSP period ${ymd(b.msp_from)} to ${ymd(b.msp_to)} covers the service date; other insurer paid ${$$(c.primary)} → keep going` : "no MSP period → keep going"},
  {say: "Approved: release the calculated payment. A rejected claim releases $0.", file: "cwf",
   cob: [[/move "ACCEPTED" to claim-cwf/, /move claim-payment to claim-released/]], py: [[/return replace\(result, cwf="ACCEPTED"/, /./]],
   ex: c => `ACCEPTED → <b>${$$(capOf(c) - Math.max(c.primary, c.deductible + c.coinsurance))} released</b>`}];
const $$ = cents => "$" + (cents / 100).toLocaleString("en-US", {maximumFractionDigits: 2});
const capOf = c => Math.min(c.gross, c.contract ?? c.charges);
const MISSING = `<p class="err">Not found in the source.</p>`;
function ruleLines(text, ranges) {
  const L = text.split("\n"), out = [];
  for (const [a, b] of ranges) {
    const s = L.findIndex(l => a.test(l)); if (s < 0) return MISSING;
    let e = s; if (b.source !== ".") { while (e < L.length && !b.test(L[e])) e++; if (e === L.length) return MISSING; }
    out.push(L.slice(s, e + 1).map((t, k) => `<div class="ln"><span>${s + k + 1}</span><span>${esc(t.replace(/^ {4,8}/, ""))}</span></div>`).join(""));
  }
  return out.join(`<div class="ln gap"><span>⋮</span><span></span></div>`);
}
async function ruleMatch() {
  const [cob, cwfSrc, py, fx, ref] = await Promise.all([file("cobol/payment.cob"), file("cobol/cwf.cob"), file("python/msp.py"), file("fixtures/curated.json"), file("fixtures/cwf.json")]);
  if (cob == null || cwfSrc == null || py == null) return `<p class="err">Source files are missing.</p>`;
  let ex = null, bene = null, hist = []; try { ex = JSON.parse(fx).map(r => r.input).find(r => r?.id === "CMS-EX3"); const rf = JSON.parse(ref); bene = rf.beneficiaries.find(b => b.mbi === ex?.mbi); hist = rf.history; } catch (e) { ex = null; }
  if (ex && ex.contract === undefined) ex.contract = null;
  if (ex) { ex.mbi = ex.mbi || "1EG4TE5MK73"; ex.dos = ex.dos || "20250315"; }
  return `<table class="rulematch"><thead><tr><th>Step</th><th>COBOL (before)</th><th>Python (after)</th>${ex ? "<th>Worked example (CMS-EX3)</th>" : ""}</tr></thead><tbody>
  ${RULE_STEPS.map((st, k) => `<tr><td><span class="stepno">${k + 1}</span> ${esc(st.say)}</td>
    <td><div class="code">${st.file === "cwf" ? '<div class="small muted">cwf.cob</div>' : ""}${ruleLines(st.file === "cwf" ? cwfSrc : cob, st.cob)}</div></td><td><div class="code">${ruleLines(py, st.py)}</div></td>${ex ? `<td>${st.ex(ex, bene, hist)}</td>` : ""}</tr>`).join("")}
  </tbody></table>`;
}
const TEST_STEPS = [
  ["Reuse the answer key, unchanged", () => `Ran all ${E.expectations?.cases?.length ?? "?"} hand-worked cases from screen 3 against the Python. Only the program being tested changed; the cases and the test code stayed the same.`, "The Python never grades itself. Every expected answer came from the CMS manual and was checked on the COBOL before any Python existed.", "key", "A claim for $1,000 where the other insurer already paid the full $1,000. The answer key says Medicare pays $0; the Python must say exactly that."],
  ["Payment math, to the cent", "Unit tests for each payment rule: the four payment limits, the optional contract amount, and when the answer is $0.", "Amounts are whole-number cents, like the COBOL, never decimals that can round. Wrong cents don't crash anything, so each rule gets its own test. Standard Python only, so there are no new packages to vet.", ["test_payment_branches", "test_contract_basis_and_cms_example_3"], "A $100 claim where the other insurer paid $20 and the patient's deductible and coinsurance are $15. Medicare must pay exactly $80.00."],
  ["Read the 92-character record like the COBOL", "Tests for each field of the claim record: which characters count as digits, valid claim IDs, the contract flag, the Medicare ID and the dates.", "If the two versions disagree on what a valid field is, they accept or reject different claims. So the Python matches the COBOL exactly, even on odd characters.", ["test_ascii_digits_rejects_non_ascii_and_non_digits", "test_claim_id_rules", "test_each_amount_field_requires_ascii_digits", "test_contract_flag_mbi_and_date_rules"], "An amount written “+000000000” (a plus sign where a digit belongs) must be rejected as a bad amount, and so must a claim ID containing “@”."],
  ["Same check order", "Tests claims with two problems at once, to see which reason is reported.", "The first problem found decides the reason code. Testing one problem at a time would miss a change in the order.", ["test_validation_precedence"], "A claim with both a bad ID and a bad amount must be reported as a bad ID, because the COBOL checks the ID first."],
  ["Same line handling", "Tests different line endings, an empty file, and lines that are too long.", "Rewrites often differ on line endings and over-long lines. The Python reproduces the COBOL's behavior.", ["test_lf_crlf_lone_cr_and_empty_stream", "test_transport_limit_and_claim_raw_padding"], "The same claim must read the same whether its line ends Windows-style or Unix-style. A line over 4,096 characters must stop the run."],
  ["CWF check: same order, same date cut-offs", "Tests the three CWF checks in order (is the patient covered, is it a repeat bill, should another insurer have paid first) and one day either side of each coverage date.", "Dates one day off are a classic migration bug. A rejected claim keeps its calculated amount but releases $0.", ["test_cwf_order_and_entitlement_boundaries"], "A claim dated June 10 for a patient covered from June 11 must be rejected as “not covered”. Move the coverage start to June 10 and it passes that check."],
  ["Read the CWF file like the COBOL", "Tests how the reference file is read, which record wins when there are two, and that a broken file stops the run.", "The COBOL reads this file in its own particular way. Matching it means both versions see the same reference data.", ["test_cwf_reader_drops_cr_truncates_and_pads", "test_first_beneficiary_record_wins", "test_cwf_parser_records_and_boundaries", "test_cwf_record_limits"], "If the file lists the same patient twice, the first record is used. A file with 1,001 patient records (the limit is 1,000) must stop the run."],
  ["Fix the Python when it differs", "The tests found one real difference: when the output folder was missing, the Python reported file error 35 where the COBOL reports 30.", "The COBOL is the yardstick, so the Python was fixed, never the expected answer.", "fix"],
  ["Prove the tests can fail", "Plants four realistic bugs, one at a time, in a copy of the Python.", "Passing tests only mean something if they would fail on a mistake. Each planted bug turns the tests red.", "break", "Change “≥” to “>” in one line, a one-character slip, and the tests turn red."],
  ["Then compare every claim", "Hands over to screen 5, which runs the COBOL and the Python on the same claims and compares every field.", () => `Tests only check what someone thought of. The comparison also covers ${(E.saved.comparisons.synthetic?.records?.python ?? 0).toLocaleString()} synthetic and ${(E.saved.comparisons.edge?.records?.python ?? 0).toLocaleString()} broken claims that nobody worked out by hand.`, "compare", "For each of the 1,000 synthetic claims, the COBOL's output line and the Python's must match character for character."],
];
function testSteps(u, pt) {
  const v = x => typeof x === "function" ? x() : esc(x);
  const proof = p => {
    if (Array.isArray(p)) return p.map(nm => { const c = (u?.cases || []).find(x => x.name === nm); return `<div>${badge(c ? (c.result === "ok" ? "PASSED" : "FAILED") : "UNKNOWN")} <code>${esc(nm)}</code></div>`; }).join("");
    if (p === "key") { const lv = E.live?.policy_tests_python, k = lv || pt; return `${badge(k?.status || "UNKNOWN")} ${lv ? "live run" : "saved run"}${k?.status === "PASSED" ? ` · all ${E.expectations?.cases?.length ?? "?"} cases match` : ""}`; }
    if (p === "fix") return "Correction 3 in <i>Corrections Devin made along the way</i>, below";
    if (p === "break") return `<a href="#compare">Try to break it</a> on screen 5`;
    return `<a href="#compare">Screen 5 · Old vs new</a>`;
  };
  return `<table class="rulematch steps"><thead><tr><th>Step</th><th>What Devin did</th><th>Decision, and why</th><th>Proof</th></tr></thead><tbody>
  ${TEST_STEPS.map(([say, did, why, p, eg], k) => `<tr><td><span class="stepno">${k + 1}</span> <b>${esc(say)}</b></td><td>${v(did)}${eg ? `<div class="eg"><b>For example:</b> ${esc(eg)}</div>` : ""}</td><td>${v(why)}</td><td>${proof(p)}</td></tr>`).join("")}
  </tbody></table>`;
}
R.python = async () => {
  const u = E.saved.python_unit_tests, pt = E.saved.policy_tests_python;
  return `<h1>4 · The new Python, and its own tests</h1>
  <p class="lede">How the new Python was tested: the same answer key the COBOL passed on screen 3, plus unit tests aimed at every detail. Screen 5 then shows how the code was translated and compares it with the COBOL claim by claim.</p>
  ${[pt, u, E.live?.policy_tests_python, E.live?.python_unit_tests].some(x => x?.status && x.status !== "PASSED") ? `<div class="err">A test layer is not passing in the latest run. See the status boxes below the table.</div>` : ""}
  <h2>How the Python was tested, step by step</h2>
  <p>A <b>unit test</b> is a tiny program that feeds the Python one made-up input and checks it gives exactly the expected answer. If it doesn't, the test fails and names what broke.</p>
  <p>The table has <b>10 steps, not 10 tests</b>. Steps 2–7 hold the ${u.tests ?? "?"} unit tests, listed by name under Proof. The other steps are the answer key, a fix, planted bugs and the claim-by-claim comparison. Each row says what was done, the decision behind it, and a real example of what was checked.</p>
  ${testSteps(u, pt)}
  <div class="grid g2" style="margin-top:14px">${testStatus(pt, E.live?.policy_tests_python, "Answer key, run on Python", E.expectations?.cases?.length)}${testStatus(u, E.live?.python_unit_tests, "Python unit tests (live count includes the app's own tests)")}</div>
  <details><summary>Unit tests run (${u.tests ?? "?"})</summary><ul>${(u.cases || []).map(c => `<li>${badge(c.result === "ok" ? "PASSED" : "FAILED", c.result)} <code>${esc(c.name)}</code></li>`).join("")}</ul></details>
  <details data-md="${esc(E.saved.corrections)}"><summary>Corrections Devin made along the way</summary><div class="muted small">Loading…</div></details>
  <p class="small">Commit ${commit(E.git.stages.stage3?.sha)} · <a href="https://github.com/wstomber/devinexecdemo/commit/${esc(E.git.stages.stage3?.sha || "")}" target="_blank">view the diff</a></p>
  ${cmd("MSP_COMMAND='python3 python/msp.py' python3 -m unittest discover -s tests_policy -v")}${cmd("python3 -m unittest discover -s tests_python -v")}`;
};
const curatedKey = () => E.live?.comparisons?.curated?.rows?.length ? "live:curated" : "saved:curated";
function cmpSources() {
  const out = []; for (const [k, v] of Object.entries(E.saved.comparisons)) out.push(["saved:" + k, v]);
  for (const [k, v] of Object.entries(E.live?.comparisons || {})) out.push(["live:" + k, v]); return out;
}
function bugBanner() {
  const L = E.live, b = L?.bug; if (!b) return "";
  const c = L.comparisons?.curated, pt = L.policy_tests_python, failed = +(/failures=(\d+)/.exec(pt?.detail || "")?.[1] || 0) + +(/errors=(\d+)/.exec(pt?.detail || "")?.[1] || 0);
  const done = L.status !== "RUNNING";
  return `<div class="bugbanner"><h3>Planted bug, on purpose: ${esc(b.title)}</h3><p>${esc(b.what)} It was planted in a throwaway copy (${raw(b.file, "see the broken file")}); the real <code>python/msp.py</code> was not changed.</p>
   <div class="code"><div class="ln"><span>${b.line}</span><span class="del">- ${esc(b.old)}</span></div><div class="ln"><span>${b.line}</span><span class="add">+ ${esc(b.new)}</span></div></div>
   ${done ? `<p><b>${L.status === "FAILED" ? "The checks caught it" : "Result: " + esc(L.status)}:</b> ${c ? `${c.mismatches} of ${(c.rows || []).length} curated claims now get a different result from the COBOL` : "comparison missing"} · ${pt?.tests ? `${failed} of ${pt.tests} hand-derived tests failed` : "hand-derived tests did not report"} · strict verifier ${badge(c?.verifier?.status || "UNKNOWN")}</p>` : `<p class="muted">Running the checks against the broken copy…</p>`}
   <p><button class="btn primary" data-undo="1" ${done ? "" : "disabled"}>Undo: run the real code again</button></p></div>`;
}
function breakCard() {
  if (E.live?.bug || !E.bugs) return "";
  const running = E.live_running || E.live?.status === "RUNNING";
  return `<div class="card"><h3>Try to break it</h3><p>Pick a mistake a rewrite could easily make. The app puts it into a throwaway copy of the Python and reruns every check against the COBOL. The real code is never touched.</p>
   <p>${Object.entries(E.bugs).map(([k, b]) => `<button class="btn" data-bug="${esc(k)}" title="${esc(b.what)}" ${running ? "disabled" : ""}>${esc(b.title)}</button>`).join(" ")}</p></div>`;
}
R.compare = async () => {
  const src = cmpSources(); if (!cmpKey || !src.find(s => s[0] === cmpKey)) cmpKey = (src.find(s => s[0] === "live:synthetic") || src.find(s => s[0] === "saved:synthetic") || src[0])[0];
  const c = src.find(s => s[0] === cmpKey)[1];
  const q = cmpQuery.trim().toUpperCase();
  let rows = c.rows || [];
  if (cmpFilter === "mismatch") rows = rows.filter(r => r[8] !== "MATCH");
  if (cmpFilter === "paid") rows = rows.filter(r => r[2] === "PAID");
  if (cmpFilter === "invalid") rows = rows.filter(r => r[2] === "INVALID");
  if (cmpFilter === "cwf") rows = rows.filter(r => r[10] === "REJECTED" || r[11] === "REJECTED");
  if (q) rows = rows.filter(r => r.join(" ").toUpperCase().includes(q));
  const per = 200, pages = Math.max(1, Math.ceil(rows.length / per)); cmpPage = Math.min(cmpPage, pages - 1);
  const shown = rows.slice(cmpPage * per, cmpPage * per + per);
  const stat = (n, l, s) => `<div class="card stat"><div class="n">${n}</div><div class="l">${l}</div>${s || ""}</div>`;
  const t = c.totals || {};
  let py = "", pay = "", rules;
  try { [py, pay, rules] = await Promise.all([codeSnippet("python/msp.py", /^def charge_basis/, /SECONDARY_PAYABLE/), codeSnippet("cobol/payment.cob", /calculate-prospective-payment\./, /SECONDARY_PAYABLE/), ruleMatch()]); }
  catch (e) { rules = `<div class="err">Could not load the code from this checkout (${esc(e.message)}). The claim-by-claim results below are unaffected.</div>`; }
  return `<h1>5 · Old vs new: same rules, same results</h1>
  <p class="lede">How the COBOL was turned into Python, and the proof that both behave the same: first the rules side by side in the code, then both programs run on the same claims.</p>
  ${bugBanner()}
  <h2>1. The same rules, in the old code and the new</h2>
  <p>Devin translated the COBOL one rule at a time, keeping the same order, so each step below can be read across. Steps 1–6 calculate the payment, and steps 7–10 are the CWF check that decides whether it is released. The last column follows one example claim through each step.</p>
  ${rules}
  <p class="small muted">Numbers on the left of the code are line numbers in the real files. Python puts steps 2–3 into small named helper functions, which is why their line numbers sit above the rest. Steps 7–10 live in <code>cobol/cwf.cob</code> and in <code>cwf_check</code> in the Python.</p>
  <details><summary>See the full code side by side</summary><div class="grid g2"><div><h3>COBOL (before)</h3>${pay}</div><div><h3>Python (after)</h3>${py}</div></div></details>
  ${await mdBlock("docs/migration/05-cobol-to-python.md", "COBOL → Python translation guide")}
  <div class="reshead" id="results"><h2>2. The same results, claim by claim</h2><span id="livectl">${liveCtl()}</span></div>
  <p>Reading the code is not proof, so both programs were run on the same claims and the same CWF reference file. For every claim they must agree on the calculated payment, the CWF decision and the amount released. The table below is rebuilt from both programs' raw output files.</p>
  <details class="card"><summary><b>Watch: COBOL vs Python validated live in a terminal (1 min)</b></summary><p class="small">Devin builds the COBOL, runs both programs on the same claims, shows the files are byte-identical, runs the strict verifier, runs all ${E.expectations?.cases?.length ?? "?"} answer-key cases on both versions, and shows the CWF-rejected claims releasing $0.</p><video controls preload="metadata" src="cobol-vs-python-validation-1min.mp4" style="width:100%;max-height:560px;background:#000"></video></details>
  ${bugBanner() ? "" : breakCard()}
  <div class="toolbar">${src.map(([k, v]) => `<button class="btn${k === cmpKey ? " on" : ""}" data-cmp="${k}">${k.startsWith("live") ? "LIVE" : "SAVED"} · ${esc(BATCH[k.split(":")[1]]?.[0] || k.split(":")[1])} (${v.records?.python?.toLocaleString() ?? "?"})${k.startsWith("live") && E.live?.started_at ? ` · ${new Date(E.live.started_at).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"})}` : ""}</button>`).join("")}</div>
  <div>${c.kind === "live" ? LIVE : SAVED} ${badge(c.status, "OVERALL " + c.status)} <b class="small">${c.kind === "live" ? `Run ${esc(when(E.live?.started_at))} (Run COBOL vs Python now)` : `Saved rehearsal, recorded ${esc(when(E.git.stages.stage4?.date))}`}</b> <span class="muted small">· ${esc(c.title)}</span></div>
  ${BATCH[cmpKey.split(":")[1]] ? `<p class="small">${esc(BATCH[cmpKey.split(":")[1]][1])}</p>` : ""}
  ${c.problem ? `<div class="err">${esc(c.problem)}</div>` : ""}
  <div class="grid cmpstats" style="margin-top:10px">
   ${stat((c.rows || []).length.toLocaleString(), "claims compared", `<div class="small">COBOL ${c.records?.cobol ?? "?"} · Python ${c.records?.python ?? "?"}</div>`)}
   ${stat(c.mismatches ?? "?", "mismatches", badge(c.mismatches === 0 ? "MATCH" : "MISMATCH", c.mismatches === 0 ? "NONE" : "INSPECT"))}
   ${stat(money(t.cobol?.released_cents), "COBOL released after CWF", `<div class="small">${money(t.cobol?.payment_cents)} calculated · ${t.cobol?.rejected ?? "?"} rejected by CWF</div>`)}
   ${stat(money(t.python?.released_cents), "Python released after CWF", `<div class="small">${money(t.python?.payment_cents)} calculated · ${t.python?.rejected ?? "?"} rejected by CWF</div>` + badge(c.totals_match ? "MATCH" : "MISMATCH", c.totals_match ? "TOTALS MATCH" : "TOTALS DIFFER"))}
   ${stat(badge(c.verifier?.status || "UNKNOWN"), "strict verifier (tools/verify.py)", `<div class="small">${c.verifier?.report ? raw(c.verifier.report, "report") : esc(c.verifier?.detail === "not applicable" ? "not run for this batch — table only" : c.verifier?.detail || "")}</div>`)}
   ${stat(c.byte_identical ? "Yes" : "No", "output files byte-identical")}</div>
  ${c.duplicates?.length ? `<div class="err">Duplicate claim IDs: ${esc(c.duplicates.join(", "))}</div>` : ""}
  <div class="toolbar"><input type="search" id="cmpq" placeholder="Search claim ID, status, reason, CWF decision…" value="${esc(cmpQuery)}">
   ${[["all", "All"], ["mismatch", "Mismatches only"], ["paid", "Paid"], ["invalid", "Malformed"], ["cwf", "Rejected by CWF"]].map(([k, l]) => `<button class="btn${cmpFilter === k ? " on" : ""}" data-f="${k}">${l}</button>`).join("")}
   <span class="muted small">${rows.length.toLocaleString()} rows${pages > 1 ? ` · page ${cmpPage + 1}/${pages} <button class="btn sm" data-pg="-1">‹</button><button class="btn sm" data-pg="1">›</button>` : ""}</span></div>
  <div class="tablewrap"><table><thead><tr><th>#</th><th>Claim ID</th><th class="num">COBOL calculates</th><th class="num">Python calculates</th><th>COBOL CWF decision</th><th>Python CWF decision</th><th class="num">COBOL releases</th><th class="num">Python releases</th><th>Result</th></tr></thead><tbody>
  ${shown.length ? shown.map(r => `<tr class="click" data-row="${r[0]}"><td>${r[0]}</td><td><code>${esc(r[1])}</code></td><td class="num">${money(r[4])}<div class="small muted">${esc(r[2] ?? "—")} · ${esc(r[6] ?? "—")}</div></td><td class="num">${money(r[5])}<div class="small muted">${esc(r[3] ?? "—")} · ${esc(r[7] ?? "—")}</div></td><td>${cwfBadge(r[10], r[12])}</td><td>${cwfBadge(r[11], r[13])}</td><td class="num"><b>${money(r[14])}</b></td><td class="num"><b>${money(r[15])}</b></td><td>${badge(r[8])}</td></tr>`).join("") : `<tr><td colspan="9" class="muted">${cmpFilter === "mismatch" ? "No mismatches in this batch." : "No rows match."}</td></tr>`}
  </tbody></table></div>
  <details><summary>Technical detail: command, identity, raw files</summary>
   <p>Input <code>${esc(c.input || "UNKNOWN")}</code> · sha256 <code>${esc(c.input_sha256 || "UNKNOWN")}</code></p>
   <p>${c.kind === "live" ? `Live run ${esc(E.live.id)} · started ${esc(E.live.started_at)} · commit ${commit(E.live.commit)}${E.live.dirty ? " (uncommitted changes present)" : ""}` : `Saved in ${commit(E.git.stages.stage4?.sha)} (${esc(E.git.stages.stage4?.date || "")})`}</p>
   <p>${Object.entries(c.raw || {}).map(([n, p]) => raw(p, n)).join(" · ")}${E.saved.fatal_parity ? " · " + raw(E.saved.fatal_parity, "fatal-path parity (duplicate ID, 4,097-byte line, 10,001 records)") : ""}</p>
   ${cmd("make compare CANDIDATE='python3 python/msp.py'")}${cmd("python3 tools/demo_compare.py --input build/synthetic.dat --cwf build/cwf.dat --out build/cmp/synthetic")}
   <p class="small muted">A green table is not the proof on its own — the strict verifier (tools/verify.py) checks every field and the totals independently.</p></details>`;
};
const PILOT_WEEKS = [
  [1, "Set up", ["Meet the system owner and agree what Devin can access.", "Security sets the guardrails and signs off before Devin sees any code.", "Devin maps the code into a DeepWiki and records today's results.", "Devin pulls every business rule out of the COBOL into one list, each linked to the code it came from."]],
  [2, "Prove it", ["Agree the expected answers: reuse CMS's test cases and past claims, fill the gaps from the manuals, and check today's COBOL against them.", "Devin migrates the claim path to Python and compares old and new on every test claim."]],
  [3, "Real work", ["Devin makes 3–5 real changes from the backlog to this same MSP/CWF claim path, each reviewed by your engineers.", "Security tries to break it."]],
  [4, "Decide", ["Review the results together and make the go / no-go call."]],
];
R.pilot = async () => `<h1>8 · Pilot: one CWF MSP claim path in four weeks</h1>
  <p class="lede">The same steps you just saw, on the real code: the MSP payment calculation and the CWF edits that approve or reject the claim before payment. Security sets the rules first, then tries to break them.</p>
  <h2>The plan, step by step</h2>
  <div class="grid g4 pilotweeks">${PILOT_WEEKS.map(([wk, title, steps], w) => `<div class="card"><div class="small muted">Week ${w + 1}</div><h3>${esc(title)}</h3><ol>${steps.map((st, i) => `<li><span class="stepno">${PILOT_WEEKS.slice(0, w).reduce((n, x) => n + x[2].length, 0) + i + 1}</span><span>${esc(st)}</span></li>`).join("")}</ol></div>`).join("")}</div>
  <details><summary>The full plan: what's in scope, week-by-week detail, what we measure, what CMS provides</summary><div class="card">${md(await file("docs/presentation/pilot-plan.md"))}</div></details>
  <div class="card ask"><h2>Proposed next step</h2><p>Name an owner for the CWF MSP claim path and give read access to the MSP payment and CWF edit repositories and a test region. Then hold a 30-minute kickoff with your security lead to agree the week-1 guardrails and how success will be measured. Week 1 starts the day security signs off.</p></div>`;
R.security = async () => `<h1>7 · Security FAQ</h1>
  <p class="lede">Questions security engineers, architects and CIOs ask about running Devin in a CMS environment, with answers from Cognition's published documentation.</p>
  <div class="card">${md(await file("docs/presentation/security-and-data.md"))}</div>`;
R.review = async () => {
  if (!D) { try { D = await (await fetch("/api/devin-run")).json(); } catch (e) {} }
  const st = E.status || {}, ev = E.session_events || [];
  return `<h1>6 · Reviewable, and repeatable</h1>
  <p class="lede">Everything a human reviewer needs is in one pull request, and the process is saved as Playbooks so Devin can do it again — or keep maintaining the code.</p>
  ${D?.session ? `<h2 id="devintop">Your live Devin run</h2><p>The run started with “Start Devin live” on the first page. Open the session to watch Devin work, or follow its pull request once it opens one.</p><div id="devinslot">${devinCard()}</div>` : ""}
  ${E.status_problem ? `<div class="err">demo/status.json ${esc(E.status_problem)}</div>` : `<p class="small muted">PR / Playbook status recorded ${esc(st.recorded_at)} — click through for the current state.</p>`}
  <h2>Pull requests</h2><div class="grid g2">${(st.pull_requests || []).map(p => `<div class="card"><h3><a href="${esc(p.url)}" target="_blank">#${p.number}</a> ${badge(p.state)}</h3>${esc(p.title)}<div class="small muted">${esc(p.role)}</div>${p.commits_url ? `<a class="small" href="${esc(p.commits_url)}" target="_blank">See the commit-by-commit order</a>` : ""}</div>`).join("")}</div>
  <h2>Commit history (this checkout)</h2><table><tbody>${E.git.commits.slice(0, 10).map(c => `<tr><td>${commit(c.sha)}</td><td class="small">${esc(c.date)}</td><td>${esc(c.subject)}</td></tr>`).join("")}</tbody></table>
  <h2>Playbooks — Devin can repeat this</h2><div class="grid g2">${(st.playbooks || []).map(p => `<div class="card"><h3><a href="${esc(p.url)}" target="_blank">${esc(p.title)}</a></h3><div class="small"><code>${esc(p.id)}</code> · starts from <code>${esc(p.start_ref)}</code> · source ${raw(p.source)}</div>
   <p>Rehearsal run: ${badge(p.fresh_run?.status || "UNKNOWN")} <a href="${esc(p.fresh_run?.session || "#")}" target="_blank">session</a>${p.fresh_run?.pr ? ` · <a href="${esc(p.fresh_run.pr)}" target="_blank">PR</a>` : ""}</p></div>`).join("")}</div>
  ${D?.session ? "" : `<h2>Watch Devin do it again, live</h2><div id="devinslot">${devinCard()}</div>`}
  <h2>Assumptions &amp; limits</h2><ul><li>Synthetic, educational module based on public CMS rules — not CMS production code, not complete Medicare policy.</li><li>Parity is proven for the tested batches (curated ${E.saved.comparisons.curated?.records?.python ?? "?"}, synthetic ${(E.saved.comparisons.synthetic?.records?.python ?? 0).toLocaleString()}, edge ${E.saved.comparisons.edge?.records?.python ?? "?"}, fatal paths) — not for every possible input.</li><li>The CWF step is three illustrative pre-payment checks on synthetic reference data, not a copy of CWF.</li><li>Both versions stop on lines over 4,096 bytes or more than 10,000 claims, deliberately identical.</li><li>No performance or cost claims.</li></ul>
  ${(E.expectations?.interface_assumptions) ? `<details><summary>Interface assumptions Devin recorded</summary><pre>${esc(JSON.stringify(E.expectations.interface_assumptions, null, 1))}</pre></details>` : ""}
  ${await mdBlock("docs/migration/02-rule-map.md", "Rule map: policy → COBOL → test → Python")}
  <details><summary>Human interventions and review time (${ev.length} events)</summary><table><thead><tr><th>When</th><th>Who</th><th>What</th><th>Human time</th></tr></thead><tbody>${ev.map(e => `<tr><td class="small">${esc(e.timestamp_utc)}</td><td>${esc(e.actor)}</td><td>${esc(e.event)}</td><td>${esc(e.human_intervention_seconds)}</td></tr>`).join("")}</tbody></table><p class="small muted">UNKNOWN means not measured — it is not zero. No efficiency claim is made.</p></details>`;
};

const manualPrompt = () => `Run this on wstomber/devinexecdemo starting from branch ${D?.start_branch || "the pinned starter branch"}.`;
const manualSteps = (MANUAL = manualPrompt()) => `<ol><li>Open <a href="https://app.devin.ai" target="_blank">app.devin.ai</a> and start a new session.</li><li>In the Playbook picker, choose <b>MSP COBOL to Python with evidence</b>.</li>
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
  if (!s) return `<div class="card">${intro}${err}<p>${startBtn("▶ Start Devin live")}</p><p class="small muted">A full run takes about 15–25 minutes and ends with a pull request into the starter branch.</p></div>`;
  const [label, cls] = devinLabel(s), started = s.started_at ? new Date(s.started_at).toLocaleTimeString([], {hour: "numeric", minute: "2-digit"}) : "";
  const prs = (s.pull_requests || []).map(p => `<a href="${esc(p.url)}" target="_blank">Pull request ${esc(p.url.split("/").pop())}</a> ${badge((p.state || "open").toUpperCase())}`).join(" · ");
  return `<div class="card">${intro}${err}
   <p>${LIVE_DEVIN} ${badge(cls, label)} <span class="small">started ${esc(started)}</span></p>
   <p><a class="btn primary" href="${esc(s.url)}" target="_blank">Open Devin's session ↗</a> <button class="btn" data-devin-reset="1" title="${devinActive(s) ? "Stops this Devin session and clears the card" : "Clears the card"}">Reset</button> ${prs ? `&nbsp; ${prs}` : devinActive(s) ? `<span class="small muted">&nbsp; Its pull request appears here once Devin opens it.</span>` : `<span class="small muted">&nbsp; No pull request was opened.</span>`}</p>
   ${s.problem ? `<p class="small muted">Last status check: ${esc(s.problem)}</p>` : ""}
   ${s.status === "suspended" ? `<p class="small muted">Devin paused this session. Open it and send a message to resume it.</p>` : devinActive(s) ? `<p class="small muted">Status updates every 10 seconds.</p>` : `<p>${startBtn("▶ Start another live run")}</p>`}</div>`;
}
let devinGen = 0;
function paintDevin() {
  if (route === "review" && !!$("#devintop") !== !!D?.session) return render();
  const slot = $("#devinslot"); if (slot) slot.innerHTML = devinCard();
}
async function refreshDevin() {
  if (!$("#devinslot")) { clearInterval(dpoll); dpoll = null; return; }
  const gen = devinGen; let d;
  try { const r = await fetch("/api/devin-run"); d = await r.json(); } catch (e) { d = {configured: true, error: "Could not reach this app's server."}; }
  if (gen !== devinGen) return;
  D = d;
  paintDevin();
  if (!devinActive(D?.session)) { clearInterval(dpoll); dpoll = null; } else if (!dpoll) dpoll = setInterval(refreshDevin, 10000);
}

function liveCtl() {
  const L = E.live, running = E.live_running || L?.status === "RUNNING";
  return `<button class="btn primary" id="runlive" ${running ? "disabled" : ""}>${running ? "Running COBOL and Python…" : "▶ Run COBOL vs Python now"}</button>${L && !running ? ' <button class="btn" id="resetlive" title="Clear live results; saved rehearsal evidence is untouched">Reset</button>' : ""}`;
}
function renderLive() {
  const L = E.live, running = E.live_running || L?.status === "RUNNING";
  $("#live").innerHTML = `${L ? `${LIVE} ${badge(L.status)} <span>${esc(L.started_at || "")}</span> <a href="#" style="color:#cfe0ff" data-steps="1">steps</a>` : `<span class="badge NOT_RUN">NO LIVE RUN YET</span>`}${L?.bug ? ' <span class="badge FAILED">PLANTED BUG</span>' : ""}`;
  const ctl = $("#livectl"); if (ctl) ctl.innerHTML = liveCtl();
  if (running && !poll) poll = setInterval(refresh, 1500);
  if (!running && poll) { clearInterval(poll); poll = null; }
}
function showSteps() {
  const L = E.live; if (!L) return;
  $("#drawer").hidden = false;
  $("#drawer").innerHTML = `<button class="btn" data-close="1" style="float:right">Close</button><h2>Live run ${esc(L.id)}</h2>${L.bug ? `<div class="err">Planted bug, on purpose: ${esc(L.bug.title)}. These checks run against a broken copy of the Python.</div>` : ""}
   <p>${LIVE} ${badge(L.status)}<br><span class="small">Started ${esc(L.started_at)} · finished ${esc(L.finished_at || "—")} · commit ${commit(L.commit)}${L.dirty ? " (uncommitted changes present)" : ""}<br>Folder <code>${esc(L.folder)}</code></span></p>
   <ul class="steps">${(L.steps || []).map(s => `<li>${badge(s.status)}<span><b>${esc(s.title)}</b><br><code class="small">${esc(s.command)}</code><br><span class="small">exit ${s.exit_code ?? "—"} · ${raw(s.log, "full output")}</span></span></li>`).join("")}</ul>
   <p class="small muted">If a step fails, the saved rehearsal evidence stays on screen, labeled SAVED REHEARSAL.</p>`;
}
function showCase(k) {
  const c = E.expectations.cases[k]; $("#drawer").hidden = false;
  $("#drawer").innerHTML = `<button class="btn" data-close="1" style="float:right">Close</button><h2><code>${esc(c.claim_id)}</code></h2><p>${esc(c.category)} · ${esc(c.source || "")}</p>
   <h3>Input</h3><pre>${esc(JSON.stringify(c.input, null, 1))}</pre><h3>Hand-derived arithmetic</h3><p>${esc(c.arithmetic || "—")}</p>
   ${c.assumptions ? `<h3>Assumptions</h3><p>${esc(c.assumptions)}</p>` : ""}<h3>Expected</h3><p>${esc(c.expected.status)} · ${money(c.expected.payment_cents)} calculated · <code>${esc(c.expected.reason)}</code><br>CWF ${cwfBadge(c.expected.cwf, c.expected.cwf_reason)} · ${money(c.expected.released_cents)} released</p>`;
}
function showRow(no) {
  const c = cmpSources().find(s => s[0] === cmpKey)[1], r = c.rows.find(x => x[0] === no); if (!r) return;
  const ex = E.expectations?.cases?.find(x => x.claim_id === r[1]);
  $("#drawer").hidden = false;
  $("#drawer").innerHTML = `<button class="btn" data-close="1" style="float:right">Close</button><h2>Record ${r[0]} · <code>${esc(r[1])}</code></h2><p>${badge(r[8])} ${c.kind === "live" ? LIVE : SAVED}</p>
   <table><thead><tr><th></th><th>COBOL (original)</th><th>Python (new)</th></tr></thead><tbody>
   <tr><td>Status</td><td>${esc(r[2] ?? "—")}</td><td>${esc(r[3] ?? "—")}</td></tr><tr><td>Payment</td><td class="num">${money(r[4])}<br><span class="small">${cents(r[4])}</span></td><td class="num">${money(r[5])}<br><span class="small">${cents(r[5])}</span></td></tr>
   <tr><td>Reason</td><td><code>${esc(r[6] ?? "—")}</code></td><td><code>${esc(r[7] ?? "—")}</code></td></tr>
   <tr><td>CWF decision</td><td>${cwfBadge(r[10], r[12])}</td><td>${cwfBadge(r[11], r[13])}</td></tr>
   <tr><td>Released</td><td class="num">${money(r[14])}<br><span class="small">${cents(r[14])}</span></td><td class="num">${money(r[15])}<br><span class="small">${cents(r[15])}</span></td></tr></tbody></table>
   ${ex ? `<h3>Independent expectation</h3><p>${esc(ex.expected.status)} · ${money(ex.expected.payment_cents)} · <code>${esc(ex.expected.reason)}</code> · CWF ${esc(ex.expected.cwf)} · ${money(ex.expected.released_cents)} released ${badge(ex.expected.payment_cents === r[5] && ex.expected.status === r[3] && ex.expected.cwf === r[11] && ex.expected.released_cents === r[15] ? "MATCH" : "MISMATCH")}</p><p class="small">${esc(ex.arithmetic || "")}</p>` : ""}`;
}

let renderGen = 0;
async function render() {
  const gen = ++renderGen;
  route = (location.hash.slice(1) || "overview"); if (!R[route]) route = "overview";
  $("#nav").innerHTML = VIEWS.map(([k, l]) => `<a href="#${k}" class="${k === route ? "on" : ""}">${l}</a>`).join("");
  const html = await R[route]();
  if (gen !== renderGen) return;
  const vid = $("#view video"), vidOpen = vid?.closest("details")?.open;
  $("#view").innerHTML = html;
  const nv = $("#view video");
  if (vid && nv && vid.getAttribute("src") === nv.getAttribute("src")) { nv.replaceWith(vid); if (vidOpen) vid.closest("details").open = true; }
  const idx = VIEWS.findIndex(v => v[0] === route);
  $("#foot").innerHTML = `<span>${idx > 0 ? `<a class="btn" href="#${VIEWS[idx - 1][0]}">← ${esc(VIEWS[idx - 1][1])}</a>` : ""}</span>
   <span class="muted">Checkout ${commit(E.git.head)} on <code>${esc(E.git.branch)}</code> · evidence read ${esc(E.generated_at)}</span>
   <span>${idx < VIEWS.length - 1 ? `<a class="btn primary" href="#${VIEWS[idx + 1][0]}">${esc(VIEWS[idx + 1][1])} →</a>` : ""}</span>`;
  renderLive();
  if ($("#devinslot")) refreshDevin();
  if (jumpResults && route === "compare") { jumpResults = false; if (!E.live?.bug) $("#results")?.scrollIntoView(); }
}
async function load() {
  const r = await fetch("/api/evidence"); if (!r.ok) throw new Error("evidence " + r.status); E = await r.json();
}
async function refresh() { const wasRunning = E?.live_running; await load(); renderLive(); if (!$("#drawer").hidden && $("#drawer h2")?.textContent.startsWith("Live run")) showSteps();
  if (wasRunning && !E.live_running) openFresh(); }
async function startRun(t, bug) {
  t.disabled = true; t.textContent = "Starting…";
  const r = await fetch("/api/live-run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(bug ? {bug} : {})});
  await load(); if (r.ok && !E.live_running) return openFresh(); renderLive(); showSteps();
}
let jumpResults = false;
function openFresh() { jumpResults = true; $("#drawer").hidden = true; cmpKey = curatedKey(); cmpQuery = ""; cmpFilter = E.live?.bug ? "mismatch" : "all"; cmpPage = 0;
  if (location.hash === "#compare") render(); else location.hash = "#compare"; }

document.addEventListener("click", async ev => {
  const t = ev.target.closest("[data-copy],[data-cmp],[data-f],[data-pg],[data-row],[data-case],[data-close],[data-steps],[data-jump],[data-goto-ex3],[data-devin-start],[data-devin-reset],[data-bug],[data-undo],#runlive,#resetlive");
  if (!t) return;
  if (t.dataset.copy) { navigator.clipboard?.writeText(t.dataset.copy); t.textContent = "Copied"; return; }
  if (t.dataset.devinReset) { if (devinActive(D?.session) && !confirm("Stop this Devin session and clear the card?")) return; devinGen++; t.disabled = true; try { const r = await fetch("/api/devin-reset", {method: "POST"}); const d = await r.json(); devinGen++; D = d; } catch (e) { D = {...(D || {}), error: "Could not reach this app's server."}; } paintDevin(); return; }
  if (t.dataset.devinStart) { devinGen++; t.disabled = true; t.textContent = "Starting Devin…"; try { const r = await fetch("/api/devin-run", {method: "POST"}); const d = await r.json(); devinGen++; D = d; } catch (e) { D = {...(D || {}), error: "Could not reach this app's server."}; } paintDevin(); if (devinActive(D?.session) && !dpoll) dpoll = setInterval(refreshDevin, 10000); return; }
  if (t.id === "runlive" || t.dataset.undo) return startRun(t);
  if (t.dataset.bug) return startRun(t, t.dataset.bug);
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
document.addEventListener("keydown", ev => { if (["INPUT", "TEXTAREA", "SELECT", "VIDEO"].includes(ev.target.tagName)) return; const idx = VIEWS.findIndex(v => v[0] === route);
  if (ev.key === "ArrowRight" && idx < VIEWS.length - 1) location.hash = VIEWS[idx + 1][0]; if (ev.key === "ArrowLeft" && idx > 0) location.hash = VIEWS[idx - 1][0];
  if (ev.key === "Escape") $("#drawer").hidden = true; });
window.addEventListener("hashchange", () => { $("#drawer").hidden = true; render(); window.scrollTo(0, 0); });
load().then(render).catch(e => { $("#view").innerHTML = `<div class="err">Could not load evidence: ${esc(e.message)}. Is <code>make demo</code> running?</div>`; });
