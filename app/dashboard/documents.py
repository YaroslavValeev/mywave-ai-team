from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from app.shared.redaction import redact


COURT_VERDICT_STEP = "COURT_VERDICT"
OWNER_DOCUMENT_ROLES = {"owner_decision", "owner_clarification", "owner_rework", "owner_merge_confirmation"}
ATTACHMENT_DOCUMENT_ROLES = {"source_attachment"}


def is_verdict_handoff(handoff) -> bool:
    payload = getattr(handoff, "payload_json", None) or {}
    return getattr(handoff, "step_name", "") == COURT_VERDICT_STEP or payload.get("document_role") == "final_verdict"


def is_owner_document_handoff(handoff) -> bool:
    payload = getattr(handoff, "payload_json", None) or {}
    return payload.get("document_role") in OWNER_DOCUMENT_ROLES


def is_attachment_handoff(handoff) -> bool:
    payload = getattr(handoff, "payload_json", None) or {}
    return payload.get("document_role") in ATTACHMENT_DOCUMENT_ROLES


def list_regular_handoffs(task) -> list:
    return [
        handoff
        for handoff in _sorted_handoffs(task)
        if not is_verdict_handoff(handoff) and not is_owner_document_handoff(handoff) and not is_attachment_handoff(handoff)
    ]


def list_owner_document_handoffs(task) -> list:
    return [handoff for handoff in _sorted_handoffs(task) if is_owner_document_handoff(handoff)]


def list_attachment_handoffs(task) -> list:
    return [handoff for handoff in _sorted_handoffs(task) if is_attachment_handoff(handoff)]


def latest_verdict_handoff(task):
    verdicts = [handoff for handoff in _sorted_handoffs(task) if is_verdict_handoff(handoff)]
    return verdicts[-1] if verdicts else None


