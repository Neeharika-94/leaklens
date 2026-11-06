const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const inr = x => "₹" + Number(x || 0).toLocaleString("en-IN", {maximumFractionDigits: 0});
let tk = localStorage.getItem("ll_tk"), code = null, link = null;
function toast(t, bad) { const e = $("#toast"); e.textContent = t; e.className = "show" + (bad ? " bad" : ""); setTimeout(() => e.className = "", 2800); }
async function api(p, m = "GET", b) {
  const r = await fetch(p, {method: m, headers: {"Content-Type": "application/json", Authorization: "Bearer " + (tk || "")}, body: b ? JSON.stringify(b) : undefined});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const d = j.detail; toast(typeof d === "string" ? d : "Request failed", 1); throw new Error("api"); }
  return j;
}
function route() {
  const h = location.hash || "#/", nav = $("#nav");
  if (h.startsWith("#/report/")) { nav.innerHTML = ""; return report(h.split("/")[2]); }
  if (!tk) { nav.innerHTML = ""; return login(); }
  nav.innerHTML = '<a href="#/audit">Audit</a><a href="#/calc">Calculator</a><a href="#/connect">Claude / MCP</a><a href="#" id="out">Logout</a>';
  $("#out").onclick = () => { localStorage.removeItem("ll_tk"); tk = null; };
  ({"#/calc": calc, "#/connect": connect}[h] || audit)();
}
addEventListener("hashchange", route); route();

