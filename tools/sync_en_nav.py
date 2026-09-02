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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fix_lang_link import normalize, EN_MARKS  # noqa: E402

# ★2026-09-03: 手書きの3つの表(`PAIRS` / `ARRAY_PAIRS` / `NO_SYNC`)をやめた。
#
#   数えたら、**生成器23本のうち14本しか名前が無く、9本がどの表にも無かった**。
#   この9本は `en_nav.build`(実ページからナビを組み直す)を使っていて
#   **同期が要らないのは本当**だったが、**確かめてはいなかった**
#   (9/2 夜の「決めた と 見ていない は、あとから見分けがつかない」と同じ形)。
#   しかも「同期が要らない生成器」の表 `NO_SYNC` は4本ぶんだけ書かれていて、
#   **コードからは一度も読まれていなかった**(定義だけあって、使われていない)。
#
#   → **表を回すのをやめ、`make_en_*.py` を実在するぶん全部回す**。
#     どう扱うかは `en_pages.nav_mode()` が**生成器のソースを読んで**決める。
#     どれにも当てはまらない生成器は「不明」として**名前を出して落とす**。
#     これで「新しい生成器を表に足し忘れて黙って落ちる」が起こりようがない。
from en_pages import (ARRAY, JA_STATIC, LIVE, UNKNOWN,  # noqa: E402
                      all_generators, slug_of)

NAV_ARRAY = re.compile(r'var NAV_LINKS = \[.*?\n\];', re.S)

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
        # ★2026-08-28: 「もう一方の言語」への行は必ず最後に置く決まりなので、
        #   `</ul>` の直前ではなく**その行の手前**に入れる(add_tool_link.py と同じ扱い)。
        tail = re.search(r'\n( *<li><a [^\n]*(?:Japanese version|English version)[^\n]*</li>)\n    </ul>', new)
        if tail:
            # ⚠ tail.start(1) は行頭(字下げの前)を指す。ここに li.strip() をそのまま差すと
            #   新しい行が字下げゼロになり、うしろの行の字下げが二重になる
            #   (2026-08-28 に実際にやらかした。英語ページ13本で `<li>` が左端に出た)。
            new = new[:tail.start(1)] + "      " + li.strip() + "\n" + new[tail.start(1):]
        else:
            new = new.replace("    </ul>", "      " + li.strip() + "\n    </ul>", 1)
        print("  英語ナビに足した: %s ← %s" % (script, li.strip()))
        n += 1
    # 足したかどうかに関わらず、字下げと「言語の行は最後」を毎回そろえ直す
    body = re.search(r"(<ul>\n)(.*?)(\n    </ul>)", new, re.S)
    if body:
        fixed, _ = normalize(body.group(2), EN_MARKS, None)
        if fixed != body.group(2):
            new = new[:body.start()] + body.group(1) + fixed + body.group(3) + new[body.end():]
            print("  英語ナビの並び・字下げをそろえた: %s" % script)
            n += 1
    if not n:
        return src, 0
    return src[:e.start()] + new + src[e.end():], n


def sync_arrays(script, sp, docs, check, ja_slug, en_name):
    """JS配列のナビを持つ生成元を、実ページの配列でまるごと置き換える。ずれた数を返す。"""
    pages = [docs / ja_slug / "index.html", docs / "en" / en_name]
    live = []
    for page in pages:
        if not page.exists():
            print("  ページが無いので飛ばす: %s" % page)
            return 0
        m = NAV_ARRAY.search(page.read_text(encoding="utf-8"))
        if not m:
            print("  !! 実ページに NAV_LINKS が無い: %s" % page)
            return 1
        live.append(m.group(0))

    src = sp.read_text(encoding="utf-8")
    found = list(NAV_ARRAY.finditer(src))
    if len(found) != len(live):
        print("  !! 生成元の NAV_LINKS が %d 個(実ページは %d 個): %s"
              % (len(found), len(live), script))
        return 1

    drift = 0
    for m, want in zip(reversed(found), reversed(live)):   # 後ろから差し替えて位置をずらさない
        if m.group(0) == want:
            continue
        print("  ずれていた（JS配列ナビ）: %s" % script)
        drift += 1
        if not check:
            src = src[:m.start()] + want + src[m.end():]
    if drift and not check:
        sp.write_text(src, encoding="utf-8")
    return drift


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

    # ★表ではなく、実在する生成器を全部回す(足し忘れが起こりようがない形)
    tally = {}
    for script, en_name, mode in all_generators(here):
        sp = here / script
        slug = slug_of(en_name) if en_name else None
        tally[mode] = tally.get(mode, 0) + 1

        if en_name is None or slug is None:
            print("  ★ en_pages.PAGES に対応が無い生成器: %s" % script)
            drift += 1
            continue
        if mode == UNKNOWN:
            print("  ★ ナビの持ち方が分からない生成器: %s"
                  "(日本語ナビ・英語ナビ・JS配列・en_nav.build のどれも見つからない)" % script)
            drift += 1
            continue
        if mode == LIVE:
            continue                       # 差し替え元を持たない = ずれようがない
        if mode == ARRAY:
            drift += sync_arrays(script, sp, docs, args.check, slug, en_name)
            continue

        src = sp.read_text(encoding="utf-8")
        if mode == JA_STATIC:
            page = docs / slug / "index.html"
            if not page.exists():
                print("  ページが無いので飛ばす: %s" % page)
                continue
            live = PAGE_NAV.search(page.read_text(encoding="utf-8"))
            if not live:
                print("  !! 実ページにナビが無い: %s" % page)
                drift += 1
                continue
            m = JA_NAV.search(src)
            if not m:
                print("  !! 生成元に日本語ナビが無い: %s" % script)
                drift += 1
            elif m.group(0) != live.group(0):
                print("  ずれていた（日本語ナビ）: %s" % script)
                drift += 1
                if not args.check:
                    src = src[:m.start()] + live.group(0) + src[m.end():]

        src, n = add_en_links(script, src, args.add_en)
        drift += n
        if not args.check:
            sp.write_text(src, encoding="utf-8")

    # ⚠ 見た本数と内訳を必ず出す(9/1〜9/2 に「見ていないことを黙る」検査が4件出たため)
    print("見た生成器: %d 本 — %s"
          % (sum(tally.values()), " / ".join("%s %d" % kv for kv in sorted(tally.items()))))
    print("見ていない範囲: 生成器を持たない手書きページ(char-counter・timezone)の英語ナビ")
    print("ずれ: %d 箇所" % drift)
    return 1 if (args.check and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
