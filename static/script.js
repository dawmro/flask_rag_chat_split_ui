let isFirstMessage = true;
const baseUrl = window.location.origin;

const chatWindow = () => document.getElementById("chat-window");
const messageList = () => document.getElementById("message-list");
const input = () => document.getElementById("message-input");
const sendBtn = () => document.getElementById("send-button");
const resetBtn = () => document.getElementById("reset-button");
const themeSwitch = () => document.getElementById("light-dark-mode-switch");
const pdfViewer = () => document.getElementById("pdf-viewer");
const pdfFrame = () => document.getElementById("pdf-frame");
const pdfEmptyState = () => document.getElementById("pdf-empty-state");

function scrollToBottom() {
  const el = chatWindow();
  if (el) {
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }
}

function syncPanelHeights() {
  if (!pdfFrame() || !pdfViewer() || pdfViewer().hidden || window.innerWidth < 768) {
    return;
  }
  pdfFrame().style.height = `${pdfViewer().clientHeight}px`;
}

function showPdf(pdfUrl) {
  if (!pdfFrame() || !pdfViewer()) return;
  pdfFrame().src = `${baseUrl}${pdfUrl}`;
  pdfViewer().hidden = false;
  if (pdfEmptyState()) {
    pdfEmptyState().hidden = true;
  }
  requestAnimationFrame(syncPanelHeights);
}

function resetPdfViewer() {
  if (pdfFrame()) {
    pdfFrame().src = "";
    pdfFrame().style.height = "";
  }
  if (pdfViewer()) {
    pdfViewer().hidden = true;
  }
  if (pdfEmptyState()) {
    pdfEmptyState().hidden = false;
  }
}

function renderBotMessage(response, uploadButtonHtml = "") {
  const text = typeof response === "string" ? response : response?.botResponse || "No response received.";
  const html = `
    <div class="message-line">
      <div class="message-box">${text}${uploadButtonHtml}</div>
    </div>
  `;
  messageList().insertAdjacentHTML("beforeend", html);
  scrollToBottom();
}

document.addEventListener("DOMContentLoaded", () => {
  sendBtn().disabled = true;
  resetPdfViewer();

  resetBtn()?.addEventListener("click", () => {
    messageList().innerHTML = "";
    isFirstMessage = true;
    resetPdfViewer();
    location.reload();
  });

  themeSwitch()?.addEventListener("change", () => {
    document.body.classList.toggle("dark-mode", themeSwitch().checked);
  });

  window.addEventListener("resize", syncPanelHeights);

  renderBotMessage(
    { botResponse: "Hello there! I'm your friendly data assistant. Please upload a PDF file." },
    `<div class="upload-bubble"><button id="upload-button" type="button">Upload PDF</button><input id="file-upload" type="file" accept="application/pdf" hidden /></div>`
  );

  const uploadButton = document.getElementById("upload-button");
  const fileInput = document.getElementById("file-upload");

  uploadButton?.addEventListener("click", () => fileInput?.click());

  fileInput?.addEventListener("change", async function () {
    const file = this.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(baseUrl + "/process-document", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (data.pdfUrl) {
      showPdf(data.pdfUrl);
      uploadButton.disabled = true;
      isFirstMessage = false;
      sendBtn().disabled = false;
    }

    renderBotMessage(data);
  }, { once: true });
});