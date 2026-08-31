#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「カラーパレット生成」の検証。

2026-08-22 作成(「基準まで寄せる」だけ) → **2026-09-01 朝、ページ全体に広げた**。

★広げた理由: 同じ枠で新設した `check_en_parity.py` が、**英語版にこの道具の看板機能が
  まるごと無い**ことを見つけた(`nudgeToContrast` も `readableOn` も無い、8/21 の手書きのまま)。
  このスクリプトは「寄せる」処理だけを、しかも**日本語版のパスを手で渡したときだけ**見ていたので、
  英語版に何も入っていないことに気づけなかった。
  → 既定で**日英2版を見る**ようにし、寄せる以外(配色の定義・画面・CSS書き出し)も測る。

## 参照の出どころを分ける

  (1) **HSL の変換は Python 標準の `colorsys`**(別実装)。道具は自前の変換を持っている
  (2) **コントラスト比は第三者の `wcag-contrast-ratio`**。規格の式を書き写さない
  (3) **配色の定義**(類似色=±15/±30度、補色=180度…)は Python 側に別表として書き下す
  (4) **「寄せる」の4項目**は 2026-08-22 からのもの:
      [1] 寄せた色が本当に基準を満たすか / [2] 動いたのが明るさだけか /
      [3] 上限内で満たせたのに諦めていないか / [4] もっと近い明るさで足りなかったか
      ★[2] は「出力の色相を測り直す」のではなく、**元の(色相,彩度)のまま明るさだけ変えた色で
      出力を再現できるか**で見る(彩度の低い色は 8bit 丸めで色相が数度ぶれるため)
  (5) **画面を読み戻す**: バッジの ○/× と比・スウォッチの16進数・寄せた量の表示・
      CSS の書き出し・下の説明文の数(全部で何色・何色寄せた・何色諦めた)

`--sabotage` でわざと傷を入れて、上の検査が本当に落ちるかを見る(空振り確認)。

    python lab/scripts/test_palette.py [--n 3000] [--sabotage] [--docs <docs>]
    python lab/scripts/test_palette.py --page docs/en/palette.html
    python lab/scripts/test_palette.py <index.htmlのパス>      # 旧来の呼び方も残してある
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

SCRIPT_RE = re.compile(r"<script>\s*(.*?)</script>", re.S)
JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")
BADGE = re.compile(r"^(.*?)([○×])\s+([\d.]+)$")
CSSVAR = re.compile(r"^--(.+)-(\d+): (#[0-9a-f]{6});$")
MAX_MOVE = 0.30      # ページ側の上限と合わせる


# ---------------------------------------------------------------- 参照(1)(2)
def to_hsl(hexstr):
    r, g, b = [int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def from_hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    # ⚠ JS の Math.round は 0.5 を上に、Python の round は偶数に丸める。floor(x+0.5) で合わせる。
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, math.floor(c * 255 + 0.5))) for c in (r, g, b))


