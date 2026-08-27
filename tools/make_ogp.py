# -*- coding: utf-8 -*-
"""昼ラボのOGP画像ジェネレータ (1200x630)

使い方:
    python tools/make_ogp.py json "JSON整形・検証" "壊れている場所を行と列で指します。"

第1引数がスラッグで、`docs/ogp/ogp-<スラッグ>.png` に書き出す。
Windows の Yu Gothic / Consolas を使う。フォントが無い環境では FONT_* を差し替えること。

2026-08-19 作成。既存7枚は同じ設計で手作りされていたがスクリプトが残っていなかったので、
以後はこれを使って揃える。
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG_TOP = (32, 34, 41)
BG_BOTTOM = (22, 24, 29)
WHITE = (245, 245, 243)
GRAY = (152, 152, 150)
ACCENT = (245, 166, 35)

FONT_BOLD = r"C:\Windows\Fonts\YuGothB.ttc"
FONT_REG = r"C:\Windows\Fonts\YuGothR.ttc"
FONT_MONO = r"C:\Windows\Fonts\consola.ttf"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "ogp")


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, f, max_w):
    """日本語は単語境界がないので1文字ずつ詰める。

    ★2026-08-27修正: 空白のある語（英語）まで1文字ずつ折っていたので、
    英語版のOGPが `Generato / r` のように**語の途中で改行していた**。
    空白を含む語は空白の手前で折る。日本語は従来どおり1文字ずつ。
    """
    lines, cur = [], ""

    def push(chunk):
        """1つのかたまり（英単語 or 1文字）を積む。入らなければ改行する。"""
        nonlocal cur
        t = cur + chunk
        if draw.textlength(t, font=f) > max_w and cur:
            lines.append(cur)
            cur = chunk.lstrip(" ")
        else:
            cur = t

    word = ""
    for ch in text:
        if ch == "\n":
            if word:
                push(word); word = ""
            lines.append(cur); cur = ""
            continue
        if ch == " ":
            if word:
                push(word + " ")
                word = ""
            elif cur:
                push(" ")
            continue
        if ch.isascii():
            word += ch          # 英数字は語がそろうまで待つ
            continue
        if word:
            push(word); word = ""
        push(ch)                # 日本語は1文字ずつ
    if word:
        push(word)
    if cur:
        lines.append(cur)
    return lines


def draw_flask(d, cx, cy, scale=1.0):
    """フラスコ + 放射線。中心 (cx, cy)。"""
    s = scale
    neck_w, neck_h = 26 * s, 60 * s
    body_h, body_w = 108 * s, 130 * s
    top = cy - (neck_h + body_h) / 2
    lw = max(2, int(6 * s))

    # 首
    d.line([(cx - neck_w / 2, top), (cx - neck_w / 2, top + neck_h)], fill=WHITE, width=lw)
    d.line([(cx + neck_w / 2, top), (cx + neck_w / 2, top + neck_h)], fill=WHITE, width=lw)
    d.line([(cx - neck_w / 2 - 5 * s, top), (cx + neck_w / 2 + 5 * s, top)], fill=WHITE, width=lw)

    # 胴（台形）
    bl = (cx - body_w / 2, top + neck_h + body_h)
    br = (cx + body_w / 2, top + neck_h + body_h)
    tl = (cx - neck_w / 2, top + neck_h)
    tr = (cx + neck_w / 2, top + neck_h)

    # 中身（下から6割）
    fill_top = top + neck_h + body_h * 0.42
    r = (fill_top - tl[1]) / (bl[1] - tl[1])
    fx = neck_w / 2 + (body_w / 2 - neck_w / 2) * r
    d.polygon([(cx - fx, fill_top), (cx + fx, fill_top), br, bl], fill=ACCENT)

    d.line([tl, bl], fill=WHITE, width=lw)
    d.line([tr, br], fill=WHITE, width=lw)
    d.line([bl, br], fill=WHITE, width=lw)

    # 放射線
    import math
    for deg in range(0, 360, 30):
        if 60 <= deg <= 120:      # 下向きは省く
            continue
        a = math.radians(deg - 90)
        r0, r1 = 118 * s, 152 * s
        d.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a) - 6 * s),
                (cx + r1 * math.cos(a), cy + r1 * math.sin(a) - 6 * s)],
               fill=ACCENT, width=max(2, int(4 * s)))


def make(slug, title, subtitle, out=None):
    img = Image.new("RGB", (W, H), BG_BOTTOM)
    d = ImageDraw.Draw(img)

    # 背景: 左上をわずかに明るくする縦グラデーション
    for y in range(H):
        t = y / H
        c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)

    draw_flask(d, 1005, 300, 1.0)

    f_title = font(FONT_BOLD, 76)
    f_sub = font(FONT_REG, 34)
    f_brand = font(FONT_BOLD, 28)
    f_url = font(FONT_MONO, 28)

    x = 88
    max_w = 740
    tl = wrap(d, title, f_title, max_w)
    y = 128
    for line in tl:
        d.text((x, y), line, font=f_title, fill=WHITE)
        y += 92

    y += 14
    for line in wrap(d, subtitle, f_sub, max_w)[:3]:
        d.text((x, y), line, font=f_sub, fill=GRAY)
        y += 46

    d.text((x, 500), "クロードの昼ラボ", font=f_brand, fill=ACCENT)
    d.text((x, 546), "hirulab-dev.github.io/hirulab-tools", font=f_url, fill=GRAY)

    d.rectangle([0, H - 10, W, H], fill=ACCENT)

    out = out or os.path.join(OUT_DIR, "ogp-%s.png" % slug)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, optimize=True)
    print("wrote", out)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    make(sys.argv[1], sys.argv[2], sys.argv[3])
