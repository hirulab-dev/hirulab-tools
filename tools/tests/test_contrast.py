#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「コントラスト比チェッカー」の検証(2026-09-01 朝 新設)。

3本目の道具(2026-08-15 公開)なのに検証スクリプトが1本も無かった。
page-contrast(8/31未明)・diff(8/31朝)・json(8/31昼)・unit(8/31夜)・
char-counter(9/1未明)に続いて、**古い道具ほど検証が薄い**穴を後ろから埋める6本目。

⚠ 紛らわしいので先に: `check_contrast.py` は**自分のサイトが AA を満たすか**を測る道具で、
   `test_page_contrast.py` は**ブックマークレット版**の検証。
   このスクリプトが見るのは **`docs/contrast/`(色を2つ入れて比を出すページ)そのもの**。

★参照の出どころを分ける(1つの参照だけだと、同じ勘違いを2回するので):

  (1) **WCAG 2.1 の比 = 第三者の `wcag-contrast-ratio` と `coloraide`(2つ)**
      + 規格の定義から Python で独立に書き下したもの。**3つの出どころが一致すること**を
      先に確かめてから、それを道具に当てる。
      ★ここで1つ、規格の版のずれを数で片付けている: 規格の本文は分岐のしきいを
        **0.03928**、sRGB の定義と道具は **0.04045** と書いている。
        **8bit の 256 値では、この2つで分岐が変わる値が1つも無い**ことを全数で示す
        (c/255 が 0.03928 と 0.04045 の間に入る整数が無い)。だから差は出ようがない。

  (2) **色の読み取りはブラウザの CSS パーサ**(`style.color` に入れて `getComputedStyle`)。
      道具を通さない独立の経路。**食い違う形はあらかじめ表にしてあり、表に無い食い違いが
      1件でも出たら落ちる**(道具はわざと厳しく作ってあるところがある)。

  (3) **APCA(WCAG 3.0 ドラフト)は公開されている定数から Python で独立に書き下したもの**。
      ⚠ 第三者実装ではない(Python に APCA の実装が見当たらない)。同じ式を2つの言語で
      書いて突き合わせているだけ、と正直に断っておく。
      代わりに**式の性質**を別に測る: 明るさの差が deltaYmin(0.0005)より小さい組では
      道具が必ず 0 を返すか(道具はこの早期打ち切りを持っていないので、
      **下限クリップだけで同じ結果になっている**ことを確かめる意味がある)。

  (4) **色覚特性シミュレーションは第三者の `daltonlens`(Viénot 1999)**。
      ★ただし **daltonlens と道具は LMS の取り方が違う**(道具は白が (1,1,1) に乗る
      正規化版、daltonlens は Smith-Pokorny 系)。**同じ色にはならない**ので、
      許容つきでしか使えない(pint のときと同じ扱い)。実測の最大差を毎回出して、
      **増えていないこと**を見る。
      これだけだと弱いので、**正確に成り立つはずの性質を別に測る**:
        - 無彩色(グレー)は動かない
        - 2回かけても1回と同じ(射影である)
        - 1型・2型では出力の赤と緑が等しく、3型では緑と青が等しい
          (Viénot 1999 の縮退の性質。daltonlens 側でも成り立つことを確認ずみ)

  (5) **修正案の「明度だけ動かす」は Python 標準の `colorsys`**(別実装の HSL)。
      道具が返した色が本当にいちばん近いか(同じ 1/100 刻みで、より小さい変化では
      届かないか)を独立に探し直す。

  (6) **画面に出た文字列から数に戻す**(比・Lc・シミュレーションの比・修正案の比)。
      ★**表示は丸めるが判定は丸めてはいけない**。4.4996 は「4.50」と表示されるが
      AA は FAIL でなければならない。**しきいをまたぐ丸めの見本を先に探して**入れてある。

`--sabotage` でわざと傷を入れて、上の検査が本当に落ちるかを見る(空振り確認)。

    python lab/scripts/test_contrast.py [--n 300] [--sabotage] [--docs <docs>]
    python lab/scripts/test_contrast.py --page docs/en/contrast.html
