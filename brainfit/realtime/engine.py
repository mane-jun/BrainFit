"""실시간 엔진: 입력 소스 → (인과) 필터 → 0.5초마다 최근 2초 창 분석 → 스냅샷.

오프라인 파이프라인과 '같은 식'을 쓰도록 features.window_features 를 그대로 호출한다.
(실시간 화면의 숫자와 최종 리포트의 숫자가 다르게 나오는 일을 막기 위함)

흐름(phase): idle → signal_check → rest_eo → rest_ec → (activity ↔ break)* → done
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, tf2sos, welch

from ..artifacts import artifact_mask, clean_segment_count, rising_edges
from ..config import BANDS, FRONTAL, LINE_FREQ, PRE, TEMPORO_PARIETAL
from ..features import band_power, individual_alpha_frequency, window_features
from ..io import Session, events_from_markers, format_marker, make_raw
from . import adaptive, brain_type
from .sources import Source

METRICS = ["log_engagement", "log_workload", "log_fatigue"]
LIVE_BANDS = ["theta", "alpha", "beta"]


class _Grow:
    """끝에 계속 붙는 (n_ch, n) 배열 (용량 2배씩 증가)."""

    def __init__(self, n_ch, cap=256 * 60):
        self.a = np.zeros((n_ch, cap))
        self.n = 0

    def add(self, x):
        k = x.shape[1]
        if self.n + k > self.a.shape[1]:
            new = np.zeros((self.a.shape[0], max(2 * self.a.shape[1], self.n + k)))
            new[:, : self.n] = self.a[:, : self.n]
            self.a = new
        self.a[:, self.n:self.n + k] = x
        self.n += k

    def view(self, start=0, stop=None):
        return self.a[:, start:(self.n if stop is None else stop)]


@dataclass
class EngineState:
    phase: str = "idle"
    activity: str | None = None
    block: int | None = None
    phase_started: float = 0.0
    baseline: dict = field(default_factory=dict)
    brain_type: dict | None = None
    activity_results: list = field(default_factory=list)


class RealtimeEngine:
    def __init__(self, source: Source, step_sec: float = 0.5, win_sec: float = 2.0,
                 marker_sink=None):
        self.src = source
        self.sf = float(source.sfreq)
        self.ch = list(source.ch_names)
        self.step = int(step_sec * self.sf)
        self.win = int(win_sec * self.sf)
        self.raw = _Grow(len(self.ch))
        self.filt = _Grow(len(self.ch))
        self.windows: list[dict] = []
        self.events: list[tuple[float, str]] = []
        self.st = EngineState()
        self.marker_sink = marker_sink  # 예: tasks.markers.MarkerOutlet.push → LabRecorder 에도 기록
        self._next_win_end = self.win
        self._wave_sent = 0
        self._ec_psd: list[np.ndarray] = []
        self._f = None
        self._zi = None
        b, a = iirnotch(LINE_FREQ, 30, self.sf)
        self.sos = np.vstack([tf2sos(b, a), butter(4, [PRE.l_freq, PRE.h_freq], btype="band",
                                                    fs=self.sf, output="sos")])
        self.t0_wall = time.monotonic()
        self._fr = [i for i, c in enumerate(self.ch) if c in FRONTAL]
        self._blinks: list[float] = []

    # ── 시간 ────────────────────────────────────────────────────────
    @property
    def t(self) -> float:
        """엔진 시각(초) = 받은 샘플 수 / 샘플링률. 모든 마커는 이 시계로 찍는다."""
        return self.raw.n / self.sf

    def wall_now(self) -> float:
        return time.monotonic() - self.t0_wall

    # ── 데이터 입력 ──────────────────────────────────────────────────
    def pump(self, now: float | None = None) -> int:
        """소스에서 새 샘플을 받아 필터링하고, 쌓인 만큼 창 분석을 수행. 새로 분석한 창 수 반환."""
        x = self.src.pull(self.wall_now() if now is None else now)
        if x.shape[1] == 0:
            return 0
        if self._zi is None:  # 첫 샘플 값으로 필터 초기 상태 설정 → DC(약 800 µV) 과도응답 최소화
            self._zi = sosfilt_zi(self.sos)[:, None, :] * x[:, :1][None, :, :]
        y, self._zi = sosfilt(self.sos, x, axis=1, zi=self._zi)
        self.raw.add(x)
        self.filt.add(y)
        n_new = 0
        while self.filt.n >= self._next_win_end:
            self._analyze_window(self._next_win_end)
            self._next_win_end += self.step
            n_new += 1
        return n_new

    def _analyze_window(self, end: int):
        ctx = int(PRE.blink_pad_sec * self.sf)               # 창 앞쪽 깜빡임의 여백까지 보기 위한 문맥
        start = max(0, end - self.win - ctx)
        full = self.filt.view(start, end)                     # µV
        m_full = artifact_mask(full, self.ch, self.sf)
        seg, m = full[:, -self.win:], m_full[:, -self.win:]
        masked = np.where(m, np.nan, seg)
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ptp = np.nanmax(masked, 1) - np.nanmin(masked, 1)
            sd = np.nanstd(masked, 1)
        nclean = clean_segment_count(m, int(self.sf))
        good = (ptp < PRE.ptp_reject_uv) & (sd > PRE.flat_uv) & (nclean >= 1)
        # 깜빡임 수 세기: 이번 단계에 새로 '확정된' 구간에서 시작한 가림만 센다(중복 방지)
        if self._fr:
            L = m_full.shape[1]
            edges = rising_edges(m_full[self._fr[0]])
            new = edges[(edges >= L - self.step - ctx) & (edges < L - ctx)]
            self._blinks.extend([(end - (L - e)) / self.sf for e in new])
        info = pd.DataFrame({"t_start": [(end - self.win) / self.sf], "t_center": [(end - self.win / 2) / self.sf]})
        for c, g in zip(self.ch, good, strict=True):
            info[f"good_{c}"] = [bool(g)]
        info["n_good"] = int(good.sum())
        info["good"] = info["n_good"] >= PRE.min_good_channels
        feats = window_features(seg[None] * 1e-6, info, self.ch, self.sf, m[None]).iloc[0].to_dict()
        feats["masked_frontal"] = float(m[self._fr].mean()) if self._fr else 0.0
        st = self.st
        feats.update({"t": end / self.sf, "phase": st.phase, "activity": st.activity, "block": st.block,
                      "t_in_phase": end / self.sf - st.phase_started})
        self.windows.append(feats)
        if st.phase == "rest_ec" and feats["good"] and feats["t_in_phase"] > 5:
            tp = [self.ch.index(c) for c in TEMPORO_PARIETAL if c in self.ch]
            f, p = welch(seg[tp], fs=self.sf, nperseg=int(self.sf), axis=-1)
            self._f = f
            self._ec_psd.append(p.mean(0))

    # ── 이벤트 / 단계 전환 ───────────────────────────────────────────
    def mark(self, event: str, **attrs) -> str:
        """이벤트를 엔진 시계로 기록. *_start/_end 는 단계를 바꾼다."""
        txt = format_marker(event, **attrs) if attrs else event
        self.events.append((self.t, txt))
        if self.marker_sink:
            self.marker_sink(event, **attrs)
        st = self.st
        if event.endswith("_start"):
            name = event[:-6]
            st.phase, st.phase_started = ("activity" if name == "block" else name), self.t
            if name == "block":
                st.activity, st.block = attrs.get("task"), attrs.get("block")
        elif event.endswith("_end"):
            name = event[:-4]
            if name == "rest_eo":
                self._finish_eo()
            elif name == "rest_ec":
                self._finish_ec()
            elif name == "block":
                self._finish_activity(attrs.get("task"), attrs.get("block"))
            st.phase, st.activity, st.block, st.phase_started = "break", None, None, self.t
        return txt

    def set_phase(self, phase: str):
        """마커 없이 화면 상태만 바꿀 때 (signal_check, done 등)."""
        self.st.phase, self.st.phase_started = phase, self.t

    def _wins(self, phase=None, block=None, skip=5.0, good_only=True) -> pd.DataFrame:
        if not self.windows:
            return pd.DataFrame()
        w = pd.DataFrame(self.windows)
        m = pd.Series(True, index=w.index)
        if phase is not None:
            m &= w["phase"] == phase
        if block is not None:
            m &= w["block"] == block
        m &= w["t_in_phase"] > skip
        if good_only:
            m &= w["good"]
        return w[m]

    def _finish_eo(self):
        w = self._wins("rest_eo")
        b = self.st.baseline
        b["n_eo_windows"] = int(len(w))
        if len(w) < 5:
            b["warning"] = "눈 뜬 휴식 구간의 깨끗한 데이터가 부족합니다. 착용 상태를 확인 후 다시 측정하세요."
            return
        b["stats"] = {m: (float(w[m].mean()), float(w[m].std(ddof=1)) or 1e-6) for m in METRICS}
        b["ch_stats"] = {}
        for c in self.ch:
            for band in LIVE_BANDS:
                v = np.log(w[f"{band}_{c}"].dropna())
                if len(v) > 3:
                    b["ch_stats"][f"{band}_{c}"] = (float(v.mean()), float(v.std(ddof=1)) or 1e-6)
        b["rel_eo"] = {k: float(w[f"{k}_rel"].mean()) for k in ("theta", "alpha", "beta")}
        tp = [c for c in TEMPORO_PARIETAL if c in self.ch]
        b["alpha_eo"] = float(np.nanmedian(w[[f"alpha_{c}" for c in tp]].mean(axis=1)))

    def _finish_ec(self):
        b = self.st.baseline
        w = self._wins("rest_ec")
        tp = [c for c in TEMPORO_PARIETAL if c in self.ch]
        if len(w):
            b["alpha_ec"] = float(np.nanmedian(w[[f"alpha_{c}" for c in tp]].mean(axis=1)))
            if b.get("alpha_eo"):
                b["alpha_reactivity"] = round(b["alpha_ec"] / b["alpha_eo"], 2)
        if self._ec_psd and self._f is not None:
            b.update(individual_alpha_frequency(self._f, np.mean(self._ec_psd, axis=0)))
        self.st.brain_type = brain_type.classify(b)

    def _finish_activity(self, task, block):
        w = self._wins("activity", block=block)
        trials = [e for e in self.events_df().itertuples() if e.event == "trial" and getattr(e, "block", None) == block]
        res = adaptive.summarize_activity(task, block, w, self.st.baseline.get("stats"), trials)
        self.st.activity_results.append(res)

    def events_df(self) -> pd.DataFrame:
        if not self.events:
            return pd.DataFrame(columns=["onset", "event", "raw"])
        return events_from_markers(np.array([e[0] for e in self.events]), [e[1] for e in self.events])

    # ── 화면용 출력 ─────────────────────────────────────────────────
    def zscores(self, row: dict) -> dict:
        stats = self.st.baseline.get("stats")
        if not stats or not row.get("good"):
            return {m: None for m in METRICS}
        return {m: round((row[m] - mu) / sd, 2) if np.isfinite(row[m]) else None
                for m, (mu, sd) in stats.items()}

    def snapshot(self, smooth: int = 6) -> dict:
        """화면에 보낼 최신 상태 (0.5초마다)."""
        st = self.st
        out = {"t": round(self.t, 2), "phase": st.phase, "activity": st.activity, "block": st.block,
               "t_in_phase": round(self.t - st.phase_started, 1), "source": self.src.kind,
               "brain_type": st.brain_type, "baseline_ready": "stats" in st.baseline}
        if not self.windows:
            return out
        recent = pd.DataFrame(self.windows[-20:])
        out["quality"] = {c: round(float(recent[f"good_{c}"].mean()), 2) for c in self.ch}
        # 판정은 귀 뒤 채널 기준(접촉 상태를 가장 잘 보여 줌) + 이마는 깜빡임을 뺀 뒤의 평균
        tp = [out["quality"][c] for c in TEMPORO_PARIETAL if c in out["quality"]] or [1.0]
        af = [out["quality"][c] for c in FRONTAL if c in out["quality"]] or [1.0]
        q_tp, q_af = min(tp), float(np.mean(af))
        out["quality_status"] = ("good" if q_tp >= 0.7 and q_af >= 0.5 else
                                 "fair" if q_tp >= 0.4 else "poor")
        span = min(60.0, max(self.t, 1e-6))
        out["blinks_per_min"] = round(sum(1 for b in self._blinks if b >= self.t - span) * 60 / span, 1)
        out["masked_frontal"] = round(float(recent["masked_frontal"].mean()), 2)
        last = recent.iloc[-smooth:]
        good = last[last["good"]]
        row = good.iloc[-1].to_dict() if len(good) else last.iloc[-1].to_dict()
        if len(good):
            for m in METRICS:
                row[m] = float(good[m].median())
        out["rel"] = {b: _r(row.get(f"{b}_rel")) for b in ("delta", "theta", "alpha", "beta")}
        out["bands"] = {c: {b: _r(row.get(f"{b}_{c}")) for b in LIVE_BANDS} for c in self.ch}
        z = self.zscores(row)
        out["z"] = {"engagement": z["log_engagement"], "workload": z["log_workload"], "fatigue": z["log_fatigue"]}
        out["state_label"] = state_label(out["z"])
        cs = st.baseline.get("ch_stats", {})
        out["head"] = {c: {b: (_r((np.log(row[f"{b}_{c}"]) - cs[f"{b}_{c}"][0]) / cs[f"{b}_{c}"][1])
                               if f"{b}_{c}" in cs and row.get(f"{b}_{c}") and np.isfinite(row[f"{b}_{c}"]) else None)
                           for b in LIVE_BANDS} for c in self.ch}
        return out

    def waveform(self, decim: int = 2, max_sec: float = 2.0) -> dict:
        """마지막 호출 이후 새로 필터링된 파형 (µV, decim 배 솎아냄)."""
        start = max(self._wave_sent, self.filt.n - int(max_sec * self.sf))
        x = self.filt.view(start)[:, ::decim]
        self._wave_sent = self.filt.n
        return {"sfreq": self.sf / decim, "ch": self.ch, "data": np.round(x, 1).tolist()}

    def history(self, last_sec: float = 120) -> dict:
        """최근 지표 추이 (그래프 초기화용)."""
        if not self.windows:
            return {"t": [], "engagement": [], "workload": [], "fatigue": [], "rel": {}}
        w = pd.DataFrame(self.windows)
        w = w[w["t"] >= self.t - last_sec]
        zs = [self.zscores(r) for r in w.to_dict("records")]
        return {"t": w["t"].round(2).tolist(),
                "engagement": [z["log_engagement"] for z in zs],
                "workload": [z["log_workload"] for z in zs],
                "fatigue": [z["log_fatigue"] for z in zs],
                "rel": {b: [_r(v) for v in w[f"{b}_rel"]] for b in ("theta", "alpha", "beta")}}

    # ── 최종 결과 ───────────────────────────────────────────────────
    def to_session(self) -> Session:
        raw = make_raw(self.raw.view() * 1e-6, self.sf, self.ch)
        return Session(raw=raw, events=self.events_df(), meta={"source": f"live:{self.src.kind}"})

    def band_power_now(self, sec: float = 2.0) -> dict:
        x = self.filt.view(max(0, self.filt.n - int(sec * self.sf)))
        f, p = welch(x, fs=self.sf, nperseg=min(x.shape[1], int(self.sf)), axis=-1)
        return {b: band_power(f, p, lo, hi).tolist() for b, (lo, hi) in BANDS.items()}


def state_label(z: dict) -> str:
    e, f = z.get("engagement"), z.get("fatigue")
    if e is None:
        return "기준선 측정 전"
    if f is not None and f > 1.0 and e < 0:
        return "피로"
    if e > 0.8:
        return "몰입"
    if e < -0.8:
        return "이완·저각성"
    return "보통"


def _r(v, nd=3):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if np.isfinite(v) else None
