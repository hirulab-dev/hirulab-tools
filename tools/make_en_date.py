#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日付計算機( docs/date/ )の英語版を、日本語版から作る(2026-09-02 昼)。

`make_en_railroad.py` 以降と同じ方式。**日本語版が唯一の原本**で、手で両方を直すことはしない。

★この道具は **25本のうち唯一「日本語版はあるのに英語版が無い」** ページだった
  (道具そのものが英語版ゼロになったのは 9/2 朝。そこから漏れていた1本)。

★英語版の中身は「日本語版の言葉を置き換えたもの」ではなく、**そのまま日本のカレンダー道具**。
  営業日は日本の祝日で数え、和暦(令和・平成…)を変換し、日本の学年を出す。
  英語で探している人(日本で働いている人・日本の日付を扱う開発者)に、
  日本のカレンダーをそのまま渡すのが役目。だから祝日の名前は**内閣府の英語表記**に寄せる。

★このページのために日本語版を3か所いじった(いずれも日本語の表示は1文字も変わらない):
  1. **月の名前を表(MN)にした**。`${dt.getMonth()+1}月` と直に書くと、日英でコードを
     バイト単位で一致させる縛りのせいで英語の語順にできない(`${…}` の並びは動かせない)。
  2. **カードに `data-k`(言葉でない名札)を足した**。検証がラベルの文字でカードを引いていて、
     そのままでは英語版に同じ検証を当てられなかった(url/headers/jwt の `data-code` と同じ手)。
  3. **`値 + "日"` の形をテンプレートに畳んだ**。文字列 "日" は**曜日の「日」(Sunday)**でもあり、
     訳の表は中身で引くので、両方が同じ鍵になって衝突する(jwt の「ヘッダ」で踏んだ型)。
     `${days.toLocaleString()}日` の形にすると中の式が違うぶん鍵が分かれる。

★単位は英語ではラベル側に置く(値は数だけ)。理由: 日英でコードを1バイトも変えられないので
  `${n}${n===1?" day":" days"}` のような単複の分岐を英語だけに書けない。
  「Days: 1」なら単複の問題が起きない(9/2未明の regex-tester と同じ逃げ方)。

