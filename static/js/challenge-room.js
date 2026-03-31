(() => {
  const room = document.querySelector("[data-challenge-room]");
  if (!room) {
    return;
  }

  const stateNode = document.getElementById("challenge-room-data");
  const starterNode = document.getElementById("challenge-starter-code");
  const templateNode = document.getElementById("challenge-starter-templates");
  const csrfToken =
    document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
    document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=")[1] ||
    "";

  const elements = {
    title: room.querySelector("[data-room-title]"),
    players: room.querySelector("[data-room-players]"),
    timer: room.querySelector("[data-room-timer]"),
    status: room.querySelector("[data-room-status]"),
    banner: room.querySelector("[data-room-alert]"),
    waitingPanel: room.querySelector("[data-waiting-panel]"),
    waitingTitle: room.querySelector("[data-waiting-title]"),
    waitingCopy: room.querySelector("[data-waiting-copy]"),
    spinner: room.querySelector("[data-waiting-spinner]"),
    countdown: room.querySelector("[data-room-countdown]"),
    loadingDots: room.querySelector("[data-loading-dots]"),
    workspace: room.querySelector("[data-workspace]"),
    submitButton: room.querySelector("[data-submit-button]"),
    runButton: room.querySelector("[data-run-button]"),
    forfeitButton: room.querySelector("[data-forfeit-button]"),
    formatButton: room.querySelector("[data-format-button]"),
    languageSelect: room.querySelector("[data-language-select]"),
    runStatus: room.querySelector("[data-run-status]"),
    editorShell: room.querySelector("[data-code-editor-shell]"),
    editorMount: room.querySelector("[data-code-editor]"),
    problemTitle: room.querySelector("[data-problem-title]"),
    problemDescription: room.querySelector("[data-problem-description]"),
    problemConstraints: room.querySelector("[data-problem-constraints]"),
    exampleList: room.querySelector("[data-example-list]"),
    testsPanel: room.querySelector('[data-room-tab-panel="tests"]'),
    outputPanel: room.querySelector('[data-room-tab-panel="output"]'),
    errorPanel: room.querySelector('[data-room-tab-panel="error"]'),
    tabButtons: Array.from(room.querySelectorAll("[data-room-tab]")),
    tabPanels: Array.from(room.querySelectorAll("[data-room-tab-panel]")),
    feed: room.querySelector("[data-submission-feed]"),
    resultPanel: room.querySelector("[data-result-panel]"),
    resultTitle: room.querySelector("[data-result-title]"),
    resultCopy: room.querySelector("[data-result-copy]"),
    pendingActions: room.querySelector("[data-pending-actions]"),
    localVideo: room.querySelector("[data-local-video]"),
    localCameraStatus: room.querySelector("[data-local-camera-status]"),
    opponentCameraStatus: room.querySelector("[data-opponent-camera-status]"),
    opponentCameraImage: room.querySelector("[data-opponent-camera-image]"),
    opponentCameraPlaceholder: room.querySelector("[data-opponent-camera-placeholder]"),
    cameraWarning: room.querySelector("[data-camera-warning]"),
    playerCards: {
      challenger: room.querySelector('[data-player-card="challenger"]'),
      opponent: room.querySelector('[data-player-card="opponent"]'),
    },
    playerStates: {
      challenger: room.querySelector('[data-player-state="challenger"]'),
      opponent: room.querySelector('[data-player-state="opponent"]'),
    },
  };

  let state = stateNode ? JSON.parse(stateNode.textContent) : null;
  const starterCode = starterNode ? JSON.parse(starterNode.textContent) : "";
  const starterTemplates = templateNode ? JSON.parse(templateNode.textContent) : {};
  const codeByLanguage = { ...starterTemplates, [state.language]: starterCode };

  let editorApi = null;
  let websocket = null;
  let websocketRetry = null;
  let refreshTimer = null;
  let presenceTimer = null;
  let localStream = null;
  let currentLanguage = state.language || "python";
  let presenceBusy = false;
  let executionBusy = false;
  let cameraReady = false;
  let countdownPlayed = false;
  let monacoPromise = null;
  let providersReady = false;

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const titleCase = (value) => (value ? value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ") : "");

  const formatDuration = (seconds) => {
    const safe = Math.max(0, Number(seconds || 0));
    return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
  };

  const simpleFormatCode = (language, code) => {
    const lines = String(code || "")
      .replaceAll("\r\n", "\n")
      .split("\n")
      .map((line) => line.replace(/\s+$/g, "").replaceAll("\t", "    "));
    if (language !== "java") {
      return lines.join("\n").trimEnd();
    }
    let indent = 0;
    return lines
      .map((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return "";
        }
        if (trimmed.startsWith("}")) {
          indent = Math.max(0, indent - 1);
        }
        const value = `${"    ".repeat(indent)}${trimmed}`;
        if (trimmed.endsWith("{")) {
          indent += 1;
        }
        return value;
      })
      .join("\n")
      .trimEnd();
  };

  const postJson = async (url, payload = {}) => {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data?.detail || data?.non_field_errors?.[0] || data?.message || "Request failed.");
    }
    return data;
  };

  const getJson = async (url) => {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data?.detail || "Unable to refresh challenge state.");
    }
    return data;
  };

  const setActiveTab = (tabName) => {
    elements.tabButtons.forEach((button) => button.classList.toggle("active", button.dataset.roomTab === tabName));
    elements.tabPanels.forEach((panel) => panel.classList.toggle("battle-room-hidden", panel.dataset.roomTabPanel !== tabName));
  };

  const setWarning = (message, tone = "warning") => {
    if (!message) {
      elements.cameraWarning.classList.add("battle-room-hidden");
      elements.cameraWarning.classList.remove("is-danger");
      elements.cameraWarning.textContent = "";
      return;
    }
    elements.cameraWarning.textContent = message;
    elements.cameraWarning.classList.remove("battle-room-hidden");
    elements.cameraWarning.classList.toggle("is-danger", tone === "danger");
  };

  const renderExecutionStatus = (message, loading = false) => {
    elements.runStatus.innerHTML = loading ? `<span class="battle-loader">${escapeHtml(message)}</span>` : escapeHtml(message);
  };

  const createFallbackEditor = () => {
    const textarea = document.createElement("textarea");
    textarea.className = "battle-editor-fallback";
    textarea.spellcheck = false;
    elements.editorMount.replaceChildren(textarea);
    return {
      getValue: () => textarea.value,
      setValue: (value) => {
        textarea.value = value;
      },
      setLanguage: (_, value) => {
        textarea.value = value;
      },
      setReadOnly: (readOnly) => {
        textarea.disabled = readOnly;
      },
      format: () => {
        textarea.value = simpleFormatCode(currentLanguage, textarea.value);
      },
      focus: () => textarea.focus(),
      dispose: () => {},
    };
  };

  const ensureMonaco = () => {
    if (window.monaco?.editor) {
      return Promise.resolve(window.monaco);
    }
    if (monacoPromise) {
      return monacoPromise;
    }
    if (typeof window.require !== "function" || !window.CODEARENA_MONACO_CDN) {
      return Promise.reject(new Error("Monaco unavailable"));
    }
    monacoPromise = new Promise((resolve, reject) => {
      window.require.config({ paths: { vs: window.CODEARENA_MONACO_CDN } });
      window.require(["vs/editor/editor.main"], () => resolve(window.monaco), reject);
    });
    return monacoPromise;
  };

  const initEditor = async () => {
    try {
      const monaco = await ensureMonaco();
      if (!providersReady) {
        ["python", "java"].forEach((language) => {
          monaco.languages.registerDocumentFormattingEditProvider(language, {
            provideDocumentFormattingEdits(model) {
              return [{ range: model.getFullModelRange(), text: simpleFormatCode(language, model.getValue()) }];
            },
          });
        });
        providersReady = true;
      }

      const models = {};
      const getModel = (language) => {
        if (!models[language]) {
          models[language] = monaco.editor.createModel(
            codeByLanguage[language] || starterTemplates[language] || "",
            language
          );
        }
        return models[language];
      };

      const editor = monaco.editor.create(elements.editorMount, {
        model: getModel(currentLanguage),
        automaticLayout: true,
        fontFamily: "'Fira Code', Consolas, monospace",
        fontSize: 14,
        lineHeight: 22,
        minimap: { enabled: false },
        padding: { top: 16, bottom: 16 },
        roundedSelection: true,
        scrollBeyondLastLine: false,
        tabSize: 4,
        insertSpaces: true,
        theme: "vs-dark",
        wordWrap: "on",
      });

      editorApi = {
        getValue: () => editor.getValue(),
        setValue: (value) => editor.getModel()?.setValue(value),
        setLanguage: (language, value) => {
          const model = getModel(language);
          editor.setModel(model);
          if (typeof value === "string") {
            model.setValue(value);
          }
        },
        setReadOnly: (readOnly) => editor.updateOptions({ readOnly }),
        format: () => editor.getAction("editor.action.formatDocument").run(),
        focus: () => editor.focus(),
        dispose: () => {
          editor.dispose();
          Object.values(models).forEach((model) => model.dispose());
        },
      };
    } catch (error) {
      console.warn("Monaco failed, using fallback editor.", error);
      editorApi = createFallbackEditor();
    }

    editorApi.setValue(codeByLanguage[currentLanguage] || starterTemplates[currentLanguage] || starterCode);
  };

  const getEditorValue = () => editorApi?.getValue?.() || "";
  const setEditorReadOnly = (readOnly) => {
    editorApi?.setReadOnly?.(readOnly);
    elements.editorShell.classList.toggle("is-disabled", readOnly);
  };

  const renderSampleCases = (samples) => {
    if (!samples?.length) {
      elements.testsPanel.innerHTML = '<p class="battle-meta mb-0">No sample cases available yet.</p>';
      elements.exampleList.innerHTML = '<p class="battle-meta mb-0">Examples unlock when the battle starts.</p>';
      return;
    }
    const html = samples
      .map(
        (item, index) => `
          <div class="battle-case">
            <div class="battle-case-status">Sample ${index + 1}</div>
            <div class="mt-2 small text-uppercase battle-meta">Input</div>
            <pre>${escapeHtml(item.input)}</pre>
            <div class="small text-uppercase battle-meta">Expected Output</div>
            <pre>${escapeHtml(item.output)}</pre>
          </div>
        `
      )
      .join("");
    elements.testsPanel.innerHTML = html;
    elements.exampleList.innerHTML = html;
  };

  const renderCaseResults = (results) => {
    if (!results?.length) {
      renderSampleCases(state.problem.examples || []);
      return;
    }
    elements.testsPanel.innerHTML = results
      .map(
        (item) => `
          <div class="battle-case ${item.passed ? "is-passed" : "is-failed"}">
            <div class="battle-case-status ${item.passed ? "is-passed" : "is-failed"}">
              ${item.passed ? "Passed" : "Failed"} · Case ${item.index}
            </div>
            <div class="mt-2 small text-uppercase battle-meta">Input</div>
            <pre>${escapeHtml(item.input)}</pre>
            <div class="small text-uppercase battle-meta">Expected Output</div>
            <pre>${escapeHtml(item.expected_output)}</pre>
            <div class="small text-uppercase battle-meta">Actual Output</div>
            <pre>${escapeHtml(item.actual_output)}</pre>
            ${
              item.error_output
                ? `<div class="small text-uppercase battle-meta">Error</div><pre>${escapeHtml(item.error_output)}</pre>`
                : ""
            }
          </div>
        `
      )
      .join("");
  };

  const renderFeed = (submissions) => {
    if (!submissions?.length) {
      elements.feed.innerHTML = `
        <div class="battle-feed-row">
          <div>
            <strong>No submissions yet</strong>
            <div class="battle-meta">The duel feed will update during the battle.</div>
          </div>
        </div>
      `;
      return;
    }
    elements.feed.innerHTML = submissions
      .map(
        (item) => `
          <div class="battle-feed-row">
            <div>
              <strong>${escapeHtml(item.username)}</strong>
              <div class="battle-meta">${titleCase(item.verdict)} · ${escapeHtml(item.language)} · ${item.time_taken_seconds}s elapsed</div>
            </div>
            <div class="battle-chip">${Number(item.execution_time || 0).toFixed(4)}s</div>
          </div>
        `
      )
      .join("");
  };

  const renderResult = (result) => {
    if (!result) {
      elements.resultPanel.classList.add("battle-room-hidden");
      return;
    }
    elements.resultPanel.classList.remove("battle-room-hidden");
    if (result.finish_reason === "disqualified" && result.violating_user_name) {
      elements.resultTitle.textContent = `${result.winner_name} wins by disqualification`;
      elements.resultCopy.textContent = `${result.violating_user_name} lost camera monitoring.`;
      return;
    }
    if (result.finish_reason === "forfeited" && result.violating_user_name) {
      elements.resultTitle.textContent = `${result.winner_name} wins by forfeit`;
      elements.resultCopy.textContent = `${result.violating_user_name} exited the challenge.`;
      return;
    }
    elements.resultTitle.textContent = `${result.winner_name} wins`;
    elements.resultCopy.textContent = `Winning time: ${result.time_taken}s.`;
  };

  const renderPlayerStrip = () => {
    const joinedMap = {
      challenger: Boolean(state.challenger_joined_at),
      opponent: Boolean(state.opponent_joined_at),
    };
    const cameraMap = {
      challenger: state.viewer_role === "challenger" ? state.monitoring.current_user_camera_active : state.monitoring.opponent_camera_active,
      opponent: state.viewer_role === "opponent" ? state.monitoring.current_user_camera_active : state.monitoring.opponent_camera_active,
    };
    ["challenger", "opponent"].forEach((role) => {
      const card = elements.playerCards[role];
      const label = elements.playerStates[role];
      const participantId = role === "challenger" ? state.challenger_id : state.opponent_id;
      card.classList.remove("is-live", "is-waiting", "is-off");
      if (state.result?.violating_user_id === participantId) {
        card.classList.add("is-off");
        label.textContent = state.result.finish_reason === "forfeited" ? "Exited" : "Disqualified";
        return;
      }
      if (state.status === "finished") {
        label.textContent = state.result?.winner_id === participantId ? "Winner" : "Finished";
        card.classList.add(state.result?.winner_id === participantId ? "is-live" : "is-waiting");
        return;
      }
      if (joinedMap[role] && state.status === "active") {
        card.classList.add(cameraMap[role] ? "is-live" : "is-waiting");
        label.textContent = cameraMap[role] ? "Live" : "Joined";
        return;
      }
      if (joinedMap[role]) {
        card.classList.add("is-waiting");
        label.textContent = "Ready";
        return;
      }
      card.classList.add("is-off");
      label.textContent = "Waiting";
    });
  };

  const renderMonitor = () => {
    elements.localCameraStatus.textContent = cameraReady ? "Active" : "Not ready";
    const opponentSnapshot = state.monitoring?.opponent_snapshot;
    const opponentActive = Boolean(state.monitoring?.opponent_camera_active);
    elements.opponentCameraStatus.textContent = opponentActive ? "Active" : "Offline";
    if (opponentSnapshot) {
      elements.opponentCameraImage.src = opponentSnapshot;
      elements.opponentCameraImage.classList.remove("battle-room-hidden");
      elements.opponentCameraPlaceholder.classList.add("battle-room-hidden");
      return;
    }
    elements.opponentCameraImage.classList.add("battle-room-hidden");
    elements.opponentCameraPlaceholder.classList.remove("battle-room-hidden");
  };

  const updateTimer = () => {
    if (!state.start_time) {
      elements.timer.textContent = "Waiting";
      return;
    }
    const start = new Date(state.start_time);
    const end = state.end_time ? new Date(state.end_time) : new Date();
    elements.timer.textContent = formatDuration(Math.floor((end.getTime() - start.getTime()) / 1000));
  };

  const showWorkspace = () => {
    elements.waitingPanel.classList.add("battle-room-hidden");
    elements.workspace.classList.remove("battle-room-hidden");
  };

  const showWaitingPanel = () => {
    elements.workspace.classList.add("battle-room-hidden");
    elements.waitingPanel.classList.remove("battle-room-hidden");
  };

  const updateButtons = () => {
    const canWork = state.can_submit && state.can_view_problem && cameraReady && state.status === "active" && !executionBusy;
    setEditorReadOnly(!canWork);
    elements.languageSelect.disabled = !state.can_view_problem || state.status === "finished" || executionBusy;
    elements.formatButton.disabled = !state.can_view_problem || executionBusy;
    elements.runButton.disabled = !canWork;
    elements.submitButton.disabled = !canWork;
    elements.forfeitButton.disabled = !state.can_forfeit || executionBusy;
  };

  const renderProblem = () => {
    if (state.can_view_problem) {
      elements.problemTitle.textContent = state.problem.title || "Untitled Problem";
      elements.problemDescription.textContent = state.problem.description || "No problem statement available.";
      elements.problemConstraints.textContent = state.problem.constraints || "No constraints available.";
      renderSampleCases(state.problem.examples || []);
      return;
    }
    elements.problemTitle.textContent = "Locked until both players are ready";
    elements.problemDescription.textContent = "The problem and tests are unlocked only after the challenge starts.";
    elements.problemConstraints.textContent = "";
    renderSampleCases([]);
  };

  const renderState = (nextState) => {
    const previousStatus = state?.status;
    state = nextState;
    if (!codeByLanguage[currentLanguage]) {
      codeByLanguage[currentLanguage] = starterTemplates[currentLanguage] || "";
    }

    elements.title.textContent = state.challenge_title;
    elements.players.textContent = `${state.challenger_name} vs ${state.opponent_name}`;
    elements.status.textContent = titleCase(state.status);
    elements.banner.textContent = state.waiting_message || "Challenge room updated.";
    elements.waitingTitle.textContent =
      state.status === "pending"
        ? "Waiting for acceptance"
        : state.status === "accepted"
          ? "Loading players into room"
          : state.status === "active"
            ? "Battle starting"
            : state.status === "finished"
              ? "Battle finished"
              : "Challenge update";
    elements.waitingCopy.textContent = state.waiting_message || "";
    if (elements.pendingActions) {
      elements.pendingActions.classList.toggle("battle-room-hidden", !state.can_accept);
    }

    elements.languageSelect.value = currentLanguage;
    renderProblem();
    renderFeed(state.latest_submissions || []);
    renderResult(state.result);
    renderPlayerStrip();
    renderMonitor();
    updateTimer();
    updateButtons();

    if (state.latest_submission && !executionBusy) {
      elements.outputPanel.textContent = state.latest_submission.output || "No output.";
      elements.errorPanel.textContent = state.latest_submission.error_output || "No errors.";
    }

    if (state.status === "finished") {
      showWorkspace();
      countdownPlayed = true;
      elements.spinner.classList.add("battle-room-hidden");
      elements.loadingDots.classList.add("battle-room-hidden");
      elements.countdown.classList.add("battle-room-hidden");
      return;
    }
    if (state.status === "active") {
      if (previousStatus !== "active" && !countdownPlayed) {
        startCountdown();
        return;
      }
      showWorkspace();
      elements.spinner.classList.add("battle-room-hidden");
      elements.loadingDots.classList.add("battle-room-hidden");
      elements.countdown.classList.add("battle-room-hidden");
      return;
    }
    showWaitingPanel();
    elements.spinner.classList.toggle("battle-room-hidden", state.status === "finished");
    elements.loadingDots.classList.toggle("battle-room-hidden", state.status !== "accepted");
    elements.countdown.classList.add("battle-room-hidden");
  };

  const startCountdown = () => {
    countdownPlayed = true;
    showWaitingPanel();
    elements.spinner.classList.add("battle-room-hidden");
    elements.loadingDots.classList.remove("battle-room-hidden");
    elements.countdown.classList.remove("battle-room-hidden");
    let value = Number(state.countdown_seconds || 3);
    elements.countdown.textContent = String(value);
    const interval = window.setInterval(() => {
      value -= 1;
      if (value <= 0) {
        elements.countdown.textContent = "GO";
        window.clearInterval(interval);
        window.setTimeout(() => {
          elements.countdown.classList.add("battle-room-hidden");
          elements.loadingDots.classList.add("battle-room-hidden");
          showWorkspace();
          updateButtons();
          editorApi?.focus?.();
        }, 700);
        return;
      }
      elements.countdown.textContent = String(value);
    }, 1000);
  };

  const captureSnapshot = () => {
    if (!localStream || !elements.localVideo.videoWidth || !elements.localVideo.videoHeight) {
      return "";
    }
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 240;
    canvas.getContext("2d").drawImage(elements.localVideo, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.65);
  };

  const sendPresence = async (cameraActive, includeSnapshot = true) => {
    if (presenceBusy) {
      return;
    }
    presenceBusy = true;
    try {
      const payload = { camera_active: cameraActive };
      if (cameraActive && includeSnapshot) {
        payload.snapshot_data = captureSnapshot();
      }
      renderState(await postJson(room.dataset.presenceUrl, payload));
    } catch (error) {
      console.error(error);
    } finally {
      presenceBusy = false;
    }
  };

  const initCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setWarning("Camera monitoring is not supported by this browser.", "danger");
      return;
    }
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      cameraReady = true;
      elements.localVideo.srcObject = localStream;
      updateButtons();
      setWarning("");
      localStream.getTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          cameraReady = false;
          updateButtons();
          setWarning("Your camera stopped. The challenge will end immediately.", "danger");
          sendPresence(false, false);
        });
      });
      await sendPresence(true, true);
      presenceTimer = window.setInterval(() => {
        if (cameraReady && state.status !== "finished" && state.status !== "rejected") {
          sendPresence(true, true);
        }
      }, 4000);
    } catch (error) {
      cameraReady = false;
      updateButtons();
      setWarning("Camera access is required during the battle. Blocking it will disqualify you.", "danger");
      if (state.status === "accepted" || state.status === "active") {
        sendPresence(false, false);
      }
    }
  };

  const refreshState = async () => {
    try {
      renderState(await getJson(room.dataset.resultUrl));
    } catch (error) {
      console.error(error);
    }
  };

  const connectWebSocket = () => {
    if (!room.dataset.websocketUrl || websocket || state.status === "finished" || state.status === "rejected") {
      return;
    }
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    websocket = new WebSocket(`${protocol}://${window.location.host}${room.dataset.websocketUrl}`);
    websocket.addEventListener("message", refreshState);
    websocket.addEventListener("close", () => {
      websocket = null;
      if (state.status !== "finished" && state.status !== "rejected") {
        websocketRetry = window.setTimeout(connectWebSocket, 2500);
      }
    });
  };

  const joinRoom = async () => {
    if (!state.can_join || state.status === "finished" || state.status === "rejected") {
      return;
    }
    try {
      renderState(await postJson(room.dataset.startUrl, {}));
    } catch (error) {
      console.error(error);
    }
  };

  const sendMonitoringEvent = async (eventType, metadata = {}) => {
    try {
      await postJson(room.dataset.eventsUrl, { event_type: eventType, metadata });
    } catch (error) {
      console.error(error);
    }
  };

  const runExecution = async (mode) => {
    const code = getEditorValue();
    codeByLanguage[currentLanguage] = code;
    executionBusy = true;
    updateButtons();
    renderExecutionStatus(mode === "submit" ? "Submitting code..." : "Running code...", true);
    try {
      const response =
        mode === "submit"
          ? await postJson(room.dataset.submitUrl, { code, language: currentLanguage })
          : await postJson(room.dataset.runCodeUrl, { code, language: currentLanguage, problem_id: state.problem_id });
      renderCaseResults(response.results || []);
      elements.outputPanel.textContent = response.output || "No output.";
      elements.errorPanel.textContent = response.error_output || "No errors.";
      renderExecutionStatus(
        response.supported === false
          ? response.error_output || `${titleCase(currentLanguage)} is not supported yet.`
          : `${response.passed_count ?? 0} passed · ${response.failed_count ?? 0} failed · ${(response.execution_time || 0).toFixed(4)}s`
      );
      setActiveTab(response.error_output ? "error" : "tests");
      if (mode === "submit") {
        await refreshState();
        renderCaseResults(response.results || []);
      }
    } catch (error) {
      elements.errorPanel.textContent = error.message;
      renderExecutionStatus(error.message);
      setActiveTab("error");
    } finally {
      executionBusy = false;
      updateButtons();
    }
  };

  elements.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.roomTab));
  });

  elements.languageSelect.addEventListener("change", async () => {
    codeByLanguage[currentLanguage] = getEditorValue();
    currentLanguage = elements.languageSelect.value;
    const nextCode = codeByLanguage[currentLanguage] || starterTemplates[currentLanguage] || "";
    editorApi?.setLanguage?.(currentLanguage, nextCode);
    await editorApi?.format?.();
    renderExecutionStatus(`Language switched to ${elements.languageSelect.options[elements.languageSelect.selectedIndex].text}.`);
  });

  elements.formatButton.addEventListener("click", async () => {
    if (elements.formatButton.disabled) {
      return;
    }
    await editorApi?.format?.();
    codeByLanguage[currentLanguage] = getEditorValue();
    renderExecutionStatus(`Formatted ${titleCase(currentLanguage)} code.`);
  });

  elements.runButton.addEventListener("click", async () => {
    if (!elements.runButton.disabled) {
      await runExecution("run");
    }
  });

  elements.submitButton.addEventListener("click", async () => {
    if (!elements.submitButton.disabled) {
      await runExecution("submit");
    }
  });

  elements.forfeitButton.addEventListener("click", async () => {
    if (elements.forfeitButton.disabled) {
      return;
    }
    if (!window.confirm("Exit challenge and forfeit? Your opponent will be declared the winner.")) {
      return;
    }
    executionBusy = true;
    updateButtons();
    renderExecutionStatus("Exiting challenge...", true);
    try {
      renderState(await postJson(room.dataset.forfeitUrl, {}));
      renderExecutionStatus("Challenge forfeited.");
    } catch (error) {
      elements.errorPanel.textContent = error.message;
      renderExecutionStatus(error.message);
      setActiveTab("error");
    } finally {
      executionBusy = false;
      updateButtons();
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && state.status === "active") {
      sendMonitoringEvent("tab_switch", { hidden: true });
      setWarning("Tab switch detected. Stay focused on the challenge room.");
    }
  });

  window.addEventListener("blur", () => {
    if (state.status === "active") {
      sendMonitoringEvent("window_blur", { blurred: true });
      setWarning("Window focus lost. Monitoring event logged.");
    }
  });

  const boot = async () => {
    await initEditor();
    renderState(state);
    setActiveTab("tests");
    renderExecutionStatus("Execution output will appear after you run or submit code.");
    await editorApi?.format?.();
    initCamera().catch((error) => console.error(error));
    joinRoom().catch((error) => console.error(error));
    connectWebSocket();
    refreshTimer = window.setInterval(refreshState, 8000);
  };

  boot().catch((error) => console.error(error));

  window.addEventListener("beforeunload", () => {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
    }
    if (presenceTimer) {
      window.clearInterval(presenceTimer);
    }
    if (websocketRetry) {
      window.clearTimeout(websocketRetry);
    }
    if (websocket) {
      websocket.close();
    }
    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
    }
    editorApi?.dispose?.();
  });
})();
