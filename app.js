const DEFAULT_API = "";
const API_KEY = "clipforge_api_url";

const $ = (id) => document.getElementById(id);
const form = $("projectForm");
const videoInput = $("videoInput");
const dropZone = $("dropZone");
const fileTitle = $("fileTitle");
const fileInfo = $("fileInfo");
const amount = $("amount");
const duration = $("duration");
const generateBtn = $("generateBtn");
const statusEmpty = $("statusEmpty");
const statusContent = $("statusContent");
const statusText = $("statusText");
const progressText = $("progressText");
const progressBar = $("progressBar");
const resultsEmpty = $("resultsEmpty");
const resultsGrid = $("resultsGrid");
const resultCount = $("resultCount");
const resultsSubtitle = $("resultsSubtitle");
const apiUrlInput = $("apiUrl");
const apiDot = $("apiDot");
const apiStatus = $("apiStatus");

let selectedFile = null;
let currentJobId = null;
let pollTimer = null;

function getApiUrl() {
  return (localStorage.getItem(API_KEY) || DEFAULT_API).replace(/\/+$/, "");
}

function setApiStatus(state, text) {
  apiDot.className = "dot " + state;
  apiStatus.textContent = text;
}

function saveApiUrl() {
  const value = apiUrlInput.value.trim().replace(/\/+$/, "");
  if (!value) {
    localStorage.removeItem(API_KEY);
    setApiStatus("offline", "API não configurada");
    return;
  }
  localStorage.setItem(API_KEY, value);
  checkApi();
}

async function checkApi() {
  const base = getApiUrl();
  if (!base) {
    setApiStatus("offline", "API não configurada");
    return false;
  }

  try {
    const response = await fetch(base + "/health", { method: "GET" });
    if (!response.ok) throw new Error();
    const data = await response.json();
    setApiStatus("online", data.openai_configured ? "API online • IA configurada" : "API online");
    return true;
  } catch {
    setApiStatus("offline", "API indisponível");
    return false;
  }
}

function setFile(file) {
  if (!file) return;
  if (!file.type.startsWith("video/")) {
    alert("Selecione um arquivo de vídeo.");
    return;
  }

  selectedFile = file;
  fileTitle.textContent = file.name;
  fileInfo.textContent = formatBytes(file.size) + " • pronto para processamento";
  dropZone.classList.add("drag");
  setTimeout(() => dropZone.classList.remove("drag"), 350);
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

videoInput.addEventListener("change", () => setFile(videoInput.files[0]));

["dragenter", "dragover"].forEach(eventName => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.add("drag");
  });
});

["dragleave", "drop"].forEach(eventName => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag");
  });
});

dropZone.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));

$("minus").addEventListener("click", () => {
  amount.value = Math.max(1, Number(amount.value || 1) - 1);
});

$("plus").addEventListener("click", () => {
  amount.value = Math.min(100, Number(amount.value || 1) + 1);
});

$("saveApi").addEventListener("click", saveApiUrl);

apiUrlInput.value = getApiUrl();

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!selectedFile) {
    alert("Escolha um vídeo primeiro.");
    return;
  }

  const base = getApiUrl();
  if (!base) {
    alert("Informe a URL da API no campo 'URL da API'.");
    apiUrlInput.focus();
    return;
  }

  generateBtn.disabled = true;
  generateBtn.querySelector("span").textContent = "ENVIANDO VÍDEO...";
  setApiStatus("busy", "Enviando vídeo");

  const data = new FormData();
  data.append("video", selectedFile);
  data.append("amount", String(Math.max(1, Math.min(100, Number(amount.value)))));
  data.append("target_duration", String(Number(duration.value)));

  showProcessing();

  try {
    const response = await fetch(base + "/api/projects", {
      method: "POST",
      body: data
    });

    const result = await readJson(response);

    if (!response.ok) {
      throw new Error(result.detail || "A API recusou o projeto.");
    }

    currentJobId = result.job_id;
    setApiStatus("busy", "Processando");
    startPolling(currentJobId);
  } catch (error) {
    finishWithError(error.message);
  }
});

async function readJson(response) {
  const text = await response.text();
  try { return JSON.parse(text); }
  catch { return { detail: text || "Resposta inválida da API." }; }
}

function showProcessing() {
  statusEmpty.classList.add("hidden");
  statusContent.classList.remove("hidden");
  statusText.textContent = "Preparando...";
  progressText.textContent = "0%";
  progressBar.style.width = "0%";
  setItems("waiting");
}

