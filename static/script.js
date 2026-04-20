const baseUrl = window.location.origin;

const messageList = document.getElementById("message-list");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-button");
const resetBtn = document.getElementById("reset-button");
const themeToggle = document.getElementById("theme-toggle");

const pdfFrame = document.getElementById("pdf-frame");
const pdfEmpty = document.getElementById("pdf-empty");
const loading = document.getElementById("loading");

const docList = document.getElementById("doc-list");
const pdfUpload = document.getElementById("pdf-upload");
const scopeSelect = document.getElementById("scope-select");

let documents = []; // {docId, filename, pdfUrl}
let activeDocId = null;

function escapeHtml(text = "") {
  return text.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function scrollToBottom() {
  window.requestAnimationFrame(() => {
    const chatWindow = document.getElementById("chat-window");
    chatWindow.scrollTop = chatWindow.scrollHeight;
  });
}

function setLoading(isLoading) {
  loading.style.display = isLoading ? "block" : "none";
  sendBtn.disabled = isLoading || documents.length === 0;
}

function addMessage(text, type = "bot", sources = []) {
  const line = document.createElement("div");
  line.className = "message-line" + (type === "user" ? " user" : "");

  const box = document.createElement("div");
  box.className = "message-box" + (type === "user" ? " user" : "");
  box.innerHTML = escapeHtml(text);

  if (type === "bot" && sources && sources.length > 0) {
    const sourcesDiv = document.createElement("div");
    sourcesDiv.className = "sources";

    sources.forEach((s) => {
      const chip = document.createElement("button");
      chip.className = "source-chip";
      chip.textContent = `${s.filename} (p.${s.page})`;

      chip.addEventListener("click", () => {
        openSource(s.docId, s.page);
      });

      sourcesDiv.appendChild(chip);
    });

    box.appendChild(sourcesDiv);
  }

  line.appendChild(box);
  messageList.appendChild(line);
  scrollToBottom();
}

function renderDocList() {
  docList.innerHTML = "";

  documents.forEach((doc) => {
    const item = document.createElement("div");
    item.className = "doc-item" + (doc.docId === activeDocId ? " active" : "");

    const name = document.createElement("div");
    name.className = "doc-name";
    name.textContent = doc.filename;

    item.appendChild(name);

    item.addEventListener("click", () => {
      setActiveDoc(doc.docId);
    });

    docList.appendChild(item);
  });
}

function setActiveDoc(docId) {
  const doc = documents.find((d) => d.docId === docId);
  if (!doc) return;

  activeDocId = docId;
  renderDocList();

  pdfFrame.src = baseUrl + doc.pdfUrl;
  pdfFrame.hidden = false;
  pdfEmpty.hidden = true;
}

function openSource(docId, page) {
  const doc = documents.find((d) => d.docId === docId);
  if (!doc) return;

  activeDocId = docId;
  renderDocList();

  pdfFrame.src = baseUrl + doc.pdfUrl + `#page=${page}`;
  pdfFrame.hidden = false;
  pdfEmpty.hidden = true;
}

async function uploadPdf(file) {
  setLoading(true);

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(baseUrl + "/process-document", {
    method: "POST",
    body: formData,
  });

  const data = await res.json();

  if (!res.ok) {
    addMessage(data.botResponse || "Upload failed.");
    setLoading(false);
    return;
  }

  documents.push({
    docId: data.docId,
    filename: data.filename,
    pdfUrl: data.pdfUrl,
  });

  addMessage(data.botResponse || "PDF uploaded.");

  setActiveDoc(data.docId);

  setLoading(false);
}

async function sendMessage(text) {
  setLoading(true);

  const scope = scopeSelect.value;

  const payload = {
    userMessage: text,
    scope: scope,
  };

  if (scope === "active") {
    payload.docId = activeDocId;
  }

  const res = await fetch(baseUrl + "/process-message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  addMessage(data.botResponse || "No response.", "bot", data.sources || []);

  setLoading(false);
}

async function resetApp() {
  messageList.innerHTML = "";
  input.value = "";

  documents = [];
  activeDocId = null;
  docList.innerHTML = "";

  pdfFrame.src = "";
  pdfFrame.hidden = true;
  pdfEmpty.hidden = false;

  sendBtn.disabled = true;

  addMessage("Hello! Upload one or more PDFs to build your knowledge base.");

  try {
    await fetch(baseUrl + "/reset", {
      method: "POST",
    });
  } catch (err) {
    console.warn("Backend reset failed:", err);
  }
}

sendBtn.addEventListener("click", () => {
  const msg = input.value.trim();
  if (!msg) return;
  if (!documents.length) return;

  input.value = "";
  addMessage(msg, "user");
  sendMessage(msg);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendBtn.click();
  }
});

resetBtn.addEventListener("click", resetApp);

themeToggle.addEventListener("change", () => {
  document.body.classList.toggle("dark-mode", themeToggle.checked);
});

pdfUpload.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (file) uploadPdf(file);
});

resetApp();