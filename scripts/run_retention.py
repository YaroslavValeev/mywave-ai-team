import json

from app.config import get_orchestration_config
from app.storage.repositories import get_session_factory
from app.storage.retention import run_retention_cleanup


def main() -> int:
    retention_days = get_orchestration_config().get("retention_days", 90)
    Session = get_session_factory()
    with Session() as session:
        result = run_retention_cleanup(session, retention_days)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
