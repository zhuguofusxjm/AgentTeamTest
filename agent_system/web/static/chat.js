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

function appendStreamEvent(evt) {
  const div = document.createElement("div");
  div.className = "stream-evt";
  div.innerHTML = `<span class="stage">${evt.stage}</span>: ${
    typeof evt.payload === "object" ? JSON.stringify(evt.payload).slice(0, 200) : evt.payload
  }`;
  streamEl.appendChild(div);
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
