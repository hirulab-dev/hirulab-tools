# -*- coding: utf-8 -*-
"""OGP画像を、記録した文言から作り直す（と、現物と食い違っていないか調べる）。

    python tools/regen_ogp.py --check   # 作り直さずに、現物と一致するかだけ見る
    python tools/regen_ogp.py           # docs/ogp/ に書き出す
    python tools/regen_ogp.py --check --only ja   # 日本語版だけ見る（en / ja）

**なぜ表を持つのか**: OGP画像に載っている文言は、これまでどこにも記録されていなかった
（`make_ogp.py` を手で呼ぶときの引数だった）。そのせいで
- 2026-08-27 に `wrap` の「英語を語の途中で改行する」バグを直しても、**すでに出来ていた画像は直らなかった**
- 2026-08-28 に下部のブランド表記を英語にしようとしたとき、**作り直すための文言が残っていなかった**
という2つが起きた。表に書いておけば、次からは作り直すだけで済む。

⚠ 画面に出る文言なので、ページの `og:description` とは**別物**（あちらは長い説明文）。
ここの副題は画像用に短く書いたもの。
"""
import os, sys, subprocess, tempfile, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("make_ogp", os.path.join(HERE, "make_ogp.py"))
mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)

# (スラッグ, タイトル, 副題)
# ★2026-08-28 に現物の画像から読み取り、**修正前の wrap で描き直してバイト一致することで**
#   読み取りが正しいことを確かめた（16枚すべて一致）。
EN_ITEMS = [
    ("en", "Claude's Daytime Lab",
     "Free browser-only tools built by an AI."),
    ("en-regex", "Regex Tester",
     "Every part of the pattern explained in plain English."),
    ("en-char-counter", "Character Counter",
     "Words, reading time, and the weighted count X actually uses."),
    ("en-palette", "Color Palette Generator",
     "Palettes with WCAG contrast checked on every swatch."),
    ("en-timezone", "Time Zone Converter",
     "Meeting overlap at a glance. Says when a time does not exist."),
    ("csv-en", "CSV Preview & Diagnostics",
     "Find the broken rows, and the columns Excel corrupts."),
    ("railroad-en", "Regex Railroad Diagrams",
     "Draw it, read it, catch the traps. Then check the diagram against your own pattern."),
    ("regex-why-en", "Why doesn't my regex match?",
     "Where it stopped, and the one change that fixes it."),
    ("replace-en", "Regex Replacement Preview",
     "See what $1 turns into, one token at a time"),
    ("url-en", "URL Parser & Builder",
     "See where a URL really goes"),
    ("headers-en", "HTTP Header Explainer",
     "Naming the mistakes that raise no error"),
    ("jwt-en", "JWT Explainer",
     "See for yourself that the payload is not encrypted. The traps that raise no error get named."),
    ("password-en", "Password Generator & Strength Check",
     "See the modulo bias with your own eyes, via a real histogram and chi-square test."),
    ("base64-en", "Base64 & Data URL Explainer",
     "Splits base64 and data URLs into their parts and names what raises no error."),
    ("qr-en", "QR Code Generator",
     "Type in your Wi-Fi password; it goes nowhere."),
    ("cron-en", "Cron Expression Explainer",
     "What it means, when it runs next, and the traps that raise no error."),
    ("contrast-en", "Contrast Ratio Checker",
     "WCAG 2.1 AA / AAA, and a colour that actually passes."),
    ("image-en", "Image Resizer & Compressor",
     "Resize and compress. Your images never leave the device."),
    ("page-contrast-en", "Whole-Page Contrast Audit",
     "Every hard-to-read line on the page you have open."),
    ("diff-en", "Text Diff",
     "Which characters changed, not just which lines."),
]

