#!/usr/bin/env python3
"""ツール25本目「和柄シームレスパターン作成」の検証。

やること:
 1. ページの /*CORE-START*/〜/*CORE-END*/ を抽出し、まっさらなページの中で実行する
    (DOM非依存の生成コアであることを、DOMの無いところで動かして確かめる意味も兼ねる)
 2. 全8柄 × 3サイズ(配色はindigo)の24枚を2000pxでSVG出力 → Chromiumでラスタライズ
 3. 各柄の「タイル周期」ぶんだけずらしたピクセルが一致するか(周期性)+
    周期がキャンバス2000を割り切るか(=ラップしても継ぎ目なし)を検査
 4. --sabotage で「割り切れない寸法」をわざと混ぜ、この検査が落ちることを確認

使い方: python lab/scripts/test_pattern_tool.py [--html PATH] [--sabotage]

⚠ 2026-09-01: クラウド線から受け取った初版は node と /opt/pw-browsers/chromium を
   前提にしていて、ローカル(Windows)では1行も動かなかった。うちの検証はすべて
   Playwright(Python)で書かれているので、そちらに寄せた。生成コアの実行も
   ラスタライズも同じブラウザで済むので、外部の実行環境が1つ減っている。
"""
import argparse
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HTML_DEFAULT = Path.home() / "hirulab-tools" / "docs" / "pattern" / "index.html"

# 生成コアをそのまま入れて、24枚ぶんのSVGと周期を返させる。
RUNNER = """
(() => {
%CORE%
  const out = [];
  for (const p of PATTERNS) {
    for (let si = 0; si < p.sizes.length; si++) {
      const pr = p.periods(p.sizes[si]);
      out.push({
        name: p.key + "-" + si,
        svg: buildSvg(p.key, COLORWAYS.indigo, si, 1.0, 2000),
        px: pr[0], py: pr[1]
      });
    }
  }
  return out;
})()
"""


# わざと仕込む傷。**どの検査が捕まえるはずか**まで書いて、そこまで一致するかを見る。
# 理由: 初版の仕込みは1種類だけで、しかも安いほうの「割り切れるか」の検査に引っかかっていた。
# つまり**高いほうの「ずらして一致するか」は1度も試されていなかった**(捕まえたのは別の検査)。
# 「壊してみるまで空振りは見えない」の一段先で、**どの検査が捕まえたかまで見ないと、
# 検査の一部だけが働いていても全部働いているように見える**。
SABOTAGES = [
    # 割り切れない寸法。周期の宣言そのものが狂うので算術の検査で捕まるはず
    ("size-not-divisor", "shippou", r'(key: "shippou",\s*sizes: \[)200', r"\g<1>300", "divide"),
    # 横の間隔だけずらす。周期の宣言は正しいままなので、算術では絶対に捕まらない。
    # 実際に描いた絵をずらして見る検査だけが捕まえられる
    ("x-spacing-off", "seigaiha", r"(x < CANVAS \+ 2 \* R; x \+= 2 \* R)\)", r"\g<1> + 5)", "pixel"),
    # 縦の送りだけずらす。同上(y方向の枝が生きているかを見る)
    ("y-rowstep-off", "seigaiha", r"(var out = \[\], rowStep = R / 2)", r"\g<1> + 3", "pixel"),
]


def extract_core(html: str) -> str:
    m = re.search(r"/\*CORE-START\*/(.*?)/\*CORE-END\*/", html, re.S)
    if not m:
        sys.exit("CORE block not found")
    return m.group(1)


def kind_of(problems):
    """問題の文言から、どの検査が捕まえたかを分類する。"""
    kinds = set()
    for p in problems:
        kinds.add("divide" if "does not divide" in p else "pixel")
    return kinds


