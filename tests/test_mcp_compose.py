from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"
MCP_SERVICES = ("mcp-literature", "mcp-materials", "mcp-research-data")


def test_mcp_services_have_get_healthchecks() -> None:
    doc = yaml.safe_load(COMPOSE.read_text())
    services = doc["services"]
    assert doc["name"] == "axiom-research"
    for name in MCP_SERVICES:
        service = services[name]
        assert service["command"][0].startswith("axiom-mcp-")
        health = service["healthcheck"]["test"]
        joined = " ".join(health)
        assert "8080/health" in joined
        assert "urllib.request" in joined or "urlopen" in joined
        assert service["build"]["dockerfile"] == "mcp/Dockerfile"
