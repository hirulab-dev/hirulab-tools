#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「タイムゾーン変換」の英語版を、日本語版から作る(2026-09-03 昼)。

**手書きの英語版を生成に置き換えた5本目。これで手書きは0本になる**
(palette 9/1 → csv 9/1 → regex-tester 9/2 → char-counter 9/3朝 → これ)。

## なぜ置き換えるか

手書きの英語版には照合の仕組みが無いので、**日本語版だけが育って英語版が置いていかれる**。
実例が2つ出ている: `en/palette.html` に看板機能がまるごと無かった /
`en/csv.html` の見本が文字コード判定を1度も動かさない形だった。どちらも6日以上気づかれていない。

## ★この1本で初めて分かったこと: 生成すると日本語のコメントが英語ページに載る

生成器は日本語版を写して**文字列リテラルだけ**を訳す。**コメントは誰も見ていなかった**。
だから既に本番でこうなっている(9/3 昼に数えた。ソースは公開してあるので読める):

    en/date.html          日本語のコメント 37行
    en/regex-tester.html                  18行
    en/take-home.html                     12行
    en/char-counter.html                   3行
    en/timezone.html(手書き)               0行  ← 置き換えると増える側に回る

つまり**このページを素直に生成に移すと品質が下がる**。手書き版は英語のコメントを持っているのに、
生成にした瞬間に日本語へ戻ってしまう。
→ `en_common.translate_comments` を新設し、**コメントも訳して突き合わせる**ことにした
(訳が無い日本語コメントがあれば止まる)。**残り4ページの日本語コメントは別件として台帳に載せる**。

⚠ **コメントの訳は行数を変えないこと**。日英のコードを突き合わせる検査は
`blank()`(コメントを消して改行は残す)を通した結果を比べるので、行数が違うと**コードの違い**として出る。

## 位置で決まる差は TR に入らない(`CODE_PARTS`)

`translate_literals` は**文字列の中身をキーにした辞書**なので、
**同じ文字列が場所によって別の訳になるもの**は入れられない。このページには3種類あった:

1. `''`(空文字)…… 語順の入れ替えで使う「前置き/後置き」。`'' + 都市 + ' を外す'` は
   英語だと `'Remove ' + 都市 + ''` になる。**空文字を辞書に入れると全部の空文字が訳される**
2. `'Asia/Tokyo'` などのゾーンID …… 既定の都市が日英で違う(下記)
3. 1 と同じ形が夏時間の説明に2か所(開始/終了)。訳し先が違うので辞書にできない

→ **行ごと差し替える `CODE_PARTS`** に置いた。差し替えても
**文字列の中身を空にすれば日英で1バイトも変わらない**(骨組みは同じ)ので、検査は従来どおり通る。

## 既定の都市を日英で変えている(意図した差)

    ja: Asia/Tokyo, America/Los_Angeles, America/New_York, Europe/London, Asia/Singapore
    en: America/Los_Angeles, America/New_York, Europe/London, Asia/Singapore, Asia/Tokyo

同じ5都市で**並び順だけ**違う(基準が日本の読み手か英語の読み手か)。手書き版がそうなっていたので
そのまま引き継いだ。**都市を足し引きはしていない**(数が変わると比較にならなくなるため)。

使い方: python lab/scripts/make_en_timezone.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (JA_CHARS, code_japanese, comments, script_span,  # noqa: E402
                       translate_comments, translate_literals)

BASE = "https://hirulab-dev.github.io/hirulab-tools/"
OGP = BASE + "ogp/ogp-en-timezone.png"

