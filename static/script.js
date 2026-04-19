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

function renderBotMessage(text) {
  const html = `
    <div class="message-line">
      <div class="message-box">${text}</div>
    </div>
  `;
  messageList().insertAdjacentHTML("beforeend", html);
  scrollToBottom();
}

function renderUserMessage(text) {
  input().value = "";
  const html = `
    <div class="message-line my-text">
      <div class="message-box my-text">${text}</div>
    </div>
  `;
  messageList().insertAdjacentHTML("beforeend", html);
  scrollToBottom();
}

document.addEventListener("DOMContentLoaded", () => {
  sendBtn()?.addEventListener("click", () => {
    const msg = input().value.trim();
    if (!msg) return;
    renderUserMessage(msg);
    renderBotMessage("Chat backend not connected yet.");
  });

  resetBtn()?.addEventListener("click", () => {
    messageList().innerHTML = "";
    resetPdfViewer();
  });

  themeSwitch()?.addEventListener("change", () => {
    document.body.classList.toggle("dark-mode", themeSwitch().checked);
  });

  resetPdfViewer();
  renderBotMessage("Hello there! I'm your friendly data assistant. Please upload a PDF file.");
});