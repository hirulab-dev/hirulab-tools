#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「コントラスト比チェッカー」の英語版を、日本語版から作る(2026-08-28)。

`make_en_cron.py` / `make_en_qr.py` / `make_en_base64.py` と同じ方式。
**日本語版が唯一の原本**で、英語版を手で直すことはしない。

1. HTML(head・本文・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. できた英語版について、**「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**
   ことを確かめる。通れば、色の解析・WCAGの比の計算・APCA・色覚特性の変換・修正案の探索は
   1バイトも違わない = 日本語版で確かめたことがそのまま英語版にも効く
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

★この回の選び方: 英語版が無い日本語ツールは9本あり、前の枠が「JSの日本語リテラルが
  少ない順」に並べていた(frima-profit 2 / page-contrast 8 / contrast 8 / …)。
  ただし **frima-profit(メルカリ・ラクマの手数料)・take-home(日本の社会保険)・
  date(和暦・祝日)は、英語にしても読む人がいない**。軽さだけで選ぶと、
  いちばん軽いものから順に「誰も読まないページ」が増える。
  → 「万国共通で、かつ軽い」で取り直して contrast を選んだ。

★ナビは**実ページ(`docs/en/cron.html`)から実行時に拾う**ので、生成元がずれようがない
  (`make_en_headers/jwt/base64/cron` と同じ)。

使い方: python lab/scripts/make_en_contrast.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (JA_CHARS, code_japanese, script_span,  # noqa: E402
                       translate_comments,
                       translate_literals)

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>コントラスト比チェッカー — WCAG 2.1 / 3.0(APCA)対応</title>',
     '<title>Contrast Ratio Checker — WCAG 2.1 AA / AAA, with APCA for reference</title>'),

    ('<meta name="description" content="文字色と背景色のコントラスト比をその場で判定。WCAG 2.1のAA/AAA基準に加え、色覚特性シミュレーションと自動修正提案つき。AI(Claude)が作ったブラウザ完結ツール。データは送信されません。">',
     '<meta name="description" content="Checks the contrast ratio between a text colour and a background colour as you type. WCAG 2.1 AA and AAA, colour vision deficiency simulation, and a suggested colour that actually passes. Built by an AI (Claude); everything runs in the browser and nothing is ever sent anywhere.">'),

    ('''  /* バッジは white-space:nowrap なので2列固定だと375px幅で19pxはみ出す。
     .badges の定義より後ろに置くこと（同じ詳細度なので、前に書くと負ける） */''',
     '''  /* The badges are white-space:nowrap, so a fixed two-column grid overflows by 19px at 375px.
     This has to come after the .badges rule — same specificity, so an earlier rule loses. */'''),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/contrast/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/contrast/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/contrast.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/contrast.html">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/contrast.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/contrast/">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="コントラスト比チェッカー — クロードの昼ラボ">',
     '<meta property="og:title" content="Contrast Ratio Checker">'),

    ('<meta property="og:description" content="文字色と背景色のコントラスト比をWCAG 2.1のAA/AAAで判定。色覚特性シミュレーションと改善案つき。">',
     '<meta property="og:description" content="Checks a text colour against a background colour with WCAG 2.1 AA and AAA, simulates colour vision deficiency, and suggests a colour that passes.">'),

    ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/contrast/">',
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/contrast.html">'),

    ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-contrast.png">',
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-contrast-en.png">'),

    ('<meta name="twitter:title" content="コントラスト比チェッカー — クロードの昼ラボ">',
     '<meta name="twitter:title" content="Contrast Ratio Checker">'),

    ('<meta name="twitter:description" content="文字色と背景色のコントラスト比をWCAG 2.1のAA/AAAで判定。色覚特性シミュレーションと改善案つき。">',
     '<meta name="twitter:description" content="WCAG 2.1 AA / AAA for any pair of colours, with colour vision deficiency simulation and a fix that passes.">'),

    ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-contrast.png">',
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-contrast-en.png">'),

    ('''  "name": "コントラスト比チェッカー",
  "url": "https://hirulab-dev.github.io/hirulab-tools/contrast/",
  "description": "文字色と背景色のコントラスト比を WCAG 2.1 の AA/AAA で判定し、色覚特性のシミュレーションと修正案を出します。",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "JPY"
  },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-contrast.png",
  "author": {
    "@type": "Organization",
    "name": "クロードの昼ラボ",
    "url": "https://note.com/hirulab"
  },
  "isPartOf": {
    "@type": "WebSite",
    "name": "クロードの昼ラボ — ツール置き場",
    "url": "https://hirulab-dev.github.io/hirulab-tools/"
  }''',
     '''  "name": "Contrast Ratio Checker",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/contrast.html",
  "description": "Works out the contrast ratio between a text colour and a background colour, judges it against WCAG 2.1 AA and AAA, simulates colour vision deficiency and suggests a colour that passes.",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-contrast-en.png",
  "author": {
    "@type": "Organization",
    "name": "Claude's Daytime Lab",
    "url": "https://note.com/hirulab"
  },
  "isPartOf": {
    "@type": "WebSite",
    "name": "Claude\'s Daytime Lab — Tools",
    "url": "https://hirulab-dev.github.io/hirulab-tools/en/"
  }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>コントラスト比チェッカー</h1>
  <div class="tagline">文字色と背景色を入れるだけ。WCAG 2.1 の AA / AAA 判定、色覚特性シミュレーション、基準を満たす色の自動提案まで。すべてブラウザ内で完結し、入力した値はどこにも送信されません。</div>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>Contrast Ratio Checker</h1>
  <div class="tagline">Type in a text colour and a background colour. You get the WCAG 2.1 AA / AAA verdict, a colour vision deficiency simulation, and a suggested colour that actually passes. Everything happens inside the browser and the values you type are never sent anywhere.</div>'''),

    ('      <div class="label">文字色 (foreground)</div>',
     '      <div class="label">Text colour (foreground)</div>'),

    ('      <div class="label">背景色 (background)</div>',
     '      <div class="label">Background colour</div>'),

    ('spellcheck="false" aria-label="文字色">', 'spellcheck="false" aria-label="Text colour">'),
    ('spellcheck="false" aria-label="背景色">', 'spellcheck="false" aria-label="Background colour">'),

    ('    <button id="swap">⇅ 入れ替え</button>\n'
     '    <button id="rand">🎲 ランダム</button>\n'
     '    <button id="copy-css">CSSをコピー</button>',
     '    <button id="swap">&#8645; Swap</button>\n'
     '    <button id="rand">&#127922; Random</button>\n'
     '    <button id="copy-css">Copy CSS</button>'),

    ('''      <div class="badge"><span class="pill" id="p-aa-n">—</span> AA 通常テキスト <span style="color:var(--sub)">4.5:1</span></div>
      <div class="badge"><span class="pill" id="p-aaa-n">—</span> AAA 通常テキスト <span style="color:var(--sub)">7:1</span></div>
      <div class="badge"><span class="pill" id="p-aa-l">—</span> AA 大きい文字 <span style="color:var(--sub)">3:1</span></div>
      <div class="badge"><span class="pill" id="p-aaa-l">—</span> AAA 大きい文字 <span style="color:var(--sub)">4.5:1</span></div>
      <div class="badge"><span class="pill" id="p-ui">—</span> UI部品・図形 <span style="color:var(--sub)">3:1</span></div>
      <div class="badge"><span class="pill" id="p-apca">—</span> APCA(参考) <span style="color:var(--sub)" id="apca-val"></span></div>''',
     '''      <div class="badge"><span class="pill" id="p-aa-n">&mdash;</span> AA normal text <span style="color:var(--sub)">4.5:1</span></div>
      <div class="badge"><span class="pill" id="p-aaa-n">&mdash;</span> AAA normal text <span style="color:var(--sub)">7:1</span></div>
      <div class="badge"><span class="pill" id="p-aa-l">&mdash;</span> AA large text <span style="color:var(--sub)">3:1</span></div>
      <div class="badge"><span class="pill" id="p-aaa-l">&mdash;</span> AAA large text <span style="color:var(--sub)">4.5:1</span></div>
      <div class="badge"><span class="pill" id="p-ui">&mdash;</span> UI parts &amp; graphics <span style="color:var(--sub)">3:1</span></div>
      <div class="badge"><span class="pill" id="p-apca">&mdash;</span> APCA (reference) <span style="color:var(--sub)" id="apca-val"></span></div>'''),

    ('''    <div class="big">大きい文字のサンプル(24px相当)</div>
    <div class="small">通常サイズの本文テキストです。The quick brown fox jumps over the lazy dog. 0123456789</div>
    <div class="tiny">注釈やキャプションに使う小さめの文字</div>''',
     '''    <div class="big">Large text sample (equivalent to 24px)</div>
    <div class="small">Body text at the usual size. The quick brown fox jumps over the lazy dog. 0123456789</div>
    <div class="tiny">The smaller size used for notes and captions</div>'''),

    ('  <h2>色覚特性シミュレーション</h2>', '  <h2>Colour vision deficiency simulation</h2>'),

    ('  <h2>AA(4.5:1)を満たす修正案</h2>', '  <h2>A fix that reaches AA (4.5:1)</h2>'),

    ('''  <h2>「大きい文字」の定義(WCAG 2.1)</h2>
  <table>
    <tr><th>条件</th><th>該当サイズ</th></tr>
    <tr><td>通常の太さ</td><td>18pt 以上(= 24px 以上)</td></tr>
    <tr><td>太字(bold)</td><td>14pt 以上(= 18.66px 以上)</td></tr>
    <tr><td>日本語の場合</td><td>WCAG は 22px 以上(太字は 18px 以上)を目安として示している</td></tr>
  </table>''',
     '''  <h2>What WCAG 2.1 counts as &ldquo;large text&rdquo;</h2>
  <table>
    <tr><th>Weight</th><th>Size that qualifies</th></tr>
    <tr><td>Normal weight</td><td>18pt or larger (= 24px or larger)</td></tr>
    <tr><td>Bold</td><td>14pt or larger (= 18.66px or larger)</td></tr>
    <tr><td>Japanese text</td><td>WCAG gives 22px or larger (18px if bold) as the guideline</td></tr>
  </table>'''),

    ('''    コントラスト比は WCAG 2.1 の相対輝度式で計算しています。APCA は WCAG 3.0 のドラフト指標で、まだ勧告ではないため参考値です。
    色覚特性シミュレーションは Brettel/Viénot 系の LMS 変換による近似で、実際の見え方を保証するものではありません。
    <br>作: <strong>クロードの昼ラボ</strong>(AIのClaudeが書いています) — このページは通信を一切行いません。''',
     '''    The contrast ratio uses the relative luminance formula from WCAG 2.1. APCA is a draft measure from WCAG 3.0 &mdash; it is not a recommendation yet, so it is shown for reference only.
    The colour vision deficiency simulation is an approximation using a Brettel/Vi&eacute;not-style LMS transform; it does not guarantee how anyone actually sees the colours.
    <br>Made by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) &mdash; this page makes no network requests at all.'''),
]

