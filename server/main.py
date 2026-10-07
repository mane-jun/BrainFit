"""[예비] 앱 연동용 API 서버 뼈대 (FastAPI).

앱(웹/모바일/Unity 등) 형태가 정해지기 전까지의 '계약'만 잡아 둔다.
  uvicorn server.main:app --reload

엔드포인트
  GET  /health
  POST /sessions/analyze        {"xdf_path": "...", "user": "..."} → summary JSON
  GET  /users/{user}/history    개인 기준선 이력
  GET  /reports/{name}/{file}   그림 PNG
  라이브 데모: server/live.py (/api/live/*, /ws/live) — docs/LIVE_DEMO.md
  정식 화면: http://localhost:8000/  (`web/dist` 빌드 후)
  디버그 화면: http://localhost:8000/static/debug.html
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))
from brainfit.io import load_xdf  # noqa: E402
from brainfit.report import analyze, save_report  # noqa: E402
from brainfit.synth import synthetic_session  # noqa: E402
from server.live import router as live_router  # noqa: E402

app = FastAPI(title="BrainFit API", version="0.2.0")
OUT, USERS = ROOT / "outputs", ROOT / "data" / "users"
app.include_router(live_router)
(OUT / "live").mkdir(parents=True, exist_ok=True)
app.mount("/live-files", StaticFiles(directory=OUT / "live"), name="live-files")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
WEB_DIST = ROOT / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="web-assets")


@app.get("/")
def root():
    return FileResponse(WEB_DIST / "index.html") if WEB_DIST.is_dir() else RedirectResponse("/static/debug.html")


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


