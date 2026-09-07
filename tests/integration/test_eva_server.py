import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

import eva_server


@pytest.fixture
def eva_http():
    server = ThreadingHTTPServer(("127.0.0.1", 0), eva_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"{host}:{port}"
    server.shutdown()
    thread.join(timeout=5)


def _get(addr: str, path: str):
    conn = HTTPConnection(addr, timeout=30)
    conn.request("GET", path)
    res = conn.getresponse()
    body = res.read()
    conn.close()
    return res.status, json.loads(body.decode("utf-8"))


def _post(addr: str, path: str, payload: dict):
    raw = json.dumps(payload).encode("utf-8")
    conn = HTTPConnection(addr, timeout=30)
    conn.request("POST", path, body=raw, headers={"Content-Type": "application/json"})
    res = conn.getresponse()
    body = res.read()
    conn.close()
    return res.status, json.loads(body.decode("utf-8"))


@pytest.mark.integration
def test_health_ok(eva_http):
    status, data = _get(eva_http, "/api/health")
    assert status == 200
    assert data["ok"] is True
    assert data["agent"] == "Eva"
    assert "summaries" in data


@pytest.mark.integration
def test_documents_payload(eva_http):
    status, data = _get(eva_http, "/api/documents")
    assert status == 200
    assert data["ok"] is True
    assert data["count"] == len(data["documents"])
    assert isinstance(data["bands"], dict)


@pytest.mark.integration
def test_changes_and_pipeline(eva_http):
    st, changes = _get(eva_http, "/api/changes")
    assert st == 200
    assert "changes" in changes
    st, pipe = _get(eva_http, "/api/pipeline")
    assert st == 200
    assert "summaries" in pipe
    assert "scored" in pipe


@pytest.mark.integration
def test_ask_requires_question(eva_http):
    status, data = _post(eva_http, "/api/eva/ask", {})
    assert status == 400
    assert "error" in data


@pytest.mark.integration
def test_ask_meta_question(eva_http):
    status, data = _post(eva_http, "/api/eva/ask", {"question": "hello", "deep": False})
    assert status == 200
    assert data.get("answer") or data.get("method")


@pytest.mark.integration
def test_unknown_route(eva_http):
    status, data = _get(eva_http, "/api/nope")
    assert status == 404
    assert data["error"] == "not found"
