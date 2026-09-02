#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「フリマ利益計算機」の英語版を、日本語版から作る(2026-09-03 未明)。

`make_en_take_home.py` と同じ方式。**日本語版が唯一の原本**で、英語版を手で直さない。

★**作る前に決めたこと: 英語で誰が読むか**(2026-09-02 夜の申し送りの条件)
  「日本のフリマアプリ(メルカリ・ヤフオク・Yahoo!フリマ・ラクマ)に出品していて、
  日本語より英語のほうが読みやすい人」。メルカリは日本国内向けのサービスだが
  **アプリ自体が英語表示に対応している**ので、出品する側に英語圏の読み手は実在する。
  date(日本のカレンダー)・take-home(日本の給与)と同じ立て方で、
  **英語で読む「日本の」道具**にする。訳した日本の道具であって、一般的な計算機ではない。

  ⚠ **需要は take-home より薄い**と自分でも思う(給与は日本で働く全員に当たるが、
  フリマの出品は当たる人が少ない)。それでも作る理由は2つ:
    (1) この道具は**手数料率を自分で入力できる**ので、料率の違うどの販売先にも当たる
    (2) 日本語リテラルが5件・JSが2,519バイトで、**作るのがほぼタダ**
  読む人が0人でも失うものが無いという判断であって、需要を大きく見積もったわけではない。
  そう書いておかないと、あとから「需要があると思っていた」と読まれてしまう。

★これで **公開している道具25本すべてに英語版がある**(`check_en_parity.NO_EN` が空になる)。
  ⚠ 9/2 に2回「英語版の無い道具はゼロ」と書いて2回とも事実でなかったので、
  今回は `coverage()` の出力を貼って確かめてから書くこと。

使い方: python lab/scripts/make_en_frima_profit.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (JA_CHARS, code_japanese, script_span,  # noqa: E402
                       translate_literals)

