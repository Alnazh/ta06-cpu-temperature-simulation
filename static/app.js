"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const SVG_NS = "http://www.w3.org/2000/svg";
const INK = "#111";
const COLORS = { reference: "#868e96", steady: "#e64980", load: "#fd7e14", ambient: "#12b886" };
const PLOT = { left: 72, right: 736 };
const PANELS = { top: [84, 328], bottom: [390, 450] };

const sliders = $$("#params input[type='range']");
const svg = $("#chart");
let scenario = $(".scenario[aria-pressed='true']").dataset.key;
let controller = null;

// angka berformat Indonesia: 74,9
const fmt = (value, digits = 1) =>
  Number(value).toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const activeButton = () => $(".scenario[aria-pressed='true']");
const accent = () => activeButton().dataset.color;

// ---------------------------------------------------------------- panel kontrol
function syncSlider(input) {
  const { min, max, value, dataset } = input;
  const text = fmt(value, Number(dataset.decimals));
  input.parentElement.querySelector("output").textContent =
    `${input.name === "d_amb" ? "+" : ""}${text} ${dataset.unit}`.trim();
  input.style.setProperty("--fill", `${((value - min) / (max - min)) * 100}%`);
}

const readParams = () => Object.fromEntries(sliders.map((input) => [input.name, Number(input.value)]));

function setScenario(key) {
  $$(".scenario").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.key === key)));
  scenario = key;
}

function setParams(values) {
  sliders.forEach((input) => {
    input.value = values[input.name] ?? input.defaultValue;
    syncSlider(input);
  });
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

sliders.forEach((input) => {
  syncSlider(input);
  input.addEventListener("input", () => {
    syncSlider(input);
    scheduleUpdate();
  });
});

$$(".scenario").forEach((button) => {
  button.addEventListener("click", () => {
    setScenario(button.dataset.key);
    update();
  });
});

$("#reset").addEventListener("click", () => {
  setParams({});
  update();
});

$$("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    const preset = JSON.parse(button.dataset.preset);
    setParams(preset.params);
    setScenario(preset.scenario);
    update();
    $("#simulator").scrollIntoView({ behavior: "smooth" });
  });
});

// ---------------------------------------------------------------- permintaan ke server
async function update() {
  controller?.abort();
  controller = new AbortController();
  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario, params: readParams() }),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    showError("");
    render(data);
  } catch (error) {
    if (error.name !== "AbortError") showError(error.message);
  }
}
const scheduleUpdate = debounce(update, 40);

function showError(message) {
  const box = $("#error");
  box.textContent = message;
  box.hidden = !message;
}

function render(data) {
  renderStatus(data);
  renderMetrics(data);
  renderInsights(data.insights);
  renderFans(data.fans);
  renderChart(data);
}

// ---------------------------------------------------------------- status, metrik, penjelasan
function renderStatus({ metrics }) {
  const tones = { aman: "good", hangat: "warn", panas: "hot" };
  $("#status").dataset.tone = tones[metrics.status];
  $("#status-label").textContent = metrics.status_label;
  $("#status-text").textContent = `Suhu puncak ${fmt(metrics.peak)} °C pada skenario ${activeButton().textContent}.`;
}

function renderMetrics({ metrics: m, t }) {
  const params = readParams();
  $("#m-peak").textContent = `${fmt(m.peak)} °C`;
  $("#s-peak").textContent = `di detik ${fmt(m.t_peak, 0)}`;
  $("#m-final").textContent = `${fmt(m.final)} °C`;
  $("#s-final").textContent = `pada detik ${fmt(t[t.length - 1], 0)}`;
  $("#m-steady").textContent = `${fmt(m.steady)} °C`;
  $("#m-tau").textContent = `${fmt(m.tau)} detik`;
  $("#s-tau").textContent = `τ = 1/k, stabil ±${fmt(3 * m.tau, 0)} detik`;
  $("#m-error").textContent = `${fmt(m.max_error, 3)} °C`;
  $("#s-error").textContent = `dt = ${fmt(params.dt)} detik`;
  $("#m-k").textContent = fmt(1 / m.tau, 3);
}

