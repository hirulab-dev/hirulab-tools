#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「テキスト差分(diff)」の英語版を、日本語版から作る(2026-08-31)。

`make_en_contrast.py` / `make_en_image.py` / `make_en_page_contrast.py` と同じ方式。
ナビは `en_nav.build` が**ほどいて組み直す**。**日本語版が唯一の原本**で、英語版を手で直さない。

1. HTML(head・本文・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = Myers の差分アルゴリズム・行内差分・たたみ込み・unified diff の組み立ては1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

★この回に固有の注意: 見本のテキスト(`例を入れる`)は**それ自体が差分の題材**なので、
  訳したあとも「1行が書き換わる / 1行が挿入される / 箇条書きの1行が入れ替わる」の
  3種類が残るように英語を選んである(訳して差分の形が変わると、見本の意味が消える)。

使い方: python lab/scripts/make_en_diff.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import en_nav
from jsblank import blank, literals
from make_en_contrast import translate_literals, script_span

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

SITE = "https://hirulab-dev.github.io/hirulab-tools"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>テキスト差分（diff）— 行の中のどこが変わったかまで色を付ける</title>',
     '<title>Text Diff &mdash; highlights which characters changed, not just which lines</title>'),

    ('<meta name="description" content="2つのテキストを比べて、変わった行と、その行の中のどの文字が変わったかまで色分けします。unified diff（パッチ）形式での書き出しつき。ブラウザ内で完結し、データはどこにも送信されません。">',
     '<meta name="description" content="Compares two texts and colours both the lines that changed and the exact characters that changed inside them. Exports a unified diff (patch). Everything runs in your browser and nothing is ever sent anywhere.">'),

    ('<link rel="canonical" href="%s/diff/">\n'
     '<link rel="alternate" hreflang="ja" href="%s/diff/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/diff.html">' % (SITE, SITE, SITE),
     '<link rel="canonical" href="%s/en/diff.html">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/diff.html">\n'
     '<link rel="alternate" hreflang="ja" href="%s/diff/">' % (SITE, SITE, SITE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="テキスト差分（diff） — クロードの昼ラボ">',
     '<meta property="og:title" content="Text Diff">'),

    ('<meta property="og:description" content="2つのテキストを比べて、行の中のどの文字が変わったかまで色を付けます。データはどこにも送信されません。">',
     '<meta property="og:description" content="Compares two texts and colours the exact characters that changed inside each line. Nothing is sent anywhere.">'),

    ('<meta property="og:url" content="%s/diff/">' % SITE,
     '<meta property="og:url" content="%s/en/diff.html">' % SITE),

    ('<meta property="og:image" content="%s/ogp/ogp-diff.png">' % SITE,
     '<meta property="og:image" content="%s/ogp/ogp-diff-en.png">' % SITE),

    ('<meta name="twitter:title" content="テキスト差分（diff） — クロードの昼ラボ">',
     '<meta name="twitter:title" content="Text Diff">'),

    ('<meta name="twitter:description" content="2つのテキストを比べて、行の中のどの文字が変わったかまで色を付けます。データはどこにも送信されません。">',
     '<meta name="twitter:description" content="Compares two texts and colours the exact characters that changed inside each line. Nothing is sent anywhere.">'),

    ('<meta name="twitter:image" content="%s/ogp/ogp-diff.png">' % SITE,
     '<meta name="twitter:image" content="%s/ogp/ogp-diff-en.png">' % SITE),

    ('''  "name": "テキスト差分（diff）",
  "url": "https://hirulab-dev.github.io/hirulab-tools/diff/",
  "description": "2つのテキストを比較して、変わった行と、その行の中のどの文字が変わったかまで色分けします。unified diff 形式での書き出しつき。ブラウザ内で完結します。",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-diff.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "Text Diff",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/diff.html",
  "description": "Compares two texts and colours the lines that changed together with the exact characters that changed inside them. Exports a unified diff. Everything runs inside the browser.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-diff-en.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>テキスト差分（diff）</h1>
  <p class="lead">2つのテキストの違いを並べて表示します。<strong>変わった行を示すだけでなく、その行の中のどの文字が変わったかまで色を付けます。</strong></p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    貼り付けたテキストも、開いたファイルも、ブラウザの中だけで処理されます。読み込んだあとは機内モードでも動きます。
    差分を取りたいものは、たいてい書きかけのコードか、社外に出せない文書です。そこを気にせず使えるように作りました。
  </div>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>Text Diff</h1>
  <p class="lead">Shows the differences between two texts side by side. <strong>It does not just mark which lines changed &mdash; it colours the exact characters that changed inside them.</strong></p>

  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    Text you paste and files you open are handled entirely inside your browser. Once the page has loaded it keeps working in airplane mode.
    Whatever you want to diff is usually half-written code or a document that cannot leave the building, so it is built to be used without thinking about that.
  </div>'''),

    ('''        <label class="h" for="a">変更前（左）</label>
        <textarea id="a" spellcheck="false" placeholder="こちらに元のテキストを貼り付け"></textarea>
        <div class="row">
          <label class="file"><span>ファイルを開く</span><input type="file" id="fa"></label>''',
     '''        <label class="h" for="a">Before (left)</label>
        <textarea id="a" spellcheck="false" placeholder="Paste the original text here"></textarea>
        <div class="row">
          <label class="file"><span>Open a file</span><input type="file" id="fa"></label>'''),

    ('''        <label class="h" for="b">変更後（右）</label>
        <textarea id="b" spellcheck="false" placeholder="こちらに新しいテキストを貼り付け"></textarea>
        <div class="row">
          <label class="file"><span>ファイルを開く</span><input type="file" id="fb"></label>''',
     '''        <label class="h" for="b">After (right)</label>
        <textarea id="b" spellcheck="false" placeholder="Paste the new text here"></textarea>
        <div class="row">
          <label class="file"><span>Open a file</span><input type="file" id="fb"></label>'''),

    ('''      <button class="primary" id="run">比較する</button>
      <button id="swap">左右を入れ替え</button>
      <button id="sample">例を入れる</button>
      <button id="clear">消す</button>
      <span class="sep"></span>
      <span class="note" style="margin:0">Ctrl + Enter でも比較できます</span>''',
     '''      <button class="primary" id="run">Compare</button>
      <button id="swap">Swap sides</button>
      <button id="sample">Load an example</button>
      <button id="clear">Clear</button>
      <span class="sep"></span>
      <span class="note" style="margin:0">Ctrl + Enter compares too</span>'''),

    ('''      <label><input type="checkbox" id="ig-case"> 大文字と小文字を区別しない</label>
      <label><input type="checkbox" id="ig-ws"> 空白の量を無視する</label>
      <label><input type="checkbox" id="ig-tail" checked> 行末の空白を無視する</label>
      <label>行の中の差分:
        <select id="gran">
          <option value="char">文字単位</option>
          <option value="word">単語単位</option>
          <option value="none">付けない</option>
        </select>
      </label>''',
     '''      <label><input type="checkbox" id="ig-case"> Ignore case</label>
      <label><input type="checkbox" id="ig-ws"> Ignore how much whitespace</label>
      <label><input type="checkbox" id="ig-tail" checked> Ignore trailing whitespace</label>
      <label>Inside a line:
        <select id="gran">
          <option value="char">by character</option>
          <option value="word">by word</option>
          <option value="none">no highlight</option>
        </select>
      </label>'''),

    ('''      <button id="tab-sbs" aria-selected="true">並べて表示</button>
      <button id="tab-inl" aria-selected="false">1列で表示</button>
      <button id="tab-uni" aria-selected="false">unified diff</button>
      <span class="sep"></span>
      <label class="file" style="text-decoration:none"><input type="checkbox" id="wrapmode" style="display:inline"> 折り返す</label>
      <label class="file" style="text-decoration:none"><input type="checkbox" id="fold" checked style="display:inline"> 変化のない行をたたむ</label>
      <button id="copy">unified diff をコピー</button>
      <button id="dl">.patch で保存</button>''',
     '''      <button id="tab-sbs" aria-selected="true">Side by side</button>
      <button id="tab-inl" aria-selected="false">One column</button>
      <button id="tab-uni" aria-selected="false">unified diff</button>
      <span class="sep"></span>
      <label class="file" style="text-decoration:none"><input type="checkbox" id="wrapmode" style="display:inline"> Wrap lines</label>
      <label class="file" style="text-decoration:none"><input type="checkbox" id="fold" checked style="display:inline"> Fold unchanged lines</label>
      <button id="copy">Copy the unified diff</button>
      <button id="dl">Save as .patch</button>'''),

    ('''    差分の計算には Myers のアルゴリズム（1986年の論文 “An O(ND) Difference Algorithm and Its Variations”）を
    自前で実装したものを使っています。<code>git diff</code> や多くの diff ツールと同じ系統の手法です。
    まず行の対応を取り、続いて置き換えられた行どうしをもう一度同じアルゴリズムにかけて、文字（または単語）単位の差分を出しています。
    <br>変更量が極端に大きい場合は途中で計算を打ち切り、その範囲を「まるごと置き換え」として表示します（打ち切ったときは画面にそう表示します）。
    <br>作: <strong>クロードの昼ラボ</strong>（AIのClaudeが書いています） — このページは通信を一切行いません。''',
     '''    The differences are computed with our own implementation of Myers&#39; algorithm
    (from the 1986 paper &ldquo;An O(ND) Difference Algorithm and Its Variations&rdquo;), the same family of method
    that <code>git diff</code> and most other diff tools use.
    Lines are matched first, then each pair of replaced lines is run through the same algorithm again to get the
    character-level (or word-level) difference.
    <br>When the amount of change is extreme the computation is cut short and that stretch is shown as one whole
    replacement (the page says so when that happens).
    <br>Made by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) &mdash; this page makes no network requests at all.'''),
]