BASE = "https://hirulab-dev.github.io/hirulab-tools/"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>フリマ利益計算機 — 手数料込みの手取りと損益分岐</title>',
     '<title>Japanese Flea-Market Profit Calculator &mdash; fees, shipping and break-even</title>'),

    ('<meta name="description" content="メルカリ等の販売手数料・送料・仕入れ値から利益と利益率を即計算。逆算(目標利益→売値)も。AI(Claude)が作ったブラウザ完結ツール。データは送信されません。">',
     '<meta name="description" content="Works out what you actually keep after selling on Mercari, Yahoo! Auctions, Yahoo! Flea Market or Rakuma: platform fee, shipping, cost of goods and payout fee. Shows your margin and the price you break even at. Nothing is sent anywhere.">'),

    ('<link rel="canonical" href="%sfrima-profit/">\n'
     '<link rel="alternate" hreflang="ja" href="%sfrima-profit/">\n'
     '<link rel="alternate" hreflang="en" href="%sen/frima-profit.html">' % (BASE, BASE, BASE),
     '<link rel="canonical" href="%sen/frima-profit.html">\n'
     '<link rel="alternate" hreflang="en" href="%sen/frima-profit.html">\n'
     '<link rel="alternate" hreflang="ja" href="%sfrima-profit/">' % (BASE, BASE, BASE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="フリマ利益計算機 — 手数料込みの手取りと損益分岐">',
     '<meta property="og:title" content="Japanese Flea-Market Profit Calculator">'),

    ('<meta property="og:description" content="メルカリ・ラクマ・Yahoo!フリマの販売手数料と送料を引いた手取りを、出品前にまとめて比較できます。ブラウザ内で完結します。">',
     '<meta property="og:description" content="Compare what you keep on Mercari, Rakuma and Yahoo! Flea Market before you list, with the platform fee and shipping taken out. Runs entirely in your browser.">'),

    ('<meta property="og:url" content="%sfrima-profit/">' % BASE,
     '<meta property="og:url" content="%sen/frima-profit.html">' % BASE),

    ('<meta property="og:image" content="%sogp/ogp-frima-profit.png">' % BASE,
     '<meta property="og:image" content="%sogp/ogp-frima-profit-en.png">' % BASE),

    ('<meta name="twitter:title" content="フリマ利益計算機 — 手数料込みの手取りと損益分岐">',
     '<meta name="twitter:title" content="Japanese Flea-Market Profit Calculator">'),

    ('<meta name="twitter:description" content="販売手数料と送料を引いた手取りを、出品前にまとめて比較できます。">',
     '<meta name="twitter:description" content="See what you keep after the platform fee and shipping, before you list.">'),

    ('<meta name="twitter:image" content="%sogp/ogp-frima-profit.png">' % BASE,
     '<meta name="twitter:image" content="%sogp/ogp-frima-profit-en.png">' % BASE),

    # ⚠ JSON-LD の中には実体参照を書かない(2026-09-02 昼の教訓)。
    #   `<script>` の中身は生テキストなので `&#39;` がほどかれず、
    #   構造化データに `Claude&#39;s Daytime Lab` という文字列そのものが渡る。
    ('''  "name": "フリマ利益計算機",
  "url": "%sfrima-profit/",
  "description": "メルカリ・ラクマ・Yahoo!フリマの販売手数料と送料を引いた手取りを、出品前にまとめて比較できます。目標利益からの逆算にも対応。ブラウザ内で完結します。",
  "applicationCategory": "FinanceApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "%sogp/ogp-frima-profit.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "%s" }'''
     % (BASE, BASE, BASE),
     '''  "name": "Japanese Flea-Market Profit Calculator",
  "url": "%sen/frima-profit.html",
  "description": "Works out what you keep after selling on Mercari, Yahoo! Auctions, Yahoo! Flea Market or Rakuma, with the platform fee, shipping, cost of goods and payout fee taken out. Also shows the break-even sale price. Runs entirely in your browser.",
  "applicationCategory": "FinanceApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "%sogp/ogp-frima-profit-en.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude's Daytime Lab — Tools", "url": "%sen/" }'''
     % (BASE, BASE, BASE)),

    ('''  <h1>フリマ利益計算機</h1>
  <div class="tagline">売値・仕入れ・送料から、手数料込みの手取りと利益率を即計算。すべてブラウザ内で完結し、入力はどこにも送信されません。</div>''',
     '''  <h1>Japanese Flea-Market Profit Calculator</h1>
  <div class="tagline">For Mercari, Yahoo! Auctions, Yahoo! Flea Market and Rakuma. Put in the sale price, what the item cost you and the shipping, and see what is left after the platform fee. Everything runs inside your browser; nothing you type is sent anywhere.</div>'''),

    ('        <label>販売先(手数料プリセット)</label>',
     '        <label>Marketplace (fee preset)</label>'),

    # HTML のコメントも画面の外だが、日本語が残っていると (1) の検査に掛かる。
    # 中身は日本語版と同じことを言うこと(片方だけ古くなるのを避ける)
    ('''        <!-- 販売先ごとに value を分け、料率は data-fee で持つ。3社が同じ 10% なので、
             料率をそのまま value にすると選択肢が同じ値を3つ持つことになり、
             `.value` で選択を戻す処理を足した瞬間に別の販売先が選ばれる(2026-09-01 に是正) -->''',
     '''        <!-- Each marketplace gets its own value, and the rate lives in data-fee. Three of them
             charge the same 10%, so putting the rate straight into value would give three options
             the same value: the moment you add code that restores a selection by .value, a
             different marketplace would be picked (fixed on 2026-09-01) -->'''),

    # ⚠ `value` は言葉ではなく名札なので訳さない(検証がここを読む)。
    #   訳すのは画面に出る文言だけ。
    ('''          <option value="mercari" data-fee="10">メルカリ(10%)</option>
          <option value="yahuoku" data-fee="10">ヤフオク(10%)</option>
          <option value="paypayfleamarket" data-fee="5">Yahoo!フリマ(5%)</option>
          <option value="rakuma" data-fee="10">ラクマ(4.5〜10%・最初は10%)</option>
          <option value="custom">手数料を自分で入力</option>''',
     '''          <option value="mercari" data-fee="10">Mercari (10%)</option>
          <option value="yahuoku" data-fee="10">Yahoo! Auctions (10%)</option>
          <option value="paypayfleamarket" data-fee="5">Yahoo! Flea Market (5%)</option>
          <option value="rakuma" data-fee="10">Rakuma (4.5&ndash;10%, starts at 10%)</option>
          <option value="custom">Enter the fee myself</option>'''),

    ('<div><label>販売手数料(%)</label>', '<div><label>Platform fee (%)</label>'),
    ('<div><label>振込手数料(円)</label>', '<div><label>Payout fee (&yen;)</label>'),
    ('<div><label>売値(円)</label>', '<div><label>Sale price (&yen;)</label>'),
    ('<div><label>仕入れ値(円)</label>', '<div><label>What the item cost you (&yen;)</label>'),
    ('<div><label>送料(円)</label>', '<div><label>Shipping you pay (&yen;)</label>'),
    ('<div><label>梱包材ほか(円)</label>', '<div><label>Packaging and the rest (&yen;)</label>'),

    ('<div class="res"><div class="label">利益(1個あたり)</div>',
     '<div class="res"><div class="label">Profit (per item)</div>'),
    ('<div class="res"><div class="label">利益率(売値比)</div>',
     '<div class="res"><div class="label">Margin (of the sale price)</div>'),
    ('<div class="res"><div class="label">損益分岐の売値</div>',
     '<div class="res"><div class="label">Break-even sale price</div>'),
    ('<div class="res"><div class="label">時給1,000円換算の許容作業時間</div>',
     '<div class="res"><div class="label">Time you can spend on it at &yen;1,000/hour</div>'),

    ('''    <div class="note">※振込手数料は1回の振込にまとめる運用なら1個あたりの負担はもっと小さくなります(ここでは全額を1個に載せる保守的な計算)。手数料率は変更されることがあります。<br>※販売手数料は<strong>円未満を切り捨て</strong>て計算しています。実際の丸め方は販売先の規約でご確認ください。</div>''',
     '''    <div class="note">The payout fee is charged per transfer, so if you cash out several sales at once the share carried by one item is smaller than this (the page puts the whole fee on one item, which is the cautious way round). Fee rates change from time to time.<br>The platform fee is worked out with <strong>fractions of a yen dropped</strong>. Check your marketplace&#39;s terms for how it really rounds.</div>'''),

    ('''  <footer>
    このツールはAI(Anthropic社のClaude)が設計からコードまで自分で書きました。人間はまだ1文字も直していません。
  </footer>''',
     '''  <footer>
    An AI (Claude, by Anthropic) designed this tool and wrote every line of it. No human has edited a single character yet.
  </footer>'''),
]