1. HTML(head・本文・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = 祝日の規則・営業日の数え方・和暦・学年の計算は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

使い方: python lab/scripts/make_en_date.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (JA_CHARS, code_japanese, comments,  # noqa: E402
                       translate_comments, script_span,
                       translate_literals)

BASE = "https://hirulab-dev.github.io/hirulab-tools"

EN_TITLE = ("Japanese Date Calculator — business days, Japanese holidays, "
            "wareki (era) converter")
EN_DESC = ("Measure the span between two dates in Japanese business days, add or subtract days, "
           "months and business days, work out age and the Japanese school year, and convert "
           "between Western years and Japanese eras (Reiwa, Heisei, Showa, Taisho, Meiji). "
           "Holidays are computed under the law as it stood in each year, 1949 to 2099. "
           "Runs entirely in your browser; nothing is sent anywhere.")
EN_SHORT = ("Spans, business days, age and school year, and Western ⇄ Japanese era conversion. "
            "Japanese holidays are computed under the law of that year, not today&#39;s.")

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>日付計算機 — 期間・営業日・年齢・和暦</title>',
     '<title>%s</title>' % EN_TITLE),

    ('<meta name="description" content="2つの日付の期間、営業日を数えた日数計算、満年齢と学年、'
     '西暦と和暦の相互変換をまとめて。日本の祝日(振替休日・国民の休日・春分秋分)を自動計算します。'
     'AI(Claude)が作ったブラウザ完結ツール。データは送信されません。">',
     '<meta name="description" content="%s">' % EN_DESC),

    ('<link rel="canonical" href="%s/date/">\n'
     '<link rel="alternate" hreflang="ja" href="%s/date/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/date.html">' % (BASE, BASE, BASE),
     '<link rel="canonical" href="%s/en/date.html">\n'
     '<link rel="alternate" hreflang="ja" href="%s/date/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/date.html">' % (BASE, BASE, BASE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n'
     '<meta property="og:locale" content="ja_JP">\n'
     '<meta property="og:title" content="日付計算機 — クロードの昼ラボ">\n'
     '<meta property="og:description" content="期間・営業日・満年齢・学年・和暦をまとめて計算。'
     '日本の祝日に自動対応。">\n'
     '<meta property="og:url" content="%s/date/">\n'
     '<meta property="og:image" content="%s/ogp/ogp-date.png">' % (BASE, BASE),
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">\n'
     '<meta property="og:title" content="Japanese Date Calculator — Claude&#39;s Daytime Lab">\n'
     '<meta property="og:description" content="%s">\n'
     '<meta property="og:url" content="%s/en/date.html">\n'
     '<meta property="og:image" content="%s/ogp/ogp-date-en.png">' % (EN_SHORT, BASE, BASE)),

    ('<meta name="twitter:title" content="日付計算機 — クロードの昼ラボ">\n'
     '<meta name="twitter:description" content="期間・営業日・満年齢・学年・和暦をまとめて計算。'
     '日本の祝日に自動対応。">\n'
     '<meta name="twitter:image" content="%s/ogp/ogp-date.png">' % BASE,
     '<meta name="twitter:title" content="Japanese Date Calculator — Claude&#39;s Daytime Lab">\n'
     '<meta name="twitter:description" content="Spans, business days, age, school year and '
     'Western ⇄ Japanese era conversion, with Japanese holidays computed per year.">\n'
     '<meta name="twitter:image" content="%s/ogp/ogp-date-en.png">' % BASE),

    ('  "name": "日付計算機",\n'
     '  "url": "%s/date/",\n'
     '  "description": "期間・営業日・満年齢・学年・和暦をまとめて計算します。日本の祝日に自動対応。",\n'
     '  "applicationCategory": "UtilitiesApplication",\n'
     '  "operatingSystem": "Web browser",\n'
     '  "browserRequirements": "JavaScript が有効なモダンブラウザ",\n'
     '  "inLanguage": "ja",' % BASE,
     '  "name": "Japanese Date Calculator",\n'
     '  "url": "%s/en/date.html",\n'
     '  "description": "Measures the span between two dates in days, weeks and Japanese business '
     'days, adds and subtracts days, months, years and business days, works out full age, '
     'traditional kazoe age and the Japanese school year, and converts between Western years and '
     'Japanese eras. Japanese public holidays are computed under the law as it stood in each year '
     "from 1949 to 2099, including substitute holidays, citizens' holidays, the equinoxes and "
     'the one-off holidays. Everything runs in the browser and no date you enter is sent '
     'anywhere.",\n'
     '  "applicationCategory": "UtilitiesApplication",\n'
     '  "operatingSystem": "Web browser",\n'
     '  "browserRequirements": "A modern browser with JavaScript enabled",\n'
     '  "inLanguage": "en",' % BASE),

    ('"priceCurrency": "JPY"', '"priceCurrency": "USD"'),

    ('  "image": "%s/ogp/ogp-date.png",\n'
     '  "author": {\n'
     '    "@type": "Organization",\n'
     '    "name": "クロードの昼ラボ",\n'
     '    "url": "https://note.com/hirulab"\n'
     '  },\n'
     '  "isPartOf": {\n'
     '    "@type": "WebSite",\n'
     '    "name": "クロードの昼ラボ — ツール置き場",\n'
     '    "url": "%s/"\n'
     '  }' % (BASE, BASE),
     # ⚠ JSON-LD は <script> の中の**生テキスト**なので、`&#39;` は復号されない
     #    (HTMLの属性と違う)。読み手にはそのまま "Claude&#39;s" と渡ってしまうので、
     #    ここは素のアポストロフィで書く。JSON としては何の問題も無い。
     '  "image": "%s/ogp/ogp-date-en.png",\n'
     '  "author": {\n'
     '    "@type": "Organization",\n'
     '    "name": "Claude\'s Daytime Lab",\n'
     '    "url": "https://note.com/hirulab"\n'
     '  },\n'
     '  "isPartOf": {\n'
     '    "@type": "WebSite",\n'
     '    "name": "Claude\'s Daytime Lab — Tools",\n'
     '    "url": "%s/en/"\n'
     '  }' % (BASE, BASE)),

    # `.hl-back` の規則はこのページの CSS にある(pattern と違い、日本語版が持っている)ので
    # 戻り導線を置いてよい。無いページに足すと既定の青リンクになり AA を落とす(9/2 朝の教訓)。
    ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>\n'
     '  <h1>日付計算機</h1>\n'
     '  <div class="tagline">期間・営業日・年齢・和暦をまとめて計算します。'
     '日本の祝日は<b>その年の規則で</b>出します(1949年からの法改正・五輪の移動・'
     '一日限りの休日まで)。すべてブラウザ内で完結し、入力した日付はどこにも送信されません。</div>',
     '  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab tools</a>\n'
     '  <h1>Japanese Date Calculator</h1>\n'
     '  <div class="tagline">Spans, business days, age and Japanese era conversion in one place. '
     'Japanese public holidays are computed <b>under the law as it stood in that year</b> — every '
     'amendment since 1949, the days the Olympics moved, and the one-off holidays. Everything runs '
     'inside your browser; no date you enter is sent anywhere.</div>'),

    ('    <button role="tab" id="tab-diff"  aria-selected="true"  aria-controls="s-diff">期間を測る</button>\n'
     '    <button role="tab" id="tab-add"   aria-selected="false" aria-controls="s-add">日数を足す・引く</button>\n'
     '    <button role="tab" id="tab-age"   aria-selected="false" aria-controls="s-age">年齢・学年</button>\n'
     '    <button role="tab" id="tab-wareki" aria-selected="false" aria-controls="s-wareki">西暦 ⇄ 和暦</button>\n'
     '    <button role="tab" id="tab-hol"   aria-selected="false" aria-controls="s-hol">祝日一覧</button>',
     '    <button role="tab" id="tab-diff"  aria-selected="true"  aria-controls="s-diff">Span between dates</button>\n'
     '    <button role="tab" id="tab-add"   aria-selected="false" aria-controls="s-add">Add or subtract</button>\n'
     '    <button role="tab" id="tab-age"   aria-selected="false" aria-controls="s-age">Age and school year</button>\n'
     '    <button role="tab" id="tab-wareki" aria-selected="false" aria-controls="s-wareki">Western ⇄ Japanese era</button>\n'
     '    <button role="tab" id="tab-hol"   aria-selected="false" aria-controls="s-hol">Holidays</button>'),

    ('  <!-- ===== 期間 ===== -->', '  <!-- ===== span ===== -->'),
    ('        <div class="label">開始日</div><input type="date" id="d-from">',
     '        <div class="label">Start date</div><input type="date" id="d-from">'),
    ('        <div class="label">終了日</div><input type="date" id="d-to">',
     '        <div class="label">End date</div><input type="date" id="d-to">'),
    ('      <button class="go" id="d-today">今日→今日</button>',
     '      <button class="go" id="d-today">Today → today</button>'),
    ('<input type="checkbox" id="d-incl"> 終了日を含めて数える(初日算入)</label>',
     '<input type="checkbox" id="d-incl"> Count the end date as well (inclusive)</label>'),

    ('  <!-- ===== 加減算 ===== -->', '  <!-- ===== add / subtract ===== -->'),
    ('        <div class="label">基準日</div><input type="date" id="a-base">',
     '        <div class="label">Base date</div><input type="date" id="a-base">'),
    ('        <div class="label">増減</div>', '        <div class="label">Change by</div>'),
    ('            <option value="day">日</option>\n'
     '            <option value="biz">営業日(土日祝を除く)</option>\n'
     '            <option value="week">週</option>\n'
     '            <option value="month">か月</option>\n'
     '            <option value="year">年</option>',
     '            <option value="day">days</option>\n'
     '            <option value="biz">business days (no weekends or holidays)</option>\n'
     '            <option value="week">weeks</option>\n'
     '            <option value="month">months</option>\n'
     '            <option value="year">years</option>'),
    ('    <div class="hint">「か月」「年」の加算で存在しない日(1/31の1か月後など)になる場合は、'
     'その月の末日に丸めます(民法の期間計算と同じ扱い)。</div>',
     '    <div class="hint">When adding months or years lands on a date that does not exist — one '
     'month after 31 January, say — the result is clamped to the last day of that month, which is '
     'how the Japanese Civil Code counts periods.</div>'),

    ('  <!-- ===== 年齢 ===== -->', '  <!-- ===== age ===== -->'),
    ('        <div class="label">生年月日</div><input type="date" id="g-birth">',
     '        <div class="label">Date of birth</div><input type="date" id="g-birth">'),
    ('        <div class="label">基準日(既定は今日)</div><input type="date" id="g-at">',
     '        <div class="label">As of (today by default)</div><input type="date" id="g-at">'),
    ('    <div class="hint">学年は「4月2日〜翌年4月1日生まれが同学年」という日本の区切り'
     '(年齢は誕生日の前日に加算される、という法の扱いによる)で計算しています。</div>',
     '    <div class="hint">School years in Japan group everyone born from 2 April to 1 April of '
     'the following year. The 1 April boundary comes from the legal rule that a person turns a year '
     'older on the day before their birthday.</div>'),

    ('  <!-- ===== 和暦 ===== -->', '  <!-- ===== era ===== -->'),
    ('      <div class="label">西暦の日付</div><input type="date" id="w-date">',
     '      <div class="label">Western (Gregorian) date</div><input type="date" id="w-date">'),
    ('      <div class="label">和暦から西暦へ</div>',
     '      <div class="label">Japanese era → Western</div>'),
    ('          <option value="令和">令和</option><option value="平成">平成</option>\n'
     '          <option value="昭和">昭和</option><option value="大正">大正</option>'
     '<option value="明治">明治</option>',
     '          <option value="Reiwa">Reiwa</option><option value="Heisei">Heisei</option>\n'
     '          <option value="Showa">Showa</option><option value="Taisho">Taisho</option>'
     '<option value="Meiji">Meiji</option>'),
    ('        <input type="number" id="w-y" value="8" min="1" style="width:80px"> 年\n'
     '        <input type="number" id="w-m" value="8" min="1" max="12" style="width:70px"> 月\n'
     '        <input type="number" id="w-d" value="16" min="1" max="31" style="width:70px"> 日',
     '        <input type="number" id="w-y" value="8" min="1" style="width:80px"> year\n'
     '        <input type="number" id="w-m" value="8" min="1" max="12" style="width:70px"> month\n'
     '        <input type="number" id="w-d" value="16" min="1" max="31" style="width:70px"> day'),

    ('  <!-- ===== 祝日 ===== -->', '  <!-- ===== holidays ===== -->'),
    ('        <div class="label">年</div><input type="number" id="h-year" value="2026" min="1949" max="2099" style="width:110px">',
     '        <div class="label">Year</div><input type="number" id="h-year" value="2026" min="1949" max="2099" style="width:110px">'),
    ('      <span class="hint" style="margin:0">1949年〜2099年に対応</span>',
     '      <span class="hint" style="margin:0">Supported range: 1949 to 2099</span>'),

    ('      <b>その年の規則で計算します。</b>祝日は何度も法律が変わっているので、'
     'いまの規則を昔の年に当てると違う日が出ます。\n'
     '      成人の日は1999年まで1月15日、天皇誕生日は平成のあいだ12月23日、海の日は1995年まで無く、\n'
     '      体育の日は1999年まで10月10日でした。2020・2021年は五輪で海の日・山の日・'
     'スポーツの日が動いています。\n'
     '      振替休日は1973年4月12日から、国民の休日は1986年から。'
     '一日限りの休日(即位の礼など)も6つ入れてあります。\n'
     '      <b>ここは期間タブの「営業日」の数にも効きます。</b>',
     '      <b>Computed under the law of that year.</b> The Holidays Act has been amended many '
     'times, so applying today&#39;s rules to an older year gives the wrong dates.\n'
     '      Coming of Age Day was 15 January until 1999; the Emperor&#39;s Birthday was 23 December '
     'throughout the Heisei era; Marine Day did not exist before 1996;\n'
     '      Health and Sports Day was 10 October until 1999. In 2020 and 2021 the Olympics moved '
     'Marine Day, Mountain Day and Sports Day.\n'
     '      Substitute holidays start on 12 April 1973 and citizens&#39; holidays in 1986. The six '
     'one-off holidays (enthronement ceremonies and the like) are included.\n'
     '      <b>All of this also feeds the business-day count on the first tab.</b>'),

    ('  <footer>\n'
     '    祝日は現行(2026年時点)の国民の祝日に関する法律にもとづいて計算しています。'
     '<strong>過去の年について当時の法律との差が出る場合があります</strong>'
     '(ハッピーマンデー導入前、天皇誕生日の移動、オリンピック特措法による移動など)。\n'
     '    春分・秋分の日は 1980〜2099 年で有効な近似式によるもので、'
     '公式には前年2月の官報で確定します。重要な予定は必ず公式の暦で確認してください。\n'
     '    <br>作: <strong>クロードの昼ラボ</strong>(AIのClaudeが書いています) — '
     'このページは通信を一切行いません。\n'
     '  </footer>',
     '  <footer>\n'
     '    Holidays follow the Act on National Holidays as amended over time, so each year is '
     'computed under the rules in force that year. <strong>Verify anything that matters against an '
     'official calendar.</strong>\n'
     '    The vernal and autumnal equinox dates come from the approximation valid for 1980–2099; '
     'officially each year is fixed by the government gazette in February of the preceding year.\n'
     '    <br>Made by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) — this '
     'page makes no network requests at all.\n'
     '  </footer>'),
]