def ratio(a, b):
    import wcag_contrast_ratio as wcr
    return wcr.rgb(tuple(int(a[i:i + 2], 16) / 255 for i in (1, 3, 5)),
                   tuple(int(b[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def clamp01(v):
    return max(0.0, min(1.0, v))


def shift(hexstr, dh, ds=0.0, dl=0.0):
    h, s, l = to_hsl(hexstr)
    return from_hsl(h + dh, clamp01(s + ds), clamp01(l + dl))


# ---------------------------------------------------------------- 参照(3)
def schemes(base):
    """配色の定義を Python 側に別表として書き下したもの(ページの表と突き合わせる)。"""
    return [
        [shift(base, -30), shift(base, -15), base, shift(base, 15), shift(base, 30)],
        [base, shift(base, 180), shift(base, 180, -.15, .15), shift(base, 0, -.2, .25)],
        [base, shift(base, 150), shift(base, 210)],
        [base, shift(base, 120), shift(base, 240)],
        [shift(base, 0, 0, -.3), shift(base, 0, 0, -.15), base,
         shift(base, 0, 0, .15), shift(base, 0, 0, .3)],
        [shift(base, 0, -.35, .1), shift(base, 20, -.4, .2),
         shift(base, -20, -.4, .25), shift(base, 0, -.3, .35)],
    ]


def readable_on(hexstr):
    return "#ffffff" if ratio(hexstr, "#ffffff") >= ratio(hexstr, "#1a1a1a") else "#1a1a1a"


def best_possible(hexstr, fg, need):
    """明るさだけを動かしたときの
      (a) 到達できる最大の比率
      (b) **基準を満たす L のうち、元の L にいちばん近いものまでの距離**
    を総当たりで出す。

    ⚠ (b) は 2026-09-01 に直したところ。それまでは「比が最大になる L」を返していたが、
    それは**いちばん遠い端(黒か白)**になりがちで、「上限内で満たせたのに諦めた」の
    判定に使うと **上限を超えている**と読めてしまう。実際、明るくする側の探索を
    わざと消した仕込み(`updown`)が、この検査を素通りしていた。
    見るべきは「近いところに満たす L があるか」なので、最近傍を返す。
    """
    h, s, l0 = to_hsl(hexstr)
    best_r, nearest = 0.0, None
    for i in range(1001):
        l = i / 1000
        r = ratio(from_hsl(h, s, l), fg)
        if r > best_r:
            best_r = r
        if r >= need and (nearest is None or abs(l - l0) < nearest):
            nearest = abs(l - l0)
    return best_r, nearest


# ---------------------------------------------------------------- 「寄せる」の検査
def check_nudge(page, cases):
    """2026-08-22 からの4項目。ページの `nudgeToContrast` を直接呼ぶ。"""
    results = page.evaluate(
        """(cases) => cases.map(([c, fg, need]) => {
             const r = nudgeToContrast(c, fg, need);
             return r === null ? null : [r.hex, r.moved, !!r.tooFar];
           })""", cases)

    n_ok = n_null = 0
    bad_ratio, bad_hue, bad_null, bad_minimal = [], [], [], []
    for (col, fg, need), res in zip(cases, results):
        if res is None or res[2]:            # null か、上限を超えて寄せなかった
            n_null += 1
            reach, nearest = best_possible(col, fg, need)
            if nearest is not None and nearest <= MAX_MOVE - 0.01:
                bad_null.append((col, fg, need, reach, nearest))
            continue
        n_ok += 1
        out, moved = res[0], res[1]
        if abs(moved) > MAX_MOVE * 100 + 1:
            bad_minimal.append(("上限超過なのに適用した", col, fg, need, moved))
        got = ratio(out, fg)
        if got < need - 0.01:
            bad_ratio.append((col, fg, need, out, got))
        h0, s0, l0 = to_hsl(col)
        _, _, l1 = to_hsl(out)
        # 「動かしたのは明るさだけ」の確かめ方。
        # 出力の色相・彩度を測り直して比べると、彩度の低い色では 8bit 丸めのせいで
        # 色相が数度ぶれ、アルゴリズムのせいなのか丸めのせいなのか区別がつかない。
        # なので逆に「元の (色相, 彩度) のまま明るさだけ変えた色で、出力を再現できるか」を見る。
        best_d, best_hex = 999, None
        for i in range(1001):
            cand = from_hsl(h0, s0, i / 1000)
            d = max(abs(int(cand[j:j + 2], 16) - int(out[j:j + 2], 16)) for j in (1, 3, 5))
            if d < best_d:
                best_d, best_hex = d, cand
            if d == 0:
                break
        if best_d > 1:       # 各チャンネル ±1 まではHSL往復の丸め誤差
            bad_hue.append((col, out, "同じ色相・彩度の線上に無い(最接近 %s, 差 %d)"
                            % (best_hex, best_d)))
        # 最小性: 元の L と出力の L のあいだに、満たせる L が無いこと
        if moved != 0:
            step = 0.002 if l1 > l0 else -0.002
            l = l0 + step
            while (l < l1 - 0.002) if step > 0 else (l > l1 + 0.002):
                if ratio(from_hsl(h0, s0, l), fg) >= need:
                    bad_minimal.append((col, fg, need, l0, l, l1))
                    break
                l += step
    return dict(ok=n_ok, null=n_null), \
        dict(ratio=bad_ratio, hue=bad_hue, null=bad_null, minimal=bad_minimal)


# ---------------------------------------------------------------- 画面の検査
VIA_UI = """(o) => {
  const $ = id => document.getElementById(id);
  $('hex').value = o.base; $('hex').dispatchEvent(new Event('change'));
  $('fg').value = o.fg; $('level').value = o.level; $('fix').checked = o.fix;
  ['fg', 'level', 'fix'].forEach(id => $(id).dispatchEvent(new Event('change')));
  const secs = [];
  let cur = null;
  for (const el of $('sections').children) {
    if (el.tagName === 'H2') { cur = {name: el.textContent, rows: []}; secs.push(cur); }
    else if (el.className === 'row' && cur) {
      cur.rows = Array.from(el.querySelectorAll('.sw')).map(b => ({
        hex: b.dataset.hex,
        badges: Array.from(b.querySelectorAll('.chip span')).map(s => s.textContent),
        meta: b.querySelector('.meta').textContent,
        moved: b.querySelector('.moved') ? b.querySelector('.moved').textContent : null
      }));
    }
  }
  return {secs: secs, css: $('css').textContent, note: $('fixnote').textContent,
          hex: $('hex').value};
}"""


def boundary_pairs(need):
    """★表示は小数1桁に丸めるが、○× は丸めていない値で決めなければならない。
    比が [need-0.05, need) に入る組は「4.5」と表示されるのに × でなければならない。
    グレー同士を全数(256×256)で走査して、しきいの前後 0.05 に入る組を拾う
    (ふつうの見本ではこの帯にまず入らない。`mark` の仕込みが素通りしたのがその証拠)。"""
    lum = {}
    for v in range(256):
        h = "#%02x%02x%02x" % (v, v, v)
        lum[v] = h
    below, above = [], []
    for a in range(256):
        for b in range(a + 1, 256):
            r = ratio(lum[a], lum[b])
            if need - 0.05 <= r < need and len(below) < 4:
                below.append((lum[a], lum[b], r))
            elif need <= r < need + 0.05 and len(above) < 4:
                above.append((lum[a], lum[b], r))
        if len(below) >= 4 and len(above) >= 4:
            break
    return below + above


CALL_BADGE = "(a) => a.map(([bg, fg, need]) => badge(bg, fg, '', need))"


def check_badge_boundary(page):
    """しきいをまたぐ丸めの見本で、○× が丸めた値ではなく本当の値で決まっているか。"""
    fails, n = [], 0
    cases = []
    for need in (3.0, 4.5, 7.0):
        for bg, fg, r in boundary_pairs(need):
            cases.append((bg, fg, need, r))
    got = page.evaluate(CALL_BADGE, [[c[0], c[1], c[2]] for c in cases])
    for (bg, fg, need, r), html in zip(cases, got):
        m = re.search(r">\s*([○×])\s+([\d.]+)<", html)
        if not m:
            fails.append("バッジが読めない %r" % html)
            continue
        want = "○" if r >= need else "×"
        if m.group(1) != want:
            fails.append("しきいの境目で○×が違う(%s on %s = %.4f / 基準 %.1f / 表示 %s%s)"
                         % (bg, fg, r, need, m.group(1), m.group(2)))
        else:
            n += 1
    return n, fails


def check_page(page, bases, lang):
    """画面に出たものを読み戻して、参照と突き合わせる。"""
    fails = []
    n = dict(swatch=0, badge=0, css=0, note=0, scheme=0, auto=0, edge=0)
    near = 0                       # HSL の往復で1ずれた見本(対象外にはしない。数だけ出す)

    for base in bases:
        for fg_sel, level, do_fix in (("#1a1a1a", "4.5", False), ("#ffffff", "4.5", True),
                                      ("auto", "3", True), ("#ffffff", "7", True)):
            got = page.evaluate(VIA_UI, {"base": base, "fg": fg_sel,
                                         "level": level, "fix": do_fix})
            need = float(level)
            want_secs = schemes(base)
            if len(got["secs"]) != len(want_secs):
                fails.append("%s: 配色の数が違う(画面 %d / 参照 %d)"
                             % (base, len(got["secs"]), len(want_secs)))
                continue

            css_lines = [l.strip() for l in got["css"].split("\n")[1:-1]]
            css_i = 0
            n_fixed = n_far = n_total = 0

            for si, (sec, want_cols) in enumerate(zip(got["secs"], want_secs)):
                if len(sec["rows"]) != len(want_cols):
                    fails.append("%s: %d番目の配色の色数が違う(画面 %d / 参照 %d)"
                                 % (base, si, len(sec["rows"]), len(want_cols)))
                    break
                for ci, (sw, want_c0) in enumerate(zip(sec["rows"], want_cols)):
                    n_total += 1
                    # 参照(3) 配色の定義(寄せる前の色)。寄せた場合は表示の色が変わるので、
                    # 寄せていない見本(fix なし)のときだけ突き合わせる。
                    if not do_fix:
                        d = max(abs(int(sw["hex"][j:j + 2], 16) - int(want_c0[j:j + 2], 16))
                                for j in (1, 3, 5))
                        if d > 1:
                            fails.append("%s: 配色の色が参照と違う(%d-%d 画面 %s / 参照 %s 差 %d)"
                                         % (base, si, ci, sw["hex"], want_c0, d))
                            continue
                        if d == 1:
                            near += 1
                        n["scheme"] += 1

                    # 参照(5) スウォッチの16進数が meta の文字にも出ているか
                    if not sw["meta"].startswith(sw["hex"]):
                        fails.append("%s: 16進数の表示が data-hex と違う(%r / %s)"
                                     % (base, sw["meta"], sw["hex"]))
                        continue
                    n["swatch"] += 1

                    # 参照(2)(5) バッジの比と ○×
                    fg = readable_on(want_c0) if fg_sel == "auto" else fg_sel
                    other = "#1a1a1a" if fg == "#ffffff" else "#ffffff"
                    if len(sw["badges"]) != 2:
                        fails.append("%s: バッジが %d 個" % (base, len(sw["badges"])))
                        continue
                    ok = True
                    for bi, (txt, on) in enumerate(zip(sw["badges"], (fg, other))):
                        m = BADGE.match(txt.strip())
                        if not m:
                            fails.append("%s: バッジが読めない %r" % (base, txt))
                            ok = False
                            break
                        r = ratio(sw["hex"], on)
                        want_mark = "○" if r >= need else "×"
                        if m.group(2) != want_mark:
                            fails.append("%s: バッジの○× が違う(%s on %s = %.4f / 基準 %.1f)"
                                         % (base, sw["hex"], on, r, need))
                            ok = False
                            break
                        if abs(float(m.group(3)) - round(r, 1)) > 0.051:
                            fails.append("%s: バッジの比が違う(画面 %s / 参照 %.4f)"
                                         % (base, m.group(3), r))
                            ok = False
                            break
                        # 白/黒の名札が、実際に当てている色と合っているか
                        label = m.group(1).strip()
                        if fg_sel == "auto" and bi == 0:
                            n["auto"] += 1
                        if label and lang == "en" and label not in ("White", "Black"):
                            fails.append("%s: バッジの名札が White/Black でない %r" % (base, label))
                            ok = False
                            break
                    if not ok:
                        continue
                    n["badge"] += 1

                    # ★寄せた/寄せなかった の見分けは**符号の有無**で見る。
                    #   寄せたときだけ符号つきで出る(「明るさ +12 寄せた」/「lightness +12 pts」)。
                    #   届かなかった側は符号なし(「要 30 ・寄せず」)か、数そのものが無い
                    #   (「寄せられません」)。数の大小で分けようとすると 30 ちょうどで割れる。
                    if sw["moved"]:
                        if re.search(r"[-+]\d+", sw["moved"]):
                            n_fixed += 1
                        else:
                            n_far += 1

                    # 参照(5) CSS の書き出しがスウォッチと同じ順・同じ色か
                    if css_i < len(css_lines):
                        m = CSSVAR.match(css_lines[css_i])
                        if not m or m.group(3) != sw["hex"] or int(m.group(2)) != ci + 1:
                            fails.append("%s: CSS の書き出しが違う(%r / 期待 %s の %d 番)"
                                         % (base, css_lines[css_i], sw["hex"], ci + 1))
                        else:
                            n["css"] += 1
                    css_i += 1

            if css_i != len(css_lines):
                fails.append("%s: CSS の行数がスウォッチの数と違う(%d / %d)"
                             % (base, len(css_lines), css_i))

            # 参照(5) 下の説明文の数が、画面のスウォッチを数えたものと合うか
            # ⚠ 説明文には基準そのもの(「4.5:1」)も出るので、先に取り除いてから数を拾う。
            #   取り除かないと 3:1 の 3 と 1 を件数と読んでしまう。
            nums = [int(x) for x in
                    re.findall(r"\b\d+\b", re.sub(r"\d+(\.\d+)?:1", "", got["note"]))]
            if do_fix:
                # ページ側の3通りの言い回しに合わせる(寄せられなかった色がある /
                # 寄せた色がある / 全部が元から満たしていた)
                if n_far:
                    want = [n_total, n_fixed, n_far]
                elif n_fixed:
                    want = [n_total, n_fixed]
                else:
                    want = [n_total]
                # ⚠ 後ろには決まり文句の「30 ポイント」が続くので、先頭だけを見る
                if nums[:len(want)] != want:
                    fails.append("%s: 説明文の数が違う(画面 %s / 参照 %s): %r"
                                 % (base, nums, want, got["note"][:60]))
                else:
                    n["note"] += 1
            else:
                n["note"] += 1

            if lang == "en":
                left = JA_CHARS.findall(got["note"] + got["css"]
                                        + "".join(s["name"] for s in got["secs"])
                                        + "".join(sw["meta"] + (sw["moved"] or "")
                                                  for s in got["secs"] for sw in s["rows"]))
                if left:
                    fails.append("英語版の画面に日本語が %d 文字: %s" % (len(left), left[:8]))
    n["edge"], edge_fails = check_badge_boundary(page)
    fails += edge_fails
    return n, fails, near


# ---------------------------------------------------------------- 空振り確認
SABOTAGE = {
    # 1. 相対輝度の分岐のしきいを外す(比が全部ずれる)
    "trc": lambda s: s.replace("v <= 0.04045 ? v/12.92", "v <= 0.4 ? v/12.92"),
    # 2. 補色の角度を変える(配色の定義の表)
    "hue": lambda s: s.replace("shift(base,180)", "shift(base,170)"),
    # 3. 二分探索の回数を減らす(寄せが足りなくなる)
    "iter": lambda s: s.replace("i < 24; i++", "i < 3; i++"),
    # 4. 上限を外す(別の色になるまで寄せてしまう)
    "maxmove": lambda s: s.replace("const MAX_MOVE = 0.30;", "const MAX_MOVE = 9.00;"),
    # 5. 明るくする側を探さない(もっと近い明るさを見落とす)
    "updown": lambda s: s.replace("if (contrast(at(1), fg) >= need) cands.push(search(l0, 1));", ""),
    # 6. 白か黒かの選び方を逆にする(auto のとき読めないほうを選ぶ)
    "readable": lambda s: s.replace(
        'contrast(hex, "#ffffff") >= contrast(hex, "#1a1a1a")',
        'contrast(hex, "#ffffff") <= contrast(hex, "#1a1a1a")'),
    # 7. バッジの ○× を丸めた値で決める(境目でずれる)
    "mark": lambda s: s.replace("const mark = c >= need", "const mark = +c.toFixed(1) >= need"),
    # 8. CSS の書き出しの番号を 0 始まりにする
    "cssidx": lambda s: s.replace("-${i + 1}: ${c};", "-${i}: ${c};"),
}


def load_functions(browser, path):
    """DOM を触る行より前だけを読み込んで、ページの関数をそのまま呼べるようにする。

    ★**毎回まっさらなページを作る**(2026-09-01 修正)。
    それまでは1枚のページに `set_content` で入れ直していたが、**同じ実行文脈に
    2度目の `const MAX_MOVE = …` を入れることになり、再宣言でスクリプト全体が落ちて
    1回目の関数がそのまま残っていた**。`add_script_tag` はそれを例外にしないので、
    `--sabotage` は**2種類目以降ずっと1種類目のコードを測っていた**
    (=空振り確認そのものが空振りしていた)。仕込みが効いているかを下で毎回確かめる。
    """
    body = SCRIPT_RE.search(path.read_text(encoding="utf-8")).group(1)
    page = browser.new_page()
    page.set_content("<!doctype html><meta charset=utf-8>")
    cut = body.index('$("base").addEventListener')
    page.add_script_tag(content=body[:cut])
    # 入れたはずのコードが本当に走っているか(古い文脈が残っていないか)を毎回見る
    live = page.evaluate("typeof nudgeToContrast === 'function' ? nudgeToContrast.toString() : null")
    if live is None or live.replace("\r\n", "\n") not in body.replace("\r\n", "\n"):
        page.close()
        sys.exit("読み込んだ関数がファイルの中身と違う(古い実行文脈が残っている): %s" % path)
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="?", help="(旧来の呼び方)この HTML だけを見る")
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--page", help="この HTML を見る(既定は日本語版と英語版の両方)")
    ap.add_argument("--n", type=int, default=3000, help="「寄せる」の見本の数")
    ap.add_argument("--bases", type=int, default=8, help="画面の検査で使う基準色の数")
    ap.add_argument("--seed", type=int, default=20260822)
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true")
    args = ap.parse_args()

    docs = pathlib.Path(args.docs)
    only = args.page or args.html
    if only:
        p = pathlib.Path(only)
        pages = [(p, "en" if p.name.startswith("en") or "en" in p.parts else "ja",
                  "指定されたページ")]
    else:
        pages = [(docs / "palette" / "index.html", "ja", "日本語版"),
                 (docs / "en" / "palette.html", "en", "英語版")]
    for p, _, _ in pages:
        if not p.exists():
            sys.exit("ページが見つかりません: %s" % p)

    rng = random.Random(args.seed)
    cases = []
    for _ in range(args.n):
        cases.append(("#%06x" % rng.randrange(0x1000000),
                      rng.choice(["#ffffff", "#1a1a1a"]),
                      rng.choice([3.0, 4.5, 7.0])))
    brng = random.Random(args.seed + 1)
    bases = ["#2b6cb0", "#ffff00", "#000000", "#ffffff"]
    while len(bases) < args.bases:
        bases.append("#%06x" % brng.randrange(0x1000000))

    import tempfile
    tmp = tempfile.TemporaryDirectory()
    work = pathlib.Path(tmp.name)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        if args.sabotage:
            src = pages[0][0].read_text(encoding="utf-8")
            small = cases[:250]
            print("--- わざと壊して、検査が落ちるかを見る ---")
            for name, fn in SABOTAGE.items():
                broken = fn(src)
                if broken == src:
                    browser.close()
                    sys.exit("仕込みが当たっていない(元のコードが変わっていない): %s" % name)
                f = work / ("broken-%s.html" % name)
                f.write_text(broken, encoding="utf-8", newline="\n")
                fnpage = load_functions(browser, f)
                _, bad = check_nudge(fnpage, small)
                fnpage.close()
                hit = sum(len(v) for v in bad.values())
                page = browser.new_page()
                page.goto(f.as_uri())
                _, fails, _ = check_page(page, bases[:4], "ja")
                page.close()
                print("  %-9s → %s" % (name, "検出した(寄せる %d件 / 画面 %d件)"
                                       % (hit, len(fails)) if hit or fails else "★素通りした"))
                if not (hit or fails):
                    browser.close()
                    sys.exit("空振り: %s を仕込んでも検査が落ちない" % name)
            browser.close()
            print("\n%d 種すべて検出した。" % len(SABOTAGE))
            return 0

        result, fails, near_total = {}, [], 0
        for path, lang, label in pages:
            fn = load_functions(browser, path)
            counts, bad = check_nudge(fn, cases)
            fn.close()
            page = browser.new_page()
            page.goto(path.resolve().as_uri())
            n, f, near = check_page(page, bases, lang)
            page.close()
            result[label] = (counts, bad, n)
            near_total += near
            fails += ["%s %s" % (label, x) for x in f]
        browser.close()

    print("「寄せる」の見本 %d 通り / 画面の検査に使った基準色 %d 色 × 4通りの設定 × %d 版"
          % (len(cases), len(bases), len(pages)))
    total_bad = 0
    for label, (counts, bad, n) in result.items():
        total_bad += sum(len(v) for v in bad.values())
        print("  %s: 寄せた %d / 寄せなかった %d" % (label, counts["ok"], counts["null"]))
        print("     [1] 寄せたのに基準未達 %d / [2] 色相か彩度が動いた %d / "
              "[3] 上限内で満たせたのに諦めた %d / [4] もっと近い明るさで足りた %d"
              % (len(bad["ratio"]), len(bad["hue"]), len(bad["null"]), len(bad["minimal"])))
        print("     配色の定義 %d / スウォッチ %d / バッジ %d / CSS %d / 説明文 %d / "
              "auto の白黒 %d / しきいの境目 %d"
              % (n["scheme"], n["swatch"], n["badge"], n["css"], n["note"], n["auto"],
                 n["edge"]))
        for k, lst in bad.items():
            for row in lst[:3]:
                print("      [%s] %s" % (k, row))
    print("HSL の往復で1だけずれた色: %d(許容。0 にはならない)" % near_total)

    sw = SkipWatch("test_palette")
    first = result[pages[0][2]][0]
    sw.check("[1] 寄せなかった見本(上限超過・到達不能)", first["null"], len(cases))
    skip_code = sw.report()

    if fails or total_bad:
        print("\n★食い違い %d 件(画面 %d / 寄せる %d)" % (len(fails) + total_bad, len(fails), total_bad))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("\n食い違い 0")
    return skip_code


if __name__ == "__main__":
    sys.exit(main())
