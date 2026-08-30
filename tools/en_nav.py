#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英語ページの「ほかの道具」ナビを、実ページから**組み直して**返す。

2026-08-31 新設。それまで各 `make_en_*.py` が持っていた `en_nav()` は
**隣の英語ページのナビをそのまま写して1行足す**だけだった。差し替え元を持たないので
「生成元が実ページから古くなる」事故は防げていたが、**写し元の傷もそのまま増える**。

実際に本番でこうなっていた(この日に発見):
  - `en/contrast.html` が自分自身をナビに載せている
  - `en/image.html` が自分自身を載せ、さらに `./contrast.html` を2つ持っている
    (= 写し元の contrast の自己リンクを引き継いだうえで、自分でもう1行足した)

写すのをやめて、**毎回ほどいて組み直す**ことにした:
  1. 写し元のナビから道具の行を全部取り出す
  2. 写し元自身への行を足す(写し元のナビには載っていないため)
  3. **これから作るページ自身への行を落とす**(自己リンクの根治)
  4. 同じ行き先を1つに畳む
  5. 「Japanese version」の行を必ず最後に置く

`check_site.py` の `nav_checks` が、出したあとの現物でも同じことを見張っている
(作る側と出す側の両方で見る。片方だけだと、手で直したページが黙って戻る)。
"""
import re
import sys

LI = re.compile(r'<li><a href="([^"]+)">(.*?)</a></li>')
NAV = re.compile(r'  <nav class="hl-nav">.*?\n  </nav>', re.S)


def build(docs, src_name, src_label, self_name, ja_href):
    """英語ナビの HTML(`  <nav …>…</nav>`)を返す。

    docs      … リポジトリの docs
    src_name  … 写し元にする英語ページのファイル名(例 "cron.html")
    src_label … その写し元ページの見出し(ナビに足す文言)
    self_name … これから作るページのファイル名(例 "page-contrast.html")。自己リンクを落とす
    ja_href   … 日本語版への相対URL(例 "../page-contrast/")
    """
    src = (docs / "en" / src_name).read_text(encoding="utf-8")
    m = NAV.search(src)
    if not m:
        sys.exit("docs/en/%s のナビが見つかりません" % src_name)
    nav = m.group(0)

    items = LI.findall(nav)
    if not any(label == "Japanese version" for _, label in items):
        sys.exit("docs/en/%s のナビに日本語版への行がありません" % src_name)

    tools = [(h, t) for h, t in items if t != "Japanese version"]
    tools.append(("./" + src_name, src_label))

    out, seen = [], set()
    for href, label in tools:
        if href == "./" + self_name:
            continue                      # 自己リンクは載せない
        if href in seen:
            continue                      # 同じ行き先は1つだけ
        seen.add(href)
        out.append('      <li><a href="%s">%s</a></li>' % (href, label))
    out.append('      <li><a href="%s">Japanese version</a></li>' % ja_href)

    head, tail = nav.split("<ul>", 1)
    return head + "<ul>\n" + "\n".join(out) + "\n    </ul>\n  </nav>"


def normalize(text):
    """すでに書き出してあるページのナビを、上と同じ決まりに揃え直す。

    自己リンクと重複を落とし、「Japanese version」を最後に置く。
    生成スクリプトを持たないページ(手で直したもの)を戻すために使う。
    直した件数と、直した中身の説明を返す。
    """
    m = NAV.search(text)
    if not m:
        return text, []
    nav = m.group(0)
    items = LI.findall(nav)
    ja = [(h, t) for h, t in items if t == "Japanese version"]
    tools = [(h, t) for h, t in items if t != "Japanese version"]

    fixed, out, seen = [], [], set()
    for href, label in tools:
        if href in seen:
            fixed.append("重複 %s" % href)
            continue
        seen.add(href)
        out.append('      <li><a href="%s">%s</a></li>' % (href, label))
    if ja:
        if len({h for h, _ in ja}) != len(ja):
            fixed.append("日本語版への行が %d 個" % len(ja))
        out.append('      <li><a href="%s">Japanese version</a></li>' % ja[0][0])

    head, _ = nav.split("<ul>", 1)
    new = head + "<ul>\n" + "\n".join(out) + "\n    </ul>\n  </nav>"
    if new == nav:
        return text, []
    return text[:m.start()] + new + text[m.end():], fixed
