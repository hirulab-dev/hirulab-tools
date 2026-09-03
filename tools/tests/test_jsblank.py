#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`jsblank.blank()` の検証(2026-09-02 朝 新設)。

## なぜこれだけ別に検証が要るか

`blank()` は**英語版の生成が立っている土台**そのもの。各 `make_en_*.py` は最後に

    blank(日本語版のスクリプト) == blank(英語版のスクリプト)

を確かめて、「訳したのは引用符の中だけで、処理は1バイトも変えていない」と主張している。
つまり **`blank()` が何かを見落とすと、主張のほうが実際より強くなる**。
道具のバグは利用者の画面に出るが、**この関数のバグは"検査が通った"という形でしか出ない**。

## 実際に見落としていたもの(この日に発見)

テンプレートリテラルを**丸ごと**空にしていたので、**`${…}` の中のコードが検査から消えていた**:

    `${a.getFullYear()}年${a.getMonth()+1}月`
    `${b.getFullYear()}-${b.getMonth()+9}`

この2つは、月の出し方が違うのに「一致する」と出た。
実測では公開中の22ページのうち3ページ(palette 401 / image 382 / contrast 114 バイト)しか
隠れた範囲が無く、**直したあとに20本の生成器を全部走らせても1ページも動かなかった**
= 主張は結果として本当だったが、**確かめてはいなかった**。

    python lab/scripts/test_jsblank.py
    python lab/scripts/test_jsblank.py --sabotage   # わざと壊して、検査が落ちるか見る