# スクリプトの中の文字列リテラル。中身の完全一致で差し替える(引用符の種類は問わない)
TR = {
    "一般的な色覚": "Typical colour vision",
    "1型(P型・赤)": "Protanopia (red)",
    "2型(D型・緑)": "Deuteranopia (green)",
    "3型(T型・青)": "Tritanopia (blue)",

    '<div class="sim"><div class="name">${name}</div>\n'
    '      <div class="swatch" style="background:${toHex(b)};color:${toHex(f)}">Aa あア亜 サンプル</div>\n'
    '      <div class="val">比 ${r.toFixed(2)}:1 / ${toHex(f)} on ${toHex(b)}</div></div>':
    '<div class="sim"><div class="name">${name}</div>\n'
    '      <div class="swatch" style="background:${toHex(b)};color:${toHex(f)}">Aa Bb 123 sample</div>\n'
    '      <div class="val">ratio ${r.toFixed(2)}:1 / ${toHex(f)} on ${toHex(b)}</div></div>',

    '<div class="empty">すでに AA(4.5:1)を満たしています。AAA(7:1)を狙うなら、下の入れ替え・ランダムで探索してみてください。</div>':
    '<div class="empty">This pair already clears AA (4.5:1). If you want AAA (7:1), try Swap or Random above to look for one.</div>',

    "文字色の明度を調整": "Adjust the lightness of the text colour",
    "背景色の明度を調整": "Adjust the lightness of the background",
    "文字を白か黒に": "Make the text white or black",

    '<button class="fix" data-fg="${f}" data-bg="${b}">\n'
    '        <div class="name">${name}</div>\n'
    '        <div class="sample" style="background:${b};color:${f}">Aa あア亜 サンプル</div>\n'
    '        <div class="val">${r.toFixed(2)}:1 — ${f} on ${b}</div>\n'
    '      </button>':
    '<button class="fix" data-fg="${f}" data-bg="${b}">\n'
    '        <div class="name">${name}</div>\n'
    '        <div class="sample" style="background:${b};color:${f}">Aa Bb 123 sample</div>\n'
    '        <div class="val">${r.toFixed(2)}:1 — ${f} on ${b}</div>\n'
    '      </button>',

    '<div class="empty">この組み合わせからは、色相を保ったまま AA に届く案が見つかりませんでした。色そのものを見直してください。</div>':
    '<div class="empty">No colour that keeps this hue reaches AA. The colours themselves need rethinking.</div>',

    "コピーしました": "Copied",
    "コピーできませんでした": "Could not copy",
}

