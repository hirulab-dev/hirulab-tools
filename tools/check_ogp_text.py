# -*- coding: utf-8 -*-
"""OGP画像の中の文字を、ページの文言と突き合わせる (2026-09-03 新設)

## なぜ要るか

`inspection-coverage.md` に「**画像の中の文字は誰も読んでいない**」と書いてあった
唯一の残件。検査は全部 HTML のテキストを見るので、**画像の中に何が描いてあっても通る**。
実際に危ないのは次の2つ:

- 英語ページに**日本語の題やブランド表記**の画像が付いている
  (`check_site` の「英語ページの日本語混入」は HTML しか見ない)
- ページの見出しを変えたのに**画像だけ古い呼び名のまま**残る
  (2026-09-03 に `frima-profit` で実際に起きていた)

## どうやって読むか

**OCR は使わない。** `make_ogp.py` は決定論的なので、**同じ引数で描き直して画素が一致するか**で
「画像の中の文字」を確かめられる。ページから拾った題の候補を順に描いて、
既存の画像の**題の領域**と一致するものを探す。一致した候補が、その画像に描いてある題。

★**副題は照合しない**。画像の副題は og:description ではなく**画像用に書き下ろした短文**で、
ページのどこにも同じ文字列が無い(既存52枚すべてで確認)。

## この検査の持ち場（3者のうちどの辺を見るか）

    表(regen_ogp.py の ITEMS) ──①── 画像(docs/ogp/*.png) ──②── ページ(docs/**/*.html)

- ① は **`regen_ogp.py --check`** が見る(表の文言で描き直して現物とバイト比較)
- ② が **この道具**。①だけでは表とページの食い違いは永久に出ない
  (2026-09-03 に `frima-profit` の呼び名の割れと `frima-profit-en` の題から
   "Japanese" が落ちていたのを、この辺を見て初めて検出した)

★**書き始めたとき、①の表があることに気づかず2つ目の記録(`ogp-args.json`)を作りかけた**。
9/2〜9/3 に3回踏んだ「同じ表が複数あって全部違う」を、**自分で1つ増やす側**でやりかけた形。
記録は `regen_ogp.py` の表だけ、が正。

## 見ているもの / 見ていない範囲

見る:
- 画像の**題**が、そのページの題(og:title / title / h1 / JSON-LD name のいずれか)と一致するか
- 画像の**ブランド表記**が日英どちらか。ページの `og:locale` と食い違っていないか
- og:image が実在するか / 参照されていない画像が残っていないか

見ていない:
- **画像の副題**(①の担当)
- フラスコの絵・色・レイアウト(文字ではないので目的の外)
- 画像の中の文字の**訳の質**
"""
import argparse
import os
import re
import sys

from PIL import Image, ImageChops

REPO = os.path.join(os.path.expanduser("~"), "hirulab-tools")
DOCS = os.path.join(REPO, "docs")
sys.path.insert(0, os.path.join(REPO, "tools"))
import make_ogp  # noqa: E402  (パスを通してから)

# 題を描く領域。make_ogp の x=88 / max_w=740 / y0=128 と、フラスコの左端(cx=1005-152=853)から。
TITLE_X0, TITLE_X1 = 80, 840
TITLE_Y0 = 120
# ブランド表記の行。make_ogp の BRAND_Y=500、その下46pxはURL(全ページ共通)。
BRAND_Y0, BRAND_Y1 = 496, 540