def check_image(png_path: Path, px: int, py: int):
    """周期性と割り切りの検査。返り値は問題のリスト。"""
    problems = []
    if 2000 % px:
        problems.append(f"x period {px} does not divide 2000")
    if 2000 % py:
        problems.append(f"y period {py} does not divide 2000")
    im = Image.open(png_path).convert("RGB").crop((0, 0, 2000, 2000))
    pix = im.load()
    step = 97  # 素数刻みでサンプル(格子と同期して見逃すのを避ける)
    # ⚠ChromiumのラスタライザはAA画素が整数平行移動で厳密不変にならない(実測: 同一円の
    # 500pxシフトで約0.4%の画素にチャネル差1〜25)。よって「厳密一致」でなく
    # 「チャネル差が64を超えたら不一致」で判定する。本物の継ぎ目ズレは柄と地が
    # 入れ替わる=差100超が大量に出るので、この閾値で見逃さない(--sabotageで確認)
    TOL = 64

    def diff(a, b):
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))

    bad = 0
    for y in range(13, 2000, step):
        for x in range(13, 2000 - px, step):
            if diff(pix[x, y], pix[x + px, y]) > TOL:
                bad += 1
    for y in range(13, 2000 - py, step):
        for x in range(13, 2000, step):
            if diff(pix[x, y], pix[x, y + py]) > TOL:
                bad += 1
    if bad:
        problems.append(f"{bad} sampled pixels differ under period shift")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=str(HTML_DEFAULT))
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()

    core = extract_core(Path(args.html).read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as td, sync_playwright() as pw:
        tdp = Path(td)
        browser = pw.chromium.launch()
        # 生成コアはDOMを触らないので、まっさらなページで動くはず
        gen = browser.new_page()
        shot = browser.new_page(viewport={"width": 2000, "height": 2000})

        def run(src, only=None, quiet=False):
            """コアを実行して24枚(または1柄ぶん)を検査し、{名前: 捕まえた検査の種類} を返す。"""
            jobs = gen.evaluate(RUNNER.replace("%CORE%", src))
            if only:
                jobs = [j for j in jobs if j["name"].startswith(only + "-")]
            caught = {}
            for j in jobs:
                svg = tdp / (j["name"] + ".svg")
                png = tdp / (j["name"] + ".png")
                svg.write_text(j["svg"], encoding="utf-8")
                shot.goto(svg.as_uri())
                shot.screenshot(path=str(png))
                probs = check_image(png, j["px"], j["py"])
                if probs:
                    caught[j["name"]] = kind_of(probs)
                if not quiet:
                    status = "OK " if not probs else "FAIL"
                    print(f"{status} {j['name']:<16} period {j['px']}x{j['py']}"
                          + ("  " + "; ".join(probs) if probs else ""))
            return len(jobs), caught

        if not args.sabotage:
            n, caught = run(core)
            browser.close()
            print(f"\n{n} cases, {len(caught)} failed")
            sys.exit(1 if caught else 0)

        # --sabotage: 仕込みごとに「捕まったか」と「どの検査が捕まえたか」を見る
        misses = []
        for name, only, pat, repl, expect in SABOTAGES:
            sab, n_sub = re.subn(pat, repl, core)
            if n_sub != 1:
                misses.append(f"{name}: 仕込みが当たらなかった(置換 {n_sub} 件)")
                print(f"NOT APPLIED  {name}")
                continue
            _, caught = run(sab, only=only, quiet=True)
            kinds = set().union(*caught.values()) if caught else set()
            if not caught:
                misses.append(f"{name}: どの検査にも捕まらなかった")
                print(f"MISSED       {name:<18} 期待={expect}")
            elif expect not in kinds:
                # 捕まってはいるが、狙った検査ではない別の検査が拾っている
                misses.append(f"{name}: 期待した検査({expect})では捕まらず {sorted(kinds)} が拾った")
                print(f"WRONG CHECK  {name:<18} 期待={expect} 実際={sorted(kinds)}")
            else:
                print(f"DETECTED     {name:<18} {expect} の検査が {len(caught)} 件で捕捉")
        browser.close()
        print(f"\n{len(SABOTAGES)} sabotages, {len(misses)} not properly detected")
        for m in misses:
            print("  - " + m)
        sys.exit(1 if misses else 0)


if __name__ == "__main__":
    main()
