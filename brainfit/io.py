"""데이터 입출력.

- XDF(LabRecorder 저장 파일) → Session
- Session 은 (mne.Raw, events DataFrame) 묶음. 모든 분석 함수는 Session 을 받는다.
- 마커 문자열 규약은 docs/MARKERS.md 참고: "event|key=value|key=value"
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import mne
import numpy as np
import pandas as pd

from .config import MUSE_EEG_CHANNELS, MUSE_SFREQ

mne.set_log_level("WARNING")
logging.getLogger("pyxdf").setLevel(logging.ERROR)  # "clock-segments differ" 경고 숨김


# ── 마커 파싱 ────────────────────────────────────────────────────────
def parse_marker(text: str) -> dict:
    """'trial|task=nback2|idx=3|correct=1' → {'event': 'trial', 'task': 'nback2', ...}"""
    parts = [p.strip() for p in str(text).split("|") if p.strip()]
    out: dict = {"event": parts[0] if parts else ""}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = _auto_type(v.strip())
    return out


def format_marker(event: str, **attrs) -> str:
    return "|".join([event] + [f"{k}={v}" for k, v in attrs.items()])


def _auto_type(v: str):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def events_from_markers(onsets_s: np.ndarray, texts: list[str]) -> pd.DataFrame:
    rows = []
    for t, txt in zip(onsets_s, texts, strict=False):
        d = parse_marker(txt)
        d["onset"] = float(t)
        d["raw"] = txt
        rows.append(d)
    if not rows:
        return pd.DataFrame(columns=["onset", "event", "raw"])
    return pd.DataFrame(rows).sort_values("onset").reset_index(drop=True)


def segments_from_events(events: pd.DataFrame) -> pd.DataFrame:
    """*_start / *_end 쌍을 구간 표로 만든다.

    결과 컬럼: name, start, end, duration, task, block
      - rest_eo_start/rest_eo_end → name='rest_eo'
      - block_start|task=nback2|block=1 → name='block', task='nback2', block=1
    """
    segs = []
    open_: dict[tuple, float] = {}
    for _, r in events.iterrows():
        ev = str(r["event"])
        if ev.endswith("_start") or ev.endswith("_end"):
            base = ev.rsplit("_", 1)[0]
            task = r.get("task") if "task" in r and pd.notna(r.get("task")) else None
            block = r.get("block") if "block" in r and pd.notna(r.get("block")) else None
            key = (base, task, block)
            if ev.endswith("_start"):
                open_[key] = r["onset"]
            elif key in open_:
                s = open_.pop(key)
                segs.append({"name": base, "start": s, "end": r["onset"],
                             "duration": r["onset"] - s, "task": task, "block": block})
    return pd.DataFrame(segs, columns=["name", "start", "end", "duration", "task", "block"])


# ── Session ──────────────────────────────────────────────────────────
@dataclass
class Session:
    raw: mne.io.BaseRaw
    events: pd.DataFrame
    meta: dict = field(default_factory=dict)

    @property
    def segments(self) -> pd.DataFrame:
        return segments_from_events(self.events)

    @property
    def trials(self) -> pd.DataFrame:
        if "event" not in self.events:
            return pd.DataFrame()
        return self.events[self.events["event"] == "trial"].reset_index(drop=True)

    def save(self, folder: str | Path) -> Path:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.raw.save(folder / "eeg_raw.fif", overwrite=True)
        self.events.to_csv(folder / "events.csv", index=False)
        (folder / "meta.json").write_text(json.dumps(self.meta, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
        return folder

    @classmethod
    def load(cls, folder: str | Path) -> "Session":
        folder = Path(folder)
        raw = mne.io.read_raw_fif(folder / "eeg_raw.fif", preload=True)
        events = pd.read_csv(folder / "events.csv")
        meta_p = folder / "meta.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
        return cls(raw=raw, events=events, meta=meta)


def _montage():
    """MNE 버전에 따라 이름이 다름(1.13+: colin27_1020). 토포맵용일 뿐 분석엔 필수 아님."""
    import warnings
    for name in ("colin27_1020", "standard_1020"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return mne.channels.make_standard_montage(name)
        except ValueError:
            continue
    return None


def make_raw(data_v: np.ndarray, sfreq: float, ch_names: list[str]) -> mne.io.RawArray:
    """data_v: (n_ch, n_samples), 단위 **볼트(V)**. MNE 는 V 를 기대한다."""
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data_v, info)
    raw.set_montage(_montage(), match_case=False, on_missing="ignore")
    return raw


def is_marker_stream(stream: dict) -> bool:
    """마커 스트림 판정: type 이 Markers 이거나, 문자열 채널 1개짜리 스트림(PsychoPy 등이 type 을 다르게 쓰는 경우)."""
    info = stream["info"]
    typ = (info.get("type") or [""])[0].lower()
    fmt = (info.get("channel_format") or [""])[0].lower()
    return typ in ("markers", "marker", "events", "event") or fmt == "string"


def list_streams(path: str | Path) -> list[dict]:
    """XDF 안의 스트림 요약 (실데이터 점검용)."""
    import pyxdf

    streams, _ = pyxdf.load_xdf(str(path), dejitter_timestamps=False)
    out = []
    for s in streams:
        i = s["info"]
        ts = s["time_stamps"]
        out.append({"name": i["name"][0], "type": i["type"][0], "format": i["channel_format"][0],
                    "n_channels": int(i["channel_count"][0]), "nominal_srate": float(i["nominal_srate"][0]),
                    "n_samples": len(ts),
                    "duration_s": round(float(ts[-1] - ts[0]), 1) if len(ts) > 1 else 0.0})
    return out


def load_xdf(path: str | Path) -> Session:
    """LabRecorder 가 저장한 .xdf 를 Session 으로.

    주의 1) BlueMuse 는 µV 단위로 보낸다 → 1e-6 곱해서 V 로 바꾼다.
           (안 바꾸면 PSD 가 dB 기준 +120 dB 부풀려져 140~160 dB 로 보인다)
    주의 2) 블루투스 끊김으로 샘플이 빠질 수 있어 마커 시점은 '타임스탬프'로 맞춘다.
    """
    import pyxdf

    streams, _ = pyxdf.load_xdf(str(path), dejitter_timestamps=True)
    eeg = next((s for s in streams if s["info"]["type"][0].upper() == "EEG"), None)
    if eeg is None:
        raise ValueError("XDF 안에 EEG 스트림이 없습니다. LabRecorder 에서 EEG 를 체크했는지 확인하세요.")
    marker_streams = [s for s in streams if is_marker_stream(s)]

    ts = np.asarray(eeg["time_stamps"])
    x = np.asarray(eeg["time_series"], dtype=float).T  # (n_ch, n)
    try:
        chans = eeg["info"]["desc"][0]["channels"][0]["channel"]
        labels = [c["label"][0] for c in chans]
    except (KeyError, IndexError, TypeError):
        labels = MUSE_EEG_CHANNELS + ["Right AUX"][: max(0, x.shape[0] - 4)]

    keep = [i for i, n in enumerate(labels) if n in MUSE_EEG_CHANNELS]
    x, labels = x[keep], [labels[i] for i in keep]
    if np.nanmedian(np.abs(x)) > 1e-2:  # µV 로 판단
        x = x * 1e-6
    x = np.nan_to_num(x)

    nominal = float(eeg["info"]["nominal_srate"][0]) or MUSE_SFREQ
    effective = (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) > 1 else nominal
    gaps = np.diff(ts)
    n_gaps = int(np.sum(gaps > 3.0 / nominal))

    raw = make_raw(x, nominal, labels)

    texts, onsets = [], []
    for ms in marker_streams:
        for t, v in zip(ms["time_stamps"], ms["time_series"], strict=False):
            idx = int(np.clip(np.searchsorted(ts, t), 0, len(ts) - 1))
            onsets.append(idx / nominal)
            texts.append(v[0] if isinstance(v, (list, np.ndarray)) else str(v))
    events = events_from_markers(np.array(onsets), texts)

    meta = {"source": str(path), "nominal_srate": nominal,
            "effective_srate": round(float(effective), 2), "n_gaps": n_gaps,
            "duration_s": round(float(ts[-1] - ts[0]), 1) if len(ts) else 0.0}
    if not marker_streams:
        meta["warning"] = "마커 스트림 없음 → 휴식/과제 구간을 알 수 없어 기준선·과제 분석이 제한됩니다."
    return Session(raw=raw, events=events, meta=meta)


def add_manual_segments(sess: Session, spec: str) -> Session:
    """마커 없이 녹화한 파일용. 예: "rest_eo:5-65,rest_ec:70-130,block:nback2:140-200"

    - 이름:시작-끝(초)  또는  block:과제명:시작-끝
    """
    rows = []
    for i, item in enumerate(s.strip() for s in spec.split(",") if s.strip()):
        parts = item.split(":")
        a, b = (float(v) for v in parts[-1].split("-"))
        if parts[0] == "block":
            task = parts[1]
            rows += [(a, format_marker("block_start", task=task, block=i + 1)),
                     (b, format_marker("block_end", task=task, block=i + 1))]
        else:
            rows += [(a, f"{parts[0]}_start"), (b, f"{parts[0]}_end")]
    extra = events_from_markers(np.array([r[0] for r in rows]), [r[1] for r in rows])
    ev = pd.concat([sess.events, extra], ignore_index=True).sort_values("onset")
    return Session(raw=sess.raw, events=ev.reset_index(drop=True),
                   meta=dict(sess.meta, manual_segments=spec))
