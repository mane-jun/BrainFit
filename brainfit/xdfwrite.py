"""최소 XDF 작성기 (개발/테스트 전용).

LabRecorder 없이도 load_xdf() 를 검증할 수 있도록, 가짜 세션을 LabRecorder 와 같은
구조(EEG 스트림 µV + Markers 문자열 스트림)의 .xdf 로 저장한다.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def _varlen(n: int) -> bytes:
    if n < 256:
        return b"\x01" + struct.pack("<B", n)
    if n < 2**32:
        return b"\x04" + struct.pack("<I", n)
    return b"\x08" + struct.pack("<Q", n)


def _chunk(tag: int, content: bytes) -> bytes:
    return _varlen(len(content) + 2) + struct.pack("<H", tag) + content


def _header_xml(name, typ, n_ch, srate, fmt, labels=None) -> bytes:
    chans = ""
    if labels:
        chans = "<desc><channels>" + "".join(
            f"<channel><label>{lb}</label><unit>microvolts</unit><type>EEG</type></channel>"
            for lb in labels) + "</channels></desc>"
    return (f'<?xml version="1.0"?><info><name>{name}</name><type>{typ}</type>'
            f"<channel_count>{n_ch}</channel_count><nominal_srate>{srate}</nominal_srate>"
            f"<channel_format>{fmt}</channel_format><created_at>0</created_at>{chans}</info>"
            ).encode()


def write_xdf(path: str | Path, eeg_uv: np.ndarray, eeg_ts: np.ndarray, labels: list[str],
              srate: float, marker_ts: np.ndarray, markers: list[str]) -> Path:
    """eeg_uv: (n_samples, n_ch) µV, eeg_ts: (n_samples,) 초"""
    out = bytearray(b"XDF:")
    out += _chunk(1, b'<?xml version="1.0"?><info><version>1.0</version></info>')
    out += _chunk(2, struct.pack("<I", 1) + _header_xml("Muse-SYNTH EEG", "EEG",
                                                         eeg_uv.shape[1], srate, "float32", labels))
    out += _chunk(2, struct.pack("<I", 2) + _header_xml("BrainFitMarkers", "Markers", 1, 0,
                                                         "string"))
    for i in range(0, len(eeg_ts), 1024):
        body = bytearray()
        ts, xs = eeg_ts[i:i + 1024], eeg_uv[i:i + 1024].astype("<f4")
        for t, x in zip(ts, xs, strict=False):
            body += b"\x08" + struct.pack("<d", t) + x.tobytes()
        out += _chunk(3, struct.pack("<I", 1) + _varlen(len(ts)) + bytes(body))
    body = bytearray()
    for t, m in zip(marker_ts, markers, strict=False):
        b = m.encode()
        body += b"\x08" + struct.pack("<d", t) + _varlen(len(b)) + b
    out += _chunk(3, struct.pack("<I", 2) + _varlen(len(markers)) + bytes(body))
    for sid, ts, n in ((1, eeg_ts, len(eeg_ts)), (2, marker_ts, len(markers))):
        xml = (f'<?xml version="1.0"?><info><first_timestamp>{ts[0]}</first_timestamp>'
               f"<last_timestamp>{ts[-1]}</last_timestamp><sample_count>{n}</sample_count>"
               "</info>").encode()
        out += _chunk(6, struct.pack("<I", sid) + xml)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(bytes(out))
    return Path(path)


def session_to_xdf(sess, path: str | Path, t0: float = 1000.0) -> Path:
    """synthetic_session() 결과를 LabRecorder 형식처럼 저장 (µV, Right AUX 포함)."""
    sf = sess.raw.info["sfreq"]
    x = sess.raw.get_data().T * 1e6
    aux = np.random.default_rng(0).normal(0, 50, (x.shape[0], 1))  # 쓰레기 AUX 채널
    x = np.hstack([x, aux])
    ts = t0 + np.arange(x.shape[0]) / sf
    ev = sess.events
    return write_xdf(path, x, ts, list(sess.raw.ch_names) + ["Right AUX"], sf,
                     t0 + ev["onset"].to_numpy(), ev["raw"].astype(str).tolist())