function login() {
  $("#main").innerHTML = `<div class="card" style="max-width:420px;margin:auto"><h2>Accountant login</h2>
  <div class="demo">Demo account: <b>meera@leaklens.demo</b> / <b>Meera@12345</b></div><br>
  <label>Email<input id="em" value="meera@leaklens.demo"></label><label>Password<input id="pw" type="password" value="Meera@12345"></label><button id="go">Log in</button></div>`;
  $("#go").onclick = async () => { const r = await api("/auth/login", "POST", {email: $("#em").value, password: $("#pw").value});
    tk = r.token; localStorage.setItem("ll_tk", tk); location.hash = "#/audit"; route(); };
}
const badge = t => `<span class="tag">${esc(t)}</span>`;
async function audit() {
  const list = await api("/audits"); code = code || list[0].code;
  const d = await api("/audits/" + code), s = d.summary, a = list.find(x => x.code === code);
  const rows = d.findings.map(f => `<tr><td><b>${esc(f.merchant)}</b><br><small>${esc(f.description)}</small><br><small><i>${esc(f.evidence.join("; "))}</i></small></td><td>${esc(f.category)}</td>
   <td>${inr(f.annual_expense)}</td><td>${inr(f.potential)}</td><td>${inr(f.approved)}</td><td>${inr(f.realised)}</td><td>${badge(f.review_status)}<br>${badge(f.action_status)}</td>
   <td><button data-a="ok" data-id="${f.id}">Approve</button><button class="bad" data-a="no" data-id="${f.id}">Reject</button><button class="sec" data-a="edit" data-id="${f.id}" data-c='${esc(JSON.stringify(f))}'>Edit</button><button class="sec" data-a="del" data-id="${f.id}">Delete</button></td></tr>`).join("");
  $("#main").innerHTML = `<h2>${esc(a.customer)} · ${esc(a.code)}</h2><p>${esc(a.period)} · Status: ${badge(s.status)}</p>
  <div class="grid"><div class="card kpi">Findings<b>${s.findings}</b></div><div class="card kpi">Potential annual savings<b>${inr(s.potential_annual_savings)}</b></div>
  <div class="card kpi">Approved<b>${inr(s.approved_savings)}</b></div><div class="card kpi">Realised<b>${inr(s.realised_savings)}</b></div><div class="card kpi">Realisation rate<b>${s.realisation_rate_pct}%</b></div></div><br>
  <button data-a="sim">▶ Simulate Claude submission (DEMO)</button><button class="sec" data-a="add">+ Add finding</button><button data-a="pub">Publish report</button>
  ${link ? `<p class="demo">Founder link (share with Arjun): <a href="${link}" target="_blank">${location.origin + link}</a></p>` : ""}
  <div class="scroll"><table><tr><th>Finding</th><th>Category</th><th>Annual expense</th><th>Potential</th><th>Approved</th><th>Realised</th><th>Status</th><th>Actions</th></tr>${rows || '<tr><td colspan="8">No findings yet. Ask Claude through MCP, or click "Simulate Claude".</td></tr>'}</table></div>
  <p><small>Savings are potential until the accountant approves, and realised only when the founder marks an approved finding as fixed. Demo data is illustrative.</small></p>`;
  $("#main").onclick = async e => { const b = e.target.closest("[data-a]"); if (!b) return; const id = b.dataset.id, k = b.dataset.a;
    try {
      if (k === "ok") await api(`/findings/${id}/review/Approved`, "POST");
      if (k === "no") await api(`/findings/${id}/review/Rejected`, "POST");
      if (k === "del" && confirm("Delete this finding? (history is kept)")) await api("/findings/" + id, "DELETE");
      if (k === "edit") { const f = JSON.parse(b.dataset.c), v = prompt("Edit calculation inputs (JSON). This recalculates savings:", JSON.stringify(f.calc_inputs || {}));
        if (v) { const o = JSON.parse(v); const pr = prompt("Priority (High/Medium/Low):", f.priority) || f.priority; await api("/findings/" + id, "PATCH", {calc_inputs: o, priority: pr}); } else return; }
      if (k === "sim") { await api("/demo/simulate/" + code, "POST"); toast("Demo findings received (simulated, not a live Claude call)"); }
      if (k === "add") { const m = prompt("Merchant"), amt = prompt("Monthly amount (INR)"), c = prompt("Category: duplicate_subscription / unused_subscription / fx_markup / idle_card / renewal / recurring_expense", "recurring_expense");
        if (m && amt && c) await api(`/audits/${code}/findings`, "POST", {merchant: m, monthly_amount: amt, category: c, currency: "INR", description: "Added manually by accountant"}); else return; }
      if (k === "pub") { const r = await api(`/audits/${code}/publish`, "POST"); link = "/app.html#/report/" + r.url.split("/").pop(); toast("Report published"); }
    } catch (x) { if (x.message !== "api") toast("Invalid input", 1); }
    audit(); };
}
const SAMPLES = {duplicate_subscription: {monthly_cost: 2000, subscriptions: 3, avoidable_monthly_amount: 1500}, unused_subscription: {monthly_fee: 4500, avoidable_months: 9},
  fx_markup: {monthly_foreign_spend: 120000, markup_pct: 3.5, alternative_markup_pct: 1, months: 12}, idle_card: {monthly_fee: 500, avoidable_monthly_fee: 500},
  recurring_expense: {amount: 10000, frequency: "quarterly"}, renewal: {renewal_amount: 120000, frequency: "annual", negotiation_or_cancellation_amount: 18000}, custom: {template: "percent_of", a: 100000, b: 5}};