def unescape(s):
    if s is None:
        return None
    for a, b in (("&#39;", "'"), ("&mdash;", "—"), ("&amp;", "&"),
                 ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#333;", "ō")):
        s = s.replace(a, b)
    return s


def meta(html, key, attr="property"):
    m = re.search(r'<meta\s+%s="%s"\s+content="([^"]*)"' % (attr, re.escape(key)), html)
    return unescape(m.group(1)) if m else None


def title_candidates(html):
    """このページの題として画像に描かれうる文字列。長いものから試す。"""
    out = []
    for raw in (meta(html, "og:title"),
                (lambda m: unescape(m.group(1).strip()) if m else None)(
                    re.search(r"<title>(.*?)</title>", html, re.S)),
                (lambda m: unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip()) if m else None)(
                    re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)),
                (lambda m: unescape(m.group(1)) if m else None)(
                    re.search(r'"name":\s*"([^"]*)"', html))):
        if not raw:
            continue
        # 「題 — 説明」の形は、画像には片側だけが載っていることが多い。
        # ★前半だけを候補にしていたら、トップページを誤って「不一致」と呼んだ。
        #   `クロードの昼ラボ — ブラウザだけで動く道具箱` の画像には**後半**が描いてある
        #   (ブランド名は下のブランド表記に別で出るので、題に重ねる必要がない)。
        parts = re.split(r"\s+—\s+|\s+&mdash;\s+", raw)
        for cand in [raw] + parts:
            if cand and cand not in out:
                out.append(cand)
    out.sort(key=len, reverse=True)   # 長いほうを先に試す(1行目だけの一致で早合点しないため)
    return out


def render(slug, title, subtitle, brand=None):
    """make_ogp と同じ描き方で1枚作り、Image で返す。"""
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "_ogp_check_%d.png" % os.getpid())
    stdout, sys.stdout = sys.stdout, open(os.devnull, "w", encoding="utf-8")
    try:
        make_ogp.make(slug, title, subtitle, out=tmp, brand=brand)
    finally:
        sys.stdout.close()
        sys.stdout = stdout
    img = Image.open(tmp).convert("RGB")
    img.load()
    os.unlink(tmp)
    return img


def ink_rows(img, x0, x1, y0, y1, bg):
    """背景と違う画素がある行の番号。題が何行あるかを測るのに使う。"""
    rows = []
    px = img.load()
    bgpx = bg.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x, y] != bgpx[x, y]:
                rows.append(y)
                break
    return rows


def same(a, b, box):
    return ImageChops.difference(a.crop(box), b.crop(box)).getbbox() is None


def find_title(img, slug, cands, bg):
    """画像の題の領域に一致する候補を探す。返り値: (題, 行の高さ, 行数) か None。"""
    rows = ink_rows(img, TITLE_X0, TITLE_X1, TITLE_Y0, BRAND_Y0 - 4, bg)
    if not rows:
        return None
    for cand in cands:
        # 副題の行数は分からないので、題のフォントサイズは総当たりで決める
        for size in make_ogp.TITLE_SIZES:
            probe = render_title_only(slug, cand, size)
            prows = ink_rows(probe, TITLE_X0, TITLE_X1, TITLE_Y0, BRAND_Y0 - 4, bg)
            if not prows:
                continue
            box = (TITLE_X0, TITLE_Y0, TITLE_X1, prows[-1] + 3)
            if same(img, probe, box):
                return cand, size, prows
    return None


def render_title_only(slug, title, size):
    """題だけを既定の位置に描いた見本。副題とブランドは描かない。"""
    from PIL import ImageDraw
    img = Image.new("RGB", (make_ogp.W, make_ogp.H), make_ogp.BG_BOTTOM)
    d = ImageDraw.Draw(img)
    for y in range(make_ogp.H):
        t = y / make_ogp.H
        c = tuple(int(make_ogp.BG_TOP[i] + (make_ogp.BG_BOTTOM[i] - make_ogp.BG_TOP[i]) * t)
                  for i in range(3))
        d.line([(0, y), (make_ogp.W, y)], fill=c)
    f = make_ogp.font(make_ogp.FONT_BOLD, size)
    line_h = round(size * 92 / 76)
    y = 128
    for line in make_ogp.wrap(d, title, f, 740):
        d.text((88, y), line, font=f, fill=make_ogp.WHITE)
        y += line_h
    return img