"""
import argparse
import colorsys
import math
import pathlib
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from skipwatch import SkipWatch  # noqa: E402

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")
RGB_TXT = re.compile(r"rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)")
HEX6 = re.compile(r"#[0-9a-f]{6}")
NUM = re.compile(r"(-?\d+\.\d+)")


# ---------------------------------------------------------------- 参照(1)
SPEC_THRESHOLD = 0.03928       # WCAG 2.1 の本文に書いてある値
SRGB_THRESHOLD = 0.04045       # sRGB の定義(道具はこちら)


def _lin(c, thr=SPEC_THRESHOLD):
    s = c / 255.0
    return s / 12.92 if s <= thr else ((s + 0.055) / 1.055) ** 2.4


# WCAG 2.1 の本文に**丸めて**書いてある係数(道具はこちら)と、sRGB の厳密な行列の Y の行。
WCAG_COEF = (0.2126, 0.7152, 0.0722)
SRGB_COEF = (0.2126390058715103, 0.7151686787677559, 0.0721923153607337)


def luminance(rgb, thr=SPEC_THRESHOLD, coef=WCAG_COEF):
    r, g, b = (_lin(v, thr) for v in rgb)
    return coef[0] * r + coef[1] * g + coef[2] * b


def ratio(fg, bg, thr=SPEC_THRESHOLD, coef=WCAG_COEF):
    a, b = luminance(fg, thr, coef), luminance(bg, thr, coef)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def ratio_exact(fg, bg):
    return ratio(fg, bg, coef=SRGB_COEF)


# ★規格の丸めた係数と sRGB の厳密な係数で **AA の判定が割れる**色の組(2026-09-01 に探して見つけた)。
#   道具は規格の本文どおりなので「通す」側、coloraide のように XYZ を経由する実装は「落とす」側。
#   どちらかが間違いという話ではなく、**規格が係数を4桁に丸めているから起きる**。
COEF_FLIP = [
    ((147, 2, 44), (213, 179, 18), 4.5),      # 丸め 4.500229 / 厳密 4.499892
    ((108, 0, 159), (22, 194, 204), 4.5),     # 丸め 4.500254 / 厳密 4.499921
    ((235, 12, 24), (133, 226, 209), 3.0),    # 丸め 3.000414 / 厳密 2.999909
    ((33, 72, 192), (160, 164, 152), 3.0),    # 丸め 2.999999 / 厳密 3.000117(向きが逆の例)
]


def threshold_is_moot():
    """8bit の 256 値で、2つのしきいが違う枝を選ぶものがあるか(答: 無い)。"""
    return [c for c in range(256)
            if (c / 255.0 <= SPEC_THRESHOLD) != (c / 255.0 <= SRGB_THRESHOLD)]


def cross_check_references(pairs):
    """参照どうしを先に突き合わせる。ここが割れていたら道具を測る資格が無い。"""
    import wcag_contrast_ratio as wcr
    from coloraide.everything import ColorAll as Color

    bad, worst = [], 0.0
    for fg, bg in pairs:
        mine = ratio(fg, bg)
        third = wcr.rgb(tuple(v / 255 for v in fg), tuple(v / 255 for v in bg))
        # ⚠ coloraide は **sRGB の厳密な行列**で輝度を取る(規格が4桁に丸めた係数ではない)。
        #   だから規格どおりの値とは 1e-4 くらい違う。厳密な係数で書いた側と突き合わせる。
        ca = Color("srgb", [v / 255 for v in fg]).contrast(
            Color("srgb", [v / 255 for v in bg]), method="wcag21")
        exact = ratio_exact(fg, bg)
        worst = max(worst, abs(mine - exact) / mine)
        if abs(mine - third) > 1e-12 or abs(exact - ca) / ca > 1e-12:
            bad.append((fg, bg, mine, third, ca, exact))
    return bad, worst


# ---------------------------------------------------------------- 参照(3)
# APCA-W3(0.1.9)の公開されている定数。
A_MAIN_TRC = 2.4
A_R, A_G, A_B = 0.2126729, 0.7151522, 0.0721750
A_NORM_BG, A_NORM_TXT = 0.56, 0.57
A_REV_TXT, A_REV_BG = 0.62, 0.65
A_BLK_THRS, A_BLK_CLMP = 0.022, 1.414
A_SCALE, A_OFFSET, A_LO_CLIP = 1.14, 0.027, 0.1
A_DELTA_Y_MIN = 0.0005


def apca_y(rgb):
    return (A_R * (rgb[0] / 255) ** A_MAIN_TRC
            + A_G * (rgb[1] / 255) ** A_MAIN_TRC
            + A_B * (rgb[2] / 255) ** A_MAIN_TRC)


def apca_clamp(y):
    return y if y > A_BLK_THRS else y + (A_BLK_THRS - y) ** A_BLK_CLMP


def apca(fg, bg):
    ytxt, ybg = apca_clamp(apca_y(fg)), apca_clamp(apca_y(bg))
    if ybg > ytxt:
        s = (ybg ** A_NORM_BG - ytxt ** A_NORM_TXT) * A_SCALE
        c = 0.0 if s < A_LO_CLIP else s - A_OFFSET
    else:
        s = (ybg ** A_REV_BG - ytxt ** A_REV_TXT) * A_SCALE
        c = 0.0 if s > -A_LO_CLIP else s + A_OFFSET
    return c * 100


# ---------------------------------------------------------------- 参照(4)
def dalton(rgb, kind):
    """第三者(daltonlens)の Viénot 1999。★道具とは LMS の取り方が違うので許容つき。"""
    import numpy as np
    from daltonlens import simulate as dl
    key = {"protanopia": dl.Deficiency.PROTAN, "deuteranopia": dl.Deficiency.DEUTAN,
           "tritanopia": dl.Deficiency.TRITAN}[kind]
    img = np.array([[list(rgb)]], dtype=np.uint8)
    out = _DL_SIM.simulate_cvd(img, key, severity=1.0)
    return [int(v) for v in out[0][0]]


_DL_SIM = None


def dalton_ready():
    global _DL_SIM
    if _DL_SIM is None:
        from daltonlens import simulate as dl
        _DL_SIM = dl.Simulator_Vienot1999()
    return _DL_SIM


# ---------------------------------------------------------------- 参照(5)
def nudge_reference(target, fixed, goal=4.5):
    """明度だけ 1/100 刻みで動かして目標に届く最も近い色(Python 標準の colorsys で)。"""
    h, l0, s = colorsys.rgb_to_hls(*(v / 255 for v in target))
    best = None
    for d in (-1, 1):
        for step in range(1, 101):
            l = l0 + d * step / 100
            if l < 0 or l > 1:
                break
            cand = tuple(math.floor(v * 255 + 0.5) for v in colorsys.hls_to_rgb(h, l, s))
            if ratio(cand, fixed) >= goal:
                dist = abs(l - l0)
                if best is None or dist < best[0]:
                    best = (dist, cand)
                break
    return best[1] if best else None


def lightness(rgb):
    return colorsys.rgb_to_hls(*(v / 255 for v in rgb))[1]


def fixes_reference(fg, bg):
    """道具が出すべき修正案の一覧(名前は言語で変わるので、種類と色と比だけ)。"""
    if ratio(fg, bg) >= 4.5:
        return None                       # 「すでに満たしています」の側
    cands = []
    nf = nudge_reference(fg, bg)
    if nf:
        cands.append(("fg", tuple(nf), tuple(bg)))
    nb = nudge_reference(bg, fg)
    if nb:
        cands.append(("bg", tuple(fg), tuple(nb)))
    bw = (0, 0, 0) if ratio((0, 0, 0), bg) >= ratio((255, 255, 255), bg) else (255, 255, 255)
    cands.append(("bw", bw, tuple(bg)))
    return [c for c in cands if ratio(c[1], c[2]) >= 4.5]


# ---------------------------------------------------------------- 見本
SITE_COLORS = ["#f7f7f5", "#ffffff", "#1a1a1a", "#666666", "#2563eb", "#116b30",
               "#9a5208", "#b3261e", "#16181d", "#1f2229", "#e8e8e6", "#9a9a97",
               "#60a5fa", "#17181c", "#33363e", "#4ade80", "#fbbf24", "#f87171",
               "#8f5c0e", "#c47f16", "#767676", "#000000"]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join("%02x" % max(0, min(255, int(v))) for v in rgb)


def boundary_pairs():
    """★しきいをまたぐ丸めの見本。
    表示は小数2桁に丸めるので 4.4996 は「4.50」と出るが、AA は FAIL でなければならない。
    グレー同士を全数(256×256)で走査して、しきいの ±0.005 に入る組を拾う。"""
    lum = [luminance((v, v, v)) for v in range(256)]
    out = []
    for t in (3.0, 4.5, 7.0):
        below, above = [], []
        for a in range(256):
            for b in range(256):
                if a == b:
                    continue
                hi, lo = max(lum[a], lum[b]), min(lum[a], lum[b])
                r = (hi + 0.05) / (lo + 0.05)
                if t - 0.005 <= r < t:
                    below.append(((a, a, a), (b, b, b)))
                elif t <= r < t + 0.005:
                    above.append(((a, a, a), (b, b, b)))
        out += below[:3] + above[:3]
    return out


def build_cases(n, rnd):
    cases = []
    for a in SITE_COLORS:
        for b in ("#ffffff", "#16181d"):
            cases.append((hex_to_rgb(a), hex_to_rgb(b)))
    cases += [((0, 0, 0), (0, 0, 0)), ((255, 255, 255), (255, 255, 255)),
              ((255, 0, 0), (0, 255, 0)), ((0, 0, 255), (255, 255, 0)),
              ((1, 1, 1), (0, 0, 0)), ((10, 10, 10), (11, 11, 11)),
              ((0, 0, 0), (255, 255, 255)), ((255, 255, 255), (0, 0, 0))]
    cases += boundary_pairs()
    cases += [(f, b) for f, b, _ in COEF_FLIP]
    fixed = len(cases)
    while len(cases) < n:
        cases.append((tuple(rnd.randrange(256) for _ in range(3)),
                      tuple(rnd.randrange(256) for _ in range(3))))
    return cases[:max(n, fixed)], fixed


# 参照(2) 色の読み取り。★道具がわざとブラウザと違う形は、ここに理由つきで並べる。
#   道具は「入れた文字列が色として通るか」を利用者に見せる道具なので、
#   はみ出した値・見慣れない書き方は**黙って直さずに拒む**側に倒してある。
KNOWN_PARSE_DIFFS = {
    "abc": "# を省いた6桁・3桁を受ける(ブラウザは受けない)。入力の手間を減らすためのおまけ",
    "123456": "# を省いた6桁を受ける",
    "crimson": "名前つきの色は13個だけ(ブラウザは148個)",
    "rebeccapurple": "名前つきの色は13個だけ",
    "transparent": "透明は扱わない",
    "currentcolor": "文脈依存の値は扱わない",
    "hsl(120, 50%, 50%)": "HSL 記法は入力として受けない(修正案の内部では使う)",
    "hsl(120 50% 50%)": "HSL 記法は入力として受けない",
    "rgb(300, 0, 0)": "255 を超える値は丸めずに拒む",
    "rgb(-5, 0, 0)": "負の値は丸めずに拒む",
    "rgb(200%, 0%, 0%)": "100% を超える値は丸めずに拒む",
    "#abcd": "4桁・8桁(アルファつき)は扱わない",
    "#abcdef12": "4桁・8桁(アルファつき)は扱わない",
    "color(srgb 1 0 0)": "color() 記法は扱わない",
}

PARSE_CASES = [
    "#000000", "#ffffff", "#FFF", "#abc", "abc", "123456", "#123456",
    "rgb(0,0,0)", "rgb(255, 255, 255)", "rgb(1, 2, 3)", "rgba(1,2,3,0.5)",
    "rgb(50%, 50%, 50%)", "rgb(0%, 100%, 0%)", "rgb(255 0 0)", "rgb(255 0 0 / 50%)",
    "  #ABCDEF  ", "black", "white", "red", "blue", "green", "gray", "grey",
    "silver", "navy", "teal", "orange", "purple", "yellow",
    "rgb(1.5, 2.4, 3.6)", "rgb(1e2, 0, 0)",
    "crimson", "rebeccapurple", "transparent", "currentcolor",
    "hsl(120, 50%, 50%)", "hsl(120 50% 50%)",
    "rgb(300, 0, 0)", "rgb(-5, 0, 0)", "rgb(200%, 0%, 0%)",
    "#abcd", "#abcdef12", "color(srgb 1 0 0)",
    "", "   ", "notacolor", "#12345", "rgb(1,2)", "rgb(a,b,c)", "#gggggg",
]


# ---------------------------------------------------------------- 画面を読む
VIA_UI = """(o) => {
  const fgT = document.getElementById('fg-text'), bgT = document.getElementById('bg-text');
  fgT.value = o.fg; fgT.dispatchEvent(new Event('input'));
  bgT.value = o.bg; bgT.dispatchEvent(new Event('input'));
  const t = id => document.getElementById(id).textContent;
  const pv = document.getElementById('preview');
  return {
    ratio: t('ratio'),
    pills: [t('p-aa-n'), t('p-aaa-n'), t('p-aa-l'), t('p-aaa-l'), t('p-ui'), t('p-apca')],
    lc: t('apca-val'),
    pvFg: pv.style.color, pvBg: pv.style.background,
    sims: Array.from(document.querySelectorAll('#sims .sim')).map(el => ({
      val: el.querySelector('.val').textContent,
      fg: el.querySelector('.swatch').style.color,
      bg: el.querySelector('.swatch').style.background})),
    fixes: Array.from(document.querySelectorAll('#fixes .fix')).map(el => ({
      fg: el.dataset.fg, bg: el.dataset.bg,
      val: el.querySelector('.val').textContent})),
    empty: document.querySelector('#fixes .empty')
             ? document.querySelector('#fixes .empty').textContent : null,
    bad: [fgT.classList.contains('bad'), bgT.classList.contains('bad')]
  };
}"""

CALL_RATIO = "(a) => a.map(([f, b]) => contrast(f, b))"
CALL_APCA = "(a) => a.map(([f, b]) => apca(f, b))"
CALL_SIM = "(a) => a.map(([c, k]) => simulate(c, k))"
CALL_PARSE = "(a) => a.map(s => parseColor(s))"
# ★ブラウザが受け付けたかは「代入したあと style.color が空のままか」で見る。
#   CSSOM は読めない値を黙って捨てるので、空なら拒まれたということ。
#   (前の版はセンチネルの色を先に入れていたが、見本に同じ色があると誤判定になった)
CALL_CSS = """(a) => a.map(s => {
  const d = document.createElement('div');
  d.style.color = '';
  try { d.style.color = s; } catch (e) {}
  if (d.style.color === '') return null;
  document.body.appendChild(d);
  const c = getComputedStyle(d).color;
  d.remove();
  return c;
})"""


def rgb_of(text):
    m = RGB_TXT.search(text or "")
    return tuple(int(m.group(i)) for i in (1, 2, 3)) if m else None


def val_numbers(text):
    """`比 4.54:1 / #aabbcc on #ddeeff` から 比と2色を取り出す(文言に依存しない)。"""
    m = re.search(r"(\d+\.\d\d)\s*:\s*1", text or "")
    hexes = HEX6.findall(text or "")
    return (float(m.group(1)) if m else None), hexes


def fmt2(x):
    """JS の toFixed(2)。Python の round は偶数丸めなので使わない。"""
    return "%.2f" % (math.floor(abs(x) * 100 + 0.5) / 100 * (1 if x >= 0 else -1))


def fmt1(x):
    return "%.1f" % (math.floor(abs(x) * 10 + 0.5) / 10 * (1 if x >= 0 else -1))


# ---------------------------------------------------------------- 検査本体
SIM_KINDS = ["normal", "protanopia", "deuteranopia", "tritanopia"]


def check_all(page, cases, lang, tol):
    fails = []
    n = dict(ratio=0, display=0, pills=0, apca=0, apca_disp=0, sims=0, sim_disp=0,
             fixes=0, preview=0, parse=0, sim_third=0, invariant=0)
    skipped = dict(fixes_edge=0)
    maxdiff = 0

    # --- (1) 比: 道具の contrast() vs Python の参照 ------------------------
    got = page.evaluate(CALL_RATIO, [[list(f), list(b)] for f, b in cases])
    for (f, b), g in zip(cases, got):
        want = ratio(f, b)
        if abs(g - want) > 1e-9:
            fails.append("比が違う %s on %s: 道具 %.6f / 参照 %.6f" % (to_hex(f), to_hex(b), g, want))
        else:
            n["ratio"] += 1

    # --- (3) APCA: 道具の apca() vs Python の参照 --------------------------
    got = page.evaluate(CALL_APCA, [[list(f), list(b)] for f, b in cases])
    tiny_bad = []
    for (f, b), g in zip(cases, got):
        want = apca(f, b)
        if abs(g - want) > 1e-9:
            fails.append("APCA が違う %s on %s: 道具 %.4f / 参照 %.4f" % (to_hex(f), to_hex(b), g, want))
            continue
        n["apca"] += 1
        # 道具は deltaYmin の早期打ち切りを持たない。下限クリップだけで 0 になるはず。
        if abs(apca_clamp(apca_y(b)) - apca_clamp(apca_y(f))) < A_DELTA_Y_MIN and g != 0.0:
            tiny_bad.append((to_hex(f), to_hex(b), g))
    if tiny_bad:
        fails.append("明るさの差が deltaYmin 未満なのに Lc が 0 でない: %d 件 %s"
                     % (len(tiny_bad), tiny_bad[:3]))

    # --- (4) 色覚特性: 第三者(許容つき)+ 正確に成り立つ性質 ----------------
    dalton_ready()
    sim_in = []
    for f, b in cases[:120]:
        for kind in SIM_KINDS:
            sim_in.append([list(f), kind])
            sim_in.append([list(b), kind])
    got = page.evaluate(CALL_SIM, sim_in)
    for (rgb, kind), out in zip([(tuple(c), k) for c, k in sim_in], got):
        out = tuple(out)
        if kind == "normal":
            if out != tuple(rgb):
                fails.append("normal なのに色が変わった %s → %s" % (to_hex(rgb), to_hex(out)))
                continue
            n["sims"] += 1
            continue
        # 性質1: 無彩色は動かない
        if rgb[0] == rgb[1] == rgb[2] and out != tuple(rgb):
            fails.append("グレーが動いた(%s) %s → %s" % (kind, to_hex(rgb), to_hex(out)))
            continue
        # 性質2: 縮退の形(1型・2型は赤=緑 / 3型は緑=青)
        if kind in ("protanopia", "deuteranopia"):
            ok = abs(out[0] - out[1]) <= 1
        else:
            ok = abs(out[1] - out[2]) <= 1
        if not ok:
            fails.append("縮退していない(%s) %s → %s" % (kind, to_hex(rgb), to_hex(out)))
            continue
        n["invariant"] += 1
        # 第三者(daltonlens)との差(許容つき。最大差を出す)
        d = dalton(rgb, kind)
        diff = max(abs(a - b2) for a, b2 in zip(out, d))
        maxdiff = max(maxdiff, diff)
        if diff <= tol:
            n["sim_third"] += 1
        else:
            fails.append("daltonlens との差が許容(%d)を超えた(%s) %s: 道具 %s / 第三者 %s (差 %d)"
                         % (tol, kind, to_hex(rgb), to_hex(out), to_hex(d), diff))
        n["sims"] += 1

    # 性質3: 2回かけても1回と同じ(射影)
    twice_in, once_out = [], []
    for f, b in cases[:60]:
        for rgb in (f, b):
            for kind in SIM_KINDS[1:]:
                once_out.append((rgb, kind))
    first = page.evaluate(CALL_SIM, [[list(r), k] for r, k in once_out])
    second = page.evaluate(CALL_SIM, [[list(v), k] for v, (_, k) in zip(first, once_out)])
    for (rgb, kind), a, b2 in zip(once_out, first, second):
        if max(abs(x - y) for x, y in zip(a, b2)) > 1:
            fails.append("2回かけると変わる(%s) %s: 1回 %s / 2回 %s"
                         % (kind, to_hex(rgb), to_hex(a), to_hex(b2)))
        else:
            n["invariant"] += 1

    # --- (2) 色の読み取り: ブラウザの CSS パーサと突き合わせる -------------
    tool = page.evaluate(CALL_PARSE, PARSE_CASES)
    css = page.evaluate(CALL_CSS, PARSE_CASES)
    def same_as_browser(t, c):
        """★「どちらも受け付けなかった」も一致とみなす。
        ⚠ ブラウザが受け付けても rgb() の形で返さない書き方(`color(srgb …)`)があるので、
        受理したかどうかは**値ではなく c が None かどうか**で見る。"""
        if (t is None) != (c is None):
            return False
        return t is None or tuple(t) == rgb_of(c)

    for s, t, c in zip(PARSE_CASES, tool, css):
        if same_as_browser(t, c):
            n["parse"] += 1
        elif s in KNOWN_PARSE_DIFFS:
            n["parse"] += 1
        else:
            fails.append("色の読み取りがブラウザと違う(表に無い形) %r: 道具 %s / ブラウザ %r"
                         % (s, tuple(t) if t else None, c))
    # 表に載せた形が本当に食い違っているか(直したのに表に残っている、を防ぐ)
    for s in KNOWN_PARSE_DIFFS:
        i = PARSE_CASES.index(s)
        if same_as_browser(tool[i], css[i]):
            fails.append("食い違いの表に載っているのに一致している(表から消すこと): %r" % s)

    # --- (6) 画面 -----------------------------------------------------------
    for i, (f, b) in enumerate(cases):
        got = page.evaluate(VIA_UI, {"fg": to_hex(f), "bg": to_hex(b)})
        r = ratio(f, b)

        if got["ratio"] != fmt2(r):
            fails.append("#%d 表示の比が違う %s on %s: 画面 %r / 参照 %r"
                         % (i, to_hex(f), to_hex(b), got["ratio"], fmt2(r)))
            continue
        n["display"] += 1

        # ★丸めた値ではなく本当の値で判定しているか
        want_pills = ["PASS" if ok else "FAIL" for ok in
                      (r >= 4.5, r >= 7, r >= 3, r >= 4.5, r >= 3,
                       abs(apca(f, b)) >= 60)]
        if got["pills"] != want_pills:
            fails.append("#%d 判定が違う %s on %s (比 %.6f): 画面 %s / 参照 %s"
                         % (i, to_hex(f), to_hex(b), r, got["pills"], want_pills))
            continue
        n["pills"] += 1

        want_lc = fmt1(apca(f, b))
        if NUM.search(got["lc"] or "") is None or NUM.search(got["lc"]).group(1) != want_lc:
            fails.append("#%d Lc の表示が違う: 画面 %r / 参照 %r" % (i, got["lc"], want_lc))
            continue
        n["apca_disp"] += 1

        if rgb_of(got["pvFg"]) != f or rgb_of(got["pvBg"]) != b:
            fails.append("#%d 見本の色が違う: 画面 %s/%s" % (i, got["pvFg"], got["pvBg"]))
            continue
        n["preview"] += 1

        # シミュレーションの表示(比の値が、表示している2色から計算した値と合うか)
        bad = None
        if len(got["sims"]) != 4:
            bad = "枠が %d 個" % len(got["sims"])
        for s in got["sims"]:
            v, hexes = val_numbers(s["val"])
            sf, sb = rgb_of(s["fg"]), rgb_of(s["bg"])
            if v is None or len(hexes) != 2:
                bad = "読めない: %r" % s["val"]
            elif (hex_to_rgb(hexes[0]), hex_to_rgb(hexes[1])) != (sf, sb):
                bad = "文字の色と枠の色が違う: %r vs %s/%s" % (s["val"], sf, sb)
            elif fmt2(ratio(sf, sb)) != "%.2f" % v:
                bad = "比が違う: 画面 %.2f / 参照 %s" % (v, fmt2(ratio(sf, sb)))
        if bad:
            fails.append("#%d シミュレーションの表示 %s" % (i, bad))
            continue
        n["sim_disp"] += 1

        # 修正案
        want_fixes = fixes_reference(f, b)
        if want_fixes is None:
            if got["fixes"] or not got["empty"]:
                fails.append("#%d AA を満たしているのに修正案が出ている(%d件)"
                             % (i, len(got["fixes"])))
                continue
        else:
            bad = None
            for c in got["fixes"]:
                cf, cb = hex_to_rgb(c["fg"]), hex_to_rgb(c["bg"])
                v, hexes = val_numbers(c["val"])
                if ratio(cf, cb) < 4.5:
                    bad = "AA に届かない案が出ている: %s on %s = %.3f" % (c["fg"], c["bg"], ratio(cf, cb))
                elif v is None or fmt2(ratio(cf, cb)) != "%.2f" % v:
                    bad = "案の比の表示が違う: %r" % c["val"]
                elif [h for h in hexes[:2]] != [c["fg"], c["bg"]]:
                    bad = "案の色と表示が違う: %r vs %s/%s" % (c["val"], c["fg"], c["bg"])
            if bad is None and len(got["fixes"]) != len(want_fixes):
                bad = "案の数が違う: 画面 %d / 参照 %d" % (len(got["fixes"]), len(want_fixes))
            elif bad is None:
                for c, (kind, wf, wb) in zip(got["fixes"], want_fixes):
                    cf, cb = hex_to_rgb(c["fg"]), hex_to_rgb(c["bg"])
                    if kind == "bw":
                        # 白か黒かは離散の選択なので完全一致で見る
                        if (cf, cb) != (wf, wb):
                            bad = "白/黒の案が違う: %s on %s / 参照 %s on %s" % (
                                c["fg"], c["bg"], to_hex(wf), to_hex(wb))
                        else:
                            other = (255, 255, 255) if cf == (0, 0, 0) else (0, 0, 0)
                            if ratio(cf, cb) < ratio(other, cb) - 1e-12:
                                bad = "白/黒の選び方が逆(%s より %s のほうが比が大きい)" % (
                                    c["fg"], to_hex(other))
                        continue
                    # ★明度を動かす案は、**同じ 1/100 刻みでも1段ずれることがある**。
                    #   HSL の往復で 1/255 だけ丸めが割れ、その1段がちょうど 4.5 をまたぐため
                    #   (実測: #b3261e on #16181d の 75段目 で 4.4956 と 4.5364 に割れた)。
                    #   なので**色の一致ではなく、動かした量が参照より1段より多く増えていないか**で見る。
                    moved, ref_moved = (cf, wf) if kind == "fg" else (cb, wb)
                    other_side = cb if kind == "fg" else cf
                    want_other = wb if kind == "fg" else wf
                    if other_side != want_other:
                        bad = "動かしてはいけないほうの色が動いた: %s on %s" % (c["fg"], c["bg"])
                    elif abs(lightness(moved) - lightness(
                            f if kind == "fg" else b)) > abs(
                            lightness(ref_moved) - lightness(f if kind == "fg" else b)) + 0.0101:
                        bad = ("明度を動かしすぎ(%s): 道具 %s(Δ%.4f) / 参照 %s(Δ%.4f)" % (
                            kind, to_hex(moved),
                            abs(lightness(moved) - lightness(f if kind == "fg" else b)),
                            to_hex(ref_moved),
                            abs(lightness(ref_moved) - lightness(f if kind == "fg" else b))))
                    else:
                        skipped["fixes_edge"] += 1 if moved != ref_moved else 0
            if bad:
                fails.append("#%d 修正案 %s (%s on %s)" % (i, bad, to_hex(f), to_hex(b)))
                continue
        n["fixes"] += 1

    # --- 英語版に日本語が残っていないか ------------------------------------
    if lang == "en":
        got = page.evaluate(VIA_UI, {"fg": "#777777", "bg": "#ffffff"})
        texts = [got["ratio"], got["lc"], got["empty"] or ""]
        texts += [s["val"] for s in got["sims"]] + [c["val"] for c in got["fixes"]]
        left = JA_CHARS.findall("".join(texts))
        if left:
            fails.append("英語版の画面に日本語が %d 文字: %s" % (len(left), left[:8]))
    return n, fails, skipped, maxdiff


# ---------------------------------------------------------------- 空振り確認
SABOTAGE = {
    # 1. 相対輝度の分岐のしきいを大きく外す
    "trc": lambda s: s.replace("s <= 0.04045 ? s/12.92", "s <= 0.4 ? s/12.92"),
    # 2. 輝度の係数を1つずらす
    "coef": lambda s: s.replace("0.2126*r + 0.7152*g", "0.2126*r + 0.7052*g"),
    # 3. ★判定を「表示に使う丸めた値」でやる(しきいをまたぐ見本でしか出ない)
    "round": lambda s: s.replace("setPill($(\"p-aa-n\"),  ratio >= 4.5);",
                                 "setPill($(\"p-aa-n\"),  Math.round(ratio*100)/100 >= 4.5);"),
    # 4. APCA の暗い側のなだらかな押し上げを外す
    "apcaclamp": lambda s: s.replace(
        "const clamp = y => y > 0.022 ? y : y + Math.pow(0.022 - y, 1.414);",
        "const clamp = y => y;"),
    # 5. APCA の下限オフセットを外す
    "apcaoffset": lambda s: s.replace("C = C < 0.1 ? 0 : C - 0.027;", "C = C < 0.1 ? 0 : C;"),
    # 6. 3桁の色の展開を間違える(#abc → #a0b0c0)
    "hex3": lambda s: s.replace("parseInt(h[0]+h[0],16)", 'parseInt(h[0]+"0",16)'),
    # 7. パーセント指定の係数をずらす(元の 2.55 を掛ける形に戻すのと同じ型の傷)
    "pct": lambda s: s.replace("Math.round(parseFloat(p)*255/100)",
                               "Math.round(parseFloat(p)*2.55)"),
    # 7b. 小数の指定を切り捨てに戻す(2026-09-01 に直したほうのバグ)
    "trunc": lambda s: s.replace(": Math.round(parseFloat(p)));", ": parseInt(p,10));"),
    # 8. 色覚特性の行列を書き換える(白とグレーは動かず、縮退も保つので第三者比較でしか出ない)
    "matrix": lambda s: s.replace("[[0,1.05118294,-0.05116099],[0,1,0],[0,0,1]]",
                                  "[[0,1.30000000,-0.30000000],[0,1,0],[0,0,1]]"),
    # 9. 明度を動かす探索を1歩で打ち切る(届いていない案が出る/案が消える)
    "nudge": lambda s: s.replace("if (contrast(cand, fixed) >= goal) {",
                                 "if (true) {"),
    # 10. 白か黒かの選び方を逆にする
    "bw": lambda s: s.replace("contrast([0,0,0], bg) >= contrast([255,255,255], bg)",
                              "contrast([0,0,0], bg) <= contrast([255,255,255], bg)"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--page", help="この HTML を見る(既定は日本語版と英語版の両方)")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--tol", type=int, default=24,
                    help="daltonlens との差の許容(LMS の取り方が違うので 0 にはならない)")
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true")
    args = ap.parse_args()

    docs = pathlib.Path(args.docs)
    if args.page:
        p = pathlib.Path(args.page)
        pages = [(p, "en" if p.name.startswith("en") or "en" in p.parts else "ja", "指定されたページ")]
    else:
        pages = [(docs / "contrast" / "index.html", "ja", "日本語版"),
                 (docs / "en" / "contrast.html", "en", "英語版")]
    for p, _, _ in pages:
        if not p.exists():
            sys.exit("ページが見つかりません: %s" % p)

    rnd = random.Random(args.seed)
    cases, n_fixed = build_cases(args.n, rnd)

    # --- 参照どうしを先に突き合わせる ---
    moot = threshold_is_moot()
    bad, worst = cross_check_references(cases[:200])
    print("参照どうしの突き合わせ: 規格どおりの係数 vs wcag-contrast-ratio(完全一致) / "
          "厳密な sRGB の係数 vs coloraide(完全一致) → %s"
          % ("食い違い %d 件" % len(bad) if bad else "%d 件すべて一致" % len(cases[:200])))
    print("規格の 0.03928 と sRGB の 0.04045 で分岐が変わる 8bit の値: %d 個"
          "(=どちらで書いても同じ)" % len(moot))
    flips = [(f, b, t) for f, b, t in COEF_FLIP
             if (ratio(f, b) >= t) != (ratio_exact(f, b) >= t)]
    print("★規格が係数を4桁に丸めているせいで判定が割れる色の組: %d/%d 件"
          "(比の最大の相対差 %.2e)。道具は規格の本文どおりの側。"
          % (len(flips), len(COEF_FLIP), worst))
    for f, b, t in flips:
        print("   %s on %s: 規格 %.6f / 厳密 %.6f (しきい %.1f)"
              % (to_hex(f), to_hex(b), ratio(f, b), ratio_exact(f, b), t))
    if bad or moot or len(flips) != len(COEF_FLIP):
        for x in bad[:3]:
            print("  ", x)
        return 1

    import tempfile
    tmp = tempfile.TemporaryDirectory()
    work = pathlib.Path(tmp.name)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        if args.sabotage:
            src = pages[0][0].read_text(encoding="utf-8")
            small, _ = build_cases(70, random.Random(args.seed))
            print("--- わざと壊して、検査が落ちるかを見る ---")
            for name, fn in SABOTAGE.items():
                broken = fn(src)
                if broken == src:
                    browser.close()
                    sys.exit("仕込みが当たっていない(元のコードが変わっていない): %s" % name)
                f = work / ("broken-%s.html" % name)
                f.write_text(broken, encoding="utf-8", newline="\n")
                page.goto(f.as_uri())
                _, fails, _, _ = check_all(page, small, "ja", args.tol)
                print("  %-11s → %s" % (name, "検出した(%d件)" % len(fails)
                                        if fails else "★素通りした"))
                if not fails:
                    browser.close()
                    sys.exit("空振り: %s を仕込んでも検査が落ちない" % name)
            browser.close()
            print("\n%d 種すべて検出した。" % len(SABOTAGE))
            return 0

        result, fails, skips, maxdiff = {}, [], {}, 0
        for path, lang, label in pages:
            page.goto(path.resolve().as_uri())
            got, f, sk, md = check_all(page, cases, lang, args.tol)
            result[label] = got
            skips[label] = sk
            maxdiff = max(maxdiff, md)
            fails += ["%s %s" % (label, x) for x in f]
        browser.close()

    print("\n見本 %d 組(うち固定 %d)× %d 版 / 色の文字列 %d 通り"
          % (len(cases), n_fixed, len(pages), len(PARSE_CASES)))
    for label, g in result.items():
        print("  %s: 比 %d / 表示 %d / 判定 %d / APCA %d(表示 %d) / "
              "色の読み取り %d / 色覚特性 %d(第三者と一致 %d・性質 %d) / "
              "見本の色 %d / シミュ表示 %d / 修正案 %d"
              % (label, g["ratio"], g["display"], g["pills"], g["apca"], g["apca_disp"],
                 g["parse"], g["sims"], g["sim_third"], g["invariant"],
                 g["preview"], g["sim_disp"], g["fixes"]))
    print("daltonlens(Viénot 1999)との最大差: %d / 255 (許容 %d。"
          "LMS の取り方が違うので 0 にはならない)" % (maxdiff, args.tol))

    sw = SkipWatch("test_contrast")
    sw.check("[1] 画面の検査を最後まで通らなかった見本",
             len(cases) - result[pages[0][2]]["fixes"], len(cases))
    sw.check("[2] 修正案の明度が参照と1段ずれた見本(HSL の往復の丸め)",
             skips[pages[0][2]]["fixes_edge"], len(cases))
    skip_code = sw.report()

    if fails:
        print("\n★食い違い %d 件" % len(fails))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("\n食い違い 0")
    return skip_code


if __name__ == "__main__":
    sys.exit(main())