# わざと日本語のまま残すリテラル(理由つき)。今回は0件
KEEP = set()

# ★2026-09-03 夜 追加(コメントも訳す)。⚠ 訳は行数を変えない・訳の中に日本語を書かない。
COMMENTS = {
    '/* ---------- 色のパース ---------- */': '/* ---------- Parsing colors ---------- */',
    '// ⚠ 2.55 を掛けると 50% が 127.49999999999999 になって 127 に落ちる(ブラウザは 128)。':
    '// Note: multiplying by 2.55 turns 50% into 127.49999999999999, which drops to 127 (browsers: 128).',
    '//    小数の指定も parseInt では切り捨てになる(1.5 → 1。ブラウザは 2)。どちらも 2026-09-01 修正。':
    '//    parseInt also truncates fractions (1.5 -> 1; browsers: 2). Both were fixed on 2026-09-01.',
    '/* ---------- WCAG 2.1 コントラスト比 ---------- */':
    '/* ---------- WCAG 2.1 contrast ratio ---------- */',
    '/* ---------- APCA(WCAG 3.0 ドラフト・参考値) ---------- */':
    '/* ---------- APCA (WCAG 3.0 draft, shown for reference) ---------- */',
    '/* ---------- 色覚特性シミュレーション(LMS空間での近似) ---------- */':
    '/* ---------- Color-vision simulation (approximated in LMS space) ---------- */',
    '/* ---------- 修正案の生成 ---------- */': '/* ---------- Building suggested fixes ---------- */',
    '/** 色相・彩度を保ったまま明度だけ動かして目標比に届く最も近い色を探す */':
    '/** Keep hue and saturation, move lightness only, find the nearest color that reaches the target */',
    '// 色覚特性': '// Color vision',
    '// 修正案': '// Suggested fixes',
}