function calc() {
  $("#main").innerHTML = `<h2>Super Calculator</h2><p>Deterministic formulas (Decimal arithmetic, no AI). Same inputs always give the same result.</p><div class="split"><div>
  <select id="cat">${Object.keys(SAMPLES).map(k => `<option>${k}</option>`).join("")}</select><textarea id="inp" rows="8"></textarea><button id="run">Calculate</button></div><div class="card" id="res">Result appears here</div></div>`;
  const fill = () => $("#inp").value = JSON.stringify(SAMPLES[$("#cat").value], null, 2); $("#cat").onchange = fill; fill();
  $("#run").onclick = async () => { try { const r = await api("/calc", "POST", {category: $("#cat").value, inputs: JSON.parse($("#inp").value)});
    $("#res").innerHTML = `<b>Formula:</b> ${esc(r.formula)}<br><b>Version:</b> ${r.version}<pre>${esc(JSON.stringify(r.outputs, null, 2))}</pre><b>Potential annual saving: ${inr(r.potential)}</b>`; } catch (e) {} };
}
async function connect() {
  const i = await api("/demo/info");
  $("#main").innerHTML = `<h2>Connect Claude to LeakLens (MCP)</h2><p>Claude reads the statement and analyses it. LeakLens only receives structured findings through these tools.</p>
  <div class="card"><b>Your MCP URL</b> (contains a secret token, treat it like a password):<br><code>${esc(i.mcp_url)}</code></div><br>
  <h3>Steps</h3><ol><li>In Claude: Settings → Connectors → Add custom connector.</li><li>Name it <b>LeakLens</b>, paste the URL above, save.</li>
  <li>Ask: <i>"Run a spend leak audit for Northwind using this statement and save the findings in LeakLens under audit LL-NW-2026-001."</i></li><li>Refresh the Audit page to see the findings arrive.</li></ol>
  <p>No connector support on your plan? Use Claude Desktop config: <code>{"mcpServers":{"leaklens":{"command":"npx","args":["mcp-remote","${esc(i.mcp_url)}"]}}}</code></p>
  <p><b>Tools:</b> get_customers, create_audit, get_audit, add_finding, add_findings_bulk, update_finding, delete_finding, calculate_savings, get_audit_summary, publish_report, get_audit_status, list_findings.</p>
  <p class="demo">Production would use OAuth-scoped sessions instead of a token in the URL. The "Simulate Claude" button on the Audit page is a labelled demo and is not a real Claude connection.</p>`;
}
async function report(t) {
  let r; try { r = await api("/public/report/" + t); } catch (e) { $("#main").innerHTML = "<p>This link is invalid, revoked or expired.</p>"; return; }
  const s = r.summary, pct = +s.approved_savings ? Math.round(s.realised_savings / s.approved_savings * 100) : 0;
  const rows = r.findings.map(f => `<div class="card" style="margin:10px 0"><b>${esc(f.merchant)}</b> ${badge(f.action_status)} ${f.owner ? "· Owner: " + esc(f.owner) : ""}
   <p>${esc(f.description)}</p><p><b>Recommendation:</b> ${esc(f.approved_recommendation || f.recommendation)}</p><p>Annual saving (approved): <b>${inr(f.approved)}</b> · Realised: <b>${inr(f.realised)}</b></p>
   ${(r.comments[f.id] || []).map(c => `<p><small>💬 <b>${esc(c.author)}</b>: ${esc(c.body)}</small></p>`).join("")}
   <button data-a="In Progress" data-id="${f.id}">Accept / start</button><button data-a="Fixed" data-id="${f.id}">Mark fixed</button><button class="bad" data-a="Dismissed" data-id="${f.id}">Dismiss</button>
   <button class="sec" data-a="owner" data-id="${f.id}">Assign owner</button><button class="sec" data-a="comment" data-id="${f.id}">Comment</button></div>`).join("");
  $("#main").innerHTML = `<p><small>Prepared by ${esc(r.firm)}</small></p><h2>${esc(r.audit.title)}</h2><p>${esc(r.audit.period)}</p>
  <div class="grid"><div class="card kpi">Approved annual savings<b>${inr(s.approved_savings)}</b></div><div class="card kpi">Realised so far<b>${inr(s.realised_savings)}</b></div><div class="card kpi">Still open<b>${inr(s.approved_savings - s.realised_savings)}</b></div></div>
  <p>Progress ${pct}%</p><div class="bar"><i style="width:${pct}%"></i></div>${rows || "<p>No approved findings yet.</p>"}<p class="demo">Illustrative demo data. Dismissed findings are excluded from savings.</p>`;
  $("#main").onclick = async e => { const b = e.target.closest("[data-a]"); if (!b) return; const k = b.dataset.a, body = {author: "Arjun (Founder)"};
    if (k === "owner") { body.owner = prompt("Assign to (employee name):"); if (!body.owner) return; }
    else if (k === "comment") { body.comment = prompt("Your comment:"); if (!body.comment) return; } else body.status = k;
    try { await api(`/public/report/${t}/findings/${b.dataset.id}`, "POST", body); } catch (x) {} report(t); };
}
