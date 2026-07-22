# Unified mission thread: mission_id == task_id, dual entry (Telegram + Dashboard) same store.


def test_api_scene_includes_mission_bundle(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="#TASK test unified mission")
    db_session.commit()

    r = client.get(f"/api/tasks/{t.id}/scene", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "mission" in data
    m = data["mission"]
    assert m["mission_id"] == t.id
    assert m["task_id"] == t.id
    assert m["entrypoints"]["api_mission_scene"] == f"/api/missions/{t.id}/scene"


def test_api_mission_scene_alias_matches_task_scene(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="#TASK alias")
    db_session.commit()

    a = client.get(f"/api/tasks/{t.id}/scene", headers=auth_headers).json()
    b = client.get(f"/api/missions/{t.id}/scene", headers=auth_headers).json()
    # entrypoints.dashboard_task содержит подписанный ?link= с exp — токен меняется между вызовами
    def _mission_core(m):
        m = dict(m)
        ep = dict(m.get("entrypoints") or {})
        for k, v in list(ep.items()):
            if isinstance(v, str) and "link=" in v:
                ep[k] = v.split("link=", 1)[0].rstrip("?")
        m["entrypoints"] = ep
        return m

    assert _mission_core(a["mission"]) == _mission_core(b["mission"])
    assert a["task"]["id"] == b["task"]["id"]


def test_api_create_task_returns_mission_id(client, auth_headers, db_session):
    r = client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"owner_text": "#TASK from api"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == data["mission_id"]
    assert data["mission"]["canonical_store"] == "tasks"


def test_api_mission_thread_merges_audit_and_handoffs(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="#TASK thread merge")
    repo.add_audit_event("task_created", task_id=t.id, payload={"mission_id": t.id})
    repo.add_handoff(
        t.id,
        1,
        "PM",
        {"summary": ["Шаг pipeline"], "next_action": "Дальше"},
        "/tmp/fake.md",
    )
    db_session.commit()

    r = client.get(f"/api/missions/{t.id}/thread?limit=50", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["mission"]["mission_id"] == t.id
    kinds = [x["kind"] for x in data["items"]]
    assert "audit" in kinds
    assert "handoff" in kinds

    r2 = client.get(f"/api/tasks/{t.id}/thread?limit=50", headers=auth_headers)
    assert r2.json()["count"] == data["count"]


def test_api_events_accepts_mission_id_alias(client, auth_headers, db_session):
    from app.storage.repositories import TaskRepository

    repo = TaskRepository(db_session)
    t = repo.create_task(owner_text="#TASK events alias")
    repo.add_audit_event("triage_done", task_id=t.id, payload={"domain": "X"})
    db_session.commit()

    a = client.get(f"/api/events?task_id={t.id}&limit=10", headers=auth_headers).json()
    b = client.get(f"/api/events?mission_id={t.id}&limit=10", headers=auth_headers).json()
    assert a["events"] == b["events"]
    assert b.get("mission_id") == t.id


def test_api_events_mission_task_mismatch_400(client, auth_headers):
    r = client.get("/api/events?task_id=1&mission_id=2&limit=5", headers=auth_headers)
    assert r.status_code == 400