def en_nav(docs):
    """英語ナビを**実ページから**組み立てる。

    `docs/en/cron.html` のナビを写し元にする。
    生成スクリプトが自前でナビを持たないので、実ページとずれようがない。

    ★2026-08-31: 写すのをやめて `en_nav.build` で**組み直す**ようにした。
    写すだけだと、写し元にあった自己リンク・重複がそのまま増える
    (実際 `en/contrast.html` が自分自身を、`en/image.html` が自分自身と
     `./contrast.html` の2つ目を抱えて本番に出ていた)。
    """
    import en_nav as _en_nav
    return _en_nav.build(docs, "cron.html", "Cron Expression Explainer",
                         "contrast.html", "../contrast/")






def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "contrast" / "index.html"
    en_path = docs / "en" / "contrast.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'    <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not nav:
        sys.exit("ナビが見つかりません")
    en = en[:nav.start()] + "  " + en_nav(docs) + en[nav.end():]

    s, e = script_span(en)
    core_en, missing = translate_comments(en[s:e], COMMENTS)
    if missing:
        sys.exit("訳されていないコメントが %d 件あります:\n  %s"
                 % (len(missing), "\n  ".join(m[:100] for m in missing[:8])))
    core_en, missing = translate_literals(core_en, TR, KEEP)
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

    # (3) 文字列の中身を空にすると、日英でコードがバイト単位で一致すること
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
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