TR = {
    # ---- たたんだ行のしるし(並べて表示・1列で表示の両方が同じ文字列を使う) ----
    '<tr class="r-gap"><td colspan="4">— 同じ行が ':
    '<tr class="r-gap"><td colspan="4">&mdash; ',
    " 行 —</td></tr>": " identical lines &mdash;</td></tr>",

    # ---- unified diff ----
    '<span class="m">差分はありません。</span>': '<span class="m">There are no differences.</span>',
    "変更前": "before",
    "変更後": "after",

    # ---- 状態の知らせ ----
    "左右どちらにもテキストがありません。「例を入れる」で試せます。":
    # ⚠ この文字列は元が二重引用符なので、訳文に \" を書くとリテラルが割れる。
    #    setStatus は textContent なので実体参照も使えない。→ 生の “ ” を使う
    "There is no text on either side. Press “Load an example” to try it.",
    "2つのテキストは完全に同じです。": "The two texts are exactly the same.",
    "行の内容は一致しています（無視する設定にした違いだけがあります）。":
    "The lines match (the only differences are ones you chose to ignore).",
    "変更量が大きすぎたため計算を打ち切りました。共通する先頭と末尾以外を、まるごと置き換えとして表示しています。":
    "The amount of change was too large, so the computation was cut short. "
    "Everything except the shared beginning and end is shown as one whole replacement.",
    "違いは ": "There are ",
    " 行です。色の付いた行が変わったところです。": " changed lines. The coloured lines are where they are.",

    # ---- 集計 ----
    "</b>行 追加</span>": "</b> lines added</span>",
    "</b>行 削除</span>": "</b> lines removed</span>",
    "</b>行 書き換え</span>": "</b> lines rewritten</span>",
    "</b>行 そのまま</span>": "</b> lines unchanged</span>",
    " 行 → ": " lines &rarr; ",
    " 行</span>": " lines</span>",
    " ミリ秒</span>": " ms</span>",

    # ---- 表示上限の注記 ----
    "行数が多いため先頭 ": "Too many lines to draw them all, so only the first ",
    " 行ぶんだけ表示しています。全体は unified diff タブか .patch の保存で確認してください。":
    " are shown. Use the unified diff tab, or save the .patch, to see all of it.",

    # ---- 見本(差分の題材そのもの。訳しても「書き換え1行・挿入1行・箇条書き1行」が残る形にした) ----
    "# 昼ラボ 運用メモ\n公開しているツールは 7 本です。\nすべてブラウザの中だけで動きます。\n"
    "データはサーバーに送信されません。\n\n## やること\n- ツールを1日1個ふやす\n"
    "- note に実験ログを書く\n- アクセス解析を入れるか決める":
    "# Daytime Lab operating notes\nThere are 7 tools published.\nEverything runs inside the browser.\n"
    "No data is sent to any server.\n\n## To do\n- Add one tool a day\n"
    "- Write up the experiment log\n- Decide whether to add analytics",

    "# 昼ラボ 運用メモ\n公開しているツールは 8 本です。\nすべてブラウザの中だけで動きます。\n"
    "データはサーバーに送信されません。\n入れていないので、送りようがありません。\n\n"
    "## やること\n- ツールを1日1個ふやす\n- note に実験ログを書く\n- Zenn に技術記事を出す":
    "# Daytime Lab operating notes\nThere are 8 tools published.\nEverything runs inside the browser.\n"
    "No data is sent to any server.\nThere is no analytics, so there is nothing to send.\n\n"
    "## To do\n- Add one tool a day\n- Write up the experiment log\n- Publish a technical article",

    # ---- ファイルを開いたときの表示・お知らせ ----
    "（": " (",
    " バイト）": " bytes)",
    "ファイルを読めませんでした": "Could not read the file",
    "差分がありません": "There is no diff yet",
    "コピーしました": "Copied",
    "コピーできませんでした": "Could not copy",
}

KEEP = set()


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "diff" / "index.html"
    en_path = docs / "en" / "diff.html"
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
        docs, "page-contrast.html", "Whole-Page Contrast Audit",
        "diff.html", "../diff/") + en[nav.end():]

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
