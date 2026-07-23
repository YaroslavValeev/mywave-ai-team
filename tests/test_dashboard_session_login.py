# tests/test_dashboard_session_login.py — cookie-вход владельца без ?api_key=
from fastapi.testclient import TestClient

from app.dashboard.app import app
from app.shared.dashboard_session import COOKIE_NAME, sign_owner_session, verify_owner_session


def test_sign_verify_owner_session_roundtrip():
    tok = sign_owner_session()
    assert tok
    assert verify_owner_session(tok)
    assert not verify_owner_session(tok + "x")
    assert not verify_owner_session("")


def test_index_shows_login_form_without_key(monkeypatch):
    monkeypatch.setenv("OWNER_API_KEY", "solo-owner-secret")
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/")
    assert r.status_code == 200
    assert "Пароль владельца" in r.text
    assert 'action="/login"' in r.text
    assert "api_key=ВАШ_КЛЮЧ" not in r.text


def test_login_sets_cookie_and_opens_dashboard(monkeypatch):
    monkeypatch.setenv("OWNER_API_KEY", "solo-owner-secret")
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/login", data={"password": "solo-owner-secret", "next": "/"}, follow_redirects=False)
    assert r.status_code == 303
    assert COOKIE_NAME in r.cookies
    r2 = client.get("/")
    assert r2.status_code == 200
    assert "Офис MyWave" in r2.text or "игровой" in r2.text.lower() or "задач" in r2.text.lower()


def test_login_rejects_bad_password(monkeypatch):
    monkeypatch.setenv("OWNER_API_KEY", "solo-owner-secret")
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/login", data={"password": "wrong", "next": "/"}, follow_redirects=False)
    assert r.status_code == 401
    assert "Неверный пароль" in r.text


def test_dashboard_pin_alternative(monkeypatch):
    monkeypatch.setenv("OWNER_API_KEY", "long-secret-key")
    monkeypatch.setenv("DASHBOARD_PIN", "1234")
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/login", data={"password": "1234", "next": "/office"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers.get("location") == "/office"
    r2 = client.get("/office")
    assert r2.status_code == 200
