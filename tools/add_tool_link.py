#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新しい道具を作ったとき、既存の全ページの「ほかの道具」ナビに1行足す。

2026-08-24 新設。これまでは道具が増えるたびに21本のJPページ+10本のENページを
手で1つずつ編集していた(実際、8/23〜8/24に生成スクリプトのナビが実ページから
2世代ぶんずれる事故を2回起こしている)。手で書き写すからずれるので、機械にする。

`<nav class="hl-nav">`の中の最初の`</ul>`だけを対象にする(`<details>`内の`<ul>`や
`<ul class="notes">`など、同じインデントの別の`</ul>`を誤って拾わないため、
まずナビのブロックそのものを正規表現で切り出してから、その中だけを操作する)。

使い方:
  python lab/scripts/add_tool_link.py \
    --docs docs \
    --jp-link '<li><a href="../password/">パスワード生成・強度診断</a></li>' \
    --en-link '<li><a href="./password.html">Password Generator &amp; Strength Check</a></li>' \
    --skip password \
    --skip-en password.html

`--docs/en/index.html` と トップの `docs/index.html` はカード形式で構造が違うので対象外
(そちらは手で足すか、別の一覧生成の仕組みに任せる)。
"""
import argparse
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

JA_NAV = re.compile(r'(  <nav class="hl-nav">\n    <h2>ほかの道具</h2>\n    <ul>\n)(.*?)(\n    </ul>)', re.S)
EN_NAV = re.compile(r'(  <nav class="hl-nav">\n    <h2>Other tools</h2>\n    <ul>\n)(.*?)(\n    </ul>)', re.S)


#   ★2026-08-27追記: ナビを JS の配列(`NAV_LINKS`)で組み立てているページがある
#   (password の日英)。静的な `<ul>` しか見ていなかったので、24本目を足したとき
#   **日英とも黙って取りこぼした**。「見つからない」と出たのに数だけ見て通り過ぎると
#   気づけない形なので、こちらも機械で面倒を見る。
NAV_ARRAY = re.compile(r'(var NAV_LINKS = \[\n)(.*?)(\n\];)', re.S)
LI_LINK = re.compile(r'<li><a href="([^"]+)">(.*?)</a></li>')


#   ★2026-08-28追記: **もう一方の言語への導線は、必ずナビの最後**という決まりがある。
#   JS配列のほう(`patch_nav_array`)はその面倒を見ていたのに、**静的な `<ul>` のほうは
#   末尾に足すだけ**だったので、24本目のときに13ページで
#   `Japanese version` の下に新しい道具がぶら下がった(この日に実際に踏んだ)。
#   同じ決まりは1か所にまとめて、両方から呼ぶ。
TAIL_MARKERS = ("English version", "Japanese version", "日本語版", "英語版")


def is_tail(line):
    return any(m in line for m in TAIL_MARKERS)


def insert_before_tail(body, link):
    """ナビの本体に1行足す。末尾が「もう一方の言語」への行なら、その手前に入れる。"""
    lines = body.rstrip("\n").split("\n")
    entry = "      " + link.strip()
    if lines and is_tail(lines[-1]):
        lines.insert(len(lines) - 1, entry)
    else:
        lines.append(entry)
    return "\n".join(lines)


def patch_nav_array(path, link, text):
    """`var NAV_LINKS = [ ["href","ラベル"], ... ];` の形のナビに1件足す。"""
    m = NAV_ARRAY.search(text)
    if not m:
        return None
    lm = LI_LINK.search(link)
    if not lm:
        return "!! リンクの形が読めない"
    href, label = lm.group(1), lm.group(2)
    if ('"%s"' % href) in m.group(2):
        return "既にある"
    body = m.group(2).rstrip()
    # 末尾が英語版/日本語版への行なら、その手前に入れる(その行は最後に置く決まり)
    lines = body.split("\n")
    entry = '  ["%s", "%s"],' % (href, label)
    tail_marker = ("English version" in lines[-1]) or ("Japanese version" in lines[-1]) \
        or ("日本語版" in lines[-1])
    if tail_marker:
        last = lines[-1]
        if not last.rstrip().endswith(","):
            last_body = last.rstrip()
            lines[-1] = entry
            lines.append(last_body)
        else:
            lines.insert(len(lines) - 1, entry)
    else:
        if lines[-1].rstrip().endswith(","):
            lines.append(entry)
        else:
            lines[-1] = lines[-1].rstrip() + ","
            lines.append(entry.rstrip(","))
    new_body = "\n".join(lines)
    new_text = text[:m.start()] + m.group(1) + new_body + m.group(3) + text[m.end():]
    path.write_text(new_text, encoding="utf-8")
    return "追加した(JS配列)"


def patch(path, pattern, link, label):
    text = path.read_text(encoding="utf-8")
    if link.strip() in text:
        return "既にある"
    m = pattern.search(text)
    if not m:
        r = patch_nav_array(path, link, text)
        if r:
            return r
        return "!! ナビが見つからない"
    new_body = insert_before_tail(m.group(2), link)
    new_text = text[:m.start()] + m.group(1) + new_body + m.group(3) + text[m.end():]
    path.write_text(new_text, encoding="utf-8")
    return "追加した"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--jp-link", required=True)
    # ★2026-09-01追記: 25本目(和柄パターン)が**英語版を持たない初めての道具**だった。
    # それまでの24本は必ず日英そろえて出していたので、この引数は必須で書いてあった。
    # 英語版が無い道具のリンクを EN ページのナビに足すと、そこだけリンク切れになる。
    ap.add_argument("--en-link", help="ENページのナビに足す行(--no-en のときは不要)")
    ap.add_argument("--no-en", action="store_true", help="英語版がまだ無い道具。ENページには足さない")
    ap.add_argument("--skip", action="append", default=[], help="このスラッグのJPページは対象外(自分自身)")
    ap.add_argument("--skip-en", action="append", default=[], help="このファイル名のENページは対象外(自分自身)")
    args = ap.parse_args()
    if not args.no_en and not args.en_link:
        ap.error("--en-link は必須です(英語版がまだ無いなら --no-en を付ける)")

    docs = pathlib.Path(args.docs)
    n_jp = n_en = 0

    for p in sorted(docs.glob("*/index.html")):
        slug = p.parent.name
        if slug in ("en",) or slug in args.skip:
            continue
        state = patch(p, JA_NAV, args.jp_link, slug)
        print("JP %-16s %s" % (slug, state))
        if state == "追加した":
            n_jp += 1

    en_dir = docs / "en"
    if args.no_en:
        print("EN: --no-en のため対象外(英語版を出したら、そのとき足すこと)")
    elif en_dir.exists():
        for p in sorted(en_dir.glob("*.html")):
            if p.name in ("index.html",) or p.name in args.skip_en:
                continue
            state = patch(p, EN_NAV, args.en_link, p.name)
            print("EN %-16s %s" % (p.name, state))
            if state == "追加した":
                n_en += 1

    print("\nJP: %d ページに追加 / EN: %d ページに追加" % (n_jp, n_en))
    return 0


if __name__ == "__main__":
    sys.exit(main())
