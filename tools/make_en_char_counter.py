#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「文字数カウンタ」の英語版を、日本語版から作る(2026-09-03 朝)。

**手書きの英語版を生成に置き換えた4本目**(palette 9/1 → csv 9/1 → regex-tester 9/2 → これ)。
残る手書きは `timezone` の1本。

## なぜ置き換えるか

手書きの英語版には照合の仕組みが無いので、**日本語版だけが育って英語版が置いていかれる**。
実例が2つ出ている: `en/palette.html` に看板機能がまるごと無かった / `en/csv.html` の見本が
文字コード判定を1度も動かさない形だった。どちらも**6日以上、誰も気づいていなかった**。

## 置き換える前に、日英で違う理由の無い差を先に消した

手書き版との差は6行あったが、**中身の差は1つだけ**で、あとは名前が違うだけだった。
先に日本語版の側を英語版に合わせて、差を1つに減らしてある(この3つは 9/3 朝に実施):

- `jpChars` → `cjkChars`(数えているのは仮名・漢字・全角記号なので **CJK のほうが正確**)
- `c-genko` → `c-pages`(id は画面に出ない。日英どちらの意味でも「ページ数」で通る)
- `x-jp` → `x-over`(超過の表示。日本語という意味は無かった)

## 残った1つの差は、消さずに固定する

    ja: 原稿用紙(400字詰め)が何枚ぶんか   = 空白を除いた文字数 / 400
    en: 書籍のページ(1ページ約250語)が何枚ぶんか = 単語数 / 250

**原稿用紙は日本語圏の単位で、英語に訳しても意味が無い**(逆も同じ)。
だから「日英でコードが1バイトも違わない」の縛りをここだけ緩めて、
**差の数を固定する**(`CODE_DIFF` が1件。増えれば生成が止まる)。
9/3 未明に `HTML_DIFF_OK` でやったのと同じ考え方 —
**「違ってよい」ではなく「いくつ違うかを固定する」**。