TITLE_EN = "Time Zone Converter &mdash; meeting overlap, DST gaps, next clock change"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>タイムゾーン変換 — 都市の時差・夏時間の切替・会議の重なり</title>',
     '<title>Time Zone Converter &mdash; meeting overlap, DST gaps, next clock change</title>'),

    ('<meta name="description" content="日時を入れると複数都市の現地時刻を一度に並べ、24時間の重なり表で会議の候補時間を出します。夏時間の切替でその時刻が「存在しない」「1日に2回ある」場合はそう表示し、各都市の次に時差が変わる日も出します。ブラウザ内で完結し、データはどこにも送信されません。">',
     '<meta name="description" content="Convert one moment into many cities at once, find the meeting hours everyone shares, and see when each city next changes its offset. When a time does not exist or happens twice because of daylight saving, this page says so instead of quietly shifting it. Runs entirely in your browser &mdash; nothing is sent anywhere.">'),

    # ── CSS の中の注釈(`<style>` はスクリプトの外なので、ここで訳す) ──
    ('''    /* リンク色は白地で 4.5:1 を超える濃さにしている（明るい #c47f16 だと 3.28:1 しか出ない）。
       --on-accent はアクセント色を背景に敷いたときの文字色。 */''',
     '''    /* The link color is dark enough to clear 4.5:1 on white (#c47f16 only gives 3.28:1).
       --on-accent is the text color used on top of the accent color. */'''),

    # 日本語のフォント指定は英語版では意味が無い(Hiragino/Meiryo は日本語フォント)
    ('       font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif}',
     '       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}'),

    ('''  /* select は一番長い選択肢の幅まで広がるので、min-width:0 で縮めるのを許して
     画面からはみ出さないようにする（IANAのゾーン名は長い） */''',
     '''  /* A select grows to fit its widest option, so allow it to shrink so it does not
     overflow the screen (IANA zone names are long) */'''),

    ('  /* 色を指定しないとブラウザ既定の青になり、ダークモードで 1.89:1 まで落ちる */',
     '  /* Without an explicit color these fall back to browser blue, which drops to 1.89:1 in dark mode */'),

    ('<link rel="canonical" href="%stz/">' % BASE,
     '<link rel="canonical" href="%sen/timezone.html">' % BASE),

    ('<meta property="og:site_name" content="クロードの昼ラボ">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">'),
    ('<meta property="og:locale" content="ja_JP">',
     '<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="タイムゾーン変換 — 都市の時差・夏時間の切替・会議の重なり">',
     '<meta property="og:title" content="%s">' % TITLE_EN),
    ('<meta property="og:description" content="複数都市の現地時刻を一度に並べ、24時間の重なり表で会議の候補時間を出します。夏時間で「存在しない時刻」「2回ある時刻」もそう表示。次に時差が変わる日も分かります。ブラウザ内で完結します。">',
     '<meta property="og:description" content="Convert one moment into many cities at once and find the hours everyone shares. When a time does not exist or happens twice because of daylight saving, this page says so instead of quietly shifting it.">'),
    ('<meta property="og:url" content="%stz/">' % BASE,
     '<meta property="og:url" content="%sen/timezone.html">' % BASE),
    ('<meta property="og:image" content="%sogp/ogp-tz.png">' % BASE,
     '<meta property="og:image" content="%s">' % OGP),

    ('<meta name="twitter:title" content="タイムゾーン変換 — 都市の時差・夏時間の切替・会議の重なり">',
     '<meta name="twitter:title" content="%s">' % TITLE_EN),
    ('<meta name="twitter:description" content="複数都市の現地時刻を一度に並べ、会議の重なり時間を出します。夏時間で存在しない時刻・2回ある時刻もそう表示。ブラウザ内で完結します。">',
     '<meta name="twitter:description" content="One moment in many cities at once, plus the meeting hours everyone shares. DST gaps and repeats are shown, not silently smoothed over.">'),
    ('<meta name="twitter:image" content="%sogp/ogp-tz.png">' % BASE,
     '<meta name="twitter:image" content="%s">' % OGP),

    # JSON-LD。⚠ `<script>` の中は生テキストなので**実体参照を書かない**
    #   (2026-09-02 昼に英語12ページで `Claude&#39;s` がそのまま構造化データに渡っていた)
    ('  "name": "タイムゾーン変換",', '  "name": "Time Zone Converter",'),
    ('  "url": "%stz/",' % BASE, '  "url": "%sen/timezone.html",' % BASE),
    ('  "description": "日時を入れると複数都市の現地時刻を一度に並べ、24時間の重なり表から会議の候補時間を出します。夏時間の切替でその時刻が存在しない場合や1日に2回ある場合はそう表示し、各都市の次に時差が変わる日も出します。ブラウザ内で完結します。",',
     '  "description": "Convert one moment into many cities at once, find the meeting hours everyone shares, and see when each city next changes its UTC offset. Times that do not exist or happen twice because of daylight saving are shown as such. Runs entirely in the browser.",'),
    ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
     '  "browserRequirements": "A modern browser with JavaScript enabled",'),
    ('  "inLanguage": "ja",', '  "inLanguage": "en",'),
    ('"price": "0", "priceCurrency": "JPY" },', '"price": "0", "priceCurrency": "USD" },'),
    ('  "image": "%sogp/ogp-tz.png",' % BASE, '  "image": "%s",' % OGP),
    ('"name": "クロードの昼ラボ", "url": "https://note.com/hirulab"',
     '"name": "Claude\'s Daytime Lab", "url": "https://note.com/hirulab"'),
    ('"name": "クロードの昼ラボ — ツール置き場", "url": "%s"' % BASE,
     '"name": "Claude\'s Daytime Lab — Tools", "url": "%sen/"' % BASE),

    # ── 本文 ──
    ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>',
     '  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab — Tools</a>'),
    ('  <h1>タイムゾーン変換</h1>', '  <h1>Time Zone Converter</h1>'),

    ('''  <p class="lead">日時を入れると、選んだ都市の<strong>現地時刻をまとめて</strong>並べます。
    24時間の<strong>重なり表</strong>から会議の候補時間が見つかり、
    各都市が<strong>次に時差を変える日</strong>も分かります。
    夏時間の切替で入力した時刻が<strong>存在しない</strong>ときや
    <strong>1日に2回ある</strong>ときは、黙ってずらさずにそう伝えます。</p>''',
     '''  <p class="lead">Pick a moment and see it in <strong>every city at once</strong>.
    The 24-hour <strong>overlap grid</strong> shows which hours your whole group can meet,
    and each city&#39;s row tells you <strong>when it next changes its offset</strong>.
    If daylight saving means your chosen time <strong>does not exist</strong> or
    <strong>happens twice that day</strong>, this page says so instead of quietly shifting it.</p>'''),

    ('''    <strong>このページは通信を一切行いません。</strong>
    時差のデータはブラウザ自身が持っているもの（IANAタイムゾーンデータベース）を読んでいます。
    読み込んだあとは機内モードでも動きます。入力した予定がどこかに送られることはありません。''',
     '''    <strong>This page makes no network requests.</strong>
    The offset data comes from the IANA time zone database your browser already ships with.
    Once loaded, it works offline. Nothing you type leaves your device.'''),

    ('    <h2>基準にする日時</h2>', '    <h2>The moment</h2>'),
    ('        <label for="d">日付</label>', '        <label for="d">Date</label>'),
    ('        <label for="t">時刻</label>', '        <label for="t">Time</label>'),
    ('        <label for="basetz">どこの時刻か</label>',
     '        <label for="basetz">In which city</label>'),
    ('      <button class="btn p" id="now">いまの時刻にする</button>',
     '      <button class="btn p" id="now">Use current time</button>'),

    ('    <h2>並べる都市</h2>', '    <h2>Cities to compare</h2>'),
    ('        <label for="addtz">追加する</label>', '        <label for="addtz">Add a city</label>'),
    ('      <button class="btn" id="add">追加</button>',
     '      <button class="btn" id="add">Add</button>'),
    ('      <button class="btn" id="reset">既定に戻す</button>',
     '      <button class="btn" id="reset">Reset to defaults</button>'),

    ('    <h2>それぞれの現地時刻</h2>', '    <h2>Local time in each city</h2>'),
    ('''          <th>都市</th><th>現地の日時</th><th>差</th>
          <th class="c-opt">UTCとの差</th><th class="c-opt">次に時差が変わる日</th>''',
     '''          <th>City</th><th>Local date and time</th><th>Difference</th>
          <th class="c-opt">UTC offset</th><th class="c-opt">Next offset change</th>'''),

    ('    <h2>会議の重なり（基準の日の24時間）</h2>',
     '    <h2>Meeting overlap (24 hours of the chosen day)</h2>'),
    ('        <label for="ws">仕事の時間（開始）</label>',
     '        <label for="ws">Working hours from</label>'),
    ('        <label for="we">終了</label>', '        <label for="we">to</label>'),
    ('      <span class="statnote" style="margin:0">全都市がこの時間帯に入る列を枠で囲みます</span>',
     '      <span class="statnote" style="margin:0">Columns where every city is inside those hours get an outline</span>'),

    ('''      <span><i class="work"></i>仕事の時間</span>
      <span><i class="awake"></i>起きてはいる（7時〜22時）</span>
      <span><i class="sleep"></i>深夜・早朝</span>''',
     '''      <span><i class="work"></i>Working hours</span>
      <span><i class="awake"></i>Awake but off the clock (7:00&ndash;22:00)</span>
      <span><i class="sleep"></i>Night</span>'''),

    ('    <h2>機械向けの表し方</h2>', '    <h2>Machine-readable</h2>'),
    ('    <p class="statnote">この瞬間を指す値です。どの都市から見ても同じ1つの数字になります。</p>',
     '    <p class="statnote">These all point at the same instant. Every city agrees on this number.</p>'),

    ('    <h2>このブラウザの時差データは新しいか</h2>',
     '    <h2>Is your browser&#39;s time zone data current?</h2>'),
    ('''      時差の規則は毎年どこかの国が変えます。ブラウザが内蔵しているデータが古ければ、
      このページの答えもその分だけ古くなります。<strong>最近変わったところを狙って3つ確かめます</strong>
      （基準は IANA タイムゾーンデータベース <b>2026c</b>。2026-08-22 に照合した内容です）。''',
     '''      Some country changes its daylight saving rules every year. If the data inside your browser
      is stale, the answers on this page are stale with it.
      <strong>Three recent changes are probed below</strong>
      (reference: IANA time zone database <b>2026c</b>, checked on 2026-08-22).'''),
    ('          <th>確かめること</th><th>2026c では</th><th>このブラウザ</th><th>結果</th>',
     '          <th>Probe</th><th>2026c says</th><th>This browser</th><th>Verdict</th>'),

    ('    <summary>夏時間まわりで何が起きるのか（このページが指摘すること）</summary>',
     '    <summary>What daylight saving actually does to your calendar</summary>'),
    ('''      <li><b>存在しない時刻がある</b>: 夏時間が始まる日、時計は 2:00 から 3:00 へ飛びます。
        その日の 2:30 は<b>この世に存在しません</b>。多くの変換サイトは黙って 3:30 に読み替えますが、
        このページは「存在しない」と表示して、前後どちらに寄せるかを見せます。</li>
      <li><b>1日に2回ある時刻がある</b>: 夏時間が終わる日、時計は 2:00 から 1:00 へ戻ります。
        その日の 1:30 は<b>2回来ます</b>。どちらの 1:30 かで、他都市の時刻は1時間ずれます。
        このページは両方を出します。</li>
      <li><b>時差は固定ではない</b>: 日本とニューヨークの差は 13時間か14時間かのどちらかで、
        年に4回入れ替わります（切り替わる日が日米でずれるため）。
        「毎週この時間」で決めた定例会議は、年に数回、片方だけ1時間ずれます。
        表の<b>「次に時差が変わる日」</b>がその日です。</li>
      <li><b>1時間とは限らない</b>: オーストラリアのロードハウ島は<b>30分</b>しか動きません。
        インドは +5:30、ネパールは +5:45、ニュージーランドのチャタム諸島は +12:45 です。</li>
      <li><b>南半球は逆</b>: シドニーやサンパウロの夏は日本の冬です。切替の向きも逆になります。</li>''',
     '''      <li><b>Some times do not exist.</b> On the spring-forward day the clock jumps from 2:00 to 3:00,
        so 2:30 never happens. Most converters silently read that as 3:30. This page tells you it is
        missing and shows the nearest real times on either side.</li>
      <li><b>Some times happen twice.</b> On the fall-back day the clock returns from 2:00 to 1:00,
        so 1:30 comes around again. Which 1:30 you meant shifts every other city by an hour,
        so this page offers both.</li>
      <li><b>The gap between two cities is not constant.</b> Tokyo and New York are either 13 or 14
        hours apart, and they swap four times a year because the two countries switch on different
        dates. A recurring meeting will drift by an hour for a few weeks each year.
        The <b>Next offset change</b> column is when that happens.</li>
      <li><b>It is not always one hour.</b> Lord Howe Island in Australia shifts by <b>30 minutes</b>.
        India sits at +5:30, Nepal at +5:45, and the Chatham Islands at +12:45.</li>
      <li><b>The southern hemisphere runs the other way.</b> Summer in Sydney and S&atilde;o Paulo is
        winter in the north, and the switch directions are reversed.</li>'''),

    ('    <summary>このページの作り（何を信じて、何を信じていないか）</summary>',
     '    <summary>How this page works (what it trusts and what it doesn&#39;t)</summary>'),
    ('''      <li><b>時差のデータはブラウザの中にあります。</b>どのブラウザも IANA タイムゾーンデータベースを
        内蔵しているので、通信せずに「その都市のその瞬間の時差」が引けます
        （<code>Intl.DateTimeFormat</code> 経由）。このページは自前の時差表を持っていません。
        持つと更新のたびに嘘になるからです。</li>
      <li><b>切替日は探して見つけています。</b>ブラウザは「いつ切り替わるか」を直接教えてくれないので、
        1時間ずつ時差を見比べて変わり目を挟み込み、そこから<b>二分探索で1秒まで</b>詰めています。</li>
      <li><b>略称（JST・PDT など）は表示していません。</b>環境によって <code>GMT+9</code> になったり
        <code>JST</code> になったり割れるうえ、CST のように<b>複数の国で同じ略称</b>が使われるものがあります。
        このページはオフセット（<code>UTC+09:00</code>）を正としています。</li>
      <li><b>ブラウザのデータが古い可能性</b>は残ります。各国の夏時間の廃止・変更は毎年あり、
        反映はブラウザの更新に依存します。上の「このブラウザの時差データは新しいか」が
        その簡易チェックです。</li>
      <li><b>検証</b>: このページの計算部分を取り出して、Python の <code>zoneinfo</code>
        （別のタイムゾーンデータ）と突き合わせています。時差・現地時刻・切替日時・
        「存在しない／2回ある」の判定を、72の都市 × 2015〜2030年で、合計 149,196件を比較しました。
        <b>その過程で、照合に使ったブラウザのほうが2か所古いことが分かりました</b>
        （バンクーバーとカサブランカ）。上の鮮度チェックは、その2か所をそのまま使っています。</li>''',
     '''      <li><b>The offset data lives in your browser.</b> Every browser ships the IANA time zone
        database, so the offset for a given city at a given instant can be read without any network
        request (through <code>Intl.DateTimeFormat</code>). This page carries no offset table of its
        own &mdash; a hand-written table would start lying the moment a country changed its rules.</li>
      <li><b>Change dates are searched for, not looked up.</b> Browsers will not tell you when an
        offset changes, so this page walks forward an hour at a time until the offset differs,
        then <b>binary-searches down to the second</b>.</li>
      <li><b>Abbreviations (JST, PDT, &hellip;) are deliberately not shown.</b> Engines disagree &mdash; the
        same zone renders as <code>GMT+9</code> in one and <code>JST</code> in another &mdash; and letters
        like CST mean different things in different countries. The numeric offset
        (<code>UTC+09:00</code>) is the authority here.</li>
      <li><b>Your browser&#39;s copy may still be out of date.</b> Countries drop or move daylight saving
        every year, and whether that reaches you depends on your browser updating. The
        &ldquo;Is your browser&#39;s time zone data current?&rdquo; panel above is the quick check.</li>
      <li><b>Verification</b>: the calculation core of this page was extracted and compared against
        Python&#39;s <code>zoneinfo</code> &mdash; an independent copy of the time zone database.
        Offsets, local wall clocks, transition instants and the &ldquo;missing / twice&rdquo; verdicts
        were checked across 72 cities and the years 2015&ndash;2030 &mdash; 149,196 comparisons in total.
        <b>The two mismatches turned out to be the browser being out of date, not this page</b>
        (Vancouver and Casablanca). The freshness probe above reuses exactly those two cases.</li>'''),

    ('''    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    時差のデータはブラウザが持っているものを読んでいます。
    大事な予定は、開催する国の告知でも確かめてください。''',
     '''    Built by Claude&#39;s Daytime Lab &mdash; an AI (Claude) working on its own. Free, no sign-up.
    Offset data comes from whatever your browser ships with; for anything important,
    confirm against the announcement from the country hosting the event.'''),
]

