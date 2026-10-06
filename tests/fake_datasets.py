"""공개 데이터와 '같은 파일 형식'의 가짜 데이터 — 다운로드 없이 로더·검증 스크립트를 테스트.

실제 형식 근거
- CogWear muse_eeg.csv: Mind Monitor 열 구성(Delta_TP9…RAW_TP9…HSI_TP10, Battery, Elements, time),
  첫 행은 '/muse/event/connected' 이벤트 행, time 은 묶음 단위로 찍힘
- Muse N400: BlueMuse(5채널: TP9, AF7, AF8, TP10, Right AUX, µV) + 문자열 마커 스트림 .xdf
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from brainfit.xdfwrite import write_xdf

CH = ["TP9", "AF7", "AF8", "TP10"]
SF = 256


def _eeg(rng, n, alpha, beta, theta=4.0):
    t = np.arange(n) / SF
    out = []
    for c in CH:
        a = alpha * (1.0 if c.startswith("TP") else 0.6)
        x = (a * np.sin(2 * np.pi * 10 * t + rng.uniform(0, 6)) * (1 + 0.3 * rng.standard_normal(n)).clip(0)
             + beta * np.sin(2 * np.pi * 20 * t + rng.uniform(0, 6))
             + theta * np.sin(2 * np.pi * 6 * t + rng.uniform(0, 6))
             + 6 * rng.standard_normal(n)) + 800
        out.append(x)
    return np.array(out)


def write_mind_monitor_csv(path: Path, condition: str, seed: int, sec: float = 60):
    rng = np.random.default_rng(seed)
    n = int(sec * SF)
    alpha, beta = (12.0, 2.5) if condition == "baseline" else (6.0, 5.0)  # Stroop: 알파↓ 베타↑
    x = _eeg(rng, n, alpha, beta)
    bands = [f"{b}_{c}" for b in ("Delta", "Theta", "Alpha", "Beta", "Gamma") for c in CH]
    df = pd.DataFrame(0.5, index=range(n), columns=bands)
    for i, c in enumerate(CH):
        df[f"RAW_{c}"] = x[i]
    df["AUX_RIGHT"], df["AUX_LEFT"] = 800.0, 800.0
    for k in ("Accelerometer_X", "Accelerometer_Y", "Accelerometer_Z", "Gyro_X", "Gyro_Y", "Gyro_Z"):
        df[k] = 0.0
    df["HeadBandOn"] = 1.0
    for c in CH:
        df[f"HSI_{c}"] = 1.0
    df["Battery"], df["Elements"] = 100.0, np.nan
    df["time"] = 1636978092.124 + np.floor(np.arange(n) / 12) * 12 / SF  # 12샘플 묶음 시각
    ev = pd.DataFrame([{c: np.nan for c in df.columns}])
    ev["Elements"], ev["time"] = "/muse/event/connected MuseS-5EF0", 1636978092.081
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([ev, df], ignore_index=True).to_csv(path, index=False)


def make_cogwear_tree(root: Path, n_people: int = 6):
    for pid in range(n_people):
        base = root / "pilot" / str(pid)
        write_mind_monitor_csv(base / "baseline" / "muse_eeg.csv", "baseline", seed=pid * 2)
        write_mind_monitor_csv(base / "cognitive_load" / "muse_eeg.csv", "cognitive_load", seed=pid * 2 + 1)
        pd.DataFrame({"text": ["red"] * 40, "color": ["blue"] * 40,
                      "stroop_color_match": [1, 0] * 20, "table_row": range(40), "pressed_key": 1,
                      "status": [1] * 36 + [2] * 3 + [3],
                      "response_speed": [650, 780] * 20}).to_csv(
            base / "cognitive_load" / "stroop_responses.csv", index=False)


def write_n400_xdf(path: Path, seed: int, effect_uv: float = 4.0, n_per_cond: int = 56):
    """관련/무관 목표 단어 마커 + 무관 조건에서 400 ms 근처 음전위(AF8 최대)."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(["related"] * n_per_cond + ["unrelated"] * n_per_cond)
    t, marks = 5.0, []
    for i, cond in enumerate(order):
        marks.append((t, f"prime_{i}"))
        marks.append((t + 0.8, f"target_{cond}_{i}"))
        t += 3.0
    n = int((t + 3) * SF)
    x = _eeg(rng, n, alpha=6, beta=2) - 800 + 800  # µV
    kt = np.arange(int(0.8 * SF)) / SF
    gain = {"AF7": 0.6, "AF8": 1.0, "TP9": 0.3, "TP10": 0.4}
    for onset, m in marks:
        if "unrelated" in m:
            w = -effect_uv * np.exp(-0.5 * ((kt - 0.40) / 0.08) ** 2)
            i = int(onset * SF)
            for ci, c in enumerate(CH):
                x[ci, i:i + len(w)] += w * gain[c]
    aux = rng.normal(0, 50, (1, n))
    data = np.vstack([x, aux]).T
    ts = 2000.0 + np.arange(n) / SF
    write_xdf(path, data, ts, CH + ["Right AUX"], SF,
              np.array([2000.0 + m[0] for m in marks]), [m[1] for m in marks])
