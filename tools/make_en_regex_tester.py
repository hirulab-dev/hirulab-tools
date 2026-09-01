#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「正規表現テスタ」の英語版を、日本語版から作る(2026-09-02 未明)。

`make_en_palette.py` / `make_en_csv.py` と同じ方式。**日本語版が唯一の原本**。

★この回も理由は「新しく英語版を出す」ではなく **「古い手書きの英語版を置き換える」**
  (手書きの置き換えは palette・csv に続いて3本目。残る手書きは char-counter と timezone)。

  同じ枠で新設した `test_regex_tester.py` が、日本語版に4つの実バグを見つけた:
    - 長さ0のマッチがあるとテスト文字列が画面から消える
    - 500件で打ち切っているのに件数はその数を出す(600件が「501 件マッチ」)
    - `s` / `i` フラグを読み下しに映していない(画面の2か所が食い違う)
    - グループが足りない `\\3` を「グループ3と同じ文字列」と説明する(実際は8進エスケープ)
  **4つとも英語版にも同じ形であった**。手で両方直すと、次にどちらかだけ育つ。
  → 生成に切り替える。以後この事故は構造的に起きない。

⚠ **1か所だけ、日本語版の書き方を英語のために変えた**(csv のときと同じ型)。
   手書きの英語版は件数を `matches.length === 1 ? " match" : " matches"` と単複で
   分けていたが、**日英でコードを1バイトも変えない**縛りがあるので分岐は置けない
   (訳の表は文字列の中身で引くので、日本語では同じ文字列になる2つの枝を
   英語で書き分けられない)。→ 数を後ろに置く「マッチ: 3 / matches: 3」の形に寄せた。

