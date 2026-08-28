# -*- coding: utf-8 -*-
"""英語版OGP画像を、記録した文言から作り直す（と、現物と食い違っていないか調べる）。

    python tools/regen_ogp.py --check   # 作り直さずに、現物と一致するかだけ見る
    python tools/regen_ogp.py           # docs/ogp/ に書き出す

**なぜ表を持つのか**: OGP画像に載っている文言は、これまでどこにも記録されていなかった
（`make_ogp.py` を手で呼ぶときの引数だった）。そのせいで
- 2026-08-27 に `wrap` の「英語を語の途中で改行する」バグを直しても、**すでに出来ていた画像は直らなかった**
- 2026-08-28 に下部のブランド表記を英語にしようとしたとき、**作り直すための文言が残っていなかった**
という2つが起きた。表に書いておけば、次からは作り直すだけで済む。

⚠ 画面に出る文言なので、ページの `og:description` とは**別物**（あちらは長い説明文）。
ここの副題は画像用に短く書いたもの。

⚠ 日本語版の25枚はまだ表に無い。日本語は1文字ずつ折るので `wrap` のバグの影響を受けず、
ブランド表記も直す必要が無いため、今回は手を付けていない（作り直すと差分だけが出る）。
"""
import os, sys, subprocess, tempfile, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("make_ogp", os.path.join(HERE, "make_ogp.py"))
mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)

# (スラッグ, タイトル, 副題)
# ★2026-08-28 に現物の画像から読み取り、**修正前の wrap で描き直してバイト一致することで**
#   読み取りが正しいことを確かめた（16枚すべて一致）。
ITEMS = [
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
]


def path_of(slug):
    return os.path.join(mk.OUT_DIR, "ogp-%s.png" % slug)


def main():
    check = "--check" in sys.argv
    tmp = tempfile.mkdtemp(prefix="ogp-") if check else None
    changed = missing = 0
    for slug, title, sub in ITEMS:
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
    if check:
        print("表と食い違う画像: %d / 現物が無い: %d（--check なので書き出していない）" % (changed, missing))
        return 1 if (changed or missing) else 0
    print("%d 枚を書き出した（うち中身が変わったのは %d 枚）" % (len(ITEMS), changed + missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
