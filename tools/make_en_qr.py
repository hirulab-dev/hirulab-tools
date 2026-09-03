#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「QRコード作成」の英語版を、日本語版から作る(2026-08-28)。

`make_en_base64.py` と同じ方式。**日本語版が唯一の原本**で、英語版は毎回ここから作り直す。

1. HTML(head・本文・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. できた英語版について、**「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**
   ことを確かめる。通れば、符号化・リード・ソロモン・ブロック交互配置・マスク評価は
   1バイトも違わない = `test_qr.py` の 587,455 モジュール一致がそのまま英語版にも効く
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

★なぜ QR を先にやったか(2026-08-28 の枠の頭で決めた)
  持ち込み記事(`outputs/launch-drafts.md`)の検証の表に QR と cron の2行が載るのに、
  どちらも英語版のページが無かった。`en-cron-plan.md` に「軽いほうから片づける手もある。
  決めるのは次の枠の頭で、リテラルを数えてから」と書いてあったので数えた:

      qr   : 日本語を含むリテラル 55件(重複を除くと 54件)
      cron : 213件(重複を除くと 164件)

  **QR は cron の3分の1**で、しかも `en-cron-plan.md` が挙げた「同じリテラルが
  違う役目で使い回されている」衝突が QR には1件も無い(重複していたのは
  「この配色のコントラスト比は 」の1件だけで、これは同じ役目)。→ QR を先にやる。

使い方: python lab/scripts/make_en_qr.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (translate_css_comments,
                       translate_comments,  # noqa: E402
                       JA_CHARS, code_japanese, script_span,  # noqa: E402
                       translate_literals)

SITE = "https://hirulab-dev.github.io/hirulab-tools"

# 「画面に出るところに日本語が残っていないか」を見るときの文字の範囲。
# ひらがな・カタカナ・漢字・和文の約物・全角空白。
HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>QRコード作成 — Wi-Fiのパスワードを入れても、どこにも送りません</title>',
     '<title>QR Code Generator — type in your Wi-Fi password; it goes nowhere</title>'),

    ('<meta name="description" content="テキスト・URL・Wi-Fi・メール・電話からQRコードを作ります。生成はブラウザの中だけで完結し、入力した内容は一切送信されません。中身がどう符号化されたか（型番・マスク・語数）まで表示します。PNG/SVGで保存できます。">',
     '<meta name="description" content="Builds a QR code from text, a URL, Wi-Fi credentials, an email address or a phone number. Everything happens inside the browser and nothing you type is ever sent anywhere. It also shows how the content was encoded — version, mask pattern and codeword counts. Save as PNG or SVG.">'),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/qr/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/qr/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/qr.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/qr.html">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/qr.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/qr/">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="QRコード作成">',
     '<meta property="og:title" content="QR Code Generator">'),

    ('<meta property="og:description" content="テキスト・URL・Wi-Fi・メール・電話からQRコードを作ります。入力した内容はどこにも送信されません。中身がどう符号化されたかまで表示します。">',
     '<meta property="og:description" content="Builds a QR code from text, a URL, Wi-Fi credentials, an email address or a phone number. Nothing you type is ever sent anywhere. It also shows how the content was encoded.">'),

    ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/qr/">',
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/qr.html">'),

    ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-qr.png">',
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-qr-en.png">'),

    ('<meta name="twitter:title" content="QRコード作成">',
     '<meta name="twitter:title" content="QR Code Generator">'),

    ('<meta name="twitter:description" content="Wi-Fiのパスワードを入れても、どこにも送りません。生成はブラウザの中だけで完結します。">',
     '<meta name="twitter:description" content="Type in your Wi-Fi password; it goes nowhere. Everything happens inside the browser.">'),

    ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-qr.png">',
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-qr-en.png">'),

    ('''  "name": "QRコード作成",
  "url": "https://hirulab-dev.github.io/hirulab-tools/qr/",
  "description": "テキスト・URL・Wi-Fi設定・メール・電話番号・位置情報からQRコードを生成します。符号化はページ内のJavaScriptだけで行い、通信は一切しません。選ばれた型番・誤り訂正レベル・マスクパターンとその評価点まで表示し、PNG と SVG で保存できます。",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-qr.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "QR Code Generator",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/qr.html",
  "description": "Generates a QR code from text, a URL, Wi-Fi settings, an email address, a phone number or a location. The encoding is done entirely by JavaScript inside the page and no network request is ever made. It shows the version, error correction level and mask pattern that were chosen, along with the penalty scores, and saves as PNG or SVG.",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-qr-en.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude's Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>QRコード作成</h1>
  <p class="lead">
    テキスト・URL・Wi-Fi・メール・電話からQRコードを作ります。
    <strong>符号化はこのページの中で全部やっています。</strong>
    出来上がりの型番・マスクパターン・語数の内訳まで表示するので、中で何が起きたかが見えます。
  </p>

  <div class="privacy">
    <strong>入力した内容は、どこにも送信されません。</strong>
    QRコードのライブラリも外部から読み込まず、符号化の処理をこのページに直接書いています。
    読み込んだあとは通信を切っても動きます。<strong>Wi-Fiのパスワードを入れても大丈夫なのはそのためです。</strong>
  </div>

  <h2>作る</h2>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>QR Code Generator</h1>
  <p class="lead">
    Builds a QR code from text, a URL, Wi-Fi credentials, an email address or a phone number.
    <strong>All of the encoding happens inside this page.</strong>
    It also shows the version, the mask pattern and the codeword breakdown of the finished code,
    so you can see what actually happened in there.
  </p>

  <div class="privacy">
    <strong>Nothing you type is ever sent anywhere.</strong>
    There is no QR library loaded from anywhere else either &mdash; the encoder is written directly
    into this page. Once the page has loaded you can go offline and it still works.
    <strong>That is why it is fine to type in your Wi-Fi password.</strong>
  </div>

  <h2>Build</h2>'''),

    ('''  <div class="tabs" id="tabs" role="group" aria-label="内容の種類">
    <button data-kind="text" aria-pressed="true">テキスト / URL</button>
    <button data-kind="wifi" aria-pressed="false">Wi-Fi</button>
    <button data-kind="mail" aria-pressed="false">メール</button>
    <button data-kind="tel" aria-pressed="false">電話</button>
    <button data-kind="sms" aria-pressed="false">SMS</button>
    <button data-kind="geo" aria-pressed="false">地図の座標</button>
  </div>''',
     '''  <div class="tabs" id="tabs" role="group" aria-label="Kind of content">
    <button data-kind="text" aria-pressed="true">Text / URL</button>
    <button data-kind="wifi" aria-pressed="false">Wi-Fi</button>
    <button data-kind="mail" aria-pressed="false">Email</button>
    <button data-kind="tel" aria-pressed="false">Phone</button>
    <button data-kind="sms" aria-pressed="false">SMS</button>
    <button data-kind="geo" aria-pressed="false">Map coordinates</button>
  </div>'''),

    ('      <label for="i-text">文字列（URLでもそのまま貼ってください）</label>',
     '      <label for="i-text">Text (paste a URL here as well)</label>'),

    ('          <label for="i-ssid">ネットワーク名（SSID）</label>',
     '          <label for="i-ssid">Network name (SSID)</label>'),

    ('          <label for="i-wpass">パスワード</label>',
     '          <label for="i-wpass">Password</label>'),

    ('''          <label for="i-wenc">暗号化方式</label>
          <select id="i-wenc">
            <option value="WPA">WPA / WPA2 / WPA3</option>
            <option value="WEP">WEP（古い方式）</option>
            <option value="nopass">パスワードなし</option>
          </select>''',
     '''          <label for="i-wenc">Encryption</label>
          <select id="i-wenc">
            <option value="WPA">WPA / WPA2 / WPA3</option>
            <option value="WEP">WEP (obsolete)</option>
            <option value="nopass">No password</option>
          </select>'''),

    ('''          <label for="i-whidden">SSIDが非公開（ステルス）か</label>
          <select id="i-whidden">
            <option value="">いいえ</option>
            <option value="1">はい</option>
          </select>''',
     '''          <label for="i-whidden">Is the SSID hidden?</label>
          <select id="i-whidden">
            <option value="">No</option>
            <option value="1">Yes</option>
          </select>'''),

    ('''      <p class="note">読み取ると、そのままWi-Fiに接続できるコードになります。来客用の紙に貼る想定です。
        <strong>ここに入れたパスワードも送信されません。</strong></p>''',
     '''      <p class="note">Scanning this connects the device to the network. It is meant for the printed
        card you leave out for guests. <strong>The password you type here is not sent anywhere either.</strong></p>'''),

    ('        <label for="i-mto">宛先アドレス</label>',
     '        <label for="i-mto">To</label>'),

    ('          <label for="i-msub">件名（任意）</label>',
     '          <label for="i-msub">Subject (optional)</label>'),

    ('        <label for="i-mbody">本文（任意）</label>\n        <textarea id="i-mbody" style="min-height:64px"></textarea>',
     '        <label for="i-mbody">Body (optional)</label>\n        <textarea id="i-mbody" style="min-height:64px"></textarea>'),

    ('''      <label for="i-tel">電話番号</label>
      <input type="text" id="i-tel" spellcheck="false" autocomplete="off" placeholder="0312345678">
      <p class="note">読み取ると発信画面が開きます（多くの端末では、すぐには発信されません）。</p>''',
     '''      <label for="i-tel">Phone number</label>
      <input type="text" id="i-tel" spellcheck="false" autocomplete="off" placeholder="+12025550123">
      <p class="note">Scanning this opens the dialler (on most devices it does not place the call by itself).</p>'''),

    ('        <label for="i-sto">宛先の電話番号</label>',
     '        <label for="i-sto">Recipient number</label>'),

    ('        <label for="i-sbody">本文（任意）</label>\n        <textarea id="i-sbody" style="min-height:64px"></textarea>',
     '        <label for="i-sbody">Message (optional)</label>\n        <textarea id="i-sbody" style="min-height:64px"></textarea>'),

    ('          <label for="i-lat">緯度</label>', '          <label for="i-lat">Latitude</label>'),
    ('          <label for="i-lon">経度</label>', '          <label for="i-lon">Longitude</label>'),

    ('''        <label for="i-ecl">誤り訂正レベル</label>
        <select id="i-ecl">
          <option value="L">L — 約7%まで復元</option>
          <option value="M" selected>M — 約15%まで復元</option>
          <option value="Q">Q — 約25%まで復元</option>
          <option value="H">H — 約30%まで復元</option>
        </select>''',
     '''        <label for="i-ecl">Error correction level</label>
        <select id="i-ecl">
          <option value="L">L &mdash; recovers up to about 7%</option>
          <option value="M" selected>M &mdash; recovers up to about 15%</option>
          <option value="Q">Q &mdash; recovers up to about 25%</option>
          <option value="H">H &mdash; recovers up to about 30%</option>
        </select>'''),

    ('        <label for="i-scale">1マスの大きさ（px）</label>',
     '        <label for="i-scale">Module size (px)</label>'),

    ('        <label for="i-quiet">まわりの余白（マス）</label>',
     '        <label for="i-quiet">Quiet zone (modules)</label>'),

    ('        <label for="i-fg">前景色（濃いほう）</label>',
     '        <label for="i-fg">Foreground (the dark one)</label>'),

    ('        <label for="i-bg">背景色</label>', '        <label for="i-bg">Background</label>'),

    ('''        <label for="i-boost">容量が余ったら訂正レベルを上げる</label>
        <select id="i-boost">
          <option value="1" selected>上げる（おすすめ）</option>
          <option value="">指定どおりにする</option>
        </select>''',
     '''        <label for="i-boost">Raise the correction level when there is room</label>
        <select id="i-boost">
          <option value="1" selected>Raise it (recommended)</option>
          <option value="">Use exactly what I picked</option>
        </select>'''),

    ('  <h2>できたもの</h2>', '  <h2>The result</h2>'),

    ('''        <button class="primary" id="dl-png">PNGで保存</button>
        <button id="dl-svg">SVGで保存</button>''',
     '''        <button class="primary" id="dl-png">Save as PNG</button>
        <button id="dl-svg">Save as SVG</button>'''),

    ('        <button id="copy-txt">符号化した文字列をコピー</button>',
     '        <button id="copy-txt">Copy the encoded string</button>'),

    ('  <h2>中で何が起きたか</h2>', '  <h2>What happened in there</h2>'),

    ('''  <h3>マスクパターンの選ばれ方</h3>
  <p class="note" style="margin-top:0">
    QRコードは、白黒の偏りを減らすために8通りの「マスク」を全部試して、
    <strong>評価点（減点方式）がいちばん低いものを採用します。</strong>下は今回の8通りの点数です。
  </p>''',
     '''  <h3>How the mask pattern gets chosen</h3>
  <p class="note" style="margin-top:0">
    To keep the dark and light modules from clumping, a QR encoder tries all eight
    &ldquo;masks&rdquo; and <strong>keeps the one with the lowest penalty score.</strong>
    Below are the eight scores for the code above.
  </p>'''),

    ('''  <h2>この道具の作り</h2>
  <dl>
    <dt>ライブラリを使っていません</dt>
    <dd>JIS X 0510 / ISO 18004 の手順（モード選択 → ビット列化 → リード・ソロモン符号での誤り訂正語の付加 →
        ブロックの交互配置 → 型番ごとの機能パターン配置 → 8通りのマスク評価）を、このページの中で書いています。
        外部スクリプトの読み込みが1つもないので、通信が発生しません。</dd>
    <dt>入力に応じてモードを選びます</dt>
    <dd>数字だけなら「数字モード」（3文字を10ビット）、英大文字と記号だけなら「英数モード」（2文字を11ビット）、
        それ以外は「バイトモード」（UTF-8で1バイト8ビット）。同じ内容でも、数字だけにするとコードは小さくなります。</dd>
    <dt>余った容量は訂正力に回します</dt>
    <dd>型番（大きさ）が変わらない範囲で誤り訂正レベルを上げられるときは、既定で上げます。
        大きさが同じなら、汚れや印刷のかすれに強いほうが得だからです。上の設定で切れます。</dd>
  </dl>''',
     '''  <h2>How this tool is built</h2>
  <dl>
    <dt>No library is used</dt>
    <dd>The procedure in JIS X 0510 / ISO 18004 (pick a mode &rarr; turn it into a bit string &rarr;
        add Reed-Solomon error correction codewords &rarr; interleave the blocks &rarr; place the
        function patterns for that version &rarr; score all eight masks) is written out inside this page.
        Not one external script is loaded, so no network request happens.</dd>
    <dt>The mode is picked from what you type</dt>
    <dd>Digits only gets numeric mode (three characters in ten bits); uppercase letters and a few
        symbols get alphanumeric mode (two characters in eleven bits); anything else gets byte mode
        (UTF-8, eight bits per byte). The same message written with digits only produces a smaller code.</dd>
    <dt>Spare capacity is spent on error correction</dt>
    <dd>When the error correction level can be raised without changing the version (the size), it is
        raised by default. If the code is the same size either way, the one that survives smudges and
        faint printing is the better deal. You can turn this off above.</dd>
  </dl>'''),

    ('''  <h2>正直に書いておくこと</h2>
  <div class="limits">
    <ul>
      <li><strong>漢字モードには対応していません。</strong>QRコードには日本語を効率よく詰める「漢字モード」
        （Shift_JISで1文字13ビット）がありますが、そのための変換表が大きいので入れていません。
        日本語はUTF-8のバイトモードで入ります（1文字3バイト＝24ビット）。
        <strong>そのぶん、日本語の長文はコードが大きめになります。</strong></li>
      <li><strong>マイクロQRコードには対応していません。</strong>通常のQRコード（型番1〜40）だけです。</li>
      <li><strong>真ん中にロゴを載せる機能は付けていません。</strong>
        載せると読み取り率が落ちることがあり、どのくらい落ちるかをこの場で測れないためです。</li>
      <li><strong>マスクの評価は「形式情報を入れる前」に行っています。</strong>
        規格（7.8.3）のこの部分は実装によって解釈が分かれていて、形式情報を入れた状態で評価する実装もあります。
        どちらでも読めるコードができますが、選ばれるマスク番号が変わることがあります。
        この道具は、評価の前に形式情報を入れない読み方を採っています。</li>
      <li><strong>できたコードは必ず実機で読んでから使ってください。</strong>
        特に印刷する場合、小さすぎる・余白が足りない・色のコントラストが低いと読めません。
        余白は4マス以上、前景と背景は白黒に近いほど安全です。</li>
    </ul>
  </div>''',
     '''  <h2>Things worth saying plainly</h2>
  <div class="limits">
    <ul>
      <li><strong>Kanji mode is not supported.</strong> QR codes have a kanji mode that packs Japanese
        efficiently (thirteen bits per character in Shift_JIS), but the conversion table it needs is
        large, so it is not included here. Japanese goes in through UTF-8 byte mode instead
        (three bytes, twenty-four bits, per character).
        <strong>Long Japanese text therefore produces a larger code than it strictly has to.</strong></li>
      <li><strong>Micro QR is not supported.</strong> Only ordinary QR codes, versions 1 to 40.</li>
      <li><strong>There is no logo-in-the-middle feature.</strong>
        Covering the centre can lower the scan rate, and there is no way to measure how much it lowers
        it from inside this page.</li>
      <li><strong>The masks are scored before the format information is written in.</strong>
        Implementations read this part of the standard (7.8.3) differently, and some score the masks
        with the format information already in place. Either reading produces a scannable code, but the
        mask number that wins can differ. This tool scores without the format information present.</li>
      <li><strong>Always scan the finished code with a real device before you use it.</strong>
        Printing is where it goes wrong: too small, too little quiet zone, or too little contrast and
        it will not read. Keep at least four modules of quiet zone, and the closer the two colours are
        to black and white the safer you are.</li>
    </ul>
  </div>'''),

    ('''  <h2>QRコードそのものの注意</h2>
  <ul>
    <li>QRコードは<strong>見ただけでは行き先が分かりません。</strong>知らない場所に貼られたコードを読んで、
      出てきたURLをそのまま開かないでください（貼り替えによる詐欺が実際に起きています）。</li>
    <li>短縮URLを入れると、コードは小さくなりますが、行き先はさらに見えなくなります。
      配る相手のことを考えると、素のURLのほうが親切です。</li>
    <li>このページで作るコードは<strong>「静的」</strong>です。作ったあとに行き先を変えることはできません。
      裏を返すと、<strong>あとから第三者に行き先を差し替えられる心配もありません</strong>
      （行き先を変えられる「動的QR」は、業者のサーバーを経由します）。</li>
  </ul>''',
     '''  <h2>About QR codes in general</h2>
  <ul>
    <li>A QR code <strong>does not show you where it leads.</strong> Do not scan a code stuck up in a
      place you do not know and then open whatever URL comes out &mdash; codes get pasted over as a
      scam, and it does happen.</li>
    <li>A shortened URL makes the code smaller, but it hides the destination even further. For the
      people you are handing it to, the plain URL is the kinder choice.</li>
    <li>The codes this page builds are <strong>static</strong>: the destination cannot be changed after
      the fact. Read the other way round, that means
      <strong>nobody else can swap the destination later either</strong>
      (a &ldquo;dynamic QR&rdquo; whose target can be changed goes through a vendor&#39;s server).</li>
  </ul>'''),

    ('''    QRコードは株式会社デンソーウェーブの登録商標です。この道具は同社とは関係のない、規格（JIS X 0510 / ISO/IEC 18004）にもとづく実装です。
    <br>作: <strong>クロードの昼ラボ</strong>（AIのClaudeが書いています） — このページは通信を一切行いません。''',
     '''    QR Code is a registered trademark of DENSO WAVE INCORPORATED. This tool is not affiliated with them;
    it is an implementation of the published standard (JIS X 0510 / ISO/IEC 18004).
    <br>Built by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) &mdash;
    this page makes no network requests at all.'''),
]

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
      <li><a href="./base64.html">Base64 &amp; Data URL Explainer</a></li>
      <li><a href="./cron.html">Cron Expression Explainer</a></li>
      <li><a href="./contrast.html">Contrast Ratio Checker</a></li>
      <li><a href="./image.html">Image Resizer &amp; Compressor</a></li>
      <li><a href="./page-contrast.html">Whole-Page Contrast Audit</a></li>
      <li><a href="./diff.html">Text Diff</a></li>
      <li><a href="./json.html">JSON Formatter &amp; Validator</a></li>
      <li><a href="./unit.html">Unit Converter</a></li>
      <li><a href="./pattern.html">Japanese Pattern Generator</a></li>
      <li><a href="./date.html">Japanese Date Calculator</a></li>
      <li><a href="./take-home.html">Japan Take-Home Pay Calculator</a></li>
      <li><a href="./frima-profit.html">Flea-Market Profit Calculator</a></li>
      <li><a href="../qr/">Japanese version</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">Tools index</a> &middot;
      <a href="https://note.com/hirulab">Experiment log (JP)</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''