# ★**文字列の中身をキーにできない差**(同じ文字列が場所によって別の訳になる)。行ごと差し替える。
#   差し替えても `blank()` を通すと日英で1バイトも変わらない = 検査はそのまま通る。
CODE_PARTS = [
    # 既定の都市。同じ5都市で並び順だけ違う(日本語版は東京が先頭)
    ("var DEFAULTS = ['Asia/Tokyo', 'America/Los_Angeles', 'America/New_York',\n"
     "                'Europe/London', 'Asia/Singapore'];",
     "var DEFAULTS = ['America/Los_Angeles', 'America/New_York', 'Europe/London',\n"
     "                'Asia/Singapore', 'Asia/Tokyo'];"),

    # 語順の入れ替え。日本語は「東京 を外す」、英語は「Remove Tokyo」
    ("      b.setAttribute('aria-label', '' + cityName(z) + ' を外す');",
     "      b.setAttribute('aria-label', 'Remove ' + cityName(z) + '');"),

    # 夏時間の**開始**。日本語は都市が先、英語は "Daylight saving starts in <都市>"
    ("    var msg = '' + cityName(baseZone) +\n"
     "      ' では、この日に夏時間が始まるため時計が飛びます。';",
     "    var msg = 'Daylight saving starts in ' + cityName(baseZone) +\n"
     "      ' on this day, so the clock jumps over it.';"),

    # 夏時間の**終了**。上と同じ形だが訳し先が違うので、辞書には入れられない
    ("      '' + cityName(baseZone) + ' ではこの日に夏時間が終わり、時計が戻ります。'",
     "      'Daylight saving ends in ' + cityName(baseZone) + ' on this day and the clock rewinds, '"),
]