def build_task_documents(task) -> list[dict]:
    documents = []
    verdict_handoff = latest_verdict_handoff(task)

    if verdict_handoff and verdict_handoff.md_path:
        payload = verdict_handoff.payload_json or {}
        documents.append(
            {
                "key": "verdict",
                "kind": "verdict",
                "title": "Финальный вердикт суда",
                "subtitle": "Каноничное решение команды после суда",
                "path": verdict_handoff.md_path,
                "summary": _summary_from_payload(
                    payload,
                    "Команда зафиксировала итоговое решение. Используйте этот документ как опорный verdict при следующих действиях по задаче.",
                ),
                "created_at": verdict_handoff.created_at.isoformat() if verdict_handoff.created_at else None,
            }
        )

    if getattr(task, "report_path", None):
        documents.append(
            {
                "key": "report",
                "kind": "report",
                "title": "Финальный отчёт",
                "subtitle": "Развёрнутый итог по задаче",
                "path": task.report_path,
                "summary": redact(task.summary or "Court report уже сохранён и готов к чтению."),
                "created_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        )

    for handoff in list_attachment_handoffs(task):
        payload = handoff.payload_json or {}
        title = payload.get("document_title") or payload.get("original_name") or Path(handoff.md_path or "").name or "Вложенный файл"
        documents.append(
            {
                "key": f"artifact-{handoff.id}",
                "kind": "attachment",
                "title": title,
                "subtitle": payload.get("document_subtitle") or "Входной файл миссии",
                "path": handoff.md_path,
                "summary": _summary_from_payload(
                    payload,
                    "Файл добавлен владельцем в контекст миссии. Команда сможет ссылаться на него в следующих шагах.",
                ),
                "created_at": handoff.created_at.isoformat() if handoff.created_at else None,
                "artifact_id": handoff.id,
                "step_index": handoff.step_index,
                "step_name": handoff.step_name,
            }
        )

    for handoff in list_owner_document_handoffs(task):
        payload = handoff.payload_json or {}
        documents.append(
            {
                "key": f"artifact-{handoff.id}",
                "kind": "owner",
                "title": payload.get("document_title") or "Документ владельца",
                "subtitle": payload.get("document_subtitle") or f"{handoff.step_name} · {handoff.created_at.isoformat() if handoff.created_at else '-'}",
                "path": handoff.md_path,
                "summary": _summary_from_payload(payload, "Решение владельца сохранено в проекте."),
                "created_at": handoff.created_at.isoformat() if handoff.created_at else None,
                "artifact_id": handoff.id,
                "step_index": handoff.step_index,
                "step_name": handoff.step_name,
            }
        )

    for handoff in list_regular_handoffs(task):
        payload = handoff.payload_json or {}
        documents.append(
            {
                "key": f"artifact-{handoff.id}",
                "kind": "handoff",
                "title": payload.get("document_title") or handoff.step_name,
                "subtitle": f"{handoff.step_name} · {handoff.created_at.isoformat() if handoff.created_at else '-'}",
                "path": handoff.md_path,
                "summary": _summary_from_payload(payload, "Документ подготовлен."),
                "created_at": handoff.created_at.isoformat() if handoff.created_at else None,
                "artifact_id": handoff.id,
                "step_index": handoff.step_index,
                "step_name": handoff.step_name,
            }
        )

    return documents


def read_task_document(task, document_key: str) -> dict | None:
    if document_key == "report" and getattr(task, "report_path", None):
        return _read_document(
            key="report",
            kind="report",
            title="Финальный отчёт",
            subtitle="Court report",
            path=task.report_path,
            summary=redact(task.summary or "Court report уже сохранён и готов к чтению."),
        )

    if document_key == "verdict":
        verdict_handoff = latest_verdict_handoff(task)
        if verdict_handoff and verdict_handoff.md_path:
            payload = verdict_handoff.payload_json or {}
            return _read_document(
                key="verdict",
                kind="verdict",
                title="Финальный вердикт суда",
                subtitle="Каноничное решение команды после суда",
                path=verdict_handoff.md_path,
                summary=_summary_from_payload(
                    payload,
                    "Команда зафиксировала итоговое решение. Используйте этот документ как опорный verdict при следующих действиях по задаче.",
                ),
            )
        return None

    if document_key.startswith("artifact-"):
        try:
            artifact_id = int(document_key.split("-", 1)[1])
        except ValueError:
            return None
        handoff = _find_document_handoff(task, artifact_id)
        if handoff and handoff.md_path:
            payload = handoff.payload_json or {}
            role = payload.get("document_role")
            return _read_document(
                key=document_key,
                kind=_kind_from_role(role),
                title=_title_for_handoff(handoff, payload),
                subtitle=payload.get("document_subtitle") or handoff.step_name,
                path=handoff.md_path,
                summary=_summary_for_role(role, payload),
            )
    return None


def preview_document_bytes(name: str, content: bytes, limit: int = 320) -> str:
    suffix = Path(name or "").suffix.lower()
    if suffix == ".docx":
        text = _extract_docx_text(BytesIO(content))
    else:
        text = content.decode("utf-8", errors="ignore")
    compact = " ".join(text.split())
    if not compact:
        return ""
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def extract_document_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return _extract_docx_text(file_path)
    return file_path.read_text(encoding="utf-8", errors="ignore")


def _sorted_handoffs(task) -> list:
    return sorted(getattr(task, "handoffs", []) or [], key=lambda item: (item.step_index, item.id))


def _find_document_handoff(task, artifact_id: int):
    for handoff in _sorted_handoffs(task):
        if handoff.id == artifact_id and not is_verdict_handoff(handoff):
            return handoff
    return None


def _kind_from_role(role: str | None) -> str:
    if role in ATTACHMENT_DOCUMENT_ROLES:
        return "attachment"
    if role in OWNER_DOCUMENT_ROLES:
        return "owner"
    return "handoff"


def _title_for_handoff(handoff, payload: dict) -> str:
    if payload.get("document_title"):
        return payload["document_title"]
    if payload.get("original_name"):
        return payload["original_name"]
    return getattr(handoff, "step_name", "") or "Документ"


def _summary_for_role(role: str | None, payload: dict) -> str:
    defaults = {
        "source_attachment": "Файл добавлен владельцем в контекст миссии. Команда сможет ссылаться на него в следующих шагах.",
        "owner_decision": "Решение владельца сохранено в проекте.",
        "owner_clarification": "Уточнение владельца сохранено в проекте.",
        "owner_rework": "Решение о доработке сохранено в проекте.",
        "owner_merge_confirmation": "Подтверждение merge сохранено в проекте.",
    }
    return _summary_from_payload(payload, defaults.get(role, "Документ подготовлен."))


def _summary_from_payload(payload: dict, default: str) -> str:
    summary = payload.get("summary")
    if isinstance(summary, list):
        for item in summary:
            if item:
                return redact(str(item))
    if summary:
        return redact(str(summary))
    return redact(default)


def _read_document(*, key: str, kind: str, title: str, subtitle: str, path: str, summary: str) -> dict | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    return {
        "key": key,
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "path": path,
        "summary": summary,
        "content": redact(extract_document_text(file_path)),
    }


def _extract_docx_text(source) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(source) as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError:
            return ""
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    return "\n\n".join(paragraphs)