# ── わざと日本語のまま残すリテラル(理由つき) ───────────────────────────────
# QR には1件も無い。符号化器は数値と定数だけで書かれていて、日本語のリテラルは
# 全部「画面に出す文言」だった。
KEEP = {}

# ★2026-09-03 夜 追加(コメントも訳す)。⚠ 訳は行数を変えない・訳の中に日本語を書かない。
COMMENTS = {
    '/* ============================================================\n'
    '   QRコード符号化（JIS X 0510 / ISO 18004）\n'
    '   ライブラリ不使用。以下は全部この場で計算している。\n'
    '   ============================================================ */':
    '/* ============================================================\n'
    '   QR code encoding (JIS X 0510 / ISO 18004)\n'
    '   No library. Everything below is computed right here.\n'
    '   ============================================================ */',

    '// 誤り訂正レベル: ord = 表の添字, fmt = 形式情報に埋める2ビット':
    '// Error-correction level: ord = index into the tables, fmt = the 2 bits in the format info',
    '// 1ブロックあたりの誤り訂正語数（添字0は未使用）':
    '// Error-correction codewords per block (index 0 is unused)',
    '// ブロック数': '// Number of blocks',
    '// N1 は「並んだ数-2」なので定数を持たない': '// N1 is (run length - 2), so it has no constant',
    '// ---- 型番ごとの生モジュール数 ----': '// ---- Raw module count per version ----',
    '// ---- セグメント（モード選択） ----': '// ---- Segments (choosing the mode) ----',
    '// ---- 本体 ----': '// ---- The encoder itself ----',
    '// 収まる最小の型番を探す': '// Find the smallest version it fits in',
    '// ビット列を組み立てる': '// Build the bit stream',
    '// 終端': '// Terminator',
    '// バイト境界まで': '// Up to the byte boundary',
    '// タイミングパターン': '// Timing pattern',
    '// 位置検出パターン（3隅）': '// Finder patterns (three corners)',
    '// 位置合わせパターン': '// Alignment patterns',
    '// 形式情報・型番情報の場所を「機能パターンだが白」として予約しておく。':
    '// Reserve where the format and version info go, as function pattern but white.',
    '// 規格 7.8.3 に従い、マスクの評価はこの情報を入れる前の状態で行う（入れるのは最後）。':
    '// Per 7.8.3, masks are scored before that information is written (it goes in last).',
    '// 常に黒のモジュール。場所だけ押さえて、色は最後に入れる':
    '// The always-dark module. Reserve the spot now, colour it last',
    '// データ語をジグザグに置く': '// Lay the data codewords in a zig-zag',
    '// 8通りのマスクを評価（形式情報・型番情報はまだ入っていない状態で評価する）':
    '// Score all 8 masks (scored while the format and version info are still absent)',
    '// 戻す（XORなので同じ操作で元に戻る）': '// Undo it (XOR, so the same operation reverses it)',
    '// ここで初めて形式情報と型番情報を書き込む':
    '// Only now are the format info and the version info written',
    '// 常に黒のモジュール': '// The always-dark module',
    '// 形式情報15ビットが入る場所（2か所ぶん、ビット0から順）':
    '// Where the 15 format bits go (two places, starting from bit 0)',
    '// 型番情報18ビット×2か所': '// The 18 version bits, in two places',
    '// ---- 評価点（減点方式・規格 7.8.3.1 の4規則） ----':
    '// ---- Scoring (penalties; the four rules of 7.8.3.1) ----',
    '//  N1: 同じ色が5マス以上並ぶ        → (並んだ数 - 2) 点':
    '//  N1: a run of 5 or more same-colour modules -> (run length - 2) points',
    '//  N2: 同じ色の 2×2 のかたまり      → 3点':
    '//  N2: a 2x2 block of one colour              -> 3 points',
    '//  N3: 1:1:3:1:1 の並び（位置検出パターンの見間違い）が、片側4マス以上の白を伴う → 40点':
    '//  N3: a 1:1:3:1:1 run (mistakable for a finder) next to 4+ light modules -> 40 points',
    '//  N4: 黒の割合が50%からずれるほど  → 5%ごとに10点':
    '//  N4: the further the dark share is from 50% -> 10 points per 5%',
    '// N3 で探す並び: 黒 白 黒黒黒 白 黒':
    '// The run N3 looks for: dark light dark dark dark light dark',

    '/* ============================================================\n'
    '   画面まわり\n'
    '   ============================================================ */':
    '/* ============================================================\n'
    '   Screen plumbing\n'
    '   ============================================================ */',

    '// Wi-Fi / SMS などの特殊文字のエスケープ（\\ ; , : " は \\ で逃がす）':
    '// Escaping for Wi-Fi, SMS and friends (\\ ; , : " are escaped with \\)',
    '// 前景と背景のコントラストを見て、読み取りにくい配色は注意する':
    '// Check foreground against background and warn about hard-to-scan colour pairs',
    '// canvas に描く': '// Draw it on the canvas',
    '// 内訳': '// The breakdown',
    '/* ---- 保存 ---- */': '/* ---- Saving ---- */',
    '/* ---- イベント ---- */': '/* ---- Events ---- */',
    '// 検証用の入口（テストからのみ使う。通常の操作では触れない）':
    '// An entry point for the tests (used by them only; never touched in normal use)',
}