# 日本語版。★2026-08-28 夜に現物25枚から読み取った。裏取りは英語版と同じ手順
# （読み取った文言で描き直して現物とバイト比較する）。
# ⚠ 最初の7枚（site / regex / char-counter / contrast / date / image / take-home）だけは
#    `make_ogp.py` ができる前の手作りで、フラスコの大きさもブランド表記の位置も違う。
#    ここに載せた文言は正しいが、描き直すと**見た目がそろうぶん現物とは一致しない**。
JA_ITEMS = [
    ("site", "ブラウザだけで動く道具箱",
     "AIのClaudeが自分で作って公開している小さなツール群。全部無料、データはどこにも送信されません。"),
    ("regex", "正規表現テスタ",
     "パターンをその場で試して、記号の意味を日本語で解説します。"),
    ("char-counter", "文字数カウンタ",
     "文字数・行数・段落数。Xの重み付きカウント、原稿用紙換算、読了時間まで。"),
    ("contrast", "コントラスト比チェッカー",
     "WCAG 2.1 の AA / AAA 判定。色覚特性シミュレーションと改善案つき。"),
    ("date", "日付計算機",
     "期間・営業日・満年齢・学年・和暦。日本の祝日に自動対応。"),
    ("image", "画像リサイズ・圧縮",
     "端末内で完結。画像はどこにもアップロードされません。"),
    ("take-home", "手取り計算機",
     "額面から手取りを概算。社会保険料率も税率も、全部あなたが直せます。"),
    ("json", "JSON整形・検証",
     "壊れている場所を、行と列で指します。データはどこにも送信されません。"),
    ("diff", "テキスト差分（diff）",
     "行の中のどの文字が変わったかまで色を付けます。"),
    ("unit", "単位換算",
     "坪・畳・合・升・匁まで、根拠つきで一度に出します。"),
    ("palette", "カラーパレット生成",
     "配色を作って、読める明るさまで寄せる。"),
    ("frima-profit", "フリマ手取り計算機",
     "手数料と送料を引いた手取りを出品前に比較。"),
    ("page-contrast", "ページまるごとコントラスト診断",
     "開いているページの読みにくい文字を、全部出します。"),
    ("tz", "タイムゾーン変換",
     "会議の重なりが一目で分かる。夏時間で「存在しない時刻」もそう言います。"),
    ("csv", "CSVプレビュー・診断",
     "文字コードを判定し、壊れている場所を行と列で指します。"),
    ("cron", "cron式の読み下し",
     "日本語の意味・次の実行時刻・落とし穴の検出まで。"),
    ("qr", "QRコード作成",
     "Wi-Fiのパスワードを入れても、どこにも送りません。"),
    ("railroad", "正規表現を鉄道図にする",
     "図に描いて、読み下して、落とし穴を指摘する。図から作った例で、その場で確かめる。"),
    ("regex-why", "正規表現がなぜマッチしないか",
     "止まった位置と、直せばマッチする一手を出します。"),
    ("replace", "正規表現の置換プレビュー",
     "$1 が何に化けるかを1つずつ見せる"),
    ("url", "URLの分解・組み立て",
     "本当にどこへつながるかを見せる"),
    ("headers", "HTTPヘッダの読み下し",
     "エラーにならない設定ミスを名指しする"),
    ("jwt", "JWTの読み下し",
     "中身は暗号化されていない、を目で見る道具。エラーにならない落とし穴を57種類、名指しします。"),
    ("password", "パスワード生成・強度診断",
     "剰余法の偏りをヒストグラムとχ²検定で自分の目で見る。手持ちのパスワードの診断もできます。"),
    ("base64", "Base64・データURLの分解",
     "宣言と中身が合っているか確かめる"),
]

ITEMS = EN_ITEMS + JA_ITEMS


def path_of(slug):
    return os.path.join(mk.OUT_DIR, "ogp-%s.png" % slug)


# ⚠ **わざと `make_ogp.NO_LINE_START` を見ない**。検査と検査される側が同じ定数を
#    読んでいると、その定数を壊したときに両方いっしょに壊れて空振りする
#    （2026-08-28夜、実際に空振りさせて確かめた）。ここは検査側の独立した表。
NO_LINE_START_CHECK = "、。，．・：；？！?!）)］]｝}」』〉》"


def check_kinsoku(items):
    """行頭に置けない字（`、` `。` 閉じ括弧）で始まる行が無いか。

    ⚠ 現物の画素ではなく**表から折り直して**見ている。現物と表が一致することは
    `--check` のほうで見ているので、2つ合わせて現物についても言えることになる。
    """
    from PIL import Image, ImageDraw, ImageFont
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    bad = []
    for slug, title, sub in items:
        for text, fp, size in ((title, mk.FONT_BOLD, mk.TITLE_SIZES[0]), (sub, mk.FONT_REG, 34)):
            for line in mk.wrap(d, text, ImageFont.truetype(fp, size), 740)[1:]:
                if line and line[0] in NO_LINE_START_CHECK:
                    bad.append((slug, line))
    for slug, line in bad:
        print("  行頭禁則  ogp-%s.png  %r で始まる行がある" % (slug, line[0]))
    return len(bad)


def main():
    check = "--check" in sys.argv
    items = ITEMS
    if "--only" in sys.argv:
        which = sys.argv[sys.argv.index("--only") + 1]
        items = {"en": EN_ITEMS, "ja": JA_ITEMS}[which]
    tmp = tempfile.mkdtemp(prefix="ogp-") if check else None
    changed = missing = 0
    for slug, title, sub in items:
        real = path_of(slug)
        out = os.path.join(tmp, "ogp-%s.png" % slug) if check else real
        old = open(real, "rb").read() if os.path.exists(real) else None
        mk.make(slug, title, sub, out=out)
        new = open(out, "rb").read()
        if old is None:
            print("  無い  ogp-%s.png" % slug); missing += 1
        elif old != new:
            print("  違う  ogp-%s.png" % slug); changed += 1
    print()
    bad = check_kinsoku(items)
    if check:
        print("表と食い違う画像: %d / 現物が無い: %d / 行頭禁則: %d（--check なので書き出していない）"
              % (changed, missing, bad))
        return 1 if (changed or missing or bad) else 0
    if bad:
        return 1
    print("%d 枚を書き出した（うち中身が変わったのは %d 枚）" % (len(items), changed + missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
