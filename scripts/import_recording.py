"""녹화 파일(.xdf) → 재생용 데모 파일(.npz). 라이브 화면을 '실제 뇌파'로 개발·시연할 때 사용.

  python scripts/import_recording.py C:/EEGData/exp001/block_Default.xdf --id damwoo_2025_math
  python scripts/import_recording.py --synthetic --id synthetic_demo        # 가짜 세션으로 생성

개인정보 보호: 기기 MAC 주소·노트북 이름 등 XDF 메타데이터는 버리고 EEG(µV)·샘플링률·
이벤트(시각+문자열)만 저장한다. 그래도 뇌파는 개인 데이터이므로 본인 동의 없이 공개 저장소에 올리지 말 것.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brainfit.io import load_xdf  # noqa: E402
from brainfit.synth import synthetic_session  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("xdf", nargs="?")
ap.add_argument("--synthetic", action="store_true")
ap.add_argument("--mode", default="demo")
ap.add_argument("--id", required=True, help="파일 이름(실명 금지), 예: p01_session1")
ap.add_argument("--out", default="data/demo")
a = ap.parse_args()
sess = synthetic_session(seed=0, mode=a.mode) if a.synthetic else load_xdf(a.xdf)
x = (sess.raw.get_data() * 1e6).astype(np.float32)
ev = sess.events
out = Path(a.out) / f"{a.id}.npz"
out.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(out, eeg_uv=x, sfreq=float(sess.raw.info["sfreq"]), ch=np.array(sess.raw.ch_names),
                    event_onset=ev["onset"].to_numpy(float) if len(ev) else np.zeros(0),
                    event_raw=ev["raw"].astype(str).to_numpy() if len(ev) else np.array([], dtype=str))
print(f"저장: {out}  ({x.shape[1] / sess.raw.info['sfreq']:.0f}초, {out.stat().st_size / 1e6:.1f} MB)")
