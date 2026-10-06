"""CogWear (PhysioNet) — Muse S + Mind Monitor CSV 로더.

폴더 구조
  pilot/<id>/{baseline,cognitive_load}/muse_eeg.csv              (id 0–10)
  survey_gamification/<id>/{pre,post}/{baseline,cognitive_load,survey}/muse_eeg.csv  (id 11–24, 19 없음)
  cognitive_load/stroop_responses.csv: text, color, stroop_color_match(1=일치,0=불일치),
                                       status(1 정답, 2 오답, 3 시간초과), response_speed(ms)

Mind Monitor CSV 주의점
  - 첫 줄(들)은 '/muse/event/...' 이벤트 행 → RAW 값이 비어 있어 제거
  - time 열은 수신 시각이라 묶음 단위로 찍힘(1 ms 안에 여러 행) → 샘플 간격으로 쓰면 안 됨.
    Muse 사양(256 Hz)대로 '행 순서 = 샘플 순서'로 보고, 전체 길이로 실효 샘플링률만 점검
  - RAW_* 는 µV (DC 오프셋 약 800 µV 포함) → V 로 변환
  - HSI_* 착용 상태: 1 좋음 / 2 보통 / 4 나쁨
  - 과제 순서가 'Stroop → 휴식' 이라 휴식 구간에 직전 과제의 여운이 섞일 수 있음(해석 시 주의)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..config import MUSE_EEG_CHANNELS, MUSE_SFREQ
from ..io import Session, events_from_markers, format_marker, make_raw

RAW_COLS = [f"RAW_{c}" for c in MUSE_EEG_CHANNELS]
HSI_COLS = [f"HSI_{c}" for c in MUSE_EEG_CHANNELS]


def find_recordings(root: str | Path) -> pd.DataFrame:
    """root 아래 muse_eeg.csv 를 모두 찾아 (participant, study, session, condition, path) 표로."""
    rows = []
    for p in sorted(Path(root).rglob("muse_eeg.csv")):
        parts = p.relative_to(root).parts
        if "pilot" in parts:
            i = parts.index("pilot")
            pid, sess, cond = parts[i + 1], "pilot", parts[i + 2]
            study = "pilot"
        elif "survey_gamification" in parts:
            i = parts.index("survey_gamification")
            pid, sess, cond = parts[i + 1], parts[i + 2], parts[i + 3]
            study = "survey_gamification"
        else:
            continue
        rows.append({"participant": f"p{int(pid):02d}" if pid.isdigit() else pid, "study": study,
                     "session": sess, "condition": cond, "path": str(p)})
    return pd.DataFrame(rows, columns=["participant", "study", "session", "condition", "path"])


def read_mind_monitor_csv(path: str | Path) -> tuple[np.ndarray, dict]:
    """반환: data_uv (4, n), info(dict: n_rows, duration_s, effective_srate, hsi_good_ratio...)"""
    usecols = lambda c: c in RAW_COLS + HSI_COLS + ["time", "HeadBandOn"]  # noqa: E731
    df = pd.read_csv(path, usecols=usecols, low_memory=False)
    df = df.dropna(subset=RAW_COLS)  # 이벤트 행 제거
    x = df[RAW_COLS].to_numpy(float).T
    t = pd.to_numeric(df["time"], errors="coerce").to_numpy()
    dur = float(np.nanmax(t) - np.nanmin(t)) if len(t) > 1 else 0.0
    info = {"n_rows": int(x.shape[1]), "duration_s": round(dur, 1),
            "effective_srate": round(x.shape[1] / dur, 1) if dur > 0 else None}
    for c, hc in zip(MUSE_EEG_CHANNELS, HSI_COLS, strict=True):
        if hc in df:
            info[f"hsi_good_{c}"] = round(float((df[hc] == 1).mean()), 3)
    if "HeadBandOn" in df:
        info["headband_on_ratio"] = round(float((df["HeadBandOn"] == 1).mean()), 3)
    # 같은 값이 길게 반복되면(수신 끊김 시 값 유지) 평탄 구간으로 표시
    same = np.all(np.diff(x, axis=1) == 0, axis=0)
    info["repeated_sample_ratio"] = round(float(same.mean()), 4) if same.size else 0.0
    return x, info


def load_recording(path: str | Path, condition: str, trim_sec: float = 5.0) -> Session:
    """CSV 1개 → Session. 전체 구간을 하나의 구간으로 표시한다.
    baseline → 'rest_eo' (휴식, 눈 뜸 가정) / cognitive_load → block(task=stroop)"""
    x_uv, info = read_mind_monitor_csv(path)
    sf = MUSE_SFREQ
    raw = make_raw(x_uv * 1e-6, sf, MUSE_EEG_CHANNELS)
    end = x_uv.shape[1] / sf
    s, e = trim_sec, max(trim_sec + 1, end - trim_sec)  # 시작/끝 착용·전환 잡음 제외
    if condition == "baseline":
        marks = [(s, "rest_eo_start"), (e, "rest_eo_end")]
    else:
        marks = [(s, format_marker("block_start", task="stroop", block=1)),
                 (e, format_marker("block_end", task="stroop", block=1))]
    ev = events_from_markers(np.array([m[0] for m in marks]), [m[1] for m in marks])
    sr = info.get("effective_srate")
    if sr and not (200 <= sr <= 320):
        info["warning"] = f"실효 샘플링률 {sr} Hz — 256 Hz 와 크게 다름(끊김/기록 설정 확인)"
    return Session(raw=raw, events=ev, meta={"source": str(path), "dataset": "cogwear",
                                             "condition": condition, **info})


def load_stroop(path: str | Path) -> dict:
    """stroop_responses.csv → 정확도, RT, Stroop 간섭효과(불일치 RT − 일치 RT)."""
    d = pd.read_csv(path)
    rt = pd.to_numeric(d["response_speed"], errors="coerce")
    ok = d["status"] == 1
    out = {"n_trials": int(len(d)), "accuracy": round(float(ok.mean()), 3),
           "timeout_rate": round(float((d["status"] == 3).mean()), 3),
           "rt_median_ms": round(float(rt[ok].median()), 1) if ok.any() else None}
    if "stroop_color_match" in d:
        con = rt[ok & (d["stroop_color_match"] == 1)].median()
        inc = rt[ok & (d["stroop_color_match"] == 0)].median()
        if pd.notna(con) and pd.notna(inc):
            out["interference_ms"] = round(float(inc - con), 1)
    return out
