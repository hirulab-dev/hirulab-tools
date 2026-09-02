#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「手取り計算機」の英語版を、日本語版から作る(2026-09-02 夜)。

`make_en_date.py` と同じ方式・同じ考え方。**日本語版が唯一の原本**で、英語版を手で直さない。

★なぜ今これを作るか(方針の見直し)
  2026-08-28 の `make_en_contrast.py` の冒頭に
  **「frima-profit・take-home・date は英語にしても読む人がいない」**と書いて外していた。
  ところが 9/2 昼に date だけ方針を変えて英語版を出している
  (「日本で働いている人・日本の日付を扱う開発者に、日本のカレンダーを英語で渡す」)。
  **同じ理屈は手取り計算機にそのまま当たる**。日本で働く外国人にとって
  「額面いくらで手取りいくらか」は日付より切実で、しかも
  **料率を自分で直せる**というこの道具の性格は、制度に不案内な読み手ほど効く。
  → 8/28 の判断を見直して作る。中身は「日本語版を英語に置き換えたもの」ではなく、
    **英語で読む日本の給与計算の道具**にする(date と同じ立て方)。

★この作業のきっかけ: 同じ日の夜に `check_en_parity.py` が
  「英語版を持たない道具が2本ある」と初めて言えるようになったこと。
  それまで手書きの対応表しか回していなかったので、**この2本は数にも入っていなかった**。

使い方: python lab/scripts/make_en_take_home.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (JA_CHARS, code_japanese, script_span,  # noqa: E402
                       translate_literals)

