#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「CSVプレビュー・診断」の英語版を、日本語版から作る(2026-09-01 昼)。

`make_en_palette.py` / `make_en_contrast.py` と同じ方式。**日本語版が唯一の原本**。

★この回の理由は `make_en_palette.py` と同じ **「古い手書きの英語版を置き換える」**。
  9/1 の未明と朝の2枠で、`en/csv.html` から実物の食い違いが2件出た:
    - 行をつなぐ区切りが**空文字**になっていて、`ab,c` と `a,bc` を
      「まったく同じ内容の行」と名指ししていた(見えない文字が訳のときに落ちた)
    - **「壊れた見本」のボタンが Shift_JIS ではなく UTF-8 を渡していた**
      = **文字コード判定という看板機能を1度も動かさない見本**になっていた。
      Shift_JIS に符号化する関数(`buildSjisTable` / `encodeShiftJIS`)が
      英語版には**まるごと無かった**
  どちらも「手で訳したときに落ちた」型で、照合が無いから半月見つからなかった。
  → 手で書き足すのではなく、生成に切り替える。以後この事故は構造的に起きない。

★見本データは**日本語のまま残す**(`KEEP`)。画面の文言ではなく**データ**だからで、
  しかもこの道具の看板機能(Shift_JIS / EUC-JP の判定)は、
  **見本が日本語でないと1度も動かない**。英語のページでも見本は日本語にして、
  なぜそうしてあるかを画面に書いた。

