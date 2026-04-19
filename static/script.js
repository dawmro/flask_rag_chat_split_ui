let responses = [];
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

const escapeHtml = (value = "") =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const cleanTextInput = (value) => value.trim().replace(/[\n\t]+/g, " ");

const scrollToBottom = () => {
  const el = chatWindow();
  if (el) {
    el.scrollTo({
      top: el.scrollHeight,
      behavior: "smooth",
    });
  }
};

function loadingElement() {
  return (
    document.querySelector(".loading-animation.bot-loading") ||
    document.querySelector(".loading-animation")
  );
}

function setLoading(visible) {
  const loader = loadingElement();
  if (loader) {
    loader.style.display = visible ? "flex" : "none";
  }
  if (sendBtn()) {
    sendBtn().disabled = visible || isFirstMessage;
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

async function processUserMessage(userMessage) {
  const response = await fetch(baseUrl + "/process-message", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ userMessage }),
  });

  return await response.json();
}

function renderUserMessage(userMessage) {
  input().value = "";
  const html = `
    <div class="message-line my-text">
      <div class="message-box my-text">${escapeHtml(userMessage)}</div>
    </div>
  `;
  messageList().insertAdjacentHTML("beforeend", html);
  scrollToBottom();
}

function renderBotMessage(response, uploadButtonHtml = "") {
  responses.push(response);
  const text = typeof response === "string" ? response : response?.botResponse || "No response received.";
  const html = `
    <div class="message-line">
      <div class="message-box">${escapeHtml(text)} ${uploadButtonHtml}</div>
    </div>
  `;
  messageList().insertAdjacentHTML("beforeend", html);
  setLoading(false);
  scrollToBottom();
}

async function populateBotResponse(userMessage = "") {
  setLoading(true);

  let response;
  let uploadButtonHtml = "";

  if (isFirstMessage) {
    response = {
      botResponse: "Hello there! I'm your friendly data assistant. Please upload a PDF file.",
    };
    uploadButtonHtml = `
      <div class="upload-bubble">
        <button id="upload-button" type="button">Upload PDF</button>
        <input id="file-upload" type="file" accept="application/pdf" hidden />
      </div>
    `;
  } else {
    response = await processUserMessage(userMessage);
  }

  renderBotMessage(response, uploadButtonHtml);

  if (isFirstMessage) {
    const uploadButton = document.getElementById("upload-button");
    const fileInput = document.getElementById("file-upload");

    uploadButton?.addEventListener("click", () => {
      fileInput?.click();
    });

    fileInput?.addEventListener(
      "change",
      async function () {
        const file = this.files?.[0];
        if (!file) return;

        setLoading(true);

        const formData = new FormData();
        formData.append("file", file);

        try {
          const response = await fetch(baseUrl + "/process-document", {
            method: "POST",
            body: formData,
          });

          const data = await response.json();

          if (response.ok && uploadButton) {
            uploadButton.disabled = true;
          }

          if (data.pdfUrl) {
            showPdf(data.pdfUrl);
          }

          renderBotMessage(data);
        } catch (error) {
          renderBotMessage({
            botResponse: `Upload failed: ${error.message}`,
          });
        }
      },
      { once: true }
    );

    isFirstMessage = false;
    setLoading(false);
  }
}

function submitMessage() {
  const msg = cleanTextInput(input().value);
  if (!msg || isFirstMessage) {
    return;
  }

  renderUserMessage(msg);
  populateBotResponse(msg);
}

document.addEventListener("DOMContentLoaded", () => {
  if (sendBtn()) {
    sendBtn().disabled = true;
  }

  resetPdfViewer();

  input()?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitMessage();
    }
  });

  sendBtn()?.addEventListener("click", submitMessage);

  resetBtn()?.addEventListener("click", () => {
    messageList().innerHTML = "";
    responses = [];
    isFirstMessage = true;
    resetPdfViewer();
    populateBotResponse();
  });

  themeSwitch()?.addEventListener("change", () => {
    document.body.classList.toggle("dark-mode", themeSwitch().checked);
  });

  window.addEventListener("resize", syncPanelHeights);
  populateBotResponse();
});