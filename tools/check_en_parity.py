#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英語版と日本語版で、**文字列の中身以外のコード**が同じかを全ページ分見る(2026-09-01 朝 新設)。

## なぜ作ったか

2026-09-01 未明に `en/csv.html` で見つけた実バグ:
**行をつなぐ区切りが日本語版では U+0001、英語版では空文字**になっていて、
英語版だけが `ab,c` と `a,bc` を「まったく同じ内容の行」と名指ししていた。
6日以上気づかなかった理由は単純で、**英語版を手で書いたページには「日本語版と同じか」を
見る仕組みが無かった**から。`make_en_*.py` で生成しているページは
「文字列の中身を空にすると日英でバイト一致」を生成のたびに検査しているので、
同じ事故が構造的に起きない。**生成器を持たないページだけが野放し**だった。

## 何を見るか

`docs/en/*.html` を全部走査して、対応する日本語ページと突き合わせる。

  - 文字列リテラルの中身・コメント・正規表現リテラルの中身を空にしてから比べる
    (= 訳した文言の違いは無視して、**処理だけ**を見る)
  - 生成器を持つページは「一致していること」が要求。1バイトでも違えば ★
  - 生成器を持たない**手書きの英語版**は、一致しないのが普通なので、
    **違う行の数と中身を出して人が見る**。ここに `en/csv.html` の型の傷が眠っている

    python lab/scripts/check_en_parity.py [--docs <docs>] [--page en/csv.html] [--show 20]
"""
import argparse
import difflib
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank  # noqa: E402

# 英語ページ -> 日本語ページ(docs からの相対)
PAIRS = {
    "base64.html": "base64/index.html",
    "char-counter.html": "char-counter/index.html",
    "contrast.html": "contrast/index.html",
    "cron.html": "cron/index.html",
    "csv.html": "csv/index.html",
    "diff.html": "diff/index.html",
    "headers.html": "headers/index.html",
    "image.html": "image/index.html",
    "json.html": "json/index.html",
    "jwt.html": "jwt/index.html",
    "page-contrast.html": "page-contrast/index.html",
    "palette.html": "palette/index.html",
    "password.html": "password/index.html",
    "qr.html": "qr/index.html",
    "railroad.html": "railroad/index.html",
    "regex-tester.html": "regex/index.html",
    "regex-why.html": "regex-why/index.html",
    "replace.html": "replace/index.html",
    "timezone.html": "tz/index.html",
    "unit.html": "unit/index.html",
    "url.html": "url/index.html",
}

# 生成器を持つページ(= 日英でコードが一致していなければならない)
GENERATED = {
    "base64.html", "contrast.html", "cron.html", "diff.html", "headers.html",
    "image.html", "json.html", "jwt.html", "page-contrast.html", "palette.html",
    "password.html", "qr.html", "railroad.html", "regex-why.html", "replace.html",
    "unit.html", "url.html",
}


def script_span(html):
    m = re.search(r"<script>\n(.*)</script>", html, re.S)
    if not m:
        return None
    core = html[m.start(1):m.end(1)]
    # ★`NAV_LINKS` は「英語版がある道具だけ」を載せるので日英で項目数が違うのが仕様。
    #   `make_en_password.py` が自分の照合から外しているのと同じ理由でここでも外す。
    return re.sub(r"var NAV_LINKS = \[.*?\];\n", "", core, flags=re.S)


def norm(src):
    """文字列・コメント・正規表現の中身を空にして、行ごとに前後の空白を落とす。"""
    b = blank(src, blank_regex=True)
    return [ln.strip() for ln in b.split("\n")]


def flat(src):
    """★改行の入れ方の違いを消した形。
    訳した文言が長くて折り返しが変わっただけ、を「処理が違う」と言わないため
    (`en/password.html` の表がこの形で、最初 15 行ちがうと出た)。"""
    return re.sub(r"\s+", " ", blank(src, blank_regex=True)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--page", help="この英語ページだけ見る(例 csv.html)")
    ap.add_argument("--show", type=int, default=6, help="手書きページで出す差分の行数")
    args = ap.parse_args()

    docs = pathlib.Path(args.docs)
    names = [args.page.split("/")[-1]] if args.page else sorted(PAIRS)
    bad, rows = [], []

    for name in names:
        ja_rel = PAIRS.get(name)
        if ja_rel is None:
            print("対応表に無い英語ページ: %s(PAIRS に足すこと)" % name)
            bad.append(name)
            continue
        en_p, ja_p = docs / "en" / name, docs / ja_rel
        if not en_p.exists() or not ja_p.exists():
            print("ページが無い: %s / %s" % (en_p, ja_p))
            bad.append(name)
            continue
        en_s, ja_s = script_span(en_p.read_text(encoding="utf-8")), \
            script_span(ja_p.read_text(encoding="utf-8"))
        if en_s is None or ja_s is None:
            rows.append((name, "—", "本体のスクリプトが見つからない"))
            continue
        a, b = norm(ja_s), norm(en_s)
        diff = [ln for ln in difflib.unified_diff(a, b, lineterm="", n=0)
                if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
        gen = name in GENERATED
        if flat(ja_s) == flat(en_s):
            rows.append((name, "生成" if gen else "手書き",
                         "一致" if not diff else "一致(折り返しだけ違う)"))
        elif gen:
            rows.append((name, "生成", "★%d 行ちがう(生成器を回し直すこと)" % len(diff)))
            bad.append(name)
            for ln in diff[:args.show]:
                print("  %s %s" % (name, ln[:160]))
        else:
            rows.append((name, "手書き", "%d 行ちがう(手書きなので普通。中身を見ること)" % len(diff)))
            for ln in diff[:args.show]:
                print("  %s %s" % (name, ln[:160]))

    print("\n| 英語ページ | 作り | コード(文字列以外)の一致 |")
    print("|---|---|---|")
    for name, kind, state in rows:
        print("| %s | %s | %s |" % (name, kind, state))
    hand = [r for r in rows if r[1] == "手書き"]
    print("\n生成 %d ページ / 手書き %d ページ(%s)"
          % (len(rows) - len(hand), len(hand), " ".join(r[0] for r in hand)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
