const GRAPHQL_ENDPOINT = "https://leetcode.com/graphql";
const ACCEPTED_STATUS = 10;
const MAX_SUBMISSION_AGE_MS = 5 * 60 * 1000;

const GET_SUBMISSIONS = [
  "query submissionList($offset: Int!, $limit: Int!, $lastKey: String, $questionSlug: String!, $lang: Int, $status: Int) {",
  "  questionSubmissionList(",
  "    offset: $offset",
  "    limit: $limit",
  "    lastKey: $lastKey",
  "    questionSlug: $questionSlug",
  "    lang: $lang",
  "    status: $status",
  "  ) {",
  "    submissions {",
  "      id",
  "      statusDisplay",
  "      timestamp",
  "    }",
  "  }",
  "}"
].join("\n");

const GET_SUBMISSION_DETAILS = [
  "query submissionDetails($submissionId: Int!) {",
  "  submissionDetails(submissionId: $submissionId) {",
  "    timestamp",
  "    statusCode",
  "    runtime",
  "    runtimeDisplay",
  "    memory",
  "    memoryDisplay",
  "    notes",
  "    lang {",
  "      name",
  "      verboseName",
  "    }",
  "    question {",
  "      questionId",
  "      questionFrontendId",
  "      title",
  "      titleSlug",
  "      difficulty",
  "      content",
  "      acRate",
  "      paidOnly: isPaidOnly",
  "      topicTags {",
  "        name",
  "        slug",
  "      }",
  "    }",
  "  }",
  "}"
].join("\n");

function getCookie(name) {
  const cookie = document.cookie
    .split(";")
    .map(function (entry) { return entry.trim(); })
    .find(function (entry) { return entry.indexOf(name + "=") === 0; });
  return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
}

async function leetCodeGraphQL(query, variables) {
  const response = await fetch(GRAPHQL_ENDPOINT, {
    method: "POST",
    credentials: "include",
    headers: {
      "content-type": "application/json",
      "x-csrftoken": getCookie("csrftoken"),
      "x-requested-with": "XMLHttpRequest"
    },
    body: JSON.stringify({ query: query, variables: variables })
  });

  if (!response.ok) {
    throw new Error("LeetCode request failed with " + response.status);
  }

  const payload = await response.json();
  if (payload.errors && payload.errors.length) {
    throw new Error(payload.errors[0].message || "LeetCode GraphQL error");
  }

  return payload.data;
}

function parsePositiveInteger(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const match = String(value).match(/(\d+)/);
  return match ? Number.parseInt(match[1], 10) : null;
}
function parseMemoryToKb(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "number") {
    return value;
  }

  const match = String(value).match(/([\d.]+)\s*([KMG]?B)?/i);
  if (!match) {
    return null;
  }

  const amount = Number.parseFloat(match[1]);
  const unit = (match[2] || "KB").toUpperCase();
  if (unit === "GB") {
    return Math.round(amount * 1024 * 1024);
  }
  if (unit === "MB") {
    return Math.round(amount * 1024);
  }
  return Math.round(amount);
}

async function getLatestAcceptedSubmission(questionSlug) {
  const submissionsData = await leetCodeGraphQL(GET_SUBMISSIONS, {
    questionSlug: questionSlug,
    limit: 1,
    offset: 0,
    lastKey: null,
    lang: null,
    status: ACCEPTED_STATUS
  });

  const submissions = submissionsData && submissionsData.questionSubmissionList
    ? submissionsData.questionSubmissionList.submissions || []
    : [];
  if (!submissions.length || !submissions[0].id) {
    return null;
  }

  const detailsData = await leetCodeGraphQL(GET_SUBMISSION_DETAILS, {
    submissionId: Number.parseInt(submissions[0].id, 10)
  });

  if (!detailsData || !detailsData.submissionDetails) {
    return null;
  }

  detailsData.submissionDetails.id = submissions[0].id;
  return detailsData.submissionDetails;
}

function isFreshSubmission(submission) {
  const timestamp = Number.parseInt(String((submission && submission.timestamp) || "0"), 10) * 1000;
  if (!timestamp) {
    return false;
  }
  return Date.now() - timestamp <= MAX_SUBMISSION_AGE_MS;
}

async function loadConfig() {
  return chrome.storage.sync.get({
    backendBaseUrl: "http://127.0.0.1:8000",
    apiToken: ""
  });
}
async function pushAcceptedSubmission(submission) {
  const config = await loadConfig();
  const backendBaseUrl = config.backendBaseUrl;
  const apiToken = config.apiToken;
  if (!backendBaseUrl || !apiToken) {
    throw new Error("Extension is not connected to LeetGram yet.");
  }

  const question = submission.question || {};
  const baseUrl = backendBaseUrl.replace(/\/+$/, "");
  const response = await fetch(baseUrl + "/api/integrations/leetcode/submissions/", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-leetgram-token": apiToken
    },
    body: JSON.stringify({
      submission_id: String(submission.id || submission.submissionId || submission.timestamp),
      status_code: submission.statusCode,
      status_display: submission.statusCode === ACCEPTED_STATUS ? "Accepted" : "Unknown",
      timestamp: Number.parseInt(String(submission.timestamp || "0"), 10),
      runtime_ms: parsePositiveInteger(submission.runtime || submission.runtimeDisplay),
      runtime_display: submission.runtimeDisplay || submission.runtime || "",
      memory_kb: parseMemoryToKb(submission.memory || submission.memoryDisplay),
      memory_display: submission.memoryDisplay || submission.memory || "",
      notes: submission.notes || "",
      lang: submission.lang ? (submission.lang.verboseName || submission.lang.name || "") : "",
      question: {
        question_id: String(question.questionId || ""),
        frontend_question_id: String(question.questionFrontendId || ""),
        title: question.title || "",
        title_slug: question.titleSlug || "",
        difficulty: question.difficulty || "",
        paid_only: Boolean(question.paidOnly),
        content: question.content || "",
        ac_rate: question.acRate || "",
        topic_tags: question.topicTags || []
      }
    })
  });

  if (!response.ok) {
    let errorPayload = {};
    try {
      errorPayload = await response.json();
    } catch (_error) {
      errorPayload = {};
    }
    throw new Error(errorPayload.detail || ("LeetGram sync failed with " + response.status));
  }

  return response.json();
}
chrome.runtime.onMessage.addListener(function (request, _sender, sendResponse) {
  if (!request || request.type !== "leetcode-submission-complete") {
    sendResponse({ status: "ignored" });
    return false;
  }

  (async function () {
    try {
      const submission = await getLatestAcceptedSubmission(request.questionSlug);
      if (!submission || submission.statusCode !== ACCEPTED_STATUS || !isFreshSubmission(submission)) {
        sendResponse({ status: "skipped" });
        return;
      }

      submission.id = submission.id || request.questionSlug;
      const result = await pushAcceptedSubmission(submission);
      chrome.runtime.sendMessage({ type: "sync-success", result: result });
      sendResponse({ status: "synced", result: result });
    } catch (error) {
      chrome.runtime.sendMessage({ type: "sync-error", message: error.message });
      sendResponse({ status: "error", message: error.message });
    }
  })();

  return true;
});



