#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「ページまるごとコントラスト診断」の英語版を、日本語版から作る(2026-08-31)。

`make_en_contrast.py` / `make_en_image.py` と同じ方式。ナビは `en_nav.build` が組み直す。
**日本語版が唯一の原本**で、英語版を手で直すことはしない。

★この道具に固有の事情: 画面に出る文言の大半は**ブックマークレットの中**にある。
ブックマークレットは他人のページに注入されて動くので、**英語版のブックマークレットは
英語で結果を出さないと意味がない**。ブックマークのURLはページ内の関数そのものから
組み立てているので、リテラルを訳せばブックマークレットも一緒に英語になる。
(=「ページの中身とブックマークの中身が食い違わない」という元の設計がそのまま効く)

使い方: python lab/scripts/make_en_page_contrast.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import en_nav
from jsblank import blank, literals
from make_en_contrast import translate_literals, script_span
from en_common import translate_comments

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

SITE = "https://hirulab-dev.github.io/hirulab-tools"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>ページまるごとコントラスト診断 — 開いているページの読みにくい文字を全部出す</title>',
     '<title>Whole-Page Contrast Audit &mdash; find every hard-to-read line on a page</title>'),

    ('<meta name="description" content="ブックマークに入れて、気になるページで押すだけ。そのページの文字を全部拾って、コントラスト比がWCAG 2.1のAA基準を満たしていない箇所を一覧にします。サーバーには何も送りません。">',
     '<meta name="description" content="Keep it in your bookmarks bar and press it on any page. It collects every piece of text on that page and lists the ones whose contrast ratio falls short of WCAG 2.1 level AA. Nothing is sent to any server.">'),

    # ⚠ 2026-08-31 昼に直した。書いた当初は日本語版に hreflang が無かったので
    #   canonical だけを差し替えていたが、**同じ枠で日本語版にも hreflang を足した**ため、
    #   次に走らせると hreflang が2組になる(実際に重複を出した)。日本語版の3行ごと差し替える。
    ('<link rel="canonical" href="%s/page-contrast/">\n'
     '<link rel="alternate" hreflang="ja" href="%s/page-contrast/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/page-contrast.html">' % (SITE, SITE, SITE),
     '<link rel="canonical" href="%s/en/page-contrast.html">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/page-contrast.html">\n'
     '<link rel="alternate" hreflang="ja" href="%s/page-contrast/">' % (SITE, SITE, SITE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="ページまるごとコントラスト診断">',
     '<meta property="og:title" content="Whole-Page Contrast Audit">'),

    ('<meta property="og:description" content="ブックマークに入れて押すだけ。開いているページの文字を全部拾って、読みにくい箇所を一覧にします。サーバーには何も送りません。">',
     '<meta property="og:description" content="Bookmark it and press it. It collects every piece of text on the page you are looking at and lists what is hard to read. Nothing is sent to any server.">'),

    ('<meta property="og:url" content="%s/page-contrast/">' % SITE,
     '<meta property="og:url" content="%s/en/page-contrast.html">' % SITE),

    ('<meta property="og:image" content="%s/ogp/ogp-page-contrast.png">' % SITE,
     '<meta property="og:image" content="%s/ogp/ogp-page-contrast-en.png">' % SITE),

    ('<meta name="twitter:title" content="ページまるごとコントラスト診断">',
     '<meta name="twitter:title" content="Whole-Page Contrast Audit">'),

    ('<meta name="twitter:description" content="ブックマークに入れて押すだけ。開いているページの読みにくい文字を全部出します。">',
     '<meta name="twitter:description" content="Bookmark it and press it. It shows every hard-to-read line on the page you are looking at.">'),

    ('<meta name="twitter:image" content="%s/ogp/ogp-page-contrast.png">' % SITE,
     '<meta name="twitter:image" content="%s/ogp/ogp-page-contrast-en.png">' % SITE),

    ('''  "name": "ページまるごとコントラスト診断",
  "url": "https://hirulab-dev.github.io/hirulab-tools/page-contrast/",
  "description": "ブックマークレット。開いているページの文字要素を全部拾い、実効の前景色と背景色からコントラスト比を計算して、WCAG 2.1 の AA 基準を満たしていない箇所を一覧表示します。通信は行いません。",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-page-contrast.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "Whole-Page Contrast Audit",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/page-contrast.html",
  "description": "A bookmarklet. It collects every text element on the page you are viewing, works out the contrast ratio from the effective foreground and background colours, and lists everything that falls short of WCAG 2.1 level AA. It makes no network requests.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-page-contrast-en.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>ページまるごとコントラスト診断</h1>
  <p class="lead">
    色を2つ入れて調べるのではなく、<strong>いま開いているページの文字を全部拾って、読みにくい箇所を一覧で出します。</strong>
    ブックマークに入れておいて、気になったページで押すだけです。
  </p>

  <div class="privacy">
    <strong>このページも、押したあとの処理も、通信を一切行いません。</strong>
    診断はあなたのブラウザの中だけで完結します。見ていたページのURLや中身が、どこかに送られることはありません。
  </div>

  <h2>入れる</h2>
  <div class="panel">
    <div class="drag">
      <a class="bm" id="bm" href="#">コントラスト診断</a>
      <p>この黄色いボタンを、<strong>ブックマークバーにドラッグ＆ドロップ</strong>してください。<br>
         スマホなど、ドラッグできない場合は下の「手で登録する」を開いてください。</p>
    </div>
    <div class="demo">
      入れる前に動きを見たい場合は、まずここで試せます →
      <button class="primary" id="try">このページを診断してみる</button>
      <br><span style="color:var(--sub)">（もう一度押すと結果が閉じます）</span>
    </div>
  </div>

  <h2>使う</h2>
  <ol>
    <li>読みにくいと思ったページを開く</li>
    <li>ブックマークバーの「コントラスト診断」を押す</li>
    <li>画面の右下に結果が出ます。一覧の項目を押すと、その場所までスクロールして赤枠で囲みます</li>
    <li>もう一度ブックマークを押すと閉じます</li>
  </ol>

  <h2>何を見ているか</h2>
  <ul>
    <li>文字が入っている要素を全部拾い、<strong>その要素に実際に効いている文字色</strong>と、<strong>透明な親を遡って実際に見えている背景色</strong>を取り出します</li>
    <li>その2色から <a href="https://www.w3.org/TR/WCAG21/#contrast-minimum">WCAG 2.1</a> の式でコントラスト比を計算します</li>
    <li>文字の大きさと太さを見て、必要な基準を出し分けます。<strong>24px以上、または18.66px以上の太字なら 3:1、それ以外は 4.5:1</strong>（AA基準）</li>
    <li>足りていないものだけを、比の小さい順に並べます</li>
  </ul>

  <h2>できないこと（先に書いておきます）</h2>
  <div class="limits">
    <strong>この診断が「合格」でも、それだけで読みやすさが保証されるわけではありません。</strong>
    以下は判定できないので、目で見て確かめてください。
    <ul>
      <li><strong>写真やグラデーションの上に載った文字</strong>。背景の色が場所によって違うので、単純な2色の比では表せません。この診断では、遡って見つけた「べた塗りの色」を背景として扱います</li>
      <li><strong>iframeの中身</strong>（埋め込み動画やSNSの埋め込みなど）。別ページ扱いなので中を読めません</li>
      <li><strong>マウスを載せたときや、押している最中の色</strong>。表示されている状態だけを見ています</li>
      <li><strong>枠線やアイコンなど、文字以外の要素</strong>。文字が入っている要素だけが対象です</li>
      <li>要素が非常に多いページでは、先頭から4000要素までで打ち切ります（打ち切った場合は画面にそう表示します）</li>
    </ul>
  </div>

  <h2>手で登録する（ドラッグできない場合）</h2>
  <div class="panel">
    <p style="font-size:.85rem;margin:0 0 10px;color:var(--sub)">
      ブックマークを1つ新規作成して、URL欄に下のコードを丸ごと貼り付けてください。名前は何でも構いません。</p>
    <button id="copy">コードをコピーする</button>
    <span id="copied" style="font-size:.85rem;color:var(--ok);margin-left:10px"></span>
  </div>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>Whole-Page Contrast Audit</h1>
  <p class="lead">
    Instead of typing in two colours, <strong>this collects every piece of text on the page you have open and lists what is hard to read.</strong>
    Keep it in your bookmarks bar and press it whenever a page looks off.
  </p>

  <div class="privacy">
    <strong>Neither this page nor the audit itself makes any network request.</strong>
    Everything happens inside your own browser. The address and the contents of the page you were reading are never sent anywhere.
  </div>

  <h2>Install it</h2>
  <div class="panel">
    <div class="drag">
      <a class="bm" id="bm" href="#">Contrast Audit</a>
      <p>Take the yellow button and <strong>drag it onto your bookmarks bar</strong>.<br>
         On a phone, or anywhere you cannot drag, open &ldquo;Add it by hand&rdquo; below instead.</p>
    </div>
    <div class="demo">
      Want to see what it does first? Try it right here &rarr;
      <button class="primary" id="try">Audit this page</button>
      <br><span style="color:var(--sub)">(press again to close the results)</span>
    </div>
  </div>

  <h2>Use it</h2>
  <ol>
    <li>Open a page that looks hard to read</li>
    <li>Press &ldquo;Contrast Audit&rdquo; in your bookmarks bar</li>
    <li>The results appear at the bottom right. Press any entry to scroll to that spot and outline it in red</li>
    <li>Press the bookmark again to close it</li>
  </ol>

  <h2>What it looks at</h2>
  <ul>
    <li>It collects every element that holds text, then reads <strong>the text colour actually in effect on that element</strong> and <strong>the background colour you can actually see</strong>, walking up through transparent parents to find it</li>
    <li>From those two colours it computes the contrast ratio with the <a href="https://www.w3.org/TR/WCAG21/#contrast-minimum">WCAG 2.1</a> formula</li>
    <li>It picks the threshold from the size and weight of the text. <strong>24px and above, or 18.66px and above in bold, needs 3:1; everything else needs 4.5:1</strong> (level AA)</li>
    <li>Only the ones that fall short are listed, smallest ratio first</li>
  </ul>

  <h2>What it cannot do (said up front)</h2>
  <div class="limits">
    <strong>A clean result here does not on its own mean the page is readable.</strong>
    The following cannot be judged automatically, so check them with your own eyes.
    <ul>
      <li><strong>Text sitting on a photo or a gradient.</strong> The background differs from place to place, so a single pair of colours cannot describe it. This audit treats the nearest solid colour it finds as the background</li>
      <li><strong>Anything inside an iframe</strong> (embedded videos, embedded posts). It counts as a separate page, so the contents cannot be read</li>
      <li><strong>Hover and active colours.</strong> Only the state currently on screen is examined</li>
      <li><strong>Borders, icons and anything that is not text.</strong> Only elements holding text are considered</li>
      <li>On pages with a very large number of elements it stops after the first 4000 (and says so on screen when it does)</li>
    </ul>
  </div>

  <h2>Add it by hand (if you cannot drag)</h2>
  <div class="panel">
    <p style="font-size:.85rem;margin:0 0 10px;color:var(--sub)">
      Create a new bookmark and paste the whole snippet below into its address field. The name can be anything.</p>
    <button id="copy">Copy the code</button>
    <span id="copied" style="font-size:.85rem;color:var(--ok);margin-left:10px"></span>
  </div>'''),

    ('''    ブックマークのURLは、このページに書いてある診断プログラムそのものから自動で組み立てています。
    ページの中身とブックマークの中身が食い違わないようにするためです（コピーした時点のコードが、そのまま動きます）。
    <br>サイトによっては、セキュリティ設定（Content Security Policy）でブックマークレットの実行が止められることがあります。
    その場合は何も起きません。壊れたわけではないので、別のページで試してみてください。
    <br>作: <strong>クロードの昼ラボ</strong>（AIのClaudeが書いています） — このページは通信を一切行いません。''',
     '''    The bookmark address is built automatically from the very audit program printed on this page,
    so what you read here and what you install can never drift apart (the code as of the moment you copy it is what runs).
    <br>On some sites the security settings (Content Security Policy) block bookmarklets from running.
    Nothing will happen there. It is not broken &mdash; try it on a different page.
    <br>Made by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) &mdash; this page makes no network requests at all.'''),
]

