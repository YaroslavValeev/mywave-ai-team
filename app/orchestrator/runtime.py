from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Callable

logger = logging.getLogger(__name__)

_RUN_LIFECYCLE_LISTENERS: list[Callable[[str, int, str, dict], None]] = []


def register_run_lifecycle_listener(fn: Callable[[str, int, str, dict], None]) -> None:
    """Подписка на started/terminal без циклических импортов (SoT persistence)."""
    if fn not in _RUN_LIFECYCLE_LISTENERS:
        _RUN_LIFECYCLE_LISTENERS.append(fn)


def _emit_run_lifecycle(event: str, task_id: int, run_id: str, state: dict) -> None:
    for fn in _RUN_LIFECYCLE_LISTENERS:
        try:
            fn(event, task_id, run_id, state)
        except Exception:
            logger.exception("run_lifecycle listener failed event=%s task_id=%s run_id=%s", event, task_id, run_id)


PHASE_LABELS = {
    "idle": "Ожидание",
    "queued": "В очереди",
    "triage": "Триаж",
    "pipeline": "Pipeline",
    "roundtable": "Совещание",
    "court": "Суд",
    "finalize": "Финализация",
}


class OrchestrationCancelled(RuntimeError):
    pass


def _iso_now() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class OrchestrationControl:
    manager: "OrchestrationRuntime"
    task_id: int
    run_id: str
    cancel_event: threading.Event

    def set_phase(self, phase: str, *, message: str = "", current_step: str = ""):
        self.manager.update(
            self.task_id,
            self.run_id,
            phase=phase,
            phase_label=PHASE_LABELS.get(phase, phase),
            message=message,
            current_step=current_step,
        )

    def check_cancelled(self):
        if self.cancel_event.is_set():
            raise OrchestrationCancelled("Background orchestration cancelled by user.")

    def snapshot(self) -> dict:
        return self.manager.snapshot(self.task_id)


class OrchestrationRuntime:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[int, dict] = {}
        self._cancel_events: dict[int, threading.Event] = {}
        self._threads: dict[int, threading.Thread] = {}

    def snapshot(self, task_id: int) -> dict:
        with self._lock:
            state = dict(self._jobs.get(task_id) or {})
        if state:
            return state
        return {
            "task_id": task_id,
            "run_id": "",
            "state": "idle",
            "phase": "idle",
            "phase_label": PHASE_LABELS["idle"],
            "message": "",
            "current_step": "",
            "started_at": None,
            "finished_at": None,
            "requested_stop_at": None,
            "last_error": "",
            "result_status": "",
            "is_active": False,
            "can_stop": False,
        }

    def update(self, task_id: int, run_id: str, **fields) -> dict:
        with self._lock:
            current = self._jobs.get(task_id)
            if not current or current.get("run_id") != run_id:
                return self.snapshot(task_id)
            current.update(fields)
            return dict(current)

    def start(self, task_id: int, *, source: str, target: Callable[[OrchestrationControl], dict]) -> dict:
        with self._lock:
            current = self._jobs.get(task_id)
            if current and current.get("state") in {"running", "stopping"}:
                raise RuntimeError("AI-Team уже выполняет эту миссию.")

            run_id = uuid.uuid4().hex[:10]
            cancel_event = threading.Event()
            state = {
                "task_id": task_id,
                "run_id": run_id,
                "source": source,
                "state": "running",
                "phase": "queued",
                "phase_label": PHASE_LABELS["queued"],
                "message": "AI-Team запускается в фоне.",
                "current_step": "",
                "started_at": _iso_now(),
                "finished_at": None,
                "requested_stop_at": None,
                "last_error": "",
                "result_status": "",
                "is_active": True,
                "can_stop": True,
            }
            self._jobs[task_id] = state
            self._cancel_events[task_id] = cancel_event

            started = dict(state)
            _emit_run_lifecycle("started", task_id, run_id, started)

            thread = threading.Thread(
                target=self._run_thread,
                args=(task_id, run_id, target, cancel_event),
                name=f"mywave-task-{task_id}-{run_id}",
                daemon=True,
            )
            self._threads[task_id] = thread
            thread.start()
            return started

    def request_stop(self, task_id: int) -> dict:
        with self._lock:
            current = self._jobs.get(task_id)
            if not current or current.get("state") not in {"running", "stopping"}:
                raise RuntimeError("Для этой миссии нет активного AI-Team процесса.")
            current["state"] = "stopping"
            current["message"] = "Остановка запрошена. Ждём безопасную checkpoint-точку."
            current["requested_stop_at"] = _iso_now()
            current["can_stop"] = False
            cancel_event = self._cancel_events.get(task_id)
        if cancel_event:
            cancel_event.set()
        return dict(current)

    def reset_for_tests(self):
        with self._lock:
            task_ids = list(self._threads.keys())
            threads = list(self._threads.values())
            events = list(self._cancel_events.values())
        for event in events:
            event.set()
        for thread in threads:
            thread.join(timeout=0.5)
        with self._lock:
            for task_id in task_ids:
                self._threads.pop(task_id, None)
                self._cancel_events.pop(task_id, None)
                self._jobs.pop(task_id, None)

    def _run_thread(
        self,
        task_id: int,
        run_id: str,
        target: Callable[[OrchestrationControl], dict],
        cancel_event: threading.Event,
    ):
        control = OrchestrationControl(manager=self, task_id=task_id, run_id=run_id, cancel_event=cancel_event)
        try:
            result = target(control) or {}
        except OrchestrationCancelled as exc:
            self.update(
                task_id,
                run_id,
                state="cancelled",
                message=str(exc),
                finished_at=_iso_now(),
                is_active=False,
                can_stop=False,
            )
            self._emit_terminal(task_id, run_id)
        except Exception as exc:
            self.update(
                task_id,
                run_id,
                state="failed",
                message="AI-Team остановился с ошибкой.",
                last_error=str(exc),
                finished_at=_iso_now(),
                is_active=False,
                can_stop=False,
            )
            self._emit_terminal(task_id, run_id)
        else:
            self.update(
                task_id,
                run_id,
                state="completed",
                message=result.get("summary", "Фоновый проход завершён."),
                result_status=result.get("status", ""),
                finished_at=_iso_now(),
                is_active=False,
                can_stop=False,
            )
            self._emit_terminal(task_id, run_id)
        finally:
            with self._lock:
                self._threads.pop(task_id, None)
                self._cancel_events.pop(task_id, None)

    def _emit_terminal(self, task_id: int, run_id: str) -> None:
        with self._lock:
            current = self._jobs.get(task_id)
            if not current or current.get("run_id") != run_id:
                return
            snapshot = dict(current)
        _emit_run_lifecycle("terminal", task_id, run_id, snapshot)


_runtime = OrchestrationRuntime()


def get_orchestration_runtime() -> OrchestrationRuntime:
    return _runtime
