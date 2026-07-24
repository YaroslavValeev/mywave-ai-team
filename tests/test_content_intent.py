"""Content outreach draft for MEDIA_OPS/content_pipeline."""

from app.orchestrator.content_intent import build_content_outreach_draft, is_content_outreach_brief


def test_is_content_outreach_brief():
    assert is_content_outreach_brief("собери контакты из ParserNews и напиши сообщение")
    assert not is_content_outreach_brief("почини баг в docker compose")


def test_build_content_outreach_draft_includes_message_and_limits():
    brief = (
        "#TASK Собери контакты из ParserNews. Дружелюбное сообщение: MyWave+Loaded, "
        "Озернинское, чистая вода, mywavewake.ru, Telegram MyWave_Admin и MyWave_WakesurfNews."
    )
    draft = build_content_outreach_draft(brief)
    assert any("Привет" in x for x in draft["message_draft"])
    assert any("ParserNews" in x for x in draft["contact_plan"])
    assert any("EXECUTE" in x or "не выполняются" in x.lower() for x in draft["honest_limits"])
    assert any("MyWave_Admin" in x or "@MyWave_Admin" in x for x in draft["channels_cta"] + draft["message_draft"])
