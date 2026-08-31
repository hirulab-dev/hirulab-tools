#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「単位換算」の英語版を、日本語版から作る(2026-08-31)。

`make_en_json.py` などと同じ方式。ナビは `en_nav.build` がほどいて組み直す。
**日本語版が唯一の原本**で、英語版を手で直さない。

★この回に固有の話が2つある。

1. **記号(`s`)と名前(`nm`)が同じ literal の行があった** — `{s:'日', nm:'日'}` など。
   同じリテラルは同じ英語にしか置き換えられないので、`s='d' / nm='day'` のように
   割ることができない。**日本語版のほうを直した**: 記号と名前が同じ行では名前を出さない
   (`u.nm !== u.s`)。日本語でも「日 日」と二重に出ていたので、これは是正でもある。
   → 英語では `{s:'day', nm:'day'}` になり、画面には `day` だけが出る。

2. **尺貫法の単位はローマ字にした**(寸→sun / 坪→tsubo / 合→gō …)。
   英語ページに日本語を1文字も出さない方針のため。読み(すん・しゃく…)は
   ローマ字と同じ文字列に訳しているので、1 の仕組みで自動的に画面から消える
   (=metric の `{s:'m', nm:'metre'}` に対して `{s:'sun', nm:'sun'}` という形)。
   ⚠ `しゃく` は **尺(長さ)と勺(体積)の両方**で使われている literal だが、
   どちらも読みは同じ「しゃく」で、**カテゴリが違うので同じ表に並ばない**。
   `じょう`(丈=長さ / 畳=面積)も同じ。

