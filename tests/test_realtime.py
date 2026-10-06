"""실시간 엔진·적응형 선택·라이브 API 테스트 (시뮬레이터를 빨리 감기로 사용)."""
import time

import numpy as np
from fastapi.testclient import TestClient

from brainfit.realtime import adaptive
from brainfit.realtime.engine import RealtimeEngine
from brainfit.realtime.sources import ReplaySource, SimSource


def _run(eng, clock, sec, dt=0.25):
    end = clock[0] + sec
    while clock[0] < end:
        clock[0] += dt
        eng.pump(clock[0])


def _baseline(eng, src, clock):
    eng.mark("rest_eo_start")
    src.set_state("rest_eo")
    _run(eng, clock, 40)
    eng.mark("rest_eo_end")
    eng.mark("rest_ec_start")
    src.set_state("rest_ec")
    _run(eng, clock, 40)
    eng.mark("rest_ec_end")
    src.set_state("rest_eo")


def _activity(eng, src, clock, task, block, response):
    eng.mark("block_start", task=task, block=block)
    src.set_state("focus", response)
    for i in range(20):
        _run(eng, clock, 1.5)
        eng.mark("trial", task=task, block=block, idx=i, target=1, resp=1, correct=1, rt=0.4)
    eng.mark("block_end", task=task, block=block)
    src.set_state("rest_eo")
    _run(eng, clock, 5)
    return eng.st.activity_results[-1]


def test_sources_shapes():
    s = SimSource(seed=0)
    assert s.pull(1.0).shape == (4, 256) and s.pull(1.0).shape == (4, 0)
    r = ReplaySource(np.zeros((4, 100)), 100.0, loop=True)
    assert r.pull(2.5).shape == (4, 250)   # 반복 재생


def test_engine_baseline_and_type():
    src, clock = SimSource(seed=2), [0.0]
    eng = RealtimeEngine(src)
    _run(eng, clock, 5)
    _baseline(eng, src, clock)
    b = eng.st.baseline
    assert b["alpha_reactivity"] > 1.5 and abs(b["iaf_peak"] - 10) < 1
    assert eng.st.brain_type["id"] in {"relaxed", "alert", "low_arousal", "balanced"}
    snap = eng.snapshot()
    assert snap["baseline_ready"] and set(snap["head"]) == {"TP9", "AF7", "AF8", "TP10"}
    assert len(eng.waveform()["data"]) == 4


def test_activity_response_and_adaptive_choice():
    src, clock = SimSource(seed=3), [0.0]
    eng = RealtimeEngine(src)
    _run(eng, clock, 5)
    _baseline(eng, src, clock)
    r1 = _activity(eng, src, clock, "gonogo", 1, response=1.0)
    r2 = _activity(eng, src, clock, "word_memory", 2, response=0.0)
    assert r1["responsive"] is True and r1["z"]["engagement"] > 0.5
    assert r2["responsive"] is False and r2["feedback"]
    nxt = adaptive.choose_next([r1, r2], n_total=4, seed=0)
    assert nxt["mode"] == "compensate" and "workload" in adaptive.ACTIVITIES[nxt["activity"]]["targets"]
    r3 = _activity(eng, src, clock, nxt["task"], 3, response=1.0)
    nxt2 = adaptive.choose_next([r1, r2, r3], n_total=4, seed=0)
    assert nxt2["mode"] == "explore"         # 보완에 성공하면 다시 탐색


def test_choose_next_rules():
    assert adaptive.choose_next([], 3, quality_ok=False, seed=1)["mode"] == "hold"
    first = adaptive.choose_next([], 3, {"start_with": ["pvt"]}, seed=1)
    assert first["mode"] == "explore" and first["index"] == 1
    assert adaptive.josa("암산", "으로", "로") == "으로" and adaptive.josa("Go", "으로", "로") == "로"


def test_live_api_flow():
    from server.main import app

    c = TestClient(app)
    r = c.post("/api/live/start", json={"source": "sim", "time_scale": 40, "n_activities": 2}).json()
    assert r["source"] == "sim"
    c.post("/api/live/phase", json={"phase": "signal_check"})
    c.post("/api/live/mark", json={"event": "rest_eo_start"})
    time.sleep(1.0)
    c.post("/api/live/mark", json={"event": "rest_eo_end"})
    c.post("/api/live/mark", json={"event": "rest_ec_start"})
    time.sleep(1.0)
    ec = c.post("/api/live/mark", json={"event": "rest_ec_end"}).json()
    assert ec["brain_type"]["name"]
    for b in (1, 2):
        nx = c.get("/api/live/next").json()
        c.post("/api/live/mark", json={"event": "block_start", "attrs": {"task": nx["task"], "block": b}})
        for i in range(5):
            c.post("/api/live/trial", json={"task": nx["task"], "block": b, "idx": i, "target": 1,
                                            "resp": 1, "correct": 1, "rt": 0.4})
            time.sleep(0.15)
        end = c.post("/api/live/mark", json={"event": "block_end", "attrs": {"task": nx["task"], "block": b}}).json()
        assert "activity_result" in end
    assert c.get("/api/live/next").json()["activity"] is None
    with c.websocket_connect("/ws/live") as ws:
        m = ws.receive_json()
        assert m["type"] == "tick" and "snapshot" in m and len(m["wave"]["data"]) == 4
    res = c.post("/api/live/finish").json()
    assert res["overall"]["message"] and len(res["activities"]) == 2
