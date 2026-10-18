"""FastAPI service: REST API, WhatsApp webhook, vision endpoints and the web UI.

Run:  uvicorn parkpulse.app:app --reload
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .bot import handle_message
from .state import LiveState
from .vision.privacy import anonymise
from .vision.slot_detector import SlotDetector
from .vision.synthetic import make_lot
from .zones import ZONES_BY_ID

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
TICK_SECONDS = float(os.getenv("PARKPULSE_TICK_SECONDS", "15"))
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "parkpulse-dev")

state: LiveState | None = None


def get_state() -> LiveState:
    global state
    if state is None:
        state = LiveState()
    return state


async def _ticker():
    while True:
        await asyncio.sleep(TICK_SECONDS)
        get_state().tick(datetime.now())


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_state()
    task = asyncio.create_task(_ticker())
    yield
    task.cancel()


app = FastAPI(title="ParkPulse Jammu", version="0.1.0", lifespan=lifespan,
              description="Live parking and congestion intelligence (prototype on simulated data).")


# ---------------------------------------------------------------------- citizen + admin API
@app.get("/api/health")
def health():
    return {"ok": True, "data": "simulated", "time": datetime.now().isoformat(timespec="seconds")}


@app.get("/api/kpis")
def kpis():
    return get_state().kpis()


@app.get("/api/zones")
def zones():
    return get_state().zones()


@app.get("/api/zones/{zone_id}")
def zone(zone_id: str):
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(404, "unknown zone")
    return get_state().zone_view(zone_id)


@app.get("/api/nearest")
def nearest(lat: float, lon: float, limit: int = Query(3, ge=1, le=10)):
    return get_state().nearest(lat, lon, limit=limit)


@app.get("/api/forecast/{zone_id}")
def forecast(zone_id: str, hours: int = Query(6, ge=1, le=24)):
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(404, "unknown zone")
    return get_state().forecast(zone_id, hours)


@app.get("/api/alerts")
def alerts():
    return get_state().alerts()


@app.get("/api/analytics")
def analytics():
    return get_state().analytics()


# ---------------------------------------------------------------------- chatbot
SESSIONS: dict[str, dict] = {}


class ChatIn(BaseModel):
    session_id: str = "web"
    text: str = ""
    lat: float | None = None
    lon: float | None = None
    lang: str | None = None


@app.post("/api/chat")
def chat(msg: ChatIn):
    loc = (msg.lat, msg.lon) if msg.lat is not None and msg.lon is not None else None
    r = handle_message(get_state(), msg.text, loc, msg.lang, SESSIONS.setdefault(msg.session_id, {}))
    return {"reply": r.text, "lang": r.lang, "intent": r.intent, "data": r.data}


@app.get("/api/webhook/whatsapp")
def whatsapp_verify(request: Request):
    """Meta WhatsApp Cloud API webhook verification handshake."""
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "verification failed")


@app.post("/api/webhook/whatsapp")
async def whatsapp_inbound(request: Request):
    """Parse WhatsApp Cloud API messages and return the replies that would be sent.

    Sending is left to a thin client (graph.facebook.com /messages) once a business
    number and access token are provisioned; the prototype returns replies in the response.
    """
    body = await request.json()
    replies = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):
                sess = SESSIONS.setdefault(f"wa:{m.get('from')}", {})
                if m.get("type") == "location":
                    loc = m["location"]
                    r = handle_message(get_state(), location=(loc["latitude"], loc["longitude"]), session=sess)
                else:
                    r = handle_message(get_state(), m.get("text", {}).get("body", ""), session=sess)
                replies.append({"to": m.get("from"), "text": r.text, "intent": r.intent})
    return JSONResponse({"replies": replies})


# ---------------------------------------------------------------------- vision
@app.get("/api/vision/demo.png")
def vision_demo(occupancy: float = Query(0.6, ge=0, le=1), seed: int = 4, anonymised: bool = True):
    lot = make_lot(occupancy=occupancy, seed=seed)
    frame = anonymise(lot.image)[0] if anonymised else lot.image
    det = SlotDetector(lot.slots)
    out = det.annotate(frame, det.detect(lot.image), title="Demo camera: Bahu Plaza (synthetic)")
    ok, buf = cv2.imencode(".png", out)
    return Response(buf.tobytes(), media_type="image/png")


@app.post("/api/vision/frame")
async def vision_frame(file: UploadFile = File(...), slots_json: str | None = None):
    """Run slot detection on an uploaded frame using the synthetic demo layout or a given slot file."""
    data = np.frombuffer(await file.read(), np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "could not decode image")
    if slots_json:
        import json
        slots = json.loads(slots_json)
    else:
        slots = make_lot(width=frame.shape[1], height=frame.shape[0]).slots
    det = SlotDetector(slots)
    states = det.detect(frame)
    return {"summary": det.summarize(states), "slots": [s.__dict__ for s in states]}


# ---------------------------------------------------------------------- web UI
@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/admin")
def admin():
    return FileResponse(WEB_DIR / "admin.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