使い方: python lab/scripts/make_en_char_counter.py <リポジトリの docs>
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
OGP = BASE + "ogp/ogp-en-char-counter.png"

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>文字数カウンタ — X換算・原稿用紙換算つき</title>',
     '<title>Character Counter &mdash; with X (Twitter) weighted count</title>'),

    ('<meta name="description" content="文字数・単語数・行数に加え、X(旧Twitter)の重み付きカウントや原稿用紙換算まで一目でわかる。AI(Claude)が作ったブラウザ完結ツール。データは送信されません。">',
     '<meta name="description" content="Characters, words, lines, paragraphs, reading time, and the weighted character count X (Twitter) actually uses. Built by an AI (Claude). Runs entirely in your browser &mdash; nothing is sent anywhere.">'),

    ('<link rel="canonical" href="%schar-counter/">\n'
     '<link rel="alternate" hreflang="ja" href="%schar-counter/">\n'
     '<link rel="alternate" hreflang="en" href="%sen/char-counter.html">' % (BASE, BASE, BASE),
     '<link rel="canonical" href="%sen/char-counter.html">\n'
     '<link rel="alternate" hreflang="en" href="%sen/char-counter.html">\n'
     '<link rel="alternate" hreflang="ja" href="%schar-counter/">' % (BASE, BASE, BASE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">'),
    ('<meta property="og:locale" content="ja_JP">',
     '<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="文字数カウンタ — クロードの昼ラボ">',
     '<meta property="og:title" content="Character Counter &mdash; words, reading time and X weighted count">'),
    ('<meta property="og:description" content="文字数・行数・段落数を数えます。Xの重み付きカウント、原稿用紙換算、読了時間の目安つき。">',
     '<meta property="og:description" content="Characters, words, reading time, and the weighted count X actually uses &mdash; CJK rules included.">'),
    ('<meta property="og:url" content="%schar-counter/">' % BASE,
     '<meta property="og:url" content="%sen/char-counter.html">' % BASE),
    ('<meta property="og:image" content="%sogp/ogp-char-counter.png">' % BASE,
     '<meta property="og:image" content="%s">' % OGP),

    ('<meta name="twitter:title" content="文字数カウンタ — クロードの昼ラボ">',
     '<meta name="twitter:title" content="Character Counter &mdash; words, reading time and X weighted count">'),
    ('<meta name="twitter:description" content="文字数・行数・段落数を数えます。Xの重み付きカウント、原稿用紙換算、読了時間の目安つき。">',
     '<meta name="twitter:description" content="Characters, words, reading time, and the weighted count X actually uses &mdash; CJK rules included.">'),
    ('<meta name="twitter:image" content="%sogp/ogp-char-counter.png">' % BASE,
     '<meta name="twitter:image" content="%s">' % OGP),

    # JSON-LD。⚠ `<script>` の中は生テキストなので**実体参照を書かない**
    #   (2026-09-02 昼に英語12ページで `Claude&#39;s` がそのまま構造化データに渡っていた)
    ('  "name": "文字数カウンタ",', '  "name": "Character Counter",'),
    ('  "url": "%schar-counter/",' % BASE, '  "url": "%sen/char-counter.html",' % BASE),
    ('  "description": "文字数・行数・段落数に加えて、Xの重み付きカウント・原稿用紙換算・読了時間を出します。",',
     '  "description": "Characters, words, reading time, and the weighted count X actually uses — CJK rules included.",'),
    ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
     '  "browserRequirements": "A modern browser with JavaScript enabled",'),
    ('  "inLanguage": "ja",', '  "inLanguage": "en",'),
    ('    "priceCurrency": "JPY"', '    "priceCurrency": "USD"'),
    ('  "image": "%sogp/ogp-char-counter.png",' % BASE, '  "image": "%s",' % OGP),
    ('''    "name": "クロードの昼ラボ",
    "url": "https://note.com/hirulab"''',
     '''    "name": "Claude's Daytime Lab",
    "url": "https://note.com/hirulab"'''),
    ('''    "name": "クロードの昼ラボ — ツール置き場",
    "url": "%s"''' % BASE,
     '''    "name": "Claude's Daytime Lab — Tools",
    "url": "%sen/"''' % BASE),

    # 本文
    ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>',
     '  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab — Tools</a>'),
    ('  <h1>文字数カウンタ</h1>', '  <h1>Character Counter</h1>'),
    ('  <div class="tagline">貼るだけで、文字数・X(旧Twitter)換算・原稿用紙換算まで一目で。すべてブラウザ内で完結し、入力した文章はどこにも送信されません。</div>',
     '  <div class="tagline">Paste your text and get every count at a glance &mdash; including the weighted count X (Twitter) actually uses. Everything runs inside your browser; your text is never sent anywhere.</div>'),
    ('<textarea id="src" placeholder="ここに文章を貼り付け(または入力)" spellcheck="false"></textarea>',
     '<textarea id="src" placeholder="Paste or type your text here" spellcheck="false"></textarea>'),

    ('<div class="label">文字数(改行・空白込み)</div>',
     '<div class="label">Characters (incl. spaces)</div>'),
    ('<div class="label">文字数(空白・改行除く)</div>',
     '<div class="label">Characters (no spaces)</div>'),
    ('<div class="label">行数</div>', '<div class="label">Lines</div>'),
    ('<div class="label">段落数</div>', '<div class="label">Paragraphs</div>'),
    ('<div class="label">英単語数</div>', '<div class="label">Words</div>'),
    # ★ここが「日英で意味の違う唯一のカード」。中身の差は CODE_DIFF のほうで固定してある
    ('<div class="card"><div class="label">原稿用紙(400字)</div><div class="value" id="c-pages">0枚</div></div>',
     '<div class="card"><div class="label">Book pages (~250 words)</div><div class="value" id="c-pages">0</div></div>'),

    ('      <div class="label">X(旧Twitter)の重み付きカウント — 公式の数え方(URLは一律23・絵文字は1つで2)</div>',
     '      <div class="label">X (Twitter) weighted count &mdash; the official rule (any URL = flat 23, an emoji = 2)</div>'),
    ('      <div class="note">無料アカウントの上限280(日本語だと実質140字)。超過分は下書きを分割。※仕様変更がありえます</div>',
     '      <div class="note">280 is the limit for free accounts (CJK text effectively 140). Split your draft if you are over. Rules may change.</div>'),
    ('''      <div class="note">★<strong>「全角なら2」ではありません。</strong>重みが1になるのは符号位置 0–4351 と、
        8192–8205 / 8208–8223 / 8242–8247 の3つの区間だけです(Xが公開している設定 v3)。
        だから <code>…</code> <code>€</code> <code>→</code> やベトナム語の <code>ế</code> は、
        半角に見えても2で数えられます。絵文字は書記素クラスタ1つで2(肌の色・ZWJ・国旗をつないでも増えません)。</div>''',
     '''      <div class="note">★<strong>It is not &ldquo;full-width counts 2&rdquo;.</strong> Only code points 0&ndash;4351 and the
        three ranges 8192&ndash;8205 / 8208&ndash;8223 / 8242&ndash;8247 weigh 1 (X&rsquo;s published configuration v3).
        So <code>&hellip;</code>, <code>&euro;</code>, <code>&rarr;</code> and Vietnamese <code>&#7871;</code>
        weigh 2 even though they look narrow. An emoji weighs 2 per grapheme cluster &mdash; skin tone, ZWJ and flags do not add.</div>'''),

    ('      <div class="label">読了時間の目安(日本語 500字/分・英語 200語/分で計算)</div>',
     '      <div class="label">Estimated reading time (200 words/min English, 500 chars/min CJK)</div>'),
    # 初期値。JS が入力のたびに書き換えるが、読み込み直後の一瞬はこれが出る
    ('      <div class="value" id="c-time">0分</div>',
     '      <div class="value" id="c-time">0 min</div>'),

    ('      <a href="../">道具箱のトップ</a> ・', '      <a href="./">Tools index</a> ·'),
    ('      <a href="https://note.com/hirulab">実験ログ（note）</a> ・',
     '      <a href="https://note.com/hirulab">Experiment log (note, JP)</a> ·'),
    ('      <a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>',
     '      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>'),

    ('''    このツールはAI(Anthropic社のClaude)が設計からコードまで自分で書きました。人間はまだ1文字も直していません。
    不具合・要望は昼ラボ(AIの自律実験プロジェクト)まで。''',
     '''    This tool was designed and coded entirely by an AI (Claude, by Anthropic). No human has edited a single character yet.
    Bugs &amp; requests: reach the hirulab project (an AI autonomy experiment).'''),
]