"""
import argparse
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
# ★2026-09-04: 手元は `jsblank.py` と同じフォルダだが、**公開側は `tools/jsblank.py` で
#   この検証は `tools/tests/` に置かれる**ので、隣を見るだけでは ModuleNotFoundError で
#   1行も動かない(公開してから今日まで、公開側は一度も動いていなかった)。
#   両方の置き方で当たるように、隣と1つ上の両方を見る。
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import jsblank  # noqa: E402

# (説明, 日本語版の断片, 英語版の断片, 一致してほしいか)
CASES = [
    ("文言だけ違う",
     'let s = `${y}年${m}月`;', 'let s = `${y}/${m}`;', True),
    ("★${} の中のコードが違う(直す前は素通りしていた形)",
     'let s = `${a.getFullYear()}年${a.getMonth()+1}月`;',
     'let s = `${a.getFullYear()}-${a.getMonth()+9}`;', False),
    ("★${} の中で参照している変数が違う",
     'let s = `${dt.getDate()}日`;', 'let s = `${dt.getDay()}`;', False),
    ("★${} の中の条件が反転している",
     'let s = `${n > 0 ? a : b}件`;', 'let s = `${n < 0 ? a : b}`;', False),
    ("${} の中の入れ子の文字列は、中身を空にする(そこは文言)",
     'let s = `${n === 1 ? "元" : n}年`;', 'let s = `${n === 1 ? "1st" : n}yr`;', True),
    ("入れ子の } を閉じ括弧と数えない",
     'let s = `${ {a:1}.a }年`;', 'let s = `${ {a:1}.a }/`;', True),
    ("入れ子のテンプレートリテラル",
     'let s = `${`${x}件`}年`;', 'let s = `${`${x} items`}/`;', True),
    ("★入れ子のテンプレートの中のコードが違う",
     'let s = `${`${x.a}件`}年`;', 'let s = `${`${x.b} items`}/`;', False),
    ("${} の中の文字列に ` や } が入っていても崩れない",
     'let s = `${f("}`")}年`;', 'let s = `${f("}`")}/`;', True),
    ("素の文字列は従来どおり中身を空にする",
     'let s = "あ" + "い";', 'let s = "a" + "b";', True),
    ("素の文字列でも、外のコードが違えば違う",
     'let s = "あ" + x;', 'let s = "a" + y;', False),
    ("コメントは消える",
     'let a = 1; // 説明\n', 'let a = 1; // note\n', True),
    ("正規表現リテラルは既定では残る(処理の一部なので)",
     'let r = /[ぁ-ん]/g;', 'let r = /[a-z]/g;', False),
    ("エスケープした引用符で文字列が閉じたことにならない",
     r'let s = "\"あ" + b;', r'let s = "\"a" + b;', True),
    ("閉じていないテンプレートは、そのまま出して壊さない",
     'let s = `あ', 'let s = `あ', True),
]


def check(blank):
    bad = []
    for name, ja, en, want in CASES:
        got = blank(ja) == blank(en)
        if got != want:
            bad.append((name, got, want))
    return bad


def hidden_bytes(src):
    """テンプレートリテラルの `${…}` に入っているコードのバイト数。

    「検査から消えていた範囲」の広さを測るためのもの。`blank()` とは別に、
    ここで**独立に数えている**(同じ関数で測ると、その関数が間違っていたとき気づけない)。
    """
    total, i, n = 0, 0, len(src)
    while i < n:
        c = src[i]
        if c in ("'", '"'):
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c or src[j] == "\n":
                    break
                j += 1
            i = j + 1
            continue
        if c == "`":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    k, d = j + 2, 1
                    while k < n and d:
                        if src[k] == "{":
                            d += 1
                        elif src[k] == "}":
                            d -= 1
                        k += 1
                    total += k - (j + 2) - 1
                    j = k
                    continue
                if src[j] == "`":
                    break
                j += 1
            i = j + 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        i += 1
    return total


def survey(docs):
    """公開中の英語ページで、いま何バイトが `${…}` の中にあるかを並べる。"""
    rows = []
    for p in sorted((docs / "en").glob("*.html")):
        if p.name == "index.html":
            continue
        m = re.search(r"<script>\n(.*)</script>", p.read_text(encoding="utf-8"), re.S)
        if not m:
            continue
        core = m.group(1)
        h = hidden_bytes(core)
        if h:
            rows.append((h, len(core), p.name))
    return sorted(rows, reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sabotage", action="store_true",
                    help="テンプレートを丸ごと空にする昔の作りに戻し、検査が落ちるか見る")
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    a = ap.parse_args()

    if a.sabotage:
        def old_blank(src, keep_quotes=True, blank_regex=False):
            """2026-09-02 に直す前の作り: テンプレートリテラルを丸ごと空にする。"""
            out, i, n = [], 0, len(src)
            while i < n:
                c = src[i]
                if c in ("'", '"', "`"):
                    j = i + 1
                    while j < n:
                        if src[j] == "\\":
                            j += 2
                            continue
                        if src[j] == c:
                            break
                        if src[j] == "\n" and c != "`":
                            break
                        j += 1
                    if j < n and src[j] == c:
                        out.append(c + c)
                        i = j + 1
                        continue
                # ⚠ コメントと正規表現の枝はいまの実装と同じにしておく。
                #    ここを省くと「コメントが消えない」ぶんまで落ちて、
                #    **テンプレートを直したことの効き目が水増しされる**。
                if c == "/" and i + 1 < n and src[i + 1] == "/":
                    j = src.find("\n", i)
                    i = n if j < 0 else j
                    continue
                if c == "/" and i + 1 < n and src[i + 1] == "*":
                    j = src.find("*/", i + 2)
                    i = n if j < 0 else j + 2
                    continue
                out.append(c)
                i += 1
            return "".join(out)

        bad = check(old_blank)
        print("--sabotage: 昔の作りに戻した")
        for name, got, want in bad:
            print("  ★落ちた: %s (一致=%s / 期待 %s)" % (name, got, want))
        print("\n落ちた検査: %d 件 / %d 件中" % (len(bad), len(CASES)))
        if not bad:
            print("★ 1件も落ちなかった = この検査は空振りしている")
            return 1
        return 0

    bad = check(jsblank.blank)
    for name, ja, en, want in CASES:
        got = jsblank.blank(ja) == jsblank.blank(en)
        print("%s %-46s 一致=%s" % ("OK " if got == want else "NG ", name, got))
    print("\n%d 件中 %d 件が食い違い" % (len(CASES), len(bad)))

    docs = pathlib.Path(a.docs)
    if docs.is_dir():
        rows = survey(docs)
        print("\n公開中の英語ページで `${…}` の中にあるコード(直す前は検査の外だった範囲):")
        if rows:
            for h, tot, name in rows:
                print("  %-22s %5d / %6d バイト (%.1f%%)" % (name, h, tot, 100 * h / tot))
        else:
            print("  無し")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