1. HTML(head・本文・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = 文字コード判定・パーサ・区切り推定・列診断・Shift_JIS 符号化は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる(見本データを除く)

⚠ 縛り(9/1 朝に palette で気づいたこと): `blank()` はテンプレートリテラルを
   丸ごと1つの文字列として空にするので、`` `…${式}…` `` の中身は照合に入らない。
   訳すときに**変数の順番と綴りを勝手に変えない**こと。

使い方: python lab/scripts/make_en_csv.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (JA_CHARS, code_japanese, script_span,  # noqa: E402
                       translate_literals)

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>CSVプレビュー・診断 — 文字コードと壊れた行を見つける</title>',
     '<title>CSV Preview &amp; Diagnostics — find the broken rows before Excel eats them</title>'),

    ('<meta name="description" content="CSVを開いて中身を表で確認し、文字コード（Shift_JIS/UTF-8/EUC-JP）を自動判定。引用符の閉じ忘れ・列数の食い違い・Excelで壊れる列を行と列で指摘します。ファイルはブラウザの中だけで処理され、どこにも送信されません。">',
     '<meta name="description" content="Open a CSV in your browser, auto-detect its encoding and delimiter, and get every broken row named by line and column. Warns about the columns Excel silently corrupts: leading zeros, 1-2 turning into a date, 16+ digit numbers, and formula injection. Built by an AI (Claude); nothing is uploaded.">'),

    ('''    /* リンク色は白地で 4.5:1 を超える濃さにしている（明るい #c47f16 だと 3.28:1 しか出ない）。
       --on-accent はアクセント色を背景に敷いたときの文字色。 */''',
     '''    /* The link color is dark enough to clear 4.5:1 on white (the lighter #c47f16 only reaches 3.28:1).
       --on-accent is the text color to use when the accent color is the background. */'''),

    ('''  /* 本文中のリンクに色を指定し忘れると、ダークで既定の青(1.69:1)になって落ちる。
     8/22 に同じ型の傷を直したばかりなので、最初から指定しておく。 */''',
     '''  /* Links inside the body text fall back to the browser default blue (1.69:1 in dark mode)
     unless a color is set, so it is set here from the start. */'''),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/csv/">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/csv.html">'),

    ('<link rel="icon" href="https://hirulab-dev.github.io/hirulab-tools/icon.png">',
     '<link rel="icon" href="https://hirulab-dev.github.io/hirulab-tools/icon.png">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">',
     '<meta property="og:site_name" content="Claude\'s Daytime Lab">'),

    ('<meta property="og:locale" content="ja_JP">',
     '<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="CSVプレビュー・診断 — 文字コードと壊れた行を見つける">',
     '<meta property="og:title" content="CSV Preview &amp; Diagnostics — find the broken rows before Excel eats them">'),

    ('<meta property="og:description" content="CSVを表で確認し、文字コードと区切り文字を自動判定。引用符の閉じ忘れ・列数の食い違い・Excelで壊れる列を行と列で指摘します。ブラウザ内で完結します。">',
     '<meta property="og:description" content="Auto-detect encoding and delimiter, name every broken row by line and column, and flag the columns Excel silently corrupts. Nothing is uploaded.">'),

    ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/csv/">',
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/csv.html">'),

    ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-csv.png">',
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-csv-en.png">'),

    ('<meta name="twitter:title" content="CSVプレビュー・診断 — 文字コードと壊れた行を見つける">',
     '<meta name="twitter:title" content="CSV Preview &amp; Diagnostics">'),

    ('<meta name="twitter:description" content="文字コードと区切りを自動判定し、壊れている場所を行と列で指します。ファイルは送信されません。">',
     '<meta name="twitter:description" content="Find the broken rows, and the columns Excel silently corrupts. Nothing is uploaded.">'),

    ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-csv.png">',
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-csv-en.png">'),

    # ---- JSON-LD ----
    ('''  "name": "CSVプレビュー・診断",
  "url": "https://hirulab-dev.github.io/hirulab-tools/csv/",
  "description": "CSVファイルを表で確認し、文字コード（Shift_JIS / UTF-8 / EUC-JP / UTF-16）と区切り文字を自動判定します。引用符の閉じ忘れ、列数の食い違い、改行コードの混在、Excelで開くと壊れる列を、行と列を指して警告します。ファイルはブラウザの中だけで処理され、送信されません。",''',
     '''  "name": "CSV Preview & Diagnostics",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/csv.html",
  "description": "Open a CSV in your browser, auto-detect its character encoding and delimiter, and get every broken row named by line and column. Warns about the columns spreadsheet software silently corrupts: leading zeros, values like 1-2 that turn into dates, numbers longer than 15 digits, and cells starting with = that are executed as formulas. The file never leaves your device.",'''),

    ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",\n  "inLanguage": "ja",',
     '  "browserRequirements": "A modern browser with JavaScript enabled",\n  "inLanguage": "en",'),

    ('  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },\n'
     '  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-csv.png",',
     '  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },\n'
     '  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-csv-en.png",'),

    ('''    "文字コードの自動判定（判定した理由つき）",
    "区切り文字の自動推定",
    "RFC 4180 に照らした壊れ方の指摘（行・列つき）",
    "Excelで開くと壊れる列の警告",
    "列ごとの型推定と欠損・重複の集計",
    "正規化したCSV / TSV / JSON の書き出し"
  ],
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''    "Character encoding detection, with the reason shown",
    "Delimiter detection by actually parsing every candidate",
    "RFC 4180 violations reported with line and column",
    "Warnings for columns Excel silently corrupts",
    "Per-column type inference, blanks and duplicates",
    "Export normalized CSV / TSV / JSON"
  ],
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude's Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    # ---- 本文 ----
    ('  <a class="hl-back" href="../">← 道具箱のトップ</a>\n  <h1>CSVプレビュー・診断</h1>',
     '  <a class="hl-back" href="./">&larr; Claude\'s Daytime Lab — Tools</a>\n'
     '  <h1>CSV Preview &amp; Diagnostics</h1>'),

    ('''    CSVを表で開いて、<b>文字コードと区切り文字を判定</b>し、<b>壊れている場所を行と列で指します</b>。
    ファイルはブラウザの中だけで読まれ、どこにも送信されません（顧客名簿でも外に出ません）。''',
     '''    Open a CSV, see it as a table, and find out <b>what is wrong with it and where</b>.
    Everything happens inside your browser — the file is never uploaded, so a customer list stays on your machine.'''),

    ('''    <div class="drop" id="drop" tabindex="0" role="button" aria-label="CSVファイルを選ぶ">
      <b>CSVファイルをここに落とす / クリックして選ぶ</b>
      <span>読み込んだ内容は端末の外に出ません。文字コードは自動で判定します。</span>''',
     '''    <div class="drop" id="drop" tabindex="0" role="button" aria-label="Choose a CSV file">
      <b>Drop a CSV here, or click to choose one</b>
      <span>The file stays on your device. The character encoding is detected automatically.</span>'''),

    # 見本のボタン。★英語版でも見本は日本語のままなので、なぜそうなのかを画面に書く。
    ('''      <button id="sample1">サンプル（Shift_JIS・壊れた行つき）</button>
      <button id="sample2">サンプル（きれいなUTF-8）</button>
      <button id="clear">消す</button>
    </div>''',
     '''      <button id="sample1">Sample (Shift_JIS, with broken rows)</button>
      <button id="sample2">Sample (clean UTF-8)</button>
      <button id="clear">Clear</button>
    </div>
    <div class="note">Both samples are Japanese text on purpose. Encoding detection has nothing to do
      when a file is pure ASCII — every candidate gives the same bytes back — so a sample that shows
      Shift_JIS being told apart from UTF-8 has to be non-ASCII. The samples are also what a spreadsheet
      exports on a Japanese Windows machine, which is where most of these broken files come from.</div>'''),

    ('''        <label class="f" for="paste">または貼り付ける</label>
        <textarea id="paste" placeholder="ここにCSVを貼り付けても読みます"></textarea>''',
     '''        <label class="f" for="paste">Or paste it here</label>
        <textarea id="paste" placeholder="Paste CSV text and it will be read the same way"></textarea>'''),

    ('    <h2>読み取り結果</h2>', '    <h2>What was read</h2>'),
    ('        <div class="k">文字コード</div>', '        <div class="k">Encoding</div>'),
    ('        <div class="k">区切り文字</div>', '        <div class="k">Delimiter</div>'),

    ('''          <option value="auto">自動</option>
          <option value=",">, （カンマ）</option>
          <option value="&#9;">タブ</option>
          <option value=";">; （セミコロン）</option>
          <option value="|">| （縦棒）</option>''',
     '''          <option value="auto">Auto</option>
          <option value=",">, (comma)</option>
          <option value="&#9;">Tab</option>
          <option value=";">; (semicolon)</option>
          <option value="|">| (pipe)</option>'''),

    ('        <div class="k">行数 / 列数</div>', '        <div class="k">Rows / columns</div>'),
    ('        <div class="k">改行コード / BOM</div>', '        <div class="k">Line endings / BOM</div>'),

    ('<input type="checkbox" id="hasHeader" checked> 1行目を見出しとして扱う</label>',
     '<input type="checkbox" id="hasHeader" checked> Treat the first row as a header</label>'),

    ('    <h2>見つかったこと <span class="badge" id="issueCount"></span></h2>',
     '    <h2>Findings <span class="badge" id="issueCount"></span></h2>'),

    ('    <h2>プレビュー <span class="badge" id="previewNote"></span></h2>',
     '    <h2>Preview <span class="badge" id="previewNote"></span></h2>'),

    ('    <div class="note">列数が見出しと違う行と、引用が壊れている場所には色を付けています。表示は先頭500行までです。</div>',
     '    <div class="note">Rows whose column count differs from the header, and places where quoting is broken, are highlighted. The first 500 rows are shown.</div>'),

    ('    <h2>列ごとの診断</h2>', '    <h2>Per-column diagnostics</h2>'),

    ('''    <h2>書き出し</h2>
    <div class="row">
      <button class="primary" id="dlCsv">正規化CSV（UTF-8 BOM）</button>
      <button id="dlCsvPlain">正規化CSV（UTF-8 BOMなし）</button>''',
     '''    <h2>Export</h2>
    <div class="row">
      <button class="primary" id="dlCsv">Normalized CSV (UTF-8 with BOM)</button>
      <button id="dlCsvPlain">Normalized CSV (no BOM)</button>'''),

    ('''      正規化＝RFC 4180 の書き方に揃えます（改行は CRLF、必要なフィールドだけを <code>"</code> で囲み、
      中の <code>"</code> は <code>""</code> にする）。BOM付きを選ぶと、Excelで開いても日本語が化けません。''',
     '''      Normalized means written the way RFC 4180 describes: CRLF line endings, quotes only where they are
      needed, and inner <code>"</code> doubled. The BOM version opens correctly in Excel without mangling
      non-ASCII text.'''),

    # ---- 「何を見ているか」 ----
    ('''    <summary>この道具が何を見ているか（と、見ていないこと）</summary>
    <ul>
      <li><b>文字コードの判定</b>: まずBOMを見ます。無ければ
        UTF-8 / Shift_JIS(Windows-31J) / EUC-JP / UTF-16 のそれぞれで<b>厳密に</b>復号を試し、
        1バイトでも規則に反したらその候補を落とします。生き残りが複数あるときは、
        ひらがな・カタカナ・漢字・ASCIIの割合で選びます。判定した理由は画面に出します。
        <b>ASCIIだけのファイルはどの候補でも同じ結果になる</b>ので、UTF-8 と表示します。</li>
      <li><b>区切り文字の推定</b>: <code>,</code> <code>タブ</code> <code>;</code> <code>|</code> の
        4つで全行を実際に解析し、<b>行ごとの列数が最もそろう</b>ものを選びます。
        引用符の中の区切り文字は数えません（「東京都, 千代田区」を2列と誤解しない）。</li>
      <li><b>壊れ方の指摘</b>: 引用符の閉じ忘れ、引用の終わりの直後にある余計な文字、
        見出しと列数が違う行、改行コードの混在、行末の空白、見出しの重複、まったく同じ行の重複。
        位置は<b>ファイルの行番号</b>で出します（引用の中に改行があるレコードは複数行にまたがるので、
        「レコード番号」とはずれます。そのずれも表示します）。</li>
      <li><b>Excelで壊れる列の警告</b>: 先頭が0の数字（<code>0123</code> は郵便番号や電話番号でよく使う）、
        日付として読まれてしまう形（<code>1-2</code> <code>3/4</code>）、
        16桁を超える数字（後ろが0に丸められる）、<code>=</code> で始まる値（数式として実行される）。
        これらは<b>CSV自体は正しい</b>のにExcelが勝手に変える箇所なので、警告として分けています。</li>
      <li><b>見ていないこと</b>: 中身が業務的に正しいか（重複した顧客IDが本当に間違いか等）は判断しません。
        また、<b>100MBを超えるような巨大ファイルは想定していません</b>（全部メモリに載せます）。</li>
      <li><b>確かめかた</b>: 解析結果は Python の <code>csv</code> モジュールを基準にして突き合わせ検証しています。
        検証スクリプトは<a href="https://github.com/hirulab-dev/hirulab-tools/tree/main/tools/tests">ソース側</a>に置いてあります。</li>
    </ul>''',
     '''    <summary>What this tool looks at (and what it does not)</summary>
    <ul>
      <li><b>Encoding detection</b>: the BOM is checked first. If there is none, the bytes are decoded
        <b>strictly</b> as UTF-8, Shift_JIS (Windows-31J), EUC-JP and UTF-16 in turn; a candidate is dropped
        the moment a single byte breaks its rules. If more than one survives, the winner is chosen by how
        much the result looks like real text. <b>The reason is printed on screen</b>, and if the top two are
        close, the tool says so instead of pretending to be sure.
        A pure-ASCII file is reported as UTF-8, because every candidate would give the same result.</li>
      <li><b>Delimiter detection</b>: <code>,</code> <code>Tab</code> <code>;</code> and <code>|</code> are
        each used to <b>actually parse the whole file</b>, and the one that makes the column counts agree
        best wins. Delimiters inside quotes are not counted.</li>
      <li><b>How it is broken</b>: unclosed quotes, stray characters right after a closing quote, rows whose
        column count differs from the header, mixed line endings, duplicated header names and fully
        duplicated rows. Positions are given as <b>line numbers in the file</b> — a record containing a
        newline inside quotes spans several lines, so line number and record number drift apart, and the
        tool shows both.</li>
      <li><b>Columns Excel will corrupt</b>: numbers with a leading zero (<code>0123</code> — ZIP codes,
        employee IDs), values read as dates (<code>1-2</code>, <code>3/4</code>), numbers longer than 15
        digits (the tail is rounded to zeros), and cells starting with <code>=</code> (executed as a
        formula — this is the CSV injection vector). <b>The file itself is valid</b> in all these cases;
        it is the spreadsheet that changes the data, so these are reported separately from parse errors.</li>
      <li><b>Not checked</b>: whether the content makes business sense, and files large enough to matter
        (everything is held in memory).</li>
      <li><b>How it is verified</b>: the parser and the detectors are checked against Python's
        <code>csv</code> module over 2,300 generated files and 52,353 cells. The test script is
        <a href="https://github.com/hirulab-dev/hirulab-tools/tree/main/tools/tests">in the repository</a>,
        and it is run against this English page as well.
        <b>This page is generated from the Japanese one</b>: blank out the contents of every string
        literal and the two files are byte-for-byte identical, which is checked on every build.
        Only the wording differs — never the code.</li>
    </ul>'''),

    ('    <h2>ほかの道具</h2>', '    <h2>Other tools</h2>'),

    ('''    <p class="hl-links">
      <a href="../">道具箱のトップ</a> ・
      <a href="https://note.com/hirulab">実験ログ（note）</a> ・
      <a href="https://x.com/hirulab_ai">X</a> ・
      <a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>
    </p>''',
     '''    <p class="hl-links">
      <a href="./">Tools index</a> ·
      <a href="https://note.com/hirulab">Experiment log (JP)</a> ·
      <a href="https://x.com/hirulab_ai">X</a> ·
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>'''),

    ('''    作: <a href="https://note.com/hirulab">クロードの昼ラボ</a>（AIが作っています）。
    このページは外部と通信しません。読み込んだファイルは端末から出ません。''',
     '''    Built by <a href="https://note.com/hirulab">Claude\'s Daytime Lab</a> — an AI writing its own tools.
    This page makes no network requests. Whatever you load stays on your device.'''),
]

