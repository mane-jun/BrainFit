"""실시간 뇌파 입력 소스. 모두 같은 인터페이스: pull(now) → (4, k) µV 배열.

- LSLSource    : BlueMuse 가 내보내는 실제 Muse 2 EEG (LSL)
- SimSource    : 기기 없이 시연·개발. set_state() 로 화면 흐름(눈 감기/활동)에 맞춰 신호가 바뀜
- ReplaySource : 녹화 파일(.npz / .xdf / Session)을 실시간처럼 재생 → 실제 데이터로 화면 개발

now = 세션 시작 후 경과 시간(초). Sim/Replay 는 now 까지의 샘플만 만들어 주므로
테스트에서는 now 를 직접 넘겨 '빨리 감기' 할 수 있다.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

from ..config import MUSE_EEG_CHANNELS, MUSE_SFREQ

CH = MUSE_EEG_CHANNELS


class Source:
    sfreq: float = MUSE_SFREQ
    ch_names: list[str] = CH
    kind = "base"

    def pull(self, now: float) -> np.ndarray:  # (n_ch, k) µV
        raise NotImplementedError

    def close(self):
        pass


# ── 기기 없이: 상태 제어형 시뮬레이터 ─────────────────────────────────
# 상태별 (alpha, theta, beta) 진폭 µV. 활동 'response' 를 낮추면 뇌파가 덜 움직이는 상황을 흉내 낸다.
SIM_STATES = {
    "idle": (7.0, 4.0, 2.6), "rest_eo": (7.0, 4.0, 2.6), "rest_ec": (16.0, 4.0, 2.4),
    "focus": (4.0, 5.5, 4.2), "relaxed": (10.0, 4.5, 2.2), "drowsy": (8.0, 7.5, 1.8),
}


class _BandGen:
    """연속적인 대역 잡음 생성기 (필터 상태를 유지해 청크 경계가 끊기지 않음)."""

    def __init__(self, rng, lo, hi, sf, n_ch):
        self.sos = butter(4, [lo, hi], btype="band", fs=sf, output="sos")
        self.zi = np.repeat(sosfilt_zi(self.sos)[:, None, :] * 0, n_ch, axis=1)
        self.rng = rng
        self.gain = 1.0 / np.sqrt((hi - lo) / sf * 2)  # 대략 단위 분산으로

    def __call__(self, n_ch, k):
        x = self.rng.standard_normal((n_ch, k))
        y, self.zi = sosfilt(self.sos, x, axis=1, zi=self.zi)
        return y * self.gain


class SimSource(Source):
    kind = "sim"

    def __init__(self, seed: int = 0, iaf: float = 10.0, blink_rate: float = 0.15):
        self.rng = np.random.default_rng(seed)
        sf = self.sfreq
        self.alpha = _BandGen(self.rng, iaf - 1.2, iaf + 1.2, sf, 4)
        self.theta = _BandGen(self.rng, 4.5, 7.5, sf, 4)
        self.beta = _BandGen(self.rng, 14, 26, sf, 4)
        self.pink = _BandGen(self.rng, 1.0, 40.0, sf, 4)
        self.n_done = 0
        self.env = np.array(SIM_STATES["idle"], float)
        self.target = self.env.copy()
        self.blink_rate = blink_rate
        self.eyes_closed = False
        self._blink_left = 0

    def set_state(self, state: str, response: float = 1.0):
        """state: SIM_STATES 키. response(0~1): 1 이면 그 상태로 완전히, 0 이면 평상시 그대로."""
        base = np.array(SIM_STATES["rest_eo"])
        tgt = np.array(SIM_STATES.get(state, SIM_STATES["idle"]))
        self.target = base + response * (tgt - base)
        self.eyes_closed = state == "rest_ec"

    def pull(self, now: float) -> np.ndarray:
        n_target = int(now * self.sfreq)
        k = max(0, n_target - self.n_done)
        if k == 0:
            return np.zeros((4, 0))
        # 포락선은 약 1초에 걸쳐 목표로 이동
        a = 1 - np.exp(-k / self.sfreq)
        self.env = self.env + a * (self.target - self.env)
        al, th, be = self.env
        gains_a = np.array([1.0, 0.6, 0.6, 1.0])[:, None]   # 알파: 귀 뒤(TP) 우세
        gains_t = np.array([0.8, 1.3, 1.3, 0.8])[:, None]   # 세타: 이마(AF) 우세
        x = (6.0 * self.pink(4, k) + al * gains_a * self.alpha(4, k)
             + th * gains_t * self.theta(4, k) + be * self.beta(4, k))
        t = (self.n_done + np.arange(k)) / self.sfreq
        x += 1.0 * np.sin(2 * np.pi * 60 * t)  # 전원 잡음
        if not self.eyes_closed:  # 눈 깜빡임 (이마 채널)
            for i in np.flatnonzero(self.rng.random(k) < self.blink_rate / self.sfreq):
                w = np.hanning(int(0.3 * self.sfreq)) * self.rng.uniform(150, 300)
                end = min(k, i + len(w))
                x[1:3, i:end] += w[: end - i]
        self.n_done += k
        return x + 800.0


# ── 녹화 재생 ────────────────────────────────────────────────────────
def load_replay_array(path: str | Path) -> tuple[np.ndarray, float]:
    """.npz(import_recording.py 결과) 또는 .xdf → (4, n) µV, sfreq"""
    path = Path(path)
    if path.suffix == ".npz":
        z = np.load(path)
        return z["eeg_uv"].astype(float), float(z["sfreq"])
    from ..io import load_xdf

    s = load_xdf(path)
    return s.raw.get_data() * 1e6, float(s.raw.info["sfreq"])


class ReplaySource(Source):
    kind = "replay"

    def __init__(self, data_uv: np.ndarray, sfreq: float, speed: float = 1.0, loop: bool = True):
        self.data, self.sfreq, self.speed, self.loop = data_uv, sfreq, speed, loop
        self.n_done = 0

    @classmethod
    def from_file(cls, path, **kw):
        x, sf = load_replay_array(path)
        return cls(x, sf, **kw)

    def pull(self, now: float) -> np.ndarray:
        n_target = int(now * self.speed * self.sfreq)
        k = max(0, n_target - self.n_done)
        n = self.data.shape[1]
        idx = (self.n_done + np.arange(k))
        if not self.loop:
            idx = idx[idx < n]
        out = self.data[:, idx % n]
        self.n_done += k
        return out


# ── 실제 Muse 2 (BlueMuse → LSL) ─────────────────────────────────────
class LSLSource(Source):
    kind = "lsl"

    def __init__(self, timeout: float = 5.0):
        from pylsl import StreamInlet, resolve_byprop

        streams = resolve_byprop("type", "EEG", timeout=timeout)
        if not streams:
            raise RuntimeError("EEG LSL 스트림이 없습니다. BlueMuse 에서 Start Streaming 했는지 확인하세요.")
        self.inlet = StreamInlet(streams[0], max_buflen=30)
        info = self.inlet.info()
        self.sfreq = info.nominal_srate() or MUSE_SFREQ
        labels = []
        ch = info.desc().child("channels").child("channel")
        for _ in range(info.channel_count()):
            labels.append(ch.child_value("label"))
            ch = ch.next_sibling()
        self.idx = [labels.index(c) for c in CH if c in labels] or list(range(4))
        self.name = info.name()

    def pull(self, now: float) -> np.ndarray:
        chunk, _ = self.inlet.pull_chunk(timeout=0.0, max_samples=4096)
        if not chunk:
            return np.zeros((4, 0))
        return np.asarray(chunk, float)[:, self.idx].T


def make_source(kind: str, replay_path: str | None = None, **kw) -> Source:
    if kind == "lsl":
        return LSLSource()
    if kind == "replay":
        if not replay_path:
            raise ValueError("replay 모드에는 파일 경로가 필요합니다 (data/demo/*.npz).")
        return ReplaySource.from_file(replay_path, **kw)
    return SimSource(**kw)