def background():
    from PIL import ImageDraw
    img = Image.new("RGB", (make_ogp.W, make_ogp.H), make_ogp.BG_BOTTOM)
    d = ImageDraw.Draw(img)
    for y in range(make_ogp.H):
        t = y / make_ogp.H
        c = tuple(int(make_ogp.BG_TOP[i] + (make_ogp.BG_BOTTOM[i] - make_ogp.BG_TOP[i]) * t)
                  for i in range(3))
        d.line([(0, y), (make_ogp.W, y)], fill=c)
    return img


def brand_of(img, bg):
    """ブランド表記が日英どちらか。どちらとも一致しなければ None。"""
    from PIL import ImageDraw
    for name, text in (("ja", make_ogp.BRAND_JA), ("en", make_ogp.BRAND_EN)):
        probe = bg.copy()
        d = ImageDraw.Draw(probe)
        d.text((88, make_ogp.BRAND_Y), text,
               font=make_ogp.font(make_ogp.FONT_BOLD, 28), fill=make_ogp.ACCENT)
        if same(img, probe, (80, BRAND_Y0, TITLE_X1, BRAND_Y1)):
            return name
    return None


def pages():
    for dirpath, _dirs, files in os.walk(DOCS):
        for fn in sorted(files):
            if not fn.endswith(".html"):
                continue
            p = os.path.join(dirpath, fn)
            html = open(p, encoding="utf-8").read()
            yield os.path.relpath(p, DOCS).replace("\\", "/"), html


def check_one(rel, html, img, name, bg):
    """1ページぶんの検査。**画像も HTML も引数で受け取る**ので、
    空振り確認はメモリ上で仕込める(公開フォルダを壊さずに済む)。
    返り値: (指摘のリスト, どの検査が出したかの名札の集合)"""
    problems, kinds = [], set()
    slug = name[len("ogp-"):-len(".png")]

    hit = find_title(img, slug, title_candidates(html), bg)
    if hit is None:
        kinds.add("title")
        problems.append("%s: 画像の題が、このページのどの題とも一致しない (%s)\n"
                        "      ページ側の候補: %s"
                        % (rel, name, " / ".join(title_candidates(html)[:3])))

    b = brand_of(img, bg)
    want = "en" if (meta(html, "og:locale") or "").startswith("en") else "ja"
    if b is None:
        kinds.add("brand-unknown")
        problems.append("%s: 画像のブランド表記が日英どちらとも一致しない (%s)" % (rel, name))
    elif b != want:
        kinds.add("brand-lang")
        problems.append("%s: 画像のブランド表記が %s なのにページは %s (%s)"
                        % (rel, b, want, name))

    return problems, kinds


def collect(docs, only=None):
    """(ページ, HTML, 画像名, 画像) を順に返す。画像が引けないものは指摘として返す。"""
    for rel, html in pages():
        if only and rel != only:
            continue
        og = meta(html, "og:image")
        if not og:
            yield rel, html, None, None, "%s: og:image が無い" % rel
            continue
        name = og.rsplit("/", 1)[-1]
        path = os.path.join(docs, "ogp", name)
        if not os.path.exists(path):
            yield rel, html, name, None, "%s: og:image の実体が無い (%s)" % (rel, name)
            continue
        yield rel, html, name, Image.open(path).convert("RGB"), None


