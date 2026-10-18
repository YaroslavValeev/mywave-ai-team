"""Validate evidence boundaries in the portfolio registry; no network or writes."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


SHA = re.compile(r"[0-9a-f]{40}")
SECRET = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github[_]pat[_][A-Za-z0-9_]+")
STATES = {"unknown", "historical", "observed"}


def validate_registry(document: dict) -> list[str]:
    """Return only field locations and fixed messages, never supplied values."""
    errors: list[str] = []

    def fail(location: str, message: str) -> None:
        errors.append(f"{location}: {message}")

    def scan(value: object, location: str) -> None:
        if isinstance(value, dict):
            for index, (key, item) in enumerate(value.items()):
                scan(key, f"{location}.field[{index}].key")
                scan(item, f"{location}.field[{index}]")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                scan(item, f"{location}[{index}]")
        elif isinstance(value, str):
            if SECRET.search(value):
                fail(location, "credential pattern is forbidden")
            for url in re.findall(r"https?://[^\s<>\"']+", value):
                try:
                    parsed = urlsplit(url)
                    if parsed.username is not None or parsed.password is not None:
                        fail(location, "URL credentials are forbidden")
                except ValueError:
                    fail(location, "invalid URL")

    if not isinstance(document, dict):
        return ["registry: expected object"]
    scan(document, "registry")
    if document.get("schema_version") != 1:
        fail("schema_version", "expected version 1")
    try:
        date.fromisoformat(document.get("as_of", ""))
    except (ValueError, TypeError):
        fail("as_of", "expected ISO calendar date")
    projects = document.get("projects")
    if not isinstance(projects, list) or not projects:
        return errors + ["projects: expected nonempty array"]
    ids: set[str] = set()
    owners: dict[str, int] = {}
    for index, project in enumerate(projects):
        at = f"projects[{index}]"
        if not isinstance(project, dict):
            fail(at, "expected object")
            continue
        project_id = project.get("id")
        if not isinstance(project_id, str) or not project_id:
            fail(at + ".id", "required nonempty string")
        elif project_id in ids:
            fail(at + ".id", "duplicate project id")
        else:
            ids.add(project_id)
        if project.get("kind") not in {"product", "module", "shared_service", "package"}:
            fail(at + ".kind", "unknown classification")
        repository = project.get("repository")
        if repository is not None and not (
            isinstance(repository, str)
            and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
        ):
            fail(at + ".repository", "expected owner/repository or null")
        main_sha = project.get("main_sha")
        if main_sha is not None and not (isinstance(main_sha, str) and SHA.fullmatch(main_sha)):
            fail(at + ".main_sha", "expected full commit SHA or null")
        ci = project.get("ci", {})
        if not isinstance(ci, dict):
            fail(at + ".ci", "expected object")
            ci = {}
        if ci.get("state") == "SUCCESS":
            if not (isinstance(ci.get("sha"), str) and SHA.fullmatch(ci["sha"])):
                fail(at + ".ci.sha", "successful CI requires full commit SHA")
            if not ci.get("evidence_url"):
                fail(at + ".ci.evidence_url", "successful CI requires evidence")
        deployment = project.get("deployment")
        if not isinstance(deployment, dict):
            fail(at + ".deployment", "required object")
            deployment = {}
        if deployment.get("state") not in STATES:
            fail(at + ".deployment.state", "expected unknown, historical or observed")
        deployed_sha = deployment.get("sha")
        if deployed_sha is not None and not (isinstance(deployed_sha, str) and SHA.fullmatch(deployed_sha)):
            fail(at + ".deployment.sha", "expected full commit SHA or null")
        if deployment.get("state") in {"observed", "historical"}:
            if not deployment.get("evidence") or not deployment.get("observed_on"):
                fail(at + ".deployment", "runtime evidence and date are required")
            elif deployment.get("state") == "observed" and deployment["observed_on"] != document.get("as_of"):
                fail(at + ".deployment", "older runtime evidence must be historical")
        if deployment.get("state") == "unknown" and deployed_sha is not None:
            fail(at + ".deployment.sha", "unknown runtime must not inherit a commit SHA")
        acceptance = project.get("acceptance")
        if not isinstance(acceptance, dict):
            fail(at + ".acceptance", "required object")
            acceptance = {}
        if acceptance.get("state") not in {"not_verified", "blocked", "accepted"}:
            fail(at + ".acceptance.state", "invalid acceptance state")
        if acceptance.get("state") == "accepted":
            gates = acceptance.get("gates")
            if not isinstance(gates, list) or not gates or not all(
                isinstance(gate, dict) and gate.get("passed") is True and gate.get("evidence")
                for gate in gates
            ):
                fail(at + ".acceptance", "accepted outcome requires passed evidenced gates")
            if not acceptance.get("accepted_by") or not acceptance.get("accepted_on"):
                fail(at + ".acceptance", "independent acceptance identity and date required")
        domains = project.get("owns_domains", [])
        if not isinstance(domains, list) or any(not isinstance(domain, str) for domain in domains):
            fail(at + ".owns_domains", "expected array of domain strings")
        else:
            for domain in domains:
                if domain in owners:
                    fail(at + ".owns_domains", "domain already has a canonical owner")
                owners[domain] = index
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    args = parser.parse_args()
    try:
        document = json.loads(args.registry.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("registry: could not read valid JSON")
        return 2
    errors = validate_registry(document)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Registry valid: {len(document['projects'])} projects; as_of={document['as_of']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
