// ===== DOM refs =====
const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const streamEl = document.getElementById("debate-stream");
const tbodyEl = document.getElementById("dec-tbody");
const paginationEl = document.getElementById("pagination");

let sessionId = null;
let currentPage = 1;
let currentTrigger = "";
const PAGE_SIZE = 20;

// ===== Helpers =====
const VIEW_CLASS = {"多": "long", "空": "short", "观望": "wait"};
const MATE_DISPLAY = {
  "trend_multi_tf": "周期师", "funding_rate": "费率官", "smart_money": "大户雷达",
  "long_short_compare": "多空裁", "volatility": "波动官", "experience": "复盘官",
  "red_team": "投资风险师", "macro_sentiment": "宏观官", "liquidity": "水位官",
  "position_mgr": "仓位管家", "decision_lead": "决策长", "smc_structure": "结构师",
};
const TRIGGER_LABEL = { scan: "扫描", chat: "对话", tracking: "跟踪" };
const PREFILTER_DIM_LABEL = {
  funding:        { text: '费率',   color: '#e74c3c' },
  position:       { text: '多空',   color: '#f39c12' },
  price:          { text: '动量',   color: '#3498db' },
  oi_growth:      { text: 'OI增长', color: '#9b59b6' },
  volume_anomaly: { text: '量异动', color: '#27ae60' },
};
function mateName(id) { return MATE_DISPLAY[id] || id; }
function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// ===== Render helpers (debate) =====
function renderMateCard(stage, payload) {
  const div = document.createElement("div");
  div.className = "mate-card";
  const view = payload.view ?? "?";
  const conf = payload.confidence ?? "?";
  const cls = VIEW_CLASS[view] || "wait";
  const evidence = payload.evidence_lead ?? "(无)";
  const roundLabel = payload.round ? `R${payload.round}` : "";
  const mateLabel = mateName(payload.mate || "?");
  const head = document.createElement("div");
  head.className = "mate-head";
  head.innerHTML = `<span class="mate-round">${roundLabel}</span>
    <span class="mate-name">${escapeHtml(mateLabel)}</span>
    <span class="mate-view ${cls}">${escapeHtml(view)}</span>
    <span class="mate-conf">${escapeHtml(String(conf))}</span>
    <span class="mate-arrow">▸</span>`;
  const evi = document.createElement("div");
  evi.className = "mate-evi"; evi.textContent = evidence;
  const detail = document.createElement("pre");
  detail.className = "mate-detail"; detail.style.display = "none";
  detail.textContent = JSON.stringify(payload.result || payload, null, 2);
  head.addEventListener("click", () => {
    const open = detail.style.display === "none";
    detail.style.display = open ? "block" : "none";
    head.querySelector(".mate-arrow").textContent = open ? "▾" : "▸";
  });
  div.appendChild(head); div.appendChild(evi); div.appendChild(detail);
  return div;
}

function renderPhaseHeader(label, sub) {
  const div = document.createElement("div");
  div.className = "phase-header";
  div.innerHTML = `<span>${escapeHtml(label)}</span>${sub ? ` <span style="font-weight:normal;color:#94a3b8">${escapeHtml(sub)}</span>` : ""}`;
  return div;
}

function renderRebuttalCard(payload) {
  const rebuttal = payload.rebuttal || {};
  const div = document.createElement("div"); div.className = "mate-card rebuttal";
  const head = document.createElement("div"); head.className = "mate-head";
  head.innerHTML = `<span class="mate-round">R2</span><span class="mate-name">投资风险师 反驳</span><span class="mate-view short">vs ${escapeHtml(payload.majority || "?")}</span><span class="mate-arrow">▸</span>`;
  const summary = (rebuttal.extra && rebuttal.extra.rebuttal) || rebuttal.evidence?.[0] || "(无)";
  const evi = document.createElement("div"); evi.className = "mate-evi";
  evi.textContent = typeof summary === "string" ? summary : JSON.stringify(summary);
  const detail = document.createElement("pre"); detail.className = "mate-detail"; detail.style.display = "none";
  detail.textContent = JSON.stringify(rebuttal, null, 2);
  head.addEventListener("click", () => { const o = detail.style.display === "none"; detail.style.display = o ? "block" : "none"; head.querySelector(".mate-arrow").textContent = o ? "▾" : "▸"; });
  div.appendChild(head); div.appendChild(evi); div.appendChild(detail);
  return div;
}

