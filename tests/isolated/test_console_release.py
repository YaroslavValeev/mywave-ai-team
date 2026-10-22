"""Release delta and rollback boundaries; no server access or real credentials."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

path = Path(__file__).resolve().parents[2] / "scripts/server/project_console_release.py"
spec = importlib.util.spec_from_file_location("console_release", path)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_release_changes_only_image_release_identity_and_proxy_trust():
    old = {
        "services": {
            "app": {
                "image": "old",
                "environment": {
                    "WORKSPACE_ACCESS_ENABLED": "true",
                    "WORKSPACE_PRINCIPAL_BINDINGS_JSON": "binding",
                },
                "env_file": ["/private/owner.env"],
                "volumes": ["existing"],
            },
            "molt": {"image": "untouched"},
        }
    }
    new = release.render(old, "127.0.0.1,::1,172.18.0.1", "2026-10-22T00:00:00Z")
    assert new["services"]["app"]["image"] == release.IMAGE
    assert old["services"]["app"]["image"] == "old"
    assert new["services"]["molt"] == old["services"]["molt"]
    app = new["services"]["app"]
    assert app["env_file"] == old["services"]["app"]["env_file"] and app["volumes"] == [
        "existing"
    ]
    assert app["environment"]["WORKSPACE_PRINCIPAL_BINDINGS_JSON"] == "binding"
    assert app["environment"]["APP_COMMIT_SHA"] == release.SOURCE
    assert app["environment"]["APP_ENVIRONMENT"] == "production"
    assert app["environment"]["APP_BUILD_TIMESTAMP"] == "2026-10-22T00:00:00Z"


@pytest.mark.parametrize(
    "trust", ["*", "0.0.0.0/0", "172.18.0.0/16", "", "127.0.0.1,*"]
)
def test_proxy_trust_never_accepts_wildcards_or_network_ranges(trust):
    with pytest.raises((RuntimeError, ValueError)):
        release.render({"services": {"app": {}}}, trust, "timestamp")


def test_failed_acceptance_restores_exact_previous_config_and_waits_for_recovery(
    tmp_path,
):
    path = tmp_path / "candidate.json"
    old = b'{"services":{"app":{"image":"old"}}}'
    path.write_bytes(old)
    ops = Mock()
    ops.COMPOSE = [None, None, path]
    ops.atomic_write.side_effect = lambda p, data: p.write_bytes(data)
    ready = Mock()
    verify = Mock(side_effect=RuntimeError("simulated verification failure"))
    recover = Mock()
    with pytest.raises(RuntimeError, match="previous 009"):
        release.cutover(ops, old, b'{"image":"candidate"}', ready, verify, recover)
    assert path.read_bytes() == old
    assert (
        ops.compose.call_count == 2
        and ready.call_count == 1
        and recover.call_count == 1
    )
    assert all(
        call.args[-1] == "app" and "--no-deps" in call.args and "--pull" in call.args
        for call in ops.compose.call_args_list
    )


def test_failed_recovery_is_distinct_and_not_claimed_success(tmp_path):
    ops = Mock()
    ops.COMPOSE = [None, None, tmp_path / "candidate"]
    with pytest.raises(RuntimeError, match="Release and recovery failed"):
        release.cutover(
            ops,
            b"old",
            b"new",
            Mock(side_effect=RuntimeError()),
            Mock(),
            Mock(side_effect=RuntimeError()),
        )


def test_wrong_owner_gate_stops_before_backup_reads_or_mutations():
    activation, ops = Mock(), Mock()
    with pytest.raises(RuntimeError, match="Owner Gate"):
        release.execute(
            activation,
            ops,
            {"candidate_image": release.IMAGE},
            b"old",
            Path("/not-used"),
            "0" * 64,
        )
    activation.protected.assert_not_called()
    ops.compose.assert_not_called()


def test_plan_hash_binds_code_image_and_configuration():
    original = {
        "operations_sha256": "one",
        "candidate_image": "image",
        "profile_sha256": "profile",
    }
    first = release.plan_hash(original)
    for key in original:
        changed = dict(original)
        changed[key] = "changed"
        assert release.plan_hash(changed) != first


def test_proxy_preflight_rejects_fixed_keys_and_unrelated_hosts():
    config = b"server { listen 443 ssl; server_name owner.example; proxy_set_header X-Forwarded-Proto $scheme; location / { proxy_pass http://127.0.0.1:8088; } }"
    ops = Mock()
    ops.command.return_value = config
    assert release.nginx_gate(ops, "https://owner.example") == "https://owner.example"
    with pytest.raises(RuntimeError, match="TLS vhost"):
        release.nginx_gate(ops, "https://sub.owner.example")
    ops.command.return_value = config.replace(
        b"location /", b"proxy_set_header X-API-Key fixed-key; location /"
    )
    with pytest.raises(RuntimeError, match="dedicated key"):
        release.nginx_gate(ops, "https://owner.example")
    ops.command.return_value = config.replace(
        b"http://127.0.0.1:8088", b"http://other-upstream:8088"
    )
    with pytest.raises(RuntimeError, match="upstream"):
        release.nginx_gate(ops, "https://owner.example")


def test_redirect_does_not_forward_the_credential():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    import urllib.error
    import urllib.request

    visits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            visits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/must-not-receive-key")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.05), daemon=True
    )
    thread.start()
    try:
        client = urllib.request.build_opener(release.NoRedirect())
        request = urllib.request.Request(
            "http://127.0.0.1:" + str(server.server_port) + "/redirect",
            headers={"X-API-Key": "synthetic-test-only"},
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            client.open(request, timeout=5)
        assert error.value.code == 302 and visits == ["/redirect"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
