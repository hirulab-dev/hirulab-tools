#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""25本目「和柄シームレスパターン作成」の英語版を、日本語版から作る(2026-09-02 朝)。

`make_en_railroad.py` 以降と同じ方式。**日本語版が唯一の原本**で、手で両方を直すことはしない。

★この道具は **うちで初めて「英語版を持たない道具」として公開したもの**(9/1夜)。
  そのために `add_tool_link.py --no-en` を新設した経緯がある。
  ここで英語版を出すので、**その足し戻し**(ENナビへの1行・JP側の hreflang・言語リンク・sitemap)も
  同じ枠でやること。片方だけやると「英語版があるのに日本語ページからのリンクが無い」
  = 8/28 に `base64` と `qr` で実際に起きた形になる。

★訳の方針: **柄の名前はローマ字を先に置き、英語の説明を括弧で添える**
  ("Seigaiha (blue ocean waves)")。理由は2つ。
  (a) 英語圏でこの柄を探している人は "seigaiha" "asanoha" "sashiko" で探す
      (sales-map v2 で "sashiko pattern generator" の実需を確認している)
  (b) 括弧の説明が無いと、探していない人には何の絵か分からない
  ⚠ ローマ字だけ・英訳だけのどちらか片方に寄せると、上のどちらかを落とす。

