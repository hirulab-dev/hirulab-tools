#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「Base64・データURLの分解」の英語版を、日本語版から作る(2026-08-27)。

`make_en_railroad.py` 以降と同じ方式。**日本語版が唯一の原本**で、英語版は毎回ここから作り直す。

1. HTML(head・本文・詳細・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. できた英語版について、**「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**
   ことを確かめる。通れば、復号・符号化・データURLの解析・中身の判定・落とし穴の検出は
   1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

★ここまでは既存の make_en_*.py と同じだが、**差し替えのやり方を1つ変えた**。

  これまでは `en.replace('"' + ja + '"', '"' + en + '"')` で、**二重引用符の文字列にしか
  当たらなかった**。このページは HTML の組み立てに `'…'` の文字列も使っているので、
  そのままでは 17 件が黙って未訳のまま残る(2026-08-27 の夜枠で実際に詰まった)。

  なので **JS を1文字ずつ読んで、文字列リテラルの中身だけを完全一致で差し替える**形にした
  (`translate_literals`)。引用符の種類を問わないうえ、
  **日本語を含むリテラルが TR にも KEEP にも無ければエラーで止まる**ので、
  「訳し忘れが黙って通る」ことが構造的に起きない。

  `KEEP` は**わざと日本語のまま残すリテラル**。理由つきで書く。
  いまは2種類しかない:
    - `isSpaceChar` が全角空白 U+3000 を空白として読み飛ばすための**処理の定数**
    - 自己検査の UTF-8 の見本(`あ` など)。**画面には出ない**うえ、
      日本語版と同じバイト列を通すほうが検査として強い

使い方: python lab/scripts/make_en_base64.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals

SITE = "https://hirulab-dev.github.io/hirulab-tools"

# 「画面に出るところに日本語が残っていないか」を見るときの文字の範囲。
# ひらがな・カタカナ・漢字・和文の約物・全角空白。
JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>Base64・データURLの分解 — 宣言と中身が合っているか確かめる道具</title>',
     '<title>Base64 &amp; Data URL Explainer — check that the declaration matches the content</title>'),

    ('<meta name="description" content="Base64の文字列やデータURL(data:...)を貼ると、部品に分けて中身を読み下します。差別化点は「エラーにならないので気づけない」ところを名指しすること — 宣言したMIMEと中身のマジックナンバーの食い違い、余ったビットが0でないbase64(別の文字列が同じバイト列に戻る)、;base64を書き忘れて文字列として解釈されている、非base64のデータURLで+が空白にならない、など。復号は自前実装で、読み込みのたびにブラウザのatobと突き合わせます。ブラウザ内で完結し、通信は一切行いません。">',
     '<meta name="description" content="Paste a base64 string or a data URL (data:...) and it is split into its parts and read back to you. What sets it apart: it names the things that raise no error, so you never notice them — a declared MIME type that disagrees with the magic number of the content, non-canonical base64 whose leftover bits are not 0 (a different string decodes to the very same bytes), a missing ;base64 so the body is taken as literal text, a + that does not become a space in a non-base64 data URL. Decoding is written from scratch and checked against the browser\'s atob on every load. Runs entirely in the browser; it makes no network requests at all.">'),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/base64/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/base64/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/base64.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/base64.html">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/base64.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/base64/">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="Base64・データURLの分解 — 宣言と中身が合っているか確かめる道具">',
     '<meta property="og:title" content="Base64 &amp; Data URL Explainer — check that the declaration matches the content">'),

    ('<meta property="og:description" content="Base64やデータURLを部品に分けて読み下します。宣言したMIMEと中身の食い違い、余ったビットが0でないbase64、;base64の書き忘れなど、エラーにならないので気づけないところを名指しします。通信は一切行いません。">',
     '<meta property="og:description" content="Splits base64 and data URLs into their parts and reads them back. It names the things that raise no error and so go unnoticed: a declared MIME type that disagrees with the content, non-canonical base64 whose leftover bits are not 0, a missing ;base64. It makes no network requests at all.">'),

    ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/base64/">',
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/base64.html">'),

    ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-base64.png">',
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-base64-en.png">'),

    ('<meta name="twitter:title" content="Base64・データURLの分解 — 宣言と中身が合っているか確かめる道具">',
     '<meta name="twitter:title" content="Base64 &amp; Data URL Explainer — check that the declaration matches the content">'),

    ('<meta name="twitter:description" content="宣言したMIMEと中身のマジックナンバーの食い違い、余ったビットが0でないbase64など、エラーにならないので気づけないところを名指しします。通信は一切行いません。">',
     '<meta name="twitter:description" content="A declared MIME type that disagrees with the magic number of the content, non-canonical base64 whose leftover bits are not 0, and other things that raise no error — all named. It makes no network requests at all.">'),

    ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-base64.png">',
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-base64-en.png">'),

    ('''  "name": "Base64・データURLの分解",
  "url": "https://hirulab-dev.github.io/hirulab-tools/base64/",
  "description": "Base64の文字列やデータURL(data:...)を部品に分けて読み下す道具です。宣言されたMIMEと中身のマジックナンバーの食い違い、余ったビットが0でないbase64(別の文字列が同じバイト列に戻る)、;base64の書き忘れ、非base64のデータURLでのプラス記号の扱いなど、エラーにならないので気づけないところを名指しします。復号は自前実装で、読み込みのたびにブラウザのatobと突き合わせます。ブラウザ内で完結し、入力はどこにも送信されません。",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-base64.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "Base64 & Data URL Explainer",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/base64.html",
  "description": "A tool that splits a base64 string or a data URL (data:...) into its parts and reads them back. It names the things that raise no error and so go unnoticed: a declared MIME type that disagrees with the magic number of the content, non-canonical base64 whose leftover bits are not 0 (a different string decodes to the very same bytes), a missing ;base64, and how a plus sign is treated in a non-base64 data URL. Decoding is written from scratch and checked against the browser's atob on every load. Runs entirely in the browser; nothing you paste is ever sent anywhere.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-base64-en.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude's Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('  <a class="hl-back" href="../">&larr; クロードの昼ラボ 道具箱</a>\n  <h1>Base64・データURLの分解</h1>',
     '  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>\n  <h1>Base64 &amp; Data URL Explainer</h1>'),

    ('''  <p class="lead">Base64 の文字列や <code>data:</code> で始まるデータURLを貼ると、部品に分けて中身を読み下します。
    <strong>差別化点は「エラーにならないので気づけない」ところだけを名指しすること。</strong>
    <code>data:image/png</code> と書いてあるのに中身は JPEG、
    <strong>余ったビットが0でない</strong>ので別の文字列が同じバイト列に戻る、
    <code>;base64</code> を書き忘れて中身が文字列として解釈されている &mdash;
    こういうものは<strong>どこもエラーを出さないまま動いてしまいます</strong>。
    復号は <code>atob</code> を使わず自前で書いてあり、読み込みのたびにブラウザのものと突き合わせています。</p>''',
     '''  <p class="lead">Paste a base64 string, or a data URL starting with <code>data:</code>, and it is split
    into its parts and read back to you.
    <strong>What sets it apart: it names only the things that raise no error.</strong>
    It says <code>data:image/png</code> but the content is JPEG;
    <strong>the leftover bits are not 0</strong>, so a different string decodes to the same bytes;
    <code>;base64</code> was left out, so the content is taken as literal text &mdash;
    <strong>none of these stop anything, and everything keeps working</strong>.
    Decoding is written from scratch rather than with <code>atob</code>, and it is checked against
    the browser&#39;s own on every load.</p>'''),

    ('''  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    分解も復号もすべてブラウザの中で完結します。読み込んだあとは機内モードでも動きます。
    <strong>貼り付けたデータがどこかに送られることはありません。</strong>
  </div>''',
     '''  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    Splitting and decoding both happen entirely in your browser. Once it has loaded, it keeps
    working in airplane mode.
    <strong>Nothing you paste is ever sent anywhere.</strong>
  </div>'''),

    ('''    <h2>1. 貼る</h2>
    <textarea id="srcIn" spellcheck="false" aria-label="Base64 またはデータURL"></textarea>
    <div class="samples">
      <button type="button" data-sample="png">正しい PNG のデータURL</button>
      <button type="button" data-sample="mismatch">image/png と書いてあるが中身は…</button>
      <button type="button" data-sample="slack">余ったビットが0でない</button>
      <button type="button" data-sample="nob64">;base64 の書き忘れ</button>
      <button type="button" data-sample="plus">+ が空白にならない</button>
      <button type="button" data-sample="svg">SVG にスクリプト</button>
      <button type="button" data-sample="jwtish">ただの base64 文字列</button>
      <button type="button" data-sample="clear">消す</button>
    </div>''',
     '''    <h2>1. Paste</h2>
    <textarea id="srcIn" spellcheck="false" aria-label="Base64 or a data URL"></textarea>
    <div class="samples">
      <button type="button" data-sample="png">a correct PNG data URL</button>
      <button type="button" data-sample="mismatch">says image/png, but inside&hellip;</button>
      <button type="button" data-sample="slack">leftover bits are not 0</button>
      <button type="button" data-sample="nob64">;base64 left out</button>
      <button type="button" data-sample="plus">+ does not become a space</button>
      <button type="button" data-sample="svg">a script inside SVG</button>
      <button type="button" data-sample="jwtish">just a base64 string</button>
      <button type="button" data-sample="clear">clear</button>
    </div>'''),

    ('    <h2>2. 部品に分ける</h2>', '    <h2>2. Split into parts</h2>'),
    ('    <h2>3. 中身は何か</h2>', '    <h2>3. What is inside</h2>'),
    ('    <h3>先頭のバイト列</h3>', '    <h3>The leading bytes</h3>'),
    ('    <h2>4. 気づきにくいところ</h2>', '    <h2>4. Easy to miss</h2>'),
    ('    <p class="none" id="noteNone" hidden>見つかりませんでした。</p>',
     '    <p class="none" id="noteNone" hidden>Nothing found.</p>'),

    ('''    <h2>5. 逆に、作る</h2>
    <p class="none" style="margin:0 0 8px">テキストを入れると base64 とデータURLにします。ファイルを選ぶこともできます（読み込みもブラウザの中だけで行います）。</p>
    <textarea id="encIn" spellcheck="false" aria-label="base64 にしたいテキスト">こんにちは、昼ラボ。</textarea>
    <div class="optrow">
      <label>字表
        <select id="encAlpha">
          <option value="std">標準（+ /）</option>
          <option value="url">base64url（- _）</option>
        </select>
      </label>
      <label><input type="checkbox" id="encPad" checked> 詰めの <code>=</code> を付ける</label>
      <label>MIME <input type="text" id="encMime" value="text/plain" size="14"></label>
      <label><input type="file" id="encFile" aria-label="ファイルを選ぶ"></label>
    </div>
    <div class="tablewrap"><table id="encTbl"><tbody></tbody></table></div>
    <div class="btnrow">
      <button type="button" class="act" id="encToSrc">上の欄に入れて分解する</button>
    </div>''',
     '''    <h2>5. Or go the other way</h2>
    <p class="none" style="margin:0 0 8px">Type some text and it becomes base64 and a data URL. You can pick a file instead (reading it also happens only inside the browser).</p>
    <textarea id="encIn" spellcheck="false" aria-label="text to turn into base64">Hello from the Daytime Lab.</textarea>
    <div class="optrow">
      <label>Alphabet
        <select id="encAlpha">
          <option value="std">standard (+ /)</option>
          <option value="url">base64url (- _)</option>
        </select>
      </label>
      <label><input type="checkbox" id="encPad" checked> add the <code>=</code> padding</label>
      <label>MIME <input type="text" id="encMime" value="text/plain" size="14"></label>
      <label><input type="file" id="encFile" aria-label="choose a file"></label>
    </div>
    <div class="tablewrap"><table id="encTbl"><tbody></tbody></table></div>
    <div class="btnrow">
      <button type="button" class="act" id="encToSrc">put it in the box above and split it</button>
    </div>'''),

    ('''    <h2>自己検査（このブラウザで、いま実行した結果）</h2>
    <p class="selfhead" id="selfHead"></p>
    <div class="self" id="selfOut"></div>
    <p class="none" style="margin-top:8px">この道具は復号も符号化も自前で書いています。
      ブラウザの <code>atob</code> / <code>btoa</code> / <code>TextDecoder</code> と一致するかを、
      ページを開くたびにその場で確かめてここに出しています。</p>''',
     '''    <h2>Self-check (run just now, in this browser)</h2>
    <p class="selfhead" id="selfHead"></p>
    <div class="self" id="selfOut"></div>
    <p class="none" style="margin-top:8px">Both decoding and encoding in this tool are written from scratch.
      Whether they agree with the browser&#39;s <code>atob</code> / <code>btoa</code> / <code>TextDecoder</code>
      is checked on the spot every time the page opens, and the result is printed here.</p>'''),

    ('''  <details>
    <summary>この道具が見ているもの／見ていないもの</summary>
    <ul>
      <li><b>種類の判定は先頭のバイト（マジックナンバー）だけで行っています。</b>
        中身が本当に壊れていないかまでは調べません。「PNG のヘッダで始まっている」は
        「開ける PNG である」を意味しません。</li>
      <li><b>ZIP で始まるものは docx・xlsx・pptx・epub・jar でも同じです。</b>
        中の <code>mimetype</code> まで見ないと区別できないので、まとめて ZIP と表示します。</li>
      <li><b>プレビューは画像だけです。</b> SVG と HTML は、たとえ中身が安全でも、
        このページでは描画しません（描画するとその中のスクリプトがこのページの権限で動くため）。</li>
      <li><b>拒みません。</b> 規格に反する形でも、読めるところまで読んで、
        何がおかしいかを名指しする方針です（規格の適合判定器ではありません）。</li>
      <li><b>MIME と中身の対応表は主要な形式に限っています。</b>
        載っていない MIME を宣言していても「食い違い」とは言いません。</li>
    </ul>
  </details>''',
     '''  <details>
    <summary>What this tool looks at, and what it does not</summary>
    <ul>
      <li><b>The type is decided from the leading bytes (the magic number) alone.</b>
        It does not go on to check whether the content is actually intact. "It starts with a PNG
        header" does not mean "it is a PNG you can open".</li>
      <li><b>Anything starting like a ZIP looks the same whether it is docx, xlsx, pptx, epub or jar.</b>
        Telling them apart means reading the <code>mimetype</code> inside, so they are all shown as ZIP.</li>
      <li><b>Only images are previewed.</b> SVG and HTML are not rendered on this page even when
        their content is safe (rendering them would run any script inside with this page's privileges).</li>
      <li><b>It does not reject anything.</b> Even for a form that breaks the spec, it reads as far as
        it can and names what is wrong (it is not a conformance checker).</li>
      <li><b>The table mapping MIME types to content covers the major formats only.</b>
        A declared MIME type that is not in the table is never called a mismatch.</li>
    </ul>
  </details>'''),

    ('''  <footer>
    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    Base64 は RFC 4648、データURLは RFC 2397 を参照して自前で実装しています。
    Base64 は符号化であって暗号ではありません。読める人には読めます。
  </footer>''',
     '''  <footer>
    Built by Claude&#39;s Daytime Lab (Claude, an AI). Free to use, no sign-up.
    base64 follows RFC 4648 and data URLs follow RFC 2397, both implemented from scratch here.
    base64 is an encoding, not encryption. Anyone who can read it, can read it.
  </footer>'''),
]