# ── スクリプトの中の文字列リテラル ────────────────────────────────
#
# ⚠ 訳の表は**文字列の中身で引く**ので、同じ日本語は必ず同じ英語になる。
#    逆に、**別の意味で同じ日本語を使っていると衝突する**(このページの "日" が
#    「日数の単位」と「日曜」の両方だった)。原本側で鍵が分かれるように直してある。
# JS のコメント(2026-09-03 昼 追加)。それまで**訳していなかった**ので、
# 英語ページのソースに日本語の注釈が71行そのまま載っていた(4ページ中いちばん多い)。
# ⚠ 訳は行数を変えないこと(日英のコード突き合わせが行単位のため)
COMMENTS = {
    '''/* 月の名前。日本語では「9月」、英語では「Sep」。
   ★英語版のために表にした(2026-09-02)。日本語の表示は前と1文字も変わらない。
   直に `${dt.getMonth()+1}月` と書くと、英語版で語順を変えられない
   (日英でコードをバイト単位で一致させる縛りがあり、`${…}` の並びは動かせないため)。 */''':
    '''/* Month names. Japanese writes the number then a suffix ("9-gatsu"); English writes "Sep".
   ★Turned into a table for the English version (2026-09-02). The Japanese output is unchanged.
   Writing the number and its suffix inline would leave no way to reorder the words in English
   (the two pages must match byte for byte, so the order of `${…}` cannot move). */''',

    '/* ---------- 日付ユーティリティ(すべてローカル時刻の 0:00 で扱う) ---------- */':
    '/* ---------- Date helpers (everything is local time at 00:00) ---------- */',

    '// 存在しない日は末日に丸める': '// a date that does not exist rounds down to the last day of the month',

    '/* ---------- 日本の祝日 ---------- */': '/* ---------- Japanese public holidays ---------- */',

    '// 最初の月曜までの日数': '// days until the first Monday',

    '''/* 春分・秋分は「その年の何日か」を近似式で出す。★1980年の前後で定数が違う
   (2026-09-01 まではあとの式だけを全部の年に当てていて、1979年以前が1日ずれていた)。
   Math.trunc であって Math.floor ではない: 負の年差で 0 のほうに丸める式なので、
   floor にすると 1979年以前がまた1日ずれる。 */''':
    '''/* The equinoxes are approximated as "which day of that month". ★The constants differ
   before and after 1980 (until 2026-09-01 only the later formula was used for every year,
   so anything before 1979 was a day out). This is Math.trunc, not Math.floor: the formula
   rounds toward zero for negative year offsets, and floor puts pre-1979 back off by a day. */''',

    '/* 一日限りの休日(その日のためだけに法律が作られたもの) */':
    '/* One-off holidays (a law was passed for that single day) */',

    '''/** その年の祝日を {キー: 名称} で返す(振替休日・国民の休日を含む)
 *
 * ★2026-09-01: それまで**いまの規則を1949年から2099年まで全部の年に当てていた**。
 *   画面は1949年から受け付けるので、1949〜2021年の73年ぶんが黙って間違っていた
 *   (成人の日は1999年まで1月15日、天皇誕生日は平成のあいだ12月23日、
 *    海の日は1995年まで無く、2020・2021年は五輪で動いた、など)。
 *   祝日は期間の「営業日」の数にも効くので、間違いは日数計算にも回っていた。
 *   → 改正の年で切り替える形に直した。
 *
 * ⚠ 2つだけ、よく使われている参照実装(Python の jpholiday)と食い違う。
 *   どちらもこちらが法律どおりで、向こうが**規則を過去にさかのぼって当てている**:
 *   - 国民の休日は昭和60年法律第103号(1985-12-27施行)なので、**最初は1986年5月4日**。
 *     jpholiday は1949年からの5月4日を全部そう呼ぶ(31日ぶん)
 *   - 振替休日は昭和48年法律第10号(1973-04-12施行)なので、**最初は1973年4月30日**。
 *     jpholiday は同じ年の2月12日も振替休日にする
 *   この2つを除けば1949〜2099年の151年ぶんが完全に一致する(`test_date.py` で毎回確かめている)。
 */''':
    '''/** Holidays for one year as {key: name} (substitute and citizens' holidays included)
 *
 * ★2026-09-01: this used to **apply today's rules to every year from 1949 to 2099**.
 *   The page accepts dates from 1949, so 73 years (1949-2021) were quietly wrong
 *   (Coming of Age Day was 15 January until 1999, the Emperor's Birthday was 23 December
 *    through Heisei, Marine Day did not exist before 1996, and 2020-2021 moved for the
 *    Olympics). Holidays also feed the working-day counts, so the error spread there too.
 *   → Rules now switch at the year each amendment took effect.
 *
 * ⚠ Two cases disagree with the usual reference implementation (Python's jpholiday).
 *   In both, this page follows the statute and jpholiday **applies it retroactively**:
 *   - Citizens' holidays come from Act No. 103 of 1985 (in force 1985-12-27), so the
 *     **first one is 4 May 1986**. jpholiday calls every 4 May from 1949 one (31 days).
 *   - Substitute holidays come from Act No. 10 of 1973 (in force 1973-04-12), so the
 *     **first one is 30 April 1973**. jpholiday also marks 12 February of that year.
 *   Apart from those two, all 151 years 1949-2099 match exactly (`test_date.py` checks).
 */''',

    '// [Date, 名称]': '// [Date, name]',
    '// 2000年からハッピーマンデー': '// moved to a Monday from 2000 (the "Happy Monday" amendment)',
    '// 昭和': '// Showa',
    '// 平成': '// Heisei',
    '// 令和(2019年は無い)': '// Reiwa (not in 2019)',
    '// 4月29日だった時期': '// the years when it fell on 29 April',
    '// 東京五輪で移動': '// moved for the Tokyo Olympics',
    '// 新設時は7月20日': '// 20 July when it was first introduced',
    '// 振替休日(1973-04-12 施行。最初に効いたのは同年4月30日)':
    '// substitute holidays (in force 1973-04-12; the first one was 30 April that year)',
    '// 2007年からは「その日より後の、いちばん近い祝日でない日」。それより前は「翌日」だけ。':
    '// from 2007 it is "the nearest later day that is not a holiday"; before that, just "the next day".',
    '// 国民の休日: 祝日に挟まれた日(1985-12-27 施行。最初に効いたのは1986年5月4日)':
    "// citizens' holiday: a day sandwiched between two holidays (in force 1985-12-27; first 1986-05-04)",

    '/* ---------- 和暦 ---------- */': '/* ---------- Japanese era years ---------- */',
    '/* ---------- 出力の組み立て ---------- */': '/* ---------- Building the output ---------- */',

    '''/* 第1引数の k は**言葉ではない名札**。画面には出ないが、検証がカードを引くときに使う。
   ラベルの文字で引くと、英語版に同じ検証を当てられない(2026-09-02。
   url・headers・jwt の data-code、正規表現テスタの data-kind と同じ手)。 */''':
    '''/* The first argument k is a **tag, not words**. It never appears on screen; the tests use
   it to find a card. Looking cards up by their label would make the same tests impossible
   to run against the English page (2026-09-02; same trick as data-code and data-kind). */''',

    '/* ---------- タブ ---------- */': '/* ---------- Tabs ---------- */',
    '/* ---------- 1. 期間 ---------- */': '/* ---------- 1. Between two dates ---------- */',

    '''/* 年月日の内訳。★2026-09-01 是正: 前は「終了日の前の月の日数を借りて引く」形だったが、
     **月末から数え始めたときに、この道具自身の加減算タブと答えが合わなかった**。
     例: 2008-10-31 → 2009-12-23 を「1年1か月22日」と出すが、
     加減算タブで 2008-10-31 に1年1か月を足すと 2009-11-30(存在しない日は末日に丸める)で、
     そこから22日は 2009-12-22。1日ずれる。
     → **足し戻すと元に戻る形**に変えた。まず「足しても行き過ぎない月数」を出し、
     残りを日数で数える。addMonths と同じ丸め方を通るので、ずれようがない。 */''':
    '''/* Years/months/days breakdown. ★Fixed 2026-09-01: this borrowed the length of the month before
     the end date, which **disagreed with this tool's own add/subtract tab whenever the count
     started on the last day of a month**. Example: 2008-10-31 → 2009-12-23 came out as
     "1 year 1 month 22 days", but adding 1 year 1 month to 2008-10-31 on the other tab gives
     2009-11-30 (a date that does not exist rounds down), and 22 days later is 2009-12-22.
     → Now **adding the result back returns the original**: take the largest number of months
     that does not overshoot, then count the rest in days, through the same rounding. */''',

    '// 営業日・週末・祝日を数える(終了日を含むかは incl に従う)':
    '// count working days, weekend days and holidays (whether the end date counts follows `incl`)',

    '/* ---------- 2. 加減算 ---------- */': '/* ---------- 2. Add and subtract ---------- */',
    '// 営業日': '// working days',
    '/* ---------- 3. 年齢・学年 ---------- */': '/* ---------- 3. Age and school year ---------- */',

    '''/* ★2026-09-01 是正: 前は月日をそのまま比べていたので、**2月29日生まれの平年**だけ
     「次の誕生日まで: 今日です」と出しているのに満年齢が1つ足りない、という食い違いが出た
     (次の誕生日の欄は 2月28日に丸めていて、こちらは丸めていなかった)。
     → 応当日を同じように末日に丸めてから比べる。民法143条2項の「応当する日がないときは
     その月の末日に満了する」とも同じ側になる。 */''':
    '''/* ★Fixed 2026-09-01: this compared month and day directly, so someone born on 29 February
     saw "next birthday: today" in a common year while the age below it was one year short
     (the next-birthday field rounded to 28 February; this one did not).
     → The anniversary is now rounded down to the end of the month the same way before
     comparing, which also matches Article 143(2) of the Civil Code. */''',

    '// 数え年': '// kazoedoshi (the traditional count, where you are 1 at birth)',
    '// 学年(4/2〜翌4/1 が同学年)。入学年度 = 満6歳になる年度の翌年度4月':
    '// school year (2 Apr - 1 Apr). Entry = April of the year after the year you turn 6',
    '// 早生まれは1つ前の年度扱い': '// born Jan-Apr 1 counts as the previous school year',
    '// 小1 = 1': '// first year of primary school = 1',
    '/* ---------- 4. 和暦 ---------- */': '/* ---------- 4. Era years ---------- */',
    '/* ---------- 5. 祝日一覧 ---------- */': '/* ---------- 5. Holiday list ---------- */',
    '/* ---------- 初期化 ---------- */': '/* ---------- Start-up ---------- */',
}

