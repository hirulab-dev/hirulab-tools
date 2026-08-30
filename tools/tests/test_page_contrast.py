#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「ページまるごとコントラスト診断」の検証(2026-08-31 新設)。

この道具には検証スクリプトが1本も無かった。自分のサイト全体を測る `check_contrast.py` は
あるが、**道具そのものが正しいか**は一度も機械で確かめていなかった。

★参照を別の出どころにする:
  - 比の値      … WCAG 2.1 の式を **Python で独立に書き下したもの**
                   (道具の JS を読み写すのではなく、規格の定義から書く)
  - 前景色・背景色 … ブラウザの `getComputedStyle`(道具が使うのと同じだが、
                   **道具を通さず Playwright から直接**読む)
  - しきい値     … 24px / 18.66px+bold の分岐を Python 側で別に判定する

やること4つ:
  1. 色としきい値が分かっている見本ページを組み立て、道具を注入して結果を読む
  2. 道具が「足りない」と名指しした要素の集合が、Python の判定と一致するか
  3. 画面に出た比の値が、Python の計算と 0.01 以内で一致するか
  4. **英語版のブックマークレットが英語で結果を出すか**(日本語が1文字も出ないか)

`--sabotage` で道具にわざと傷を入れて、上の検査が本当に落ちるかを見る(空振り確認)。

    python lab/scripts/test_page_contrast.py [--sabotage] [--docs <docs>]
