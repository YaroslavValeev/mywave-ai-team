"use strict";
const el = id => document.getElementById(id);
let projects = [], selected = null, busy = false, generation = 0;
function message(text, error = false) { el("message").textContent = text; el("message").dataset.error = String(error); }
function clearTasks() { el("tasks").replaceChildren(); el("empty").hidden = true; }
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
  for (const task of tasks) { const li = document.createElement("li"), title = document.createElement("strong"), text = document.createElement("span"); title.textContent = `#${task.id} · ${task.status}`; text.textContent = task.owner_text; li.append(title, text); el("tasks").append(li); }
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
