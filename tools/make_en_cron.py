#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「cron式の読み下し」の英語版を、日本語版から作る(2026-08-28)。

`make_en_qr.py` / `make_en_base64.py` と同じ方式。**日本語版が唯一の原本**。

1. HTML(head・本文・details・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. できた英語版について、**「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**
   ことを確かめる。通れば、解析・次回実行時刻の計算・落とし穴の検出は1バイトも違わない
   = `test_cron.py` の 4,996式の突き合わせがそのまま英語版にも効く
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

★この回の下ごしらえ(`outputs/en-cron-plan.md` に書いた宿題)
  cron は「同じリテラルが違う役目で使い回されている」のが多く、そのままでは訳が割れない。
  差し替えは**リテラルの中身の完全一致**でやるので、`日` が Sunday でもあり
  day of month でもあり日付の接尾辞でもある、という状態だと必ずどれかが壊れる。
  → 先に**日本語ページ側で役目ごとに枠を分けた**(表示は1文字も変えていない)。
     DOW_JA / LBL / GAP / MON_LB の4本の表と、文をつなぐ語の W。
  畳み込みの前後で `test_cron.py` が同じ数字(800式・不一致0・意図的な差7/7)を出すことと、
  `diff_cron_text.py` で読み下しの文が4,000式で1文字も変わらないことを確認ずみ。

使い方: python lab/scripts/make_en_cron.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    # CSS のコメント。画面には出ないが、英語版に日本語を残さない方針をここでも通す
    # (`docs/en/index.html` は手書きなので日本語のコメントが残っている。そちらは別件)
    ('''    /* リンク色は白地で 4.5:1 を超える濃さにしている（明るい #c47f16 だと 3.28:1 しか出ない）。
       --on-accent はアクセント色を背景に敷いたときの文字色。 */''',
     '''    /* The link colour is dark enough to clear 4.5:1 on white; the lighter #c47f16
       only reaches 3.28:1. --on-accent is the text colour on top of the accent. */'''),

    ('  /* 色を指定しないとブラウザ既定の青になり、ダークモードで 1.89:1 まで落ちる */',
     '  /* Without a colour this falls back to the browser default blue, which drops to 1.89:1 in dark mode */'),

    ('<title>cron式の読み下し — 日本語の意味・次の実行時刻・落とし穴の検出</title>',
     '<title>Cron Expression Explainer — what it means, when it runs next, what will bite you</title>'),

    ('<meta name="description" content="cron式（* * * * *）を日本語に読み下し、次の実行時刻を20件並べ、1年あたりの実行回数と最短・最長の間隔まで出します。「日と曜日を両方書くとORになる」「*/7 は折り返しで間隔が飛ぶ」といった定番の落とし穴を自動で検出します。ブラウザ内で完結し、データはどこにも送信されません。">',
     '<meta name="description" content="Reads a cron expression (* * * * *) back to you as a sentence, lists the next 20 run times, and works out how many times a year it fires and what the shortest and longest gaps are. It also flags the classic traps automatically — day-of-month and day-of-week being OR, not AND, and */7 skipping at the wrap-around. Everything happens in the browser and nothing is ever sent anywhere.">'),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/cron/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/cron/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/cron.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/cron.html">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/cron.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/cron/">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="cron式の読み下し — 日本語の意味・次の実行時刻・落とし穴の検出">',
     '<meta property="og:title" content="Cron Expression Explainer">'),

    ('<meta property="og:description" content="cron式を日本語に読み下し、次の実行時刻を20件、1年あたりの実行回数と最短・最長の間隔まで出します。「日と曜日はORになる」等の定番の罠を自動検出。ブラウザ内で完結します。">',
     '<meta property="og:description" content="Reads a cron expression back as a sentence, lists the next 20 run times, and gives the runs per year and the shortest and longest gaps. Classic traps such as day-of-month and day-of-week being OR are flagged automatically. Runs entirely in the browser.">'),

    ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/cron/">',
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/cron.html">'),

    ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-cron.png">',
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-cron-en.png">'),

    ('<meta name="twitter:title" content="cron式の読み下し — 日本語の意味・次の実行時刻・落とし穴の検出">',
     '<meta name="twitter:title" content="Cron Expression Explainer">'),

    ('<meta name="twitter:description" content="cron式を日本語に読み下し、次の実行時刻と1年あたりの実行回数・最短最長の間隔まで出します。定番の罠を自動検出。ブラウザ内で完結します。">',
     '<meta name="twitter:description" content="Reads a cron expression back as a sentence, with the next run times, runs per year and the shortest and longest gaps. Classic traps flagged automatically.">'),

    ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-cron.png">',
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-cron-en.png">'),

    ('''  "name": "cron式の読み下し",
  "url": "https://hirulab-dev.github.io/hirulab-tools/cron/",
  "description": "cron式を日本語に読み下し、次の実行時刻を20件並べ、1年あたりの実行回数と最短・最長の間隔を出します。日と曜日の同時指定がORになる件や、範囲の幅で割り切れないステップで間隔が飛ぶ件などを自動で検出します。ブラウザ内で完結します。",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-cron.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "Cron Expression Explainer",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/cron.html",
  "description": "Reads a cron expression back to you as a sentence, lists the next 20 run times, and gives the number of runs per year along with the shortest and longest gaps. It automatically flags traps such as day-of-month and day-of-week being combined with OR, and steps that do not divide the range evenly leaving a jump at the wrap-around. Runs entirely in the browser.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-cron-en.png",
  "author": { "@type": "Organization", "name": "Claude&#39;s Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude&#39;s Daytime Lab &mdash; Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>cron式の読み下し</h1>
  <p class="lead"><code>0 9 * * 1-5</code> のような式を<strong>日本語の文</strong>にして、
    <strong>次の実行時刻</strong>と<strong>1年で何回動くか・間隔は最短何分か</strong>まで出します。
    「日と曜日を両方書くと <strong>かつ</strong> ではなく <strong>または</strong> になる」といった
    定番の落とし穴も、当てはまっていたら自動で指摘します。</p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    解析も時刻の計算もすべてブラウザの中でやっています。読み込んだあとは機内モードでも動きます。
    入力した式がどこかに送られることはありません。
  </div>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>Cron Expression Explainer</h1>
  <p class="lead">Turns an expression like <code>0 9 * * 1-5</code> into <strong>a sentence</strong>,
    and gives you <strong>the next run times</strong> plus
    <strong>how many times a year it fires and how short the gaps get</strong>.
    The classic traps &mdash; such as writing both day-of-month and day-of-week meaning
    <strong>OR</strong>, not <strong>AND</strong> &mdash; are pointed out automatically
    whenever they apply.</p>

  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    Parsing and every time calculation happen inside the browser. Once the page has loaded
    it still works in aeroplane mode.
    The expression you type is never sent anywhere.
  </div>'''),

    ('    <label for="expr" class="hide">cron式</label>',
     '    <label for="expr" class="hide">Cron expression</label>'),

    ('           value="0 9 * * 1-5" placeholder="例: 0 9 * * 1-5">',
     '           value="0 9 * * 1-5" placeholder="e.g. 0 9 * * 1-5">'),

    ('      <h2>気をつけるところ</h2>', '      <h2>Things to watch out for</h2>'),

    ('''      <h2>フィールドの中身</h2>
      <div class="tablewrap">
        <table>
          <thead><tr>
            <th>書いた値</th><th>意味するもの</th><th>当てはまる値</th><th class="c-cnt">個数</th>
          </tr></thead>''',
     '''      <h2>What each field holds</h2>
      <div class="tablewrap">
        <table>
          <thead><tr>
            <th>As written</th><th>Field</th><th>Values it matches</th><th class="c-cnt">Count</th>
          </tr></thead>'''),

    ('''      <h2>次の実行時刻</h2>
      <div class="tzrow">
        <label for="tz">タイムゾーン</label>''',
     '''      <h2>Next run times</h2>
      <div class="tzrow">
        <label for="tz">Time zone</label>'''),

    ('      <h2>どれくらいの頻度か</h2>', '      <h2>How often it fires</h2>'),

    ('''  <details>
    <summary>書ける記法と、このページの解釈のしかた</summary>
    <ul>
      <li><b>フィールドの数</b>: 5個（分 時 日 月 曜日）が標準です。6個書いた場合は
        <b>先頭を秒</b>として解釈します（Spring・Quartz・一部のジョブ実行基盤の書き方）。
        7個目（年）には対応していません。</li>
      <li><b>使える記号</b>: <code>*</code>（全部） <code>,</code>（並べる）
        <code>-</code>（範囲） <code>/</code>（間隔）。
        <code>*/15</code>、<code>1-5</code>、<code>0,30</code>、<code>9-17/2</code>、
        <code>5/10</code>（5から最後まで10おき）が書けます。</li>
      <li><b>名前</b>: 月は <code>JAN</code>〜<code>DEC</code>、曜日は <code>SUN</code>〜<code>SAT</code>。
        大文字小文字は問いません。<code>MON-FRI</code> のような範囲も書けます。</li>
      <li><b>曜日の 0 と 7 はどちらも日曜</b>です。<code>0-7</code> は全曜日と同じ意味になります。</li>
      <li><b>@から始まる別名</b>: <code>@yearly</code> <code>@annually</code> <code>@monthly</code>
        <code>@weekly</code> <code>@daily</code> <code>@midnight</code> <code>@hourly</code>
        に対応しています。<code>@reboot</code> は時刻を持たないので扱えません。</li>
      <li><b>対応していない記法</b>: <code>L</code>（月末・最終曜日） <code>W</code>（直近の平日）
        <code>#</code>（第n何曜日）は Quartz などの拡張で、標準の cron では動きません。
        書かれていたらエラーにして、その旨をお伝えします。<code>?</code> は
        <code>*</code> と同じものとして扱います。</li>
      <li><b>日と曜日の組み合わせ</b>: 両方に <code>*</code> 以外を書いた場合、
        標準の cron は「<b>どちらかに当てはまれば実行</b>」（OR）です。
        片方だけを絞った場合は、絞ったほうだけを見ます。このページもその規則に従っています。</li>
      <li><b>ステップの起点</b>: <code>*/n</code> はそのフィールドの<b>最小値から</b>数えます。
        分なら 0 から。<code>5/10</code> のように書いた場合は 5 が起点です。</li>
      <li><b>タイムゾーンと夏時間</b>: cron は「壁時計」を見て動きます。
        このページも壁時計で一致を判定しているので、夏時間の切り替え日には
        飛ばされる時刻・二度来る時刻が理屈のうえで発生します。
        日本標準時には夏時間がないため、既定の <code>Asia/Tokyo</code> ではこの問題は起きません。</li>
      <li><b>確かめかた</b>: 次の実行時刻の計算は、Python の <code>croniter</code> を基準にして
        ランダムな式で突き合わせ検証をしています。結果は
        <a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>側に置いてあります。</li>
    </ul>
  </details>''',
     '''  <details>
    <summary>What you can write, and how this page reads it</summary>
    <ul>
      <li><b>Number of fields</b>: five (minute hour day-of-month month day-of-week) is the
        standard. If you write six, <b>the first one is read as seconds</b> (the form used by
        Spring, Quartz and some job runners). A seventh field (year) is not supported.</li>
      <li><b>Symbols</b>: <code>*</code> (all) <code>,</code> (list)
        <code>-</code> (range) <code>/</code> (step).
        <code>*/15</code>, <code>1-5</code>, <code>0,30</code>, <code>9-17/2</code> and
        <code>5/10</code> (from 5 to the end, every 10) all work.</li>
      <li><b>Names</b>: months are <code>JAN</code>&ndash;<code>DEC</code>, weekdays are
        <code>SUN</code>&ndash;<code>SAT</code>. Case does not matter, and ranges such as
        <code>MON-FRI</code> are fine.</li>
      <li><b>Both 0 and 7 mean Sunday</b> in the day-of-week field. <code>0-7</code> therefore
        means the same as every day of the week.</li>
      <li><b>Aliases beginning with @</b>: <code>@yearly</code> <code>@annually</code>
        <code>@monthly</code> <code>@weekly</code> <code>@daily</code> <code>@midnight</code>
        <code>@hourly</code> are supported. <code>@reboot</code> has no clock time, so it cannot
        be handled.</li>
      <li><b>Not supported</b>: <code>L</code> (last day, last weekday) <code>W</code> (nearest
        weekday) and <code>#</code> (nth weekday) are Quartz-style extensions and do not work in
        standard cron. If they appear, this page reports an error saying so. <code>?</code> is
        treated as the same thing as <code>*</code>.</li>
      <li><b>Day-of-month with day-of-week</b>: when both hold something other than
        <code>*</code>, standard cron <b>runs if either one matches</b> (OR). When only one of
        them is narrowed, only that one is consulted. This page follows the same rule.</li>
      <li><b>Where a step starts</b>: <code>*/n</code> counts <b>from the minimum</b> of that
        field &mdash; 0 for minutes. Written as <code>5/10</code>, the start is 5.</li>
      <li><b>Time zones and daylight saving</b>: cron watches the wall clock. This page matches
        against the wall clock too, so on a daylight-saving changeover there are, in principle,
        times that get skipped and times that come round twice.
        Japan Standard Time has no daylight saving, so the default <code>Asia/Tokyo</code>
        never runs into this.</li>
      <li><b>How it was checked</b>: the next-run calculation is verified against Python
        <code>croniter</code> over randomly generated expressions. The script lives with the
        <a href="https://github.com/hirulab-dev/hirulab-tools">source</a>.</li>
    </ul>
  </details>'''),

    ('''  <footer>
    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    実行時刻の計算は目安として使ってください。実際に動くかどうかは、必ず動かす環境で確かめてください。
  </footer>''',
     '''  <footer>
    Built by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI). Free to use,
    no sign-up. Treat the calculated run times as a guide: always confirm the behaviour on the
    machine that will actually run the job.
  </footer>'''),
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
      <li><a href="./qr.html">QR Code Generator</a></li>
      <li><a href="../cron/">Japanese version</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">Tools index</a> &middot;
      <a href="https://note.com/hirulab">Experiment log (JP)</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''