function renderInsights(items) {
  $("#insights").replaceChildren(...items.map(({ tone, title, text }) => {
    const card = document.createElement("article");
    card.className = "insight";
    card.dataset.tone = tone;
    const heading = document.createElement("h4");
    heading.textContent = title;
    const body = document.createElement("p");
    body.textContent = text;
    card.append(heading, body);
    return card;
  }));
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

// ---------------------------------------------------------------- grafik SVG
function element(name, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  if (text !== undefined) node.textContent = text;
  return node;
}

const linear = (d0, d1, r0, r1) => (value) => r0 + ((value - d0) / (d1 - d0 || 1)) * (r1 - r0);

function niceTicks(lo, hi, count = 5) {
  const span = hi - lo || 1;
  const raw = span / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(Number(v.toFixed(6)));
  return ticks;
}

function paddedScale(values, count) {
  const lo = Math.min(...values), hi = Math.max(...values);
  const pad = (hi - lo) * 0.1 || 1;
  return { domain: [lo - pad, hi + pad], ticks: niceTicks(lo - pad, hi + pad, count) };
}

const pathOf = (xs, ys, x, y) => xs.map((v, i) => `${i ? "L" : "M"}${x(v).toFixed(1)},${y(ys[i]).toFixed(1)}`).join("");

function drawPanel(root, { xs, x, bounds, scale: { domain, ticks }, label, lines }) {
  const [top, bottom] = bounds;
  const y = linear(domain[0], domain[1], bottom, top);
  root.append(element("rect", { class: "plot-bg", x: PLOT.left, y: top, width: PLOT.right - PLOT.left, height: bottom - top }));
  ticks.forEach((tick) => {
    root.append(
      element("line", { class: "grid-line", x1: PLOT.left, x2: PLOT.right, y1: y(tick), y2: y(tick) }),
      element("text", { class: "tick", x: PLOT.left - 10, y: y(tick) + 4, "text-anchor": "end" }, fmt(tick, 0)),
    );
  });
  root.append(element("text", { class: "axis-label", transform: `translate(18 ${(top + bottom) / 2}) rotate(-90)`, "text-anchor": "middle" }, label));

  lines.forEach(({ values, color, dash, width, fill }) => {
    const d = pathOf(xs, values, x, y);
    if (fill) {
      root.append(element("path", { d: `${d}L${x(xs[xs.length - 1])},${y(domain[0])}L${x(xs[0])},${y(domain[0])}Z`, fill: color, "fill-opacity": 0.22 }));
    }
    root.append(element("path", { d, fill: "none", stroke: color, "stroke-width": width, "stroke-dasharray": dash ?? "none", "stroke-linejoin": "miter" }));
  });
  return y;
}

// kotak teks bergaya brutal; `anchor` menentukan arah kotak terhadap titik (x, y)
function tag(root, { x, y, text, fill, anchor = "start" }) {
  const width = text.length * 6.6 + 14;
  const left = anchor === "end" ? x - width : x;
  root.append(
    element("rect", { class: "note-box", x: left, y: y - 14, width, height: 21, fill }),
    element("text", { class: "note-label", x: left + 7, y: y + 1 }, text),
  );
}

function renderChart(data) {
  svg.replaceChildren();
  const xs = data.t;
  const x = linear(0, xs[xs.length - 1], PLOT.left, PLOT.right);
  const color = accent();

  svg.append(element("text", { class: "chart-title", x: PLOT.left, y: 28 }, activeButton().textContent));

  const hot = data.thresholds.hot;
  const tempValues = [...data.temperature, ...data.reference, data.steady];
  const tempScale = paddedScale(tempValues, 6);
  const yTemp = drawPanel(svg, {
    xs, x, bounds: PANELS.top, scale: tempScale, label: "Suhu CPU (°C)",
    lines: [
      { values: data.reference, color: COLORS.reference, dash: "2 5", width: 2.5 },
      { values: data.temperature, color, width: 3.5, fill: true },
      { values: xs.map(() => data.steady), color: COLORS.steady, dash: "8 5", width: 2 },
    ],
  });

  if (hot > tempScale.domain[0] && hot < tempScale.domain[1]) {
    svg.append(element("line", { class: "hot-line", x1: PLOT.left, x2: PLOT.right, y1: yTemp(hot), y2: yTemp(hot) }));
    tag(svg, { x: PLOT.left + 8, y: yTemp(hot) + 22, text: `Batas panas ${fmt(hot, 0)} °C`, fill: "#ff6b6b" });
  }

  const bottom = data.disturbed
    ? { values: data.ambient, scale: paddedScale(data.ambient, 3), label: "Ruangan (°C)", color: COLORS.ambient }
    : { values: data.load, scale: { domain: [-12, 112], ticks: [0, 50, 100] }, label: "Beban (%)", color: COLORS.load };
  drawPanel(svg, {
    xs, x, bounds: PANELS.bottom, scale: bottom.scale, label: bottom.label,
    lines: [{ values: bottom.values, color: bottom.color, width: 2.8, fill: true }],
  });

  data.events.forEach((event, index) => {
    const ex = x(event.t);
    svg.append(element("line", { class: "event-line", x1: ex, x2: ex, y1: PANELS.top[0], y2: PANELS.bottom[1] }));
    tag(svg, { x: ex + 4, y: PANELS.top[0] + 24 + index * 26, text: event.label, fill: "#ffd93d", anchor: ex > PLOT.right - 150 ? "end" : "start" });
  });

  annotatePeak(data, x, yTemp);

  niceTicks(0, xs[xs.length - 1], 6).forEach((tick) => {
    svg.append(element("text", { class: "tick", x: x(tick), y: PANELS.bottom[1] + 20, "text-anchor": "middle" }, fmt(tick, 0)));
  });
  svg.append(element("text", { class: "axis-label", x: (PLOT.left + PLOT.right) / 2, y: 488, "text-anchor": "middle" }, "Waktu (detik)"));

  drawLegend(data.steady, color);
  attachHover(data, x, yTemp, color);
}

function annotatePeak({ metrics, t }, x, yTemp) {
  const px = x(metrics.t_peak);
  const py = yTemp(metrics.peak);
  const size = 8;
  svg.append(element("path", {
    d: `M${px},${py - size}L${px + size},${py}L${px},${py + size}L${px - size},${py}Z`,
    fill: "#ff6b6b", stroke: INK, "stroke-width": 2.5,
  }));
  const nearRight = px > (PLOT.left + PLOT.right) / 2;
  tag(svg, {
    x: nearRight ? px - 14 : px + 14, y: py + 30, anchor: nearRight ? "end" : "start",
    text: `Puncak ${fmt(metrics.peak)} °C @ ${fmt(metrics.t_peak, 0)} s`, fill: "#ff8fb1",
  });
}

function drawLegend(steady, color) {
  const items = [
    ["Euler", color, "none", 0],
    ["Langkah halus", COLORS.reference, "2 4", 60],
    [`Steady state ${fmt(steady)} °C`, COLORS.steady, "8 5", 175],
  ];
  items.forEach(([text, stroke, dash, offset]) => {
    const x = 330 + offset;
    svg.append(
      element("line", { x1: x, x2: x + 22, y1: 24, y2: 24, stroke, "stroke-width": 3, "stroke-dasharray": dash }),
      element("text", { class: "legend-text", x: x + 28, y: 28 }, text),
    );
  });
}

function attachHover(data, x, yTemp, color) {
  const cursor = element("line", { class: "cursor", y1: PANELS.top[0], y2: PANELS.bottom[1], visibility: "hidden" });
  const dot = element("circle", { r: 6, fill: color, stroke: INK, "stroke-width": 3, visibility: "hidden" });
  const readout = element("text", { class: "hover-text", x: PLOT.right, y: 60, "text-anchor": "end" });
  const area = element("rect", {
    x: PLOT.left, y: PANELS.top[0], width: PLOT.right - PLOT.left, height: PANELS.bottom[1] - PANELS.top[0], fill: "transparent",
  });
  svg.append(cursor, dot, readout, area);

  const move = (event) => {
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const { x: px } = point.matrixTransform(svg.getScreenCTM().inverse());
    const ratio = Math.min(Math.max((px - PLOT.left) / (PLOT.right - PLOT.left), 0), 1);
    const i = Math.round(ratio * (data.t.length - 1));
    cursor.setAttribute("x1", x(data.t[i]));
    cursor.setAttribute("x2", x(data.t[i]));
    dot.setAttribute("cx", x(data.t[i]));
    dot.setAttribute("cy", yTemp(data.temperature[i]));
    const extra = data.disturbed ? `ruangan ${fmt(data.ambient[i], 0)} °C` : `beban ${fmt(data.load[i], 0)}%`;
    readout.textContent = `t = ${fmt(data.t[i], 0)} s · T = ${fmt(data.temperature[i], 2)} °C · ${extra}`;
    [cursor, dot].forEach((node) => node.setAttribute("visibility", "visible"));
  };
  const leave = () => {
    readout.textContent = "";
    [cursor, dot].forEach((node) => node.setAttribute("visibility", "hidden"));
  };
  area.addEventListener("pointermove", move);
  area.addEventListener("pointerleave", leave);
}

update();
