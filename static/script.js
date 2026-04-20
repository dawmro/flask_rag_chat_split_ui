const baseUrl = window.location.origin;

const messageList = document.getElementById("message-list");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-button");
const resetBtn = document.getElementById("reset-button");
const themeToggle = document.getElementById("theme-toggle");

const pdfFrame = document.getElementById("pdf-frame");
const pdfEmpty = document.getElementById("pdf-empty");
const loading = document.getElementById("loading");

let pdfLoaded = false;

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
  sendBtn.disabled = isLoading || !pdfLoaded;
}

function addMessage(text, type = "bot") {
  const line = document.createElement("div");
  line.className = "message-line" + (type === "user" ? " user" : "");

  const box = document.createElement("div");
  box.className = "message-box" + (type === "user" ? " user" : "");
  box.innerHTML = escapeHtml(text);

  line.appendChild(box);
  messageList.appendChild(line);
  scrollToBottom();
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

  if (data.pdfUrl) {
    pdfFrame.src = baseUrl + data.pdfUrl;
    pdfFrame.hidden = false;
    pdfEmpty.hidden = true;
    pdfLoaded = true;
  }

  addMessage(data.botResponse || "PDF uploaded.");
  setLoading(false);
}

async function sendMessage(text) {
  setLoading(true);

  const res = await fetch(baseUrl + "/process-message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userMessage: text }),
  });

  const data = await res.json();
  addMessage(data.botResponse || "No response.");
  setLoading(false);
}

function resetApp() {
  messageList.innerHTML = "";
  input.value = "";

  pdfLoaded = false;
  pdfFrame.src = "";
  pdfFrame.hidden = true;
  pdfEmpty.hidden = false;

  sendBtn.disabled = true;

  addMessage("Hello! Please upload a PDF to begin.");

  // Create upload UI message
  const line = document.createElement("div");
  line.className = "message-line";

  const box = document.createElement("div");
  box.className = "message-box";

  box.innerHTML = `
    <input type="file" id="pdf-upload" accept="application/pdf">
  `;

  line.appendChild(box);
  messageList.appendChild(line);

  document.getElementById("pdf-upload").addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) uploadPdf(file);
  });

  scrollToBottom();
}

sendBtn.addEventListener("click", () => {
  const msg = input.value.trim();
  if (!msg || !pdfLoaded) return;

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

resetApp();