"""
import argparse
import itertools
import pathlib
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")


# ---- 参照: WCAG 2.1 の式を Python で独立に書く -------------------------------
def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def needed(size_px, weight):
    """AA のしきい値。24px以上、または 18.66px以上の太字なら 3:1、それ以外 4.5:1。"""
    large = size_px >= 24 or (size_px >= 18.66 and weight >= 700)
    return 3.0 if large else 4.5


# ---- 見本ページ ---------------------------------------------------------------
COLORS = [(0, 0, 0), (255, 255, 255), (119, 119, 119), (143, 92, 14), (245, 166, 35),
          (21, 112, 63), (179, 38, 30), (26, 26, 26), (232, 232, 230), (100, 149, 237),
          (200, 200, 200), (60, 60, 60)]
SIZES = [12, 14, 16, 18.5, 19, 24, 30]
WEIGHTS = [400, 700]


def sample_page(seed, n=40):
    """色・大きさ・太さが分かっている行を並べた見本ページ。期待値も一緒に返す。"""
    rnd = random.Random(seed)
    rows, expect = [], []
    combos = list(itertools.product(COLORS, COLORS, SIZES, WEIGHTS))
    rnd.shuffle(combos)
    for i, (fg, bg, size, w) in enumerate(combos[:n]):
        if fg == bg:
            continue
        text = "sample line %d" % i
        rows.append(
            '<p id="r%d" style="color:rgb(%d,%d,%d);background:rgb(%d,%d,%d);'
            'font-size:%spx;font-weight:%d;margin:0">%s</p>'
            % (i, fg[0], fg[1], fg[2], bg[0], bg[1], bg[2], size, w, text))
        v = ratio(fg, bg)
        need = needed(size, w)
        expect.append({"id": "r%d" % i, "text": text, "v": v, "need": need,
                       "bad": v < need})
    html = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<style>body{background:#fff;margin:0}</style></head><body>'
            + "".join(rows) + "</body></html>")
    return html, expect


# ---- 道具の取り出し -----------------------------------------------------------
def bookmarklet(path, sabotage=None):
    """ページに書いてある診断関数そのものを取り出す(道具の設計どおりの経路)。"""
    src = path.read_text(encoding="utf-8")
    m = re.search(r"function hirulabContrast\(\)\{.*?\n\}\n", src, re.S)
    if not m:
        sys.exit("%s から診断関数を取り出せません" % path)
    fn = m.group(0)
    if sabotage:
        fn = SABOTAGE[sabotage](fn)
    # `page.evaluate` は渡した文字列を式として読むので、関数宣言のままだと落ちる。
    # 本物のブックマークレットと同じく、丸ごと1つの式に包んで呼ぶ。
    return "(() => {\n" + fn + "\nhirulabContrast();\n})()"


SABOTAGE = {
    # しきい値をひっくり返す(大きい文字にも 4.5 を求める)
    "need": lambda s: s.replace("var need = large ? 3 : 4.5;", "var need = 4.5;"),
    # 比の式から 0.05 を落とす(暗い側で値が跳ね上がる)
    "formula": lambda s: s.replace("+ 0.05) / (Math.min(l1, l2) + 0.05)",
                                   ") / (Math.min(l1, l2))").replace(
                                   "(Math.max(l1, l2) + 0.05", "(Math.max(l1, l2)"),
    # 相対輝度の係数を入れ替える
    "lum": lambda s: s.replace("0.2126 * lin(c[0]) + 0.7152 * lin(c[1])",
                               "0.7152 * lin(c[0]) + 0.2126 * lin(c[1])"),
    # sRGB の折れ点を無視して、いつも単純なべき乗にする
    "linear": lambda s: s.replace("return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);",
                                  "return Math.pow(c, 2.2);"),
    # 太字の判定を落とす
    "bold": lambda s: s.replace("(size >= 18.66 && weight >= 700)", "false"),
}

READ = """() => {
  const box = document.getElementById("__hirulab_contrast__");
  if (!box) return null;
  return {
    text: box.innerText,
    rows: [...box.querySelectorAll("[data-hlc-i]")].map(d => d.innerText)
  };
}"""


def run(page, html, fn):
    page.set_content(html)
    page.evaluate(fn)
    return page.evaluate(READ)


ROW = re.compile(r"([\d.]+):1\s*[（(]\D*([\d.]+):1\s*/\s*(\d+)px")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--seeds", type=int, default=12)
    args = ap.parse_args()
    docs = pathlib.Path(args.docs)
    ja = docs / "page-contrast" / "index.html"
    en = docs / "en" / "page-contrast.html"

    fails = []

    def check(page, path, label, fn):
        """1つの版について、見本ページを何枚も食わせて突き合わせる。"""
        n_set = n_val = 0
        for seed in range(args.seeds):
            html, expect = sample_page(seed)
            got = run(page, html, fn)
            if got is None:
                fails.append("%s seed=%d 結果の箱が出なかった" % (label, seed))
                continue
            listed = {}
            for row in got["rows"]:
                m = ROW.search(row)
                text = row.split("\n")[-1].strip()
                if m:
                    listed[text] = (float(m.group(1)), float(m.group(2)), int(m.group(3)))
            want = {e["text"] for e in expect if e["bad"]}
            if set(listed) != want:
                miss = sorted(want - set(listed))[:3]
                extra = sorted(set(listed) - want)[:3]
                fails.append("%s seed=%d 名指しの集合が違う(拾えていない %s / 余計 %s)"
                             % (label, seed, miss, extra))
            else:
                n_set += 1
            for e in expect:
                if not e["bad"]:
                    continue
                if e["text"] not in listed:
                    continue
                v, need, _ = listed[e["text"]]
                if abs(v - e["v"]) > 0.011:
                    fails.append("%s seed=%d 比が違う %s: 道具 %.2f / 参照 %.2f"
                                 % (label, seed, e["text"], v, e["v"]))
                elif abs(need - e["need"]) > 0.001:
                    fails.append("%s seed=%d しきい値が違う %s: 道具 %s / 参照 %s"
                                 % (label, seed, e["text"], need, e["need"]))
                else:
                    n_val += 1
        return n_set, n_val

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        if args.sabotage:
            print("--- わざと壊して、検査が落ちるかを見る ---")
            for name in SABOTAGE:
                fails.clear()
                fn = bookmarklet(ja, name)
                check(page, ja, "sabotage:" + name, fn)
                print("  %-8s → %s" % (name, "検出した" if fails else "★素通りした"))
                if not fails:
                    browser.close()
                    sys.exit("空振り: %s を仕込んでも検査が落ちない" % name)
            browser.close()
            print("\n%d 種すべて検出した。" % len(SABOTAGE))
            return 0

        total = {}
        for path, label in [(ja, "日本語版"), (en, "英語版")]:
            s, v = check(page, path, label, bookmarklet(path))
            total[label] = (s, v)

        # 英語版のブックマークレットが英語で結果を出すか
        html, _ = sample_page(0)
        got = run(page, html, bookmarklet(en))
        en_ja = JA_CHARS.findall(got["text"]) if got else ["(結果が出なかった)"]
        if en_ja:
            fails.append("英語版の結果に日本語が %d 文字: %s" % (len(en_ja), en_ja[:8]))
        for want in ["Contrast Audit", "fall short of the standard", "Press an entry"]:
            if got and want not in got["text"]:
                fails.append("英語版の結果に %r が出ていない" % want)

        # 合格するページでは「基準を満たしています」側の文が出るか(日英とも)
        clean = ('<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
                 '<body style="background:#fff"><p style="color:#000">ok</p></body></html>')
        for path, label, want in [(ja, "日本語版", "満たしています"),
                                  (en, "英語版", "meets level AA")]:
            got2 = run(page, clean, bookmarklet(path))
            if not got2 or want not in got2["text"]:
                fails.append("%s: 合格したページで %r が出ない" % (label, want))

        browser.close()

    print("見本ページ %d 枚 × 2版" % args.seeds)
    for label, (s, v) in total.items():
        print("  %s: 名指しの集合が一致 %d/%d 枚 / 比としきい値が一致 %d 件"
              % (label, s, args.seeds, v))
    print("英語版の結果に出た日本語: %d 文字" % len(en_ja))
    if fails:
        print("\n★食い違い %d 件" % len(fails))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("\n食い違い 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
