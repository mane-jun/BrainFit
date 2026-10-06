"""라이브 데모 API — 웹 화면(web/ 또는 /debug)이 이 API 와 WebSocket 으로 엔진을 조종한다.

REST (모두 JSON)
  POST /api/live/start      {source:"sim"|"lsl"|"replay", replay_path?, user?, n_activities?, time_scale?, record_markers?}
  POST /api/live/phase      {phase:"signal_check"|"done"}
  POST /api/live/mark       {event:"rest_eo_start"|..., attrs:{}}       ← 단계 시작/끝
  POST /api/live/trial      {task, block, idx, target, resp, correct, rt}  ← 활동 화면의 매 시행 결과
  GET  /api/live/next       → 다음 활동 + 선택 이유 (adaptive.choose_next)
  GET  /api/live/activities → 활동 목록
  GET  /api/live/status     → 최신 스냅샷
  POST /api/live/finish     → 최종 리포트(JSON + 그림 URL), outputs/live/<id>/ 저장
WebSocket
  /ws/live  0.5초마다 {"type":"tick", "snapshot":{...}, "wave":{sfreq, ch, data}}
메시지 스키마는 docs/LIVE_DEMO.md 3절.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from brainfit.realtime import adaptive
from brainfit.realtime.engine import RealtimeEngine
from brainfit.realtime.sources import SimSource, make_source
from brainfit.report import analyze, save_report

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "live"
router = APIRouter()

# 시뮬레이터: 활동별 '뇌파 반응 정도'(0~1). 일부를 낮게 둬서 적응형 선택이 시연되도록 함.
SIM_RESPONSE = {"gonogo": 1.0, "nback": 1.0, "oddball": 0.15, "stroop": 0.9, "arithmetic": 1.0,
                "pvt": 0.8, "word_memory": 0.1}


class LiveSession:
    def __init__(self, engine: RealtimeEngine, user: str, n_activities: int, sim_response: dict):
        self.engine, self.user, self.n_activities = engine, user, n_activities
        self.id = f"{datetime.now():%Y%m%d_%H%M%S}_{user}"
        self.sim_response = sim_response
        self.lock = asyncio.Lock()


SESSION: dict[str, LiveSession | None] = {"cur": None}


def cur() -> LiveSession:
    s = SESSION["cur"]
    if s is None:
        raise HTTPException(409, "세션이 없습니다. /api/live/start 를 먼저 호출하세요.")
    return s


def _json(obj):
    return json.loads(json.dumps(obj, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))


class StartReq(BaseModel):
    source: str = "sim"
    replay_path: str | None = None
    user: str = "demo"
    n_activities: int = 4
    time_scale: float = 1.0
    record_markers: bool = False
    seed: int = 0
    sim_response: dict | None = None


@router.post("/api/live/start")
def start(req: StartReq):
    kw = {"seed": req.seed} if req.source == "sim" else {}
    try:
        src = make_source(req.source, req.replay_path, **kw)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e)) from e
    sink = None
    if req.record_markers:  # LabRecorder 로 같은 세션을 .xdf 로 남기고 싶을 때
        import sys
        sys.path.insert(0, str(ROOT / "tasks"))
        from markers import MarkerOutlet

        sink = MarkerOutlet().push
    eng = RealtimeEngine(src, marker_sink=sink)
    if req.time_scale != 1.0:
        base = eng.wall_now
        eng.wall_now = lambda: base() * req.time_scale  # 데모·테스트용 빨리 감기
    SESSION["cur"] = LiveSession(eng, req.user, max(1, min(req.n_activities, 7)),
                                 {**SIM_RESPONSE, **(req.sim_response or {})})
    return {"session_id": SESSION["cur"].id, "source": src.kind, "channels": eng.ch, "sfreq": eng.sf}


class PhaseReq(BaseModel):
    phase: str


@router.post("/api/live/phase")
def phase(req: PhaseReq):
    s = cur()
    s.engine.pump()
    s.engine.set_phase(req.phase)
    return {"phase": req.phase, "t": s.engine.t}


class MarkReq(BaseModel):
    event: str
    attrs: dict = {}


@router.post("/api/live/mark")
def mark(req: MarkReq):
    s = cur()
    eng = s.engine
    eng.pump()  # 마커 시각을 '지금'에 맞추기 위해 먼저 데이터를 받아 둔다
    txt = eng.mark(req.event, **req.attrs)
    if isinstance(eng.src, SimSource):  # 시뮬레이터는 화면 흐름에 맞춰 신호를 바꾼다
        if req.event == "rest_ec_start":
            eng.src.set_state("rest_ec")
        elif req.event == "block_start":
            act = adaptive.activity_of(req.attrs.get("task", ""))
            eng.src.set_state("focus", s.sim_response.get(act, 1.0))
        elif req.event.endswith("_end") or req.event == "rest_eo_start":
            eng.src.set_state("rest_eo")
    out = {"marker": txt, "t": round(eng.t, 2), "phase": eng.st.phase}
    if req.event == "rest_ec_end":
        out["brain_type"] = eng.st.brain_type
        out["baseline"] = {k: v for k, v in eng.st.baseline.items() if k not in ("stats", "ch_stats")}
    if req.event == "block_end" and eng.st.activity_results:
        out["activity_result"] = eng.st.activity_results[-1]
    return _json(out)


class TrialReq(BaseModel):
    task: str
    block: int
    idx: int
    target: int = -1
    resp: int = -1
    correct: int = -1
    rt: float = -1
    extra: dict = {}


@router.post("/api/live/trial")
def trial(req: TrialReq):
    s = cur()
    s.engine.pump()
    s.engine.mark("trial", task=req.task, block=req.block, idx=req.idx, target=req.target,
                  resp=req.resp, correct=req.correct, rt=round(req.rt, 3), **req.extra)
    return {"ok": True}


@router.get("/api/live/activities")
def activities():
    return adaptive.ACTIVITIES


@router.get("/api/live/next")
def next_activity():
    s = cur()
    eng = s.engine
    eng.pump()
    q = eng.snapshot().get("quality_status", "good")
    nxt = adaptive.choose_next(eng.st.activity_results, s.n_activities, eng.st.brain_type,
                               quality_ok=q != "poor", seed=len(eng.st.activity_results) + 7)
    return _json(nxt or {"activity": None, "reason": "계획한 활동을 모두 마쳤어요."})


@router.get("/api/live/status")
def status():
    s = cur()
    s.engine.pump()
    return _json(s.engine.snapshot())


@router.get("/api/live/history")
def history(last_sec: float = 120):
    s = cur()
    s.engine.pump()
    return _json(s.engine.history(last_sec))


@router.post("/api/live/finish")
def finish():
    s = cur()
    eng = s.engine
    eng.pump()
    eng.set_phase("done")
    out_dir = OUT / s.id
    result = {"session_id": s.id, "brain_type": eng.st.brain_type,
              "activities": eng.st.activity_results, "baseline": {
                  k: v for k, v in eng.st.baseline.items() if k not in ("stats", "ch_stats")}}
    try:
        summary = save_report(analyze(eng.to_session()), out_dir, user=s.user,
                              store_root=ROOT / "data" / "users")
        result["report"] = {k: summary.get(k) for k in ("quality", "sustained", "fatigue", "profile",
                                                         "recommendations")}
        result["figures"] = [f"/live-files/{s.id}/{p.name}" for p in sorted(out_dir.glob("*.png"))]
    except Exception as e:  # noqa: BLE001 — 데이터가 짧아도 활동 요약은 돌려준다
        result["report_error"] = str(e)
    result["overall"] = overall_summary(eng.st.activity_results)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "live_result.json").write_text(json.dumps(_json(result), ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    return _json(result)


def overall_summary(results: list[dict]) -> dict:
    judged = [r for r in results if r.get("z")]
    if not judged:
        return {"message": "판단할 수 있는 활동 데이터가 부족해요."}
    best = max(judged, key=lambda r: r["z"]["engagement"])
    worst = min(judged, key=lambda r: r["z"]["engagement"])
    drop = [r for r in judged if (r.get("engagement_slope_per_min") or 0) < -0.5]
    return {"most_focused": best["name"], "least_focused": worst["name"],
            "fast_decline": [r["name"] for r in drop],
            "message": (f"'{best['name']}'에서 가장 몰입했고, '{worst['name']}'에서 몰입이 가장 낮았어요."
                        + (f" '{drop[0]['name']}'에서는 후반으로 갈수록 집중이 떨어졌어요." if drop else ""))}


@router.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            s = SESSION["cur"]
            if s is None:
                await ws.send_json({"type": "idle"})
            else:
                s.engine.pump()
                await ws.send_json(_json({"type": "tick", "snapshot": s.engine.snapshot(),
                                          "wave": s.engine.waveform()}))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