# ── ナビ(既存の英語ページと同じ構造) ──────────────────────────────────────
EN_NAV = '''  <nav class="hl-nav">
    <h2>Other tools</h2>
    <ul>
      <li><a href="./regex-why.html">Why doesn&#39;t my regex match?</a></li>
      <li><a href="./replace.html">Regex Replacement Preview</a></li>
      <li><a href="./railroad.html">Regex Railroad Diagrams</a></li>
      <li><a href="./regex-tester.html">Regex Tester</a></li>
      <li><a href="./char-counter.html">Character Counter</a></li>
      <li><a href="./palette.html">Color Palette Generator</a></li>
      <li><a href="./timezone.html">Time Zone Converter</a></li>
      <li><a href="./csv.html">CSV Preview &amp; Diagnostics</a></li>
      <li><a href="./url.html">URL Parser &amp; Builder</a></li>
      <li><a href="./headers.html">HTTP Header Explainer</a></li>
      <li><a href="./jwt.html">JWT Explainer</a></li>
      <li><a href="./password.html">Password Generator &amp; Strength Check</a></li>
      <li><a href="./qr.html">QR Code Generator</a></li>
      <li><a href="./cron.html">Cron Expression Explainer</a></li>
      <li><a href="./contrast.html">Contrast Ratio Checker</a></li>
      <li><a href="./image.html">Image Resizer &amp; Compressor</a></li>
      <li><a href="./page-contrast.html">Whole-Page Contrast Audit</a></li>
      <li><a href="./diff.html">Text Diff</a></li>
      <li><a href="./json.html">JSON Formatter &amp; Validator</a></li>
      <li><a href="./unit.html">Unit Converter</a></li>
      <li><a href="./pattern.html">Japanese Pattern Generator</a></li>
      <li><a href="../base64/">Japanese version</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">Tools index</a> &middot;
      <a href="https://note.com/hirulab">Experiment log (JP)</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''

# ── わざと日本語のまま残すリテラル(理由つき) ───────────────────────────────
KEEP = {
    "　": "isSpaceChar が全角空白 U+3000 を空白として読み飛ばすための処理の定数。画面には出ない",
    "あ": "自己検査の UTF-8 の見本(3バイト)。画面には出ない",
    "Hello, 世界": "自己検査の UTF-8 の見本(1+3バイトの混在)。画面には出ない",
    "改\\n行": "自己検査の UTF-8 の見本(改行を挟む)。画面には出ない",
    "　全角": "自己検査の UTF-8 の見本(先頭に全角空白)。画面には出ない",
}

# ── 文字列の中身だけの差し替え(TR辞書) ────────────────────────────────────
TR = {
    # --- 中身の種類(マジックナンバーの表) ---
    "PNG画像": "PNG image",
    "JPEG画像": "JPEG image",
    "GIF画像": "GIF image",
    "WebP画像": "WebP image",
    "BMP画像": "BMP image",
    "TIFF画像": "TIFF image",
    "アイコン(ICO)": "Icon (ICO)",
    "ZIP書庫（docx・xlsx・epub なども同じ先頭）": "ZIP archive (docx, xlsx and epub start the same way)",
    "WOFFフォント": "WOFF font",
    "WOFF2フォント": "WOFF2 font",
    "TrueTypeフォント": "TrueType font",
    "OpenTypeフォント": "OpenType font",
    "MP3音声": "MP3 audio",
    "WAV音声": "WAV audio",
    "MP4系": "MP4 family",
    "SVG画像": "SVG image",
    "空": "Empty",
    "テキスト（UTF-8として読めた）": "Text (readable as UTF-8)",
    "判別できないバイト列": "Unrecognized bytes",

    # --- 16進ダンプ ---
    '<span class="off">…… 以下 ': '<span class="off">…… ',
    " バイト省略</span>": " more bytes not shown</span>",
    '<span class="off">（0 バイト）</span>': '<span class="off">(0 bytes)</span>',

    # --- 部品の表 ---
    "形": "Form",
    "データURL（RFC 2397）": "Data URL (RFC 2397)",
    "スキーム": "Scheme",
    " <em>（小文字の data と同じ扱い）</em>": " <em>(treated the same as lowercase data)</em>",
    "メディア型": "Media type",
    " <em>（省略されたので既定値）</em>": " <em>(omitted, so this is the default)</em>",
    "引数": "Parameters",
    " <em>（値なし）</em>": " <em>(no value)</em>",
    "あり": "yes",
    "なし <em>（本体はパーセント符号化として読む）</em>": "no <em>(the body is read as percent-encoding)</em>",
    "本体": "Body",
    "<em>（コンマが無いので本体を切り出せません）</em>": "<em>(no comma, so the body cannot be extracted)</em>",
    " 文字 → ": " chars → ",
    " バイト": " bytes",
    "パーセント符号化 ": "percent-encoded ",
    "データURLではありません（base64 の文字列として読みます）": "Not a data URL (read as a plain base64 string)",
    "文字数": "Characters",
    " 文字（詰めの <code>=</code> を除く）": " characters (excluding the <code>=</code> padding)",
    "バイト数": "Bytes",
    "字表": "Alphabet",
    "base64url（<code>-</code> <code>_</code>）": "base64url (<code>-</code> <code>_</code>)",
    "標準（<code>+</code> <code>/</code>）": "standard (<code>+</code> <code>/</code>)",
    '<b style="color:var(--err)">混在</b>': '<b style="color:var(--err)">mixed</b>',
    "<em>この文字列からは区別できません（62・63番の文字が出てこない）</em>":
        "<em>cannot be told apart from this string (characters 62 and 63 never appear)</em>",

    # --- データURL の指摘 ---
    "コンマがありません": "There is no comma",
    "データURLは <code>data:</code> のあとに必ず <code>,</code> が要ります（RFC 2397）。":
        "A data URL must have a <code>,</code> after <code>data:</code> (RFC 2397). ",
    "これが無いと、ブラウザはこの文字列をデータURLとして読み込めません。":
        "Without it, the browser cannot load this string as a data URL. ",
    "<code>&lt;img src&gt;</code> に入れても画像は出ませんが、<b>コンソールに何も出ないことがあります</b>。":
        "Put it in <code>&lt;img src&gt;</code> and no image appears &mdash; but <b>the console may stay silent</b>.",

    "<code>%</code> のあとが16進2桁になっていません": "<code>%</code> is not followed by two hex digits",
    " か所あります。パーセント符号化では <code>%</code> 自体を書くときに ":
        " place(s) like this. In percent-encoding, a literal <code>%</code> has to be written as ",
    "<code>%25</code> と書く必要があります。生の <code>%</code> は壊れた符号として扱われます。":
        "<code>%25</code>. A bare <code>%</code> is treated as a broken escape.",

    "<code>;base64</code> が抜けている可能性があります": "<code>;base64</code> may be missing",
    "本体が base64 の形をしているのに <code>;base64</code> の宣言がありません。":
        "The body has the shape of base64, but there is no <code>;base64</code> declaration. ",
    "この場合ブラウザは<b>base64 として復号せず、その文字そのものを中身として扱います</b>。":
        "In that case the browser <b>does not decode it as base64; it takes the characters themselves as the content</b>. ",
    "画像なら「壊れた画像」になりますが、<b>URL としては正しい</b>ので構文エラーは出ません。":
        "For an image that means a broken image, but <b>the URL itself is valid</b>, so no syntax error is raised.",

    "<code>+</code> は空白になりません": "<code>+</code> does not become a space",
    "クエリ文字列（<code>?a=b+c</code>）では <code>+</code> が空白として読まれますが、":
        "In a query string (<code>?a=b+c</code>) a <code>+</code> is read as a space, but ",
    "<b>データURLの本体はクエリではありません</b>。ここでの <code>+</code> は文字どおりのプラス記号です。":
        "<b>the body of a data URL is not a query</b>. A <code>+</code> here is a literal plus sign. ",
    "同じ「パーセント符号化」でも場所によって規則が違う、という取り違えがよく起きます。":
        "The same name &mdash; percent-encoding &mdash; follows different rules in different places, and that is a common mix-up.",

    "<code>;base64</code> のあとに引数が書かれています": "A parameter is written after <code>;base64</code>",
    "RFC 2397 では <code>;base64</code> はメディア型の<b>最後</b>に置きます。":
        "RFC 2397 puts <code>;base64</code> <b>last</b> in the media type. ",
    "多くのブラウザは前後してもそれなりに読みますが、実装によって解釈が割れる書き方です。":
        "Most browsers read it either way, but this is a form implementations disagree on.",

    "メディア型を省略したときの既定は <code>text/plain;charset=US-ASCII</code> です":
        "Omitting the media type defaults to <code>text/plain;charset=US-ASCII</code>",
    "<b>UTF-8 ではありません。</b> 日本語を <code>data:,</code> のように型なしで書くと、":
        "<b>Not UTF-8.</b> Write non-ASCII text with no type at all, as in <code>data:,</code>, and ",
    "受け手によっては US-ASCII として読まれます。日本語を入れるなら ":
        "some readers will take it as US-ASCII. To carry non-ASCII text, say so: ",
    "<code>data:text/plain;charset=UTF-8,</code> と明示してください。":
        "<code>data:text/plain;charset=UTF-8,</code>.",

    "宣言された文字コードと中身が食い違っているかもしれません": "The declared charset may not match the content",
    "</code> と書かれていますが、中身は UTF-8 として素直に読めます。":
        "</code> is what it says, but the content reads cleanly as UTF-8.",

    "データURLの中に改行が入っています": "There is a line break inside the data URL",
    "HTML の属性や CSS に貼ると壊れます。base64 の側は改行を無視して読める実装が多いのですが、":
        "Paste it into an HTML attribute or into CSS and it breaks. Many base64 readers do ignore line breaks, but ",
    "<b>URL としては改行を含められません</b>。貼る前に取り除いてください。":
        "<b>a URL cannot contain a line break</b>. Strip them before pasting.",

    "データURLが長すぎるかもしれません（": "This data URL may be too long (",
    " 文字）": " characters)",
    "base64 にすると元のバイト数の約 4/3 に増えます。HTML や CSS に埋め込むと ":
        "base64 grows the original by about 4/3. Embed that in HTML or CSS and ",
    "<b>その部分だけキャッシュが効かなくなり</b>、ページを開くたびに毎回転送されます。":
        "<b>that part alone stops being cacheable</b>, so it is transferred again every time the page opens. ",
    "大きいものは普通のファイルとして置いたほうが速くなります。":
        "Anything large is faster served as an ordinary file.",

    # --- base64 の指摘 ---
    "標準の字表と base64url が混ざっています": "The standard alphabet and base64url are mixed together",
    "<code>+</code> <code>/</code> と <code>-</code> <code>_</code> が同じ文字列の中に両方あります。":
        "<code>+</code> <code>/</code> and <code>-</code> <code>_</code> both appear in the same string. ",
    "本来どちらか一方の字表しか使いません。<b>途中で置換処理が二重にかかった疑いがあります。</b>":
        "Only one alphabet should ever be in use. <b>It looks like a replacement step ran twice somewhere.</b>",

    "字表にない文字が ": "Characters outside the alphabet: ",
    " 個あります": " found",
    "見つかったもの: <code>": "What was found: <code>",
    "</code>。": "</code>. ",
    "この道具は<b>読み飛ばして先に進みました</b>が、実装によって扱いが割れるところです。":
        "This tool <b>skipped them and carried on</b>, but implementations disagree here. ",
    "ブラウザの <code>atob</code> は例外を投げ、Python の ":
        "The browser&#39;s <code>atob</code> throws, while Python&#39;s ",
    "<code>base64.urlsafe_b64decode</code> は<b>既定で黙って捨てます</b>":
        "<code>base64.urlsafe_b64decode</code> <b>drops them silently by default</b>",
    "（<code>validate=True</code> を書いて初めて拒みます）。":
        " (it only rejects them once you write <code>validate=True</code>).",

    "<code>%</code> が混ざっています（二重に符号化された疑い）":
        "A <code>%</code> is mixed in (it looks doubly encoded)",
    "base64 の字表に <code>%</code> はありません。": "There is no <code>%</code> in the base64 alphabet. ",
    "<b>base64 の文字列をさらに URL 符号化した</b>ものが、戻されないまま渡ってきた形です。":
        "This is <b>a base64 string that was then URL-encoded</b> and handed on without being decoded back. ",
    "典型は <code>+</code> が <code>%2B</code> に、<code>/</code> が <code>%2F</code> になっているもの。":
        "The typical sign is <code>+</code> turned into <code>%2B</code> and <code>/</code> into <code>%2F</code>.",

    "文字数を4で割った余りが1です": "The number of characters leaves a remainder of 1 when divided by 4",
    "base64 は1文字が6ビットなので、4で割って1余る長さは<b>どうやってもバイトの境界に届きません</b>":
        "Each base64 character carries 6 bits, so a length that leaves 1 over <b>can never reach a byte boundary</b>",
    "（6ビットでは1バイトに足りない）。<b>末尾が欠けています。</b>":
        " (6 bits is short of a byte). <b>The end is missing.</b> ",
    "この道具は最後の1文字を落として残りを読みました。":
        "This tool dropped the last character and read the rest.",

    "詰めの <code>=</code> のあとにデータの文字が続いています":
        "Data characters continue after the <code>=</code> padding",
    "<code>=</code> は終わりの印なので途中には現れません。":
        "<code>=</code> marks the end, so it never appears in the middle. ",
    "<b>2つの base64 文字列が連結された</b>か、切り貼りの失敗が疑われます。":
        "Either <b>two base64 strings were joined together</b> or a copy-and-paste went wrong.",

    "詰めの <code>=</code> がありません（本来 ": "There is no <code>=</code> padding (",
    " 個）": " expected)",
    "RFC 4648 は詰めを求めていますが、<b>省く流儀も広く使われています</b>":
        "RFC 4648 asks for padding, but <b>leaving it out is widely practised too</b>",
    "（JWT の base64url は詰めを付けないと決まっています）。多くの実装は受け取りますが、":
        " (JWT&#39;s base64url is defined to carry no padding). Most implementations accept it, but ",
    "<b>厳密に検査する実装では拒まれます</b>。": "<b>a strict validator rejects it</b>.",

    "詰めの <code>=</code> の数が合いません（":
        "The number of <code>=</code> padding characters does not match (",
    " 個、本来 ": " present, ",
    "詰めは 0・1・2 個のいずれかで、データの文字数から一意に決まります。":
        "Padding is 0, 1 or 2 characters, fixed uniquely by the number of data characters. ",
    "多すぎる <code>=</code> は<b>大半の実装が黙って無視します</b>。":
        "Extra <code>=</code> characters are <b>silently ignored by most implementations</b>.",

    "空白や改行が含まれています": "It contains whitespace or line breaks",
    "MIME（RFC 2045）は76文字ごとの改行を認めますが、":
        "MIME (RFC 2045) allows a line break every 76 characters, but ",
    "<b>RFC 4648 の base64 は空白を認めていません</b>。":
        "<b>base64 in RFC 4648 allows no whitespace at all</b>. ",
    "ブラウザの <code>atob</code> は空白を読み飛ばしますが、拒む実装もあります。":
        "The browser&#39;s <code>atob</code> skips whitespace, but some implementations reject it. ",
    "この道具は読み飛ばしました。": "This tool skipped it.",

    "余ったビットが0ではありません（正規形ではない base64）":
        "The leftover bits are not 0 (non-canonical base64)",
    "最後の文字 <code>": "The last character <code>",
    "</code> は6ビットのうち ": "</code> has, of its 6 bits, ",
    " ビットが<b>バイトに使われずに捨てられます</b>。その捨てられる部分が0でないので、":
        " that are <b>thrown away without landing in any byte</b>. Those discarded bits are not 0, so ",
    "<b>これと違う文字列が、まったく同じバイト列に復号されます</b>":
        "<b>a different string decodes to exactly the same bytes</b>",
    "（最後を <code>": " (the one ending in <code>",
    "</code> にしたもの）。": "</code>). ",
    "RFC 4648 §3.5 はこれを拒むことも認めていますが、<b>ブラウザの <code>atob</code> も ":
        "RFC 4648 §3.5 allows rejecting this, but <b>the browser&#39;s <code>atob</code> and ",
    "Python も黙って受け取ります</b>。": "Python both accept it silently</b>. ",
    "「base64 が一致するか」で同一性を判定していると、ここで取り違えます。":
        "If you decide whether two things are the same by asking whether their base64 matches, this is where you get it wrong.",

    "base64 は暗号ではありません": "base64 is not encryption",
    "読みにくくなるだけで、誰でも元に戻せます（この道具がやっているのがそれです）。":
        "It only makes things harder to read; anyone can turn it back (that is all this tool is doing). ",
    "秘密の値を base64 にして「隠した」ことにはなりません。":
        "Putting a secret into base64 does not hide it.",

    # --- 宣言と中身の食い違い ---
    "宣言された型と中身が食い違っています": "The declared type does not match the content",
    "</code> と書かれていますが、先頭のバイトは <b>":
        "</code> is what it says, but the leading bytes are those of <b>",
    "</b>（<code>": "</b> (<code>",
    "</code>）のものです。": "</code>). ",
    "<b>ブラウザの多くは中身のほうを信じて表示してしまう</b>ので、":
        "<b>Most browsers trust the content and display it anyway</b>, so ",
    "見た目には気づけません。<code>&lt;img&gt;</code> では動いても、":
        "you cannot tell by looking. It may work in <code>&lt;img&gt;</code>, but ",
    "型で振り分ける処理（保存時の拡張子・CDN・検査器）は宣言のほうを見ます。":
        "anything that branches on the type &mdash; the extension when saving, a CDN, a scanner &mdash; looks at the declaration.",

    # --- SVG / data:text/html ---
    "<code>on…=</code> のイベント属性": "an <code>on…=</code> event attribute",
    "SVG の中に実行されうるものが入っています": "The SVG contains something that can execute",
    "見つかったもの: ": "What was found: ",
    "・": ", ",
    "。": ". ",
    "SVG を <code>&lt;img&gt;</code> で表示する分にはスクリプトは動きませんが、":
        "Shown through <code>&lt;img&gt;</code> the script does not run, but ",
    "<b><code>&lt;object&gt;</code>・<code>&lt;embed&gt;</code>・直接ページを開く・":
        "<b><code>&lt;object&gt;</code>, <code>&lt;embed&gt;</code>, opening the file directly, or ",
    "インラインで貼る</b>と動きます。受け取った SVG をそのまま貼る作りは危険です。":
        "pasting it inline</b> all run it. Pasting a received SVG as-is is dangerous. ",
    "（このページは SVG を描画しません。）": "(This page does not render SVG.)",

    "<code>data:text/html</code> はリンク先として開けません":
        "<code>data:text/html</code> cannot be opened as a link target",
    "Chrome と Firefox は<b>トップレベルの遷移でデータURLを開くのを禁止しています</b>":
        "Chrome and Firefox <b>forbid opening a data URL as a top-level navigation</b>",
    "（<code>&lt;a href=\\\"data:text/html,…\\\"&gt;</code>、<code>window.open</code>、アドレス欄への貼り付け）。":
        " (<code>&lt;a href=\\\"data:text/html,…\\\"&gt;</code>, <code>window.open</code>, pasting into the address bar). ",
    "フィッシングに使われたための制限です。<code>&lt;iframe&gt;</code> でなら読み込めますが、":
        "The restriction exists because it was used for phishing. It can still be loaded in an <code>&lt;iframe&gt;</code>, but ",
    "そのフレームのオリジンは <code>null</code> になります。":
        "that frame&#39;s origin becomes <code>null</code>.",

    # --- 復号したバイト列についての指摘 ---
    "先頭に BOM（<code>EF BB BF</code>）があります": "There is a BOM (<code>EF BB BF</code>) at the start",
    "見えない3バイトです。JSON として読ませると<b>先頭でエラーになります</b>し、":
        "Three invisible bytes. Read as JSON it <b>errors on the very first character</b>, and ",
    "CSV の1列目の名前がずれる原因にもなります。":
        "it is also why the name of the first CSV column comes out wrong. ",
    "Python の <code>TextDecoder</code> 相当や多くのエディタは黙って落とすので、":
        "Python&#39;s equivalent of <code>TextDecoder</code>, and many editors, drop it silently, so ",
    "<b>目で見ても分かりません</b>。": "<b>you cannot see it by looking</b>.",

    "必要より長い形で書かれた文字（overlong）": "a character written longer than it needs to be (overlong)",
    "サロゲートの符号位置がそのまま符号化されている": "a surrogate code point encoded as-is",
    "末尾が途中で切れている": "the end is cut off mid-character",
    # ⚠ この3つは「前置き + 位置 + 後置き」で組み立てる。日本語は
    #    「…が <位置> バイト目にあります」だが、英語は数字がすぐ後ろに来る形にする必要がある
    #    (語順を変えると「文字列を空にすると一致」の検査が通らない)。
    #    ud.badAt は ok=false のとき必ず 0 以上になるので、後置きは空でよい。
    "UTF-8 として読めないバイトが ": "A byte that cannot be read as UTF-8, at offset ",
    " バイト目に": "",
    "あります": "",
    "<b>ブラウザの <code>TextDecoder</code> は既定でこれを <code>U+FFFD</code>（&#xfffd;）に置き換えて黙ります。</b>":
        "<b>The browser&#39;s <code>TextDecoder</code> replaces this with <code>U+FFFD</code> (&#xfffd;) by default and says nothing.</b> ",
    "「文字化けした」と見えるものの多くは、この置き換えが起きたあとの姿です。":
        "Most of what looks like mojibake is what is left after that replacement.",

    "NUL バイト（<code>00</code>）が ": "NUL bytes (<code>00</code>): ",
    "テキストとして扱う処理の多くは、ここで<b>文字列が終わったとみなします</b>（C 由来の実装）。":
        "Most code that handles this as text <b>treats the string as finished</b> here (a habit inherited from C). ",
    "先が捨てられても例外は出ません。": "Whatever follows is dropped, and no exception is raised.",
    "画面に出ない制御文字が ": "Control characters that never show on screen: ",
    "見た目では分かりません。比較や検索が合わない原因になります。":
        "You cannot see them. They are a common reason comparisons and searches fail to match.",

    # --- 余ったビットの図 ---
    '<div class="slackbox">最後の文字 <code>': '<div class="slackbox">The last character <code>',
    '</code> の6ビット: <span class="bits"><span class="keep">':
        '</code> as 6 bits: <span class="bits"><span class="keep">',
    " — 赤い ": " &mdash; the ",
    " ビットは<b>どのバイトにも入らずに捨てられます</b>。":
        " bits in red are <b>thrown away without landing in any byte</b>.",
    " ここは 0 なので正規形です。": " They are 0 here, so this is the canonical form.",
    " ここが 0 でないので、最後を <code>": " They are not 0 here, so the string ending in <code>",
    "</code> にした文字列も<b>まったく同じバイト列</b>になります。":
        "</code> instead decodes to <b>exactly the same bytes</b>.",

    # --- 中身の行とプレビュー ---
    '<span class="badge ok">宣言と一致</span>': '<span class="badge ok">matches the declaration</span>',
    '<span class="badge ng">宣言は ': '<span class="badge ng">declared as ',
    "中身は <b>": "Content: <b>",
    "貼り付けられた画像のプレビュー": "Preview of the pasted image",
    "中身から判定した型でこのページ内に描いています（通信はしていません）。":
        "Drawn inside this page using the type detected from the content (no network request was made).",
    "\\n……（以下省略）": "\\n…… (truncated)",
    "SVG と HTML は、中に実行されうるものが入っている場合があるのでこのページでは描画しません。文字として表示しています。":
        "SVG and HTML can contain something that executes, so this page does not render them. They are shown as text.",

    # --- 作る側 ---
    "元": "Source",
    "長さ": "Length",
    " 文字（元の ": " characters (",
    " 倍）": "× the original)",
    "データURL": "Data URL",

    # --- 自己検査 ---
    "符号化が btoa と一致する（": "Encoding matches btoa (",
    " 件）": " cases)",
    " 件ちがう": " differ",
    "復号が atob と一致する（": "Decoding matches atob (",
    "符号化してから復号すると元に戻る（": "Encode then decode gives the original back (",
    " 件・字表と詰めの有無を変えて）": " cases, varying the alphabet and the padding)",
    "UTF-8 の読み書きが TextEncoder / TextDecoder と一致する（":
        "UTF-8 read and write match TextEncoder / TextDecoder (",
    "QQ== と QR== がブラウザで同じ1バイトに戻る（余ったビットの実演）":
        "QQ== and QR== decode to the same single byte in this browser (the leftover-bits demo)",
    "このブラウザでは再現しませんでした": "Not reproduced in this browser",
    " 項目すべて一致</b>（このブラウザで、いま実行した結果）":
        " checks all match</b> (run just now, in this browser)",
    " 項目が食い違いました</b>（": " checks disagreed</b> (",
    " 項目は一致）": " matched)",
}


def translate_literals(src, tr, keep):
    """JS を1文字ずつ読み、**文字列リテラルの中身だけ**を辞書と完全一致で差し替える。

    引用符の種類(' " `)を問わない。日本語を含むのに tr にも keep にも無いものが
    見つかったら、その一覧を返す(呼び出し側で止める)。
    """
    out, missing = [], []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in ("'", '"', "`"):
            q, j = c, i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    break
                if src[j] == "\n" and q != "`":
                    break
                j += 1
            if j < n and src[j] == q:
                body = src[i + 1:j]
                if body in tr:
                    body = tr[body]
                elif JA_CHARS.search(body) and body not in keep:
                    missing.append(body)
                out.append(q + body + q)
                i = j + 1
                continue
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(src[i:j])
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(src[i:j])
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out), missing


def script_span(html):
    """ページ本体の <script>…</script>(JSON-LD ではないほう)の範囲を返す。"""
    m = re.search(r"<script>\n(.*)</script>", html, re.S)
    if not m:
        sys.exit("本体のスクリプトが見つかりません")
    return m.start(1), m.end(1)


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "base64" / "index.html"
    en_path = docs / "en" / "base64.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'  <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not nav:
        sys.exit("ナビが見つかりません")
    en = en[:nav.start()] + EN_NAV + en[nav.end():]

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
    print("わざと残した日本語のリテラル: %d 件(%s)" % (len(kept), "・".join(sorted(set(kept)))))
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
