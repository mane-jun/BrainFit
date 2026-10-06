"""기기 없이 개발할 때: 가짜 세션을 .xdf 로 만든다 (LabRecorder 결과물과 같은 구조).

  python scripts/make_synthetic.py --out data/sample/synthetic_seed0.xdf --seed 0
  python scripts/analyze_session.py --xdf data/sample/synthetic_seed0.xdf
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brainfit.synth import synthetic_session  # noqa: E402
from brainfit.xdfwrite import session_to_xdf  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="data/sample/synthetic_seed0.xdf")
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--fatigue", type=float, default=1.0)
a = ap.parse_args()
p = session_to_xdf(synthetic_session(seed=a.seed, fatigue=a.fatigue), a.out)
print(f"저장: {p} ({p.stat().st_size / 1e6:.1f} MB)")
