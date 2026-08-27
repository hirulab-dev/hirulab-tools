#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英語版の生成スクリプトが持っている「差し替え元のナビ」を、実ページから同期する。

2026-08-24 新設。前日に踏んだ事故の根治。
`make_en_*.py` は「日本語版のこの塊を、英語版のこの塊に差し替える」という対で書いてある。
ナビは道具が増えるたびに変わるので、**日本語ページだけ手で直して生成元を更新し忘れる**と、
生成スクリプトが黙って古いまま残る（次に走らせたときに「差し替え元が見つかりません」で
止まるので事故にはならないが、そのとき初めて2世代ぶんずれていたことに気づく）。

手で書き写すからずれるので、そこを機械にする。

やること:
1. 各 `make_en_*.py` の中の「ほかの道具」ナビ（＝日本語版の差し替え元）を、
   対応する実ページの `<nav class="hl-nav">…</nav>` でまるごと置き換える
2. 「Other tools」ナビ（＝英語版として書き出す側）に、指定した項目が入っているか確かめ、
   無ければ `</ul>` の直前に足す

使い方:
  python lab/scripts/sync_en_nav.py [--docs docs] [--add-en '<li><a href="./jwt.html">JWT Explainer</a></li>']
"""
import argparse
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 生成スクリプト名 → 日本語ページのスラッグ
PAIRS = {
    "make_en_railroad.py": "railroad",
    "make_en_regex_why.py": "regex-why",
    "make_en_replace.py": "replace",
    "make_en_url.py": "url",
    # None = 日本語ナビの同期は不要。`make_en_{headers,jwt,base64}.py` は差し替え元を持たず、
    # **実ページのナビを実行時に正規表現で拾って捨てる**ので構造的にずれない。
    # 英語ナビ（書き出す側）だけは静的なので --add-en の面倒を見る（2026-08-27）。
    "make_en_headers.py": None,
    "make_en_jwt.py": None,
    "make_en_base64.py": None,
}

JA_NAV = re.compile(r'  <nav class="hl-nav">\n    <h2>ほかの道具</h2>.*?\n  </nav>', re.S)
EN_NAV = re.compile(r'  <nav class="hl-nav">\n    <h2>Other tools</h2>.*?\n  </nav>', re.S)
PAGE_NAV = re.compile(r'  <nav class="hl-nav">.*?\n  </nav>', re.S)


def own_page(script):
    """生成スクリプト名から、それが書き出す英語ページの名前を出す。

    `make_en_regex_why.py` → `regex-why.html`。
    **自分自身へのリンクをナビに足してしまう事故を止めるため**に使う
    （2026-08-27、`make_en_base64.py` に `./base64.html` が入って実際に踏んだ）。
    """
    return script[len("make_en_"):-len(".py")].replace("_", "-") + ".html"


def add_en_links(script, src, add_en):
    """英語ナビ（書き出す側）に、まだ入っていない <li> を足す。(新しいsrc, 足した数)"""
    e = EN_NAV.search(src)
    if not e:
        print("  !! 生成元に英語ナビが無い: %s" % script)
        return src, 0
    block = new = e.group(0)
    n = 0
    for li in add_en:
        if li.strip() in new:
            continue
        if ('"./%s"' % own_page(script)) in li:
            print("  自分自身なので足さない: %s" % script)
            continue
        new = new.replace("    </ul>", "      " + li.strip() + "\n    </ul>", 1)
        print("  英語ナビに足した: %s ← %s" % (script, li.strip()))
        n += 1
    if not n:
        return src, 0
    return src[:e.start()] + new + src[e.end():], n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--add-en", action="append", default=[],
                    help="英語版ナビに入っていなければ足す <li> 行（そのまま書く）")
    ap.add_argument("--check", action="store_true", help="書き換えずに、ずれているかだけ見る")
    args = ap.parse_args()

    here = pathlib.Path(__file__).resolve().parent
    docs = pathlib.Path(args.docs)
    drift = 0

    for script, slug in PAIRS.items():
        sp = here / script
        if not sp.exists():
            continue
        if slug is None:
            src = sp.read_text(encoding="utf-8")
            new_src, n = add_en_links(script, src, args.add_en)
            drift += n
            if n and not args.check:
                sp.write_text(new_src, encoding="utf-8")
            continue
        page = docs / slug / "index.html"
        if not page.exists():
            print("  ページが無いので飛ばす: %s" % page)
            continue
        src = sp.read_text(encoding="utf-8")
        live = PAGE_NAV.search(page.read_text(encoding="utf-8"))
        if not live:
            print("  !! 実ページにナビが無い: %s" % page)
            drift += 1
            continue
        live_nav = live.group(0)

        m = JA_NAV.search(src)
        if not m:
            print("  !! 生成元に日本語ナビが無い: %s" % script)
            drift += 1
        elif m.group(0) != live_nav:
            print("  ずれていた（日本語ナビ）: %s" % script)
            drift += 1
            if not args.check:
                src = src[:m.start()] + live_nav + src[m.end():]

        src, n = add_en_links(script, src, args.add_en)
        drift += n

        if not args.check:
            sp.write_text(src, encoding="utf-8")

    print("ずれ: %d 箇所" % drift)
    return 1 if (args.check and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
