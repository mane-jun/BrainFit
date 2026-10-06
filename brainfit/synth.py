"""기기 없이 개발하기 위한 '가짜 Muse 세션' 생성기 (BrainFit Cognitive Battery 구조).

진짜 뇌파가 아니다. 목적은
  1) 팀원 누구나 기기 없이 전체 파이프라인을 돌려 보고,
  2) 테스트에서 '눈 감으면 알파↑', '난이도↑ → 부하↑', '시간 경과 → 피로↑',
     'Oddball 타깃 → P300' 같은 알려진 현상을 코드가 제대로 잡는지 검증하는 것.
"""
from __future__ import annotations

import random

import numpy as np
from scipy.signal import butter, sosfiltfilt

from .config import BATTERY_MODES, MUSE_EEG_CHANNELS, MUSE_SFREQ
from .io import Session, events_from_markers, format_marker, make_raw
from .sequences import gonogo_sequence, oddball_sequence

# 상태별 (alpha, theta, beta) 진폭(µV) — '경향'만 흉내 낸 값
STATE = {"rest_eo": (7.0, 4.0, 2.6), "rest_ec": (16.0, 4.0, 2.5), "gonogo": (5.0, 4.5, 3.4),
         "oddball": (5.5, 4.3, 3.2), "pvt": (6.0, 4.2, 3.0), "idle": (6.5, 4.0, 2.5)}
# 과제별 가상 수행 (적중률, 오경보율, 평균 RT)
BEHAV = {"gonogo": (0.97, 0.18, 0.38), "oddball": (0.95, 0.02, 0.45), "pvt": (0.97, 0.0, 0.32)}


def _band_noise(rng, n, sf, lo, hi):
    sos = butter(4, [lo, hi], btype="band", fs=sf, output="sos")
    x = sosfiltfilt(sos, rng.standard_normal(n))
    return x / (x.std() + 1e-12)


def _pink(rng, n):
    f = np.fft.rfftfreq(n)
    spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0
    x = np.fft.irfft(spec, n)
    return x / x.std()


def build_protocol(mode: str = "standard", seed: int = 0, fatigue: float = 1.0):
    """BATTERY_MODES 와 같은 순서·타이밍의 마커 목록 + 가상 행동 반응.
    반환: marks [(onset_s, marker)], blocks [(start, end, task, n)], p300 [(onset, target)], total_sec"""
    m = BATTERY_MODES[mode]
    rng = random.Random(seed)
    st = {"t": 2.0, "b": 1, "task_t0": None}
    marks = [(0.5, f"session_start|user=synthetic|protocol=battery-{mode}-v1")]
    blocks, p300 = [], []

    def rest(name):
        t = st["t"]
        marks.extend([(t, f"{name}_start"), (t + m["rest_sec"], f"{name}_end")])
        blocks.append((t, t + m["rest_sec"], name, None))
        st["t"] += m["rest_sec"] + 5

    def trial(task, i, target, window, lvl=None, pos=-1):
        t = st["t"]
        tot = max(0.0, (t - (st["task_t0"] or t)) / 600.0) * fatigue
        if task.startswith("nback"):
            ph, pf, mu = 0.97 - 0.12 * max(lvl - 1, 0), 0.02 + 0.05 * max(lvl - 1, 0), 0.55 + 0.12 * lvl
        else:
            ph, pf, mu = BEHAV[task]
        ph, pf = max(0.3, ph - 0.08 * tot), min(0.6, pf + 0.03 * tot)
        resp = int(rng.random() < (ph if target else pf))
        rt = round(max(0.16, rng.gauss(mu + 0.05 * tot, 0.08)), 3) if resp else -1
        marks.append((t, format_marker("stim", task=task, block=st["b"], idx=i, target=target)))
        marks.append((t + window, format_marker("trial", task=task, block=st["b"], idx=i, pos=pos,
                                                target=target, resp=resp,
                                                correct=int(resp == target), rt=rt)))

    def block(task, body, lvl=None):
        s = st["t"]
        marks.append((s, format_marker("block_start", task=task, block=st["b"])))
        body()
        marks.append((st["t"], format_marker("block_end", task=task, block=st["b"])))
        blocks.append((s, st["t"], task, lvl))
        st["b"] += 1
        st["t"] += m["between"]

    rest("rest_eo")
    rest("rest_ec")
    st["task_t0"] = st["t"]

    if m["pvt"]:
        def pvt_body():
            end, i = st["t"] + m["pvt"]["sec"], 0
            while st["t"] < end:
                st["t"] += rng.uniform(*m["pvt"]["isi"])
                trial("pvt", i, 1, 0.5)
                st["t"] += 0.5
                i += 1
        block("pvt", pvt_body)

    g = m["gonogo"]

    def gng_body():
        for i, go in enumerate(gonogo_sequence(g["n"], g["p_nogo"], rng)):
            trial("gonogo", i, go, g["window"])
            st["t"] += g["window"] + rng.uniform(*g["iti"])
    block("gonogo", gng_body)

    nb = m["nback"]
    for lvl in nb["levels"]:
        def nb_body(lvl=lvl):
            n_tr = nb["trials"] + lvl
            pos = [rng.randrange(9) for _ in range(n_tr)]
            for i in range(n_tr):
                if lvl == 0:
                    pos[i] = 4 if rng.random() < 0.3 else rng.choice([0, 1, 2, 3, 5, 6, 7, 8])
                elif i >= lvl and rng.random() < 0.3:
                    pos[i] = pos[i - lvl]
                tgt = int(pos[i] == 4) if lvl == 0 else int(i >= lvl and pos[i] == pos[i - lvl])
                trial(f"nback{lvl}", i, tgt, nb["trial"] - 0.05, lvl, pos[i])
                st["t"] += nb["trial"]
        block(f"nback{lvl}", nb_body, lvl)

    o = m["oddball"]

    def odd_body():
        for i, tgt in enumerate(oddball_sequence(o["n"], o["p_target"], rng)):
            p300.append((st["t"], tgt))
            trial("oddball", i, tgt, o["stim"] + 0.9)
            st["t"] += o["stim"] + rng.uniform(*o["iti"])
    block("oddball", odd_body)

    if m["post_rest"]:
        rest("rest_ec_post")
    marks.append((st["t"], "session_end"))
    return sorted(marks), blocks, p300, st["t"] + 1


