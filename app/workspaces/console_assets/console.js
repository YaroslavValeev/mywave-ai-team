"use strict";
const el = id => document.getElementById(id);
let projects = [], selected = null, busy = false, generation = 0;
let executionTask = null, executionState = null;
const statusLabels = {NEW:"Новая задача",REWORK:"На доработке",WAIT_OWNER:"Ожидает утверждения",EXECUTION_READY:"Готова к запуску",EXECUTING:"Выполняется",EXECUTION_FAILED:"Ошибка исполнения",APPROVED_WAIT_MERGE:"PR готов к проверке",DONE:"Завершена"};
const phaseLabels = {queued:"В очереди",claimed:"Принята к исполнению",preflight:"Проверка условий",access:"Проверка доступа к репозиторию",validation:"Проверка тестами",commit:"Сохранение изменений",publish:"Создание PR"};
function closeExecution() { executionTask = null; executionState = null; el("execution-panel").hidden = true; el("patch-text").value = ""; el("proposal-patch").textContent = ""; el("proposal-plan").textContent = ""; el("approval-check").checked = false; }
function message(text, error = false) { el("message").textContent = text; el("message").dataset.error = String(error); }
function clearTasks() { el("tasks").replaceChildren(); el("empty").hidden = true; closeExecution(); }
function loggedOut() {
  generation++; projects = []; selected = null; clearTasks(); el("project").replaceChildren(); el("task-text").value = "";
  el("login-panel").hidden = false; el("project-panel").hidden = true;
}
function controls() {
  el("task-form").hidden = !selected || !selected.can_create;
  el("read-only").hidden = !selected || selected.can_create;
  el("create").disabled = busy || !selected || !selected.can_create;
  el("task-text").disabled = !selected || !selected.can_create;
  el("project").disabled = busy; el("refresh").disabled = busy;
  document.querySelectorAll("#execution-panel button, #tasks button").forEach(button => { button.disabled = busy; });
  el("patch-approve").disabled = busy || !el("approval-check").checked;
}
async function api(path, options = {}) {
  const response = await fetch("/api/workspaces" + path, {credentials: "same-origin", cache: "no-store", ...options});
  if (!response.ok) { const error = new Error(response.status === 403 ? "Доступ закрыт или сессия истекла. Войдите снова." : "Не удалось выполнить запрос. Обновите страницу и повторите."); error.status = response.status; throw error; }
  return response.json();
}
function fail(error) { clearTasks(); if (error.status === 403) loggedOut(); message(error.message, true); }
async function loadTasks() {
  clearTasks(); if (!selected) return;
  const version = ++generation, project = selected;
  const tasks = await api(`/${project.workspace_id}/projects/${project.project_id}/tasks`);
  if (version !== generation) return;
  for (const task of tasks) { const li = document.createElement("li"), title = document.createElement("strong"), text = document.createElement("span"), button = document.createElement("button"); title.textContent = `#${task.id} · ${statusLabels[task.status] || task.status}`; text.textContent = task.owner_text; button.type = "button"; button.className = "secondary"; button.textContent = "Исполнение"; button.addEventListener("click", () => action(() => openExecution(task.id))); li.append(title, text, button); el("tasks").append(li); }
  el("empty").hidden = tasks.length !== 0;
}
async function loadProjects() {
  clearTasks(); const old = selected;
  projects = await api("/projects"); el("project").replaceChildren();
  projects.forEach((project, index) => { const option = document.createElement("option"); option.value = String(index); option.textContent = `${project.workspace_name} / ${project.project_name}`; el("project").append(option); });
  let index = projects.findIndex(p => old && p.project_id === old.project_id && p.workspace_id === old.workspace_id);
  if (index < 0) index = 0;
  selected = projects[index] || null; el("project").value = String(index);
  el("login-panel").hidden = true; el("project-panel").hidden = false; controls();
  message(selected ? "" : "Доступных проектов пока нет. Обратитесь к владельцу доступа."); await loadTasks();
}
async function action(fn) { if (busy) return; busy = true; controls(); try { await fn(); } catch (error) { fail(error); } finally { busy = false; controls(); } }
function executionPath() { if (!selected || !executionTask) throw new Error("Сначала выберите задачу."); return `/${selected.workspace_id}/projects/${selected.project_id}/tasks/${executionTask}/execution`; }
async function openExecution(taskId) {
  const project = selected, version = generation;
  if (!project) return;
  const path = `/${project.workspace_id}/projects/${project.project_id}`;
  const [profiles, state] = await Promise.all([api(path + "/execution/profiles"), api(path + `/tasks/${taskId}/execution`)]);
  if (version !== generation || selected !== project) return;
  closeExecution(); executionTask = taskId; executionState = state;
  el("execution-title").textContent = `Исполнение задачи #${taskId}`;
  const run = state.run ? ` · ${phaseLabels[state.run.phase] || state.run.phase}` : "";
  el("execution-summary").textContent = `${statusLabels[state.status] || state.status}${run}. ${state.summary || ""}`;
  el("execution-unavailable").hidden = profiles.enabled && profiles.profiles.length > 0;
  el("execution-profile").replaceChildren();
  profiles.profiles.forEach(profile => { const option = document.createElement("option"); option.value = profile.id; option.textContent = profile.repository; el("execution-profile").append(option); });
  el("patch-form").hidden = !project.can_create || !profiles.enabled || !profiles.profiles.length || !["NEW", "REWORK", "EXECUTION_FAILED"].includes(state.status);
  const proposal = state.proposal;
  el("proposal-panel").hidden = !proposal;
  if (proposal) { const plan = proposal.plan; el("proposal-plan").textContent = `Репозиторий: ${plan.repository}\nИсходный commit: ${plan.base_sha}\nPatch SHA256: ${plan.patch_sha256}\nУтверждение: ${proposal.proposal_sha256}\nПроверка: Python/pytest в изолированной среде, без сети и ключей`; el("proposal-patch").textContent = proposal.patch_text; }
  const canApprove = profiles.enabled && state.can_approve && state.status === "WAIT_OWNER";
  el("approval-label").hidden = !canApprove; el("patch-approve").hidden = !canApprove; el("patch-rework").hidden = !canApprove;
  el("patch-start").hidden = !profiles.enabled || !project.can_create || state.status !== "EXECUTION_READY";
  const safePR = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+$/.test(state.pr_url || "");
  el("execution-pr").hidden = !safePR; el("execution-pr").removeAttribute("href"); if (safePR) el("execution-pr").href = state.pr_url;
  el("execution-panel").hidden = false;
}
async function writeExecution(suffix, body) { const task = executionTask; await api(executionPath() + suffix, {method:"POST", headers:{"Content-Type":"application/json", "X-Workspace-Request":"1"}, body:JSON.stringify(body)}); await loadTasks(); await openExecution(task); }
el("execution-close").addEventListener("click", closeExecution);
el("execution-refresh").addEventListener("click", () => action(() => openExecution(executionTask)));
el("approval-check").addEventListener("change", controls);
el("patch-form").addEventListener("submit", event => { event.preventDefault(); action(async () => { await writeExecution("/prepare", {profile_id:el("execution-profile").value, patch_text:el("patch-text").value}); message("Patch подготовлен. Владелец должен проверить его перед запуском."); }); });
el("patch-approve").addEventListener("click", () => action(async () => { if (!el("approval-check").checked) return; await writeExecution("/decision", {proposal_sha256:executionState.proposal.proposal_sha256, decision:"approve"}); message("Patch утверждён. Для исполнения нажмите кнопку запуска."); }));
el("patch-rework").addEventListener("click", () => action(() => writeExecution("/decision", {proposal_sha256:executionState.proposal.proposal_sha256, decision:"rework"})));
el("patch-start").addEventListener("click", () => action(async () => { await writeExecution("/start", {proposal_sha256:executionState.proposal.proposal_sha256}); message("Исполнение поставлено в очередь. Обновляйте состояние; merge автоматически не выполняется."); }));
el("login-form").addEventListener("submit", event => { event.preventDefault(); action(async () => {
  try { await api("/session", {method: "POST", headers: {"X-API-Key": el("key").value}}); } finally { el("key").value = ""; }
  await loadProjects();
}); });
el("project").addEventListener("change", () => action(async () => { selected = projects[Number(el("project").value)] || null; el("task-text").value = ""; message(""); await loadTasks(); }));
el("refresh").addEventListener("click", () => action(loadProjects));
el("logout").addEventListener("click", () => action(async () => { await api("/session", {method: "DELETE", headers: {"X-Workspace-Request": "1"}}); loggedOut(); message("Вы вышли из проекта."); }));
el("task-form").addEventListener("submit", event => { event.preventDefault(); action(async () => {
  if (!selected || !selected.can_create) return;
  const text = el("task-text").value.trim(); if (!text) { message("Опишите задачу.", true); return; }
  await api(`/${selected.workspace_id}/projects/${selected.project_id}/tasks`, {method: "POST", headers: {"Content-Type": "application/json", "X-Workspace-Request": "1"}, body: JSON.stringify({owner_text: text})});
  el("task-text").value = ""; await loadTasks(); message("Задача создана. Исполнение ещё не запускалось.");
}); });
action(async () => { try { await loadProjects(); } catch (error) { if (error.status === 403) { loggedOut(); message("Введите отдельный ключ доступа к проектам."); } else throw error; } });
