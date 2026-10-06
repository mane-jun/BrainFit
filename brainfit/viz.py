"""matplotlib 시각화. 모든 함수는 Figure 를 반환하고, 저장은 report.py 가 한다.

그림 목록 (시연 순서 추천)
  01 신호 품질        → '데이터를 믿을 수 있나'부터 보여준다
  02 기준선 스펙트럼   → 눈 감으면 알파(8~13Hz)가 솟는 것 = 기기가 제대로 측정 중이라는 증거
  03 대역 타임라인     → 휴식/과제 구간별 세타·알파·베타 변화
  04 집중 곡선         → 지속 집중 시간 표시
  05 블록 요약         → 과제별 집중·정확도
  06 피로 추세         → 시간 경과에 따른 피로 지표
  07 Brain Profile    → 레이더 차트
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .fonts import setup_korean_font  # noqa: E402

SEG_COLORS = {"rest_eo": "#d8e8f5", "rest_ec": "#dcefd8", "rest_ec_post": "#dcefd8",
              "block": "#f9e6cf"}
BAND_COLORS = {"theta": "#4c72b0", "alpha": "#dd8452", "beta": "#55a868"}


setup_korean_font()


def _shade_segments(ax, segments: pd.DataFrame):
    for _, s in segments.iterrows():
        ax.axvspan(s["start"], s["end"], color=SEG_COLORS.get(s["name"], "#eeeeee"),
                   alpha=0.6, lw=0)
        label = s["task"] if s["name"] == "block" else s["name"].replace("rest_", "")
        ax.text((s["start"] + s["end"]) / 2, 1.0, str(label), transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=7)


def fig_quality(quality: dict, ch_names: list[str]):
    fig, ax = plt.subplots(figsize=(6, 3))
    vals = [quality[f"{c}_good_ratio"] * 100 for c in ch_names]
    bars = ax.bar(ch_names, vals, color=["#4c72b0" if v >= 60 else "#c44e52" for v in vals])
    ax.axhline(60, ls="--", c="gray", lw=1)
    ax.set_ylim(0, 100)
    ax.set_ylabel("사용 가능한 창 비율 (%)")
    ax.set_title(f"신호 품질 — 전체 {quality['good_window_ratio'] * 100:.0f}%")
    ax.bar_label(bars, fmt="%.0f")
    fig.tight_layout()
    return fig


def fig_baseline_spectrum(baseline: dict):
    fig, ax = plt.subplots(figsize=(7, 4))
    sp = baseline.get("_spectra", {})
    for key, label, c in (("eo", "눈 뜬 휴식 (EO)", "#4c72b0"), ("ec", "눈 감은 휴식 (EC)", "#55a868")):
        if key in sp:
            f, p = sp[key]
            m = (f >= 1) & (f <= 40)
            ax.semilogy(f[m], p[m], label=label, c=c, lw=2)
    ax.axvspan(8, 13, color="#dd8452", alpha=0.15, label="알파 대역 8–13 Hz")
    if "iaf_peak" in baseline:
        ax.axvline(baseline["iaf_peak"], c="#dd8452", ls="--",
                   label=f"IAF {baseline['iaf_peak']:.1f} Hz")
    t = "기준선 스펙트럼 (TP9·TP10 평균)"
    if "alpha_reactivity" in baseline:
        t += f" — 알파 반응성 EC/EO = {baseline['alpha_reactivity']:.2f}"
    ax.set_title(t)
    ax.set_xlabel("주파수 (Hz)")
    ax.set_ylabel("파워 (µV²/Hz, 로그)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def fig_band_timeline(feats: pd.DataFrame, segments: pd.DataFrame, smooth: int = 9):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    _shade_segments(ax, segments)
    good = feats[feats["good"]]
    for b, c in BAND_COLORS.items():
        y = good[f"{b}_rel"].rolling(smooth, center=True, min_periods=1).median() * 100
        ax.plot(good["t_center"], y, c=c, lw=1.6, label=f"{b} 상대파워")
    bad = feats[~feats["good"]]
    ax.scatter(bad["t_center"], np.zeros(len(bad)), marker="|", c="#c44e52", s=30,
               label="버린 창(잡음)")
    ax.set_xlabel("시간 (s)")
    ax.set_ylabel("전체 대비 %")
    ax.set_title("대역별 상대 파워 변화", pad=16)
    ax.legend(ncol=4, fontsize=8, loc="upper right")
    fig.tight_layout()
    return fig


def fig_engagement(tl: pd.DataFrame, sustained: dict, drop_z: float = -1.0):
    fig, ax = plt.subplots(figsize=(11, 3.8))
    if tl.empty or "relative_curve" not in sustained:
        ax.text(0.5, 0.5, "과제 데이터 없음", ha="center", transform=ax.transAxes)
        return fig
    x = tl["time_on_task_min"]
    ax.plot(x, sustained["relative_raw"], c="#cccccc", lw=0.6, label="창별 값")
    ax.plot(x, sustained["relative_curve"], c="#4c72b0", lw=2, label="집중 곡선(평활, 초반 대비 z)")
    ax.axhline(drop_z, c="#c44e52", ls="--", lw=1, label=f"저하 기준 z={drop_z}")
    sm = sustained.get("sustained_min")
    if sm is not None:
        ax.axvline(sm, c="#c44e52", lw=2)
        txt = f"지속 집중 ≥ {sm}분 (끝까지 유지)" if sustained.get("censored") else f"지속 집중 ≈ {sm}분"
        ax.text(sm, ax.get_ylim()[1] * 0.85, " " + txt, color="#c44e52", fontsize=10)
    for (blk, task), g in tl.groupby(["block", "task"]):
        x0 = g["time_on_task_min"].iloc[0]
        ax.axvline(x0, c="#bbbbbb", lw=0.6, ls=":")
        ax.text(x0, 1.0, f" B{int(blk)} {task}", transform=ax.get_xaxis_transform(),
                ha="left", va="bottom", fontsize=7, color="gray")
    ax.set_xlabel("과제 누적 시간 (분)")
    ax.set_ylabel("Engagement z")
    ax.set_title("집중 지표 β/(α+θ) — 지속 집중 시간", pad=16)
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    return fig


def fig_blocks(blocks_eeg: pd.DataFrame, beh: pd.DataFrame):
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    if blocks_eeg.empty:
        return fig
    df = blocks_eeg.merge(beh, on=["task", "block"], how="left") if not beh.empty else blocks_eeg
    df = df.sort_values("block")
    lab = [f"B{int(b)}\n{t}" for b, t in zip(df["block"], df["task"], strict=False)]
    axes[0].bar(lab, df["engagement_z"], color="#4c72b0")
    axes[0].set_title("블록별 집중(z, 휴식 대비)")
    axes[1].bar(lab, df["engagement_slope_per_min"],
                color=["#c44e52" if v < 0 else "#55a868" for v in df["engagement_slope_per_min"]])
    axes[1].set_title("블록 내 집중 변화(분당)")
    if "dprime" in df:
        axes[2].bar(lab, df["dprime"], color="#8172b3")
        axes[2].set_title("수행 d′ (높을수록 정확)")
    for a in axes:
        a.axhline(0, c="gray", lw=0.8)
        a.tick_params(labelsize=7)
    fig.tight_layout()
    return fig


def fig_fatigue(tl: pd.DataFrame, fatigue: dict):
    fig, ax = plt.subplots(figsize=(7, 3.6))
    if tl.empty or "z_log_fatigue" not in tl:
        return fig
    ax.scatter(tl["time_on_task_min"], tl["z_log_fatigue"], s=4, c="#999999", alpha=0.5)
    if "fatigue_slope_per_10min" in fatigue:
        x = np.linspace(0, tl["time_on_task_min"].max(), 50)
        b = np.polyfit(tl["time_on_task_min"], tl["z_log_fatigue"], 1)
        ax.plot(x, np.polyval(b, x), c="#c44e52", lw=2,
                label=f"추세: 10분당 {fatigue['fatigue_slope_per_10min']:+.2f} z")
        ax.legend(fontsize=8)
    extra = ""
    if "ec_alpha_change_pct" in fatigue:
        extra = f" | 사후 눈감기 알파 {fatigue['ec_alpha_change_pct']:+.0f}%, 세타 {fatigue['ec_theta_change_pct']:+.0f}%"
    ax.set_title("피로 지표 (θ+α)/β 추세" + extra, fontsize=10)
    ax.set_xlabel("과제 누적 시간 (분)")
    ax.set_ylabel("Fatigue z")
    fig.tight_layout()
    return fig


def fig_profile_radar(profile: dict):
    """육각형 Brain Profile. 측정 안 된 축은 회색 점선 + '측정 불충분'."""
    axes = list(profile["axes"].values())
    labels = [a["ko"] for a in axes]
    vals = [a["score"] if a["score"] is not None else 0 for a in axes]
    ang = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    fig = plt.figure(figsize=(6.0, 6.6))
    ax = fig.add_axes([0.12, 0.1, 0.76, 0.76], polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.plot(ang + ang[:1], [50] * (len(ang) + 1), c="#999999", lw=1, ls="--")  # 기준 평균
    ax.plot(ang + ang[:1], vals + vals[:1], c="#4c72b0", lw=2)
    ax.fill(ang + ang[:1], vals + vals[:1], c="#4c72b0", alpha=0.25)
    ax.set_xticks(ang)
    ax.set_xticklabels([f"{a['ko']}\n{a['score'] if a['score'] is not None else '측정 불충분'}"
                        for a in axes], fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75])
    ax.tick_params(axis="y", labelsize=7)
    ax.tick_params(axis="x", pad=12)
    t = "Brain Profile"
    if profile.get("composite_behavior") is not None:
        t += f"  ·  종합 수행 {profile['composite_behavior']}"
    ax.set_title(t, pad=28)
    fig.text(0.5, 0.015, profile["disclaimer"] + " · 점선=기준 평균(50)", ha="center",
             fontsize=7, color="gray")
    return fig


def fig_erp(erp: dict):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    if "diff_wave" not in erp:
        ax.text(0.5, 0.5, f"P300 분석 불가: {erp.get('reason', '')}", ha="center",
                transform=ax.transAxes)
        return fig
    t = erp["times"] * 1000
    ax.axvspan(250, 500, color="#f9e6cf", alpha=0.7, label="P300 구간 250–500 ms")
    ax.plot(t, erp["standard_wave"], c="#999999", lw=1.5, label=f"표준 ○ (n={erp['n_standard_clean']})")
    ax.plot(t, erp["target_wave"], c="#dd8452", lw=1.5, label=f"타깃 △ (n={erp['n_target_clean']})")
    ax.plot(t, erp["diff_wave"], c="#c44e52", lw=2.2, label="차이파(타깃−표준)")
    ax.axvline(0, c="k", lw=0.8)
    ax.axhline(0, c="k", lw=0.5)
    ok = "" if erp["valid"] else "  (⚠ 에포크 부족: 참고용)"
    ax.set_title(f"Oddball P300 (TP9·TP10) — {erp['p300_amp_uv']} µV, 피크 {erp['p300_latency_ms']:.0f} ms{ok}",
                 fontsize=10)
    ax.set_xlabel("자극 후 시간 (ms)")
    ax.set_ylabel("µV")
    ax.legend(fontsize=7)
    fig.tight_layout()
    return fig
