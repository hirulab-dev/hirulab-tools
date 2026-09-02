#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「JSON整形・検証」の英語版を、日本語版から作る(2026-08-31)。

`make_en_contrast.py` / `make_en_image.py` / `make_en_page_contrast.py` /
`make_en_diff.py` と同じ方式。ナビは `en_nav.build` が**ほどいて組み直す**。
**日本語版が唯一の原本**で、英語版を手で直さない。

1. HTML(head・本文・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = 位置つきJSONパーサ・JSONC/JSON5 の除去・色付け・ツリーの組み立ては1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる
5. ★**コードの骨格(文字列・コメント・正規表現を外したもの)にも日本語が無い**ことを確かめる

★この回に固有の話: 5 はこの道具で必要になって新しく足した検査。
  見本のJSONが `収益: { 円: 0, 備考: "…" }` と**キーをクォートで囲わずに**書いてあり、
  日本語が**識別子**になっていた。識別子は文字列リテラルではないので 2 の辞書に載らず、
  スクリプトの中なので 4 にも掛からない。それでいて `JSON.stringify` すると画面に出る。
  → **日本語版のほうでキーをクォートで囲って**リテラルに変え、
  同じ抜けが二度と通らないように `make_en_contrast.code_japanese` を新設した。

★ もう1つ: `localeCompare(a, b, "ja")` の照合順序も英語版では "en" にしてある
  (日本語が無いので 2〜5 のどの検査にも掛からない。辞書に明示的に載せて差し替える)。

使い方: python lab/scripts/make_en_json.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import en_nav
from jsblank import blank, literals
from make_en_contrast import translate_literals, script_span, code_japanese

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

SITE = "https://hirulab-dev.github.io/hirulab-tools"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>JSON整形・検証 — エラー箇所を行と列で指す</title>',
     '<title>JSON Formatter &amp; Validator &mdash; points at the error by line and column</title>'),

    ('<meta name="description" content="JSONを整形・圧縮・検証します。壊れている場所を行と列で指摘して、その場所を実際にハイライトします。ブラウザ内で完結し、データはどこにも送信されません。">',
     '<meta name="description" content="Formats, minifies and validates JSON. When something is broken it names the line and the column and shows you that line. Everything runs in your browser and nothing is ever sent anywhere.">'),

    ('<link rel="canonical" href="%s/json/">\n'
     '<link rel="alternate" hreflang="ja" href="%s/json/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/json.html">' % (SITE, SITE, SITE),
     '<link rel="canonical" href="%s/en/json.html">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/json.html">\n'
     '<link rel="alternate" hreflang="ja" href="%s/json/">' % (SITE, SITE, SITE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="JSON整形・検証 — クロードの昼ラボ">',
     '<meta property="og:title" content="JSON Formatter &amp; Validator">'),

    ('<meta property="og:description" content="JSONを整形・圧縮・検証。壊れている場所を行と列で指摘します。データはどこにも送信されません。">',
     '<meta property="og:description" content="Formats, minifies and validates JSON, naming the line and column of whatever is broken. Nothing is sent anywhere.">'),

    ('<meta property="og:url" content="%s/json/">' % SITE,
     '<meta property="og:url" content="%s/en/json.html">' % SITE),

    ('<meta property="og:image" content="%s/ogp/ogp-json.png">' % SITE,
     '<meta property="og:image" content="%s/ogp/ogp-json-en.png">' % SITE),

    ('<meta name="twitter:title" content="JSON整形・検証 — クロードの昼ラボ">',
     '<meta name="twitter:title" content="JSON Formatter &amp; Validator">'),

    ('<meta name="twitter:description" content="JSONを整形・圧縮・検証。壊れている場所を行と列で指摘します。データはどこにも送信されません。">',
     '<meta name="twitter:description" content="Formats, minifies and validates JSON, naming the line and column of whatever is broken. Nothing is sent anywhere.">'),

    ('<meta name="twitter:image" content="%s/ogp/ogp-json.png">' % SITE,
     '<meta name="twitter:image" content="%s/ogp/ogp-json-en.png">' % SITE),

    ('''  "name": "JSON整形・検証",
  "url": "https://hirulab-dev.github.io/hirulab-tools/json/",
  "description": "JSONを整形・圧縮・検証します。壊れている場所を行と列で指摘し、その位置を実際に表示します。",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-json.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "JSON Formatter & Validator",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/json.html",
  "description": "Formats, minifies and validates JSON. When something is broken it names the line and the column and shows you that line. Everything runs inside the browser.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-json-en.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>JSON整形・検証</h1>
  <p class="lead">整形・圧縮・検証を1画面で。<strong>壊れている場所を「何行目の何文字目」で指して、その行を実際に表示します。</strong></p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    貼り付けたJSONはブラウザの中だけで処理されます。読み込んだあとは機内モードでも動きます。
    APIのレスポンスにはトークンや個人情報が混ざりがちなので、そこを気にせず使えるように作りました。
  </div>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>JSON Formatter &amp; Validator</h1>
  <p class="lead">Format, minify and validate on one screen. <strong>When something is broken it says which line and which column, and shows you that line.</strong></p>

  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    JSON you paste is handled entirely inside your browser. Once the page has loaded it keeps working in airplane mode.
    API responses tend to carry tokens and personal data, so it is built to be used without having to think about that.
  </div>'''),

    ('''    <label class="h" for="src">JSON を貼り付け</label>
    <textarea id="src" spellcheck="false" placeholder='{"name": "クロードの昼ラボ", "tools": 7, "free": true}'></textarea>
    <div class="row">
      <button class="primary" id="fmt">整形する</button>
      <button id="min">1行に圧縮</button>
      <select id="indent" aria-label="インデント">
        <option value="2">スペース2</option>
        <option value="4">スペース4</option>
        <option value="tab">タブ</option>
      </select>
      <label style="font-size:.83rem;color:var(--sub)">
        <input type="checkbox" id="sortkeys"> キーを名前順に
      </label>
      <label style="font-size:.83rem;color:var(--sub)">
        <input type="checkbox" id="strip"> コメント・末尾カンマを許す
      </label>
      <span class="sep"></span>
      <button id="sample">例を入れる</button>
      <button id="clear">消す</button>
    </div>''',
     '''    <label class="h" for="src">Paste your JSON</label>
    <textarea id="src" spellcheck="false" placeholder='{"name": "Claude's Daytime Lab", "tools": 7, "free": true}'></textarea>
    <div class="row">
      <button class="primary" id="fmt">Format</button>
      <button id="min">Minify to one line</button>
      <select id="indent" aria-label="Indent">
        <option value="2">2 spaces</option>
        <option value="4">4 spaces</option>
        <option value="tab">tab</option>
      </select>
      <label style="font-size:.83rem;color:var(--sub)">
        <input type="checkbox" id="sortkeys"> Sort keys by name
      </label>
      <label style="font-size:.83rem;color:var(--sub)">
        <input type="checkbox" id="strip"> Allow comments and trailing commas
      </label>
      <span class="sep"></span>
      <button id="sample">Load an example</button>
      <button id="clear">Clear</button>
    </div>'''),

    ('''      <button id="tab-text" aria-selected="true">整形結果</button>
      <button id="tab-tree" aria-selected="false">ツリー</button>
      <span class="sep"></span>
      <button id="copy">コピー</button>
      <button id="dl">ファイルに保存</button>''',
     '''      <button id="tab-text" aria-selected="true">Formatted</button>
      <button id="tab-tree" aria-selected="false">Tree</button>
      <span class="sep"></span>
      <button id="copy">Copy</button>
      <button id="dl">Save to a file</button>'''),

    ('''    検証はこのページ独自のパーサで行っています（ブラウザ標準の <code>JSON.parse</code> はエラー文言が
    ブラウザごとに違い、位置も分かりにくいためです）。仕様は RFC 8259 に合わせています。
    「コメント・末尾カンマを許す」を有効にすると、JSONC / JSON5 でよくある書き方を取り除いてから解釈します。
    <br>作: <strong>クロードの昼ラボ</strong>(AIのClaudeが書いています) — このページは通信を一切行いません。''',
     '''    Validation is done by this page&#39;s own parser (the browser&#39;s built-in <code>JSON.parse</code> words its
    errors differently in every browser, and does not make the position easy to find). It follows RFC 8259.
    With &ldquo;Allow comments and trailing commas&rdquo; turned on, the writing habits common in JSONC / JSON5
    are stripped out before the text is read.
    <br>Made by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) &mdash; this page makes no network requests at all.'''),
]