1. HTML(head・本文・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = 解析・照合・ハイライト・グループの数え方は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

⚠ 訳すときの縛り: 文が「前置き + 変数 + 後置き」で組み立てられているので、
   **英語も変数の順番を変えずに読める言い回し**にすること(鉄道図のときと同じ)。

使い方: python lab/scripts/make_en_regex_tester.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>正規表現テスタ — 日本語でわかる regex</title>',
     '<title>Regex Tester — with every part of the pattern explained</title>'),

    ('<meta name="description" content="正規表現をその場でテストして、パターンの意味を日本語で解説。'
     'AI(Claude)が作ったブラウザ完結ツール。データは送信されません。">',
     '<meta name="description" content="Live regex testing with a plain-English explanation of '
     'every token in the pattern. Built by an AI (Claude); everything runs in the browser and '
     'nothing is ever sent anywhere.">'),

    # ⚠ フォント指定は日本語版のまま(生成の先行例 palette・csv と同じ扱い)。
    #   英語でも読める並びで、ここを変えると日英で CSS が割れる。
    ('  /* 長さ0のマッチ。塗る中身が無いので細い縦線で位置だけ示す(文字は足さない) */',
     '  /* A zero-length match has nothing to paint, so mark the spot with a thin rule '
     '(no characters are added) */'),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/regex/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/regex/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/regex-tester.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/regex-tester.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/regex/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/regex-tester.html">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n'
     '<meta property="og:locale" content="ja_JP">\n'
     '<meta property="og:title" content="正規表現テスタ — クロードの昼ラボ">\n'
     '<meta property="og:description" content="正規表現をその場でテストして、パターンの意味を日本語で解説。'
     'ブラウザ内で完結し、データは送信されません。">\n'
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/regex/">\n'
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-regex.png">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">\n'
     '<meta property="og:title" content="Regex Tester — with every part of the pattern explained">\n'
     '<meta property="og:description" content="Live regex testing with a plain-English explanation '
     'of every token in the pattern.">\n'
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/regex-tester.html">\n'
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-en-regex.png">'),

    ('<meta name="twitter:title" content="正規表現テスタ — クロードの昼ラボ">\n'
     '<meta name="twitter:description" content="正規表現をその場でテストして、パターンの意味を日本語で解説。'
     'ブラウザ内で完結し、データは送信されません。">\n'
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-regex.png">',
     '<meta name="twitter:title" content="Regex Tester — with every part of the pattern explained">\n'
     '<meta name="twitter:description" content="Live regex testing with a plain-English explanation '
     'of every token in the pattern.">\n'
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-en-regex.png">'),

    ('  "name": "正規表現テスタ",\n'
     '  "url": "https://hirulab-dev.github.io/hirulab-tools/regex/",\n'
     '  "description": "正規表現をその場で試して、パターンの意味を日本語で解説します。",\n'
     '  "applicationCategory": "UtilitiesApplication",\n'
     '  "operatingSystem": "Web browser",\n'
     '  "browserRequirements": "JavaScript が有効なモダンブラウザ",\n'
     '  "inLanguage": "ja",',
     '  "name": "Regex Tester",\n'
     '  "url": "https://hirulab-dev.github.io/hirulab-tools/en/regex-tester.html",\n'
     '  "description": "Live regex testing with a plain-English explanation of every token in the pattern.",\n'
     '  "applicationCategory": "DeveloperApplication",\n'
     '  "operatingSystem": "Web browser",\n'
     '  "browserRequirements": "A modern browser with JavaScript enabled",\n'
     '  "inLanguage": "en",'),

    ('    "priceCurrency": "JPY"', '    "priceCurrency": "USD"'),

    ('  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-regex.png",\n'
     '  "author": {\n'
     '    "@type": "Organization",\n'
     '    "name": "クロードの昼ラボ",\n'
     '    "url": "https://note.com/hirulab"\n'
     '  },\n'
     '  "isPartOf": {\n'
     '    "@type": "WebSite",\n'
     '    "name": "クロードの昼ラボ — ツール置き場",\n'
     '    "url": "https://hirulab-dev.github.io/hirulab-tools/"\n'
     '  }',
     '  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-en-regex.png",\n'
     '  "author": {\n'
     '    "@type": "Organization",\n'
     '    "name": "Claude&#39;s Daytime Lab",\n'
     '    "url": "https://note.com/hirulab"\n'
     '  },\n'
     '  "isPartOf": {\n'
     '    "@type": "WebSite",\n'
     '    "name": "Claude&#39;s Daytime Lab — Tools",\n'
     '    "url": "https://hirulab-dev.github.io/hirulab-tools/en/"\n'
     '  }'),

    ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>\n'
     '  <h1>正規表現テスタ</h1>\n'
     '  <div class="tagline">パターンの意味を日本語で解説しながら、その場でテスト。'
     'すべてブラウザ内で完結し、入力した文字列はどこにも送信されません。</div>',
     '  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab — Tools</a>\n'
     '  <h1>Regex Tester</h1>\n'
     '  <div class="tagline">Test a pattern live while every part of it gets explained in plain '
     'English. Everything runs inside your browser; your text is never sent anywhere.</div>'),

    ('    <label for="pattern">パターン</label>', '    <label for="pattern">Pattern</label>'),

    ('        <label><input type="checkbox" id="fg" checked> g <small>(全部)</small></label>\n'
     '        <label><input type="checkbox" id="fi"> i <small>(大小無視)</small></label>\n'
     '        <label><input type="checkbox" id="fm"> m <small>(複数行)</small></label>\n'
     '        <label><input type="checkbox" id="fs"> s <small>(.が改行も)</small></label>',
     '        <label><input type="checkbox" id="fg" checked> g <small>(all matches)</small></label>\n'
     '        <label><input type="checkbox" id="fi"> i <small>(ignore case)</small></label>\n'
     '        <label><input type="checkbox" id="fm"> m <small>(multiline)</small></label>\n'
     '        <label><input type="checkbox" id="fs"> s <small>(dot matches newline)</small></label>'),

    ('    <h2>このパターンの意味(日本語)</h2>', '    <h2>What this pattern means</h2>'),

    ('    <label for="testtext">テスト文字列</label>',
     '    <label for="testtext">Test string</label>'),

    ('    <textarea id="testtext" spellcheck="false">問い合わせは support@example.com か、'
     '個人あては taro.yamada+work@mail.example.co.jp まで。\n'
     '電話は 045-123-4567。サイトは https://hirulab.example です。</textarea>',
     '    <textarea id="testtext" spellcheck="false">For inquiries, write to support@example.com '
     'or reach me at jane.doe+work@mail.example.co.uk.\n'
     'Call 415-555-0142, or visit https://hirulab.example for details.</textarea>'),

    ('    <div style="margin-top:10px"><label>マッチ箇所ハイライト</label><div id="highlight"></div></div>',
     '    <div style="margin-top:10px"><label>Match highlighting</label><div id="highlight"></div></div>'),

    ('    <h2>マッチ詳細</h2>\n'
     '    <table><thead><tr><th>#</th><th>マッチ</th><th>位置</th><th>グループ</th></tr></thead>'
     '<tbody id="mrows"></tbody></table>',
     '    <h2>Match details</h2>\n'
     '    <table><thead><tr><th>#</th><th>Match</th><th>Index</th><th>Groups</th></tr></thead>'
     '<tbody id="mrows"></tbody></table>'),

    ('    このツールはAI(Anthropic社のClaude)が設計からコードまで自分で書きました。'
     '人間はまだ1文字も直していません。\n'
     '    不具合・要望は昼ラボ(AIの自律実験プロジェクト)まで。',
     '    This tool was designed and coded entirely by an AI (Claude, by Anthropic). '
     'No human has edited a single character yet.\n'
     '    Bugs &amp; requests: reach the hirulab project (an AI autonomy experiment).'),
]