function setItems(state) {
  ["itemAnalyze", "itemSelect", "itemRender"].forEach(id => {
    $(id).classList.remove("active", "done", "error");
    const em = $(id).querySelector("em");
    em.textContent = "aguardando";
  });

  if (state === "analyze") {
    setItem("itemAnalyze", "active", "processando");
  } else if (state === "select") {
    setItem("itemAnalyze", "done", "concluído");
    setItem("itemSelect", "active", "processando");
  } else if (state === "render") {
    setItem("itemAnalyze", "done", "concluído");
    setItem("itemSelect", "done", "concluído");
    setItem("itemRender", "active", "processando");
  } else if (state === "done") {
    ["itemAnalyze", "itemSelect", "itemRender"].forEach(id => setItem(id, "done", "concluído"));
  } else if (state === "error") {
    ["itemAnalyze", "itemSelect", "itemRender"].forEach(id => {
      if (!$(id).classList.contains("done")) setItem(id, "error", "erro");
    });
  }
}

function setItem(id, cls, text) {
  const el = $(id);
  el.classList.add(cls);
  el.querySelector("em").textContent = text;
}

function startPolling(jobId) {
  if (pollTimer) clearInterval(pollTimer);

  pollJob(jobId);
  pollTimer = setInterval(() => pollJob(jobId), 1200);
}

async function pollJob(jobId) {
  const base = getApiUrl();

  try {
    const response = await fetch(base + "/api/projects/" + encodeURIComponent(jobId));
    const data = await readJson(response);

    if (!response.ok) throw new Error(data.detail || "Erro consultando projeto.");

    const progress = Number(data.progress || 0);
    progressText.textContent = progress + "%";
    progressBar.style.width = progress + "%";
    statusText.textContent = data.message || data.status || "Processando...";

    if (progress < 35) setItems("analyze");
    else if (progress < 45) setItems("select");
    else if (progress < 100) setItems("render");

    if (Array.isArray(data.outputs)) renderResults(data.outputs);

    if (data.status === "concluido") {
      clearInterval(pollTimer);
      setItems("done");
      setApiStatus("online", "API online • concluído");
      finishButton();
    }

    if (data.status === "erro") {
      clearInterval(pollTimer);
      setItems("error");
      finishWithError(data.message || "O processamento falhou.");
    }
  } catch (error) {
    clearInterval(pollTimer);
    finishWithError(error.message);
  }
}

function renderResults(outputs) {
  resultsEmpty.classList.add("hidden");
  resultCount.textContent = outputs.length + (outputs.length === 1 ? " corte" : " cortes");
  resultsSubtitle.textContent = "Os cortes selecionados pela IA estão prontos para revisão.";

  resultsGrid.innerHTML = outputs.map(item => `
    <article class="result-item">
      <video controls playsinline preload="metadata" src="${safe(item.file)}"></video>
      <div class="result-meta">
        <div class="result-line">
          <strong>Corte ${String(item.index).padStart(2, "0")}</strong>
          <span class="score">${Number(item.score || 0).toFixed(0)}/100</span>
        </div>
        <div class="result-line" style="margin-top:6px;color:#858ea0">
          <span>${Number(item.duration || 0).toFixed(1)}s</span>
          <span>${formatTime(item.start)} → ${formatTime(item.end)}</span>
        </div>
        <div class="result-actions">
          <a href="${safe(item.file)}" target="_blank" rel="noopener">Abrir</a>
          <a href="${safe(item.file)}" download>Baixar</a>
        </div>
      </div>
    </article>
  `).join("");
}

function safe(value) {
  return String(value || "").replace(/"/g, "&quot;");
}

function formatTime(seconds) {
  seconds = Math.max(0, Number(seconds || 0));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h) return `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
  return `${m}:${String(s).padStart(2,"0")}`;
}

function finishButton() {
  generateBtn.disabled = false;
  generateBtn.querySelector("span").textContent = "GERAR NOVOS CORTES";
}

function finishWithError(message) {
  statusContent.classList.remove("hidden");
  statusEmpty.classList.add("hidden");
  statusText.textContent = "Erro: " + message;
  progressBar.style.width = "100%";
  progressText.textContent = "ERRO";
  setItems("error");
  setApiStatus("offline", "Verifique a API");
  generateBtn.disabled = false;
  generateBtn.querySelector("span").textContent = "TENTAR NOVAMENTE";
}

checkApi();
