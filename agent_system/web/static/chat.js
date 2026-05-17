const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const streamEl = document.getElementById("debate-stream");
const listEl = document.getElementById("decisions-list");

let sessionId = null;

function appendMsg(role, content) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  if (typeof content === "object") {
    div.appendChild(renderCard(content));
  } else {
    div.textContent = content;
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderCard(card) {
  const root = document.createElement("div");
  root.className = "card";
  const dirClass = card.direction === "多" ? "long" : card.direction === "空" ? "short" : "wait";
  root.innerHTML = `
    <div class="dir ${dirClass}">${card.symbol || ""} ${card.direction || ""} (信心 ${card.confidence ?? "-"})</div>
    <div><b>入场:</b> ${card.entry_price ?? "-"} (zone: ${JSON.stringify(card.entry_zone || [])})</div>
    <div><b>止损/止盈:</b> ${card.stop_loss ?? "-"} / ${card.take_profit ?? "-"} (RR ${card.risk_reward_ratio ?? "-"})</div>
    <div><b>仓位:</b> ${card.position_size_pct ?? "-"}%</div>
    <div><b>依据:</b><ul>${(card.key_evidence || []).map(e => `<li>${e}</li>`).join("")}</ul></div>
    <div><b>风险:</b><ul>${(card.key_risks || []).map(r => `<li>${r}</li>`).join("")}</ul></div>
    <div><b>计划:</b> ${card.execution_plan || ""}</div>
  `;
  return root;
}

const VIEW_CLASS = {"多": "long", "空": "short", "观望": "wait"};

const MATE_DISPLAY = {
  "trend_multi_tf": "周期师",
  "funding_rate": "费率官",
  "smart_money": "大户雷达",
  "long_short_compare": "多空裁",
  "volatility": "波动官",
  "experience": "复盘官",
  "red_team": "蒋军",
  "macro_sentiment": "宏观官",
  "liquidity": "水位官",
  "position_mgr": "仓位管家",
  "decision_lead": "决策长",
};
function mateName(id) { return MATE_DISPLAY[id] || id; }

function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

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
  head.innerHTML = `
    <span class="mate-round">${roundLabel}</span>
    <span class="mate-name">${escapeHtml(mateLabel)}</span>
    <span class="mate-view ${cls}">${escapeHtml(view)}</span>
    <span class="mate-conf">${escapeHtml(String(conf))}</span>
    <span class="mate-arrow">▸</span>
  `;
  const evi = document.createElement("div");
  evi.className = "mate-evi";
  evi.textContent = evidence;
  const detail = document.createElement("pre");
  detail.className = "mate-detail";
  detail.style.display = "none";
  detail.textContent = JSON.stringify(payload.result || payload, null, 2);

  head.addEventListener("click", () => {
    const open = detail.style.display === "none";
    detail.style.display = open ? "block" : "none";
    head.querySelector(".mate-arrow").textContent = open ? "▾" : "▸";
  });

  div.appendChild(head);
  div.appendChild(evi);
  div.appendChild(detail);
  return div;
}

function renderPhaseHeader(label, sub) {
  const div = document.createElement("div");
  div.className = "phase-header";
  div.innerHTML = `<span class="phase-label">${escapeHtml(label)}</span>${
    sub ? `<span class="phase-sub">${escapeHtml(sub)}</span>` : ""
  }`;
  return div;
}

function renderRebuttalCard(payload) {
  const rebuttal = payload.rebuttal || {};
  const div = document.createElement("div");
  div.className = "mate-card rebuttal";
  const head = document.createElement("div");
  head.className = "mate-head";
  head.innerHTML = `
    <span class="mate-round">R2</span>
    <span class="mate-name">蒋军 反驳</span>
    <span class="mate-view short">vs ${escapeHtml(payload.majority || "?")}</span>
    <span class="mate-arrow">▸</span>
  `;
  const summary = (rebuttal.extra && rebuttal.extra.rebuttal) || rebuttal.evidence?.[0] || "(无)";
  const evi = document.createElement("div");
  evi.className = "mate-evi";
  evi.textContent = typeof summary === "string" ? summary : JSON.stringify(summary);
  const detail = document.createElement("pre");
  detail.className = "mate-detail";
  detail.style.display = "none";
  detail.textContent = JSON.stringify(rebuttal, null, 2);
  head.addEventListener("click", () => {
    const open = detail.style.display === "none";
    detail.style.display = open ? "block" : "none";
    head.querySelector(".mate-arrow").textContent = open ? "▾" : "▸";
  });
  div.appendChild(head); div.appendChild(evi); div.appendChild(detail);
  return div;
}