def sabotage(docs, bg):
    """わざと壊して、狙った検査が捕まえるかを見る。**どの検査が出したかまで照合する**
    (9/1 の和柄で「安いほうの検査に引っかかって本命が一度も試されていなかった」ため)。"""
    base = [(rel, html, name, img) for rel, html, name, img, err
            in collect(docs) if err is None]
    # 題が通っていて日本語のページを1枚、英語のページを1枚とる
    ja = next(x for x in base if x[0] == "qr/index.html")
    en = next(x for x in base if x[0] == "en/qr.html")

    cases = []
    # 1) 画像の題を別の言葉にする
    bad = render("qr", "QRコードを作る道具", "テキスト・URL・Wi-Fi・メール・電話からQRを作ります。")
    cases.append(("画像の題がページと違う", ja[0], ja[1], ja[2], bad, "title"))
    # 2) ページの題だけを変える(画像はそのまま)
    cases.append(("ページの題だけ変わった", ja[0],
                  ja[1].replace("<h1>QRコード作成</h1>", "<h1>QRコード生成</h1>")
                       .replace('content="QRコード作成', 'content="QRコード生成')
                       .replace('"name": "QRコード作成', '"name": "QRコード生成')
                       .replace("<title>QRコード作成", "<title>QRコード生成"),
                  ja[2], ja[3], "title"))
    # 3) 英語ページの画像に日本語のブランド表記
    bad_en = render("qr-en", "QR Code Generator",
                    "Builds a QR code from text, a URL, Wi-Fi, email or a phone number.",
                    brand=make_ogp.BRAND_JA)
    cases.append(("英語ページに日本語のブランド表記", en[0], en[1], en[2], bad_en, "brand-lang"))
    # 4) ブランド表記が日英どちらでもない
    bad_brand = render("qr", "QRコード作成",
                       "テキスト・URL・Wi-Fi・メール・電話からQRコードを作ります。",
                       brand="昼ラボ")
    cases.append(("ブランド表記が別の文字列", ja[0], ja[1], ja[2], bad_brand, "brand-unknown"))
    # 5) 画像の題が2行のうち1行目だけ合っている(短い候補で早合点しないか)
    bad_half = render("railroad", "正規表現を鉄道図に",
                      "図に描いて、読み下して、落とし穴を指摘する。")
    rr = next(x for x in base if x[0] == "railroad/index.html")
    cases.append(("題が途中で切れている", rr[0], rr[1], rr[2], bad_half, "title"))

    print("\n=== 空振り確認 (%d 種) ===" % len(cases))
    ok = 0
    for label, rel, html, name, img, want_kind in cases:
        _probs, kinds = check_one(rel, html, img, name, bg)
        if want_kind in kinds:
            print("  ✓ %s → %s が捕まえた" % (label, want_kind))
            ok += 1
        else:
            print("  ✗ %s → 素通り(出たのは %s)" % (label, sorted(kinds) or "なし"))
    print("%d / %d 種を狙いどおりの検査が捕まえた" % (ok, len(cases)))
    return 0 if ok == len(cases) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=DOCS)
    ap.add_argument("--only", help="このページだけ見る(docs からの相対パス)")
    ap.add_argument("--sabotage", action="store_true", help="わざと壊して検査が働くか見る")
    a = ap.parse_args()

    bg = background()
    if a.sabotage:
        return sabotage(a.docs, bg)

    problems = []
    seen_images = set()
    n_pages = n_title_ok = 0

    for rel, html, name, img, err in collect(a.docs, a.only):
        if err:
            problems.append(err)
            continue
        seen_images.add(name)
        n_pages += 1
        probs, kinds = check_one(rel, html, img, name, bg)
        problems += probs
        if "title" not in kinds:
            n_title_ok += 1

    if not a.only:
        orphans = sorted(x for x in os.listdir(os.path.join(a.docs, "ogp"))
                         if x.endswith(".png") and x not in seen_images)
        for x in orphans:
            problems.append("ogp/%s: どのページからも参照されていない" % x)

    print("見たページ %d 枚 / 画像 %d 枚 / 題がページと一致 %d 枚"
          % (n_pages, len(seen_images), n_title_ok))
    print("見ていない範囲: 画像の副題(regen_ogp.py --check の担当)・絵柄・訳の質")
    if problems:
        print("\n★ %d 件" % len(problems))
        for p in problems:
            print("  -", p)
        return 1
    print("問題なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