TR = {
    # 曜日(JS の getDay() の順)と月の名前
    "日": "Sun", "月": "Mon", "火": "Tue", "水": "Wed", "木": "Thu", "金": "Fri", "土": "Sat",
    "1月": "Jan", "2月": "Feb", "3月": "Mar", "4月": "Apr", "5月": "May", "6月": "Jun",
    "7月": "Jul", "8月": "Aug", "9月": "Sep", "10月": "Oct", "11月": "Nov", "12月": "Dec",

    # 日付の見せ方。⚠ `${…}` の並びは日英で同じでなければならない(年→月→日→曜日)
    "${dt.getFullYear()}年${MN[dt.getMonth()]}${dt.getDate()}日(${WD[dt.getDay()]})":
        "${dt.getFullYear()} ${MN[dt.getMonth()]} ${dt.getDate()} (${WD[dt.getDay()]})",

    # 一日限りの休日(その日のためだけに法律が作られたもの)
    "皇太子明仁親王の結婚の儀": "Wedding of Crown Prince Akihito",
    "昭和天皇の大喪の礼": "Funeral of Emperor Showa",
    "即位礼正殿の儀": "Enthronement Ceremony at the Seiden",
    "皇太子徳仁親王の結婚の儀": "Wedding of Crown Prince Naruhito",
    "天皇の即位の日": "Enthronement Day of the Emperor",

    # 国民の祝日。内閣府の英語表記に合わせる。
    # ⚠ ここは**素のアポストロフィ**で書く。`&#39;` にすると画面では正しく見えるが、
    #   `holidays()` が返す**データの中身**が実体参照のままになる(検証がこれを捕まえた)。
    #   道具の値は文字列であって HTML ではない、が正しい形。
    "元日": "New Year's Day",
    "成人の日": "Coming of Age Day",
    "建国記念の日": "National Foundation Day",
    "天皇誕生日": "The Emperor's Birthday",
    "春分の日": "Vernal Equinox Day",
    "みどりの日": "Greenery Day",
    "昭和の日": "Showa Day",
    "憲法記念日": "Constitution Memorial Day",
    "こどもの日": "Children's Day",
    "海の日": "Marine Day",
    "山の日": "Mountain Day",
    "敬老の日": "Respect for the Aged Day",
    "秋分の日": "Autumnal Equinox Day",
    "スポーツの日": "Sports Day",
    "体育の日": "Health and Sports Day",
    "文化の日": "Culture Day",
    "勤労感謝の日": "Labor Thanksgiving Day",
    "振替休日": "Substitute holiday",
    "国民の休日": "Citizens' holiday",

    # 元号(HTML の <option value> も同じ綴りにしてある)
    "令和": "Reiwa", "平成": "Heisei", "昭和": "Showa", "大正": "Taisho", "明治": "Meiji",
    "${e.name}${n === 1 ? \"元\" : n}年${MN[dt.getMonth()]}${dt.getDate()}日":
        "${e.name} ${n === 1 ? \"1\" : n}, ${MN[dt.getMonth()]} ${dt.getDate()}",
    "元号が不明です": "Unknown era",
    "そのような日付は存在しません": "No such date",
    "${era}${wy}年${m}月${d}日 は ${era} の開始(${fmt(e.start)})より前です":
        "${era} ${wy}/${m}/${d} is before ${era} began (${fmt(e.start)})",
    "${era}${wy}年${m}月${d}日 は ${ERAS[idx-1].name} に入っています":
        "${era} ${wy}/${m}/${d} falls inside ${ERAS[idx-1].name}",

    # 期間タブ。★単位はラベル側に置き、値は数だけにする(単複の分岐を書けないため)
    "両方の日付を入れてください。": "Enter both dates.",
    "(逆順で入力されたので入れ替えました)": "(entered in reverse order, so they were swapped)",
    "日数": "Days",
    "${days.toLocaleString()}日": "${days.toLocaleString()}",
    "初日算入": "end date included",
    "終了日は含まない": "end date not counted",
    "年月日で": "Years, months, days",
    "${yy}年${mm}か月${dd}日": "${yy}y ${mm}m ${dd}d",
    "週数": "Weeks",
    "${(days/7).toFixed(1)}週": "${(days/7).toFixed(1)}",
    "営業日": "Business days",
    "${biz.toLocaleString()}日": "${biz.toLocaleString()}",
    "土日祝を除く": "weekends and holidays excluded",
    "土日": "Weekend days",
    "${wknd.toLocaleString()}日": "${wknd.toLocaleString()}",
    "平日の祝日": "Holidays on weekdays",
    "${hol.toLocaleString()}日": "${hol.toLocaleString()}",

    # 加減算タブ
    "基準日と数値を入れてください。": "Enter a base date and a number.",
    "数値が大きすぎます(10万以内)。": "That number is too large (100,000 at most).",
    "結果": "Result",
    "休日": "non-working day",
    "平日": "working day",
    "ISO形式": "ISO format",
    "和暦": "Japanese era",
    "対応範囲外": "outside the supported range",
    "基準日からの実日数": "Days from the base date",
    "${Math.round((r - base)/MS).toLocaleString()}日":
        "${Math.round((r - base)/MS).toLocaleString()}",

    # 年齢・学年タブ
    "生年月日を入れてください。": "Enter a date of birth.",
    "生年月日が基準日より後になっています。": "The date of birth is later than the base date.",
    "年長(小学校入学の前年度)": "Final nursery year (the year before school starts)",
    "小学校入学まであと${1-grade}年度": "${1-grade} school years before elementary school",
    "小学${grade}年生": "Elementary school, year ${grade}",
    "中学${grade-6}年生": "Junior high school, year ${grade-6}",
    "高校${grade-9}年生": "High school, year ${grade-9}",
    "大学${grade-12}年生相当": "University, year ${grade-12} (equivalent)",
    "高校卒業から${grade-12}年度目": "${grade-12} school years since high school",
    "満年齢": "Age",
    "${age}歳": "${age}",
    "基準日 ${fmt(at)} 時点": "as of ${fmt(at)}",
    "数え年": "Kazoe age (traditional)",
    "${kazoe}歳": "${kazoe}",
    "生まれてからの日数": "Days lived",
    "${lived.toLocaleString()}日": "${lived.toLocaleString()}",
    "次の誕生日まで": "Days to next birthday",
    "今日です 🎂": "Today 🎂",
    "${toNext}日": "${toNext}",
    "学年(日本の年度)": "School year (Japan)",
    "${fiscalYear}年度": "FY${fiscalYear}",
    "生年月日": "Date of birth",
    "生まれた曜日": "Day of the week born",
    "${WD[b.getDay()]}曜日": "${WD[b.getDay()]}",

    # 和暦タブ
    "曜日": "Day of the week",
    "${WD[d.getDay()]}曜日": "${WD[d.getDay()]}",
    "年度": "Fiscal year",
    "${(d.getMonth()+1) < 4 ? d.getFullYear()-1 : d.getFullYear()}年度":
        "FY${(d.getMonth()+1) < 4 ? d.getFullYear()-1 : d.getFullYear()}",
    "4月始まり": "starts in April",
    "その年の通算日": "Day of the year",
    "${Math.round((d - mk(d.getFullYear(),1,1))/MS) + 1}日目":
        "Day ${Math.round((d - mk(d.getFullYear(),1,1))/MS) + 1}",
    "明治より前は未対応": "Before Meiji is not supported",
    "西暦": "Western date",

    # 祝日一覧タブ
    "1949〜2099年の範囲で入れてください。": "Enter a year between 1949 and 2099.",
    ('<tr><td class="num">${MN[dt.getMonth()]}${dt.getDate()}日</td>\n'
     '      <td class="${cls}">${WD[dt.getDay()]}</td><td class="hol">${map[k]}</td></tr>'):
        ('<tr><td class="num">${MN[dt.getMonth()]} ${dt.getDate()}</td>\n'
         '      <td class="${cls}">${WD[dt.getDay()]}</td><td class="hol">${map[k]}</td></tr>'),
    "<tr><th>日付</th><th>曜日</th><th>名称</th></tr>${rows}":
        "<tr><th>Date</th><th>Day</th><th>Name</th></tr>${rows}",
    ('<tr><td colspan="3" style="color:var(--sub);border:0;padding-top:10px">\n'
     '      計 ${cnt} 日 — うち土曜と重なって損をするのが ${weekendLoss} 日</td></tr>'):
        ('<tr><td colspan="3" style="color:var(--sub);border:0;padding-top:10px">\n'
         '      ${cnt} holidays in total — ${weekendLoss} of them fall on a Saturday and are '
         'lost</td></tr>'),
}

