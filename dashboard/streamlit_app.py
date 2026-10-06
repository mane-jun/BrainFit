"""[예비] 시연용 대시보드 (Streamlit). 앱이 정해지기 전 가장 빠른 결과 화면.

  streamlit run dashboard/streamlit_app.py
"""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brainfit.io import load_xdf  # noqa: E402
from brainfit.report import analyze, save_report  # noqa: E402
from brainfit.synth import synthetic_session  # noqa: E402

st.set_page_config(page_title="BrainFit", layout="wide")
st.title("🧠 BrainFit — 뇌파 기반 집중·인지 프로필")
st.caption("학습·훈련용 참고 지표이며 의학적 진단이 아닙니다.")

with st.sidebar:
    user = st.text_input("사용자 ID", "demo")
    src = st.radio("데이터", ["가짜 데이터(데모)", "XDF 파일 경로"])
    xdf = st.text_input("XDF 경로", "C:/EEGData/exp001/block_Default.xdf") if src != "가짜 데이터(데모)" else None
    run = st.button("분석 실행", type="primary")

if run:
    sess = synthetic_session() if xdf is None else load_xdf(xdf)
    out = ROOT / "outputs" / f"dash_{user}"
    with st.spinner("분석 중..."):
        summary = save_report(analyze(sess), out, user=user, store_root=ROOT / "data" / "users")
    p = summary["profile"]
    cols = st.columns(len(p["scores_ko"]) + 1)
    for c, (k, v) in zip(cols, p["scores_ko"].items(), strict=False):
        c.metric(k, v)
    cols[-1].metric("지속 집중 시간", f"{'≥' if p['sustained_censored'] else '약'} {p['sustained_min']}분")
    left, right = st.columns([2, 1])
    with left:
        for f in ("04_engagement", "03_band_timeline", "05_blocks", "06_fatigue"):
            st.image(str(out / f"{f}.png"))
    with right:
        for f in ("07_profile", "08_erp", "02_baseline_spectrum", "01_quality"):
            st.image(str(out / f"{f}.png"))
        st.json(summary["answers"])
        st.subheader("추천 훈련")
        for r in summary["recommendations"]:
            st.write(f"**{r['training']}** — {r['why']}  \n{r['how']}")
    with st.expander("전체 결과 JSON"):
        st.code(json.dumps(summary, ensure_ascii=False, indent=2)[:20000], language="json")