使い方: python lab/scripts/make_en_unit.py <リポジトリの docs>
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

    ('<title>単位換算 — 坪・畳・合・升・匁まで、根拠つきで一度に出す</title>',
     '<title>Unit Converter &mdash; tsubo, tatami, g&#333; and monme too, each with its basis</title>'),

    ('<meta name="description" content="長さ・重さ・面積・体積・温度など12種類の単位を一度にまとめて換算します。坪・畳・尺・合・升・匁といった日本の単位に対応し、それぞれの換算値が「定義された正確な値」か「近似値」かを表示します。ブラウザ内で完結し、データはどこにも送信されません。">',
     '<meta name="description" content="Converts 12 kinds of unit &mdash; length, mass, area, volume, temperature and more &mdash; all at once. It covers the Japanese traditional units (tsubo, tatami, shaku, g&#333;, sh&#333;, monme) and marks every row as either an exact defined value or an approximation. Everything runs in your browser and nothing is sent anywhere.">'),

    ('<link rel="canonical" href="%s/unit/">\n'
     '<link rel="alternate" hreflang="ja" href="%s/unit/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/unit.html">' % (SITE, SITE, SITE),
     '<link rel="canonical" href="%s/en/unit.html">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/unit.html">\n'
     '<link rel="alternate" hreflang="ja" href="%s/unit/">' % (SITE, SITE, SITE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="単位換算 — 坪・畳・合・升・匁まで、根拠つきで一度に出す">',
     '<meta property="og:title" content="Unit Converter">'),

    ('<meta property="og:description" content="12種類の単位をまとめて換算。坪・畳・尺・合・升・匁など日本の単位に対応し、換算値が定義値か近似値かを表示します。ブラウザ内で完結します。">',
     '<meta property="og:description" content="Converts 12 kinds of unit at once, including the Japanese traditional ones, and marks each row as an exact defined value or an approximation. It all runs in the browser.">'),

    ('<meta property="og:url" content="%s/unit/">' % SITE,
     '<meta property="og:url" content="%s/en/unit.html">' % SITE),

    ('<meta property="og:image" content="%s/ogp/ogp-unit.png">' % SITE,
     '<meta property="og:image" content="%s/ogp/ogp-unit-en.png">' % SITE),

    ('<meta name="twitter:title" content="単位換算 — 坪・畳・合・升・匁まで、根拠つきで一度に出す">',
     '<meta name="twitter:title" content="Unit Converter">'),

    ('<meta name="twitter:description" content="12種類の単位をまとめて換算。坪・畳・尺・合・升・匁など日本の単位に対応し、換算値が定義値か近似値かを表示します。">',
     '<meta name="twitter:description" content="Converts 12 kinds of unit at once, including the Japanese traditional ones, and marks each row as exact or approximate.">'),

    ('<meta name="twitter:image" content="%s/ogp/ogp-unit.png">' % SITE,
     '<meta name="twitter:image" content="%s/ogp/ogp-unit-en.png">' % SITE),

    ('''  "name": "単位換算",
  "url": "https://hirulab-dev.github.io/hirulab-tools/unit/",
  "description": "長さ・重さ・面積・体積・温度など12種類の単位を一度にまとめて換算します。坪・畳・尺・合・升・匁といった日本の単位に対応し、換算値が定義された正確な値か近似値かを表示します。ブラウザ内で完結します。",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-unit.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "Unit Converter",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/unit.html",
  "description": "Converts 12 kinds of unit &mdash; length, mass, area, volume, temperature and more &mdash; all at once. It covers the Japanese traditional units and marks every row as an exact defined value or an approximation. It all runs inside the browser.",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-unit-en.png",
  "author": { "@type": "Organization", "name": "Claude&#39;s Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude&#39;s Daytime Lab &mdash; Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>単位換算</h1>
  <p class="lead">1つ入れると、同じ種類の単位が<strong>全部いっぺんに</strong>出ます。
    坪・畳・尺・合・升・匁といった日本の単位にも対応していて、
    <strong>その換算値が「定義された正確な値」なのか「近似値」なのかを1件ずつ表示します。</strong></p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    換算はすべてブラウザの中で計算しています。読み込んだあとは機内モードでも動きます。
    （為替レートのように通信が必要になる「通貨」は、この方針と両立しないので入れていません。）
  </div>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>Unit Converter</h1>
  <p class="lead">Type one number and <strong>every unit of that kind</strong> comes out at once.
    The Japanese traditional units are here too &mdash; tsubo, tatami, shaku, g&#333;, sh&#333;, monme &mdash; and
    <strong>each row says whether its value is exact by definition or only an approximation.</strong></p>

  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    Every conversion is computed inside your browser. Once the page has loaded it keeps working in airplane mode.
    (Currency is deliberately absent: exchange rates would need the network, which this page will not do.)
  </div>'''),

    ('''      <input type="text" id="value" inputmode="decimal" spellcheck="false" value="1"
             aria-label="換算したい数値" placeholder="例: 1.5 / 3/8 / 5 3/8 / 1,200">
      <select id="from" aria-label="入力した値の単位"></select>
      <button class="mini" id="swapTop" title="この単位を一覧の先頭にして基準にします">↑ 基準にする</button>''',
     '''      <input type="text" id="value" inputmode="decimal" spellcheck="false" value="1"
             aria-label="The number to convert" placeholder="e.g. 1.5 / 3/8 / 5 3/8 / 1,200">
      <select id="from" aria-label="The unit that number is in"></select>
      <button class="mini" id="swapTop" title="Move this unit to the top of the list and convert from it">&uarr; Use as the base</button>'''),

    ('''      畳1枚の広さは地域や建物で違います。何を基準にするか:
      <select id="tatamiSel">
        <option value="1.62">表示基準 1.62㎡</option>
        <option value="1.82405">京間・本間 1.824㎡</option>
        <option value="1.65620">中京間 1.656㎡</option>
        <option value="1.54880">江戸間・関東間 1.549㎡</option>
        <option value="1.44500">団地間 1.445㎡</option>
      </select>
      <br><span style="font-size:.95em">「表示基準」は不動産広告の規約で決められた下限（1畳＝1.62㎡以上として表示する）。
      京間は0.955×1.91m、中京間は0.91×1.82m、江戸間は0.88×1.76m、団地間は0.85×1.70mの畳を1枚として計算しています。</span>''',
     '''      One tatami mat is not one fixed size &mdash; it varies by region and by building. Which one to use:
      <select id="tatamiSel">
        <option value="1.62">Advertising standard 1.62 m&sup2;</option>
        <option value="1.82405">Ky&#333;ma (Kansai) 1.824 m&sup2;</option>
        <option value="1.65620">Ch&#363;ky&#333;ma (Nagoya) 1.656 m&sup2;</option>
        <option value="1.54880">Edoma (Kant&#333;) 1.549 m&sup2;</option>
        <option value="1.44500">Danchima (housing blocks) 1.445 m&sup2;</option>
      </select>
      <br><span style="font-size:.95em">The &ldquo;advertising standard&rdquo; is the floor set by the Japanese real-estate advertising rules
      (one mat must be shown as 1.62 m&sup2; or more). The others are computed from real mat sizes:
      Ky&#333;ma 0.955&times;1.91 m, Ch&#363;ky&#333;ma 0.91&times;1.82 m, Edoma 0.88&times;1.76 m, Danchima 0.85&times;1.70 m.</span>'''),

    ('''      <label>有効数字:
        <select id="sig">
          <option value="4">4桁</option>
          <option value="6" selected>6桁</option>
          <option value="8">8桁</option>
          <option value="12">12桁</option>
          <option value="0">まるめない</option>
        </select>
      </label>
      <label><input type="checkbox" id="jpOnly"> 日本の単位だけ表示</label>
      <button class="mini" id="clear">消す</button>''',
     '''      <label>Significant figures:
        <select id="sig">
          <option value="4">4</option>
          <option value="6" selected>6</option>
          <option value="8">8</option>
          <option value="12">12</option>
          <option value="0">do not round</option>
        </select>
      </label>
      <label><input type="checkbox" id="jpOnly"> Japanese units only</label>
      <button class="mini" id="clear">Clear</button>'''),

    ('''          <th style="text-align:right">値</th>
          <th>単位</th>
          <th class="c-note">根拠・注意</th>''',
     '''          <th style="text-align:right">Value</th>
          <th>Unit</th>
          <th class="c-note">Basis and caveats</th>'''),

    ('''      <summary>この換算表の作り方（何を信じて計算しているか）</summary>
      <ul>
        <li><span class="badge def">定義</span> は、条約・法令・規格で <strong>その値ちょうど</strong> と決められている換算です。丸め誤差は計算上のものだけで、値そのものに不確かさはありません。（例：1インチ＝2.54cm、1尺＝10/33m、1匁＝3.75g）</li>
        <li><span class="badge apx">近似</span> は、条件によって変わるか、割り切れない値です。<strong>そのまま信じずに、注意書きを読んでください。</strong>（例：マッハは気温で変わる、1か月の長さは月ごとに違う、畳は地域で違う）</li>
        <li>計算はすべて「いったん基準単位に直してから、目的の単位へ直す」の2段階です。基準単位は各カテゴリの先頭に書いてあります。</li>
        <li>温度だけは倍率ではなくオフセットを含むので、専用の式で計算しています。燃費（km/L と L/100km）も比例ではなく反比例の関係です。</li>
      </ul>''',
     '''      <summary>How this table is built (what the numbers are trusted from)</summary>
      <ul>
        <li><span class="badge def">exact</span> means a treaty, a law or a standard fixes the conversion at <strong>that value exactly</strong>. The only error is the rounding you asked for; the value itself carries no uncertainty. (1 inch = 2.54 cm, 1 shaku = 10/33 m, 1 monme = 3.75 g.)</li>
        <li><span class="badge apx">approx.</span> means the value depends on conditions, or does not divide evenly. <strong>Read the note before trusting it.</strong> (Mach changes with air temperature, a month is not a fixed length, a tatami mat differs by region.)</li>
        <li>Every conversion goes through two steps: into the base unit, then out to the target unit. Each category names its base unit at the top.</li>
        <li>Temperature is the exception: it carries an offset rather than a plain factor, so it uses its own formulas. Fuel economy (km/L against L/100km) is inverse rather than proportional.</li>
      </ul>'''),

    ('''    数値は「3/8」「5 3/8」のような分数、「1,200」のようなカンマ区切り、全角の数字でも入力できます。
    <br>尺貫法の換算はメートル法移行時（1891年の度量衡法）の定義値にもとづいています
    （1尺＝10/33m、1貫＝3.75kg、1升＝2401/1331L）。坪・反・町はそこから導いた値です。
    <br>作: <strong>クロードの昼ラボ</strong>（AIのClaudeが書いています） — このページは通信を一切行いません。''',
     '''    Numbers can be written as fractions (&ldquo;3/8&rdquo;, &ldquo;5 3/8&rdquo;), with thousands separators (&ldquo;1,200&rdquo;),
    or in full-width digits.
    <br>The Japanese traditional units use the values fixed when Japan moved to the metric system
    (the Weights and Measures Act of 1891): 1 shaku = 10/33 m, 1 kan = 3.75 kg, 1 sh&#333; = 2401/1331 L.
    Tsubo, tan and ch&#333; are derived from those.
    <br>Made by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) &mdash; this page makes no network requests at all.'''),
]