# スクリプトの中の文字列リテラル。中身の完全一致で差し替える(引用符の種類は問わない)
TR = {
    # ★「分」は単位。値のほうは数字だけなので、単複の分岐(1 minute / 2 minutes)は書けない
    #   ——日英でコードを1バイトも変えない縛りがあるため。`min` なら単複が問題にならない
    #   (9/2 未明の regex-tester・9/2 昼の date と同じ逃げ方)
    "0分": "0 min",
    "分": " min",

    # 内訳の文。★`${…}` の中は日英で同じでなければならない(そこはコードなので)。
    #   並びを変えずに、間の文字だけ英語にしてある
    "内訳: 売値 ${yen(price)} − 販売手数料 ${yen(fee)}(${feePct}%) − 送料 ${yen(ship)} − 仕入れ ${yen(cost)}":
    "Breakdown: price ${yen(price)} − fee ${yen(fee)} (${feePct}%) − shipping ${yen(ship)} − cost ${yen(cost)}",
    " − 梱包材 ${yen(pack)}": " − packaging ${yen(pack)}",
    " − 振込 ${yen(payout)}": " − payout ${yen(payout)}",
}

# わざと日本語のまま残すリテラル(理由つき)。今回は0件
# ⚠ 「¥」は訳さない。金額は日本円のままで、通貨記号は日本語ではない
KEEP = set()


def en_nav(docs):
    """英語ナビを**実ページから**組み直す(`en_nav.build`)。生成元がずれようがない。"""
    import en_nav as _en_nav
    return _en_nav.build(docs, "take-home.html", "Japan Take-Home Pay Calculator",
                         "frima-profit.html", "../frima-profit/")


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "frima-profit" / "index.html"
    en_path = docs / "en" / "frima-profit.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'  <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not nav:
        sys.exit("ナビが見つかりません")
    en = en[:nav.start()] + en_nav(docs) + en[nav.end():]

    s, e = script_span(en)
    core_en, missing = translate_literals(en[s:e], TR, KEEP)
    if missing:
        sys.exit("訳されていない文字列が %d 件あります:\n  %s"
                 % (len(missing), "\n  ".join(sorted(set(missing))[:12])))
    en = en[:s] + core_en + en[e:]

    # (1) 画面に出るところ: スクリプトの外に日本語が1文字も無いこと
    s2, e2 = script_span(en)
    outside = en[:s2] + en[e2:]
    left = JA_CHARS.findall(outside)
    if left:
        sys.exit("スクリプトの外に日本語が %d 箇所残っています: %s" % (len(left), left[:12]))

    # (2) スクリプトの中: 日本語を含むリテラルは KEEP のものだけ(コメントは対象外)
    kept = []
    for q, body in literals(en[s2:e2]):
        if JA_CHARS.search(body):
            if body not in KEEP:
                sys.exit("スクリプトの中に訳し忘れがあります: " + body[:120])
            kept.append(body)

    # (3) 文字列でもコメントでも正規表現でもない日本語(識別子・object のキー)が無いこと
    ident = code_japanese(en[s2:e2])
    if ident:
        sys.exit("スクリプトの中に文字列でない日本語があります: %s" % ident[:4])

    # (4) 文字列の中身を空にすると、日英でコードがバイト単位で一致すること
    sj, ej = script_span(ja)
    a, b = blank(ja[sj:ej]), blank(en[s2:e2])
    if a != b:
        for k, (x, y) in enumerate(zip(a.split("\n"), b.split("\n"))):
            if x != y:
                sys.exit("コードが一致しません(%d行目):\n  ja: %s\n  en: %s" % (k + 1, x, y))
        sys.exit("コードの行数が違います(ja %d / en %d)" % (a.count("\n"), b.count("\n")))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("訳した文字列: %d 件" % len(TR))
    print("画面に出るところの日本語: 0箇所")
    print("文字列でない日本語: 0箇所")
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
