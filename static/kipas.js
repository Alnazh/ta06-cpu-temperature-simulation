"use strict";

let controller = null;

async function update() {
  controller?.abort();
  controller = new AbortController();
  try {
    const data = await postJson("/api/fans", { params: readParams() }, controller);
    renderFans(data.fans);
    renderInsights(data.summary);
    showError("");
  } catch (error) {
    if (error.name !== "AbortError") showError(friendly(error));
  }
}

function renderFans(rows) {
  const max = Math.max(...rows.map((row) => row.steady)) * 1.05;
  $("#fans").replaceChildren(...rows.map((row) => {
    const bar = document.createElement("div");
    bar.className = `bar${row.current ? " current" : ""}`;
    bar.dataset.status = row.status;
    bar.innerHTML = `<span class="bar-label">Kipas ${fmt(row.fan, 0)}%</span>
      <div class="bar-track"><div class="bar-fill" style="--w: ${(row.steady / max) * 100}%"></div></div>
      <span class="bar-value">${fmt(row.steady)} °C<small>τ = ${fmt(row.tau)} detik</small></span>`;
    return bar;
  }));
}

bindSliders(update);
update();
