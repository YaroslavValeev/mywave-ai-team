(function () {
  const root = document.getElementById("office-app");
  if (!root) return;

  const apiKeyQuery = root.dataset.apiKeyQuery || "";
  const storageKey = "mywave.office.last-task-id";
  const initialTaskId = Number(root.dataset.initialTaskId || "") || parseTaskIdFromLocation() || restoreStoredTaskId();
  const POLL_INTERVALS = {
    officeEvents: 8000,
    tasks: 15000,
    health: 30000,
    taskEvents: 4000,
  };
  const STRUCTURAL_EVENTS = new Set([
    "triage_done",
    "pipeline_done",
    "roundtable_done",
    "orchestration_done",
    "orchestration_error",
    "pipeline_background_started",
    "pipeline_background_completed",
    "pipeline_background_stopped",
    "pipeline_background_failed",
    "OWNER_APPROVED",
    "OWNER_REWORK",
    "OWNER_CLARIFY",
    "OWNER_MERGED",
  ]);
  const OVERVIEW_VIEWS = new Set(["office", "missions", "control"]);
  const ACTIVE_WORK_STATUSES = new Set(["TRIAGED", "IN_PIPELINE", "IN_ROUNDTABLE", "IN_COURT"]);
  const FINAL_STATUSES = new Set(["DONE", "ARCHIVED"]);

  const state = {
    selectedTaskId: initialTaskId || null,
    tasks: [],
    health: null,
    scene: null,
    unifiedThread: null,
    docs: [],
    officeFeed: [],
    taskFeed: [],
    view: initialTaskId ? "task" : "office",
    loading: false,
    toast: "",
    drafts: {
      missionChat: "",
      taskComposer: "",
    },
    uploads: {
      taskComposerFiles: [],
      missionFiles: [],
    },
    compose: {
      activeField: "",
      lockUntil: 0,
    },
    stale: {
      scope: "",
      message: "",
    },
    live: {
      officeLastEventId: 0,
      taskLastEventId: 0,
      taskFeedBadgeCount: 0,
      shouldScrollTaskFeed: false,
      overviewBusy: false,
      taskBusy: false,
      lastTaskSyncAt: "",
      lastOfficeSyncAt: "",
      userPaused: false,
    },
  };

  const pollers = {};
  const stageOrder = ["NEW", "TRIAGED", "IN_PIPELINE", "IN_ROUNDTABLE", "IN_COURT", "WAIT_OWNER", "APPROVED_WAIT_MERGE", "DONE"];
  const stageLabels = {
    NEW: "Новая",
    TRIAGED: "Разбор",
    IN_PIPELINE: "Исполнение",
    IN_ROUNDTABLE: "Совещание",
    IN_COURT: "Суд",
    WAIT_OWNER: "Ждёт владельца",
    APPROVED_WAIT_MERGE: "Ждёт merge",
    NEED_INFO: "Нужно уточнение",
    REWORK: "Доработка",
    DONE: "Готово",
    ARCHIVED: "Архив",
  };
  const zoneLabels = {
    reception: "Приёмная",
    strategy: "Разбор",
    worklane: "Рабочий коридор",
    design: "Дизайн-зона",
    frontend: "Frontend-зона",
    backend: "Backend-зона",
    architecture: "Архитектурный стол",
    qa: "Контроль качества",
    meeting: "Переговорная",
    court: "Суд решений",
    owner: "Стол владельца",
    archive: "Архив",
    ops: "Ops-панель",
    content: "Контент-студия",
    analytics: "Аналитика",
    operations: "Операционный стол",
    lab: "AI-лаборатория",
    management: "PM-зона",
    delivery: "Delivery-зона",
  };
  const PERSONA_GLYPHS = {
    COORDINATOR: "CO",
    PS: "PS",
    PM: "PM",
    UX: "UX",
    FE: "FE",
    BE: "BE",
    ARCH: "AR",
    QA: "QA",
    DEVOPS: "OP",
    RC: "RC",
    SEC: "SC",
    LEGAL: "LG",
    FIN: "FN",
    JUDGE: "JD",
    OWNER: "OW",
  };
  const STATUS_TO_PERSONA = {
    NEW: "COORDINATOR",
    TRIAGED: "PS",
    IN_PIPELINE: "PM",
    IN_ROUNDTABLE: "RC",
    IN_COURT: "JUDGE",
    WAIT_OWNER: "OWNER",
    APPROVED_WAIT_MERGE: "OWNER",
    NEED_INFO: "OWNER",
    REWORK: "PM",
    DONE: "OWNER",
    ARCHIVED: "OWNER",
  };
  const FALLBACK_PERSONAS = {
    COORDINATOR: { code: "COORDINATOR", label: "Координатор", zone: "reception", animation: "accept" },
    PS: { code: "PS", label: "Продуктовый стратег", zone: "strategy", animation: "think" },
    PM: { code: "PM", label: "Менеджер поставки", zone: "management", animation: "brief" },
    UX: { code: "UX", label: "UX-дизайнер", zone: "design", animation: "sketch" },
    FE: { code: "FE", label: "Frontend инженер", zone: "frontend", animation: "build" },
    BE: { code: "BE", label: "Backend инженер", zone: "backend", animation: "build" },
    ARCH: { code: "ARCH", label: "Архитектор", zone: "architecture", animation: "review" },
    QA: { code: "QA", label: "QA ревьюер", zone: "qa", animation: "review" },
    DEVOPS: { code: "DEVOPS", label: "DevOps инженер", zone: "ops", animation: "ops" },
    RC: { code: "RC", label: "Проверка реальности", zone: "meeting", animation: "debate" },
    SEC: { code: "SEC", label: "Security ревьюер", zone: "meeting", animation: "review" },
    LEGAL: { code: "LEGAL", label: "Юрист", zone: "meeting", animation: "review" },
    FIN: { code: "FIN", label: "Финансовый аналитик", zone: "meeting", animation: "review" },
    JUDGE: { code: "JUDGE", label: "Судья", zone: "court", animation: "decide" },
    OWNER: { code: "OWNER", label: "Владелец", zone: "owner", animation: "approve" },
  };

  function parseTaskIdFromLocation() {
    const match = window.location.pathname.match(/^\/office\/tasks\/(\d+)$/);
    return match ? Number(match[1]) : null;
  }

  function restoreStoredTaskId() {
    try {
      const value = window.localStorage.getItem(storageKey);
      return value ? Number(value) : null;
    } catch (_) {
      return null;
    }
  }

  function rememberTaskId(taskId) {
    if (!taskId) return;
    try {
      window.localStorage.setItem(storageKey, String(taskId));
    } catch (_) {}
  }

  function clampSelection(value, position) {
    const safeValue = String(value || "");
    const fallback = safeValue.length;
    if (typeof position !== "number" || Number.isNaN(position)) return fallback;
    return Math.max(0, Math.min(position, fallback));
  }

  function captureDraftSnapshot() {
    const missionInput = root.querySelector("#mission-chat-input");
    const taskComposerInput = root.querySelector("#task-composer-input");
    if (missionInput) state.drafts.missionChat = missionInput.value;
    if (taskComposerInput) state.drafts.taskComposer = taskComposerInput.value;

    const active = document.activeElement;
    if (!active || !root.contains(active)) return null;

    return {
      activeId: active.id || "",
      selectionStart: typeof active.selectionStart === "number" ? active.selectionStart : null,
      selectionEnd: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
    };
  }

  function restoreDraftSnapshot(snapshot) {
    const missionInput = root.querySelector("#mission-chat-input");
    const taskComposerInput = root.querySelector("#task-composer-input");

    if (missionInput) missionInput.value = state.drafts.missionChat || "";
    if (taskComposerInput) taskComposerInput.value = state.drafts.taskComposer || "";

    if (!snapshot?.activeId) return;
    const target = root.querySelector(`#${snapshot.activeId}`);
    if (!target || target.disabled || typeof target.focus !== "function") return;

    target.focus({ preventScroll: true });
    if (typeof target.setSelectionRange === "function") {
      const value = String(target.value || "");
      const start = clampSelection(value, snapshot.selectionStart);
      const end = clampSelection(value, snapshot.selectionEnd);
      target.setSelectionRange(start, end);
    }
  }

  function markComposeActivity(fieldId) {
    state.compose.activeField = fieldId || "";
    state.compose.lockUntil = Date.now() + 12000;
  }

  function clearComposeActivity(fieldId) {
    if (!fieldId || state.compose.activeField === fieldId) {
      state.compose.activeField = "";
      state.compose.lockUntil = 0;
    }
  }

  function isComposeLocked() {
    return Boolean(state.compose.activeField) && Date.now() < state.compose.lockUntil;
  }

  function officeUrl() {
    return `/office${apiKeyQuery}`;
  }

  function taskUrl(taskId) {
    return `/office/tasks/${taskId}${apiKeyQuery}`;
  }

  function syncHistory(mode) {
    if (!mode) return;
    const next = state.selectedTaskId && ["task", "docs"].includes(state.view)
      ? taskUrl(state.selectedTaskId)
      : officeUrl();
    const current = `${window.location.pathname}${window.location.search}`;
    if (current === next) return;
    window.history[mode === "replace" ? "replaceState" : "pushState"]({}, "", next);
  }

  function apiUrl(path) {
    const separator = path.includes("?") ? "&" : "?";
    const apiKey = new URLSearchParams(apiKeyQuery.replace(/^\?/, "")).get("api_key") || "";
    return `${path}${separator}api_key=${encodeURIComponent(apiKey)}`;
  }

  function taskDocumentUrl(document, mode = "view") {
    if (!state.selectedTaskId || !document?.key) return "#";
    const suffix = mode === "download" ? "/download" : "";
    return `/tasks/${state.selectedTaskId}/documents/${encodeURIComponent(document.key)}${suffix}${apiKeyQuery}`;
  }

  async function fetchJson(path, options) {
    const response = await fetch(apiUrl(path), {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return response.json();
  }

  function selectedUploadNames(files) {
    return (files || []).map((file) => file.name);
  }

  function renderUploadSelection(files, emptyText) {
    const names = selectedUploadNames(files);
    if (!names.length) {
      return `<div class="upload-empty">${escapeHtml(emptyText)}</div>`;
    }
    return `
      <div class="upload-file-list">
        ${names.map((name) => `<span class="tag upload-file-chip">${escapeHtml(name)}</span>`).join("")}
      </div>
    `;
  }

  function bytesToBase64(bytes) {
    let binary = "";
    const chunkSize = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      const chunk = bytes.subarray(offset, offset + chunkSize);
      binary += String.fromCharCode(...chunk);
    }
    return window.btoa(binary);
  }

  async function filesToPayload(files) {
    const payload = [];
    for (const file of files || []) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      payload.push({
        name: file.name,
        content_base64: bytesToBase64(bytes),
      });
    }
    return payload;
  }

  async function uploadMissionFiles(taskId, files) {
    if (!taskId || !(files || []).length) return { uploaded: [] };
    return fetchJson(`/api/tasks/${taskId}/attachments/upload`, {
      method: "POST",
      body: JSON.stringify({ files: await filesToPayload(files) }),
    });
  }

  function setToast(message) {
    state.toast = message;
    render();
    if (!message) return;
    window.setTimeout(() => {
      if (state.toast === message) {
        state.toast = "";
        render();
      }
    }, 3200);
  }

  function setStale(scope, message) {
    state.stale = { scope, message };
    render();
  }

  function clearStale(scope) {
    if (!scope || state.stale.scope === scope) {
      state.stale = { scope: "", message: "" };
    }
  }

  function scrollToTarget(targetId) {
    const target = root.querySelector(`#${targetId}`);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function mergeEvents(existing, incoming, maxItems) {
    const map = new Map(existing.map((event) => [event.id, event]));
    incoming.forEach((event) => map.set(event.id, event));
    const merged = Array.from(map.values()).sort((a, b) => a.id - b.id);
    return typeof maxItems === "number" ? merged.slice(-maxItems) : merged;
  }

  function lookupPersona(code) {
    if (!code) return FALLBACK_PERSONAS.COORDINATOR;
    const livePersona = state.scene?.cast?.find((persona) => persona.code === code);
    return livePersona || FALLBACK_PERSONAS[code] || { code, label: code, zone: "worklane", animation: "think" };
  }

  function personaGlyph(code) {
    return PERSONA_GLYPHS[code] || String(code || "??").slice(0, 2).toUpperCase();
  }

  function personaTone(persona) {
    const zone = persona?.zone;
    if (["frontend", "backend", "delivery"].includes(zone)) return "build";
    if (["meeting", "court"].includes(zone)) return "debate";
    if (["owner", "archive"].includes(zone)) return "owner";
    if (["ops", "lab", "analytics"].includes(zone)) return "ops";
    return "plan";
  }

  function renderPersonaAvatar(persona, options = {}) {
    const { current = false, compact = false } = options;
    const tone = personaTone(persona);
    const classes = [
      "persona-avatar",
      `tone-${tone}`,
      current ? "is-current" : "",
      compact ? "is-compact" : "",
    ].filter(Boolean).join(" ");
    return `<div class="${classes}" aria-hidden="true"><span>${escapeHtml(personaGlyph(persona?.code))}</span></div>`;
  }

  function personaForTask(task) {
    return lookupPersona(STATUS_TO_PERSONA[task?.status] || "COORDINATOR");
  }

  function thoughtForPersona(persona, isCurrent) {
    const handoff = state.scene?.handoffs?.find((item) => item.step_name === persona.code);
    return handoff?.payload?.summary?.[0] || fallbackThought(persona.code, isCurrent);
  }

  function eventPersona(event) {
    const code = event.event_type && event.event_type.startsWith("OWNER_")
      ? "OWNER"
      : event.event_type === "triage_done"
        ? "COORDINATOR"
        : event.event_type === "pipeline_done"
          ? "PM"
          : event.event_type === "roundtable_done"
            ? "RC"
            : event.event_type === "orchestration_done"
              ? "JUDGE"
              : event.event_type === "orchestration_error"
                ? "SEC"
                : STATUS_TO_PERSONA[event.status_after] || "COORDINATOR";
    return lookupPersona(code);
  }

  function renderStageHero(task, scene, currentActor) {
    const focusPersona = currentActor || personaForTask(task);
    const focusThought = thoughtForPersona(focusPersona, true);
    const cast = state.scene?.cast || [];
    return `
      <section class="stage-hero stage-zone-${escapeHtml(scene.zone || "worklane")}">
        <div class="stage-copy">
          <div class="stage-kicker">Штаб в движении</div>
          <div class="stage-title">${escapeHtml(scene.title)}</div>
          <div class="stage-subtitle">${escapeHtml(scene.subtitle)}</div>
          <div class="scene-meta">
            <span class="tag">Фаза: ${escapeHtml(stageLabels[task.status] || task.status)}</span>
            <span class="tag">Зона: ${escapeHtml(zoneLabels[scene.zone] || scene.zone || "Штаб")}</span>
          </div>
        </div>
        <div class="stage-focus-card">
          <div class="focus-head">
            ${renderPersonaAvatar(focusPersona, { current: true })}
            <div>
              <div class="focus-title">${escapeHtml(focusPersona.label)}</div>
              <div class="focus-subtitle">${escapeHtml(zoneLabels[focusPersona.zone] || focusPersona.zone)} · ${escapeHtml(focusPersona.code)}</div>
            </div>
          </div>
          <div class="focus-thought">${escapeHtml(focusThought)}</div>
        </div>
        <div class="negotiation-rail">
          ${cast.map((persona) => {
            const isCurrent = focusPersona.code === persona.code;
            const hasHandoff = state.scene.handoffs.some((handoff) => handoff.step_name === persona.code);
            return `
              <div class="rail-node ${isCurrent ? "is-current" : ""} ${hasHandoff ? "is-done" : ""}">
                ${renderPersonaAvatar(persona, { current: isCurrent, compact: true })}
                <div class="rail-code">${escapeHtml(persona.code)}</div>
              </div>
            `;
          }).join("")}
        </div>
      </section>
    `;
  }

  async function refreshTasks() {
    state.tasks = (await fetchJson("/api/tasks")) || [];
  }

  async function refreshHealth() {
    state.health = await fetchJson("/api/system/health");
  }

  async function refreshOfficeFeed(options = {}) {
    const { reset = false } = options;
    const afterId = reset ? null : state.live.officeLastEventId;
    const path = afterId
      ? `/api/events?after_id=${afterId}&limit=20`
      : "/api/events?limit=20";
    const data = await fetchJson(path);
    const events = data.events || [];
    state.officeFeed = reset ? events : mergeEvents(state.officeFeed, events, 40);
    state.live.officeLastEventId = data.last_event_id || state.live.officeLastEventId || 0;
    state.live.lastOfficeSyncAt = new Date().toISOString();
  }

  async function refreshScene(taskId) {
    state.scene = await fetchJson(`/api/tasks/${taskId}/scene`);
    state.selectedTaskId = taskId;
    state.live.taskLastEventId = state.scene?.live?.last_event_id || 0;
    rememberTaskId(taskId);
    try {
      state.unifiedThread = await fetchJson(`/api/missions/${taskId}/thread?limit=80`);
    } catch (err) {
      state.unifiedThread = { items: [], error: err?.message || String(err) };
    }
  }

  async function refreshTaskFeed(taskId, options = {}) {
    const { reset = false } = options;
    const afterId = reset ? null : state.live.taskLastEventId;
    const query = afterId
      ? `/api/events?task_id=${taskId}&after_id=${afterId}&limit=20`
      : `/api/events?task_id=${taskId}&limit=20`;
    const data = await fetchJson(query);
    const events = data.events || [];
    if (reset) {
      state.taskFeed = events;
      state.live.taskFeedBadgeCount = 0;
    } else if (events.length) {
      state.taskFeed = mergeEvents(state.taskFeed, events, 50);
      state.live.taskFeedBadgeCount += events.length;
      state.live.shouldScrollTaskFeed = true;
    }
    state.live.taskLastEventId = data.last_event_id || state.live.taskLastEventId || 0;
    state.live.lastTaskSyncAt = new Date().toISOString();
    return events;
  }

  async function openDocument(document) {
    const result = await fetchJson(`/api/tasks/${state.selectedTaskId}/documents/${encodeURIComponent(document.key)}`);
    state.docs = [{
      key: document.key,
      title: result.title,
      subtitle: result.path || result.subtitle,
      content: result.content,
      openUrl: taskDocumentUrl(document, "view"),
      downloadUrl: taskDocumentUrl(document, "download"),
    }];
    state.view = "docs";
    syncHistory("push");
    render();
    syncPolling();
  }

  function openDocumentWindow(docItem) {
    const popup = window.open(taskDocumentUrl(docItem, "view"), "_blank", "noopener,noreferrer,width=980,height=860");
    if (!popup) {
      setToast("Браузер заблокировал новое окно. Разреши pop-up для verdict.");
    }
  }

  function downloadDocument(docItem) {
    const link = window.document.createElement("a");
    link.href = taskDocumentUrl(docItem, "download");
    link.download = "";
    link.rel = "noopener";
    window.document.body.appendChild(link);
    link.click();
    link.remove();
  }

  async function openTask(taskId, options = {}) {
    const { historyMode = "push", withSpinner = true } = options;
    if (!taskId) return;
    if (withSpinner) {
      state.loading = true;
      render();
    }
    try {
      await refreshScene(taskId);
      await refreshTaskFeed(taskId, { reset: true });
      state.view = "task";
      clearStale("task");
      syncHistory(historyMode);
    } catch (error) {
      setToast(`Не удалось открыть миссию: ${error.message}`);
      if (!state.scene) {
        state.view = "office";
      }
    } finally {
      state.loading = false;
      render();
      syncPolling();
    }
  }

  async function loadRoute() {
    state.loading = true;
    render();
    try {
      await Promise.all([refreshTasks(), refreshHealth(), refreshOfficeFeed({ reset: true })]);
      if (state.selectedTaskId) {
        await refreshScene(state.selectedTaskId);
        await refreshTaskFeed(state.selectedTaskId, { reset: true });
        if (state.view === "task") {
          syncHistory("replace");
        }
      }
      clearStale();
    } catch (error) {
      setToast(`Ошибка загрузки: ${error.message}`);
      setStale("overview", `Автообновление временно недоступно: ${error.message}`);
    } finally {
      state.loading = false;
      render();
      syncPolling();
    }
  }

  function activeTaskCount() {
    return state.tasks.filter((task) => !["DONE", "ARCHIVED"].includes(task.status)).length;
  }

  function tasksWaitingDecision() {
    return state.tasks.filter((task) => ["WAIT_OWNER", "APPROVED_WAIT_MERGE"].includes(task.status)).length;
  }

  function latestTask() {
    return state.tasks[0] || null;
  }

  function zoneCards() {
    const currentZone = state.scene?.scene?.zone || "reception";
    const currentActor = state.scene?.current_actor;
    const cards = [
      { code: "reception", title: "Приёмная", note: "Сюда приходят новые задачи из Telegram и панели." },
      { code: "worklane", title: "Коридор исполнения", note: "Здесь задача проходит через ключевые роли и handoff-этапы." },
      { code: "meeting", title: "Переговорная", note: "Совет обсуждает риски, ограничения и рекомендации." },
      { code: "court", title: "Суд решений", note: "Формируется финальный отчёт и итоговый статус." },
      { code: "owner", title: "Стол владельца", note: "Здесь принимаются решения: утвердить / доработать / уточнить / merge." },
      { code: "archive", title: "Архив миссий", note: "Завершённые миссии хранятся здесь вместе с итогами." },
      { code: "ops", title: "Ops-панель", note: "Статус базы, Telegram, orchestration и runner." },
      { code: "lab", title: "AI-лаборатория", note: "Место для model-backed reasoning и prompt-work." },
    ];

    return cards.map((card) => {
      const isActive = currentZone === card.code;
      const actor = isActive && currentActor ? `<div class="agent-chip agent-${escapeHtml(currentActor.animation || "think")}">${escapeHtml(currentActor.code)}</div>` : "";
      return `
        <div class="zone-card ${isActive ? "is-active" : ""}">
          <div class="zone-name">${zoneLabels[card.code] || card.code}</div>
          <div class="zone-title">${card.title}</div>
          <div class="zone-note">${card.note}</div>
          ${actor}
        </div>
      `;
    }).join("");
  }

  function renderHealthCard(name, check) {
    const statusClass = check.status === "ok" ? "status-ok" : check.status === "warn" ? "status-warn" : "status-error";
    return `
      <div class="panel-card">
        <div class="scene-head">
          <div>
            <div class="scene-title">${escapeHtml(labelizeHealth(name))}</div>
            <div class="scene-subtitle">${escapeHtml(check.message || "Нет деталей")}</div>
          </div>
          <span class="status-pill ${statusClass}">${escapeHtml(check.status)}</span>
        </div>
      </div>
    `;
  }

  function renderLiveEvent(event, options = {}) {
    const { showTaskLink = false, compact = false } = options;
    const severityClass = `event-${escapeHtml(event.severity || "info")}`;
    const persona = eventPersona(event);
    const taskLink = showTaskLink && event.task_id
      ? `<button class="small-btn" data-open-task="${event.task_id}">#${event.task_id}</button>`
      : (event.task_id ? `<span class="tag">#${event.task_id}</span>` : "");
    return `
      <article class="live-event ${severityClass} ${compact ? "is-compact" : ""}">
        <div class="live-event-head">
          <div class="live-event-titlebox">
            ${renderPersonaAvatar(persona, { compact: true })}
            <div>
              <div class="doc-title">${escapeHtml(event.label || event.event_type)}</div>
              <div class="doc-subtitle">${formatDate(event.created_at)} · ${escapeHtml(persona.label)}</div>
            </div>
          </div>
          <div class="live-meta">
            ${event.status_after ? `<span class="scene-pill">${escapeHtml(stageLabels[event.status_after] || event.status_after)}</span>` : ""}
            ${taskLink}
          </div>
        </div>
        <div class="live-note">${escapeHtml(event.note || "Событие зафиксировано.")}</div>
      </article>
    `;
  }

  function buildDialogueTarget(targetCode, task) {
    if (!targetCode || targetCode === "Roundtable") {
      if (["WAIT_OWNER", "APPROVED_WAIT_MERGE", "DONE"].includes(task?.status)) return lookupPersona("OWNER");
      return lookupPersona("RC");
    }
    if (targetCode === "Court") return lookupPersona("JUDGE");
    if (targetCode === "Owner") return lookupPersona("OWNER");
    return lookupPersona(targetCode);
  }

  function topicSnippet(task, limit = 52) {
    const compact = String(task?.owner_text || "").replace(/\s+/g, " ").trim();
    if (!compact) return "текущей миссии";
    return compact.length <= limit ? compact : `${compact.slice(0, limit - 1)}…`;
  }

  function specialistLine(speaker, target, task, handoff) {
    const topic = topicSnippet(task);
    const nextLabel = target?.label || "следующий контур";
    const firstRisk = task?.risk_table?.[0]?.issue;
    const templates = {
      COORDINATOR: `Миссию по теме «${topic}» принял. Передаю её в ${nextLabel}.`,
      PS: `Формулирую рамку решения по теме «${topic}». Следом подключаю ${nextLabel}.`,
      PM: `Разбиваю работу на шаги и фиксирую следующий переход к ${nextLabel}.`,
      UX: `Уточняю пользовательский путь и визуальные ожидания по теме «${topic}».`,
      FE: `Готовлю интерфейсную часть и состояния экранов. Затем передаю в ${nextLabel}.`,
      BE: `Собираю backend-логику и границы контрактов. Следующий ход у ${nextLabel}.`,
      ARCH: `Сверяю архитектурные ограничения и точки стыка перед передачей в ${nextLabel}.`,
      QA: `Собираю короткий план проверки и риски приёмки. После меня идёт ${nextLabel}.`,
      DEVOPS: `Держу rollout, откат и healthcheck в поле зрения. Передаю данные в ${nextLabel}.`,
      RC: `Поднимаю спорные места и ограничения. Дальше слово у ${nextLabel}.`,
      SEC: `Проверяю доступы, чувствительные данные и границы безопасности. Передаю вывод в ${nextLabel}.`,
      LEGAL: `Смотрю формулировки, обязательства и правовые риски. Дальше подключается ${nextLabel}.`,
      FIN: `Проверяю влияние на бюджет и экономику решения. Передаю вывод в ${nextLabel}.`,
      JUDGE: `Фиксирую итог команды и формирую вердикт. Передаю его ${nextLabel}.`,
      OWNER: `Смотрю финальное решение команды и выбираю следующий управленческий ход.`,
    };
    const text = templates[speaker?.code] || `Держу тему «${topic}» в работе и передаю контекст дальше.`;
    return firstRisk && ["JUDGE", "OWNER"].includes(speaker?.code)
      ? `${text} Ключевой риск: ${firstRisk}.`
      : text;
  }

  function buildSpecialistDialogue(task) {
    const handoffs = state.scene?.handoffs || [];
    const dialogue = [];

    if (!handoffs.length) {
      const coordinator = lookupPersona("COORDINATOR");
      const strategist = lookupPersona("PS");
      dialogue.push({
        speaker: coordinator,
        target: strategist,
        text: specialistLine(coordinator, strategist, task),
        routeLabel: "Приёмная -> Разбор",
      });
      dialogue.push({
        speaker: strategist,
        target: lookupPersona("PM"),
        text: specialistLine(strategist, lookupPersona("PM"), task),
        routeLabel: "Разбор -> Исполнение",
      });
      return dialogue;
    }

    const recent = handoffs.slice(-3);
    if (recent[0]?.step_name !== "COORDINATOR") {
      const starterTarget = recent[0]?.persona || lookupPersona("PS");
      dialogue.push({
        speaker: lookupPersona("COORDINATOR"),
        target: starterTarget,
        text: specialistLine(lookupPersona("COORDINATOR"), starterTarget, task),
        routeLabel: "Приёмная -> Разбор",
      });
    }

    recent.forEach((handoff, index) => {
      const speaker = handoff.persona || lookupPersona(handoff.step_name);
      const fallbackTargetCode = recent[index + 1]?.step_name || handoff.payload?.next_action || (task.status === "WAIT_OWNER" ? "OWNER" : "JUDGE");
      const target = buildDialogueTarget(fallbackTargetCode, task);
      dialogue.push({
        speaker,
        target,
        text: specialistLine(speaker, target, task, handoff),
        routeLabel: `${zoneLabels[speaker.zone] || speaker.zone} -> ${zoneLabels[target.zone] || target.zone}`,
      });
    });

    if (["WAIT_OWNER", "APPROVED_WAIT_MERGE", "DONE"].includes(task.status)) {
      const judge = lookupPersona("JUDGE");
      const owner = lookupPersona("OWNER");
      dialogue.push({
        speaker: judge,
        target: owner,
        text: specialistLine(judge, owner, task),
        routeLabel: "Суд -> Стол владельца",
      });
    }

    return dialogue.slice(0, 4);
  }

  function renderSpecialistDialogue(task) {
    const dialogue = buildSpecialistDialogue(task);
    return `
      <section class="scene-card" style="margin-top:1rem;">
        <div class="scene-head">
          <div>
            <div class="scene-title">Короткий диалог команды</div>
            <div class="scene-subtitle">Короткие русские сообщения между специалистами по текущей теме миссии.</div>
          </div>
        </div>
        <div class="dialogue-list">
          ${dialogue.map((line, index) => `
            <article class="dialogue-card ${index === dialogue.length - 1 ? "is-hot" : ""}">
              <div class="doc-head">
                <div class="mission-headline">
                  ${renderPersonaAvatar(line.speaker, { compact: true })}
                  <div>
                    <div class="doc-title">${escapeHtml(line.speaker.label)} -> ${escapeHtml(line.target.label)}</div>
                    <div class="doc-subtitle">${escapeHtml(line.routeLabel)}</div>
                  </div>
                </div>
                <span class="scene-pill">${escapeHtml(line.speaker.code)}</span>
              </div>
              <div class="dialogue-line">${escapeHtml(line.text)}</div>
            </article>
          `).join("")}
        </div>
      </section>
    `;
  }

  function renderUnifiedMissionThread() {
    const ut = state.unifiedThread;
    if (!ut) return "";
    if (ut.error) {
      return `
        <section class="scene-card" style="margin-top:1rem;">
          <div class="scene-head">
            <div>
              <div class="scene-title">Единая нить миссии</div>
              <div class="scene-subtitle">Не удалось загрузить объединённую ленту: ${escapeHtml(ut.error)}</div>
            </div>
          </div>
        </section>
      `;
    }
    const items = (ut.items || []).slice(-40);
    if (!items.length) {
      return `
        <section class="scene-card" style="margin-top:1rem;">
          <div class="scene-head">
            <div>
              <div class="scene-title">Единая нить миссии</div>
              <div class="scene-subtitle">Пока нет событий в объединённой ленте (audit + чат + handoffs). После запуска AI-Team записи появятся здесь и совпадут с API для Telegram.</div>
            </div>
          </div>
        </section>
      `;
    }
    return `
      <section class="scene-card" style="margin-top:1rem;">
        <div class="scene-head">
          <div>
            <div class="scene-title">Единая нить миссии</div>
            <div class="scene-subtitle">Одна хронология для Telegram и Dashboard: события системы, сообщения чата и handoffs. Эндпоинт: /api/missions/${state.selectedTaskId}/thread</div>
          </div>
          <span class="scene-pill">${items.length} записей</span>
        </div>
        <div class="docs-grid">
          ${items.map((item) => `
            <div class="doc-card">
              <div class="doc-head">
                <div>
                  <div class="doc-title">${escapeHtml(item.label || item.kind || "Запись")}</div>
                  <div class="doc-subtitle">${escapeHtml(formatDate(item.created_at))} · ${escapeHtml(item.kind || "")}</div>
                </div>
                ${item.severity ? `<span class="scene-pill">${escapeHtml(item.severity)}</span>` : ""}
              </div>
              <div class="mission-brief">${escapeHtml(String(item.note || "").slice(0, 800))}</div>
            </div>
          `).join("")}
        </div>
      </section>
    `;
  }

  function renderMissionChat() {
    const chat = state.scene?.chat || { messages: [], quick_prompts: [], can_send: false };
    const chatDraft = state.drafts.missionChat || "";
    return `
      <section class="scene-card chat-panel" id="mission-chat-panel">
        <div class="scene-head">
          <div>
            <div class="scene-title">Чат с командой</div>
            <div class="scene-subtitle">Пиши команде по-человечески на русском. Ответы идут в контексте текущей миссии, а live-обновление больше не должно сбрасывать ввод во время набора.</div>
          </div>
          <span class="scene-pill">${chat.can_send ? "Команда онлайн" : "Чат недоступен"}</span>
        </div>
        <div class="chat-feed" data-chat-feed>
          ${chat.messages.length
            ? chat.messages.map((item) => {
              const persona = lookupPersona(item.speaker_code);
              return `
                <div class="chat-message ${item.role === "owner" ? "is-owner" : "is-team"}">
                  <div class="chat-head">
                    ${renderPersonaAvatar(persona, { compact: true, current: item.role === "team" })}
                    <div>
                      <div class="chat-author">${escapeHtml(item.speaker_name)}</div>
                      <div class="chat-time">${escapeHtml(formatDate(item.created_at))}</div>
                    </div>
                  </div>
                  <div class="chat-text">${escapeHtml(item.text)}</div>
                </div>
              `;
            }).join("")
            : `<div class="empty-state">Пока диалога нет. Спроси команду, что происходит по миссии.</div>`}
        </div>
        <div class="chat-suggestions">
          ${(chat.quick_prompts || []).map((prompt) => `
            <button type="button" class="small-btn" data-chat-suggestion="${escapeHtml(prompt)}">${escapeHtml(prompt)}</button>
          `).join("")}
        </div>
        <div class="task-composer chat-composer">
          <textarea id="mission-chat-input" rows="3" placeholder="Написать команде: спросить про статус, риски, документы или следующий шаг..." ${chat.can_send ? "" : "disabled"}>${escapeHtml(chatDraft)}</textarea>
          <div class="inline-actions interactive-layer">
            <button type="button" class="primary-btn" data-action="send-chat" ${chat.can_send ? "" : "disabled"}>Написать команде</button>
          </div>
        </div>
      </section>
    `;
  }

  function renderChatPreview() {
    const chat = state.scene?.chat || { messages: [], can_send: false };
    const latest = [...(chat.messages || [])].reverse().find((item) => item.role === "team") || chat.messages?.[chat.messages.length - 1];
    const title = latest ? `${latest.speaker_name}: последнее сообщение` : "Чат команды ещё не начат";
    const body = latest
      ? latest.text
      : "Команда отвечает в этой миссии в отдельном чате. Нажми «К чату команды», чтобы перейти прямо к диалогу.";
    return `
      <section class="scene-card chat-preview-card">
        <div class="scene-head">
          <div>
            <div class="scene-title">Ответы команды</div>
            <div class="scene-subtitle">Быстрый вход в живой чат миссии без долгой прокрутки вниз.</div>
          </div>
          <span class="scene-pill">${chat.can_send ? "Команда онлайн" : "Чат недоступен"}</span>
        </div>
        <div class="chat-preview-body">
          <div class="doc-title">${escapeHtml(title)}</div>
          <div class="mission-brief">${escapeHtml(body)}</div>
        </div>
        <div class="inline-actions interactive-layer">
          <button type="button" class="primary-btn" data-action="scroll-chat">К чату команды</button>
        </div>
      </section>
    `;
  }

  function renderOfficeView() {
    const latest = latestTask();
    const healthChecks = state.health?.checks || {};
    const spotlightTask = state.selectedTaskId
      ? state.tasks.find((task) => task.id === state.selectedTaskId)
      : latest;
    const spotlightPersona = personaForTask(spotlightTask || { status: "NEW" });
    const taskDraft = state.drafts.taskComposer || "";
    return `
      <section class="office-hero">
        <div class="hero-title">Офис MyWave</div>
        <div class="hero-subtitle">Игровая операционная панель: наблюдай, как сотрудники-агенты принимают миссии, обсуждают решение и возвращают результат.</div>
        <div class="metrics-row">
          <div class="metric-box">
            <div class="metric-label">Активные миссии</div>
            <div class="metric-value">${activeTaskCount()}</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Ждут владельца</div>
            <div class="metric-value">${tasksWaitingDecision()}</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Последняя миссия</div>
            <div class="metric-value">${latest ? `#${latest.id}` : "—"}</div>
          </div>
        </div>
        <div class="hq-ribbon">
          <article class="hq-card">
            <div class="hq-card-head">
              ${renderPersonaAvatar(spotlightPersona, { current: true })}
              <div>
                <div class="doc-title">${latest ? `Миссия #${latest.id}` : "Штаб ждёт новую миссию"}</div>
                <div class="doc-subtitle">${latest ? escapeHtml(stageLabels[latest.status] || latest.status) : "Новых задач пока нет"}</div>
              </div>
            </div>
            <div class="mission-brief">${latest ? "Текущая миссия остаётся главным фокусом штаба." : "Создай новую миссию, чтобы оживить офис."}</div>
          </article>
          <article class="hq-card">
            <div class="doc-title">Штабный эфир</div>
            <div class="doc-subtitle">Сцены, handoffs и owner-решения теперь двигаются в одном live-контуре.</div>
            <div class="hq-chip-row">
              <span class="tag">Live ops</span>
              <span class="tag">Game UI</span>
            </div>
          </article>
        </div>
        <div class="office-map">${zoneCards()}</div>
      </section>

      <section>
        <div class="scene-head">
          <div>
            <div class="scene-title">Ситуационный центр</div>
            <div class="scene-subtitle">Техническое здоровье системы, доступное с телефона и запасной панели.</div>
          </div>
        </div>
        <div class="health-grid">
          ${Object.entries(healthChecks).map(([name, check]) => renderHealthCard(name, check)).join("") || `<div class="empty-state">Пока нет данных health.</div>`}
        </div>
      </section>

      <section class="scene-card">
        <div class="scene-head">
          <div>
            <div class="scene-title">Лента штаба</div>
            <div class="scene-subtitle">Последние реальные AuditEvent по всем миссиям. Обновляется каждые 8 секунд.</div>
          </div>
          <div class="live-head-meta">
            <span class="scene-pill">Live</span>
          </div>
        </div>
        <div class="live-feed">
          ${state.officeFeed.length
            ? state.officeFeed.slice().reverse().map((event) => renderLiveEvent(event, { showTaskLink: true, compact: true })).join("")
            : `<div class="empty-state">Пока нет событий для штаба.</div>`}
        </div>
      </section>

      <section class="task-composer">
        <div class="scene-head">
          <div>
            <div class="scene-title">Поставить новую миссию</div>
            <div class="scene-subtitle">Можно создавать задачи прямо из панели. Для критичных действий Telegram остаётся главным каналом подтверждений.</div>
          </div>
        </div>
        <textarea id="task-composer-input" placeholder="#TASK Подготовить план выката новой фичи сайта с rollback, healthcheck и рисками">${escapeHtml(taskDraft)}</textarea>
        <div class="composer-note">Подсказка: вводи задачу в том же формате, что и в Telegram. После создания откроется игровая сцена миссии.</div>
        <div class="upload-card">
          <div class="doc-title">Добавить входные файлы</div>
          <div class="scene-subtitle">Поддерживаются форматы <code>.md</code>, <code>.txt</code>, <code>.docx</code>. Файлы будут сохранены в проекте как документы новой миссии.</div>
          <label class="upload-picker">
            <span class="small-btn">Выбрать файлы</span>
            <input id="task-attachment-input" type="file" accept=".md,.txt,.docx" multiple hidden>
          </label>
          ${renderUploadSelection(state.uploads.taskComposerFiles, "Пока не выбрано ни одного файла для новой миссии.")}
        </div>
        <div class="inline-actions interactive-layer">
          <button type="button" class="primary-btn" data-action="create-task">Создать миссию</button>
          <button type="button" class="ghost-btn" data-nav="missions">Открыть все миссии</button>
        </div>
      </section>
    `;
  }

  function renderMissionsView() {
    if (!state.tasks.length) {
      return `<div class="empty-state">Пока нет миссий. Создай первую задачу из Telegram или прямо из панели.</div>`;
    }
    return `
      <section class="mission-grid">
        ${state.tasks.map((task) => `
          <article class="mission-card mission-card-poster ${state.selectedTaskId === task.id ? "is-selected" : ""}">
            <div class="mission-head">
              <div class="mission-headline">
                ${renderPersonaAvatar(personaForTask(task))}
                <div>
                  <div class="mission-title">Миссия #${task.id}</div>
                  <div class="mission-subtitle">${escapeHtml(task.domain || "Без домена")} · ${escapeHtml(stageLabels[task.status] || task.status)}</div>
                </div>
              </div>
              <div class="mission-badges">
                <span class="scene-pill">${coarseProgressPercent(task)}%</span>
                <span class="scene-pill">${escapeHtml(task.criticality || "—")}</span>
                ${task.runner?.is_active ? `<span class="status-pill status-ok">${escapeHtml(task.runner.phase_label || "AI-Team работает")}</span>` : ""}
              </div>
            </div>
            <div class="mission-route">
              <span class="route-node ${task.status === "WAIT_OWNER" || task.status === "APPROVED_WAIT_MERGE" ? "is-hot" : ""}">${escapeHtml(stageLabels[task.status] || task.status)}</span>
              <span class="route-arrow">/</span>
              <span class="route-node">${escapeHtml(task.domain || "general")}</span>
            </div>
            <div class="mission-brief">Открой сцену, чтобы посмотреть переговоры команды, live feed и решение owner.</div>
            <div class="inline-actions interactive-layer">
              <button type="button" class="primary-btn" data-open-task="${task.id}">Открыть сцену</button>
            </div>
          </article>
        `).join("")}
      </section>
    `;
  }

  function normalizedProgressStatus(status) {
    if (status === "REWORK") return "IN_PIPELINE";
    if (status === "NEED_INFO") return "WAIT_OWNER";
    if (status === "ARCHIVED") return "DONE";
    return status || "NEW";
  }

  function progressBasePercent(status) {
    return {
      NEW: 6,
      TRIAGED: 18,
      IN_PIPELINE: 42,
      IN_ROUNDTABLE: 64,
      IN_COURT: 81,
      WAIT_OWNER: 92,
      APPROVED_WAIT_MERGE: 97,
      DONE: 100,
    }[normalizedProgressStatus(status)] || 6;
  }

  function coarseProgressPercent(task) {
    return progressBasePercent(task?.status);
  }

  function nextProgressStatus(status) {
    const normalized = normalizedProgressStatus(status);
    const index = stageOrder.indexOf(normalized);
    if (index === -1 || index >= stageOrder.length - 1) return null;
    return stageOrder[index + 1];
  }

  function latestImportantTaskEvent(task) {
    const events = [...state.taskFeed].reverse();
    const important = events.find((event) => STRUCTURAL_EVENTS.has(event.event_type) || ["task_created", "pipeline_start"].includes(event.event_type));
    return important || events[0] || null;
  }

  function runnerSnapshot() {
    return state.scene?.runner || {
      state: "idle",
      phase: "idle",
      phase_label: "Ожидание",
      is_active: false,
      can_stop: false,
      can_start: false,
      current_step: "",
      message: "",
      last_error: "",
    };
  }

  function currentAiStateLabel(task) {
    const runner = runnerSnapshot();
    if (runner.is_active && runner.state === "stopping") return "Останавливается";
    if (runner.is_active) return `Работает: ${runner.phase_label}`;
    if (runner.state === "cancelled") return "Остановлен";
    if (runner.state === "failed") return "Ошибка";
    if (ACTIVE_WORK_STATUSES.has(task.status)) return "Работает";
    if (task.status === "WAIT_OWNER") return "Ждёт владельца";
    if (task.status === "APPROVED_WAIT_MERGE") return "Ждёт merge";
    if (task.status === "NEED_INFO") return "Ждёт уточнения";
    if (task.status === "REWORK") return "Ожидает перезапуск";
    if (task.status === "NEW") return "Не запущен";
    if (FINAL_STATUSES.has(task.status)) return "Завершён";
    return "В обработке";
  }

  function currentAiTone(task) {
    const runner = runnerSnapshot();
    if (runner.is_active) return runner.state === "stopping" ? "status-warn" : "status-ok";
    if (runner.state === "cancelled" || runner.state === "failed") return "status-warn";
    if (ACTIVE_WORK_STATUSES.has(task.status)) return "status-ok";
    if (["WAIT_OWNER", "APPROVED_WAIT_MERGE", "NEED_INFO", "REWORK"].includes(task.status)) return "status-warn";
    if (FINAL_STATUSES.has(task.status)) return "status-ok";
    return "status-pill";
  }

  function currentOperatorLabel(task, currentActor) {
    const runner = runnerSnapshot();
    if (runner.is_active && runner.current_step) {
      return lookupPersona(runner.current_step).label;
    }
    if (ACTIVE_WORK_STATUSES.has(task.status)) {
      return currentActor?.label || personaForTask(task).label;
    }
    if (["WAIT_OWNER", "APPROVED_WAIT_MERGE", "NEED_INFO"].includes(task.status)) {
      return "Владелец";
    }
    if (FINAL_STATUSES.has(task.status)) {
      return "Никто, цикл закрыт";
    }
    return "Ожидает запуска";
  }

  function nextHumanAction(task) {
    const runner = runnerSnapshot();
    if (runner.is_active && runner.can_stop) {
      return "Если хочешь прервать текущий проход, нажми «Остановить AI-Team» и дождись безопасной остановки.";
    }
    return {
      NEW: "Запустить AI-Team для первого прохода.",
      TRIAGED: "Дождаться завершения pipeline.",
      IN_PIPELINE: "Дождаться handoff и перехода к roundtable.",
      IN_ROUNDTABLE: "Дождаться фиксации рисков и передачи в суд.",
      IN_COURT: "Дождаться финального вердикта команды.",
      WAIT_OWNER: "Выбрать решение владельца: утвердить, доработать или запросить уточнение.",
      APPROVED_WAIT_MERGE: "Сделать ручной merge и нажать «Подтвердить merge».",
      NEED_INFO: "Добавить недостающие вводные и снова запустить AI-Team.",
      REWORK: "После правок снова запустить AI-Team.",
      DONE: "Открыть финальные документы или отправить в новый цикл через доработку.",
      ARCHIVED: "Смотреть архив и итоговые документы.",
    }[task.status] || "Следить за обновлением миссии.";
  }

  function currentRealityText(task, latestEvent) {
    const runner = runnerSnapshot();
    if (runner.is_active) {
      const currentStep = runner.current_step ? ` Сейчас работает роль ${lookupPersona(runner.current_step).label}.` : "";
      return `AI-Team выполняет миссию в фоне. Активная фаза: ${runner.phase_label}.${currentStep} ${runner.message || ""}`.trim();
    }
    if (runner.state === "cancelled") {
      return runner.message || "Проход AI-Team остановлен вручную. Контекст сохранён, задачу можно запустить снова.";
    }
    if (runner.state === "failed") {
      return runner.last_error
        ? `Фоновый проход завершился ошибкой: ${runner.last_error}`
        : "Фоновый проход завершился ошибкой. Проверь журнал и перезапусти миссию.";
    }
    if (ACTIVE_WORK_STATUSES.has(task.status)) {
      return `AI-Team реально выполняет задачу. Последний подтверждённый этап: ${latestEvent?.label || stageLabels[task.status] || task.status}.`;
    }
    return {
      NEW: "AI-Team ещё не стартовал. Сейчас ничего не выполняется, пока ты не запустишь задачу вручную.",
      WAIT_OWNER: "Команда уже закончила свою часть. Сейчас ничего не исполняется: система ждёт только решение владельца.",
      APPROVED_WAIT_MERGE: "Команда уже закончила работу. Owner одобрил результат, остался только ручной merge.",
      NEED_INFO: "Текущий цикл остановлен. AI-Team ждёт дополнительный контекст перед следующим запуском.",
      REWORK: "Прошлый цикл завершён. Задача возвращена на доработку и ждёт повторного запуска.",
      DONE: "Процесс полностью завершён. Сейчас AI-Team ничего не выполняет, доступны только документы и история.",
      ARCHIVED: "Миссия уже в архиве. Активного процесса сейчас нет.",
    }[task.status] || "Текущее состояние задачи обновлено.";
  }

  function ownerNowSteps(task) {
    const runner = runnerSnapshot();
    if (runner.is_active && runner.can_stop) {
      return [
        "Если проход нужно прервать, нажми «Остановить AI-Team».",
        "Дождись безопасной остановки на checkpoint-точке.",
        "После остановки реши: перезапустить миссию или уточнить задачу для команды.",
      ];
    }
    return {
      NEW: [
        "Прочитай краткое описание миссии.",
        "Нажми «Запустить AI-Team», чтобы команда начала работу.",
        "После старта следи за progress и live-событиями.",
      ],
      TRIAGED: [
        "Проверь, что разбор задачи выглядит корректно.",
        "Дождись завершения pipeline и handoff-документов.",
        "Если контекст изменился, останови цикл и уточни задачу.",
      ],
      IN_PIPELINE: [
        "Дай команде закончить handoff-документы.",
        "Следи за live-лентой и текущим этапом выполнения.",
        "Если вводные изменились, останови цикл и обнови задачу.",
      ],
      IN_ROUNDTABLE: [
        "Дождись фиксации рисков и рекомендаций команды.",
        "Проверь, нет ли блокеров или спорных мест.",
        "Если нужно, останови цикл до финального суда.",
      ],
      IN_COURT: [
        "Дождись финального отчёта и вердикта суда.",
        "После завершения открой документы команды.",
        "Дальше прими owner-решение по результату.",
      ],
      WAIT_OWNER: [
        "Открой финальный вердикт и краткий отчёт команды.",
        "Выбери одно действие: утвердить, вернуть на доработку или запросить уточнение.",
        "Если решение положительное, после фактического merge подтверди его в сцене.",
      ],
      APPROVED_WAIT_MERGE: [
        "Сделай ручной merge вне этой сцены.",
        "Вернись в миссию и нажми «Подтвердить merge».",
        "Проверь, что задача перешла в завершённый статус.",
      ],
      NEED_INFO: [
        "Добавь недостающие вводные в задачу.",
        "Запусти AI-Team заново после уточнения контекста.",
        "Проверь, что новый цикл действительно стартовал.",
      ],
      REWORK: [
        "Ознакомься с замечаниями команды и суда.",
        "После исправлений снова запусти AI-Team.",
        "Сверь новый результат с предыдущим вердиктом и документами.",
      ],
      DONE: [
        "Открой финальные документы и проверь итог команды.",
        "Если задача действительно завершена, больше действий не требуется.",
        "Если нужен новый цикл, верни задачу на доработку.",
      ],
      ARCHIVED: [
        "Открой архивные документы при необходимости.",
        "Используй финальный вердикт как опорную точку для следующих задач.",
        "Если нужен новый цикл, создай новую миссию или вернись к активной задаче.",
      ],
    }[task.status] || [
      "Проверь текущее состояние миссии.",
      "Открой документы и live-ленту для контекста.",
      "При необходимости верни задачу на новый цикл.",
    ];
  }

  function currentLiveLabel() {
    if (state.live.userPaused) return "Пауза вручную";
    if (state.scene?.live?.can_auto_refresh) return "Автообновление включено";
    return "Автообновление завершено";
  }

  function rawSummaryLooksStale(task) {
    const summary = (task.summary || "").trim();
    if (!summary) return false;
    return FINAL_STATUSES.has(task.status) && /approve owner/i.test(summary);
  }

  function controlStateSnapshot() {
    return state.scene?.control_state || {
      status_summary: "",
      owner_waiting_for: "",
      start_reason: "",
      stop_reason: "",
    };
  }

  function buildOwnerPanelSummary(task, currentActor) {
    const controlState = controlStateSnapshot();
    const parts = [controlState.status_summary || currentRealityText(task, latestImportantTaskEvent(task)), `Следующее действие: ${controlState.owner_waiting_for || nextHumanAction(task)}`];
    const rawSummary = (task.summary || "").trim();
    if (rawSummary && !rawSummaryLooksStale(task)) {
      parts.push(`Командный итог: ${rawSummary}`);
    }
    return parts.join(" ").slice(0, 900);
  }

  function buildCurrentState(task, currentActor) {
    const latestEvent = latestImportantTaskEvent(task);
    const runner = runnerSnapshot();
    const controlState = controlStateSnapshot();
    const toneClass = currentAiTone(task);
    const latestLine = latestEvent
      ? `${latestEvent.label || latestEvent.event_type} · ${formatDate(latestEvent.created_at)}`
      : "История событий пока не собрана";
    const focusAction = runner.is_active
      ? { label: "К управлению AI-Team", action: "scroll-owner" }
      : canRunPipeline(task)
      ? { label: "К запуску AI-Team", action: "scroll-owner" }
      : ["WAIT_OWNER", "APPROVED_WAIT_MERGE"].includes(task.status)
        ? { label: "К решению владельца", action: "scroll-owner" }
        : (state.scene?.documents?.length || task.report_path)
          ? { label: "К документам", action: "scroll-docs" }
          : null;
    return {
      toneClass,
      statusLabel: stageLabels[task.status] || task.status,
      aiStateLabel: currentAiStateLabel(task),
      liveLabel: currentLiveLabel(),
      runnerLabel: runner.is_active || runner.state === "cancelled" || runner.state === "failed"
        ? `${runner.phase_label}${runner.current_step ? ` · ${lookupPersona(runner.current_step).label}` : ""}`
        : "Нет активного фонового job-а",
      operatorLabel: currentOperatorLabel(task, currentActor),
      nextActionLabel: nextHumanAction(task),
      latestLine,
      note: controlState.status_summary || currentRealityText(task, latestEvent),
      teamSummary: rawSummaryLooksStale(task) ? "" : (task.summary || "").trim(),
      ownerWaitingFor: controlState.owner_waiting_for || nextHumanAction(task),
      startReason: state.scene?.runner?.start_reason || "",
      stopReason: state.scene?.runner?.stop_reason || "",
      ownerNowSteps: ownerNowSteps(task),
      focusAction,
    };
  }

  function buildProcessMotionText(task, actor, latestEvent) {
    const label = actor?.label || "Команда";
    if (latestEvent?.note) {
      return `${label}: ${latestEvent.note}`;
    }
    return {
      NEW: `${label} принимает миссию и готовит её к разбору.`,
      TRIAGED: `${label} завершает классификацию и передаёт задачу в pipeline.`,
      IN_PIPELINE: `${label} готовит handoff и двигает задачу по рабочему коридору.`,
      IN_ROUNDTABLE: `${label} участвует в обсуждении рисков и компромиссов.`,
      IN_COURT: `${label} собирает итоговую позицию и финальный отчёт.`,
      WAIT_OWNER: `Система ждёт решения владельца по готовому результату.`,
      APPROVED_WAIT_MERGE: `Задача одобрена. Остался ручной merge и подтверждение закрытия.`,
      NEED_INFO: `Система ждёт дополнительные вводные от владельца.`,
      REWORK: `${label} повторно проводит задачу по циклу доработки.`,
      DONE: `Миссия завершена. Артефакты готовы к архиву и просмотру.`,
      ARCHIVED: `Миссия закрыта и хранится в архиве штаба.`,
    }[task.status] || `${label} продолжает обработку миссии.`;
  }

  function buildTaskProgress(task, currentActor) {
    const normalized = normalizedProgressStatus(task.status);
    const handoffCount = state.scene?.handoffs?.length || 0;
    const liveCount = state.taskFeed.length || 0;
    const docsCount = state.scene?.documents?.length || (handoffCount + (task.report_path ? 1 : 0));
    const latestEvent = latestImportantTaskEvent(task);
    let percent = progressBasePercent(normalized);

    if (["IN_PIPELINE", "IN_ROUNDTABLE", "IN_COURT", "WAIT_OWNER", "APPROVED_WAIT_MERGE", "DONE"].includes(normalized)) {
      percent = Math.max(percent, 18 + Math.min(handoffCount, 6) / 6 * 34);
    }
    if (["IN_ROUNDTABLE", "IN_COURT", "WAIT_OWNER", "APPROVED_WAIT_MERGE", "DONE"].includes(normalized)) {
      percent = Math.max(percent, 66);
    }
    if (["IN_COURT", "WAIT_OWNER", "APPROVED_WAIT_MERGE", "DONE"].includes(normalized)) {
      percent = Math.max(percent, task.report_path ? 88 : 82);
    }
    if (normalized === "WAIT_OWNER") {
      percent = Math.max(percent, 92);
    }
    if (normalized === "APPROVED_WAIT_MERGE") {
      percent = Math.max(percent, 97);
    }
    if (normalized === "DONE") {
      percent = 100;
    }

    const nextStatus = nextProgressStatus(normalized);
    return {
      percent: Math.max(1, Math.min(100, Math.round(percent))),
      currentLabel: stageLabels[normalized] || normalized,
      nextLabel: nextStatus ? (stageLabels[nextStatus] || nextStatus) : "Архив",
      handoffCount,
      liveCount,
      docsCount,
      ownerGate: ["WAIT_OWNER", "APPROVED_WAIT_MERGE", "NEED_INFO"].includes(task.status),
      latestEvent,
      motionText: buildProcessMotionText(task, currentActor, latestEvent),
      currentActor: currentActor || personaForTask(task),
    };
  }

  function renderCurrentState(task, currentActor) {
    const truth = buildCurrentState(task, currentActor);
    const canToggleLive = Boolean(state.live.userPaused || OVERVIEW_VIEWS.has(state.view) || state.scene?.live?.can_auto_refresh);
    const toggleLabel = state.live.userPaused ? "Продолжить live" : "Остановить live";
    const returnLabel = state.view === "docs" ? "Вернуться к миссии" : "К началу миссии";
    return `
      <section class="scene-card current-state-card" id="mission-top">
        <div class="scene-head">
          <div>
            <div class="scene-title">Сейчас по-настоящему</div>
            <div class="scene-subtitle">Это реальное текущее состояние миссии. Ниже история и последний переход показаны отдельно.</div>
          </div>
          <div class="frame-badges">
            <span class="scene-pill">${escapeHtml(truth.statusLabel)}</span>
            <span class="status-pill ${truth.toneClass}">${escapeHtml(truth.aiStateLabel)}</span>
          </div>
        </div>
        <div class="current-state-grid">
          <div class="current-state-metric">
            <div class="current-state-kicker">AI-Team</div>
            <div class="current-state-value">${escapeHtml(truth.aiStateLabel)}</div>
          </div>
          <div class="current-state-metric">
            <div class="current-state-kicker">Фоновый job</div>
            <div class="current-state-value current-state-value-small">${escapeHtml(truth.runnerLabel)}</div>
          </div>
          <div class="current-state-metric">
            <div class="current-state-kicker">Кто сейчас отвечает</div>
            <div class="current-state-value">${escapeHtml(truth.operatorLabel)}</div>
          </div>
          <div class="current-state-metric">
            <div class="current-state-kicker">Следующее действие</div>
            <div class="current-state-value current-state-value-small">${escapeHtml(truth.nextActionLabel)}</div>
          </div>
          <div class="current-state-metric">
            <div class="current-state-kicker">Live экран</div>
            <div class="current-state-value current-state-value-small">${escapeHtml(truth.liveLabel)}</div>
          </div>
          <div class="current-state-metric current-state-metric-wide">
            <div class="current-state-kicker">Последнее подтверждённое действие</div>
            <div class="current-state-value current-state-value-small">${escapeHtml(truth.latestLine)}</div>
          </div>
        </div>
        <div class="current-state-note">${escapeHtml(truth.note)}</div>
        <div class="current-state-team">Сейчас система ждёт: ${escapeHtml(truth.ownerWaitingFor)}</div>
        ${truth.teamSummary ? `<div class="current-state-team">Командный итог: ${escapeHtml(truth.teamSummary)}</div>` : ""}
        <div class="owner-now-block">
          <div class="owner-now-title">Что делать владельцу прямо сейчас</div>
          <ol class="owner-now-list">
            ${truth.ownerNowSteps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}
          </ol>
        </div>
        <div class="inline-actions current-state-actions interactive-layer">
          <button type="button" class="ghost-btn" data-action="toggle-live" ${canToggleLive ? "" : "disabled"}>${canToggleLive ? toggleLabel : "Live уже остановлен"}</button>
          <button type="button" class="primary-btn" data-action="${state.view === "docs" ? "return-task" : "scroll-top"}">${returnLabel}</button>
          ${truth.focusAction ? `<button type="button" class="warn-btn" data-action="${truth.focusAction.action}">${escapeHtml(truth.focusAction.label)}</button>` : ""}
        </div>
        <div class="scene-subtitle current-state-hint">
          ${state.live.userPaused
            ? "Пауза касается только автообновления и анимации этого экрана. Backend-задача от этого не отменяется."
            : "Если нужно остановить движение экрана, используй «Остановить live». Это не ломает саму миссию."}
        </div>
      </section>
    `;
  }

  function nextActorForTask(currentActor, task) {
    const cast = state.scene?.cast || [];
    if (!cast.length) return personaForTask({ status: nextProgressStatus(task.status) || task.status });

    const currentIndex = cast.findIndex((persona) => persona.code === currentActor?.code);
    const pending = cast.find((persona) => !state.scene.handoffs.some((handoff) => handoff.step_name === persona.code) && persona.code !== currentActor?.code);
    if (pending) return pending;
    if (currentIndex >= 0 && cast[currentIndex + 1]) return cast[currentIndex + 1];
    return personaForTask({ status: nextProgressStatus(task.status) || task.status });
  }

  function canRunPipeline(task) {
    return Boolean(state.scene?.runner?.can_start);
  }

  function canStopTeam() {
    return Boolean(state.scene?.runner?.can_stop);
  }

  function fallbackEventType(task) {
    return {
      NEW: "task_created",
      TRIAGED: "triage_done",
      IN_PIPELINE: "pipeline_done",
      IN_ROUNDTABLE: "roundtable_done",
      IN_COURT: "orchestration_done",
      WAIT_OWNER: "orchestration_done",
      APPROVED_WAIT_MERGE: "OWNER_APPROVED",
      NEED_INFO: "OWNER_CLARIFY",
      REWORK: "OWNER_REWORK",
      DONE: "OWNER_MERGED",
      ARCHIVED: "OWNER_MERGED",
    }[task.status] || "task_created";
  }

  function defaultRouteForStatus(status) {
    return {
      NEW: ["reception", "strategy", "worklane"],
      TRIAGED: ["reception", "strategy", "worklane"],
      IN_PIPELINE: ["strategy", "management", "worklane", "meeting"],
      IN_ROUNDTABLE: ["worklane", "meeting", "court"],
      IN_COURT: ["meeting", "court", "owner"],
      WAIT_OWNER: ["court", "owner", "archive"],
      APPROVED_WAIT_MERGE: ["owner", "archive"],
      NEED_INFO: ["owner", "reception", "strategy", "owner"],
      REWORK: ["owner", "worklane", "meeting", "court"],
      DONE: ["owner", "archive"],
      ARCHIVED: ["archive"],
    }[status] || ["reception", "worklane", "owner"];
  }

  function eventFramePreset(task, latestEvent) {
    const eventType = latestEvent?.event_type || fallbackEventType(task);
    if (eventType === "task_created") {
      return {
        mode: "triage",
        roomLabel: "Приёмная и триаж",
        headline: "Миссия поступила в штаб",
        signalText: "Входящий запрос зарегистрирован и отправлен на разбор.",
        actorCode: "COORDINATOR",
        nextActorCode: "PS",
        currentZone: "reception",
        nextZone: "strategy",
        route: ["reception", "strategy", "worklane"],
        currentCue: "Регистрация задачи",
        nextCue: "Классификация и маршрут",
        currentSpeech: latestEvent?.note || "Миссия зафиксирована. Проверяю входные данные и отправляю на триаж.",
        nextSpeech: "Забираю задачу в продуктовый разбор и определяю маршрут.",
        transitionNote: "Задача переходит из приёмной в режим триажа.",
      };
    }
    if (eventType === "triage_done") {
      return {
        mode: "triage",
        roomLabel: "Комната триажа",
        headline: "Триаж завершён",
        signalText: "Категория, критичность и маршрут уже зафиксированы.",
        actorCode: "COORDINATOR",
        nextActorCode: "PM",
        currentZone: "strategy",
        nextZone: "management",
        route: ["reception", "strategy", "management", "worklane"],
        currentCue: "Маршрут определён",
        nextCue: "Запуск рабочего pipeline",
        currentSpeech: latestEvent?.note || "Классификация готова. Передаю миссию в pipeline без потери контекста.",
        nextSpeech: "Принимаю маршрут и запускаю handoff по ролям команды.",
        transitionNote: "После triage задача уходит из зоны разбора в коридор исполнения.",
      };
    }
    if (eventType === "pipeline_done") {
      return {
        mode: "pipeline",
        roomLabel: "Рабочий pipeline",
        headline: "Pipeline собран",
        signalText: "Основные handoff-этапы готовы и выстроены по роли.",
        actorCode: "PM",
        nextActorCode: task.status === "IN_ROUNDTABLE" ? "RC" : "JUDGE",
        currentZone: "worklane",
        nextZone: task.status === "IN_ROUNDTABLE" ? "meeting" : "court",
        route: ["management", "worklane", "meeting", "court"],
        currentCue: "Handoffs сформированы",
        nextCue: task.status === "IN_ROUNDTABLE" ? "Совещание по рискам" : "Переход к вердикту",
        currentSpeech: latestEvent?.note || "Основной пакет handoff готов. Передаю задачу в следующий контур принятия решений.",
        nextSpeech: task.status === "IN_ROUNDTABLE"
          ? "Поднимаю риски, ограничения и спорные места на общий стол."
          : "Проверяю финальную позицию и готовлю решение.",
        transitionNote: task.status === "IN_ROUNDTABLE"
          ? "После pipeline миссия уходит в переговорную для обсуждения рисков."
          : "Pipeline завершён, задача сразу движется в судебную фазу.",
      };
    }
    if (eventType === "roundtable_done") {
      return {
        mode: "roundtable",
        roomLabel: "Переговорная",
        headline: "Совещание завершено",
        signalText: "Риски и компромиссы собраны, остаётся финальный арбитраж.",
        actorCode: "RC",
        nextActorCode: "JUDGE",
        currentZone: "meeting",
        nextZone: "court",
        route: ["worklane", "meeting", "court", "owner"],
        currentCue: "Аргументы собраны",
        nextCue: "Финальный вердикт",
        currentSpeech: latestEvent?.note || "Совет закончил обсуждение. Передаю согласованные риски и рекомендации судье.",
        nextSpeech: "Получаю материалы совещания и формирую итоговый вердикт.",
        transitionNote: "Комната совещаний закрывает обсуждение и передаёт пакет в суд решений.",
      };
    }
    if (eventType === "orchestration_done") {
      const goesToArchive = task.status === "DONE";
      return {
        mode: goesToArchive ? "owner-merged" : "court",
        roomLabel: goesToArchive ? "Архивный режим" : "Суд решений",
        headline: goesToArchive ? "Миссия закрыта" : "Вердикт сформирован",
        signalText: goesToArchive
          ? "Финальный отчёт закрыт, задача готова к архиву."
          : "Суд завершил оркестрацию и передал задачу владельцу.",
        actorCode: "JUDGE",
        nextActorCode: goesToArchive ? "OWNER" : "OWNER",
        currentZone: "court",
        nextZone: goesToArchive ? "archive" : "owner",
        route: ["meeting", "court", goesToArchive ? "archive" : "owner"],
        currentCue: goesToArchive ? "Финал и закрытие" : "Вердикт готов",
        nextCue: goesToArchive ? "Архив миссии" : "Решение owner",
        currentSpeech: latestEvent?.note || (goesToArchive
          ? "Финальная позиция утверждена. Миссия готова к закрытию."
          : "Собрал итоговую позицию команды и передаю владельцу."),
        nextSpeech: goesToArchive
          ? "Сохраняю документы и закрываю миссию в архиве."
          : "Получаю отчёт и принимаю управленческое решение.",
        transitionNote: goesToArchive
          ? "После вердикта задача переходит в архивный контур."
          : "После суда задача уходит на owner gate.",
      };
    }
    if (eventType === "orchestration_error") {
      return {
        mode: "error",
        roomLabel: "Аварийный режим",
        headline: "Ошибка оркестрации",
        signalText: "Система переводит задачу в режим контроля и восстановления.",
        actorCode: "SEC",
        nextActorCode: "DEVOPS",
        currentZone: "meeting",
        nextZone: "ops",
        route: ["worklane", "meeting", "ops"],
        currentCue: "Найден сбой",
        nextCue: "Разбор и восстановление",
        currentSpeech: latestEvent?.note || "Зафиксировал сбой в orchestration. Передаю событие в контур восстановления.",
        nextSpeech: "Проверяю runtime, логи и условия безопасного продолжения.",
        transitionNote: "Ошибка уводит процесс из бизнес-сцены в ops-контур.",
      };
    }
    if (eventType === "OWNER_APPROVED") {
      return {
        mode: "owner-approve",
        roomLabel: "Режим утверждения",
        headline: "Owner одобрил результат",
        signalText: "Решение принято. Остался merge и финальное подтверждение.",
        actorCode: "OWNER",
        nextActorCode: "OWNER",
        currentZone: "owner",
        nextZone: task.status === "DONE" ? "archive" : "owner",
        route: ["court", "owner", task.status === "DONE" ? "archive" : "owner"],
        currentCue: "Решение принято",
        nextCue: task.status === "DONE" ? "Архив миссии" : "Ожидание merge",
        currentSpeech: latestEvent?.note || "Результат меня устраивает. Подтверждаю переход к merge.",
        nextSpeech: task.status === "DONE"
          ? "Сохраняю итог в архив и закрываю миссию."
          : "Жду ручной merge и финального закрытия задачи.",
        transitionNote: task.status === "DONE"
          ? "После approve задача сразу переходит в архив."
          : "Owner открыл финальный merge-gate без возврата в pipeline.",
      };
    }
    if (eventType === "OWNER_REWORK") {
      return {
        mode: "owner-rework",
        roomLabel: "Режим доработки",
        headline: "Owner отправил на доработку",
        signalText: "Маршрут развёрнут обратно в рабочий контур.",
        actorCode: "OWNER",
        nextActorCode: "PM",
        currentZone: "owner",
        nextZone: "worklane",
        route: ["owner", "worklane", "meeting", "court"],
        currentCue: "Возврат на цикл",
        nextCue: "Новый проход pipeline",
        currentSpeech: latestEvent?.note || "Этого недостаточно. Возвращаю миссию в доработку.",
        nextSpeech: "Принимаю обратную связь и запускаю новый проход через команду.",
        transitionNote: "После rework маршрут возвращается из owner gate в коридор исполнения.",
      };
    }
    if (eventType === "OWNER_CLARIFY") {
      return {
        mode: "owner-clarify",
        roomLabel: "Режим уточнений",
        headline: "Нужны уточнения",
        signalText: "Штаб останавливает движение и ждёт дополнительный контекст.",
        actorCode: "OWNER",
        nextActorCode: "COORDINATOR",
        currentZone: "owner",
        nextZone: "reception",
        route: ["owner", "reception", "strategy", "owner"],
        currentCue: "Запрос на уточнение",
        nextCue: "Сбор дополнительного контекста",
        currentSpeech: latestEvent?.note || "Перед принятием решения мне нужны дополнительные вводные.",
        nextSpeech: "Соберу недостающий контекст и верну миссию в штаб.",
        transitionNote: "Процесс уходит из owner gate обратно в приёмную для дозапроса контекста.",
      };
    }
    if (eventType === "OWNER_MERGED") {
      return {
        mode: "owner-merged",
        roomLabel: "Архивный режим",
        headline: "Merge подтверждён",
        signalText: "Цикл завершён, документы переходят в архив миссий.",
        actorCode: "OWNER",
        nextActorCode: "OWNER",
        currentZone: "owner",
        nextZone: "archive",
        route: ["owner", "archive"],
        currentCue: "Merge подтверждён",
        nextCue: "Архивация",
        currentSpeech: latestEvent?.note || "Merge подтверждён. Закрываю миссию.",
        nextSpeech: "Переношу итоговые материалы в архив штаба.",
        transitionNote: "После merge миссия окончательно покидает активный контур.",
      };
    }
    return {
      mode: "pipeline",
      roomLabel: "Операционный режим",
      headline: actionHeadline(task, latestEvent),
      signalText: latestEvent?.label || "Штаб обновляет сцену по текущему статусу задачи.",
      currentCue: "Текущий шаг",
      nextCue: "Следующий шаг",
      transitionNote: "Процесс движется по стандартному маршруту задачи.",
    };
  }

  function buildRouteSteps(routeCodes, currentZone, nextZone) {
    const unique = [];
    routeCodes.filter(Boolean).forEach((code) => {
      if (!unique.includes(code)) unique.push(code);
    });
    if (!unique.includes(currentZone)) {
      unique.unshift(currentZone);
    }
    if (!unique.includes(nextZone)) {
      unique.push(nextZone);
    }
    const currentIndex = Math.max(unique.indexOf(currentZone), 0);
    const nextIndex = Math.max(unique.indexOf(nextZone), Math.min(currentIndex + 1, unique.length - 1));
    return unique.map((code, index) => ({
      code,
      label: zoneLabels[code] || code,
      state: index < currentIndex ? "is-passed" : index === currentIndex ? "is-current" : index === nextIndex ? "is-next" : "",
    }));
  }

  function buildEventFrame(task, scene, currentActor) {
    const progress = buildTaskProgress(task, currentActor);
    const latestEvent = progress.latestEvent;
    const preset = eventFramePreset(task, latestEvent);
    const fallbackActor = latestEvent ? eventPersona(latestEvent) : progress.currentActor;
    const actor = lookupPersona(preset.actorCode || fallbackActor?.code || progress.currentActor?.code);
    const nextActor = lookupPersona(preset.nextActorCode || nextActorForTask(actor, task)?.code);
    const currentZone = preset.currentZone || scene?.zone || actor.zone || "worklane";
    const nextZone = preset.nextZone || nextActor.zone || currentZone;
    const currentZoneLabel = zoneLabels[currentZone] || currentZone || "Штаб";
    const nextZoneLabel = zoneLabels[nextZone] || nextZone || "Следующая зона";
    return {
      ...progress,
      actor,
      nextActor,
      currentZone,
      nextZone,
      currentZoneLabel,
      nextZoneLabel,
      eventType: latestEvent?.event_type || fallbackEventType(task),
      roomMode: preset.mode || "pipeline",
      roomLabel: preset.roomLabel || "Операционный режим",
      headline: preset.headline || actionHeadline(task, latestEvent),
      signalText: preset.signalText || latestEvent?.label || "Штаб обновляет сцену по последнему событию.",
      currentCue: preset.currentCue || "Текущий шаг",
      nextCue: preset.nextCue || "Следующий шаг",
      currentSpeech: preset.currentSpeech || actionSpeech(actor, task, latestEvent, "current"),
      nextSpeech: preset.nextSpeech || actionSpeech(nextActor, task, latestEvent, "next"),
      transitionNote: preset.transitionNote || `Сейчас ${actor.label} ведёт миссию и передаст процесс в ${nextZoneLabel}.`,
      route: buildRouteSteps(preset.route || defaultRouteForStatus(task.status), currentZone, nextZone),
    };
  }

  function renderFrameRoute(frame) {
    return `
      <div class="frame-route" aria-label="Маршрут покадровой сцены">
        ${frame.route.map((step, index) => `
          <div class="frame-route-step ${step.state}">
            <div class="frame-route-index">${index + 1}</div>
            <div class="frame-route-label">${escapeHtml(step.label)}</div>
          </div>
          ${index < frame.route.length - 1 ? `<div class="frame-route-arrow" aria-hidden="true">→</div>` : ""}
        `).join("")}
      </div>
    `;
  }

  function actionHeadline(task, latestEvent) {
    if (latestEvent?.label) return latestEvent.label;
    return {
      NEW: "Миссия поступила в штаб",
      TRIAGED: "Триаж завершён",
      IN_PIPELINE: "Pipeline в движении",
      IN_ROUNDTABLE: "Идёт совещание",
      IN_COURT: "Формируется вердикт",
      WAIT_OWNER: "Ожидается решение owner",
      APPROVED_WAIT_MERGE: "Ожидается merge",
      NEED_INFO: "Нужны уточнения",
      REWORK: "Задача ушла на доработку",
      DONE: "Миссия завершена",
      ARCHIVED: "Миссия заархивирована",
    }[task.status] || "Штаб обрабатывает миссию";
  }

  function actionSpeech(persona, task, latestEvent, role) {
    if (role === "current") {
      return latestEvent?.note || thoughtForPersona(persona, true);
    }
    return {
      WAIT_OWNER: "Жду финальное решение и подтверждение владельца.",
      APPROVED_WAIT_MERGE: "Готов подтвердить merge и закрыть миссию.",
      DONE: "Готов передать материалы в архив штаба.",
    }[task.status] || `Следующим включаюсь в процесс. ${fallbackThought(persona.code, false)}`;
  }

  function renderActionScene(task, scene, currentActor) {
    const frame = buildEventFrame(task, scene, currentActor);
    return `
      <section class="action-stage action-tone-${escapeHtml(personaTone(frame.actor))} room-mode-${escapeHtml(frame.roomMode)}">
        <div class="scene-head action-scene-head">
          <div>
            <div class="scene-title">Последний важный переход</div>
            <div class="scene-subtitle">Это не текущее состояние миссии, а последний зафиксированный переход команды по AuditEvent.</div>
          </div>
          <div class="frame-badges">
            <span class="scene-pill">${escapeHtml(frame.headline)}</span>
            <span class="tag frame-event-code">${escapeHtml(frame.eventType)}</span>
          </div>
        </div>
        <section class="frame-route-wrap">
          <div class="transition-label">Маршрут кадра</div>
          ${renderFrameRoute(frame)}
        </section>
        <div class="action-stage-grid">
          <article class="action-bubble-card is-current">
            <div class="action-bubble-head">
              ${renderPersonaAvatar(frame.actor, { current: true })}
              <div>
                <div class="focus-title">${escapeHtml(frame.actor.label)}</div>
                <div class="focus-subtitle">${escapeHtml(frame.currentZoneLabel)} · ${escapeHtml(frame.actor.code)}</div>
              </div>
            </div>
            <div class="dialog-cue">${escapeHtml(frame.currentCue)}</div>
            <div class="dialog-bubble is-current">${escapeHtml(frame.currentSpeech)}</div>
          </article>
          <section class="transition-stage">
            <div class="transition-head">
              <div>
                <div class="transition-label">Режим комнаты</div>
                <div class="frame-room-name">${escapeHtml(frame.roomLabel)}</div>
              </div>
              <div class="frame-signal">
                <span class="signal-dot"></span>
                <span>${escapeHtml(frame.signalText)}</span>
              </div>
            </div>
            <div class="transition-rail">
              <div class="transition-stop is-current">
                <span>${escapeHtml(frame.currentZoneLabel)}</span>
              </div>
              <div class="transition-lane">
                <div class="transition-lane-fill"></div>
                <div class="transition-packet"></div>
              </div>
              <div class="transition-stop is-next">
                <span>${escapeHtml(frame.nextZoneLabel)}</span>
              </div>
            </div>
            <div class="transition-note">${escapeHtml(frame.transitionNote)}</div>
          </section>
          <article class="action-bubble-card is-next">
            <div class="action-bubble-head">
              ${renderPersonaAvatar(frame.nextActor, { compact: false })}
              <div>
                <div class="focus-title">${escapeHtml(frame.nextActor.label)}</div>
                <div class="focus-subtitle">${escapeHtml(frame.nextZoneLabel)} · ${escapeHtml(frame.nextActor.code)}</div>
              </div>
            </div>
            <div class="dialog-cue is-next">${escapeHtml(frame.nextCue)}</div>
            <div class="dialog-bubble is-next">${escapeHtml(frame.nextSpeech)}</div>
          </article>
        </div>
      </section>
    `;
  }

  function renderProgress(task, currentActor) {
    const progress = buildTaskProgress(task, currentActor);
    const currentIndex = stageOrder.indexOf(normalizedProgressStatus(task.status));
    return `
      <section class="process-card">
        <div class="process-head">
          <div>
            <div class="scene-title">Прогресс миссии</div>
            <div class="scene-subtitle">Понятно, где находится задача, кто сейчас работает и что будет дальше.</div>
          </div>
          <div class="process-percent">${progress.percent}%</div>
        </div>
        <div class="process-meter" aria-label="Прогресс выполнения миссии">
          <div class="process-meter-fill" style="width:${progress.percent}%"></div>
          <div class="process-meter-runner" style="left: calc(${progress.percent}% - 14px);"></div>
        </div>
        <div class="process-caption">
          <span>Сейчас: ${escapeHtml(progress.currentLabel)}</span>
          <span>Следом: ${escapeHtml(progress.nextLabel)}</span>
        </div>
        <div class="process-ticker">
          <div class="process-dots"><span></span><span></span><span></span></div>
          <div class="process-note">${escapeHtml(progress.motionText)}</div>
        </div>
        <div class="process-stats">
          <div class="process-stat">
            <div class="process-stat-label">Handoffs</div>
            <div class="process-stat-value">${progress.handoffCount}</div>
          </div>
          <div class="process-stat">
            <div class="process-stat-label">Документы</div>
            <div class="process-stat-value">${progress.docsCount}</div>
          </div>
          <div class="process-stat">
            <div class="process-stat-label">Live-события</div>
            <div class="process-stat-value">${progress.liveCount}</div>
          </div>
          <div class="process-stat">
            <div class="process-stat-label">Owner gate</div>
            <div class="process-stat-value">${progress.ownerGate ? "Да" : "Нет"}</div>
          </div>
        </div>
        <div class="progress-track progress-track-wide">
        ${stageOrder.map((code, index) => {
          const className = index < currentIndex ? "is-done" : index === currentIndex ? "is-current" : "";
          return `<div class="progress-step ${className}">${escapeHtml(stageLabels[code] || code)}</div>`;
        }).join("")}
        </div>
      </section>
    `;
  }

  function renderTaskView() {
    if (!state.scene) {
      return `<div class="empty-state">Выбери миссию, чтобы открыть сцену.</div>`;
    }
    const task = state.scene.task;
    const scene = state.scene.scene;
    const currentActor = state.scene.current_actor;
    const liveBadge = state.live.taskFeedBadgeCount > 0
      ? `<span class="live-badge">+${state.live.taskFeedBadgeCount} новых</span>`
      : "";
      return `
        <section class="scene-card">
          <div class="scene-head">
            <div>
              <div class="scene-title">Миссия #${task.id}: ${escapeHtml(scene.title)}</div>
            <div class="scene-subtitle">${escapeHtml(scene.subtitle)}</div>
            ${state.scene.mission ? `<div class="scene-subtitle" style="opacity:.92">Единый контур: mission_id = ${state.scene.mission.mission_id} (совпадает с task_id). Telegram и Dashboard пишут в одну запись.</div>` : ""}
          </div>
          <span class="scene-pill">${escapeHtml(task.status)}</span>
        </div>
        <div class="scene-meta">
          <span class="tag">${escapeHtml(task.domain || "Без домена")}</span>
          <span class="tag">${escapeHtml(task.task_type || "general")}</span>
          <span class="tag">${escapeHtml(task.criticality || "MEDIUM")}</span>
          <span class="tag">${escapeHtml(task.plan_or_execute || "PLAN")}</span>
        </div>
          <div class="scene-brief">${escapeHtml(task.owner_text || "Нет текста задачи")}</div>
          ${renderCurrentState(task, currentActor)}
          ${renderChatPreview()}
          ${renderProgress(task, currentActor)}
        </section>

          ${renderStageHero(task, scene, currentActor)}

        ${renderActionScene(task, scene, currentActor)}

        ${renderSpecialistDialogue(task)}

        ${renderMissionChat()}

        <div class="scene-layout">
        <section>
          <div class="office-map">${zoneCards()}</div>

          <section class="scene-card" style="margin-top:1rem;">
            <div class="scene-head">
              <div>
                <div class="scene-title">Сотрудники на сцене</div>
                <div class="scene-subtitle">Активный сотрудник выделен. Реплики и handoffs берутся из текущего pipeline.</div>
              </div>
            </div>
            <div class="cast-strip">
              ${state.scene.cast.map((persona) => {
                const isCurrent = currentActor && currentActor.code === persona.code;
                const thought = thoughtForPersona(persona, isCurrent);
                return `
                  <div class="persona-card ${isCurrent ? "is-current" : ""}">
                    <div class="persona-row">
                      ${renderPersonaAvatar(persona, { current: isCurrent })}
                      <div>
                        <div class="persona-name">${escapeHtml(persona.label)}</div>
                        <div class="persona-role">${escapeHtml(zoneLabels[persona.zone] || persona.zone)} · ${escapeHtml(persona.code)}</div>
                      </div>
                    </div>
                    <div class="persona-thought">${escapeHtml(thought)}</div>
                  </div>
                `;
              }).join("")}
            </div>
          </section>

          <section class="scene-card" style="margin-top:1rem;">
            <div class="scene-head">
              <div>
                <div class="scene-title">История миссии</div>
                <div class="scene-subtitle">Здесь только уже произошедшие события. Для текущего состояния смотри блок «Сейчас по-настоящему» выше.</div>
              </div>
            </div>
            <div class="docs-grid">
              ${state.scene.timeline.map((item) => `
                <div class="doc-card">
                  <div class="doc-head">
                    <div>
                      <div class="doc-title">${escapeHtml(item.title || "Событие")}</div>
                      <div class="doc-subtitle">${formatDate(item.created_at)}</div>
                    </div>
                    ${item.status ? `<span class="scene-pill">${escapeHtml(item.status)}</span>` : ""}
                  </div>
                  <div class="mission-brief">${escapeHtml(item.note || "Без деталей")}</div>
                </div>
              `).join("") || `<div class="empty-state">События пока не сформированы.</div>`}
            </div>
          </section>
          ${renderUnifiedMissionThread()}
        </section>

        <section>
          <section class="scene-card">
            <div class="scene-head">
              <div>
                <div class="scene-title">Live feed миссии</div>
                <div class="scene-subtitle">Лента автообновления экрана. Это мониторинг событий, а не признак того, что AI-Team прямо сейчас работает.</div>
              </div>
              <div class="live-head-meta">
                ${liveBadge}
                <span class="scene-pill">${state.live.userPaused ? "Мониторинг на паузе" : state.scene.live?.can_auto_refresh ? "Мониторинг включён" : "Мониторинг завершён"}</span>
              </div>
            </div>
            <div class="live-feed live-feed-task" data-task-feed>
              ${state.taskFeed.length
                ? state.taskFeed.map((event) => renderLiveEvent(event, { compact: true })).join("")
                : `<div class="empty-state">Пока нет новых live-событий для этой миссии.</div>`}
            </div>
          </section>

          <section class="scene-card" id="mission-docs-panel" style="margin-top:1rem;">
            <div class="scene-head">
              <div>
                <div class="scene-title">Папки отделов</div>
                <div class="scene-subtitle">Handoffs, входные файлы, выводы сотрудников и финальные документы.</div>
              </div>
            </div>
            <div class="upload-card upload-card-inline">
              <div class="doc-title">Добавить файл в миссию</div>
              <div class="scene-subtitle">Файл останется внутри проекта и сразу появится в документах миссии.</div>
              <label class="upload-picker">
                <span class="small-btn">Выбрать: .md, .txt, .docx</span>
                <input id="mission-attachment-input" type="file" accept=".md,.txt,.docx" multiple hidden>
              </label>
              ${renderUploadSelection(state.uploads.missionFiles, "Пока в очередь на загрузку ничего не выбрано.")}
              <div class="inline-actions interactive-layer">
                <button type="button" class="primary-btn" data-action="upload-attachments" ${state.uploads.missionFiles.length ? "" : "disabled"}>Добавить в миссию</button>
              </div>
            </div>
            <div class="docs-grid">
              ${(state.scene.documents || []).map((document) => `
                <div class="doc-card">
                  <div class="doc-head">
                    <div>
                      <div class="doc-title">${escapeHtml(document.title)}</div>
                      <div class="doc-subtitle">${escapeHtml(document.path || document.subtitle || "")}</div>
                    </div>
                    <span class="scene-pill">${document.kind === "handoff" ? String((document.step_index || 0) + 1) : document.kind === "attachment" ? "FILE" : document.kind.toUpperCase()}</span>
                  </div>
                  <div class="mission-brief">${escapeHtml(document.summary || "Документ подготовлен.")}</div>
                  <div class="inline-actions doc-action-row interactive-layer">
                    <button type="button" class="small-btn" data-open-document-key="${document.key}">${document.kind === "handoff" ? "Открыть папку" : document.kind === "attachment" ? "Открыть файл" : "Открыть документ"}</button>
                    ${document.kind === "verdict" ? `<button type="button" class="small-btn window-btn" data-open-document-window="${document.key}">Финальный вердикт отдельно</button>` : ""}
                    <button type="button" class="small-btn download-btn" data-download-document-key="${document.key}">Скачать док. созданный командой</button>
                  </div>
                </div>
              `).join("") || `<div class="empty-state">Документы ещё не подготовлены.</div>`}
            </div>
          </section>

          <section class="scene-card task-action-bar" id="mission-owner-panel" style="margin-top:1rem;">
            <div class="scene-head">
              <div>
                <div class="scene-title">Решение владельца</div>
                <div class="scene-subtitle">Ниже только реальные owner/control actions для текущей фазы. Недоступные кнопки объяснены прямо под ними.</div>
              </div>
            </div>
            <div class="action-grid interactive-layer">
              <button type="button" class="primary-btn" data-action="run-pipeline" ${canRunPipeline(task) ? "" : "disabled"}>Запустить AI-Team</button>
              <button type="button" class="danger-btn" data-action="stop-pipeline" ${canStopTeam() ? "" : "disabled"}>Остановить AI-Team</button>
              <button type="button" class="primary-btn" data-owner-action="approve" ${state.scene.owner_actions.can_approve ? "" : "disabled"}>Утвердить</button>
              <button type="button" class="warn-btn" data-owner-action="rework" ${state.scene.owner_actions.can_rework ? "" : "disabled"}>На доработку</button>
              <button type="button" class="ghost-btn" data-owner-action="clarify" ${state.scene.owner_actions.can_clarify ? "" : "disabled"}>Нужно уточнение</button>
              <button type="button" class="ghost-btn" data-owner-action="merged" ${state.scene.owner_actions.can_mark_merged ? "" : "disabled"}>Подтвердить merge</button>
            </div>
            <div class="docs-grid" style="margin-top:0.75rem;">
              <div class="doc-card">
                <div class="doc-title">Запуск AI-Team</div>
                <div class="mission-brief">${escapeHtml(state.scene.runner?.start_reason || "—")}</div>
              </div>
              <div class="doc-card">
                <div class="doc-title">Остановка AI-Team</div>
                <div class="mission-brief">${escapeHtml(state.scene.runner?.stop_reason || "—")}</div>
              </div>
              <div class="doc-card">
                <div class="doc-title">Утверждение</div>
                <div class="mission-brief">${escapeHtml(state.scene.owner_actions.approve_reason || "—")}</div>
              </div>
              <div class="doc-card">
                <div class="doc-title">Доработка / уточнение / merge</div>
                <div class="mission-brief">${escapeHtml([state.scene.owner_actions.rework_reason, state.scene.owner_actions.clarify_reason, state.scene.owner_actions.merged_reason].filter(Boolean).join(" "))}</div>
              </div>
            </div>
            <div class="scene-subtitle" style="margin-top:0.75rem;">
              ${escapeHtml(buildOwnerPanelSummary(task, currentActor))}
            </div>
          </section>
        </section>
      </div>
    `;
  }

  function renderDocsView() {
    if (!state.docs.length) {
      return `<div class="empty-state">Открой папку отдела, финальный отчёт или вердикт суда, чтобы читать документы прямо с телефона.</div>`;
    }
    return `
      <section class="scene-card current-state-card" id="mission-top">
        <div class="scene-head">
          <div>
            <div class="scene-title">Документы миссии</div>
            <div class="scene-subtitle">Открыт режим чтения. Отсюда можно вернуться обратно в сцену задачи одним нажатием.</div>
          </div>
        </div>
        <div class="inline-actions current-state-actions interactive-layer">
          <button type="button" class="primary-btn" data-action="return-task">Вернуться к миссии</button>
          <button type="button" class="ghost-btn" data-action="scroll-top">К началу экрана</button>
        </div>
      </section>
      <section class="docs-grid">
        ${state.docs.map((doc) => `
          <article class="doc-card">
            <div class="doc-head">
              <div>
                <div class="doc-title">${escapeHtml(doc.title)}</div>
                <div class="doc-subtitle">${escapeHtml(doc.subtitle || "")}</div>
              </div>
            </div>
            <div class="inline-actions doc-action-row interactive-layer">
              ${doc.openUrl ? `<button type="button" class="small-btn window-btn" data-open-document-window="${escapeHtml(doc.key || "")}">Открыть в отдельном окне</button>` : ""}
              ${doc.downloadUrl ? `<button type="button" class="small-btn download-btn" data-download-document-key="${escapeHtml(doc.key || "")}">Скачать док. созданный командой</button>` : ""}
            </div>
            <pre>${escapeHtml(doc.content || "")}</pre>
          </article>
        `).join("")}
      </section>
    `;
  }

  function renderControlView() {
    const latest = latestTask();
    return `
      <section class="scene-card">
        <div class="scene-head">
          <div>
            <div class="scene-title">Управление штабом</div>
            <div class="scene-subtitle">Быстрые переходы для телефона: открыть последнюю миссию, перейти в запасную панель и проверить mobile URL.</div>
          </div>
        </div>
        <div class="inline-actions interactive-layer">
          ${latest ? `<button type="button" class="primary-btn" data-open-task="${latest.id}">Открыть последнюю миссию</button>` : ""}
          <a class="ghost-btn" href="/tasks${apiKeyQuery}">Fallback: классический список задач</a>
          ${state.selectedTaskId ? `<a class="ghost-btn" href="/tasks/${state.selectedTaskId}${apiKeyQuery}">Fallback: детальная карточка</a>` : ""}
        </div>
        <div class="scene-subtitle" style="margin-top: 1rem;">
          Mobile URL для Android в одной Wi-Fi сети: <strong>${escapeHtml(window.location.origin)}${escapeHtml(apiKeyQuery)}</strong>
        </div>
      </section>
    `;
  }

  function renderStaleBanner() {
    if (!state.stale.message) return "";
    return `
      <div class="stale-banner">
        <strong>Связь с live-обновлением ослабла.</strong>
        <span>${escapeHtml(state.stale.message)}</span>
      </div>
    `;
  }

  function render() {
    const draftSnapshot = captureDraftSnapshot();
    const topbarReturnLabel = state.selectedTaskId
      ? state.view === "docs"
        ? "Вернуться к миссии"
        : state.view === "task"
          ? "К началу миссии"
          : "К миссии"
      : "";
      const canToggleLive = Boolean(state.live.userPaused || OVERVIEW_VIEWS.has(state.view) || state.scene?.live?.can_auto_refresh);
      const canJumpToChat = Boolean(state.selectedTaskId && state.view === "task");
      const nav = `
        <nav class="bottom-nav">
        <button class="nav-btn ${state.view === "office" ? "is-active" : ""}" data-nav="office">Офис</button>
        <button class="nav-btn ${state.view === "missions" ? "is-active" : ""}" data-nav="missions">Миссии</button>
        <button class="nav-btn ${state.view === "task" || state.view === "docs" ? "is-active" : ""}" data-nav="task" ${state.selectedTaskId ? "" : "disabled"}>Сцена</button>
        <button class="nav-btn ${state.view === "control" ? "is-active" : ""}" data-nav="control">Управление</button>
      </nav>
    `;

    const content = state.loading
      ? `<div class="empty-state">Загружаю игровой штаб...</div>`
      : state.view === "office"
        ? renderOfficeView()
        : state.view === "missions"
          ? renderMissionsView()
          : state.view === "task"
            ? renderTaskView()
            : state.view === "docs"
              ? renderDocsView()
              : renderControlView();

    root.innerHTML = `
      <div class="office-shell ${state.live.userPaused ? "is-live-paused" : ""}">
        <header class="office-topbar">
          <div>
            <div class="brand-title">MyWave AI-TEAM: Офис</div>
            <div class="brand-subtitle">Игровой центр управления сотрудниками-агентами</div>
          </div>
            <div class="topbar-actions">
              ${state.selectedTaskId ? `<button type="button" class="ghost-btn" data-action="return-task">${topbarReturnLabel}</button>` : ""}
              ${canJumpToChat ? `<button type="button" class="ghost-btn" data-action="scroll-chat">К чату команды</button>` : ""}
              <button type="button" class="ghost-btn" data-action="toggle-live" ${canToggleLive ? "" : "disabled"}>${canToggleLive ? (state.live.userPaused ? "Продолжить live" : "Остановить live") : "Live завершён"}</button>
              <button type="button" class="ghost-btn" data-refresh="all">Обновить</button>
            </div>
        </header>
        ${renderStaleBanner()}
        <main class="office-main">${content}</main>
        ${nav}
        ${state.toast ? `<div class="toast">${escapeHtml(state.toast)}</div>` : ""}
      </div>
    `;
    restoreDraftSnapshot(draftSnapshot);
    syncTaskFeedScroll();
  }

  function syncTaskFeedScroll() {
    if (!state.live.shouldScrollTaskFeed) return;
    const container = root.querySelector("[data-task-feed]");
    if (!container) return;
    container.scrollTop = container.scrollHeight;
    state.live.shouldScrollTaskFeed = false;
  }

  function startPoller(name, interval, callback) {
    stopPoller(name);
    pollers[name] = window.setInterval(() => {
      if (document.hidden) return;
      callback().catch((error) => {
        setStale(name, `Автообновление не удалось: ${error.message}`);
      });
    }, interval);
  }

  function stopPoller(name) {
    if (pollers[name]) {
      window.clearInterval(pollers[name]);
      delete pollers[name];
    }
  }

  function syncPolling() {
    if (state.live.userPaused) {
      stopPoller("tasks");
      stopPoller("officeEvents");
      stopPoller("health");
      stopPoller("taskEvents");
      return;
    }
    startPoller("tasks", POLL_INTERVALS.tasks, pollTasks);

    if (OVERVIEW_VIEWS.has(state.view)) {
      startPoller("officeEvents", POLL_INTERVALS.officeEvents, pollOfficeEvents);
    } else {
      stopPoller("officeEvents");
    }

    if (state.view === "office") {
      startPoller("health", POLL_INTERVALS.health, pollHealth);
    } else {
      stopPoller("health");
    }

    if ((state.view === "task" || state.view === "docs") && state.selectedTaskId && state.scene?.live?.can_auto_refresh) {
      startPoller("taskEvents", state.scene.live.poll_interval_ms || POLL_INTERVALS.taskEvents, pollTaskEvents);
    } else {
      stopPoller("taskEvents");
    }
  }

  async function pollTasks() {
    if (state.live.overviewBusy) return;
    state.live.overviewBusy = true;
    try {
      await refreshTasks();
      clearStale("tasks");
      if (!isComposeLocked()) {
        render();
      }
    } finally {
      state.live.overviewBusy = false;
    }
  }

  async function pollHealth() {
    if (state.live.overviewBusy) return;
    state.live.overviewBusy = true;
    try {
      await refreshHealth();
      clearStale("health");
      if (!isComposeLocked()) {
        render();
      }
    } finally {
      state.live.overviewBusy = false;
    }
  }

  async function pollOfficeEvents() {
    if (state.live.overviewBusy) return;
    state.live.overviewBusy = true;
    try {
      await refreshOfficeFeed();
      clearStale("officeEvents");
      if (!isComposeLocked()) {
        render();
      }
    } finally {
      state.live.overviewBusy = false;
    }
  }

  async function pollTaskEvents() {
    if (!state.selectedTaskId || state.live.taskBusy) return;
    state.live.taskBusy = true;
    try {
      const incoming = await refreshTaskFeed(state.selectedTaskId);
      const hasStructuralEvents = incoming.length && incoming.some((event) => STRUCTURAL_EVENTS.has(event.event_type));
      const composeLocked = isComposeLocked();
      const shouldRefreshScene = state.scene?.runner?.is_active
        || hasStructuralEvents;
      if (shouldRefreshScene) {
        await refreshScene(state.selectedTaskId);
      }
      if (hasStructuralEvents) {
        await refreshTaskFeed(state.selectedTaskId, { reset: true });
        state.live.shouldScrollTaskFeed = true;
      }
      clearStale("taskEvents");
      if (!composeLocked || hasStructuralEvents) {
        render();
      }
    } finally {
      state.live.taskBusy = false;
    }
  }

  async function toggleLiveUpdates() {
    state.live.userPaused = !state.live.userPaused;
    render();
    syncPolling();
    if (state.live.userPaused) {
      setToast("Live поставлен на паузу. Это останавливает только автообновление экрана.");
      return;
    }
    setToast("Live снова включён.");
    try {
      await refreshTasks();
      await refreshOfficeFeed({ reset: true });
      if (state.view === "office") {
        await refreshHealth();
      }
      if (state.selectedTaskId) {
        await refreshScene(state.selectedTaskId);
        await refreshTaskFeed(state.selectedTaskId, { reset: true });
      }
      clearStale();
    } catch (error) {
      setStale("live", `Не удалось возобновить live: ${error.message}`);
    } finally {
      render();
      syncPolling();
    }
  }

  async function returnToTaskView() {
    if (!state.selectedTaskId) return;
    if (!state.scene) {
      await openTask(state.selectedTaskId, { historyMode: "push", withSpinner: true });
      return;
    }
    state.view = "task";
    syncHistory("push");
    render();
    syncPolling();
    window.requestAnimationFrame(() => scrollToTarget("mission-top"));
  }

  function bindEvents() {
    root.addEventListener("focusin", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLTextAreaElement) && !(target instanceof HTMLInputElement)) return;
      if (target.id === "mission-chat-input" || target.id === "task-composer-input") {
        markComposeActivity(target.id);
      }
    });

    root.addEventListener("focusout", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLTextAreaElement) && !(target instanceof HTMLInputElement)) return;
      if (target.id === "mission-chat-input" || target.id === "task-composer-input") {
        clearComposeActivity(target.id);
      }
    });

    root.addEventListener("input", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLTextAreaElement) && !(target instanceof HTMLInputElement)) return;
      if (target.id === "mission-chat-input") {
        state.drafts.missionChat = target.value;
        markComposeActivity(target.id);
      }
      if (target.id === "task-composer-input") {
        state.drafts.taskComposer = target.value;
        markComposeActivity(target.id);
      }
    });

    root.addEventListener("change", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement) || target.type !== "file") return;
      if (target.id === "task-attachment-input") {
        state.uploads.taskComposerFiles = Array.from(target.files || []);
        render();
      }
      if (target.id === "mission-attachment-input") {
        state.uploads.missionFiles = Array.from(target.files || []);
        render();
      }
    });

    root.addEventListener("click", async (event) => {
      const target = event.target.closest("button, a");
      if (!target) return;
      if (target.dataset.nav) {
        const nextView = target.dataset.nav;
        if (nextView === "task" && state.selectedTaskId) {
          await openTask(state.selectedTaskId, { historyMode: "push", withSpinner: false });
          return;
        }
        state.view = nextView;
        if (nextView !== "docs") {
          syncHistory("push");
        }
        render();
        syncPolling();
        return;
      }
      if (target.dataset.refresh) {
        await loadRoute();
        return;
      }
      if (target.dataset.action === "toggle-live") {
        await toggleLiveUpdates();
        return;
      }
      if (target.dataset.action === "return-task") {
        await returnToTaskView();
        return;
      }
        if (target.dataset.action === "scroll-top") {
          scrollToTarget("mission-top");
          return;
        }
        if (target.dataset.action === "scroll-chat") {
          scrollToTarget("mission-chat-panel");
          return;
        }
        if (target.dataset.action === "scroll-owner") {
          scrollToTarget("mission-owner-panel");
          return;
      }
      if (target.dataset.action === "scroll-docs") {
        scrollToTarget("mission-docs-panel");
        return;
      }
      if (target.dataset.openTask) {
        await openTask(Number(target.dataset.openTask), { historyMode: "push", withSpinner: true });
        return;
      }
      if (target.dataset.chatSuggestion) {
        const input = root.querySelector("#mission-chat-input");
        if (input) {
          input.value = target.dataset.chatSuggestion;
          state.drafts.missionChat = target.dataset.chatSuggestion;
          input.focus();
        }
        return;
      }
      if (target.dataset.openDocumentKey) {
        const document = state.scene?.documents?.find((item) => item.key === target.dataset.openDocumentKey);
        if (!document) return;
        try {
          await openDocument(document);
        } catch (error) {
          setToast(`Не удалось открыть документ: ${error.message}`);
        }
        return;
      }
      if (target.dataset.openDocumentWindow) {
        const document = state.scene?.documents?.find((item) => item.key === target.dataset.openDocumentWindow)
          || state.docs.find((item) => item.key === target.dataset.openDocumentWindow);
        if (!document) return;
        openDocumentWindow(document);
        return;
      }
      if (target.dataset.downloadDocumentKey) {
        const document = state.scene?.documents?.find((item) => item.key === target.dataset.downloadDocumentKey)
          || state.docs.find((item) => item.key === target.dataset.downloadDocumentKey);
        if (!document) return;
        downloadDocument(document);
        return;
      }
      if (target.dataset.ownerAction) {
        await submitOwnerAction(target.dataset.ownerAction);
        return;
      }
      if (target.dataset.action === "run-pipeline") {
        await runPipeline();
        return;
      }
      if (target.dataset.action === "stop-pipeline") {
        await stopPipeline();
        return;
      }
      if (target.dataset.action === "send-chat") {
        await submitMissionChat();
        return;
      }
      if (target.dataset.action === "upload-attachments") {
        await submitMissionAttachments();
        return;
      }
      if (target.dataset.action === "create-task") {
        await createTask();
      }
    });

    window.addEventListener("popstate", async () => {
      const taskId = parseTaskIdFromLocation();
      if (taskId) {
        await openTask(taskId, { historyMode: null, withSpinner: true });
        return;
      }
      state.view = "office";
      render();
      syncPolling();
    });

    document.addEventListener("visibilitychange", async () => {
      if (document.hidden) return;
      if (state.view === "office") {
        await Promise.allSettled([pollOfficeEvents(), pollHealth(), pollTasks()]);
      } else if (state.selectedTaskId && (state.view === "task" || state.view === "docs")) {
        await Promise.allSettled([pollTaskEvents(), pollTasks()]);
      }
    });
  }

  async function createTask() {
    const input = document.getElementById("task-composer-input");
    const value = (input?.value || "").trim();
    if (!value) {
      setToast("Сначала опиши миссию.");
      return;
    }
    try {
      const task = await fetchJson("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ owner_text: value }),
      });
      if (state.uploads.taskComposerFiles.length) {
        setToast(`Миссия #${task.id} создана. Сохраняю входные файлы...`);
        await uploadMissionFiles(task.id, state.uploads.taskComposerFiles);
      }
      setToast(`Миссия #${task.id} создана. Запускаю AI-Team в фоне...`);
      state.drafts.taskComposer = "";
      state.uploads.taskComposerFiles = [];
      if (input) input.value = "";
      await fetchJson(`/api/tasks/${task.id}/pipeline/start`, { method: "POST" });
      await Promise.all([refreshTasks(), refreshOfficeFeed({ reset: true })]);
      await openTask(task.id, { historyMode: "push", withSpinner: false });
      setToast(`AI-Team запущен для миссии #${task.id}. Можно остановить его из сцены.`);
    } catch (error) {
      setToast(`Не удалось создать миссию: ${error.message}`);
    }
  }

  async function submitMissionAttachments() {
    if (!state.selectedTaskId) return;
    if (!state.uploads.missionFiles.length) {
      setToast("Сначала выбери хотя бы один файл.");
      return;
    }
    try {
      setToast(`Сохраняю файлы в миссию #${state.selectedTaskId}...`);
      await uploadMissionFiles(state.selectedTaskId, state.uploads.missionFiles);
      state.uploads.missionFiles = [];
      await Promise.all([refreshTasks(), refreshOfficeFeed({ reset: true })]);
      await openTask(state.selectedTaskId, { historyMode: "replace", withSpinner: false });
      setToast("Файлы добавлены в миссию и доступны команде как документы.");
    } catch (error) {
      setToast(`Не удалось добавить файлы: ${error.message}`);
    }
  }

  async function runPipeline() {
    if (!state.selectedTaskId) return;
    try {
      setToast(`Запускаю AI-Team для миссии #${state.selectedTaskId} в фоне...`);
      await fetchJson(`/api/tasks/${state.selectedTaskId}/pipeline/start`, { method: "POST" });
      await Promise.all([refreshTasks(), refreshOfficeFeed({ reset: true })]);
      await openTask(state.selectedTaskId, { historyMode: "replace", withSpinner: false });
      setToast(`AI-Team запущен в фоне для миссии #${state.selectedTaskId}.`);
    } catch (error) {
      setToast(`Не удалось запустить AI-Team: ${error.message}`);
    }
  }

  async function stopPipeline() {
    if (!state.selectedTaskId) return;
    try {
      setToast(`Запрашиваю остановку AI-Team для миссии #${state.selectedTaskId}...`);
      await fetchJson(`/api/tasks/${state.selectedTaskId}/pipeline/stop`, { method: "POST" });
      await openTask(state.selectedTaskId, { historyMode: "replace", withSpinner: false });
      setToast("Остановка запрошена. Дождись безопасной checkpoint-точки.");
    } catch (error) {
      setToast(`Не удалось остановить AI-Team: ${error.message}`);
    }
  }

  async function submitOwnerAction(action) {
    if (!state.selectedTaskId) return;
    const mapping = {
      approve: "approve",
      rework: "rework",
      clarify: "clarify",
      merged: "merged",
    };
    try {
      const path = action === "rework"
        ? `/api/tasks/${state.selectedTaskId}/rework/start`
        : `/api/tasks/${state.selectedTaskId}/${mapping[action]}`;
      await fetchJson(path, { method: "POST" });
      setToast(`Действие "${buttonLabel(action)}" выполнено.`);
      await Promise.all([refreshTasks(), refreshOfficeFeed({ reset: true })]);
      await openTask(state.selectedTaskId, { historyMode: "replace", withSpinner: false });
    } catch (error) {
      setToast(`Ошибка действия: ${error.message}`);
    }
  }

  async function submitMissionChat() {
    if (!state.selectedTaskId) return;
    const input = root.querySelector("#mission-chat-input");
    const message = (input?.value || "").trim();
    if (!message) {
      setToast("Сначала напиши сообщение команде.");
      return;
    }
    try {
      await fetchJson(`/api/tasks/${state.selectedTaskId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      state.drafts.missionChat = "";
      if (input) input.value = "";
      await openTask(state.selectedTaskId, { historyMode: "replace", withSpinner: false });
      setToast("Команда ответила в чате миссии.");
    } catch (error) {
      setToast(`Не удалось отправить сообщение: ${error.message}`);
    }
  }

  function buttonLabel(action) {
    return {
      approve: "Утвердить",
      rework: "На доработку",
      clarify: "Нужно уточнение",
      merged: "Подтвердить merge",
    }[action] || action;
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function fallbackThought(code, isCurrent) {
    const thoughts = {
      COORDINATOR: "Новая миссия зарегистрирована. Подготовлю маршрут.",
      PS: "Собираю продуктовый смысл и итоговую ценность.",
      PM: "Выстраиваю последовательность действий и критерии приёмки.",
      UX: "Смотрю на пользовательский путь и точки трения.",
      FE: "Думаю о состоянии интерфейса и экранных сценариях.",
      BE: "Проверяю контракты, данные и устойчивость backend.",
      ARCH: "Проверяю ограничения архитектуры и границы модулей.",
      QA: "Ищу риски и сценарии проверки.",
      DEVOPS: "Проверяю rollout, rollback и healthcheck.",
      RC: "Сверяю план с реальностью и ограничениями.",
      SEC: "Оцениваю безопасность и чувствительные действия.",
      LEGAL: "Проверяю правовые и публичные обязательства.",
      FIN: "Смотрю на бюджет и коммерческие риски.",
      JUDGE: "Формирую итоговую позицию команды.",
      OWNER: "Жду управленческого решения по миссии.",
    };
    if (isCurrent) return thoughts[code] || "Я сейчас активен на этой сцене.";
    return "Ожидаю свою фазу работы.";
  }

  function labelizeHealth(name) {
    return {
      database: "База данных",
      auth: "Авторизация",
      telegram: "Telegram",
      orchestration: "Оркестрация",
      runner: "Runner",
    }[name] || name;
  }

  bindEvents();
  loadRoute();
})();
