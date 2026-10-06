"""공개 데이터셋 내려받기. 결과는 data/external/<이름>/ (커밋 금지 폴더).

  python scripts/download_datasets.py --list
  python scripts/download_datasets.py --dataset cogwear        # ZIP 약 179 MB
  python scripts/download_datasets.py --dataset muse_n400      # OSF 프로젝트 전체 ZIP 시도
"""
from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brainfit.datasets import REGISTRY  # noqa: E402

MANUAL = {
    "muse_n400": """OSF 자동 다운로드가 안 되면 수동으로:
  1) 브라우저에서 https://osf.io/u6y9g/ → Files
  2) 'EEG Data' → 'Raw EEG' 에서 .xdf 파일들만 다운로드 (BIDS/.set 은 필요 없음)
  3) data/external/muse_n400/ 에 넣기
  4) python scripts/validate_muse_n400.py --inspect data/external/muse_n400/<아무 파일>.xdf""",
}


def download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "BrainFit/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            got += len(chunk)
            msg = f"{got / 1e6:,.0f} MB" + (f" / {total / 1e6:,.0f} MB" if total else "")
            print(f"\r  {msg}", end="", flush=True)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=list(REGISTRY))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--keep-zip", action="store_true")
    a = ap.parse_args()
    if a.list or not a.dataset:
        for k, d in REGISTRY.items():
            print(f"[{k}] {d['title']}\n   기기: {d['device']}\n   용도: {d['use']}\n"
                  f"   크기: {d['size']} | 라이선스: {d['license']}\n   {d['url']}\n")
        return
    d = REGISTRY[a.dataset]
    local = Path(d["local"])
    zpath = local.with_suffix(".zip")
    print(f"[{a.dataset}] {d['url']}\n  → {local}  ({d['size']})")
    try:
        download(d["zip"], zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(local)
        if not a.keep_zip:
            zpath.unlink()
        print(f"완료: {local}\n인용: {d['cite']}")
    except Exception as e:  # noqa: BLE001
        print(f"자동 다운로드 실패: {e}")
        if zpath.exists():
            zpath.unlink()
        print(MANUAL.get(a.dataset, f"브라우저에서 {d['url']} 를 열어 받은 뒤 {local} 에 풀어 주세요."))
        shutil.rmtree(local, ignore_errors=True) if local.exists() and not any(local.iterdir()) else None


if __name__ == "__main__":
    main()