1. HTML(head・本文・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = 作図の幾何・周期の計算・SVGの組み立ては1バイトも違わない
   (この道具の主張「継ぎ目なく繋がる」は幾何そのものなので、
    ここが一致していれば `test_pattern_tool.py` の検証がそのまま英語版にも効く)
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

⚠ 訳すときの縛り: 自己検査の文が「前置き + 数 + 後置き」で組み立てられているので、
   **英語も変数の順番を変えずに読める言い回し**にすること(鉄道図のときと同じ)。

使い方: python lab/scripts/make_en_pattern.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

BASE = "https://hirulab-dev.github.io/hirulab-tools"

EN_TITLE = ("Japanese Pattern Generator — seamless seigaiha, asanoha, "
            "sashiko tiles as SVG/PNG")
EN_DESC = ("Generate seamless Japanese patterns in your browser and download them as SVG or PNG. "
           "Seigaiha, asanoha, kikkou, ichimatsu, yagasuri, shippou, uroko and sashiko. "
           "Each result is checked for seamlessness on the spot and the check is shown to you. "
           "No uploads, no sign-up, free for commercial use.")
EN_SHORT = ("Eight Japanese patterns, drawn from geometry rather than a generative image model, "
            "saved as SVG or PNG. Seamlessness is verified on every render and shown to you.")

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>和柄シームレスパターン作成 — 青海波・麻の葉・刺し子のジェネレーター | 昼ラボ</title>',
     '<title>%s</title>' % EN_TITLE),

    ('<meta name="description" content="和柄のシームレスパターンをブラウザで生成してSVG/PNGで'
     'ダウンロード。青海波・麻の葉・亀甲・市松・矢絣・七宝・鱗・刺し子。継ぎ目が無いことを'
     '生成のたびにその場で検証して表示します。通信ゼロ・無料。">',
     '<meta name="description" content="%s">' % EN_DESC),

    # canonical / hreflang。日本語版に hreflang を足したうえで、ここで向きを入れ替える
    ('<link rel="canonical" href="%s/pattern/">\n'
     '<link rel="alternate" hreflang="ja" href="%s/pattern/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/pattern.html">' % (BASE, BASE, BASE),
     '<link rel="canonical" href="%s/en/pattern.html">\n'
     '<link rel="alternate" hreflang="ja" href="%s/pattern/">\n'
     '<link rel="alternate" hreflang="en" href="%s/en/pattern.html">' % (BASE, BASE, BASE)),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n'
     '<meta property="og:locale" content="ja_JP">\n'
     '<meta property="og:title" content="和柄シームレスパターン作成 — 青海波・麻の葉・刺し子のジェネレーター">\n'
     '<meta property="og:description" content="和柄のシームレスパターンをブラウザで生成してSVG/PNGで'
     '保存できます。青海波・麻の葉・亀甲・市松・矢絣・七宝・鱗・刺し子。継ぎ目が無いことを生成のたびに'
     'その場で検証して表示します。通信は一切行いません。">\n'
     '<meta property="og:url" content="%s/pattern/">\n'
     '<meta property="og:image" content="%s/ogp/ogp-pattern.png">' % (BASE, BASE),
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">\n'
     '<meta property="og:title" content="Japanese Pattern Generator — seigaiha, asanoha, sashiko">\n'
     '<meta property="og:description" content="%s">\n'
     '<meta property="og:url" content="%s/en/pattern.html">\n'
     '<meta property="og:image" content="%s/ogp/ogp-pattern-en.png">' % (EN_SHORT, BASE, BASE)),

    ('<meta name="twitter:title" content="和柄シームレスパターン作成 — 青海波・麻の葉・刺し子のジェネレーター">\n'
     '<meta name="twitter:description" content="8種類の和柄をその場で生成してSVG/PNGで保存。'
     '継ぎ目が無いことを生成のたびに検証して見せます。通信は一切行いません。">\n'
     '<meta name="twitter:image" content="%s/ogp/ogp-pattern.png">' % BASE,
     '<meta name="twitter:title" content="Japanese Pattern Generator — seigaiha, asanoha, sashiko">\n'
     '<meta name="twitter:description" content="Eight Japanese patterns generated on the spot and '
     'saved as SVG or PNG. Seamlessness is verified on every render. Nothing is ever uploaded.">\n'
     '<meta name="twitter:image" content="%s/ogp/ogp-pattern-en.png">' % BASE),

    ('  "name": "和柄シームレスパターン作成",\n'
     '  "url": "%s/pattern/",\n'
     '  "description": "青海波・麻の葉・亀甲・市松・矢絣・七宝・鱗・刺し子の8種類の和柄を、'
     '幾何を計算して描くシームレスパターンとして生成します。配色・細かさ・線の太さを変えて、'
     'SVG(4000px)またはPNGで保存できます。差別化点は、継ぎ目なく繋がることを言葉で主張するのではなく、'
     'タイルの周期ぶんずらして一致するかをその場で検証して画面に出すことです。'
     '生成AIの画像出力ではなくプログラムによる作図で、ブラウザ内で完結し、'
     '入力はどこにも送信されません。",\n'
     '  "applicationCategory": "DesignApplication",\n'
     '  "operatingSystem": "Web browser",\n'
     '  "browserRequirements": "JavaScript が有効なモダンブラウザ",\n'
     '  "inLanguage": "ja",' % BASE,
     '  "name": "Japanese Pattern Generator",\n'
     '  "url": "%s/en/pattern.html",\n'
     '  "description": "Generates eight traditional Japanese patterns — seigaiha, asanoha, kikkou, '
     'ichimatsu, yagasuri, shippou, uroko and sashiko — as seamless tiles drawn from geometry. '
     'Colourway, scale and stroke weight are adjustable, and the result saves as SVG (4000px) or PNG. '
     'What sets it apart is that seamlessness is not claimed in words: the tile period is checked '
     'against the canvas on every render and the check is shown on screen. The artwork is drawn by '
     'code, not by a generative image model, everything runs inside the browser, and nothing you '
     'enter is ever sent anywhere.",\n'
     '  "applicationCategory": "DesignApplication",\n'
     '  "operatingSystem": "Web browser",\n'
     '  "browserRequirements": "A modern browser with JavaScript enabled",\n'
     '  "inLanguage": "en",' % BASE),

    ('"priceCurrency": "JPY"', '"priceCurrency": "USD"'),

    ('  "image": "%s/ogp/ogp-pattern.png",\n'
     '  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },\n'
     '  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "%s/" }'
     % (BASE, BASE),
     '  "image": "%s/ogp/ogp-pattern-en.png",\n'
     '  "author": { "@type": "Organization", "name": "Claude\'s Daytime Lab", "url": "https://note.com/hirulab" },\n'
     '  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — Tools", "url": "%s/en/" }'
     % (BASE, BASE)),

    ('<h1>和柄シームレスパターン作成</h1>\n'
     '<p class="lead">青海波・麻の葉・亀甲・市松・矢絣・七宝・鱗・刺し子のタイルパターンを'
     'その場で生成し、SVG / PNG で保存できます。すべてブラウザ内で完結し、通信は一切行いません。</p>',
     # ⚠ ここに `<a class="hl-back">` を置いてはいけない。**このページの CSS には
     #    `.hl-back` の規則が無い**(日本語版が hl-back を持たないため)ので、
     #    既定の青リンクになり、ダークで 1.89:1 = AA不合格になる。実際に1度出した。
     #    道具箱への戻り導線はナビ下の「Tools index」が持っている。
     '<h1>Japanese Pattern Generator</h1>\n'
     '<p class="lead">Seigaiha, asanoha, kikkou, ichimatsu, yagasuri, shippou, uroko and sashiko, '
     'generated as seamless tiles and saved as SVG or PNG. Everything runs inside your browser; '
     'nothing is ever sent anywhere.</p>'),

    ('    <label>柄 <select id="pat"></select></label>\n'
     '    <label>配色 <select id="preset"></select></label>\n'
     '    <label>地 <input type="color" id="cbg" value="#1b3a5b"></label>\n'
     '    <label>柄色 <input type="color" id="cfg" value="#f2ede3"></label>\n'
     '    <label>差し色 <input type="color" id="cac" value="#f2ede3"></label>',
     '    <label>Pattern <select id="pat"></select></label>\n'
     '    <label>Colourway <select id="preset"></select></label>\n'
     '    <label>Ground <input type="color" id="cbg" value="#1b3a5b"></label>\n'
     '    <label>Line <input type="color" id="cfg" value="#f2ede3"></label>\n'
     '    <label>Accent <input type="color" id="cac" value="#f2ede3"></label>'),

    ('    <label>細かさ <select id="size"><option value="0">細かい</option>'
     '<option value="1" selected>標準</option><option value="2">大きい</option></select></label>\n'
     '    <label>線の太さ <input type="range" id="stroke" min="60" max="160" value="100" step="10"></label>\n'
     '    <span class="checkbox-note">寸法は「キャンバスを割り切る値」だけに制限しています'
     '(だから必ず継ぎ目なく繋がります)</span>',
     '    <label>Scale <select id="size"><option value="0">Fine</option>'
     '<option value="1" selected>Standard</option><option value="2">Large</option></select></label>\n'
     '    <label>Stroke weight <input type="range" id="stroke" min="60" max="160" value="100" step="10"></label>\n'
     '    <span class="checkbox-note">Sizes are restricted to values that divide the canvas exactly, '
     'which is why the tiles always meet without a seam</span>'),

    ('    <button class="primary" id="dlsvg">SVGを保存(4000px)</button>\n'
     '    <button id="dlpng">PNGを保存</button>',
     '    <button class="primary" id="dlsvg">Save SVG (4000px)</button>\n'
     '    <button id="dlpng">Save PNG</button>'),

    ('<div id="preview" role="img" aria-label="生成したパターンをタイル状に敷き詰めたプレビュー"></div>\n'
     '<p class="checkbox-note">↑ プレビューは1枚のタイルを繰り返し敷き詰めた実物表示です。'
     '継ぎ目が見えなければ、それがそのまま検証結果です。</p>',
     '<div id="preview" role="img" aria-label="Preview of the generated pattern tiled across the area"></div>\n'
     '<p class="checkbox-note">↑ The preview is one tile repeated for real, not a mock-up. '
     'If you cannot see a seam, that is the result of the check.</p>'),

    ('  <p>この道具はAI(Claude)がプログラムで作りました。柄も生成AIの画像出力ではなく、'
     '幾何を計算して描いています。生成した画像は商用を含め自由にお使いください(帰属表示不要)。</p>\n'
     '  <p>調整済みの配色パック(SVG+PNG一式)はストアにあります → '
     '<a href="https://hirulab.gumroad.com" rel="noopener">hirulab.gumroad.com</a></p>',
     '  <p>This tool was written by an AI (Claude). The patterns are drawn by computing their '
     'geometry, not by a generative image model. Use anything you generate freely, including '
     'commercially, with no attribution required.</p>\n'
     '  <p>Ready-made colourway packs (SVG + PNG) are in the store → '
     '<a href="https://hirulab.gumroad.com" rel="noopener">hirulab.gumroad.com</a></p>'),
]

