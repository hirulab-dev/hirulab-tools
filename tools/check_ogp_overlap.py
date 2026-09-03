# -*- coding: utf-8 -*-
"""OGP画像で、題や副題が下のブランド表記に食い込んでいないかを**画素で**調べる。

    python tools/check_ogp_overlap.py            # docs/ogp/ を全部見る
    python tools/check_ogp_overlap.py <フォルダ>  # 別の場所（空振り確認で使う）

`make_ogp.py` は題を y=128 から下へ流し、ブランド表記を y=500 に決め打ちで置く。
題が長いと下へ伸びて詰まるが、**書き出したあとの画像を見ないと分からない**
（2026-08-28、`Password Generator & Strength Check` で実際に起きた）。
生成側にも収まるまで縮める処理を入れたが、**すでに出来ている画像はそれでは直らない**ので、
現物を見るこの検査を別に置く。

★ 測るのは「重なり」ではなく**すき間**。実際に起きた形は、行が重なるのではなく
本文の最下行がブランド表記の真上まで降りてきて、すき間が数画素になる、というものだった。
重なりだけを見る検査だと**これを一度も捕まえられない**（最初にそう書いて空振りした）。
"""
import os, sys, importlib.util
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

# ⚠ 2026-09-04: ここは `os.path.join(os.path.dirname(HERE), "docs", "ogp")` と
#    **自分のファイル位置から**組み立てていたので、原本のある `lab/assets/` から回すと
#    存在しない `lab/docs/ogp` を見て FileNotFoundError で落ちていた。
#    **9/3 夕に `regen_ogp.py` で直したのと同じ傷が、同じフォルダの3本目に残っていた**
#    (あのとき直したのは `make_ogp.OUT_DIR` で、この道具は make_ogp を import して
#     いなかったので直しが届かなかった = **名指しされたファイルだけを直した**形)。
#    → 場所は `make_ogp` の1か所から引く。判定の定数(BRAND_Y など)は
#      **わざと写したまま**にしてある(検査と検査される側が同じ定数を読むと空振りするため)。
_spec = importlib.util.spec_from_file_location("make_ogp_for_overlap",
                                               os.path.join(HERE, "make_ogp.py"))
_mk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mk)

OGP_DIR = sys.argv[1] if len(sys.argv) > 1 else _mk.OUT_DIR

BRAND_Y = 500                 # make_ogp.py と同じ
LEFT, RIGHT = 88, 830         # 本文が入る帯（フラスコの手前まで）
TEXT_COLORS = [(245, 245, 243), (152, 152, 150)]   # 題(白) / 副題(グレー)
TOL = 26                      # アンチエイリアスぶんの許容
MIN_GAP = 12                  # 本文の最下端とブランド表記の上端のすき間の下限


def near(px, c):
    return all(abs(px[i] - c[i]) <= TOL for i in range(3))


def lowest_text_row(im):
    """ブランド表記より上にある本文（白・グレー）の、いちばん下の行。無ければ None。"""
    px = im.load()
    for y in range(BRAND_Y - 1, 100, -1):
        n = 0
        for x in range(LEFT, RIGHT):
            if any(near(px[x, y], c) for c in TEXT_COLORS):
                n += 1
                if n >= 3:     # 1〜2画素は背景のゆらぎを拾うことがある
                    return y
    return None


def main():
    names = sorted(n for n in os.listdir(OGP_DIR) if n.endswith(".png"))
    bad = worst = 0
    worst_name = ""
    for n in names:
        im = Image.open(os.path.join(OGP_DIR, n)).convert("RGB")
        y = lowest_text_row(im)
        gap = BRAND_Y - y if y is not None else 999
        if not worst_name or gap < worst:
            worst, worst_name = gap, n
        if gap < MIN_GAP:
            print("  詰まり  %-26s すき間 %d px（下限 %d）" % (n, gap, MIN_GAP))
            bad += 1
    print()
    print("見た画像: %d / 詰まっているもの: %d（いちばん狭いのは %s の %d px）"
          % (len(names), bad, worst_name, worst))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