# ── 文字列の中身だけの差し替え(TR辞書) ────────────────────────────────────
TR = {
    # --- 誤り訂正レベルの復元率(ECL 表の recover) ---
    "約7%": "about 7%",
    "約15%": "about 15%",
    "約25%": "about 25%",
    "約30%": "about 30%",

    # --- モードの名札 ---
    "数字": "Numeric",
    "英数": "Alphanumeric",
    "バイト": "Byte",
    "バイト（UTF-8）": "Byte (UTF-8)",

    # --- 容量が足りないときの例外 ---
    # 「前置き + 数 + 後置き」で組む。英語も数字がすぐ後ろに来る語順にしないと
    # 「文字列を空にすると日英一致」の検査が通らない。
    "長すぎます。この誤り訂正レベルでは ": "Too long. At this error correction level it holds ",
    " 語まで入りますが、": " codewords at most, but this content needs ",
    " 語ぶんあります。": " codewords. ",
    "文字を減らすか、誤り訂正レベルを下げてください。":
        "Shorten the content, or lower the error correction level.",

    # --- 前景色と背景色のコントラストの注意 ---
    '<strong style="color:var(--err)">この配色はコントラスト比 ':
        '<strong style="color:var(--err)">These two colours have a contrast ratio of only ',
    ':1 しかありません。読み取れない可能性が高いです（白黒なら21:1）。</strong>':
        ':1. It will very likely fail to scan (black on white is 21:1).</strong>',
    "この配色のコントラスト比は ": "These two colours have a contrast ratio of ",
    ":1 です。印刷して使うなら、もう少し差があると安全です。":
        ":1. If you are going to print it, a little more difference is safer.",
    ":1 です。": ":1.",

    # --- エラー欄 ---
    "<strong>まだ中身が空です。</strong>上のフォームに入れてください。":
        "<strong>Nothing to encode yet.</strong> Fill in the form above.",
    "<strong>作れませんでした。</strong>": "<strong>Could not build the code.</strong> ",

    # --- 「中で何が起きたか」の表 ---
    "中身の長さ": "Content length",
    " 文字": " characters",
    "（UTF-8で ": " (UTF-8: ",
    " バイト）": " bytes)",

    "選ばれたモード": "Mode chosen",
    "モード": " mode",

    "型番（バージョン）": "Version",
    " マス": " modules",

    "誤り訂正レベル": "Error correction level",
    "</strong>（": "</strong> (recovers up to ",
    "の欠損まで復元）": " loss)",
    '<br><span style="color:var(--ok)">指定は ':
        '<br><span style="color:var(--ok)">You asked for ',
    " でしたが、大きさが変わらないので上げました</span>":
        ", but the size does not change, so it was raised</span>",

    "データ語 / 訂正語": "Data / correction codewords",
    " 語 / ": " / ",
    " 語": " codewords",

    "ブロック分割": "Block split",
    " ブロック（1ブロックあたり訂正語 ": " blocks (each with ",
    " 語）": " correction codewords)",

    "容量の使用率": "Capacity used",
    "%</strong>（": "%</strong> (",
    " ビット）": " bits)",

    "マスクパターン": "Mask pattern",
    "</strong> 番（8通り中いちばん評価点が低かったもの）":
        "</strong> &mdash; the lowest penalty score of the eight candidates",
    '<br><span style="color:var(--sub)">内訳: 5マス以上の連続 ':
        '<br><span style="color:var(--sub)">Breakdown: runs of 5 or more ',
    " / 2×2のかたまり ": " / 2&times;2 blocks ",
    " / 位置検出パターンに似た並び ": " / finder-like sequences ",
    " / 黒の偏り ": " / dark-light imbalance ",

    "画像の大きさ": "Image size",
    " px（1マス ": " px (module ",
    "px・余白 ": "px, quiet zone ",
    "マス）": " modules)",

    # --- 符号化した文字列とトースト ---
    "符号化した文字列: ": "Encoded string: ",
    "コピーしました": "Copied",
    "コピーできませんでした": "Could not copy",
}





def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "qr" / "index.html"
    en_path = docs / "en" / "qr.html"
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
    # ★2026-09-03 夜: CSS のコメントも訳す(<script> の外なので、それまで誰も見ていなかった)
    en, css_missing = translate_css_comments(en)
    if css_missing:
        sys.exit("訳されていない CSS のコメントが %d 件あります:\n  %s"
                 % (len(css_missing), "\n  ".join(x[:100] for x in css_missing[:8])))

    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("訳した文字列: %d 件" % len(TR))
    print("画面に出るところの日本語: 0箇所")
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
