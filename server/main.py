"""[예비] 앱 연동용 API 서버 뼈대 (FastAPI).

앱(웹/모바일/Unity 등) 형태가 정해지기 전까지의 '계약'만 잡아 둔다.
  uvicorn server.main:app --reload

엔드포인트
  GET  /health
  POST /sessions/analyze        {"xdf_path": "...", "user": "..."} → summary JSON
  GET  /users/{user}/history    개인 기준선 이력
  GET  /reports/{name}/{file}   그림 PNG
  WS   /live                    (TODO) 실시간 집중 지표 스트림
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brainfit.io import load_xdf  # noqa: E402
from brainfit.report import analyze, save_report  # noqa: E402
from brainfit.synth import synthetic_session  # noqa: E402

app = FastAPI(title="BrainFit API", version="0.1.0")
OUT, USERS = ROOT / "outputs", ROOT / "data" / "users"


class AnalyzeReq(BaseModel):
    xdf_path: str | None = None
    user: str = "anon"
    synthetic: bool = False


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/sessions/analyze")
def analyze_session(req: AnalyzeReq):
    if req.synthetic:
        sess = synthetic_session()
    elif req.xdf_path and Path(req.xdf_path).exists():
        sess = load_xdf(req.xdf_path)
    else:
        raise HTTPException(400, "xdf_path 가 없거나 파일이 존재하지 않습니다.")
    name = f"{datetime.now():%Y%m%d_%H%M%S}_{req.user}"
    summary = save_report(analyze(sess), OUT / name, user=req.user, store_root=USERS)
    summary["report"] = name
    return summary


@app.get("/users/{user}/history")
def history(user: str):
    p = USERS / user / "history.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


@app.get("/reports/{name}/{file}")
def report_file(name: str, file: str):
    p = (OUT / name / file).resolve()
    if OUT.resolve() not in p.parents or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.websocket("/live")
async def live(ws: WebSocket):
    """TODO(3번 확장): pylsl inlet → 0.5초마다 {"t":..,"engagement_z":..} 전송.
    scripts/live_monitor.py 의 계산 로직을 brainfit/realtime.py 로 옮겨 재사용할 것."""
    await ws.accept()
    await ws.send_json({"todo": "not implemented"})
    await ws.close()