# JS のコメント。⚠ **行数を変えないこと**(日英のコード突き合わせが行単位のため)
COMMENTS = {
    '''/* ---- タイムゾーンの計算 ------------------------------------------------
   自前の時差表は持たない。ブラウザが内蔵している IANA タイムゾーンデータを
   Intl.DateTimeFormat 経由で引き、そこから
     ・ある瞬間の時差（tzOffsetSec）
     ・壁時計 → 瞬間（wallToInstants。0個＝存在しない / 2個＝2回ある）
     ・時差が変わる瞬間（transitionsBetween）
   を組み立てる。Date.UTC は「タイムゾーンのないカレンダー計算機」として使う。 */''':
    '''/* ---- Time zone math ----------------------------------------------------
   No hand-written offset table. The IANA data inside the browser is read
   through Intl.DateTimeFormat, and everything else is built on top of it:
     - the offset at an instant        (tzOffsetSec)
     - wall clock -> instant           (wallToInstants; 0 = missing, 2 = repeated)
     - the instant an offset changes   (transitionsBetween)
   Date.UTC is used purely as a calendar calculator with no zone attached. */''',

    '/* その瞬間に、その都市の時計が指している値（壁時計） */':
    '/* What the clock in that city reads at that instant */',

    '''/* 壁時計を「タイムゾーンのない通し番号」に変換する。
   Date.UTC は 0〜99 年を 1900 年代に読み替えるので、そこだけ手当てする。 */''':
    '''/* Turn a wall clock into a zone-free serial number.
   Date.UTC maps years 0-99 into the 1900s, so that case is patched up. */''',

    '/* その瞬間の時差（秒。UTC+9 なら 32400） */':
    '/* Offset at an instant, in seconds (UTC+9 is 32400) */',

    '''/* 壁時計 → 該当する瞬間の一覧。
   通常は1個。夏時間の開始で飛んだ時刻は0個、終了で戻った時刻は2個になる。 */''':
    '''/* Wall clock -> every instant it maps to. Usually one.
   Zero when the spring-forward jump swallowed it, two when the rewind repeated it. */''',

    '/* ±26時間 */': '/* +/- 26 hours */',

    '''/* 期間内で時差が変わる瞬間を全部拾う。
   1時間刻みで変わり目を挟み込み、二分探索で1秒まで詰める。
   （1時間より近い2回の切替は1回に見える。tzdata の 1970 年以降には無い） */''':
    '''/* Every instant in the range where the offset changes.
   Bracket it an hour at a time, then binary-search down to the second.
   (Two changes less than an hour apart would look like one. Post-1970 tzdata has none.) */''',

    '''/* その年に使われる時差のうち一番小さいものを標準時とみなし、
   それより進んでいれば夏時間中と判定する（南半球でも同じ理屈で成り立つ）。 */''':
    '''/* The smallest offset used during the year is treated as standard time;
   anything ahead of it counts as daylight saving. Works in both hemispheres. */''',

    '/* ---- 都市の名前 ------------------------------------------------------- */':
    '/* ---- City names -------------------------------------------------------- */',

    '/* ---- 画面 -------------------------------------------------------------- */':
    '/* ---- UI ---------------------------------------------------------------- */',

    '/* 取れなければ東京のまま */': '/* keep the default if the browser will not say */',

    '/* 曖昧なときに選ばれた側 */': '/* which side the reader picked when a time is ambiguous */',

    '/* 夏時間の開始で飛んだ時刻。前後の実在する時刻を出す。 */':
    '/* A time swallowed by the spring-forward jump. Show the real times on either side. */',

    '/* 基準の日の 0時〜23時（基準都市の壁時計）を1列ずつ見る */':
    '/* Walk hours 0-23 of the chosen day on the base city clock, one column each */',

    '''/* 全員は無理でも「いちばんマシな時間」は要る。仕事の時間に入る都市が
       一番多い列を出し、そこから外れる都市を現地時刻つきで名指しする。 */''':
    '''/* No hour works for everyone, so name the least bad one: the column with the
       most cities inside working hours, plus who it leaves out and at what local time. */''',

    '''/* ---- ブラウザの時差データの鮮度 ---------------------------------------
   最近規則が変わった場所を狙い撃ちして、いま動いているブラウザがそれを
   知っているかを見る。基準は IANA 2026c（Python の zoneinfo と照合ずみ）。
   1つ目は「昔から動かない場所」で、この検査自体が動いていることの確認用。 */''':
    '''/* ---- How current is the browser's time zone data ----------------------
   Probe places whose rules changed recently. Reference: IANA 2026c, cross
   checked against Python's zoneinfo. The first row is a place that has not
   moved in decades, so you can see the check itself is alive. */''',

    '/* ---- 起動 -------------------------------------------------------------- */':
    '/* ---- Start ------------------------------------------------------------- */',

    '/* 一覧に無いゾーンなら足す */': '/* add the zone if it is not in the list */',
}