# ── スクリプトの中の文字列リテラル ────────────────────────────────
#
# ⚠ 訳の表は**文字列の中身で引く**ので、同じ日本語は必ず同じ英語になる。
#    「文字列「」そのもの」が i フラグの有無で2通りあるのは、
#    **日本語側で別の文字列にしてある**から書き分けられている。
TR = {
    # プリセット(名前と式。英語圏向けに中身ごと差し替える)
    "メールアドレス": "Email address",
    "日本の電話番号": "US phone number",
    r"0\d{1,4}-\d{1,4}-\d{3,4}": r"\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}",
    "郵便番号": "ZIP code",
    r"\d{3}-\d{4}": r"\d{5}(-\d{4})?",
    "全角カタカナ": "Hex color",
    "[ァ-ヶー]+": r"#[0-9a-fA-F]{6}\b",
    "日付(YYYY-MM-DD)": "Date (YYYY-MM-DD)",

    # 文字クラスの説明
    "数字(0-9)": "a digit (0-9)",
    "数字以外": "anything but a digit",
    "英数字とアンダースコア": "a letter, digit, or underscore",
    "英数字_以外": "anything but a word character",
    "空白文字(スペース・タブ・改行)": "a whitespace character (space, tab, newline)",
    "空白以外": "anything but whitespace",
    "単語の境界": "a word boundary",
    "単語の境界以外": "not a word boundary",
    "改行": "a newline",
    "タブ": "a tab",
    "任意の1文字(改行以外)": "any single character (except newline)",
    "任意の1文字(改行も含む・sフラグ)": "any single character, newline included (s flag)",

    # 量指定子
    "(最短一致)": " (lazy: as few as possible)",
    "0回以上の繰り返し": "repeated 0 or more times",
    "1回以上の繰り返し": "repeated 1 or more times",
    "あってもなくてもよい(0回か1回)": "optional (0 or 1 time)",
    "ちょうど": "exactly ",
    "〜": " to ",
    "回": " times",
    "回以上": " or more times",

    # グループ・アンカー・エスケープ
    #   ⚠ 下の4つは「前置き + 番号 + 中置き + 番号 …」でつながる。英語も同じ順で読めること
    "グループ ": "group ",
    " ここから(あとで \\\\": " starts here (refer to it later as \\\\",
    " や $": " or $",
    " で参照可)": ")",
    "グループここから(番号なし・まとめるだけ)": "non-capturing group starts here (just grouping)",
    "先読み: この先に続くことを確認(消費しない)":
        "lookahead: checks what follows without consuming it",
    "否定先読み: この先に続かないことを確認": "negative lookahead: checks that this does not follow",
    "後読み: この直前にあることを確認": "lookbehind: checks what comes just before",
    "否定後読み: この直前にないことを確認":
        "negative lookbehind: checks that this does not come just before",
    "名前付きグループ ": "named group ",
    " ここから": " starts here",
    "グループここまで": "group ends here",
    "または(左右どちらかにマッチ)": "or (either the left side or the right side)",
    "行の先頭(mフラグ)": "start of a line (m flag)",
    "文字列の先頭": "start of the string",
    "行の末尾(mフラグ)": "end of a line (m flag)",
    "文字列の末尾": "end of the string",
    "次の文字以外の1文字: ": "any single character except these: ",
    "次のうちの1文字: ": "any single one of these: ",
    "グループ": "the same text as group ",
    "と同じ文字列": "",
    "8進エスケープ(制御文字)。グループが":
        "octal escape (a control character) — the pattern only has ",
    "個しか無いので後方参照にはならない": " group(s), so this is not a backreference",
    "文字「": "the character ",
    "」そのもの(エスケープ)": " itself (escaped)",
    "文字列「": "the text ",
    "」そのもの(大小どちらでも・iフラグ)": " itself, in either case (i flag)",
    "」そのもの": " itself",

    # 画面の状態
    "パターンエラー: ": "Pattern error: ",
    "件で打ち切りました)": " matches, stopped counting there)",
    "(表は先頭": "(table shows the first ",
    "件)": ")",
    "(うち長さ0が": "(zero-length: ",
    "マッチ: ": "matches: ",
    "マッチなし": "no matches",
}

KEEP = set()


def en_nav(docs):
    import en_nav as _en_nav
    return _en_nav.build(docs, "regex-why.html", "Why doesn&#39;t my regex match?",
                         "regex-tester.html", "../regex/")


def translate_literals(src, tr, keep):
    """JS を1文字ずつ読み、**文字列リテラルの中身だけ**を辞書と完全一致で差し替える。"""
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
    m = re.search(r"<script>\n\"use strict\";\n(.*)</script>", html, re.S)
    if not m:
        sys.exit("本体のスクリプトが見つかりません")
    return m.start(1), m.end(1)


def code_japanese(src):
    """文字列でもコメントでも正規表現でもない日本語(=識別子として書かれた日本語)。"""
    skeleton = blank(src, blank_regex=True)
    return [skeleton[max(0, m.start() - 20):m.start() + 20].replace("\n", " ")
            for m in JA_CHARS.finditer(skeleton)]


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "regex" / "index.html"
    en_path = docs / "en" / "regex-tester.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'    <nav class="hl-nav">.*?\n  </nav>', en, re.S)
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

    # (2) スクリプトの中: 日本語を含むリテラルは KEEP のものだけ
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
    print("わざと日本語のまま残したリテラル: %d 件" % len(kept))
    print("画面に出るところの日本語: 0箇所")
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
