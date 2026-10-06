"""[확장] 실시간 집중 지표 모니터 — 시연용.

BlueMuse 가 내보내는 LSL EEG 를 직접 받아 0.5초마다 최근 2초 창의 대역 파워와
engagement 를 계산해 그래프로 보여준다. (LabRecorder 와 동시에 켜도 된다: LSL 은 여러 수신자 가능)

  python scripts/live_monitor.py              # 실제 Muse
  python scripts/live_monitor.py --fake       # 기기 없이 가짜 LSL 스트림을 띄워서 테스트

처음 30초는 '눈 뜨고 편하게' 있으면 그 구간을 기준으로 z 점수를 낸다.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brainfit.config import BANDS, MUSE_EEG_CHANNELS  # noqa: E402
from brainfit.features import band_power  # noqa: E402


def fake_stream():
    """가짜 Muse LSL 스트림: 20초 간격으로 '휴식(알파↑)'과 '집중(베타↑)'이 번갈아 나옴."""
    from pylsl import StreamInfo, StreamOutlet

    info = StreamInfo("Muse-FAKE", "EEG", 4, 256, "float32", "fake-muse")
    ch = info.desc().append_child("channels")
    for c in MUSE_EEG_CHANNELS:
        ch.append_child("channel").append_child_value("label", c)
    out = StreamOutlet(info)
    t = 0
    while True:
        focus = (t // (256 * 20)) % 2 == 1
        n = np.arange(t, t + 32) / 256
        a, b = (3, 6) if focus else (12, 2)
        x = (a * np.sin(2 * np.pi * 10 * n) + b * np.sin(2 * np.pi * 20 * n))[:, None] \
            + np.random.randn(32, 4) * 5 + 800
        out.push_chunk(x.tolist())
        t += 32
        time.sleep(32 / 256)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--baseline-sec", type=float, default=30)
    a = ap.parse_args()

    import matplotlib.pyplot as plt
    from pylsl import StreamInlet, resolve_byprop
    from scipy.signal import butter, sosfiltfilt, welch

    from brainfit.fonts import setup_korean_font

    if a.fake:
        threading.Thread(target=fake_stream, daemon=True).start()
        time.sleep(1)
    print("EEG 스트림 찾는 중... (BlueMuse 에서 Start Streaming 했는지 확인)")
    streams = resolve_byprop("type", "EEG", timeout=10)
    if not streams:
        sys.exit("EEG 스트림을 찾지 못했습니다.")
    inlet = StreamInlet(streams[0], max_chunklen=12)
    sf = int(inlet.info().nominal_srate())
    buf = deque(maxlen=sf * 4)
    sos = butter(4, [1, 40], btype="band", fs=sf, output="sos")

    hist_t, hist_e, base = deque(maxlen=600), deque(maxlen=600), []
    t0 = time.time()
    setup_korean_font()
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6))
    while plt.fignum_exists(fig.number):
        chunk, _ = inlet.pull_chunk(timeout=0.1)
        for s in chunk:
            buf.append(s[:4])
        if len(buf) < sf * 2:
            plt.pause(0.05)
            continue
        x = sosfiltfilt(sos, np.array(buf).T, axis=1)[:, -sf * 2:]
        f, p = welch(x, fs=sf, nperseg=sf, axis=-1)
        bp = {b: band_power(f, p, lo, hi).mean() for b, (lo, hi) in BANDS.items()}
        eng = np.log(bp["beta"] / (bp["alpha"] + bp["theta"]))
        el = time.time() - t0
        if el < a.baseline_sec:
            base.append(eng)
            z, status = 0.0, f"기준선 측정 중... {a.baseline_sec - el:.0f}s"
        else:
            z = (eng - np.mean(base)) / (np.std(base) + 1e-6)
            status = "집중 ↑" if z > 1 else ("이완/저하 ↓" if z < -1 else "보통")
        hist_t.append(el)
        hist_e.append(z)
        ax1.cla()
        ax1.bar(list(bp)[:4], [bp[k] for k in list(bp)[:4]], color="#4c72b0")
        ax1.set_title(f"현재 대역 파워 — {status}")
        ax2.cla()
        ax2.plot(hist_t, hist_e, c="#c44e52")
        ax2.axhline(0, c="gray", lw=0.8)
        ax2.set_ylabel("engagement z")
        ax2.set_xlabel("시간 (s)")
        plt.pause(0.5)


if __name__ == "__main__":
    main()
