#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「画像リサイズ・圧縮」の英語版を、日本語版から作る(2026-08-28)。

`make_en_contrast.py` と同じ方式(ナビは実行時に実ページから組み立てるので差し替え元を持たない)。
**日本語版が唯一の原本**で、英語版を手で直すことはしない。

1. HTML(head・本文・details・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = 段階的な縮小・canvas への描き直し・形式変換・削減率の計算は日英で1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

使い方: python lab/scripts/make_en_image.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals
from make_en_contrast import translate_literals, script_span
from en_common import translate_comments

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>画像リサイズ・圧縮 — アップロードしない画像圧縮</title>',
     '<title>Image Resizer &amp; Compressor — nothing is uploaded</title>'),

    ('<meta name="description" content="画像のリサイズと圧縮を、ブラウザの中だけで行います。ファイルはどこにもアップロードされません。JPEG/PNG/WebPに変換、複数枚まとめて処理、圧縮率もその場で確認。AI(Claude)が作ったツール。">',
     '<meta name="description" content="Resizes and compresses images entirely inside your browser. Nothing is uploaded anywhere. Convert to JPEG, PNG or WebP, process several files at once, and see how much smaller each one got. Built by an AI (Claude).">'),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/image/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/image/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/image.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/image.html">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/image.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/image/">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n<meta property="og:locale" content="ja_JP">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n<meta property="og:locale" content="en_US">'),

    ('<meta property="og:title" content="画像リサイズ・圧縮 — クロードの昼ラボ">',
     '<meta property="og:title" content="Image Resizer &amp; Compressor">'),

    ('<meta property="og:description" content="画像を軽くしてサイズを変えます。端末内で完結し、画像はどこにもアップロードされません。">',
     '<meta property="og:description" content="Makes images smaller and changes their size. Everything happens on your device and no image is ever uploaded.">'),

    ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/image/">',
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/image.html">'),

    ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-image.png">',
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-image-en.png">'),

    ('<meta name="twitter:title" content="画像リサイズ・圧縮 — クロードの昼ラボ">',
     '<meta name="twitter:title" content="Image Resizer &amp; Compressor">'),

    ('<meta name="twitter:description" content="画像を軽くしてサイズを変えます。端末内で完結し、画像はどこにもアップロードされません。">',
     '<meta name="twitter:description" content="Makes images smaller and changes their size. Nothing leaves your device.">'),

    ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-image.png">',
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-image-en.png">'),

    ('''  "name": "画像リサイズ・圧縮",
  "url": "https://hirulab-dev.github.io/hirulab-tools/image/",
  "description": "画像のサイズ変更と圧縮をブラウザ内で行います。画像はどこにもアップロードされません。",
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
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-image.png",
  "author": {
    "@type": "Organization",
    "name": "クロードの昼ラボ",
    "url": "https://note.com/hirulab"
  },
  "isPartOf": {
    "@type": "WebSite",
    "name": "クロードの昼ラボ — ツール置き場",
    "url": "https://hirulab-dev.github.io/hirulab-tools/"
  }''',
     '''  "name": "Image Resizer & Compressor",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/image.html",
  "description": "Resizes and compresses images inside the browser. No image is ever uploaded anywhere.",
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
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-image-en.png",
  "author": {
    "@type": "Organization",
    "name": "Claude's Daytime Lab",
    "url": "https://note.com/hirulab"
  },
  "isPartOf": {
    "@type": "WebSite",
    "name": "Claude\'s Daytime Lab — Tools",
    "url": "https://hirulab-dev.github.io/hirulab-tools/en/"
  }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>画像リサイズ・圧縮</h1>
  <div class="tagline">サイズを変えて、軽くして、形式を変換します。複数枚まとめて処理できます。</div>
  <div class="privacy">
    <strong>画像はアップロードされません。</strong>
    このページには通信するコードが1行も入っていません(fetch も XMLHttpRequest も使っていません)。
    処理はすべてあなたの端末の中で完結し、画像がこの端末から出ることはありません。
    <strong>読み込んだあとは、機内モードにしても普通に動きます。</strong>試してみてください。
  </div>''',
     '''  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab &mdash; tools</a>
  <h1>Image Resizer &amp; Compressor</h1>
  <div class="tagline">Change the size, make the file smaller, convert the format. Several images at once.</div>
  <div class="privacy">
    <strong>Your images are not uploaded.</strong>
    There is not a single line of networking code on this page (no fetch, no XMLHttpRequest).
    Everything happens on your own device, and no image ever leaves it.
    <strong>Once the page has loaded it keeps working in aeroplane mode.</strong> Try it.
  </div>'''),

    ('''  <div class="drop" id="drop" tabindex="0" role="button" aria-label="画像を選ぶ">
    <div class="big">画像をドロップ、またはクリックして選択</div>
    <div class="sub">JPEG / PNG / WebP / GIF / BMP — 複数枚まとめてOK</div>''',
     '''  <div class="drop" id="drop" tabindex="0" role="button" aria-label="Choose images">
    <div class="big">Drop images here, or click to choose</div>
    <div class="sub">JPEG / PNG / WebP / GIF / BMP &mdash; several at once is fine</div>'''),

    ('''      <div class="label">サイズの決め方</div>
      <select id="mode">
        <option value="longest">長辺を指定</option>
        <option value="width">幅を指定</option>
        <option value="height">高さを指定</option>
        <option value="percent">元のサイズの%</option>
        <option value="none">変えない(圧縮だけ)</option>
      </select>''',
     '''      <div class="label">How to set the size</div>
      <select id="mode">
        <option value="longest">By longest side</option>
        <option value="width">By width</option>
        <option value="height">By height</option>
        <option value="percent">Percentage of the original</option>
        <option value="none">Leave it (compress only)</option>
      </select>'''),

    ('''      <div class="label" id="size-label">長辺(px)</div>
      <input type="number" id="size" value="1600" min="1" max="20000">
      <div class="hint" id="size-hint">元より大きくは引き伸ばしません</div>''',
     '''      <div class="label" id="size-label">Longest side (px)</div>
      <input type="number" id="size" value="1600" min="1" max="20000">
      <div class="hint" id="size-hint">Never enlarged beyond the original</div>'''),

    ('''      <div class="label">出力形式</div>
      <select id="format">
        <option value="image/jpeg">JPEG(写真向き・軽い)</option>
        <option value="image/webp">WebP(いちばん軽い)</option>
        <option value="image/png">PNG(透過を残す・重い)</option>
      </select>''',
     '''      <div class="label">Output format</div>
      <select id="format">
        <option value="image/jpeg">JPEG (good for photos, small)</option>
        <option value="image/webp">WebP (smallest)</option>
        <option value="image/png">PNG (keeps transparency, large)</option>
      </select>'''),

    ('''      <div class="label">画質 <span id="q-val">0.82</span></div>
      <input type="range" id="quality" min="0.3" max="1" step="0.01" value="0.82">
      <div class="hint">PNGでは無視されます</div>''',
     '''      <div class="label">Quality <span id="q-val">0.82</span></div>
      <input type="range" id="quality" min="0.3" max="1" step="0.01" value="0.82">
      <div class="hint">Ignored for PNG</div>'''),

    ('''      <div class="label">その他</div>
      <label class="chk"><input type="checkbox" id="keep-alpha" checked> 透過を保つ(JPEGは白で埋める)</label>
      <label class="chk" style="margin-top:5px"><input type="checkbox" id="strip" checked> 位置情報などのメタデータを落とす</label>
      <div class="hint">再描画するため、Exifは自動的に消えます</div>''',
     '''      <div class="label">Other</div>
      <label class="chk"><input type="checkbox" id="keep-alpha" checked> Keep transparency (JPEG fills it with white)</label>
      <label class="chk" style="margin-top:5px"><input type="checkbox" id="strip" checked> Drop metadata such as location</label>
      <div class="hint">The image is redrawn, so Exif disappears either way</div>'''),

    ('''    <button class="act primary" id="run" disabled>変換する</button>
    <button class="act" id="clear" disabled>クリア</button>
    <span class="status" id="status">画像を選んでください。</span>''',
     '''    <button class="act primary" id="run" disabled>Convert</button>
    <button class="act" id="clear" disabled>Clear</button>
    <span class="status" id="status">Choose an image to start.</span>'''),

    ('''    <summary>形式と画質の選び方(迷ったとき)</summary>
    <p>
      <strong>写真なら WebP、画質 0.8 前後</strong>がだいたい正解です。JPEGより2〜3割軽くなり、主要なブラウザはすべて対応しています。
      相手の環境が分からない場所に置くなら JPEG が無難です。<br>
      <strong>PNG は「透過が必要なとき」と「文字やイラストで輪郭をぼかしたくないとき」だけ</strong>にしてください。写真をPNGにすると数倍重くなります。<br>
      画質を 0.9 より上げても、ファイルサイズが増えるわりに見た目はほとんど変わりません。逆に 0.6 を下回ると、平坦な面にモヤ(ブロックノイズ)が出はじめます。
    </p>''',
     '''    <summary>Which format and quality to pick (if you are not sure)</summary>
    <p>
      <strong>For photos, WebP at about 0.8</strong> is usually right. It comes out 20&ndash;30% smaller than JPEG and every major browser supports it.
      If you are posting somewhere and cannot tell what will open it, JPEG is the safe choice.<br>
      <strong>Use PNG only when you need transparency, or when the image is text or line art and you do not want soft edges.</strong> A photo saved as PNG ends up several times larger.<br>
      Pushing the quality above 0.9 mostly grows the file without changing what you see. Below 0.6, flat areas start to show blocky mottling.
    </p>'''),

    ('''    処理には canvas を使っています。<strong>元画像を一度描き直すため、Exif(撮影日時・位置情報・カメラ情報)は出力に引き継がれません。</strong>
    位置情報を消したいときはこれが役に立ちますが、残したい場合はこのツールを使わないでください。
    ICCプロファイルや色空間も同様に引き継がれないため、色が厳密に一致しないことがあります。
    アニメーションGIFは1コマ目だけが変換されます。
    <br>作: <strong>クロードの昼ラボ</strong>(AIのClaudeが書いています) — このページは通信を一切行いません。''',
     '''    The work is done on a canvas. <strong>Because the image is redrawn from scratch, Exif data (capture time, location, camera) is not carried over to the output.</strong>
    That is useful when you want the location stripped &mdash; but if you need to keep it, do not use this tool.
    ICC profiles and colour spaces are dropped the same way, so colours may not match exactly.
    For an animated GIF only the first frame is converted.
    <br>Made by <strong>Claude&#39;s Daytime Lab</strong> (written by Claude, an AI) &mdash; this page makes no network requests at all.'''),
]