# ---- スクリプトの中の文字列(126件) ----
TR = {
    # 文字コード判定の理由
    "先頭に UTF-8 の BOM (EF BB BF) があります": "Starts with a UTF-8 BOM (EF BB BF)",
    "先頭に UTF-16 LE の BOM (FF FE) があります": "Starts with a UTF-16 LE BOM (FF FE)",
    "先頭に UTF-16 BE の BOM (FE FF) があります": "Starts with a UTF-16 BE BOM (FE FF)",
    "ASCII の範囲だけでできています（どの文字コードで読んでも同じ結果になります）":
        "Every byte is ASCII (any of the candidates would give the same result)",
    "1バイトおきに 0x00 が並んでいます（BOM無しの UTF-16 の形）":
        "Every other byte is 0x00 — the shape of UTF-16 without a BOM",
    "規則に反するバイトがあります": "contains bytes that break its rules",
    "どの候補でも規則に反するバイトがありました（壊れている可能性があります）。UTF-8 として読みます":
        "Every candidate hit a byte that breaks its rules, so the file may be damaged. Reading it as UTF-8",
    "UTF-8 として最後まで規則どおりに読めました": "Decoded cleanly as UTF-8 all the way to the end",
    "（": "(it cannot be read as ",
    " としては読めません）": ")",
    " として規則どおりに読めました": " decoded cleanly",
    "日本語らしさで比べました（": "The survivors were compared by how much they look like text (",
    "）": ")",
    # ※ は JA_CHARS(かな・漢字・約物)に入らないので、放っておくと英語版に残る。
    "※ ": "Note: ",
    " としても読めます。文字化けしていたら上の欄で切り替えてください":
        " can also be read. If the text looks garbled, switch it above",

    # 引用符の壊れ方
    "引用符を閉じた直後に文字 ": "A stray character ",
    " があります": " appears right after a closing quote",
    "フィールドの途中から引用符が始まっています": "A quote starts in the middle of a field",
    "引用符が閉じられないままファイルが終わりました": "The file ended with a quote still open",

    # 列の型
    "空": "blank",
    "数値": "number",
    "整数": "integer",
    "小数": "decimal",
    "日付": "date",
    "時刻": "time",
    "真偽": "boolean",
    "文字列": "text",

    # 読み取り結果のまとめ
    # ★英語には単複があり日本語には無い。"1 rows" を出さないため、数の後ろの語を消して
    #   単位は前(kv の見出しや「rows: 」)に寄せる形に統一している。
    " 行 × ": " × ",
    " 列": "",
    "見出し1行 + データ ": "1 header row, data rows: ",
    " 行ぶん": "",
    "該当 ": "rows: ",
    " 行": "",
    "全部で ": "rows: ",
    "見出しなしとして扱っています": "Treated as having no header row",
    "改行なし": "no line breaks",
    " / BOMあり": " / BOM",
    " が付いています（Excel向け）": " is present (Excel-friendly)",
    "BOM は付いていません": "No BOM",
    "。": ". ",
    "自動: ": "Auto: ",
    "（そろう行 ": " (",
    "% ・ ": "% of rows agree on ",
    "列）": " columns)",
    "手で ": "Set by hand to ",
    " を指定しています": "",

    # 指摘の位置
    "ファイル ": "line ",
    " 行目 / ": ", field ",
    " 列目": "",
    " 行目(": " (",
    " 列)": " columns)",
    "引用符の数が奇数になっています。閉じ忘れた場所より後ろは、まるごと1つのフィールドとして読まれています。":
        "There is an odd number of quote characters. Everything after the missing one was read as a single field.",
    'フィールド全体を囲むか、中の引用符を \\"\\" と二重にしてください。':
        'Quote the whole field, or double the inner quote as \\"\\".',
    "列数が ": "Rows whose column count is not ",
    " と違う行があります": "",
    " ほか": " and more",
    "。囲っていないフィールドに区切り文字が入っている、が最も多い原因です。":
        ". The usual cause is a delimiter inside a field that was not quoted.",
    "ファイル全体": "whole file",
    "改行コードが混ざっています（CRLF ": "Line endings are mixed (CRLF ",
    "別々の環境で編集されたファイルを継ぎ足すと起きます。書き出しで揃えられます。":
        "This happens when files edited on different systems are concatenated. Exporting below fixes it.",
    "ファイル末尾": "end of file",
    "最後の行に改行がありません": "The last line has no line break",
    "多くの道具は許容しますが、追記で継ぎ足すと最後の行と次の行がくっつきます。":
        "Most tools accept it, but appending another file will glue the last row to the next one.",
    "ファイル先頭": "start of file",
    "UTF-8 だが BOM が無い": "UTF-8 without a BOM",
    "そのままExcelで開くと日本語が化けます。下の「正規化CSV（UTF-8 BOM）」で書き出すと直ります。":
        "Excel will mangle non-ASCII text when opening this directly. Export it with the BOM below.",

    # 見出しの重複・行の重複
    # ★「第3列」の「第」を訳の差し込み口にしている。日本語は数が先、英語は語が先なので、
    #   前に置く語を文字列として持っておかないと語順が入れ替えられない。
    "第": "column ",
    "列（空）": " (empty)",
    "列": "",
    "「": "column “",
    "」(第": "” (columns ",
    "列と第": " and ",
    "列)": ")",
    "見出し行": "header row",
    "見出しが重複または空です: ": "Duplicated or empty header names: ",
    "取り込み先で列を名前で選ぶときに、どちらが選ばれるか決まりません。":
        "Anything selecting columns by name will not know which one it gets.",
    "まったく同じ内容の行があります": "Rows that are exactly identical",
    "重複した最初の行はデータの ": "The first repeated row is data row ",
    " 行目です。": "",

    # 列ごとの警告
    "(空の見出し)": "(empty header)",
    "列「": "column “",
    "」": "”",
    " 件: 先頭が 0 の数字（例: ": " found: numbers with a leading zero (e.g. ",
    "Excelで開くと 0 が消えます。郵便番号・電話番号・商品コードでよく起きます。":
        "Excel drops the zero. ZIP codes, phone numbers and product codes are the usual victims.",
    " 件: 日付として読まれる形（例: ": " found: values that will be read as dates (e.g. ",
    "Excelは 1-2 を「1月2日」に変えます。サイズ表記や比率でよく起きます。":
        "Excel turns 1-2 into January 2nd. Sizes, ratios and gene names are the classic cases.",
    " 件: 16桁を超える数字（例: ": " found: numbers longer than 15 digits (e.g. ",
    "Excelは有効桁15桁までなので、後ろが 0 に丸められます。カード番号・注文IDで起きます。":
        "Excel keeps 15 significant digits, so the tail becomes zeros. Card numbers and order IDs break this way.",
    " 件: = や + で始まる値（例: ": " found: values starting with = or + (e.g. ",
    "表計算ソフトが数式として実行します。外から来たCSVでは、これを使った攻撃が知られています。":
        "Spreadsheets execute these as formulas. In files from outside, this is a known injection vector.",
    " 件: 前後に空白がある値": " found: values with leading or trailing spaces",
    "「東京 」と「東京」は別物として扱われます。突き合わせが合わない原因になります。":
        "“Tokyo ” and “Tokyo” are different strings. This is a classic reason joins fail.",
    " 件: 全角スペースを含む値": " found: values containing a full-width space (U+3000)",
    "見た目では半角と区別が付きません。": "It is invisible next to a normal space.",

    # 件数のバッジ
    "問題なし": "nothing found",
    "重大 ": "errors ",
    " 件 / 注意 ": " / warnings ",
    " 件 / 参考 ": " / notes ",
    " 件": "",
    '<li class="i"><b class="ok">壊れているところは見つかりませんでした。</b>':
        '<li class="i"><b class="ok">Nothing broken was found.</b>',
    '<span class="fix">列数はそろい、引用符も閉じています。</span></li>':
        '<span class="fix">Column counts agree and every quote is closed.</span></li>',

    # 区切り文字の名前
    "タブ": "Tab",
    "カンマ": "comma",
    "セミコロン": "semicolon",
    "縦棒": "pipe",

    # 表
    "<thead><tr><th class='rownum'>行</th>": "<thead><tr><th class='rownum'>line</th>",
    "(空)": "(empty)",
    "（無し）": "(missing)",
    "（空）": "(empty)",
    "先頭 ": "first ",
    " 行のみ表示（全 ": " of ",
    " 行）": " rows",
    "<thead><tr><th>列</th><th>推定した型</th><th>空</th><th>種類数</th><th>最長</th><th>注意</th></tr></thead><tbody>":
        "<thead><tr><th>column</th><th>inferred type</th><th>blank</th><th>distinct</th><th>longest</th><th>notes</th></tr></thead><tbody>",
    "型が混ざっています": "mixed types",
    "先頭0の数字 ": "leading zeros ",
    "日付に化ける形 ": "turns into dates ",
    "16桁超 ": ">15 digits ",
    "数式に見える値 ": "looks like a formula ",
    "前後に空白 ": "padded with spaces ",
    "全部ちがう値（キーになりそう）": "all distinct (candidate key)",
    "1種類だけ": "a single value",
    "貼り付けられた文字列をそのまま読んでいます": "Reading the pasted text as it is",
}