def synthetic_session(seed: int = 0, fatigue: float = 1.0, iaf: float = 10.0,
                      blink_rate: float = 0.12, mode: str = "standard",
                      p300_uv: float = 8.0) -> Session:
    rng = np.random.default_rng(seed)
    sf = MUSE_SFREQ
    marks, blocks, p300, total = build_protocol(mode, seed, fatigue)
    n = int(total * sf)
    tt = np.arange(n) / sf

    a_env, t_env, b_env = (np.full(n, v) for v in STATE["idle"])
    task_mask, eyes_closed = np.zeros(n, bool), np.zeros(n, bool)
    first_task = None
    for s, e, task, lvl in blocks:
        i0, i1 = int(s * sf), int(e * sf)
        if task.startswith("nback"):
            a, th, be = 6.0 - 0.9 * lvl, 4.0 + 0.9 * lvl, 3.0 + 0.35 * lvl
        elif task == "rest_ec_post":
            a, th, be = 16.0 + 3 * fatigue, 4.0 + 1.5 * fatigue, 2.5
        else:
            a, th, be = STATE[task]
        a_env[i0:i1], t_env[i0:i1], b_env[i0:i1] = a, th, be
        if task.startswith("rest_ec"):
            eyes_closed[i0:i1] = True
        elif not task.startswith("rest"):
            task_mask[i0:i1] = True
            first_task = i0 if first_task is None else first_task

    if first_task is not None:  # 피로: 과제 누적 시간에 따라 알파·세타↑, 베타↓
        tot = np.clip((tt - first_task / sf) / 600.0, 0, None) * fatigue
        a_env[task_mask] += 2.0 * tot[task_mask]
        t_env[task_mask] += 1.5 * tot[task_mask]
        b_env[task_mask] -= 0.6 * tot[task_mask]
    k = np.ones(int(sf)) / sf
    a_env, t_env, b_env = (np.convolve(e, k, "same") for e in (a_env, t_env, b_env))

    data = np.zeros((4, n))
    for ci, ch in enumerate(MUSE_EEG_CHANNELS):
        frontal = ch.startswith("AF")
        x = 8.0 * _pink(rng, n)
        x += (0.6 if frontal else 1.0) * a_env * _band_noise(rng, n, sf, iaf - 1.2, iaf + 1.2)
        x += (1.3 if frontal else 0.8) * t_env * _band_noise(rng, n, sf, 4.5, 7.5)
        x += b_env * _band_noise(rng, n, sf, 14, 26)
        x += 1.0 * np.sin(2 * np.pi * 60 * tt)
        data[ci] = x + 800.0

    # P300: 타깃 자극 후 약 350 ms 양전위 (Muse 에서는 TP 채널에서 주로 관찰, Krigolson 2017)
    kern_t = np.arange(int(0.8 * sf)) / sf
    for onset, tgt in p300:
        lat = 0.35 + rng.normal(0, 0.03)
        wave = np.exp(-0.5 * ((kern_t - lat) / 0.07) ** 2) * (p300_uv if tgt else 1.0)
        i = int(onset * sf)
        stop = min(i + len(wave), n)
        for ci, ch in enumerate(MUSE_EEG_CHANNELS):
            data[ci, i:stop] += wave[: stop - i] * (0.4 if ch.startswith("AF") else 1.0)

    for bt in rng.uniform(0, total - 1, int(total * blink_rate)):  # 눈 깜빡임 (이마 채널)
        i = int(bt * sf)
        if eyes_closed[i]:
            continue
        w = np.hanning(int(0.3 * sf)) * rng.uniform(150, 300)
        data[1:3, i:i + len(w)] += w[: n - i]

    raw = make_raw(data * 1e-6, sf, MUSE_EEG_CHANNELS)
    events = events_from_markers(np.array([m[0] for m in marks]), [m[1] for m in marks])
    return Session(raw=raw, events=events, meta={"source": "synthetic", "mode": mode, "seed": seed,
                                                 "true_iaf": iaf, "fatigue": fatigue})
