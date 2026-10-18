from fastapi.testclient import TestClient

from parkpulse import app as appmod


def client(state):
    appmod.state = state
    return TestClient(appmod.app)


def test_core_endpoints(state):
    c = client(state)
    assert c.get("/api/health").json()["ok"]
    zones = c.get("/api/zones").json()
    assert len(zones) == 6 and all(z["free"] >= 0 for z in zones)
    assert c.get("/api/zones/nope").status_code == 404
    assert len(c.get("/api/nearest", params={"lat": 32.72, "lon": 74.86}).json()) <= 3
    assert "hotspots" in c.get("/api/analytics").json()
    assert c.get("/api/vision/demo.png").headers["content-type"] == "image/png"


def test_whatsapp_webhook(state):
    c = client(state)
    v = c.get("/api/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "parkpulse-dev", "hub.challenge": "42"})
    assert v.text == "42"
    body = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "919999999999", "type": "text", "text": {"body": "parking near gandhi nagar"}},
        {"from": "919999999999", "type": "text", "text": {"body": "1"}},
    ]}}]}]}
    replies = c.post("/api/webhook/whatsapp", json=body).json()["replies"]
    assert [r["intent"] for r in replies] == ["find", "directions"]