TR = {
    # ---- ブックマークレットが他人のページに出す文言(ここが本体) ----
    '<strong style="font-size:14px">コントラスト診断</strong>':
    '<strong style="font-size:14px">Contrast Audit</strong>',

    ';font-size:11px">クロードの昼ラボ</span>':
    ';font-size:11px">Claude&#39;s Daytime Lab</span>',

    '<div style="margin-bottom:10px">文字のある要素 <strong>':
    '<div style="margin-bottom:10px">Checked <strong>',

    "</strong> 件を調べて、": "</strong> elements with text; ",

    '基準に足りないもの <strong style="color:':
    '<strong style="color:',

    "</strong> 件。</div>": "</strong> fall short of the standard.</div>",

    ';margin-bottom:10px">※要素が多いため先頭':
    ';margin-bottom:10px">Note: this page has a lot of elements, so only the first ',

    "件で打ち切りました。</div>": " were checked.</div>",

    '">このページの文字は、表示されている状態では AA 基準（通常 4.5:1 / 大きい文字 3:1）を満たしています。':
    '">As currently displayed, the text on this page meets level AA (4.5:1 normally, 3:1 for large text).',

    '">※写真の上の文字やiframeの中は判定できていません。</span></div>':
    '">Text over photos, and anything inside an iframe, could not be judged.</span></div>',

    ';margin-bottom:8px">押すとその場所へ移動して赤枠で囲みます。</div>':
    ';margin-bottom:8px">Press an entry to jump to it and outline it in red.</div>',

    '">（必要 ': '">(needs ',
    "px）</span><br>": "px)</span><br>",
    "（文字なし）": "(no text)",
    '">…ほか ': '">&hellip;and ',
    " 件</div>": " more</div>",

    # ---- ページ側の文言 ----
    "コピーしました（": "Copied (",
    "文字）": " characters)",
    "コピーできませんでした": "Could not copy",
}

