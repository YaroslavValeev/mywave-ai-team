from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "packages" / "shared-schema" / "entities.yaml"
APPROVAL_PATH = ROOT / "packages" / "shared-policy" / "approval_rules.yaml"
ROUTING_CONTRACT_PATH = ROOT / "packages" / "shared-policy" / "routing_contract.yaml"


def _load_yaml(path: Path) -> dict:
    assert path.exists(), f"Missing contract file: {path}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"Contract must be a mapping: {path}"
    return data


def test_shared_schema_contains_canonical_entities():
    data = _load_yaml(SCHEMA_PATH)
    entities = data.get("entities", {})
    assert isinstance(entities, dict)

    expected = {
        "Project",
        "Task",
        "Run",
        "Decision",
        "Approval",
        "Artifact",
        "MemoryEntry",
        "Channel",
        "Agent",
        "PolicyRule",
        "ExecutionEvent",
    }
    assert expected.issubset(set(entities.keys()))


def test_shared_policy_contains_mandatory_critical_actions():
    data = _load_yaml(APPROVAL_PATH)
    approval = data.get("approval", {})
    critical_actions = approval.get("critical_actions", [])
    assert isinstance(critical_actions, list)

    expected = {
        "codebase_write",
        "git_commit",
        "git_push",
        "patch_application",
        "deploy_release_prod",
        "file_write_outside_sandbox",
        "external_api_action",
        "telegram_production_send",
        "personal_data_operation",
        "money_legal_public_action",
        "destructive_operation",
    }
    assert expected.issubset(set(critical_actions))


def test_routing_contract_requires_core_task_fields():
    data = _load_yaml(ROUTING_CONTRACT_PATH)
    contract = data.get("routing_contract", {})
    required_task_fields = contract.get("required_task_fields", [])
    assert isinstance(required_task_fields, list)
    assert {"domain", "task_type", "criticality", "plan_or_execute", "execute_gate"}.issubset(
        set(required_task_fields)
    )