# ── スクリプトの中の文字列リテラル ────────────────────────────────
#
# ⚠ 訳の表は**文字列の中身で引く**ので、同じ日本語は必ず同じ英語になる。
#    この道具は言葉が LBL の1ブロックに集めてあるので、訳す対象はそこだけ。
TR = {
    # 柄の名前。ローマ字 + 括弧で英語の説明(上の「訳の方針」参照)
    "青海波": "Seigaiha (blue ocean waves)",
    "麻の葉": "Asanoha (hemp leaf)",
    "亀甲": "Kikkou (tortoise shell)",
    "市松": "Ichimatsu (checkerboard)",
    "矢絣": "Yagasuri (arrow fletching)",
    "七宝": "Shippou (seven treasures)",
    "鱗": "Uroko (fish scales)",
    "刺し子": "Sashiko (running stitch)",

    # 配色
    "藍": "Indigo",
    "夜金": "Night gold",
    "紅金": "Red and gold",
    "カスタム": "Custom",

    # 自己検査の文。⚠ 数の位置は日本語版と同じ順のまま読める言い回しにすること
    #   ja: この柄のタイル周期は 200 × 100 px。キャンバス2000pxをそれぞれ 10 × 20 分割し、…
    #   en: The tile period is 200 × 100 px, which divides the 2000px canvas into 10 × 20 parts, …
    "シームレス検証(この生成結果に対する検査)": "Seamlessness check (run on this exact result)",
    "この柄のタイル周期は ": "The tile period of this pattern is ",
    " px。キャンバス2000pxをそれぞれ ": " px, which divides the 2000px canvas into ",
    " 分割し、どちらも整数で割り切れます。": " parts, both of them whole numbers.",
    "= 端と端が必ず一致し、継ぎ目は構造的に生じません ✓":
        "= the opposite edges must line up, so a seam cannot occur by construction ✓",
}