// ===== Chat panel =====
function appendMsg(role, content) {
  const div = document.createElement("div"); div.className = "msg " + role;
  if (typeof content === "object") { div.appendChild(renderCard(content)); } else { div.textContent = content; }
  messagesEl.appendChild(div); messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderCard(card) {
  const root = document.createElement("div"); root.className = "card";
  const dirClass = card.direction === "多" ? "long" : card.direction === "空" ? "short" : "wait";
  root.innerHTML = `<div class="dir ${dirClass}">${card.symbol || ""} ${card.direction || ""} (信心 ${card.confidence ?? "-"})</div>
    <div><b>入场:</b> ${card.entry_price ?? "-"} (zone: ${JSON.stringify(card.entry_zone || [])})</div>
    <div><b>止损/止盈:</b> ${card.stop_loss ?? "-"} / ${card.take_profit ?? "-"} (RR ${card.risk_reward_ratio ?? "-"})</div>
    <div><b>仓位:</b> ${card.position_size_pct ?? "-"}%</div>
    <div><b>依据:</b><ul>${(card.key_evidence || []).map(e => `<li>${e}</li>`).join("")}</ul></div>
    <div><b>风险:</b><ul>${(card.key_risks || []).map(r => `<li>${r}</li>`).join("")}</ul></div>
    <div><b>计划:</b> ${card.execution_plan || ""}</div>`;
  return root;
}

function appendStreamEvent(evt) {
  const stage = evt.stage; const payload = evt.payload || {};
  if (stage === "intent") { streamEl.appendChild(renderPhaseHeader("意图", `${payload.intent || ""} ${payload.symbol || ""}`)); }
  else if (stage === "data_packing") { streamEl.appendChild(renderPhaseHeader("拉数据", payload.symbol || "")); }
  else if (stage === "orchestrator_start") { streamEl.appendChild(renderPhaseHeader("圆桌开始", `${payload.symbol} mode=${payload.mode}`)); }
  else if (stage === "round_1_start") { streamEl.appendChild(renderPhaseHeader("第 1 轮", (payload.mates || []).map(mateName).join(", "))); }
  else if (stage === "mate_done") { streamEl.appendChild(renderMateCard(stage, payload)); }
  else if (stage === "rebuttal_start") { streamEl.appendChild(renderPhaseHeader("第 2 轮 反驳", `多数派 = ${payload.majority || "?"}`)); }
  else if (stage === "rebuttal_done") { streamEl.appendChild(renderRebuttalCard(payload)); }
  else if (stage === "response_done") { streamEl.appendChild(renderMateCard("mate_done", { mate: payload.mate, round: 2, view: payload.result?.updated_view, confidence: payload.result?.updated_confidence, evidence_lead: payload.result?.note, result: payload.result })); }
  else if (stage === "round_3_start") { streamEl.appendChild(renderPhaseHeader("第 3 轮 综合", `多数派 = ${payload.majority || "?"}`)); }
  else if (stage === "done" || stage === "decision_card") { streamEl.appendChild(renderPhaseHeader("决策完成", "")); }
  streamEl.scrollTop = streamEl.scrollHeight;
}

async function send(text) {
  appendMsg("user", text); openDebateDrawer();
  streamEl.innerHTML = "";
  const r = await fetch("/api/chat", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: sessionId, text}) });
  const data = await r.json(); sessionId = data.session_id;
  const es = new EventSource(`/api/chat/stream/${sessionId}`);
  es.onmessage = (e) => {
    const evt = JSON.parse(e.data); appendStreamEvent(evt);
    if (evt.stage === "done") {
      const result = evt.payload;
      if (result.type === "decision_card") { appendMsg("assistant", result.card); }
      else if (result.type === "follow_up_answer") { appendMsg("assistant", result.message); }
      else { appendMsg("assistant", result.message || JSON.stringify(result)); }
      es.close(); loadDecisions();
    }
    if (evt.stage === "error") { appendMsg("assistant", "错误: " + JSON.stringify(evt.payload)); es.close(); }
  };
}

