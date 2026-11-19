"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const fmt = (value, digits = 1) =>
  Number(value).toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function syncSlider(input) {
  const { min, max, value, dataset } = input;
  const text = fmt(value, Number(dataset.decimals));
  input.parentElement.querySelector("output").textContent =
    `${input.name === "d_amb" ? "+" : ""}${text} ${dataset.unit}`.trim();
  input.style.setProperty("--fill", `${((value - min) / (max - min)) * 100}%`);
}

const paramSliders = () => $$("#params input[type='range']");
const readParams = () => Object.fromEntries(paramSliders().map((input) => [input.name, Number(input.value)]));

function setParams(values) {
  paramSliders().forEach((input) => {
    input.value = values[input.name] ?? input.defaultValue;
    syncSlider(input);
  });
}

function bindSliders(onChange) {
  const schedule = debounce(onChange, 40);
  $("#params").addEventListener("submit", (event) => event.preventDefault());
  paramSliders().forEach((input) => {
    syncSlider(input);
    input.addEventListener("input", () => {
      syncSlider(input);
      schedule();
    });
  });
  $("#reset").addEventListener("click", () => {
    setParams({});
    onChange();
  });
}

const friendly = (error) => (error instanceof TypeError ? "Server tidak dapat dihubungi. Pastikan python app.py masih berjalan." : error.message);

function showError(message) {
  const box = $("#error");
  box.textContent = message;
  box.hidden = !message;
}

// kirim JSON ke API; permintaan lama dibatalkan bila ada yang baru (`controller` per pemanggil)
async function postJson(url, body, controller) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: controller.signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error);
  return data;
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
