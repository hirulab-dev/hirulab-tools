#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英語版の生成器が共通で使う道具(2026-09-02 昼 新設)。

## なぜ作ったか

`make_en_*.py` は21本あり、そのうち9本が `translate_literals` を、9本が `script_span` を、
6本が `code_japanese` を**各自のファイルに持っていた**。新しい道具を出すたびに
前の生成器から写していたため。

★**「同じ形のコピーが増えている」と思っていたが、数えたら違った。**
   `translate_literals` は9本で**4通り**、`script_span` は9本で**3通り**に分かれていた。
   写した時点の版がそのまま凍る = **写すたびに古い版が1本ずつ増える**形だった。

差がどこにあったか(=ここで1本に決めたときに何を選んだか):

1. **`//` コメントが改行で終わらずファイル末尾に来たとき**
   片方は残り全部を出して `break`、もう片方は `j = n` として同じ結果に落ちる。
   **どちらも同じ文字列になる**(=見た目の違いだけ)。短いほうを採った。
2. **`keep` と `tr` の両方に同じ文字列があるとき**
   `csv` の版だけ **`keep` を先に見る**(訳さない)。ほかは `tr` が勝つ。
   → **`keep` を先に見る側**を採った。「わざと日本語のまま残す」と書いてあるものを
   黙って訳すほうが事故が大きいため。
   ⚠ 1本化する前に**全生成器の `TR` と `KEEP` の重なりを数え、14本すべて 0 件**を確かめた
   (= どの生成器でも、この選択で**出力は1バイトも変わらない**)。実際、1本化のあと
   21本すべてを生成し直して `docs/` に差分が出ないことを確かめている。
3. **`script_span` が `"use strict";` を範囲に含めるか**
   `regex-tester` だけ含めない。→ 引数 `prefix` にした(既定は従来どおり含める)。

## ここに置かないもの

`core_of` / `strip_literals` / `drop_comments`(railroad・regex-why・replace・headers・
jwt・url が持っている)は**同じ名前で別のことをしている**。1本にできるかは中身を読んでからで、
この枠では触らない。
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank  # noqa: E402

# 画面に出たら「訳し忘れ」とみなす文字(かな・漢字・全角の約物)
JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")


def script_span(html, prefix=""):
    """ページ本体の <script>…</script>(JSON-LD ではないほう)の範囲を返す。

    prefix … `<script>` の直後にあって**範囲に含めたくない**行(例 '"use strict";\\n')。
    """
    m = re.search(r"<script>\n" + re.escape(prefix) + r"(.*)</script>", html, re.S)
    if not m:
        sys.exit("本体のスクリプトが見つかりません")
    return m.start(1), m.end(1)


def code_japanese(src):
    """**文字列でもコメントでも正規表現でもない**日本語を、前後20文字つきで返す。

    2026-08-31 追加(contrast)。それまでの検査は
      (a) 文字列リテラルの中身  (b) スクリプトの外(=HTML本文)
    の2か所しか見ていなかった。**識別子として書かれた日本語**——
    `収益: { 円: 0 }` のような object のキー——はリテラルではないので (a) に掛からず、
    スクリプトの中なので (b) にも掛からない。それでいて `Object.keys()` で拾えば画面に出る。

    正規表現リテラルは中身を空にしてから見る(`/[ぁ-ん]/` は**処理の一部**であって
    画面に出る文言ではないため。char-counter が実際にこれを持っている)。
    """
    skeleton = blank(src, blank_regex=True)
    return [skeleton[max(0, m.start() - 20):m.start() + 20].replace("\n", " ")
            for m in JA_CHARS.finditer(skeleton)]


def comments(src):
    """JS の中のコメントを、**書いてある順に**そのまま返す(`//` も `/* */` も)。

    2026-09-03 昼 追加。それまで**誰もコメントを見ていなかった**。
    生成器は日本語版を写して文字列だけ訳すので、**コメントは日本語のまま英語ページに載る**。
    実際に本番でそうなっている(この日に数えた): en/date.html 37行 / en/regex-tester.html 18行 /
    en/take-home.html 12行 / en/char-counter.html 3行。
    ソースは公開してあるので、英語の読み手が開くと日本語の注釈が出てくる。
    """
    out, i, n = [], 0, len(src)
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
            i = j + 1 if j < n and src[j] == q else i + 1
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
        i += 1
    return out


def translate_comments(src, tr):
    """コメントの中身を辞書と**完全一致**で差し替える(文字列リテラルには触らない)。

    ⚠ 訳は**行数を変えないこと**。日英でコードの骨組みを突き合わせる検査
    (`blank()` はコメントを消すが改行は残す)が、行数の違いをコードの違いとして出すため。
    日本語を含むのに辞書に無いコメントは一覧で返す(呼び出し側で止める)。
    """
    missing = [c for c in comments(src) if JA_CHARS.search(c) and c not in tr]
    if missing:
        return src, missing
    # ⚠ 行数が変わる訳は**全部まとめて**出す(1件ずつ止めると、直すたびに次が出て往復が増える。
    #   2026-09-03 昼、date の37件を訳したときに実際にそうなった)
    bad = ["%d行 → %d行: %s" % (c.count("\n") + 1, tr[c].count("\n") + 1, c[:70])
           for c in comments(src) if c in tr and tr[c].count("\n") != c.count("\n")]
    if bad:
        sys.exit("コメントの訳で行数が変わっています(検査が壊れます)。%d 件:\n  %s"
                 % (len(bad), "\n  ".join(bad)))
    out, i, n = [], 0, len(src)
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
                out.append(src[i:j + 1])
                i = j + 1
                continue
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] in "/*":
            if src[i + 1] == "/":
                j = src.find("\n", i)
                j = n if j < 0 else j
            else:
                j = src.find("*/", i + 2)
                j = n if j < 0 else j + 2
            body = src[i:j]
            new = tr.get(body, body)
            if new.count("\n") != body.count("\n"):
                sys.exit("コメントの訳で行数が変わっています(検査が壊れます):\n  " + body[:120])
            out.append(new)
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out), []


def translate_literals(src, tr, keep):
    """JS を1文字ずつ読み、**文字列リテラルの中身だけ**を辞書と完全一致で差し替える。

    引用符の種類(' " `)を問わない。**`keep` にあるものは訳さない**。
    日本語を含むのに `tr` にも `keep` にも無いものが見つかったら、その一覧を返す
    (呼び出し側で止める)。戻り値は (差し替えたソース, 訳し忘れの一覧)。
    """
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
                if body in keep:
                    pass
                elif body in tr:
                    body = tr[body]
                elif JA_CHARS.search(body):
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