formEl.addEventListener("submit", (e) => { e.preventDefault(); const t = inputEl.value.trim(); if (!t) return; inputEl.value = ""; send(t); });

// ===== PLACEHOLDER_DECISIONS =====

// ===== Decisions Table =====
const STATUS_DESC = {
  open: "进行中 — 尚未触发止损或止盈,持续监控中",
  win: "盈利 — 价格先触达止盈位,决策成功",
  loss: "亏损 — 价格先触达止损位,决策失败",
  expired: "过期 — 7天内未触发止损/止盈,按最终价格结算",
};

function getSearchParams() {
  const params = new URLSearchParams();
  params.set("page", currentPage);
  params.set("page_size", PAGE_SIZE);
  if (currentTrigger) params.set("trigger_mode", currentTrigger);
  const sym = document.getElementById("search-symbol").value.trim();
  if (sym) params.set("symbol", sym);
  const dir = document.getElementById("search-direction").value;
  if (dir) params.set("direction", dir);
  const conf = document.getElementById("search-confidence").value;
  if (conf) params.set("confidence_min", conf);
  const st = document.getElementById("search-status").value;
  if (st) params.set("status", st);
  const ds = document.getElementById("search-date-start").value;
  if (ds) params.set("date_start", ds);
  const de = document.getElementById("search-date-end").value;
  if (de) params.set("date_end", de);
  return params.toString();
}

async function loadDecisions() {
  const url = `/api/decisions?${getSearchParams()}`;
  const r = await fetch(url);
  const data = await r.json();
  renderTable(data.items || []);
  renderPagination(data);
}

function renderTable(items) {
  tbodyEl.innerHTML = items.map(d => {
    const card = d.card || {};
    const tm = d.trigger_mode || "";
    const time = (d.created_at || "").slice(0, 16).replace("T", " ");
    const dirCls = d.direction === "多" ? "dir-long" : d.direction === "空" ? "dir-short" : "dir-wait";
    const statusCls = d.status ? `status-${d.status}` : "";
    const triggerCls = tm ? `trigger-${tm}` : "";
    const debateBtn = d.audit_path ? `<button class="debate-btn" data-id="${d.decision_id}">辩论流</button>` : "-";

    // 详情列:默认显示摘要(入场价+止损止盈),点击展开完整
    const summary = d.direction === "观望" ? "观望,无操作建议"
      : `入${card.entry_price ?? "-"} 止损${card.stop_loss ?? "-"} 止盈${card.take_profit ?? "-"}`;
    const evidence = (card.key_evidence || []).map(e => `<li>${escapeHtml(e)}</li>`).join("");
    const risks = (card.key_risks || []).map(r => `<li>${escapeHtml(r)}</li>`).join("");
    const detailFull = `<b>入场:</b> ${card.entry_price ?? "-"} (zone: ${JSON.stringify(card.entry_zone || [])})<br>
      <b>止损:</b> ${card.stop_loss ?? "-"} | <b>止盈:</b> ${card.take_profit ?? "-"} | <b>RR:</b> ${card.risk_reward_ratio ?? "-"}<br>
      <b>仓位:</b> ${card.position_size_pct ?? "-"}%<br>
      ${evidence ? `<b>依据:</b><ul>${evidence}</ul>` : ""}
      ${risks ? `<b>风险:</b><ul>${risks}</ul>` : ""}
      ${card.execution_plan ? `<b>计划:</b> ${escapeHtml(card.execution_plan)}` : ""}`;

    // 状态 tooltip
    const tooltip = STATUS_DESC[d.status] || "";

    return `<tr>
      <td>${time}</td>
      <td><b>${d.symbol}</b></td>
      <td class="prefilter-cell">${(d.prefilter_tags || []).map(k => {
        const dim = PREFILTER_DIM_LABEL[k] || { text: k, color: '#94a3b8' };
        return `<span class="prefilter-badge" style="background:${dim.color}">${dim.text}</span>`;
      }).join("")}</td>
      <td><span class="trigger-badge ${triggerCls}">${TRIGGER_LABEL[tm] || tm}</span></td>
      <td class="${dirCls}">${d.direction || "-"}</td>
      <td class="detail-cell">
        <span class="detail-summary" data-did="${d.decision_id}">${escapeHtml(summary.slice(0, 20))}${summary.length > 20 ? "..." : ""}</span>
        <div class="detail-expand" id="detail-${d.decision_id}">${detailFull}</div>
      </td>
      <td>${d.confidence ?? "-"}</td>
      <td class="status-cell ${statusCls}">${d.status || "-"}<span class="status-tooltip">${escapeHtml(tooltip)}</span></td>
      <td>${debateBtn}</td>
    </tr>`;
  }).join("");

  // 辩论流按钮
  tbodyEl.querySelectorAll(".debate-btn").forEach(btn => {
    btn.addEventListener("click", () => showDebate(parseInt(btn.dataset.id, 10)));
  });
  // 详情展开/收起
  tbodyEl.querySelectorAll(".detail-summary").forEach(span => {
    span.addEventListener("click", () => {
      const did = span.dataset.did;
      const el = document.getElementById(`detail-${did}`);
      if (el) el.classList.toggle("show");
    });
  });
}