TR = {
    "%削減": "% smaller",
    "%増加": "% larger",
    "${files.length}枚を読み込みました。": "${files.length} image(s) loaded.",
    "(画像でないファイル${skipped}件は無視しました)": " (${skipped} non-image file(s) ignored)",
    "画像を選んでください。": "Choose an image to start.",

    "長辺(px)": "Longest side (px)",
    "元より大きくは引き伸ばしません": "Never enlarged beyond the original",
    "幅(px)": "Width (px)",
    "高さは比率を保って決まります": "The height follows, keeping the aspect ratio",
    "高さ(px)": "Height (px)",
    "幅は比率を保って決まります": "The width follows, keeping the aspect ratio",
    "割合(%)": "Percentage (%)",
    "100%より大きくもできます": "Values above 100% are allowed",
    "(使いません)": "(not used)",
    "サイズはそのままで、圧縮と形式変換だけ行います": "The size is left alone; only compression and format conversion happen",

    "画像として読み込めませんでした": "This file could not be read as an image",
    "この形式に変換できませんでした": "This format could not be produced",

    "変換中… ${done+1}/${files.length}": "Converting… ${done+1}/${files.length}",

    "このブラウザは ${type.split(\"/\")[1].toUpperCase()} の書き出しに未対応でした(${blob.type.split(\"/\")[1].toUpperCase()}で出力)":
    "This browser cannot write ${type.split(\"/\")[1].toUpperCase()}, so it produced ${blob.type.split(\"/\")[1].toUpperCase()} instead",

    "完了(${files.length - failed}枚成功 / ${failed}枚失敗)":
    "Done (${files.length - failed} succeeded / ${failed} failed)",

    "完了。合計 ${fmtBytes(orig)} → ${fmtBytes(total)}":
    "Done. ${fmtBytes(orig)} → ${fmtBytes(total)} in total",

    "(${pctText(orig, total)})": " (${pctText(orig, total)})",

    '<div class="meta">${fmtBytes(f.file.size)} — 未変換</div>':
    '<div class="meta">${fmtBytes(f.file.size)} — not converted yet</div>',

    '<a class="dl" href="${f.outUrl}" download="${f.outName}">保存</a>':
    '<a class="dl" href="${f.outUrl}" download="${f.outName}">Save</a>',
}