# スクリプトの中の文字列リテラル。中身の完全一致で差し替える
TR = {
    # 都市名(表示用)。IANA のゾーンIDは訳さない
    '東京': 'Tokyo', 'ソウル': 'Seoul', '上海・北京': 'Shanghai / Beijing',
    '台北': 'Taipei', '香港': 'Hong Kong', 'シンガポール': 'Singapore',
    'バンコク': 'Bangkok', 'ジャカルタ': 'Jakarta', 'マニラ': 'Manila',
    'ホーチミン': 'Ho Chi Minh City', 'インド（コルカタ）': 'India (Kolkata)',
    'カトマンズ': 'Kathmandu', 'カラチ': 'Karachi', 'ドバイ': 'Dubai',
    'テヘラン': 'Tehran', 'エルサレム': 'Jerusalem', 'イスタンブール': 'Istanbul',
    'モスクワ': 'Moscow', 'キーウ': 'Kyiv', 'ワルシャワ': 'Warsaw',
    'ベルリン': 'Berlin', 'パリ': 'Paris', 'アムステルダム': 'Amsterdam',
    'チューリッヒ': 'Zurich', 'ローマ': 'Rome', 'マドリード': 'Madrid',
    'ストックホルム': 'Stockholm', 'ヘルシンキ': 'Helsinki', 'リスボン': 'Lisbon',
    'ダブリン': 'Dublin', 'ロンドン': 'London', 'UTC（協定世界時）': 'UTC',
    'ラゴス': 'Lagos', 'カイロ': 'Cairo', 'ナイロビ': 'Nairobi',
    'ヨハネスブルグ': 'Johannesburg', 'サンパウロ': 'Sao Paulo',
    'ブエノスアイレス': 'Buenos Aires', 'サンティアゴ': 'Santiago', 'リマ': 'Lima',
    'ボゴタ': 'Bogota', 'ニューヨーク': 'New York', 'トロント': 'Toronto',
    'シカゴ': 'Chicago', 'メキシコシティ': 'Mexico City', 'デンバー': 'Denver',
    'フェニックス': 'Phoenix', 'ロサンゼルス': 'Los Angeles', 'バンクーバー': 'Vancouver',
    'アンカレジ': 'Anchorage', 'ホノルル': 'Honolulu', 'グアム': 'Guam',
    'フィジー': 'Fiji', 'アピア（サモア）': 'Apia (Samoa)', 'パース': 'Perth',
    'ブリスベン': 'Brisbane', 'アデレード': 'Adelaide', 'メルボルン': 'Melbourne',
    'シドニー': 'Sydney', 'ロードハウ島': 'Lord Howe Island', 'オークランド': 'Auckland',
    'チャタム諸島': 'Chatham Islands',

    # 曜日。表の幅に効くので3文字に揃える
    '日': 'Sun', '月': 'Mon', '火': 'Tue', '水': 'Wed', '木': 'Thu', '金': 'Fri', '土': 'Sat',

    # 選択肢のグループ
    'よく使う都市': 'Common cities',
    'そのほかすべて（': 'All other zones (',
    '件）': ')',

    # 夏時間の注意書き
    ' 直前に実在するのは ': ' The last real time before it is ',
    '、直後は ': ' and the first one after is ',
    ' です。': '.',
    'その時刻は存在しません': 'That time never happens',
    '直後の時刻で計算しています': 'Using the time just after the jump',
    '以下の表は ': 'Everything below is calculated as ',
    ' として並べています。': '.',
    'この時刻は1日に2回あります': 'That time happens twice on this day',
    '同じ ': 'so ',
    ' が2回来るので、どちらかを選んでください。': ' comes around twice. Pick the one you meant.',
    '1回目': 'First',
    '2回目': 'Second',

    # 一覧表
    ' 翌日': ' next day',
    ' 前日': ' previous day',
    '基準': 'base',
    '時間': ' h',
    '夏時間': 'DST',
    '当分ありません': 'none coming up',
    '時間）': ' h)',
    '基準は ': 'Base: ',
    ' の ': ', ',
    '（': ' (',
    '）': ')',
    '）です。': '). ',
    '時差の大きい順に並べています。「次に時差が変わる日」は、その都市の夏時間が始まるか終わる日です。':
        'Sorted from the largest offset down. "Next offset change" is the day that city starts or ends daylight saving.',

    # 重なり表
    '基準都市でこの時刻は存在しません（夏時間の開始）':
        'This hour does not exist in the base city (daylight saving starts)',
    '横は基準都市（': 'Columns are hours in the base city (',
    '）の時刻、マスの中は各都市の現地の「時」です。': '); each cell is that city’s local hour.',
    ' 全員が ': ' No hour puts every city inside ',
    '時〜': ':00–',
    '時に入る時間帯は、この組み合わせでは1つもありません。': ':00.',
    '時': ':00',
    ' 一番多くの都市が入るのは ': ' The closest is ',
    '時（': ':00 in ',
    '基準）で、': ', which works for ',
    '都市のうち ': ' cities; ',
    '都市。外れるのは ': ' fit. Left out: ',
    '・': ', ',
    ' 都市を減らすか、時間の幅を広げてみてください。': ' Try dropping a city or widening the hours.',
    ' 全員が仕事の時間に入るのは ': ' Everyone is inside working hours at ',
    '基準）の ': ' time) — ',
    '枠です。': ' slots.',

    # 機械向けの表し方
    'UNIX時間（秒）': 'Unix time (seconds)',
    'UNIX時間（ミリ秒）': 'Unix time (milliseconds)',
    'ISO 8601（UTC）': 'ISO 8601 (UTC)',
    '基準都市のISO 8601': 'ISO 8601 (base city)',

    # 鮮度チェック
    '東京は1951年から動いていない': 'Tokyo has not moved since 1951',
    '検査そのものの動作確認': 'control row',
    'バンクーバーは冬も UTC−07:00': 'Vancouver stays at UTC−07:00 in winter',
    '2026年秋以降、時計を戻さなくなる': 'stops falling back after autumn 2026',
    'カサブランカは UTC+00:00': 'Casablanca sits at UTC+00:00',
    '2026年秋以降、切替が無くなる': 'switching stops after autumn 2026',
    '判定できず': 'unknown zone',
    '知っている': 'up to date',
    '古い': 'stale',
    'このブラウザの時差データは 2026c 相当まで新しいようです。':
        'Your browser looks current as of IANA 2026c.',
    'このブラウザの時差データは ': 'Your browser is behind on ',
    ' 件ぶん古いようです。': ' of these. ',
    '該当する国・地域の結果は実際とずれる可能性があります。': 'Results for those countries may be wrong. ',
    'ブラウザ（スマートフォンならOS）を更新すると新しくなります。':
        'Updating the browser (or the OS on a phone) refreshes the data.',
    '一部のタイムゾーンをこのブラウザが知らないため判定できませんでした。':
        'Your browser does not know some of these zones, so the check could not run.',
    ' なお、この3件を知っていても他の変更まで反映されているとは限りません。':
        ' Passing all three does not prove every other change made it in either. ',
    '大事な予定は開催する国の告知でも確かめてください。':
        'For anything important, confirm against the announcement from the country hosting the event.',
}

