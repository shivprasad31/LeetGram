const recentSubmissions = new Map();
const BADGE_TIMEOUT_MS = 5000;

function setBadge(text, color) {
  chrome.action.setBadgeBackgroundColor({ color });
  chrome.action.setBadgeText({ text });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), BADGE_TIMEOUT_MS);
}

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request?.type === "sync-success") {
    setBadge("OK", "#198754");
    sendResponse({ status: "ok" });
    return;
  }

  if (request?.type === "sync-error") {
    setBadge("!", "#dc3545");
    sendResponse({ status: "ok" });
    return;
  }

  sendResponse({ status: "ignored" });
});

chrome.webRequest.onCompleted.addListener(
  (details) => {
    if (details.method !== "POST" || !details.url.includes("/submit/") || details.tabId < 0) {
      return;
    }

    const questionSlug = details.url.match(/\/problems\/([^/]+)\/submit\//)?.[1];
    if (!questionSlug) {
      return;
    }

    const dedupeKey = `${details.tabId}:${questionSlug}`;
    const now = Date.now();
    const previous = recentSubmissions.get(dedupeKey);
    if (previous && now - previous < 15000) {
      return;
    }
    recentSubmissions.set(dedupeKey, now);

    setTimeout(() => {
      chrome.tabs.sendMessage(details.tabId, {
        type: "leetcode-submission-complete",
        questionSlug,
      });
    }, 4500);
  },
  {
    urls: ["https://leetcode.com/problems/*/submit/*"],
    types: ["xmlhttprequest"],
  }
);
