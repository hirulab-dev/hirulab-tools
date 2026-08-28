#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「パスワード生成・強度診断」の英語版を、日本語版から作る(2026-08-24)。

`make_en_railroad.py` 以降と同じ方式。**日本語版が唯一の原本**で、英語版は毎回ここから作り直す。

1. HTML(head・本文・詳細・footer)を英語の版に差し替える
2. スクリプトの中の**引用符で囲まれた文字列だけ**を英語に差し替える(TR辞書)
3. できた英語版について、**「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**
   ことを確かめる。通れば、拒否サンプリング・χ²計算・落とし穴の検出ロジックは1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

使い方: python lab/scripts/make_en_password.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank

SITE = "https://hirulab-dev.github.io/hirulab-tools"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>パスワード生成・強度診断 — 剰余法の偏りを自分の目で見る道具</title>',
     '<title>Password Generator & Strength Check — see the modulo bias with your own eyes</title>'),

    ('<meta name="description" content="安全な乱数でパスワードを作り、強さと落とし穴を見せる道具です。差別化点は「剰余法(v % n)がなぜ偏るか」を自分の目で確かめられること — 拒否サンプリングと素朴な剰余法を同じ回数だけ実際に引いて、ヒストグラムとχ²検定をその場に出します。生成だけでなく、手持ちのパスワードの診断(ありがちな並び・使い回されている語・年号の混入など約20種類の名指し)もできます。ブラウザ内で完結し、入力はどこにも送信されません。">',
     '<meta name="description" content="Generate passwords with cryptographically secure randomness, and see the strength and traps behind them. What sets this apart: you can see for yourself why naive modulo (v % n) is biased. It draws from rejection sampling and naive modulo the same number of times and shows the histogram and chi-square test right there. Beyond generating, it can also diagnose a password you already use (about 20 named traps: predictable patterns, reused words, embedded years). Runs entirely in the browser; nothing you type is ever sent anywhere.">'),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/password/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/password/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/password.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/password.html">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/password.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/password/">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="パスワード生成・強度診断 — 剰余法の偏りを自分の目で見る道具">',
     '<meta property="og:title" content="Password Generator & Strength Check — see the modulo bias with your own eyes">'),

    ('<meta property="og:description" content="拒否サンプリングと素朴な剰余法を同じ回数だけ実際に引いて、ヒストグラムとχ²検定で偏りを目で見せます。生成に加えて手持ちのパスワードの診断もでき、約20種類の落とし穴を名指しします。ブラウザ内で完結し、通信は一切行いません。">',
     '<meta property="og:description" content="Draws from rejection sampling and naive modulo the same number of times and shows the bias with a histogram and a chi-square test. It can also diagnose a password you already use, and names about 20 traps. Runs entirely in the browser; it never sends anything anywhere.">'),

    ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/password/">',
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/password.html">'),

    ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-password.png">',
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-password-en.png">'),

    ('<meta name="twitter:title" content="パスワード生成・強度診断 — 剰余法の偏りを自分の目で見る道具">',
     '<meta name="twitter:title" content="Password Generator & Strength Check — see the modulo bias with your own eyes">'),

    ('<meta name="twitter:description" content="拒否サンプリングと素朴な剰余法を実際に引いて、偏りをヒストグラムとχ²検定で見せます。手持ちのパスワードの診断もできます。通信は一切行いません。">',
     '<meta name="twitter:description" content="Draws from rejection sampling and naive modulo for real and shows the bias with a histogram and a chi-square test. It can also diagnose a password you already use. It never sends anything anywhere.">'),

    ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-password.png">',
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-password-en.png">'),

    ('''  "name": "パスワード生成・強度診断",
  "url": "https://hirulab-dev.github.io/hirulab-tools/password/",
  "description": "安全な乱数(crypto.getRandomValues)を拒否サンプリングで使ってパスワードを作り、強さと落とし穴を見せる道具です。素朴な剰余法(v % n)がなぜ偏るかを、実際に同じ回数だけ引いた結果のヒストグラムとχ²検定でその場に出します。手持ちのパスワードの診断(ありがちな並び・使い回されている語・年号の混入など約20種類の名指し)もできます。ブラウザ内で完結し、入力はどこにも送信されません。",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-password.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "Password Generator & Strength Check",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/password.html",
  "description": "Generates passwords using cryptographically secure randomness (crypto.getRandomValues) drawn through rejection sampling, and shows their strength and traps. It shows, with a real histogram and a chi-square test drawn the same number of times, why naive modulo (v % n) is biased. It can also diagnose a password you already use (about 20 named traps: predictable patterns, reused words, embedded years). Runs entirely in the browser; nothing you type is ever sent anywhere.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-password-en.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude's Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>\n  <h1>パスワード生成・強度診断</h1>',
     '  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab — tools</a>\n  <h1>Password Generator & Strength Check</h1>'),

    ('''  <p class="lead">安全な乱数でパスワードを作る道具です。<strong>差別化点は、なぜ安全なのかを主張するだけでなく
    自分の目で確かめられること。</strong> よくある実装は文字を選ぶのに <code>乱数 % 文字数</code> という
    素朴な剰余法を使いますが、これは文字数が256を割り切らない限り<strong>必ず偏ります</strong>。
    この道具は<strong>拒否サンプリング(rejection sampling)</strong>で偏りを避け、
    その違いを<strong>実際に同じ回数だけ引いて、ヒストグラムとχ²検定で見せます</strong>
    (下の「剰余法はなぜ偏るか」)。生成だけでなく、<strong>手持ちのパスワードの診断</strong>もできます。</p>''',
     '''  <p class="lead">A tool that builds passwords from cryptographically secure randomness.
    <strong>What sets it apart: instead of just claiming it is safe, it lets you check for
    yourself.</strong> A common implementation picks each character with
    <code>random % alphabet size</code>, plain naive modulo, and unless the alphabet size
    divides 256 evenly this <strong>is always biased</strong>. This tool avoids the bias with
    <strong>rejection sampling</strong>, and <strong>shows the difference by actually drawing
    the same number of times from both and plotting a histogram with a chi-square test</strong>
    (see "Why does naive modulo end up biased?" below). Beyond generating, it can also
    <strong>diagnose a password you already use</strong>.</p>'''),

    ('''  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    生成も診断もすべてブラウザの中で完結します。読み込んだあとは機内モードでも動きます。
    <strong>入力したパスワードがどこかに送られることはありません。</strong>
    それでも、生成したパスワードの保存先はこのページではなくパスワードマネージャーにしてください。
  </div>''',
     '''  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    Generating and diagnosing both happen entirely in your browser. Once it has loaded, it
    keeps working in airplane mode.
    <strong>Nothing you type is ever sent anywhere.</strong>
    Even so, save the password you generate in a password manager, not on this page.
  </div>'''),

    ('    <h2>1. 生成する</h2>', '    <h2>1. Generate</h2>'),
    ('      <label for="len">長さ</label>', '      <label for="len">Length</label>'),
    ('      <span>文字</span>', '      <span>characters</span>'),
    ('      <label><input type="checkbox" id="oLower" checked> 小文字 (a-z)</label>\n'
     '      <label><input type="checkbox" id="oUpper" checked> 大文字 (A-Z)</label>\n'
     '      <label><input type="checkbox" id="oDigit" checked> 数字 (0-9)</label>\n'
     '      <label><input type="checkbox" id="oSymbol" checked> 記号</label>\n'
     '      <label><input type="checkbox" id="oNoAmbig"> 紛らわしい文字を除く(<span class="mono">0 O 1 l I o |</span>)</label>\n'
     '      <label><input type="checkbox" id="oEachClass" checked> 選んだ種類を必ず1文字以上含める</label>',
     '      <label><input type="checkbox" id="oLower" checked> lowercase (a-z)</label>\n'
     '      <label><input type="checkbox" id="oUpper" checked> uppercase (A-Z)</label>\n'
     '      <label><input type="checkbox" id="oDigit" checked> digits (0-9)</label>\n'
     '      <label><input type="checkbox" id="oSymbol" checked> symbols</label>\n'
     '      <label><input type="checkbox" id="oNoAmbig"> exclude look-alike characters (<span class="mono">0 O 1 l I o |</span>)</label>\n'
     '      <label><input type="checkbox" id="oEachClass" checked> always include at least one of each chosen type</label>'),
    ('      <label for="outBox" class="hide">生成されたパスワード</label>',
     '      <label for="outBox" class="hide">Generated password</label>'),
    ('      <button class="act" id="btnGen" type="button">生成し直す</button>\n'
     '      <button class="sub" id="btnCopy" type="button">コピー</button>',
     '      <button class="act" id="btnGen" type="button">Regenerate</button>\n'
     '      <button class="sub" id="btnCopy" type="button">Copy</button>'),

    ('    <h2>強さの目安</h2>\n    <div class="bandlabel">エントロピー <b id="bitsVal"></b> — <b id="bandVal"></b></div>',
     '    <h2>Strength estimate</h2>\n    <div class="bandlabel">Entropy <b id="bitsVal"></b> — <b id="bandVal"></b></div>'),
    ('      <table><thead><tr><th>総当たりされたら(平均)</th><th>目安の速さ</th><th>かかる時間</th></tr></thead>',
     '      <table><thead><tr><th>Brute force (average)</th><th>rate assumed</th><th>time it would take</th></tr></thead>'),
    ('''    <p class="statline">これは<strong>力任せ攻撃だけ</strong>の目安です。辞書攻撃や下の「気をつけるところ」に
      挙がるような並びの弱さには、エントロピーの数字だけでは効きません。</p>''',
     '''    <p class="statline">This is a <strong>brute-force-only</strong> estimate. Dictionary attacks and the
      kinds of pattern weaknesses listed under "Traps" below are not covered by the entropy
      number alone.</p>'''),

    ('    <h2>気をつけるところ(生成したパスワードについて)</h2>',
     '    <h2>Traps (about the generated password)</h2>'),
    ('    <p class="none" id="genNotesNone">いまのところ指摘はありません。</p>',
     '    <p class="none" id="genNotesNone">Nothing to flag right now.</p>'),

    ('    <h2>2. 手持ちのパスワードを診断する</h2>',
     '    <h2>2. Diagnose a password you already use</h2>'),
    ('''    <p class="statline">生成したものでなくても、既に使っているパスワードの弱さをその場で診断できます。
      <strong>通信は行わないので</strong>、実在のパスワードを試しても外には出ません。
      それでも、使い回している最重要のパスワード(メインメール等)は避けることをおすすめします。</p>''',
     '''    <p class="statline">Not only what this page generates — you can diagnose a password you already
      use, right here. <strong>It never sends anything anywhere</strong>, so trying a real
      password does not leak it. Even so, it is best to avoid your single most important,
      reused password (your main email account, say).</p>'''),
    ('      <label for="pwIn" class="hide">診断するパスワード</label>',
     '      <label for="pwIn" class="hide">Password to diagnose</label>'),
    ('        placeholder="ここに貼るか入力してください">',
     '        placeholder="Paste or type it here">'),
    ('      <button class="sub" id="btnShow" type="button">表示</button>',
     '      <button class="sub" id="btnShow" type="button">Show</button>'),
    ('    <p class="none" id="ownNotesNone">まだ何も入力されていません。</p>',
     '    <p class="none" id="ownNotesNone">Nothing entered yet.</p>'),

    ('    <h2>剰余法はなぜ偏るか — 実際に引いて確かめる</h2>',
     '    <h2>Why does naive modulo end up biased? — see it by actually drawing</h2>'),
    ('''    <p class="statline">乱数バイト(0〜255)を<code>v % n</code>で文字数 n に落とすと、
      256 が n で割り切れない限り、余りの分だけ一部の文字が多く選ばれます。
      <strong>拒否サンプリング</strong>は、割り切れる範囲(<code>Math.floor(256/n)*n</code>未満)を
      超えたバイトを引き直すことで、これを避けます。理屈だけでなく、実際に同じ回数だけ両方を
      引いてヒストグラムとχ²検定を出します。</p>''',
     '''    <p class="statline">Fold a random byte (0-255) down to an alphabet of n characters with
      <code>v % n</code>, and unless 256 divides evenly by n, the leftover skews some characters
      toward being picked more often. <strong>Rejection sampling</strong> avoids this by
      re-drawing any byte at or past the divisible range
      (<code>Math.floor(256/n)*n</code>). Beyond the theory, this draws from both methods the
      same number of times for real and plots a histogram with a chi-square test.</p>'''),
    ('      <label for="demoN">文字数 n</label>', '      <label for="demoN">Alphabet size n</label>'),
    ('''        <option value="62">62(英大小文字+数字。既定の文字種相当)</option>
        <option value="26">26(英小文字のみ)</option>
        <option value="95">95(印字可能ASCII全部)</option>
        <option value="10">10(数字のみ)</option>
        <option value="16">16(0-9a-f。256を割り切る=理論上は偏らない例)</option>
        <option value="64">64(base64相当。256を割り切る)</option>''',
     '''        <option value="62">62 (upper+lower+digits, roughly the default alphabet)</option>
        <option value="26">26 (lowercase only)</option>
        <option value="95">95 (all printable ASCII)</option>
        <option value="10">10 (digits only)</option>
        <option value="16">16 (0-9a-f; divides 256 evenly — the theoretical no-bias case)</option>
        <option value="64">64 (base64-sized; divides 256 evenly)</option>'''),
    ('      <label for="demoK">回数</label>', '      <label for="demoK">Draws</label>'),
    ('      <button class="act" id="btnDemo" type="button">実験する</button>',
     '      <button class="act" id="btnDemo" type="button">Run the experiment</button>'),

    ('    <h2>自己検査</h2>', '    <h2>Self-check</h2>'),

    ('''  <details>
    <summary>この道具は何をしているか</summary>
    <ul>
      <li><b>乱数は <code>crypto.getRandomValues</code> だけを使います。</b>
        <code>Math.random()</code> は仕様上どの実装を使うか決まっておらず、多くのブラウザでは
        暗号用途に設計されていない生成器(V8 は xorshift128+ 系)です。少数の出力から内部状態を
        復元できる場合があり、<b>パスワード生成には使ってはいけません</b>。</li>
      <li><b>文字を選ぶのに、乱数バイトの剰余(<code>v % n</code>)をそのまま使いません。</b>
        256 が文字数 n で割り切れないと、余りの分だけ一部の文字が多く選ばれます
        (上の実験で実際に確かめられます)。<b>拒否サンプリング</b>で、割り切れる範囲を
        超えたバイトは引き直すことで避けています。</li>
      <li><b>「選んだ種類を必ず1文字以上含める」は正確には均一分布ではありません。</b>
        文字種の充足を後から強制する分、理論上のエントロピーはわずかに下がります
        (下の強さの目安は、この制約を踏まえて計算しています)。均一性を最優先するなら外してください。</li>
      <li><b>診断のよくある単語リストは、公開されている「よく使われるパスワード」調査
        (英国NCSCなど毎年公表される集計)を参考にした小さな一覧です。</b>
        網羅はしていません。載っていないから安全、という意味ではありません。</li>
      <li><b>キーボード配列の判定はUSレイアウトのQWERTY基準です。</b>
        JISかな配列など他の配列での「並び」は拾えません。</li>
      <li><b>χ²検定のp値は近似式(Wilson–Hilferty)です。</b>
        自由度が大きいところでは実用上十分な精度ですが、正確な値ではありません。</li>
    </ul>
  </details>''',
     '''  <details>
    <summary>What this tool actually does</summary>
    <ul>
      <li><b>Randomness comes only from <code>crypto.getRandomValues</code>.</b>
        <code>Math.random()</code> leaves the implementation up to the engine, and in most
        browsers it is a generator not designed for cryptographic use (V8 uses an
        xorshift128+ family). Its internal state can sometimes be recovered from a handful of
        outputs, so <b>it must never be used to generate passwords</b>.</li>
      <li><b>Characters are not chosen with a plain modulo of the random byte
        (<code>v % n</code>).</b> Unless 256 divides evenly by the alphabet size n, the
        leftover skews some characters to be picked more often (you can confirm this yourself
        with the experiment above). <b>Rejection sampling</b> avoids it by re-drawing any byte
        past the divisible range.</li>
      <li><b>"Always include at least one of each chosen type" is not, strictly speaking, a
        uniform distribution.</b> Forcing coverage after the fact costs a small amount of
        theoretical entropy (the strength estimate below accounts for this constraint). Turn it
        off if uniformity matters most to you.</li>
      <li><b>The list of common passwords used for diagnosis is a small one, drawn from published
        "most common passwords" surveys (such as the UK NCSC's annual report).</b> It is not
        exhaustive. Not being on the list does not mean a password is safe.</li>
      <li><b>Keyboard-walk detection is based on the US QWERTY layout.</b>
        Adjacency on other layouts, such as JIS kana, is not picked up.</li>
      <li><b>The p-value for the chi-square test is an approximation (Wilson-Hilferty).</b>
        It is accurate enough in practice at larger degrees of freedom, but it is not exact.</li>
    </ul>
  </details>'''),

    ('''    <p class="hl-links">
      <a href="../">道具箱のトップ</a> ・
      <a href="https://note.com/hirulab">実験ログ（note）</a> ・
      <a href="https://x.com/hirulab_ai">X</a> ・
      <a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>
    </p>''',
     '''    <p class="hl-links">
      <a href="./">All tools (English)</a> &middot;
      <a href="../">Japanese site</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>'''),

    ('''  <footer>
    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    乱数は <code>crypto.getRandomValues</code>（Web Crypto API）のみを使用し、
    拒否サンプリングで剰余法の偏りを避けています。強さの目安は力任せ攻撃の理論値であり、
    実運用の絶対的な安全を保証するものではありません。
  </footer>''',
     '''  <footer>
    Built by Claude&#39;s Daytime Lab (Claude, an AI). Free to use, no sign-up.
    Randomness comes only from <code>crypto.getRandomValues</code> (the Web Crypto API),
    drawn through rejection sampling to avoid the bias of naive modulo. The strength estimate
    is a theoretical brute-force figure, not a guarantee of absolute real-world safety.
  </footer>'''),
]

# ── ナビ(既存の他ページと同じ構造で英語版を書く) ──────────────────────────
EN_NAV = '''  <nav class="hl-nav">
    <h2>Other tools</h2>
    <ul id="navList"></ul>
    <p class="hl-links">
      <a href="./">All tools (English)</a> &middot;
      <a href="https://note.com/hirulab">Experiment log (JP)</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''

NAV_LINKS_JA = '''var NAV_LINKS = [
  ["../regex/", "正規表現テスタ"], ["../regex-why/", "正規表現がなぜマッチしないか診断"],
  ["../railroad/", "正規表現を鉄道図にする"], ["../replace/", "正規表現の置換プレビュー"],
  ["../url/", "URLの分解・組み立て"], ["../headers/", "HTTPヘッダの読み下し"],
  ["../jwt/", "JWTの読み下し"], ["../char-counter/", "文字数カウンタ"],
  ["../contrast/", "コントラスト比チェッカー"], ["../date/", "日付計算機"],
  ["../image/", "画像リサイズ・圧縮"], ["../take-home/", "手取り計算機"],
  ["../json/", "JSON整形・検証"], ["../diff/", "テキスト差分（diff）"],
  ["../unit/", "単位換算"], ["../page-contrast/", "ページまるごとコントラスト診断"],
  ["../qr/", "QRコード作成"], ["../palette/", "カラーパレット生成"],
  ["../frima-profit/", "フリマ手取り計算機"], ["../cron/", "cron式の読み下し"],
  ["../tz/", "タイムゾーン変換"], ["../csv/", "CSVプレビュー・診断"],
  ["../base64/", "Base64・データURLの分解"],
  ["../en/password.html", "English version"]
];'''

NAV_LINKS_EN = '''var NAV_LINKS = [
  ["./regex-tester.html", "Regex Tester"], ["./regex-why.html", "Why does my regex not match?"],
  ["./railroad.html", "Regex Railroad Diagrams"], ["./replace.html", "Regex Replacement Preview"],
  ["./url.html", "URL Parser & Builder"], ["./headers.html", "HTTP Header Explainer"],
  ["./jwt.html", "JWT Explainer"], ["./char-counter.html", "Character Counter"],
  ["./timezone.html", "Time Zone Converter"], ["./csv.html", "CSV Preview & Diagnostics"],
  ["./palette.html", "Color Palette Generator"],
  ["./base64.html", "Base64 &amp; Data URL Explainer"],
  ["./qr.html", "QR Code Generator"],
  ["./cron.html", "Cron Expression Explainer"],
  ["./contrast.html", "Contrast Ratio Checker"],
  ["./image.html", "Image Resizer &amp; Compressor"],
  ["../password/", "Japanese version"]
];'''

# ── 文字列だけの差し替え(TR辞書) ──────────────────────────────────────────
TR = {
    "小文字": "lowercase", "大文字": "uppercase", "数字": "digits", "記号": "symbols",
    "n は 1〜256": "n must be 1-256",

    "きわめて弱い": "extremely weak", "弱い": "weak", "ふつう": "fair",
    "強い": "strong", "非常に強い": "very strong",
    "計算不能": "cannot be computed",
    "年": "y", " 年": " y",
    "(宇宙の年齢の約 ": "(about ", " 倍)": "× the age of the universe)",
    "(宇宙の年齢の約 10^": "(about 10^",
    "1秒未満": "under 1 second",
    "秒": "s", "分": "min", "時間": "h", "日": "d",

    "オンライン(スロットル済み。100回/時 目安)": "Online (throttled, roughly 100/hour)",
    "オフライン・遅いハッシュ(bcrypt等 目安)": "Offline, slow hash (e.g. bcrypt)",
    "オフライン・速いハッシュ/GPU群(目安)": "Offline, fast hash / GPU cluster",

    "「": "“",
    "同じ文字が3回以上連続しています": "The same character repeats 3 or more times in a row",
    "」。当てずっぽうで最初に試される並びの一つです。":
        "”. This kind of run is among the first things a guesser tries.",
    "連続した並びが含まれています": "It contains a run of sequential characters",
    "」。文字コードが1つずつ増減する並びは辞書攻撃で真っ先に試されます。":
        "”. Runs where the character code steps by one are tried first by dictionary attacks.",
    "キーボードの並び通りの部分があります": "Part of it follows the keyboard layout",
    "」。USレイアウトのQWERTY基準での判定です。見た目はランダムでも配列上は一直線です。":
        "”. Judged against a US QWERTY layout. It can look random while sitting in a straight line on the keyboard.",
    "同じ並びの繰り返しでできています": "It is built from the same short sequence repeated",
    "」を繰り返すと元の文字列になります。見かけの長さほど選択肢は増えていません。":
        "” repeated makes the whole string. The apparent length overstates how many choices it actually represents.",
    "よく使われるパスワードそのものです": "This is a commonly used password, as-is",
    "公開されている「よく使われるパスワード」調査に載っている形と一致します。真っ先に試されます。":
        "It matches an entry in a published “most common passwords” survey. It gets tried first.",
    "よくあるパスワードの文字置き換え(1→i、0→oなど)にすぎません":
        "It is only a character substitution of a common password (1→i, 0→o, etc.)",
    "置き換えを戻すと「": "Undo the substitution and it becomes “",
    "」になり、これも既知のよく使われる形です。": "”, which is also a known common form.",
    "「単語+数字+記号1つ」という定型の形です": "It follows the stock “word + digits + one symbol” shape",
    "多くの企業ポリシーが要求する形そのもので、辞書攻撃の候補生成が最初に試すパターンです。":
        "It is exactly what many corporate policies require, and it is the first pattern a dictionary attack's candidate generator tries.",
    "西暦らしい4桁が含まれています": "It contains 4 digits that look like a year",
    "誕生年や現在の年を組み込む書き方は推測されやすい定番です。":
        "Working a birth year or the current year into a password is a classic, guessable habit.",
    "1種類の文字だけでできています": "It is built from only one character class",
    "英小文字だけ・数字だけ、のように1種類しか使っていないと、同じ長さでも選択肢の数(=強さ)が大きく落ちます。":
        "Using only lowercase letters, or only digits, drops the number of possibilities (= strength) sharply even at the same length.",
    "使われている文字の種類が少なめです": "Relatively few distinct characters are used",
    "異なり文字数は ": "Distinct characters: ",
    "。同じ文字の使い回しが多いと、見た目の長さより実質の選択肢は少なくなります。":
        ". Heavy reuse of the same characters leaves fewer real choices than the apparent length suggests.",
    "回文になっています": "It is a palindrome",
    "前から読んでも後ろから読んでも同じ並びです。構造自体が推測の手がかりになります。":
        "It reads the same forwards and backwards. The structure itself is a clue for guessing.",
    "ちょうど8文字です": "It is exactly 8 characters",
    "多くのサイトの最低文字数がここにあるため、「要件を満たすためだけの長さ」になっていないか確認してください。長いほど、掛け算で選択肢が増えます。":
        "This is where many sites set their minimum, so check that it is not just long enough to pass the requirement and no more. Every extra character multiplies the number of possibilities.",
    "紛らわしい文字が含まれています": "It contains characters that are easy to confuse",
    "0/O、1/l/I、o/O のように書体によっては区別しにくい文字があります(強さではなく手入力のしやすさの話です)。":
        "Characters like 0/O, 1/l/I and o/O can be hard to tell apart in some fonts (this is about typing it by hand, not strength).",

    "拒否サンプリングの閾値(floor(256/n)*n)がn=1〜256すべてで256以下・nの倍数になっている":
        "The rejection-sampling threshold (floor(256/n)×n) stays ≤256 and a multiple of n for every n from 1 to 256",
    "生成した200文字が、指定した文字種の外に出ていない":
        "None of 200 generated characters fall outside the chosen character classes",
    "長さ ": "length ",
    "「紛らわしい文字を除く」を有効にすると、対象の文字が文字種プールから消えている":
        "Turning on “exclude look-alike characters” actually removes them from the character pool",
    "エントロピー計算 20文字×62文字種 が手計算(log2(62)×20)と一致":
        "The entropy for 20 characters × 62-character alphabet matches the hand calculation (log2(62)×20)",
    "このブラウザで crypto.getRandomValues が使える": "crypto.getRandomValues is available in this browser",
    "「選んだ種類を必ず1文字以上含める」を有効にすると、50回試して全部で4種類そろっている":
        "With “always include at least one of each type” on, all 4 classes appear in every one of 50 trials",

    "少なくとも1つ文字種を選んでください": "Choose at least one character type",
    "文字種プール: <b>": "Character pool: <b>",
    "</b> 種類": "</b> characters",
    "(各種類を必ず1文字以上含める設定つき)": " (with “always include each type” on)",
    " 回/秒": " draws/sec",
    " 文字 ／ 使われている文字種から見た理論上のエントロピー <b>":
        " characters / theoretical entropy from the character classes actually used: <b>",
    ")。<span class=\\\"none\\\">※実際に使われた文字だけで判定した参考値で、上の生成器のように「宣言した文字種プール」とは別の見積もりです。</span>":
        "). <span class=\\\"none\\\">This estimate is based only on the character classes actually present, a different measure from the generator's “declared pool” above.</span>",

    "この道具の内部一貫性を確認しました: ": "Internal consistency of this tool was checked: ",
    " 一致": " match",

    "素朴な剰余法(v % ": "Naive modulo (v % ",
    "拒否サンプリング": "Rejection sampling",
    "偏りがある(強い証拠。p < 0.01)": "biased (strong evidence, p < 0.01)",
    "偏りの疑いがある(p < 0.05)": "possibly biased (p < 0.05)",
    "一様分布として自然な範囲(偏りは見られない)": "within the range expected for a uniform distribution (no bias seen)",
    "剰余法: χ² = ": "Naive modulo: χ² = ",
    "(自由度 ": " (df ",
    "拒否サンプリング: χ² = ": "Rejection sampling: χ² = ",
    ")、p ≈ ": "), p ≈ ",
    "理論値: n=": "Theory: n=",
    " は256を割り切るので、剰余法でも理論上まったく偏りません":
        " divides 256 evenly, so even naive modulo is theoretically not biased at all",
    "(このNだけは例外です。上の実験でも差が小さいはずです)。":
        " (this N is the exception; the experiment above should show little difference).",
    " は256を割り切らないので、最初の ": " does not divide 256 evenly, so the first ",
    " 文字が確率 ": " characters land with probability ",
    "%、残り ": "%, and the remaining ",
    "% で選ばれる計算になります": "% — by the math",
    "(本来は均等に ": " (the fair share would be ",
    "% ずつのはず)。": "% each).",

    "正規表現テスタ": "Regex Tester",
    "正規表現がなぜマッチしないか診断": "Why doesn&#39;t my regex match?",
    "正規表現を鉄道図にする": "Regex Railroad Diagrams",
    "正規表現の置換プレビュー": "Regex Replacement Preview",
    "URLの分解・組み立て": "URL Parser & Builder",
    "HTTPヘッダの読み下し": "HTTP Header Explainer",
    "JWTの読み下し": "JWT Explainer",
    "文字数カウンタ": "Character Counter",
    "コントラスト比チェッカー": "Contrast Checker",
    "日付計算機": "Date Calculator",
    "画像リサイズ・圧縮": "Image Resize & Compress",
    "手取り計算機": "Take-Home Pay Calculator",
    "JSON整形・検証": "JSON Formatter & Validator",
    "テキスト差分（diff）": "Text Diff",
    "単位換算": "Unit Converter",
    "ページまるごとコントラスト診断": "Whole-Page Contrast Checker",
    "QRコード作成": "QR Code Generator",
    "カラーパレット生成": "Color Palette Generator",
    "フリマ手取り計算機": "Marketplace Payout Calculator",
    "cron式の読み下し": "Cron Expression Explainer",
    "タイムゾーン変換": "Time Zone Converter",
    "CSVプレビュー・診断": "CSV Preview & Diagnostics",

    "コピーしました。クリップボードは他のアプリやクラウド同期の履歴から見えることがあります。使ったら早めに上書きしてください。":
        "Copied. Your clipboard can be visible to other apps and to cloud-synced clipboard history. Overwrite it soon after use.",
    "コピーに失敗しました。選択して手動でコピーしてください。":
        "Copy failed. Select the text and copy it manually.",
    "隠す": "Hide", "表示": "Show",
}


def core_of(html):
    """比較対象のコアだけを取り出す。`NAV_LINKS` は「英語版があるツールだけ」を
    載せるので日英で項目数が違うのが仕様(他ツールが静的HTMLの<nav>を比較対象の外に
    置いているのと同じ理由で、ここも除外する)。"""
    m = re.search(r"<script>(.*)</script>", html, re.S)
    core = m.group(1)
    core = re.sub(r"var NAV_LINKS = \[.*?\];\n", "", core, flags=re.S)
    return core


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "password" / "index.html"
    en_path = docs / "en" / "password.html"
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

    if NAV_LINKS_JA not in en:
        sys.exit("NAV_LINKS(JA)の差し替え元が見つかりません")
    en = en.replace(NAV_LINKS_JA, NAV_LINKS_EN, 1)

    for a, b in sorted(TR.items(), key=lambda kv: -len(kv[0])):
        en = en.replace('"' + a + '"', '"' + b + '"')

    body = re.sub(r"/\*.*?\*/", "", en, flags=re.S)
    body = re.sub(r"(?m)(?<!:)//.*$", "", body)
    left = re.findall("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？]+", body)
    if left:
        sys.exit("日本語が %d 箇所残っています: %s" % (len(left), left[:12]))

    a, b = blank(core_of(ja)), blank(core_of(en))
    if a != b:
        for k, (x, y) in enumerate(zip(a.split("\n"), b.split("\n"))):
            if x != y:
                sys.exit("コードが一致しません(%d行目):\n  ja: %s\n  en: %s" % (k + 1, x, y))
        sys.exit("コードの行数が違います(ja %d / en %d)" % (a.count("\n"), b.count("\n")))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("日本語の残り: 0箇所")
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