function renderPagination(data) {
  const { page, total_pages, total } = data;
  if (total_pages <= 1) { paginationEl.innerHTML = `<span class="page-info">共 ${total} 条</span>`; return; }
  let html = `<button ${page <= 1 ? "disabled" : ""} data-page="${page - 1}">上一页</button>`;
  html += `<span class="page-info">${page} / ${total_pages} (共 ${total})</span>`;
  html += `<button ${page >= total_pages ? "disabled" : ""} data-page="${page + 1}">下一页</button>`;
  paginationEl.innerHTML = html;
  paginationEl.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", () => { currentPage = parseInt(btn.dataset.page, 10); loadDecisions(); });
  });
}

// ===== Filter Tabs =====
document.querySelectorAll(".filter-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    currentTrigger = btn.dataset.trigger || "";
    currentPage = 1;
    document.querySelectorAll(".filter-tab").forEach(b => b.classList.toggle("active", b === btn));
    loadDecisions();
  });
});

// ===== Search =====
document.getElementById("search-btn").addEventListener("click", () => { currentPage = 1; loadDecisions(); });
document.getElementById("search-reset").addEventListener("click", () => {
  document.getElementById("search-symbol").value = "";
  document.getElementById("search-direction").value = "";
  document.getElementById("search-confidence").value = "";
  document.getElementById("search-status").value = "";
  document.getElementById("search-date-start").value = "";
  document.getElementById("search-date-end").value = "";
  currentTrigger = "";
  currentPage = 1;
  document.querySelectorAll(".filter-tab").forEach(b => b.classList.toggle("active", !b.dataset.trigger));
  loadDecisions();
});
// 回车触发搜索
document.querySelectorAll(".search-bar input").forEach(el => {
  el.addEventListener("keydown", (e) => { if (e.key === "Enter") { currentPage = 1; loadDecisions(); } });
});

// ===== Debate Drawer =====
function openDebateDrawer() {
  document.getElementById("debate-drawer").classList.add("open");
  document.getElementById("debate-overlay").classList.add("show");
}
function closeDebateDrawer() {
  document.getElementById("debate-drawer").classList.remove("open");
  document.getElementById("debate-overlay").classList.remove("show");
}
document.getElementById("debate-close").addEventListener("click", closeDebateDrawer);
document.getElementById("debate-overlay").addEventListener("click", closeDebateDrawer);

