"""Регрессия: #TASK после пробелов/переносов не должен «молчать» в Smart Intake."""
import asyncio
from types import SimpleNamespace


def test_smart_intake_leading_newline_runs_mission(monkeypatch):
    from app.bot import handlers

    calls: list[tuple[str, int, object]] = []

    async def fake_create_mission(owner_text: str, chat_id: int, bot: object, *, source: str = "telegram"):
        calls.append((owner_text, chat_id, bot))

    monkeypatch.setattr(handlers, "create_mission_and_run", fake_create_mission)
    monkeypatch.setattr(handlers, "is_owner", lambda _cid: True)

    msg = SimpleNamespace(
        text="\n\n#TASK проверка после переноса строки",
        chat=SimpleNamespace(id=999),
        bot=object(),
    )
    asyncio.run(handlers.handle_smart_intake_text(msg))
    assert len(calls) == 1
    assert calls[0][0].startswith("#TASK")
    assert "проверка" in calls[0][0]


def test_is_task_command_after_strip():
    from app.bot.handlers import _is_task_command_after_strip

    ok, s = _is_task_command_after_strip("  \n#TASK x")
    assert ok and s.startswith("#TASK")
    ok2, s2 = _is_task_command_after_strip("# TASK y")
    assert ok2 and s2.startswith("# TASK")
    ok3, _ = _is_task_command_after_strip("просто текст")
    assert not ok3
