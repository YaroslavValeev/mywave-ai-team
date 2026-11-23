from __future__ import annotations

from app.orchestrator.business_plan_intent import (
    build_business_plan_draft,
    detect_business_plan_intent,
    render_owner_decision_pack_md,
    specialist_lines_for_step,
    telegram_decision_pack_hint,
)


SAMPLE = """
#TASK BUSINESS / finance-business: пересчитать окупаемость клуба водных дисциплин.
Заказчик: ФВЛС. Loaded CAPEX. РГУФК бесплатные часы. 3 группы. 2 500 000 и 300 000.
Коммерческие взрослые платят. Дети U14.
"""


def test_detect_business_plan_intent():
    assert detect_business_plan_intent(SAMPLE, {"domain": "PRODUCT_DEV"}) is True
    assert detect_business_plan_intent("починить кнопку", {}) is False
    assert detect_business_plan_intent("x", {"domain": "BUSINESS"}) is True


def test_draft_has_hypotheses_simulations_probs():
    draft = build_business_plan_draft(SAMPLE)
    assert len(draft["hypotheses"]) >= 3
    assert len(draft["simulations"]) >= 3
    assert len(draft["probabilities"]) >= 2
    assert all(0 < p["p"] <= 1 for p in draft["probabilities"])
    assert draft["role_summaries"]["FIN"]
    md = render_owner_decision_pack_md(draft)
    joined = "\n".join(md)
    assert "Пакет решения владельца" in joined
    assert "Вероятности успеха" in joined
    assert "Гипотезы" in joined
    fin_lines = specialist_lines_for_step(draft, "FIN")
    assert any("Симуляции" in x or "FIN" in x or "финанс" in x.lower() or "Unit" in x for x in fin_lines)
    hint = telegram_decision_pack_hint(draft)
    assert "P:" in hint or "≈" in hint
