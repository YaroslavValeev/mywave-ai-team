# app/orchestrator/crewai_bridge.py — CrewAI flows/crews (stub для MVP)
# В v0.1: заменить rule-based triage/pipeline на реальные CrewAI flows.

def run_crewai_triage(text: str) -> dict:
    """Stub: в v0.1 вызовет CrewAI Agent для triage."""
    return {}

def run_crewai_pipeline(task_id: int, steps: list, context: dict) -> list:
    """Stub: в v0.1 вызовет CrewAI Crew для pipeline."""
    return []