# わざと日本語のまま残すリテラル(理由つき)。今回は0件。
KEEP = set()


def en_nav(docs):
    """英語ナビを**実ページから**組み直す(`en_nav.build`)。生成元がずれようがない。"""
    import en_nav as _en_nav
    return _en_nav.build(docs, "frima-profit.html", "Flea-Market Profit Calculator",
                         "timezone.html", "../tz/")


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path.home() / "hirulab-tools" / "docs")
    ja_path = docs / "tz" / "index.html"
    en_path = docs / "en" / "timezone.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    for a, b in CODE_PARTS:
        if a not in en:
            sys.exit("コードの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'  <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not nav:
        sys.exit("ナビが見つかりません")
    en = en[:nav.start()] + en_nav(docs) + en[nav.end():]

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
    for _q, body in literals(en[s2:e2]):
        if JA_CHARS.search(body):
            if body not in KEEP:
                sys.exit("スクリプトの中に訳し忘れがあります: " + body[:120])
            kept.append(body)

    # (3) 文字列でもコメントでも正規表現でもない日本語(識別子・object のキー)が無いこと
    ident = code_japanese(en[s2:e2])
    if ident:
        sys.exit("スクリプトの中に文字列でない日本語があります: %s" % ident[:4])

    # (4) ★コメントにも日本語が残っていないこと(このページで初めて見る検査)
    ja_com = [c for c in comments(en[s2:e2]) if JA_CHARS.search(c)]
    if ja_com:
        sys.exit("コメントに日本語が %d 件残っています: %s" % (len(ja_com), ja_com[0][:120]))

    # (5) 文字列の中身を空にすると、日英でコードが**1バイトも違わない**こと
    sj, ej = script_span(ja)
    a, b = blank(ja[sj:ej]), blank(en[s2:e2])
    if a != b:
        la, lb = a.split("\n"), b.split("\n")
        if len(la) != len(lb):
            sys.exit("コードの行数が違います(ja %d / en %d)" % (len(la), len(lb)))
        for i, (x, y) in enumerate(zip(la, lb)):
            if x != y:
                sys.exit("コードが違います(%d行目):\n  ja: %s\n  en: %s" % (i + 1, x, y))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("訳した文字列: %d 件 / 訳したコメント: %d 件" % (len(TR), len(COMMENTS)))
    print("位置で決まる差し替え(CODE_PARTS): %d 件" % len(CODE_PARTS))
    print("画面に出るところの日本語: 0箇所 / 文字列でない日本語: 0箇所 / コメントの日本語: 0件")
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: %d バイトで日英が一致" % len(a.encode()))


if __name__ == "__main__":
    main()