KEEP = set()

# ナビの下に置く英語のリンク行(日本語版の hl-links にあたるもの)。
# `en_nav.build` は <ul> までしか組まないので、ここで足す。
EN_LINKS = """    <p class="hl-links">
      <a href="./">Tools index</a> &middot;
      <a href="https://note.com/hirulab">Experiment log (JP)</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>"""


def en_nav(docs):
    import en_nav as _en_nav
    nav = _en_nav.build(docs, "base64.html", "Base64 &amp; Data URL Explainer",
                        "pattern.html", "../pattern/")
    return nav[:-len("\n  </nav>")] + "\n" + EN_LINKS


def script_span(html):
    m = re.search(r"<script>\n(.*)</script>", html, re.S)
    if not m:
        sys.exit("本体のスクリプトが見つかりません")
    return m.start(1), m.end(1)


def code_japanese(src):
    """文字列でもコメントでも正規表現でもない日本語(=識別子として書かれた日本語)。"""
    skeleton = blank(src, blank_regex=True)
    return [skeleton[max(0, m.start() - 20):m.start() + 20].replace("\n", " ")
            for m in JA_CHARS.finditer(skeleton)]


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
            if j < 0:
                out.append(src[i:])
                break
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


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "pattern" / "index.html"
    en_path = docs / "en" / "pattern.html"
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
    #     = 作図の幾何と周期の計算は1バイトも違わない(検証がそのまま効く根拠)
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
