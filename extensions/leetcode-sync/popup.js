const defaults = {
  backendBaseUrl: "http://127.0.0.1:8000",
  apiToken: ""
};

const elements = {
  backendBaseUrl: document.getElementById("backendBaseUrl"),
  apiToken: document.getElementById("apiToken"),
  status: document.getElementById("status"),
  saveButton: document.getElementById("saveButton")
};

function setStatus(message, type) {
  elements.status.textContent = message;
  elements.status.className = "status" + (type ? " is-" + type : "");
}

function normalizeBaseUrl(value) {
  return (value || "").trim().replace(/\/+$/, "");
}

async function loadSettings() {
  const stored = await chrome.storage.sync.get(defaults);
  elements.backendBaseUrl.value = stored.backendBaseUrl || defaults.backendBaseUrl;
  elements.apiToken.value = stored.apiToken || "";
}

async function saveSettings() {
  const backendBaseUrl = normalizeBaseUrl(elements.backendBaseUrl.value);
  const apiToken = elements.apiToken.value.trim();

  if (!backendBaseUrl || !apiToken) {
    setStatus("Backend URL and token are required.", "error");
    return;
  }

  await chrome.storage.sync.set({ backendBaseUrl, apiToken });
  setStatus("Saved. Accepted submissions will sync automatically.", "success");
}

document.addEventListener("DOMContentLoaded", function () {
  loadSettings();
  elements.saveButton.addEventListener("click", saveSettings);
});
