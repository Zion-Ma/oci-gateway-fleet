import socket
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
import app as app_module  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app_module.app)


def test_health_reports_ok_and_version(client, monkeypatch):
    monkeypatch.setattr(app_module, "VERSION", "v2")
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "v2"}


def test_health_default_version_is_v1(client):
    assert client.get("/health").json()["version"] == "v1"


def test_whoami_returns_hostname(client):
    r = client.get("/whoami")
    assert r.status_code == 200
    assert r.json() == {"hostname": socket.gethostname()}


def test_egress_ok_when_site_reachable(client, monkeypatch):
    monkeypatch.setattr(app_module, "fetch_public_site", lambda: None)
    r = client.get("/egress")
    assert r.status_code == 200
    assert r.json() == {"egress": "ok"}


def test_egress_fail_when_site_unreachable(client, monkeypatch):
    def boom():
        raise OSError("network unreachable")

    monkeypatch.setattr(app_module, "fetch_public_site", boom)
    r = client.get("/egress")
    assert r.status_code == 200
    assert r.json()["egress"] == "fail"


def test_notes_saves_via_storage_function(client, monkeypatch):
    saved = []
    monkeypatch.setattr(app_module, "save_note", lambda text: saved.append(text) or "note-1.txt")
    r = client.post("/notes", json={"text": "hello"})
    assert r.status_code == 200
    assert r.json() == {"saved": "note-1.txt"}
    assert saved == ["hello"]


def test_notes_returns_502_when_storage_fails(client, monkeypatch):
    def boom(text):
        raise RuntimeError("service gateway down")

    monkeypatch.setattr(app_module, "save_note", boom)
    r = client.post("/notes", json={"text": "hello"})
    assert r.status_code == 502