TR = {
    # ---- 1. 位置つきパーサのエラー文言 ----
    '文字列は \\" で始める必要があります': 'A string has to start with a \\"',
    '文字列が閉じられていません（\\" が足りません）': 'This string is never closed (a \\" is missing)',
    "エスケープ記号 \\\\ の後に文字がありません": "There is no character after the escape \\\\",
    '\\\\u の後には16進4桁が必要です（例: \\\\u3042）':
    "\\\\u has to be followed by 4 hexadecimal digits (for example \\\\u0041)",
    # ⚠ 前置きと後置きに割れている: fail("…" + e + " です")
    "JSONで使えないエスケープ \\\\": "The escape \\\\",
    " です": " is not one JSON allows",
    "文字列の途中で改行しています。改行は \\\\n と書きます":
    "This string has a line break inside it. Write a line break as \\\\n",
    "文字列に制御文字が入っています（コード ": "This string contains a control character (code ",
    "）": ")",
    "数値になっていません": "This is not a number",
    "小数点の後に数字がありません": "There is no digit after the decimal point",
    "指数部に数字がありません": "There is no digit in the exponent",
    "入れ子が深すぎます（500段を超えました）": "The nesting is too deep (past 500 levels)",
    "値が来るはずの場所で入力が終わっています": "The input ends where a value was expected",
    'JSONの文字列はシングルクォートではなくダブルクォート \\" を使います':
    'JSON strings use double quotes \\", not single quotes',
    " はJSONでは使えません": " cannot be used in JSON",
    # ⚠ 後置き「 があります」を2つの文が共有している。英語も後置きだけで両方読める形にした
    #    (「The unquoted word "x" is not allowed here」「The character "@" is not allowed here」)
    "クォートで囲われていない語 ": "The unquoted word ",
    "ここに来られない文字 ": "The character ",
    " があります": " is not allowed here",
    "{ が閉じられていません（} が足りません）": "This { is never closed (a } is missing)",
    "要素の後に , があるのに次の項目がありません（末尾のカンマ）":
    "There is a , after an item but nothing follows it (a trailing comma)",
    'オブジェクトのキーは \\" で囲む必要があります': 'Object keys have to be wrapped in \\"',
    "キーの後には : が必要です": "A key has to be followed by a :",
    "ここには , か } が必要です": "A , or a } is needed here",
    "[ が閉じられていません（] が足りません）": "This [ is never closed (a ] is missing)",
    "ここには , か ] が必要です": "A , or a ] is needed here",
    "入力が空です": "The input is empty",
    "JSONは1つの値で終わりますが、この後にまだ文字が残っています":
    "JSON ends after a single value, but there are more characters after this one",

    # ---- 3. 出力(キーを名前順にするときの照合順序) ----
    # 日本語が1文字も無いのでどの検査にも掛からない。意図して差し替えるためここに書く
    "ja": "en",

    # ---- ツリーの件数 ----
    " 要素": " items",
    " キー": " keys",

    # ---- 4. 画面(状態の知らせ) ----
    "<b>入力が空です。</b> JSONを貼り付けてください。": "<b>The input is empty.</b> Paste some JSON.",
    "<b>正しいJSONです。</b> ": "<b>This is valid JSON.</b> ",
    "1行に圧縮しました（": "Minified to one line (",
    " 文字）。": " characters).",
    "整形しました（": "Formatted (",
    " 行）。": " lines).",

    # ---- 集計(<b>12</b> のすぐ後ろに続くので、英語は頭に空白を置く) ----
    "キー": " keys",
    "オブジェクト": " objects",
    "配列": " arrays",
    "値の総数": " values in total",
    "最大の深さ": " deepest level",
    "文字数": " characters",

    # ---- 位置の表示【3行目 5文字目】----
    "【": "[line ",
    "行目 ": ", column ",
    "文字目】": "]",

    # ---- 見本のJSON(キーは日本語版でクォートに直したのでここに載る) ----
    "クロードの昼ラボ": "Claude's Daytime Lab",
    "運営": "operator",
    "AI（Claude）": "AI (Claude)",
    "正規表現テスタ": "Regex Tester",
    "文字数カウンタ": "Character Counter",
    "JSON整形・検証": "JSON Formatter & Validator",
    "公開日": "published",
    "収益": "revenue",
    "円": "yen",
    "備考": "note",
    "まだ1円も稼げていません": "not a single yen so far",
    "送信するデータ": "dataSent",

    # ---- お知らせ ----
    "コピーしました": "Copied",
    "コピーできませんでした": "Could not copy",
}

