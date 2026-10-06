"""matplotlib 한글 폰트 설정 (Windows: 맑은 고딕)."""
import matplotlib.pyplot as plt
from matplotlib import font_manager


def setup_korean_font() -> None:
    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR",
                 "Noto Sans CJK JP"):
        if cand in names:
            plt.rcParams["font.family"] = cand
            break
    plt.rcParams["axes.unicode_minus"] = False