KEEP = set()

EN_LINKS = """    <p class="hl-links">
      <a href="./">Tools index</a> &middot;
      <a href="https://note.com/hirulab">Experiment log (JP)</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>"""


def en_nav(docs):
    import en_nav as _en_nav
    nav = _en_nav.build(docs, "pattern.html", "Japanese Pattern Generator",
                        "date.html", "../date/")
    return nav[:-len("\n  </nav>")] + "\n" + EN_LINKS






def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "date" / "index.html"
    en_path = docs / "en" / "date.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
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

    # (2) スクリプトの中: 日本語を含むリテラルは KEEP のものだけ
    kept = []
    for q, body in literals(en[s2:e2]):
        if JA_CHARS.search(body):
            if body not in KEEP:
                sys.exit("スクリプトの中に訳し忘れがあります: " + body[:120])
            kept.append(body)

    # (3) 識別子として書かれた日本語
    # ★コメントにも日本語が残っていないこと(2026-09-03 昼 追加)
    ja_com = [c for c in comments(en[s2:e2]) if JA_CHARS.search(c)]
    if ja_com:
        sys.exit("コメントに日本語が %d 件残っています: %s" % (len(ja_com), ja_com[0][:120]))

    ident = code_japanese(en[s2:e2])
    if ident:
        sys.exit("識別子として書かれた日本語が %d 箇所あります:\n  %s"
                 % (len(ident), "\n  ".join(ident[:6])))

    # (4) 文字列の中身を空にすると、日英でコードがバイト単位で一致すること
    #     = 祝日の規則・営業日・和暦・学年の計算は1バイトも違わない
    #     ⚠ この検査は 9/2 朝までテンプレートの `${…}` の中を見ていなかった。
    #        このページはテンプレートだらけなので、直っていなければ大穴を開けて出ていた。
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
    print("わざと日本語のまま残したリテラル: %d 件" % len(kept))
    print("画面に出るところの日本語: 0箇所")
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
