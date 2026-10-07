"""Muse 2 신호 진단: 기기 문제인지, 착용 문제인지, 눈 깜빡임(정상)인지 구분한다.

  python scripts/check_signal.py            # 눈 뜸 20초 → 눈 감음 20초
  python scripts/check_signal.py --sec 30   # 구간 길이 변경

BlueMuse 에서 Start Streaming 한 상태에서 실행. 라이브 웹 서버는 켜 둬도 된다(LSL 은 여러 곳에서 동시에 받을 수 있음).
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from pylsl import StreamInlet, resolve_byprop
from scipy.signal import butter, sosfiltfilt, welch

CH = ["TP9", "AF7", "AF8", "TP10"]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brainfit.artifacts import artifact_mask  # noqa: E402
from brainfit.config import PRE  # noqa: E402

PTP_LIMIT = PRE.ptp_reject_uv  # 라이브 화면과 같은 잡음 기준


def record(inlet, sec, sf):
    inlet.pull_chunk(timeout=0.0, max_samples=100000)  # 이전에 쌓인 데이터 버리기
    buf, t0 = [], time.time()
    while time.time() - t0 < sec:
        d, _ = inlet.pull_chunk(timeout=0.2, max_samples=4096)
        buf += d
        left = int(sec - (time.time() - t0))
        print(f"\r  남은 시간 {left:2d}초", end="", flush=True)
    print()
    x = np.asarray(buf, float)[:, :4].T
    return x[:, : int(sec * sf)]


def analyze(x, sf):
    y = sosfiltfilt(butter(4, [1, 40], "band", fs=sf, output="sos"), x, axis=1)[:, int(sf):]
    w, s = int(2 * sf), int(0.5 * sf)
    ptps = np.array([np.ptp(y[:, i:i + w], axis=1) for i in range(0, y.shape[1] - w, s)])
    m = artifact_mask(y, CH, sf)  # 라이브 화면과 같은 깜빡임 가림
    ym = np.where(m, np.nan, y)
    ptps_m = np.array([np.nanmax(ym[:, i:i + w], 1) - np.nanmin(ym[:, i:i + w], 1)
                       if (~m[:, i:i + w]).any() else np.full(4, np.inf) for i in range(0, y.shape[1] - w, s)])
    low = sosfiltfilt(butter(4, 4, "low", fs=sf, output="sos"), y, axis=1)
    blinks = []
    for c in (1, 2):  # AF7, AF8: 100 µV 넘는 느린 큰 파형 = 깜빡임 후보
        above = np.abs(low[c]) > 100
        blinks.append(int(np.sum(np.diff(above.astype(int)) == 1)))
    f, p = welch(y, fs=sf, nperseg=int(2 * sf), axis=1)
    alpha = p[:, (f >= 8) & (f <= 13)].mean(axis=1)
    return {"good": (ptps < PTP_LIMIT).mean(axis=0), "good_masked": (np.nan_to_num(ptps_m, nan=np.inf) < PTP_LIMIT).mean(axis=0),
            "ptp_med": np.median(ptps, axis=0),
            "ptp_p90": np.percentile(ptps, 90, axis=0), "blinks": max(blinks),
            "alpha": alpha, "std": y.std(axis=1), "sec": y.shape[1] / sf}


def show(name, r):
    print(f"\n[{name}]  깜빡임 후보 약 {r['blinks']}회 / {r['sec']:.0f}초")
    print("  채널    깨끗한 구간(예전) (깜빡임 제외)  ptp 중앙값  ptp 상위10%   std")
    for i, c in enumerate(CH):
        print(f"  {c:<6}   {r['good'][i] * 100:6.0f}%      {r['good_masked'][i] * 100:6.0f}%    "
              f"{r['ptp_med'][i]:8.0f}µV  {r['ptp_p90'][i]:8.0f}µV  {r['std'][i]:6.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sec", type=float, default=20)
    a = ap.parse_args()
    s = resolve_byprop("type", "EEG", timeout=5)
    if not s:
        raise SystemExit("EEG 스트림 없음 → BlueMuse 에서 Start Streaming 확인")
    inlet = StreamInlet(s[0], max_buflen=60)
    sf = inlet.info().nominal_srate() or 256
    print(f"스트림: {s[0].name()}  ({sf:.0f} Hz)")

    input("\n① 눈을 뜨고 화면 한 점을 편하게 보세요. 준비되면 Enter")
    eo = analyze(record(inlet, a.sec, sf), sf)
    input("② 이제 눈을 감고 쉬세요. Enter 를 누른 뒤 눈을 감으세요 (끝나면 삑 소리)")
    ec = analyze(record(inlet, a.sec, sf), sf)
    print("\a")
    show("눈 뜸", eo)
    show("눈 감음", ec)

    tp, af = [0, 3], [1, 2]
    react = float(ec["alpha"][tp].mean() / max(eo["alpha"][tp].mean(), 1e-9))
    print(f"\n알파 반응성(귀 뒤, 눈 감음/눈 뜸) = {react:.2f}  (1.3 이상이면 뇌파가 정상적으로 측정되는 신호)")

    print("\n── 판정 ──")
    tp_ec = ec["good"][tp].min()
    af_eo, af_ec = eo["good"][af].mean(), ec["good"][af].mean()
    if tp_ec < 0.5 and ec["good"][af].mean() < 0.5:
        print("· 눈을 감아도 모든 채널이 나쁨 → 착용/접촉 문제 가능성이 큼."
              " 머리카락 정리·물티슈로 적시기 후 재측정. 다른 사람이 써도 같으면 기기·센서 점검 필요.")
    elif tp_ec < 0.5:
        print("· 귀 뒤 센서만 나쁨 → 귀 뒤 고무가 피부에 안 닿는 경우가 대부분. 머리카락을 넘기고 밴드를 조여 보세요.")
    elif af_eo < 0.6 and af_ec >= 0.7:
        print("· 이마 채널이 눈 뜰 때만 나쁨 → 기기 문제가 아니라 '눈 깜빡임' 때문(정상 현상)."
              " 분석 코드에서 깜빡임 구간만 잘라내도록 개선하면 됨.")
    if react >= 1.3:
        print("· 눈을 감으면 알파가 커짐 → 기기는 뇌파를 제대로 측정하고 있음(기기 고장 아님).")
    elif tp_ec >= 0.5:
        print("· 알파 반응이 약함 → 귀 뒤 접촉을 다시 확인하거나, 눈 감음 구간을 더 길게(30초+) 재측정.")
    bad_ptp = [c for i, c in enumerate(CH) if ec["ptp_med"][i] > PTP_LIMIT]
    if bad_ptp and react >= 1.3:
        print(f"· 뇌파는 정상인데 {', '.join(bad_ptp)} 의 진폭이 기준({PTP_LIMIT:.0f}µV)보다 큼 → 잡음 기준값 조정이 필요할 수 있음.")


if __name__ == "__main__":
    main()