async function showDebate(decisionId) {
  openDebateDrawer();
  streamEl.innerHTML = "<p>加载中...</p>";
  document.getElementById("debate-title").textContent = `辩论流 #${decisionId}`;
  try {
    const r = await fetch(`/api/debate/${decisionId}`);
    if (!r.ok) { streamEl.innerHTML = "<p>加载失败</p>"; return; }
    const data = await r.json();
    if (!data.audit) { streamEl.innerHTML = "<p>此决策未保留 audit</p>"; return; }
    streamEl.innerHTML = "";
    const sym = data.decision?.symbol || "";
    streamEl.appendChild(renderPhaseHeader("回放", `${sym} #${decisionId}`));
    for (const round of (data.audit.rounds || [])) {
      streamEl.appendChild(renderPhaseHeader(`第 ${round.round} 轮`, `${round.calls.length} 次调用`));
      for (const call of round.calls) {
        let parsed = {}; try { parsed = JSON.parse(call.response); } catch (e) {}
        streamEl.appendChild(renderMateCard("mate_done", { mate: call.mate, round: round.round, view: parsed.view, confidence: parsed.confidence, evidence_lead: (parsed.evidence || [])[0], result: parsed }));
      }
    }
    streamEl.scrollTop = 0;
  } catch (e) { streamEl.innerHTML = `<p>异常: ${escapeHtml(e)}</p>`; }
}

// ===== Team Modal =====
async function loadTeam() {
  const r = await fetch("/api/team"); const list = await r.json();
  const el = document.getElementById("team-list");
  el.innerHTML = list.map(m => `<div class="team-card">
    <div class="tc-name">${escapeHtml(m.name)} (${m.mate})</div>
    <div class="tc-role">${escapeHtml(m.role || "")}</div>
    <div class="tc-focus"><b>关注:</b> ${escapeHtml(m.focus || "")}</div>
    <div class="tc-focus"><b>信号:</b> ${escapeHtml(m.signals || "")}</div>
    <div class="tc-focus"><b>输出:</b> ${escapeHtml(m.output || "")}</div>
    <div class="tc-focus" style="color:${m.enabled ? '#16a34a' : '#dc2626'}">${m.enabled ? "已启用" : "未启用"} | model: ${m.model || "-"}</div>
  </div>`).join("");
}
document.getElementById("team-btn").addEventListener("click", () => { document.getElementById("team-overlay").classList.add("show"); loadTeam(); });
document.getElementById("team-close").addEventListener("click", () => { document.getElementById("team-overlay").classList.remove("show"); });
document.getElementById("team-overlay").addEventListener("click", (e) => { if (e.target === e.currentTarget) document.getElementById("team-overlay").classList.remove("show"); });

// ===== Chat Panel Toggle =====
const chatPanel = document.getElementById("chat-panel");
const chatToggle = document.getElementById("chat-toggle");
document.getElementById("chat-panel-close").addEventListener("click", () => { chatPanel.classList.remove("open"); chatToggle.classList.remove("hidden"); });
chatToggle.addEventListener("click", () => { chatPanel.classList.add("open"); chatToggle.classList.add("hidden"); inputEl.focus(); });

// ===== Status Bar =====
async function loadStatus() {
  try {
    const r = await fetch("/api/status"); const s = await r.json();
    const dec = s.decisions || {};
    const badge = document.getElementById("sys-status");
    const ok = s.dependencies?.deepseek_key && s.dependencies?.binance_key;
    badge.textContent = ok ? "运行中" : "配置异常";
    badge.className = "status-badge" + (ok ? "" : " err");
    document.getElementById("topbar-stats").innerHTML = `
      <span class="stat">决策 <b>${dec.total || 0}</b></span>
      <span class="stat">进行中 <b>${dec.open || 0}</b></span>
      <span class="stat">24h 胜 <b>${dec.win_24h || 0}</b></span>
      <span class="stat">24h 负 <b>${dec.loss_24h || 0}</b></span>
      <span class="stat">跟踪 <b>${s.active_tracks || 0}</b></span>`;
  } catch (e) {
    document.getElementById("sys-status").textContent = "离线";
    document.getElementById("sys-status").className = "status-badge err";
  }
}

// ===== Init =====
loadDecisions();
loadStatus();
setInterval(loadStatus, 60000);
