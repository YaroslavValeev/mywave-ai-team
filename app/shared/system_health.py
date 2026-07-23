import os

from sqlalchemy import text

from app.config import get_orchestration_config, get_telegram_config
from app.orchestrator.crewai_bridge import is_crewai_enabled
from app.shared.auth import get_owner_api_key
from app.storage.repositories import get_engine


def collect_system_health() -> dict:
    checks = {
        "database": _check_database(),
        "auth": _check_auth(),
        "gateway": _check_gateway(),
        "telegram": _check_telegram(),
        "orchestration": _check_orchestration(),
        "runner": _check_runner(),
    }
    overall = "ok"
    if any(item["status"] == "error" for item in checks.values()):
        overall = "error"
    elif any(item["status"] == "warn" for item in checks.values()):
        overall = "warn"
    return {"status": overall, "checks": checks}


def _check_database() -> dict:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Подключение к базе данных в порядке."}
    except Exception as exc:
        return {"status": "error", "message": f"Проверка БД не удалась: {exc}"}


def _check_auth() -> dict:
    if get_owner_api_key():
        return {"status": "ok", "message": "OWNER_API_KEY настроен."}
    return {"status": "error", "message": "OWNER_API_KEY отсутствует."}


def _check_gateway() -> dict:
    """OpenClaw-style gateway: реестр capabilities из app/config/gateway.yaml."""
    try:
        from app.gateway import gateway_health

        status, message = gateway_health()
        return {"status": status, "message": message}
    except Exception as exc:
        return {"status": "warn", "message": f"Проверка Gateway не удалась: {exc}"}


def _check_telegram() -> dict:
    cfg = get_telegram_config()
    token = cfg.get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = cfg.get("owner_chat_id") or os.getenv("OWNER_CHAT_ID")
    if token and chat_id:
        return {"status": "ok", "message": "Telegram: токен бота и chat id владельца настроены."}
    return {"status": "warn", "message": "Telegram: уведомления настроены не полностью."}


def _check_orchestration() -> dict:
    cfg = get_orchestration_config()
    engine = cfg.get("engine", "auto")
    if engine == "rule_based":
        return {"status": "ok", "message": "Оркестрация: rule-based активна."}

    try:
        from crewai import Agent  # type: ignore
    except Exception as exc:
        status = "warn" if cfg.get("allow_fallback", True) else "error"
        hint = (
            " Установи пакет crewai в образ или верни rule-based: ORCHESTRATION_ENGINE=rule_based в .env."
        )
        return {"status": status, "message": f"CrewAI runtime недоступен: {exc}.{hint}"}

    from app.orchestrator.crewai_bridge import has_llm_credentials

    model = (
        cfg.get("crewai_model")
        or os.getenv("OPENAI_MODEL_NAME")
        or os.getenv("MODEL")
        or os.getenv("CREWAI_DEFAULT_MODEL")
        or ""
    ).strip()
    if not has_llm_credentials():
        status = "warn" if cfg.get("allow_fallback", True) else "error"
        return {
            "status": status,
            "message": "CrewAI enabled but no OPENAI_API_KEY/CREWAI_API_KEY or OPENAI_BASE_URL.",
        }
    if not model and engine == "crewai":
        status = "warn" if cfg.get("allow_fallback", True) else "error"
        return {"status": status, "message": "CrewAI enabled but model not configured (CREWAI_MODEL / CREWAI_DEFAULT_MODEL)."}

    mode = "включён" if is_crewai_enabled() else "неактивен"
    return {"status": "ok", "message": f"CrewAI runtime {mode}; model={model or 'default'}."}


def _check_runner() -> dict:
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        try:
            from app.gateway.secrets import github_token

            token = github_token()
        except Exception:
            token = None
    cursor_hint = ""
    try:
        from app.runners.cursor_runner.runner import get_runner_config

        cr = get_runner_config()
        cursor_hint = (
            f" Cursor CLI: {cr.get('cursor_binary')}"
            f" ({'найден' if cr.get('cursor_binary_exists') else 'не найден в PATH'})."
        )
    except Exception as exc:
        cursor_hint = f" Конфиг Cursor runner недоступен: {exc}."

    if repo and token:
        return {"status": "ok", "message": "Интеграция Runner/PR настроена." + cursor_hint}
    msg = "Интеграция Runner/PR частичная: нет GITHUB_REPOSITORY или GH_TOKEN (проверьте gateway и env)."
    return {"status": "warn", "message": msg + cursor_hint}