KEEP = set()


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "json" / "index.html"
    en_path = docs / "en" / "json.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'  <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not nav:
        sys.exit("ナビが見つかりません")
    en = en[:nav.start()] + en_nav.build(
        docs, "diff.html", "Text Diff",
        "json.html", "../json/") + en[nav.end():]

    s, e = script_span(en)
    core_en, missing = translate_literals(en[s:e], TR, KEEP)
    if missing:
        sys.exit("訳されていない文字列が %d 件あります:\n  %s"
                 % (len(missing), "\n  ".join(sorted(set(missing))[:12])))
    en = en[:s] + core_en + en[e:]

    s2, e2 = script_span(en)
    outside = en[:s2] + en[e2:]
    outside = re.sub(r"/\*.*?\*/", "", outside, flags=re.S)   # CSS のコメント(画面に出ない)
    outside = re.sub(r"<!--.*?-->", "", outside, flags=re.S)
    left = JA_CHARS.findall(outside)
    if left:
        sys.exit("スクリプトの外に日本語が %d 箇所残っています: %s" % (len(left), left[:12]))

    kept = []
    for q, body in literals(en[s2:e2]):
        if JA_CHARS.search(body):
            if body not in KEEP:
                sys.exit("スクリプトの中に訳し忘れがあります: " + body[:120])
            kept.append(body)

    # ★ 文字列でもコメントでも正規表現でもない日本語(=識別子)が残っていないか
    ident = code_japanese(en[s2:e2])
    if ident:
        sys.exit("コードの骨格に日本語が %d 箇所あります(識別子として書かれた日本語):\n  %s"
                 % (len(ident), "\n  ".join(ident[:8])))

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
    print("コードの骨格の日本語(識別子): 0箇所")
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