function appendStreamEvent(evt) {
  const stage = evt.stage;
  const payload = evt.payload || {};

  if (stage === "intent") {
    streamEl.appendChild(renderPhaseHeader("意图", `${payload.intent || ""} ${payload.symbol || ""}`));
  } else if (stage === "data_packing") {
    streamEl.appendChild(renderPhaseHeader("拉数据", payload.symbol || ""));
  } else if (stage === "orchestrator_start") {
    streamEl.appendChild(renderPhaseHeader("圆桌开始", `${payload.symbol} mode=${payload.mode}`));
  } else if (stage === "round_1_start") {
    const names = (payload.mates || []).map(mateName).join(", ");
    streamEl.appendChild(renderPhaseHeader("第 1 轮 独立分析", names));
  } else if (stage === "mate_done") {
    streamEl.appendChild(renderMateCard(stage, payload));
  } else if (stage === "rebuttal_start") {
    streamEl.appendChild(renderPhaseHeader("第 2 轮 反驳", `多数派 = ${payload.majority || "?"}`));
  } else if (stage === "rebuttal_done") {
    streamEl.appendChild(renderRebuttalCard(payload));
  } else if (stage === "response_done") {
    const inner = renderMateCard("mate_done", {
      mate: payload.mate, round: 2, view: payload.result?.updated_view,
      confidence: payload.result?.updated_confidence,
      evidence_lead: payload.result?.note, result: payload.result,
    });
    streamEl.appendChild(inner);
  } else if (stage === "round_3_start") {
    streamEl.appendChild(renderPhaseHeader("第 3 轮 综合", `多数派 = ${payload.majority || "?"}`));
  } else if (stage === "done" || stage === "decision_card") {
    streamEl.appendChild(renderPhaseHeader("决策完成", ""));
  } else {
    const div = document.createElement("div");
    div.className = "stream-evt";
    div.innerHTML = `<span class="stage">${escapeHtml(stage)}</span>: ${
      typeof payload === "object" ? escapeHtml(JSON.stringify(payload).slice(0, 200)) : escapeHtml(payload)
    }`;
    streamEl.appendChild(div);
  }
  streamEl.scrollTop = streamEl.scrollHeight;
}

async function send(text) {
  appendMsg("user", text);
  streamEl.innerHTML = "";
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({session_id: sessionId, text}),
  });
  const data = await r.json();
  sessionId = data.session_id;
  const es = new EventSource(`/api/chat/stream/${sessionId}`);
  es.onmessage = (e) => {
    const evt = JSON.parse(e.data);
    appendStreamEvent(evt);
    if (evt.stage === "done") {
      const result = evt.payload;
      if (result.type === "decision_card") {
        appendMsg("assistant", result.card);
      } else if (result.type === "follow_up_answer") {
        appendMsg("assistant", result.message);
      } else {
        appendMsg("assistant", result.message || JSON.stringify(result));
      }
      es.close();
      loadDecisions();
    }
    if (evt.stage === "error") {
      appendMsg("assistant", "错误: " + JSON.stringify(evt.payload));
      es.close();
    }
  };
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  send(text);
});

async function loadDecisions() {
  const r = await fetch("/api/decisions");
  const list = await r.json();
  listEl.innerHTML = list.map(d =>
    `<li>${d.symbol} ${d.direction || ""} (${d.confidence ?? "-"}) ${d.status}</li>`
  ).join("");
}

loadDecisions();

// --- Resizable right panel ---
(function initSplitter() {
  const splitter = document.getElementById("splitter");
  if (!splitter) return;
  const root = document.documentElement;
  const saved = parseInt(localStorage.getItem("rightPanelWidth") || "0", 10);
  if (saved > 200 && saved < window.innerWidth - 400) {
    root.style.setProperty("--right-w", saved + "px");
  }
  let dragging = false;
  splitter.addEventListener("mousedown", (e) => {
    dragging = true;
    splitter.classList.add("dragging");
    document.body.style.cursor = "col-resize";
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const newW = window.innerWidth - e.clientX;
    const clamped = Math.min(Math.max(newW, 220), window.innerWidth - 400);
    root.style.setProperty("--right-w", clamped + "px");
  });
  document.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    splitter.classList.remove("dragging");
    document.body.style.cursor = "";
    const cur = getComputedStyle(root).getPropertyValue("--right-w").trim();
    if (cur) localStorage.setItem("rightPanelWidth", parseInt(cur, 10));
  });
})();