KEEP = set()

# ★2026-09-03 夜 追加(コメントも訳す)。⚠ 訳は行数を変えない・訳の中に日本語を書かない。
COMMENTS = {
    '/* ============================================================\n'
    '   診断の本体。この関数の中身がそのままブックマークレットになる。\n'
    '   （下で String(hirulabContrast) を取り出して javascript: URL を組み立てている）\n'
    '   ページの外の変数に依存しないよう、必要なものは全部この中に閉じてある。\n'
    '   ============================================================ */':
    '/* ============================================================\n'
    '   The diagnosis itself. The body of this function IS the bookmarklet.\n'
    '   (below, String(hirulabContrast) is pulled out to build the javascript: URL)\n'
    '   Everything it needs is closed inside, so it depends on nothing outside.\n'
    '   ============================================================ */',
    '/* 2回目は閉じる */': '/* A second run closes it */',
    '/* 透明を遡って、実際に見えている色を探す */':
    '/* Walk up through transparency to find the color actually seen */',
    '/* 子要素ではなく自分が持っている文字 */':
    '/* Text this element owns, not the text of its children */',
    '/* ---- ブックマークレットのURLを、上の関数そのものから組み立てる ---- */':
    '/* ---- Build the bookmarklet URL from the function above itself ---- */',
}


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "page-contrast" / "index.html"
    en_path = docs / "en" / "page-contrast.html"
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
        docs, "image.html", "Image Resizer &amp; Compressor",
        "page-contrast.html", "../page-contrast/") + en[nav.end():]

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

    s2, e2 = script_span(en)
    outside = en[:s2] + en[e2:]
    # ⚠ この道具は `<style>` の中に日本語のコメントがある(なぜこの色にしたかの覚え書き)。
    # コメントは画面に出ないので、JS のコメントと同じ扱いで対象外にする。
    # (これまでの make_en_*.py はたまたま CSS コメントが無かっただけで、
    #  スクリプトの外を丸ごと見ていた。ここで型を1つ足しておく)
    outside = re.sub(r"/\*.*?\*/", "", outside, flags=re.S)
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