# ★日英で意味が違うので、消さずに数を固定する差。
#   (ja側の行, en側の行, なぜ違ってよいか)
CODE_DIFF = [
    ('  $("c-pages").textContent = (noWs.length ? Math.ceil(noWs.length / 400) : 0) + "枚";',
     '  $("c-pages").textContent = words ? Math.ceil(words / 250).toLocaleString() : 0;',
     "原稿用紙(400字詰め)は日本語圏の単位で、英語では書籍のページ(約250語)が対応する。"
     "単位そのものが違うので、訳ではなく別の式になる"),
]

# JS のコメント(2026-09-03 昼 追加)。それまで**訳していなかった**ので、
# 英語ページのソースに日本語の注釈が3行そのまま載っていた。⚠ 訳は行数を変えないこと
COMMENTS = {
    '// Xの数え方(twitter-text の公開設定 v3)。「全角なら2」ではない。':
    "// How X counts (twitter-text's published configuration v3). It is not \"full-width counts 2\".",
    '// 重みが1になるのはこの4つの範囲の符号位置だけで、それ以外はすべて2。':
    '// Only code points in these four ranges weigh 1; everything else weighs 2.',
    '// 絵文字は書記素クラスタ1つで2(肌の色・ZWJ・国旗をつないでも増えない)。URLは長さによらず23。':
    '// An emoji weighs 2 per grapheme cluster (skin tone, ZWJ and flags do not add). Any URL counts 23.',
    '// 古いブラウザでは符号位置ごと(絵文字は多めに出る)':
    '// Older browsers fall back to per-code-point counting (emoji come out high)',
    '// URLを23枠のプレースホルダに': '// Replace each URL with a 23-wide placeholder',
}

# スクリプトの中の文字列リテラル。中身の完全一致で差し替える
TR = {
    "(超過)": "(over)",
    "0分": "0 min",
    "1分未満": "under 1 min",
    "分": " min",
}

# わざと日本語のまま残すリテラル(理由つき)。今回は0件。
# ⚠ 文字の範囲 `[　-ヿ一-鿿＀-￯]` は**正規表現**なので `literals` の対象外
#   (数える対象そのもので、訳したら道具が壊れる)
KEEP = set()


def en_nav(docs):
    """英語ナビを**実ページから**組み直す(`en_nav.build`)。生成元がずれようがない。"""
    import en_nav as _en_nav
    return _en_nav.build(docs, "regex-tester.html", "Regex Tester",
                         "char-counter.html", "../char-counter/")


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                        else pathlib.Path.home() / "hirulab-tools" / "docs")
    ja_path = docs / "char-counter" / "index.html"
    en_path = docs / "en" / "char-counter.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    for a, b, _why in CODE_DIFF:
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

    # ★コメントにも日本語が残っていないこと(2026-09-03 昼 追加)
    ja_com = [c for c in comments(en[s2:e2]) if JA_CHARS.search(c)]
    if ja_com:
        sys.exit("コメントに日本語が %d 件残っています: %s" % (len(ja_com), ja_com[0][:120]))

    # (4) 文字列の中身を空にすると、日英でコードが一致すること。
    #     ★このページだけは CODE_DIFF のぶん**違う行があってよい**。ただし
    #     「何行違うか」と「どの行がどう違うか」の両方を固定する。
    sj, ej = script_span(ja)
    a, b = blank(ja[sj:ej]), blank(en[s2:e2])
    la, lb = a.split("\n"), b.split("\n")
    if len(la) != len(lb):
        sys.exit("コードの行数が違います(ja %d / en %d)" % (len(la), len(lb)))
    want = {(blank(x), blank(y)) for x, y, _w in CODE_DIFF}
    diffs = [(i + 1, x, y) for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    for i, x, y in diffs:
        if (x, y) not in want:
            sys.exit("固定してある差ではないコードの違いです(%d行目):\n  ja: %s\n  en: %s" % (i, x, y))
    if len(diffs) != len(CODE_DIFF):
        sys.exit("固定してある差は %d 件ですが、実際に違うのは %d 行です"
                 % (len(CODE_DIFF), len(diffs)))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("訳した文字列: %d 件" % len(TR))
    print("画面に出るところの日本語: 0箇所")
    print("文字列でない日本語: 0箇所")
    print("わざと残した日本語のリテラル: %d 件" % len(set(kept)))
    print("文字列の中身を空にしたコード: %d バイト中、意図して違う行が %d 行(それ以外は完全一致)"
          % (len(a.encode()), len(diffs)))
    for _i, _x, _y in diffs:
        pass
    for _a, _b, why in CODE_DIFF:
        print("  違ってよい理由: %s" % why)


if __name__ == "__main__":
    main()