BASE = "https://hirulab-dev.github.io/hirulab-tools/"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>手取り計算機 — 料率を自分で直せる</title>',
     '<title>Japan Take-Home Pay Calculator &mdash; every rate is yours to edit</title>'),

    ('<meta name="description" content="額面から手取りを概算します。社会保険料率・税率をすべて画面上で編集できるので、料率が改定されても自分で直して使えます。データは送信されません。">',
     '<meta name="description" content="Estimates your take-home pay in Japan from your gross annual salary. Every social insurance rate, tax rate and cap is editable on the page, so the tool still works after the rules change. Nothing is sent anywhere.">'),

    ('''  /* 表の中の入力欄が固定幅のままだと、狭い画面で表ごと右へはみ出す */''',
     '''  /* If the inputs inside the table keep a fixed width, the whole table overflows on a narrow screen */'''),

    ('<link rel="canonical" href="%stake-home/">\n'
     '<link rel="alternate" hreflang="ja" href="%stake-home/">\n'
     '<link rel="alternate" hreflang="en" href="%sen/take-home.html">' % (BASE, BASE, BASE),
     '<link rel="canonical" href="%sen/take-home.html">\n'
     '<link rel="alternate" hreflang="en" href="%sen/take-home.html">\n'
     '<link rel="alternate" hreflang="ja" href="%stake-home/">' % (BASE, BASE, BASE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="手取り計算機 — クロードの昼ラボ">',
     '<meta property="og:title" content="Japan Take-Home Pay Calculator">'),

    ('<meta property="og:description" content="額面から手取りを概算します。社会保険料率も税率も全部画面で編集できるので、制度が変わっても自分で直して使えます。">',
     '<meta property="og:description" content="Estimates take-home pay in Japan from gross annual salary. Every rate and cap is editable, so the tool survives the next rule change.">'),

    ('<meta property="og:url" content="%stake-home/">' % BASE,
     '<meta property="og:url" content="%sen/take-home.html">' % BASE),

    ('<meta property="og:image" content="%sogp/ogp-take-home.png">' % BASE,
     '<meta property="og:image" content="%sogp/ogp-take-home-en.png">' % BASE),

    ('<meta name="twitter:title" content="手取り計算機 — クロードの昼ラボ">',
     '<meta name="twitter:title" content="Japan Take-Home Pay Calculator">'),

    ('<meta name="twitter:description" content="額面から手取りを概算します。社会保険料率も税率も全部画面で編集できるので、制度が変わっても自分で直して使えます。">',
     '<meta name="twitter:description" content="Gross to take-home in Japan, with every social insurance rate, tax rate and cap editable on the page.">'),

    ('<meta name="twitter:image" content="%sogp/ogp-take-home.png">' % BASE,
     '<meta name="twitter:image" content="%sogp/ogp-take-home-en.png">' % BASE),

    # ⚠ JSON-LD の中には実体参照を書かない(2026-09-02 昼の教訓)。
    #   `<script>` の中身は生テキストなので `&#39;` がほどかれず、構造化データに
    #   `Claude&#39;s Daytime Lab` という文字列そのものが渡る。
    ('''  "name": "手取り計算機",
  "url": "%stake-home/",
  "description": "額面から手取りを概算します。社会保険料率も税率も画面上で編集できます。",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "JPY"
  },
  "image": "%sogp/ogp-take-home.png",
  "author": {
    "@type": "Organization",
    "name": "クロードの昼ラボ",
    "url": "https://note.com/hirulab"
  },
  "isPartOf": {
    "@type": "WebSite",
    "name": "クロードの昼ラボ — ツール置き場",
    "url": "%s"
  }''' % (BASE, BASE, BASE),
     '''  "name": "Japan Take-Home Pay Calculator",
  "url": "%sen/take-home.html",
  "description": "Estimates take-home pay in Japan from a gross annual salary. Every social insurance rate, tax rate and cap can be edited on the page.",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "image": "%sogp/ogp-take-home-en.png",
  "author": {
    "@type": "Organization",
    "name": "Claude's Daytime Lab",
    "url": "https://note.com/hirulab"
  },
  "isPartOf": {
    "@type": "WebSite",
    "name": "Claude's Daytime Lab — Tools",
    "url": "%sen/"
  }''' % (BASE, BASE, BASE)),

    ('''<a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>手取り計算機</h1>
<p class="lead">額面から手取りを概算します。<strong>料率は全部あなたが直せます。</strong>制度は毎年変わるので、固定値を信じさせない作りにしました。</p>''',
     '''<a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab tools</a>
  <h1>Japan Take-Home Pay Calculator</h1>
<p class="lead">Estimates what actually lands in your bank account, from your gross annual pay in Japan. <strong>Every rate on this page is yours to edit.</strong> The rules change every year, so the tool is built not to make you trust a hard-coded number.</p>'''),

    ('''  <strong>これは概算です。</strong>社会保険料は本来「標準報酬月額」の等級表で決まりますが、ここでは月額に料率を直接かけています。等級の境目では実際と数千円ずれます。
  正確な金額は給与明細か勤務先にご確認ください。<span id="asof"></span>''',
     '''  <strong>This is an estimate.</strong> Social insurance in Japan is really worked out from a table of standard monthly remuneration grades; this page multiplies your monthly pay by the rate directly. Near a grade boundary the result can be a few thousand yen out.
  For the real figure, check your payslip or ask your employer. <span id="asof"></span>'''),

    ('  <h2>あなたの条件</h2>', '  <h2>Your situation</h2>'),

    ('      <label for="annual">額面年収（賞与込み・円）</label>',
     '      <label for="annual">Gross annual pay, bonuses included (JPY)</label>'),

    ('      <label for="bonus">うち賞与の合計（円）</label>',
     '      <label for="bonus">Of which, total bonuses (JPY)</label>'),

    ('''        社会保険料には<strong>月給と賞与で別々の上限</strong>があるので、内訳で結果が変わります。''',
     '''        Social insurance has <strong>separate caps for monthly pay and for bonuses</strong>, so how the total splits changes the answer.'''),

    ('      <label for="bonusN">賞与の支給回数（年）</label>',
     '      <label for="bonusN">How many bonus payments per year</label>'),

    ('''        厚生年金の賞与の上限は<strong>1回あたり</strong>なので、回数で変わります。''',
     '''        The pension cap on bonuses is <strong>per payment</strong>, so the number of payments matters.'''),

    ('      <label for="age">年齢</label>', '      <label for="age">Age</label>'),

    ('      <label for="deps">扶養親族の人数（配偶者含む・16歳以上）</label>',
     '      <label for="deps">Dependants (spouse included, aged 16 or over)</label>'),

    ('''    <label class="chip"><input type="checkbox" id="empIns" checked> 雇用保険に加入している</label>
    <label class="chip"><input type="checkbox" id="pension" checked> 厚生年金に加入している</label>
    <label class="chip"><input type="checkbox" id="health" checked> 健康保険に加入している</label>''',
     '''    <label class="chip"><input type="checkbox" id="empIns" checked> Enrolled in employment insurance</label>
    <label class="chip"><input type="checkbox" id="pension" checked> Enrolled in the employees&#39; pension</label>
    <label class="chip"><input type="checkbox" id="health" checked> Enrolled in health insurance</label>'''),

    ('  <h2>手取り</h2>', '  <h2>Take-home pay</h2>'),

    ('      <div class="big"><span id="netY">—</span><small>／年</small></div>\n'
     '      <div style="color:var(--sub);font-size:.9rem">月あたり <b id="netM">—</b>（賞与を12等分した平均）</div>',
     '      <div class="big"><span id="netY">&mdash;</span><small>&nbsp;/ year</small></div>\n'
     '      <div style="color:var(--sub);font-size:.9rem">Per month <b id="netM">&mdash;</b> (bonuses spread evenly over 12)</div>'),

    ('      <div style="font-size:.82rem;color:var(--sub)">手取り率</div>\n'
     '      <div style="font-size:1.5rem;font-weight:700" id="rate">—</div>',
     '      <div style="font-size:.82rem;color:var(--sub)">Kept</div>\n'
     '      <div style="font-size:1.5rem;font-weight:700" id="rate">&mdash;</div>'),

    ('''    <span><b style="background:var(--accent)"></b>手取り</span>
    <span><b style="background:#7c8aa0"></b>社会保険料</span>
    <span><b style="background:#b3261e"></b>所得税</span>
    <span><b style="background:#8b5cf6"></b>住民税</span>''',
     '''    <span><b style="background:var(--accent)"></b>Take-home</span>
    <span><b style="background:#7c8aa0"></b>Social insurance</span>
    <span><b style="background:#b3261e"></b>Income tax</span>
    <span><b style="background:#8b5cf6"></b>Residence tax</span>'''),

    ('  <h2>内訳（年額）</h2>', '  <h2>Breakdown (per year)</h2>'),

    ('    <thead><tr><th>項目</th><th>金額</th><th>額面比</th></tr></thead>',
     '    <thead><tr><th>Item</th><th>Amount</th><th>Of gross</th></tr></thead>'),

    ('    <summary>計算の途中経過を見る</summary>',
     '    <summary>Show the intermediate figures</summary>'),

    ('  <h2>料率（ここを直してください）</h2>', '  <h2>Rates (this is the part you edit)</h2>'),

    ('''    初期値は一般的な目安です。<strong>健康保険料率は都道府県と保険者で違います</strong>（協会けんぽか組合健保か）。
    給与明細の控除額から逆算して合わせると精度が上がります。''',
     '''    The starting values are common ballpark figures. <strong>The health insurance rate differs by prefecture and by insurer</strong> (the national association scheme or a company society). Working backwards from the deductions on your payslip will make this much more accurate.'''),

    ('''    <div class="rate"><label>健康保険（本人負担）</label><input type="number" id="r_health" value="5.00" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>介護保険（40〜64歳・本人）</label><input type="number" id="r_care" value="0.80" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>厚生年金（本人負担）</label><input type="number" id="r_pension" value="9.15" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>雇用保険（本人負担）</label><input type="number" id="r_emp" value="0.55" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>住民税・所得割</label><input type="number" id="r_res" value="10.0" step="0.1"><span class="unit">%</span></div>
    <div class="rate"><label>住民税・均等割（年額）</label><input type="number" id="r_resflat" value="5000" step="100"><span class="unit">円</span></div>
    <div class="rate"><label>基礎控除（所得税）</label><input type="number" id="d_basic" value="480000" step="10000"><span class="unit">円</span></div>
    <div class="rate"><label>基礎控除（住民税）</label><input type="number" id="d_basic_r" value="430000" step="10000"><span class="unit">円</span></div>
    <div class="rate"><label>扶養控除・1人あたり（所得税）</label><input type="number" id="d_dep" value="380000" step="10000"><span class="unit">円</span></div>
    <div class="rate"><label>扶養控除・1人あたり（住民税）</label><input type="number" id="d_dep_r" value="330000" step="10000"><span class="unit">円</span></div>
    <div class="rate"><label>復興特別所得税</label><input type="number" id="r_recon" value="2.1" step="0.1"><span class="unit">%</span></div>
    <div class="rate"><label>健保の上限（標準報酬月額）</label><input type="number" id="c_health_m" value="1390000" step="10000"><span class="unit">円</span></div>
    <div class="rate"><label>厚年の上限（標準報酬月額）</label><input type="number" id="c_pension_m" value="650000" step="10000"><span class="unit">円</span></div>
    <div class="rate"><label>健保の上限（賞与・年度の累計）</label><input type="number" id="c_health_b" value="5730000" step="10000"><span class="unit">円</span></div>
    <div class="rate"><label>厚年の上限（賞与・1回あたり）</label><input type="number" id="c_pension_b" value="1500000" step="10000"><span class="unit">円</span></div>''',
     '''    <div class="rate"><label>Health insurance (employee share)</label><input type="number" id="r_health" value="5.00" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>Long-term care insurance (ages 40&ndash;64)</label><input type="number" id="r_care" value="0.80" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>Employees&#39; pension (employee share)</label><input type="number" id="r_pension" value="9.15" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>Employment insurance (employee share)</label><input type="number" id="r_emp" value="0.55" step="0.01"><span class="unit">%</span></div>
    <div class="rate"><label>Residence tax, income-based part</label><input type="number" id="r_res" value="10.0" step="0.1"><span class="unit">%</span></div>
    <div class="rate"><label>Residence tax, flat part (per year)</label><input type="number" id="r_resflat" value="5000" step="100"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Basic deduction (income tax)</label><input type="number" id="d_basic" value="480000" step="10000"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Basic deduction (residence tax)</label><input type="number" id="d_basic_r" value="430000" step="10000"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Dependant deduction each (income tax)</label><input type="number" id="d_dep" value="380000" step="10000"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Dependant deduction each (residence tax)</label><input type="number" id="d_dep_r" value="330000" step="10000"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Special reconstruction income tax</label><input type="number" id="r_recon" value="2.1" step="0.1"><span class="unit">%</span></div>
    <div class="rate"><label>Health insurance cap (monthly)</label><input type="number" id="c_health_m" value="1390000" step="10000"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Pension cap (monthly)</label><input type="number" id="c_pension_m" value="650000" step="10000"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Health insurance cap (bonuses, per fiscal year)</label><input type="number" id="c_health_b" value="5730000" step="10000"><span class="unit">&yen;</span></div>
    <div class="rate"><label>Pension cap (bonuses, per payment)</label><input type="number" id="c_pension_b" value="1500000" step="10000"><span class="unit">&yen;</span></div>'''),

    ('    <button id="reset">初期値に戻す</button>\n'
     '    <span class="note" style="margin:0">変更はこの端末に保存されます（次回も引き継がれます）。</span>',
     '    <button id="reset">Reset to defaults</button>\n'
     '    <span class="note" style="margin:0">Your edits are kept on this device, so they are still here next time.</span>'),

    ('  <h2>所得税の税率表</h2>\n'
     '  <p class="note" style="margin-top:-6px">課税所得に応じた累進税率。ここも直せます。</p>',
     '  <h2>Income tax brackets</h2>\n'
     '  <p class="note" style="margin-top:-6px">The progressive rates applied to taxable income. Editable too.</p>'),

    ('<button id="resetBr">税率表を初期値に戻す</button>',
     '<button id="resetBr">Reset the brackets</button>'),

    ('''  <strong>この計算に入れていないもの</strong>：標準報酬月額の<strong>等級区分</strong>（上限だけは入れましたが、
  途中の等級は使わず月額に直接かけています）、生命保険料控除・iDeCo・住宅ローン控除などの各種控除、ふるさと納税、
  子ども・子育て拠出金（会社負担なので手取りに影響しません）、住民税の調整控除、非課税限度額、
  基礎控除が合計所得2,400万円を超えると減っていく分。<br>
  <strong>2026-09-01 に入れたもの</strong>：社会保険料の上限（健保の標準報酬月額139万円・厚年65万円、
  賞与は健保が年度累計573万円・厚年が1回150万円）。それまで上限を見ていなかったので、
  <strong>年収が高いほど実際より多く引かれていました</strong>。上限は下の欄で直せます。<br>
  <strong>住民税は前年の所得に対してかかります。</strong>新社会人の1年目は住民税が引かれないので、実際の手取りはこの計算より多くなります。''',
     '''  <strong>What this does not model</strong>: the <strong>grade table</strong> for standard monthly remuneration (the caps are in, but the grades in between are not &mdash; the rate is applied to your monthly pay directly), deductions for life insurance premiums, iDeCo or a housing loan, hometown tax donations, the child-rearing contribution (paid by the employer, so it does not touch your take-home), the residence tax adjustment credit, the non-taxable threshold, and the way the basic deduction shrinks above &yen;24,000,000 of total income.<br>
  <strong>Added on 2026-09-01</strong>: the social insurance caps (health insurance at &yen;1,390,000 of standard monthly remuneration and the pension at &yen;650,000; for bonuses, &yen;5,730,000 per fiscal year for health insurance and &yen;1,500,000 per payment for the pension). Before that the caps were missing, so <strong>the higher the salary, the more this tool over-deducted</strong>. The caps are editable in the panel above.<br>
  <strong>Residence tax is charged on last year&#39;s income.</strong> In your first year of work in Japan there is no residence tax to pay, so your real take-home is higher than this page shows.'''),

    ('''  <footer>
  ブラウザの中だけで計算しています。入力した金額はどこにも送信されません（送信する仕組みを書いていません）。
</footer>''',
     '''  <footer>
  Everything is worked out inside your browser. The amounts you type are never sent anywhere &mdash; there is no code on this page that could send them.
</footer>'''),
]

