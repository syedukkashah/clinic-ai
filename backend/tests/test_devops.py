from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import httpx
import redis


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker-compose", "-f", str(ROOT / "docker-compose.dev.yml")]


def _run_compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*COMPOSE, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )


def test_all_services_start_cleanly():
    up = _run_compose("up", "-d")
    assert up.returncode == 0, up.stderr or up.stdout
    time.sleep(30)

    ps = _run_compose("ps", "--format", "json")
    assert ps.returncode == 0, ps.stderr or ps.stdout
    rows = [json.loads(line) for line in ps.stdout.splitlines() if line.strip()]
    assert rows, "docker-compose ps returned no services"
    bad = [row for row in rows if row.get("State") in {"exited", "restarting"} or row.get("ExitCode") not in (None, 0, "0")]
    assert bad == []


def test_api_service_health():
    response = httpx.get("http://localhost:8000/api/health", timeout=5)
    assert response.status_code == 200
    assert "status" in response.json()


def test_ml_service_health():
    response = httpx.get("http://localhost:8001/health", timeout=5)
    assert response.status_code == 200


def test_prometheus_scraping():
    response = httpx.get("http://localhost:9090/api/v1/query", params={"query": "up"}, timeout=5)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    results = data["data"]["result"]
    assert any("mediflow" in json.dumps(item).lower() and item["value"][1] == "1" for item in results)


def test_mlflow_accessible():
    response = httpx.post(
        "http://localhost:5000/api/2.0/mlflow/experiments/search",
        json={"max_results": 1000},
        timeout=5,
    )
    assert response.status_code == 200
    assert "experiments" in response.json()


def test_redis_accessible():
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    assert client.ping() is True


def test_postgres_migrations_applied():
    expected = {"appointments", "doctors", "slots", "patients", "ops_alerts", "notifications", "ml_predictions"}
    query = "select table_name from information_schema.tables where table_schema='public';"
    result = _run_compose("exec", "-T", "postgres", "psql", "-U", "mediflow", "-d", "mediflow", "-At", "-c", query)
    assert result.returncode == 0, result.stderr or result.stdout
    actual = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    assert expected <= actual


def test_environment_variables_loaded():
    response = httpx.get("http://localhost:8000/api/health", timeout=5)
    assert response.status_code == 200
    compose_text = (ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8")
    for env_name in ("DATABASE_URL", "REDIS_URL"):
        assert env_name in compose_text


def test_docker_compose_no_hardcoded_secrets():
    prod = ROOT / "docker-compose.prod.yml"
    content = prod.read_text(encoding="utf-8") if prod.exists() else ""
    assert not re.search(r"AIza[0-9A-Za-z_-]{20,}", content)
    assert not re.search(r"gsk_[0-9A-Za-z_-]{20,}", content)
    secretish_lines = [
        line for line in content.splitlines()
        if any(key in line for key in ("GEMINI", "GROQ", "TOGETHER", "OPENROUTER", "SECRET", "PASSWORD"))
    ]
    assert all("${" in line or ":-" in line for line in secretish_lines)