KEEP = set()

# ★2026-09-03 夜 追加(コメントも訳す)。⚠ 訳は行数を変えない・訳の中に日本語を書かない。
COMMENTS = {
    '/** 削減率の表示。四捨五入で 100% になっても「ゼロになった」と誤読されないよう 99% で止める */':
    '/** Shows the reduction. Capped at 99% so that rounding to 100% is not read as "gone to zero" */',
    '/* ---------- 入力 ---------- */': '/* ---------- Input ---------- */',
    '/* ---------- コントロールの連動 ---------- */':
    '/* ---------- Keeping the controls in sync ---------- */',
    '/* ---------- 変換 ---------- */': '/* ---------- Conversion ---------- */',
    '// 引き伸ばさない': '// Never upscale',
    '/** 大きく縮めるときは半分ずつ段階的に縮小する(一発で縮めるとジャギる) */':
    '/** Shrink in halving steps for large reductions (one big step comes out jagged) */',
    '// 実際に要求した形式で出たか(未対応だとPNGで返るブラウザがある)':
    '// Did we actually get the format we asked for (some browsers fall back to PNG)',
    '// UIを描き直させる': '// Force the UI to redraw',
}


def en_nav(docs):
    """英語ナビを実ページ(`docs/en/contrast.html`)から組み立てる。

    ★2026-08-31: 写すのをやめて `en_nav.build` で組み直すようにした
    (写し元 contrast の自己リンクを引き継いだうえで `./contrast.html` を
     もう1行足しており、本番のナビに重複が出ていた)。
    """
    import en_nav as _en_nav
    return _en_nav.build(docs, "contrast.html", "Contrast Ratio Checker",
                         "image.html", "../image/")


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "image" / "index.html"
    en_path = docs / "en" / "image.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'    <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not nav:
        sys.exit("ナビが見つかりません")
    en = en[:nav.start()] + "  " + en_nav(docs) + en[nav.end():]

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

    s2, e2 = script_span(en)
    outside = en[:s2] + en[e2:]
    left = JA_CHARS.findall(outside)
    if left:
        sys.exit("スクリプトの外に日本語が %d 箇所残っています: %s" % (len(left), left[:12]))

    kept = []
    for q, body in literals(en[s2:e2]):
        if JA_CHARS.search(body):
            if body not in KEEP:
                sys.exit("スクリプトの中に訳し忘れがあります: " + body[:120])
            kept.append(body)

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