# スクリプトの中の文字列リテラル。中身の完全一致で差し替える(引用符の種類は問わない)
TR = {
    # 内訳の行の名前。★これは画面に出る「値」なので実体参照は書かない
    #   (2026-09-02 昼、日付計算機の英語版で `New Year&#39;s Day` と書いて実バグにした)
    "健康保険": "Health insurance",
    "介護保険": "Long-term care insurance",
    "厚生年金": "Employees' pension",
    "雇用保険": "Employment insurance",
    "額面年収": "Gross annual pay",
    # 内訳の字下げ。日本語は全角空白1つ。HTML は普通の空白を畳むので、
    # 英語側はノーブレークスペース2つにする(見た目の字下げを保つため)
    "　": "  ",
    "社会保険料 合計": "Social insurance, total",
    "所得税（復興税込み）": "Income tax (incl. reconstruction surtax)",
    "住民税": "Residence tax",

    '<tr class="sum" data-k="net"><td>手取り</td><td class="pos">${yen(net)}</td>\n'
    '     <td>${annual?(net/annual*100).toFixed(1)+"%":""}</td></tr>':
    '<tr class="sum" data-k="net"><td>Take-home</td><td class="pos">${yen(net)}</td>\n'
    '     <td>${annual?(net/annual*100).toFixed(1)+"%":""}</td></tr>',

    "給与所得控除": "Employment income deduction",
    "給与所得（額面 − 給与所得控除）": "Employment income (gross − deduction)",
    "所得税の課税所得": "Taxable income for income tax",
    "所得税（復興税を除く）": "Income tax (before reconstruction surtax)",
    "住民税の課税所得": "Taxable income for residence tax",

    "<thead><tr><th>課税所得がこの額以上</th><th>税率</th><th>控除額</th></tr></thead><tbody>":
    "<thead><tr><th>Taxable income from</th><th>Rate</th><th>Deduction</th></tr></thead><tbody>",

    # 桁区切りの出しかた。どちらも 3 桁区切りなので表示は変わらないが、
    # 英語ページが ja-JP を指定しているのは説明がつかないので合わせる。
    "ja-JP": "en-US",
}

# わざと日本語のまま残すリテラル(理由つき)。今回は0件
KEEP = set()


def en_nav(docs):
    """英語ナビを**実ページから**組み直す(`en_nav.build`)。生成元がずれようがない。"""
    import en_nav as _en_nav
    return _en_nav.build(docs, "date.html", "Japanese Date Calculator",
                         "take-home.html", "../take-home/")


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "take-home" / "index.html"
    en_path = docs / "en" / "take-home.html"
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

    # (3) 文字列でもコメントでも正規表現でもない日本語(識別子・object のキー)が無いこと
    ident = code_japanese(en[s2:e2])
    if ident:
        sys.exit("スクリプトの中に文字列でない日本語があります: %s" % ident[:4])

    # (4) 文字列の中身を空にすると、日英でコードがバイト単位で一致すること
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
    print("文字列でない日本語: 0箇所")
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a.encode()))


if __name__ == "__main__":
    main()