TR = {
    # ============ 長さ ============
    "長さ": "Length",
    "メートル (m)": "Metre (m)",
    "基準はメートル。ヤード・ポンド法の値は1959年の国際協定で「ちょうどこの値」と決められています。":
        "The base unit is the metre. The imperial values were fixed as exact numbers by the "
        "international yard and pound agreement of 1959.",
    "ミリメートル": "millimetre",
    "センチメートル": "centimetre",
    "メートル": "metre",
    "キロメートル": "kilometre",
    "マイクロメートル": "micrometre",
    "ナノメートル": "nanometre",
    "インチ": "inch",
    "1959年の国際ヤード・ポンド協定でちょうど2.54cm。": "Exactly 2.54 cm under the 1959 agreement.",
    "フィート": "foot",
    "12インチ。ちょうど0.3048m。": "12 inches. Exactly 0.3048 m.",
    "ヤード": "yard",
    "3フィート。ちょうど0.9144m。": "3 feet. Exactly 0.9144 m.",
    "マイル": "mile",
    "1760ヤード。": "1,760 yards.",
    "海里": "nmi",
    "ノーティカルマイル": "nautical mile",
    "1929年にちょうど1852mと定められた国際海里。":
        "The international nautical mile, fixed at exactly 1,852 m in 1929.",
    "寸": "sun", "すん": "sun",
    "1尺の10分の1。": "One tenth of a shaku.",
    "尺": "shaku", "しゃく": "shaku",
    "1891年の度量衡法で「1メートルの33分の10」と定義。":
        "Defined by the Weights and Measures Act of 1891 as 10/33 of a metre.",
    "間": "ken", "けん": "ken",
    "6尺。畳の長辺と同じで、木造住宅の柱の間隔の基本。":
        "6 shaku. The long side of a tatami mat, and the standard pillar spacing in wooden houses.",
    "丈": "jō", "じょう": "jō",
    "10尺。": "10 shaku.",
    "町": "chō", "ちょう（長さ）": "chō",
    "60間＝360尺。面積の「町」とは別物です。":
        "60 ken = 360 shaku. Not the same as the chō of area.",
    "里": "ri", "り": "ri",
    "36町。約3.927km。「一里塚」の一里。":
        "36 chō, about 3.927 km. The ri of the old roadside milestones.",
    "天文単位": "astronomical unit",
    "2012年にちょうどこの値と定義。地球と太陽の距離の目安。":
        "Fixed at exactly this value in 2012. Roughly the Earth&#8211;Sun distance.",
    "光年": "ly", "こうねん": "light-year",
    "光がユリウス年（365.25日）で進む距離。定義値です。":
        "How far light travels in a Julian year (365.25 days). A defined value.",

    # ============ 重さ ============
    "重さ": "Mass",
    "キログラム (kg)": "Kilogram (kg)",
    "基準はキログラム。厳密には「重さ」ではなく「質量」です（体重計が測っているのはこちら）。":
        "The base unit is the kilogram. Strictly this is mass rather than weight "
        "(mass is what a bathroom scale is really reading).",
    "ミリグラム": "milligram",
    "グラム": "gram",
    "キログラム": "kilogram",
    "トン": "tonne",
    "メートルトン。": "The metric tonne.",
    "オンス": "ounce",
    "1ポンドの16分の1。": "One sixteenth of a pound.",
    "ポンド": "pound",
    "1959年の国際協定でちょうど0.45359237kg。":
        "Exactly 0.45359237 kg under the 1959 agreement.",
    "ストーン": "stone",
    "14ポンド。イギリスで体重に使われます。": "14 pounds. Used for body weight in the UK.",
    "カラット": "carat",
    "宝石用。ちょうど200mg。金の「K」（純度）とは別物です。":
        "For gemstones. Exactly 200 mg. Not the karat that measures gold purity.",
    "匁": "monme", "もんめ": "monme",
    "ちょうど3.75g。真珠の取引で今も世界的に使われています。":
        "Exactly 3.75 g. Still used worldwide in the pearl trade.",
    "貫": "kan", "かん": "kan",
    "1000匁。ちょうど3.75kg。": "1,000 monme. Exactly 3.75 kg.",
    "斤": "kin", "きん": "kin",
    "160匁＝600g。ただし食パンの「1斤」はこれではなく、340g以上と決められた別の単位です。":
        "160 monme = 600 g. The &ldquo;kin&rdquo; on a loaf of bread is a different unit: at least 340 g.",

    # ============ 面積 ============
    "面積": "Area",
    "平方メートル (㎡)": "Square metre (m&sup2;)",
    "基準は平方メートル。坪・畳・反は日本の不動産で今も現役です。":
        "The base unit is the square metre. Tsubo, tatami and tan are still in daily use "
        "in Japanese property listings.",
    "平方センチメートル": "square centimetre",
    "平方メートル": "square metre",
    "アール": "are",
    "ヘクタール": "hectare",
    "平方キロメートル": "square kilometre",
    "平方フィート": "square foot",
    "エーカー": "acre",
    "4840平方ヤード。": "4,840 square yards.",
    "平方マイル": "square mile",
    "坪": "tsubo", "つぼ": "tsubo",
    "1間四方＝(20/11)²㎡。約3.3058㎡。1歩（ぶ）も同じ広さです。":
        "One ken square = (20/11)&sup2; m&sup2;, about 3.3058 m&sup2;. The bu is the same area.",
    "畳": "jō",
    "★地域と建物で実際の広さが違います。既定は不動産広告の表示基準（1畳＝1.62㎡以上）。上のメニューで京間・中京間などに切り替えられます。":
        "&#9733; The real size differs by region and by building. The default is the "
        "advertising standard (one mat shown as 1.62 m&sup2; or more). The menu above switches "
        "to Ky&#333;ma, Ch&#363;ky&#333;ma and the others.",
    "畝": "se", "せ": "se",
    "30坪。約99.17㎡。": "30 tsubo, about 99.17 m&sup2;.",
    "反": "tan", "たん": "tan",
    "300坪。約991.7㎡。田畑の面積に使います。":
        "300 tsubo, about 991.7 m&sup2;. Used for fields and paddies.",
    "町歩": "chōbu", "ちょうぶ（面積）": "chōbu",
    "10反＝3000坪。約9917㎡。長さの「町」とは別です。":
        "10 tan = 3,000 tsubo, about 9,917 m&sup2;. Not the ch&#333; of length.",

    # ============ 体積 ============
    "体積": "Volume",
    "リットル (L)": "Litre (L)",
    "基準はリットル。料理の計量カップは日本と海外で量が違うので、両方入れています。":
        "The base unit is the litre. A cooking cup is not the same size in Japan and abroad, "
        "so both are listed.",
    "ミリリットル": "millilitre",
    "1c㎥と同じ。": "The same as 1 cm&sup3;.",
    "リットル": "litre",
    "立方メートル": "cubic metre",
    "水道やガスの検針票の単位。": "The unit on water and gas bills.",
    "立方センチメートル": "cubic centimetre",
    "ccと同じ。": "The same as cc.",
    "小さじ": "tsp (JP)", "こさじ（日本）": "Japanese teaspoon",
    "日本の計量スプーンは5mL。": "A Japanese measuring teaspoon is 5 mL.",
    "大さじ": "tbsp (JP)", "おおさじ（日本）": "Japanese tablespoon",
    "日本の計量スプーンは15mL。": "A Japanese measuring tablespoon is 15 mL.",
    "カップ": "cup (JP)", "計量カップ（日本）": "Japanese measuring cup",
    "日本は200mL。米用の「1合カップ」は180mLで別物です。":
        "200 mL in Japan. The rice cup that comes with a rice cooker is 180 mL, a different thing.",
    "カップ（米）": "cup (US)",
    "アメリカのレシピはこちら。日本の200mLより多いので注意。":
        "What American recipes mean. Larger than the Japanese 200 mL.",
    "液量オンス（米）": "fluid ounce (US)",
    "ガロン（米）": "gallon (US)",
    "ガロン（英）": "gallon (UK)",
    "米ガロンとは2割ほど違います。": "About 20% away from the US gallon.",
    "石油バレル": "oil barrel",
    "42米ガロン。原油価格のニュースの単位。":
        "42 US gallons. The unit crude oil prices are quoted in.",
    "勺": "shaku",
    "1合の10分の1。": "One tenth of a g&#333;.",
    "合": "gō", "ごう": "gō",
    "1升の10分の1。約180.39mL。炊飯器の「1合」。":
        "One tenth of a sh&#333;, about 180.39 mL. The cup a rice cooker measures in.",
    "升": "shō", "しょう": "shō",
    "度量衡法の定義は「1立方メートルの2401/1331000」。約1.8039L。一升瓶。":
        "Defined by the Weights and Measures Act as 2401/1331000 of a cubic metre, about 1.8039 L. "
        "The size of a sake bottle.",
    "斗": "to", "と": "to",
    "10升。約18.04L。一斗缶。": "10 sh&#333;, about 18.04 L. The size of a square metal can.",
    "石": "koku", "こく": "koku",
    "10斗。約180.4L。「加賀百万石」の石。":
        "10 to, about 180.4 L. The koku that old domains were once measured in.",

    # ============ 温度 ============
    "温度": "Temperature",
    "ケルビン (K)": "Kelvin (K)",
    "温度だけは倍率では換算できません（0の位置が単位ごとに違うため）。専用の式で計算しています。":
        "Temperature is the one thing a plain factor cannot convert, because zero sits in a "
        "different place in each scale. It uses its own formulas.",
    "摂氏": "Celsius",
    "水の融点が0、沸点がほぼ100。": "Water melts at 0 and boils at about 100.",
    "華氏": "Fahrenheit",
    "アメリカの天気予報の単位。0℉は寒剤で作れる下限あたり。":
        "The unit of American weather forecasts. 0 &deg;F is roughly the coldest a salt-and-ice "
        "mixture reaches.",
    "ケルビン": "kelvin",
    "絶対温度。0Kは-273.15℃。": "Absolute temperature. 0 K is &minus;273.15 &deg;C.",
    "ランキン度": "degree Rankine",
    "華氏を絶対温度にしたもの。工学で使われます。":
        "Fahrenheit measured from absolute zero. Used in engineering.",

    # ============ 速さ ============
    "速さ": "Speed",
    "メートル毎秒 (m/s)": "Metre per second (m/s)",
    "メートル毎秒": "metre per second",
    "キロメートル毎時": "kilometre per hour",
    "マイル毎時": "mile per hour",
    "フィート毎秒": "foot per second",
    "ノット": "knot",
    "1時間に1海里。船と飛行機の速度。":
        "One nautical mile per hour. How ships and aircraft state their speed.",
    "マッハ": "Mach", "音速の何倍か": "multiples of the speed of sound",
    "★音速は温度で変わります。ここでは海面・15℃の標準大気での340.29m/s。上空では300m/s前後まで下がります。":
        "&#9733; The speed of sound changes with temperature. This uses 340.29 m/s, the standard "
        "atmosphere at sea level and 15 &deg;C. High up it falls to around 300 m/s.",

    # ============ 時間 ============
    "時間": "hour",
    "秒 (s)": "Second (s)",
    "ミリ秒": "millisecond",
    "秒": "second",
    "分": "minute",
    "日": "day",
    "ちょうど86400秒として計算（うるう秒は考えません）。":
        "Taken as exactly 86,400 seconds (leap seconds are not considered).",
    "週": "week",
    "月": "month", "か月": "months",
    "★月ごとに長さが違います。ここではグレゴリオ暦の平均（30.436875日）。":
        "&#9733; Months are not all the same length. This uses the Gregorian average, 30.436875 days.",
    "年": "year",
    "★グレゴリオ暦の平均（365.2425日）。うるう年を4年に1回とする「ユリウス年」は365.25日で少し違います。":
        "&#9733; The Gregorian average, 365.2425 days. The Julian year, which leaps every fourth "
        "year without exception, is 365.25 days &mdash; slightly different.",

    # ============ データ量 ============
    "データ量": "Data size",
    "バイト (B)": "Byte (B)",
    "★「1KB＝1024B」と「1KB＝1000B」は違います。ここでは規格どおり、1000倍系を KB/MB、1024倍系を KiB/MiB として分けています。Windowsが「KB」と表示している値は、実際には KiB（1024倍系）です。":
        "&#9733; &ldquo;1 KB = 1024 B&rdquo; and &ldquo;1 KB = 1000 B&rdquo; are not the same claim. "
        "This table follows the standard: powers of 1000 are KB/MB, powers of 1024 are KiB/MiB. "
        "What Windows labels &ldquo;KB&rdquo; is really KiB.",
    "ビット": "bit",
    "バイト": "byte",
    "キロバイト（1000倍）": "kilobyte (&times;1000)",
    "メガバイト（1000倍）": "megabyte (&times;1000)",
    "ギガバイト（1000倍）": "gigabyte (&times;1000)",
    "テラバイト（1000倍）": "terabyte (&times;1000)",
    "キビバイト（1024倍）": "kibibyte (&times;1024)",
    "Windowsの「KB」表示はこちら。": "This is what Windows shows as &ldquo;KB&rdquo;.",
    "メビバイト（1024倍）": "mebibyte (&times;1024)",
    "ギビバイト（1024倍）": "gibibyte (&times;1024)",
    "スマホの「64GB」は1000倍系なので、実際に使える表示容量はこれより小さく見えます。":
        "The &ldquo;64 GB&rdquo; on a phone is the powers-of-1000 kind, so the capacity the "
        "phone reports back looks smaller than that.",
    "テビバイト（1024倍）": "tebibyte (&times;1024)",

    # ============ 圧力 ============
    "圧力": "Pressure",
    "パスカル (Pa)": "Pascal (Pa)",
    "パスカル": "pascal",
    "ヘクトパスカル": "hectopascal",
    "天気図の単位。": "The unit on weather maps.",
    "キロパスカル": "kilopascal",
    "メガパスカル": "megapascal",
    "バール": "bar",
    "気圧": "atmosphere",
    "標準大気圧。ちょうど101325Pa と定義されています。":
        "Standard atmospheric pressure, defined as exactly 101,325 Pa.",
    "水銀柱ミリメートル": "millimetre of mercury",
    "Torr と同じ。血圧の単位。": "The same as the torr. The unit of blood pressure.",
    "重量ポンド毎平方インチ": "pound-force per square inch",
    "タイヤの空気圧。日本のスタンドは kPa 表示のことが多い。":
        "Tyre pressure. Japanese filling stations usually show kPa instead.",

    # ============ エネルギー ============
    "エネルギー": "Energy",
    "ジュール (J)": "Joule (J)",
    "ジュール": "joule",
    "キロジュール": "kilojoule",
    "海外の食品表示。": "What food labels outside Japan use.",
    "カロリー": "calorie",
    "熱化学カロリー。ちょうど4.184J。": "The thermochemical calorie. Exactly 4.184 J.",
    "キロカロリー": "kilocalorie",
    "食品表示の「カロリー」は、ふつうこちら（kcal）です。":
        "The &ldquo;calories&rdquo; on a food label are normally these (kcal).",
    "ワット時": "watt hour",
    "キロワット時": "kilowatt hour",
    "電気の検針票の単位。": "The unit on an electricity bill.",
    "英熱量": "British thermal unit",
    "エアコンの能力表示（海外）。": "How air conditioners are rated outside Japan.",
    "電子ボルト": "electronvolt",
    "2019年のSI改定で定義値になりました。":
        "Became a defined value with the 2019 revision of the SI.",

    # ============ 角度 ============
    "角度": "Angle",
    "度 (°)": "Degree (&deg;)",
    "度": "degree",
    "ラジアン": "radian",
    "円周率が入るので、10進の小数では割り切れません。":
        "It carries pi, so it never comes out even in decimal.",
    "分（角度）": "arcminute",
    "秒（角度）": "arcsecond",
    "グラード": "gradian",
    "直角を100とする単位。": "A right angle is 100 of these.",
    "回転": "turn",
    "勾配（％）": "grade (%)",
    "道路標識の坂の表示。100%＝45°です（90°ではありません）。★-90°より小さい／90°より大きい角度は坂として表せないので「—」と表示します（垂直の壁の勾配は無限大になるため）。":
        "How road signs state a slope. 100% is 45&deg;, not 90&deg;. &#9733; Angles below "
        "&minus;90&deg; or above 90&deg; cannot be written as a slope at all, so they show as "
        "&mdash; (a vertical wall would be an infinite grade).",

    # ============ 燃費 ============
    "燃費": "Fuel economy",
    "リットル毎100km (L/100km)": "Litres per 100 km (L/100km)",
    "★燃費は比例ではなく反比例の関係です。「km/L が2倍」は「L/100km が半分」になります。0を入れると無限大になるので計算できません。":
        "&#9733; Fuel economy is inverse, not proportional: twice the km/L is half the L/100km. "
        "A zero would mean infinity, so it cannot be converted.",
    "キロメートル毎リットル": "kilometre per litre",
    "日本のカタログ燃費。": "How Japanese brochures state fuel economy.",
    "リットル毎100キロ": "litres per 100 kilometres",
    "ヨーロッパ式。数字が小さいほど良い燃費。":
        "The European way round: the smaller the number, the better.",
    "マイル毎ガロン（米）": "miles per gallon (US)",
    "マイル毎ガロン（英）": "miles per gallon (UK)",
    "英ガロンは米ガロンより大きいので、同じ車でも数字が大きく出ます。":
        "The UK gallon is larger, so the same car scores a bigger number.",

    # ============ 画面の文言 ============
    "数値を入力してください。": "Enter a number.",
    "分母に0は使えません。": "The denominator cannot be 0.",
    # ⚠ 前置きと後置きに割れている: '「' + 入力 + '」を数値として…'
    "「": "“",
    "」を数値として読めませんでした。1.5 / 3/8 / 5 3/8 / 1,200 のような形で入力してください。":
        "” could not be read as a number. Try a form like 1.5 / 3/8 / 5 3/8 / 1,200.",
    "基準単位: ": "Base unit: ",
    "定義": "exact",
    "近似": "approx.",
    "コピー": "Copy",
    "コピーしました: ": "Copied: ",
    "コピーできませんでした": "Could not copy",
    # ⚠ 後置きだけ: fmt(v) + ' ' + u.s + ' を基準にしました'
    " を基準にしました": " is now the base",
}

KEEP = set()


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "unit" / "index.html"
    en_path = docs / "en" / "unit.html"
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
        docs, "json.html", "JSON Formatter &amp; Validator",
        "unit.html", "../unit/") + en[nav.end():]

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