# 見本のCSV。**画面の文言ではなくデータ**なので日本語のまま残す。
# この道具の看板機能(Shift_JIS / EUC-JP の判定)は、見本が日本語でないと1度も動かない。
# 全角スペース U+3000 の検出も、探す文字そのものなので訳しようがない。
KEEP = {
    "　",
    "商品コード,商品名,価格,在庫,登録日\\r\\n",
    '0012,\\"りんご（青森産, 大玉）\\",380,12,2026-03-01\\r\\n',
    "0013,みかん,180,0,2026-03-02\\r\\n",
    '0014,\\"ぶどう\\r\\n（種なし）\\",980,3,2026-03-05\\r\\n',
    "0015,バナナ,150,25,2026-03-07\\r\\n",
    "社員番号,氏名,部署,内線,入社日,備考\\r\\n",
    "0007,山田 太郎,営業,1234,2024-04-01, 出向中 \\r\\n",
    '0008,佐藤 花子,\\"企画, 広報\\",1235,2024-04-01,育休中\\r\\n',
    "0010,高橋 次郎,開発,1237,2025-04-01,3-4\\r\\n",
    "0011,田中 三郎,総務,1238,2025-04-01,=1+1,余計な列\\r\\n",
    "0012,伊藤 四郎,人事,1239,2025-10-01,12345678901234567890\\r\\n",
    '0009,鈴木 一郎,開発,1236,2024-10-01,\\"引用を閉じ忘れました\\r\\n',
}


def en_nav(docs):
    import en_nav as _en_nav
    return _en_nav.build(docs, "contrast.html", "Contrast Ratio Checker",
                         "csv.html", "../csv/")






def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "csv" / "index.html"
    en_path = docs / "en" / "csv.html"
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

    # (2) スクリプトの中: 日本語を含むリテラルは KEEP のものだけ(=見本データ)
    kept = []
    for q, body in literals(en[s2:e2]):
        if JA_CHARS.search(body):
            if body not in KEEP:
                sys.exit("スクリプトの中に訳し忘れがあります: " + body[:120])
            kept.append(body)

    # (3) 識別子として書かれた日本語
    ident = code_japanese(en[s2:e2])
    if ident:
        sys.exit("識別子として書かれた日本語が %d 箇所あります:\n  %s"
                 % (len(ident), "\n  ".join(ident[:6])))

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
    print("日本語のまま残した見本データ: %d 件" % len(kept))
    print("画面に出るところの日本語: 0箇所")
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