# ── わざと日本語のまま残すリテラル(理由つき) ───────────────────────────────
# cron には1件も無い。計算はすべて数値で書かれていて、日本語のリテラルは
# 全部「画面に出す文言」だった(QR と同じ)。
KEEP = {}

# ── 文字列の中身だけの差し替え(TR辞書) ────────────────────────────────────
TR = {
    # --- 役目ごとに枠を分けた表(日本語側で畳んである) ---
    "日,月,火,水,木,金,土": "Sun,Mon,Tue,Wed,Thu,Fri,Sat",
    "秒,分,時,日,月,曜日": "seconds,minutes,hours,day of month,month,day of week",
    "秒,分,時間,日,か月": " s, min, h, d, mo",
    "1月,2月,3月,4月,5月,6月,7月,8月,9月,10月,11月,12月":
        "January,February,March,April,May,June,July,August,September,October,November,December",
    # 文をつなぐ語。日本語では空になる枠がある(だから1つの表にまとめてある)
    "runPre=|monPre=|monthOf=の|dowPre=|domPre=|at=":
        "runPre=Runs |monPre=in |monthOf=, |dowPre=on |domPre=on day |at=at ",

    # --- 解析のエラー ---
    "のフィールドが空です。": " field is empty.",
    "「": "“",
    "」は Quartz などの拡張記法で、標準の cron では使えません。":
        "” is a Quartz-style extension and is not part of standard cron. ",
    "このページも対応していません。": "This page does not support it either.",
    "に空の項目があります（カンマが余っていませんか）。":
        " has an empty item (is there a stray comma?).",
    "の「/」のうしろは数字で書いてください（":
        ": what follows the “/” has to be a number (",
    "）。": ").",
    "の間隔に 0 は指定できません（": ": the step cannot be 0 (",
    "の「/」の前が空です（": ": there is nothing before the “/” (",
    "）。「*/": "). Write it as “*/",
    "」と書きます。": "”.",
    "の範囲が逆さまです（": ": the range runs backwards (",
    "）。小さいほうを先に書いてください。": "). Put the smaller value first.",
    "に当てはまる値がありません（": ": no value matches (",
    "に ": " cannot take ",
    " は指定できません（": " (the allowed range is ",
    "〜": "–",
    "の範囲で書きます）。": ").",
    "に「": ": “",
    "」は書けません。": "” is not something you can write here. ",
    "数字か ": "Use a number, or a name from ",
    " の名前で書きます。": ".",
    " の数字で書きます。": ".",
    "式が空です。": "The expression is empty.",
    "@reboot は「起動したとき」という意味で、時刻を持ちません。次の実行時刻は計算できません。":
        "@reboot means “when the machine boots” and carries no clock time, "
        "so there is no next run time to calculate.",
    "」という別名は知りません。@yearly / @monthly / @weekly / @daily / @hourly が使えます。":
        "” is not an alias this page knows. "
        "@yearly / @monthly / @weekly / @daily / @hourly are available.",
    "フィールドが ": "This expression has ",
    "個あります。5個（分 時 日 月 曜日）":
        " fields. Write either 5 (minute hour day-of-month month day-of-week) ",
    "または6個（秒 分 時 日 月 曜日）で書いてください。":
        "or 6 (second minute hour day-of-month month day-of-week).",

    # --- 読み下しの文 ---
    # 日本語は「前置き + 数 + 後置き」で組む。英語も数字がすぐ後ろに来る語順に
    # しないと「文字列を空にすると日英一致」の検査が通らない。
    "曜": "",
    "・": ", ",
    '<span class="em">毎秒</span>実行します。': '<span class="em">every second</span>.',
    '<span class="em">毎分</span>実行します。': '<span class="em">every minute</span>.',
    "毎秒": "every second",
    "秒から": " s onward, ",
    "秒おき": "-second intervals",
    "秒": " s",
    "分から": " min onward, ",
    "分おき": "-minute intervals",
    '<span class="em">毎時': '<span class="em">every hour &mdash; ',
    "（": " (",
    "）": ")",
    "に実行します。": ".",
    "分": " min",
    "毎時": "every hour",
    "時から": ":00 through ",
    "時まで": ":00, every ",
    "時間おき": " hours",
    "時": ":00",
    "台の毎分</span>": " &mdash; every minute</span>",
    "実行します。": ".",
    "の": " &mdash; ",
    "日から": " onward, every ",
    "日おき": " days",
    "日": "",
    "毎日": "any day of the week",
    "平日（月〜金）": "weekdays (Mon&ndash;Fri)",
    "土日": "weekends (Sat and Sun)",
    "<b>または</b>": "<b> or </b>",
    "の、": ", ",
    "</span>の、": "</span>, ",

    # --- 落とし穴の指摘 ---
    "別名で書かれています": "Written as an alias",
    "</code> は <code>": "</code> means the same as <code>",
    "</code> と同じ意味です。以下はこの式として読んでいます。":
        "</code>. Everything below is read as that expression.",
    "フィールドが6個あります": "This expression has six fields",
    "先頭を<b>秒</b>として読みました。標準の cron（crontab）は5個なので、":
        "The first field was read as <b>seconds</b>. Standard cron (crontab) takes five, so ",
    "そのまま貼ると「フィールドが多い」と怒られる環境があります。":
        "pasting this as it stands is rejected as &ldquo;too many fields&rdquo; in some places. ",
    "Quartz や Spring の <code>@Scheduled(cron=...)</code> 系はこの6個の書き方です。":
        "Quartz and Spring (<code>@Scheduled(cron=...)</code>) use this six-field form.",
    "日と曜日を両方書いています → 「かつ」ではなく「または」です":
        "Both day-of-month and day-of-week are set &rarr; this is OR, not AND",
    "標準の cron は、日にちと曜日の両方が絞られているとき<b>どちらかに当てはまれば実行</b>します。":
        "When both the day-of-month and the day-of-week are narrowed, standard cron "
        "<b>runs if either one matches</b>. ",
    "</code>（日）と <code>": "</code> (day of month) and <code>",
    "</code>（曜日）の": "</code> (day of week): ",
    "<b>両方を満たす日だけ</b>のつもりなら、この式ではそうなりません。":
        "if you meant <b>only the days that satisfy both</b>, this expression does not do that. ",
    "「毎月1日、ただし月曜だけ」のような条件は cron 式だけでは書けないので、":
        "A condition like &ldquo;the 1st of the month, but only when it is a Monday&rdquo; "
        "cannot be written in a cron expression at all, so ",
    "スクリプト側の先頭で曜日を見て抜ける、という書き方をします。":
        "the usual approach is to check the weekday at the top of the script and exit early.",
    "の「": ": a step of ",
    "おき」は、折り返しのところだけ間隔が変わります":
        " changes the gap only where it wraps around",
    "</code> は ": "</code> matches ",
    " に当てはまります。": ". ",
    "最後の ": "From the last one, ",
    " から次の ": ", to the next one, ",
    " までは <b>": ", there are only <b>",
    "</b> しかありません": "</b>",
    "（ほかは": " (everywhere else the step is ",
    "おき）。": "). ",
    " が ": " is not divisible by ",
    " で割り切れないためで、": ", and ",
    "cron の <code>/</code> は「前回からの経過時間」ではなく「値の一覧」を作る記号だからです。":
        "the <code>/</code> in cron builds a <b>list of values</b>, not "
        "an &ldquo;every N since the last run&rdquo; timer. ",
    "書き方を変えても直りません（値を書き並べても同じ一覧になります）。":
        "Rewriting it does not help (spelling the values out by hand gives the same list). ",
    "等間隔にしたいなら ": "For an even spacing, pick a divisor of ",
    " を割り切る ": " &mdash; ",
    " のどれかにするか、折り返しの": " &mdash; or accept the ",
    "を承知のうえで使ってください。": " at the wrap-around and use it as it is. ",
    "ちょうどの間隔が要るなら、それは cron ではなく":
        " exactly is what you need, that is not a job for cron but for ",
    "常駐プロセスやタイマーの仕事になります。": "a long-running process or a timer.",
    "月": "/",
    "2月29日": "2/29",
    "月31日": "/31",
    "この式は一度も実行されません": "This expression never runs",
    " は存在しない日付です。": " are dates that do not exist. ",
    "指定した日と月の組み合わせが全部この状態なので、この cron は永遠に動きません。":
        "Every combination of the days and months given is like this, so this cron never fires.",
    "存在しない日付が混ざっています": "Some of these dates do not exist",
    " ほか": " and more",
    " は存在しないので、その月では実行されません。":
        " do not exist, so nothing runs in those months.",
    "うるう年しか実行されません": "Runs in leap years only",
    "2月29日は4年に一度（正確には400年に97回）しか来ません。次の実行が3年以上先になります。":
        "29 February comes round once every four years (97 times in 400 years, to be exact). "
        "The next run can be more than three years away.",
    "31日は7か月しかありません": "Only seven months have a 31st",
    "「毎月31日」と書いても、2・4・6・9・11月には実行されません。年7回です。":
        "&ldquo;The 31st of every month&rdquo; still skips February, April, June, September and "
        "November, so it runs seven times a year. ",
    "「月末に実行」を <code>L</code> なしで表したいなら、毎日動かしてスクリプト側で":
        "To say &ldquo;run at the end of the month&rdquo; without <code>L</code>, the usual "
        "workaround is to run every day and let the script check ",
    "「明日が1日かどうか」を見るのが定番の回避策です。": "whether tomorrow is the 1st.",
    "曜日の 7 は日曜です": "7 in the day-of-week field means Sunday",
    "cron の曜日は 0 と 7 のどちらも日曜を指します。":
        "In cron, both 0 and 7 point at Sunday. ",
    "</code> は結果として全曜日と同じ意味になっています。":
        "</code> therefore ends up meaning every day of the week.",
    "「?」が使われています": "&ldquo;?&rdquo; is used",
    "<code>?</code> は Quartz の記法で、標準の cron にはありません。":
        "<code>?</code> is Quartz notation; standard cron does not have it. ",
    "ここでは <code>*</code> と同じものとして読んでいます。crontab に貼るときは <code>*</code> に直してください。":
        "It is read here as the same thing as <code>*</code>. "
        "Change it to <code>*</code> before pasting into a crontab.",
    "1分おきに動きます（年52万回）": "Fires every minute (about 526,000 times a year)",
    "前の実行が終わっていなくても次が始まります。処理が1分を超えると多重に走るので、":
        "The next run starts whether or not the previous one has finished. If the job takes "
        "longer than a minute they pile up on each other, so ",
    "重複を防ぐ仕掛け（ロックファイルなど）を用意しておくのが安全です。":
        "it is safer to have something in place that prevents overlap, such as a lock file.",
    "1秒おきに動きます": "Fires every second",
    "cron 系のスケジューラで毎秒起動するのは、プロセス起動のコストのほうが大きくなりがちです。":
        "Starting a process every second through a cron-style scheduler tends to cost more in "
        "process startup than the work itself. ",
    "常駐プロセスの中でループさせるほうが向いています。":
        "A loop inside a long-running process is the better fit.",

    # --- 見本の式 ---
    "平日の朝9時": "Weekdays at 9am",
    "15分おき": "Every 15 minutes",
    "7分おき（罠）": "Every 7 minutes (trap)",
    "毎月1日の0時": "1st of the month at 0:00",
    "日と曜日の両方（罠）": "Day and weekday together (trap)",
    "うるう年だけ": "Leap years only",
    "週末の2時間おき": "Every 2 hours at weekends",
    "Quartzの ?": "Quartz ?",
    "6フィールド（秒つき）": "Six fields (with seconds)",
    "毎日0時の別名": "Alias for daily at 0:00",

    # --- 画面の更新 ---
    "（このブラウザ）": " (this browser)",
    "秒つき6フィールドとして読みました（Quartz / Spring 系の書き方）":
        "Read as six fields with seconds (the Quartz / Spring form)",
    "標準の5フィールドとして読みました（crontab の書き方）":
        "Read as the standard five fields (the crontab form)",
    "8年先まで探しましたが、当てはまる時刻が見つかりませんでした。存在しない日付を指しているはずです。":
        "Searched eight years ahead and found no matching time. "
        "It must be pointing at a date that does not exist.",
    "あと": "in ",
    "当てはまる時刻は8年以内に ": "Only ",
    " 件しかありませんでした。": " matching times were found within eight years.",
    "左の列が実行時刻（": "The left column is the run time (wall clock in ",
    "の壁時計）、右が1件目からの経過です。": "), the right is the time since the first one.",
    "回以上": "+ times",
    "回": " times",
    "これから1年で": "Over the next year",
    "いちばん短い間隔": "Shortest gap",
    "いちばん長い間隔": "Longest gap",
    "ならすと": "On average",
    "に1回": " apart",
    "これから1年のあいだには一度も実行されません。次に実行されるのは上の一覧のとおりです。":
        "It does not fire at all during the next year. The next runs are the ones listed above.",
    "この式に当てはまる時刻はありません。存在しない日付を指しているはずです。":
        "No time matches this expression. It must be pointing at a date that does not exist.",
    "数えるのは ": "Counting stops at ",
    "件で打ち切っています（1年ぶんに届いていません）。":
        " entries, which is short of a full year. ",
    "間隔の最短・最長は、その打ち切った範囲での値です。":
        "The shortest and longest gaps are taken from that truncated range.",
    "最短と最長の間隔がずれています（実行のない日や時間帯があるためです）。":
        "The shortest and longest gaps are far apart, because there are days or hours "
        "with no runs at all. ",
    "「◯おきに1回」のつもりで書いたなら、上の「気をつけるところ」も確認してください。":
        "If you meant “once every N”, read the points above as well.",
    "これから1年ぶんを実際に数えた値です（見積もりではありません）。":
        "This is counted from an actual year ahead, not an estimate.",
    "（cron は壁時計で動きます。ここで選んだ時計で判定します）":
        "(cron runs on the wall clock. Matching uses the clock selected here.)",
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
    ja_path = docs / "cron" / "index.html"
    en_path = docs / "en" / "cron.html"
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
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
