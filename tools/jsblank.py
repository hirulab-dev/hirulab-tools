# -*- coding: utf-8 -*-
"""JavaScript のソースから「文字列リテラルの中身」と「コメント」を取り除く。

英語版の生成で使う。目的は
**「文字列の中身を全部空にすると、日本語版と英語版のコードがバイト単位で一致する」**
を確かめること。つまり、訳したのは引用符の中だけで、処理は1バイトも変えていない、を機械で保証する。

正規表現でやると、`add("a", "b", "c")` のような並びで
`", "` を1つの文字列と読んでしまう境界の事故が起きた（2026-08-23 に踏んだ）。
なので前から1文字ずつ読む。見るのは
  - 文字列 '…' "…" `…`（エスケープつき）
  - コメント // と /* */
  - 正規表現リテラル（直前のトークンから判定する素朴な方法）
"""

import re

# 正規表現リテラルが来うる位置かどうかを、直前の非空白文字で判断する素朴な規則。
_BEFORE_REGEX = set("(,=:[!&|?{};+-*%~^<>") | {"\n"}
_KEYWORD_BEFORE_REGEX = ("return", "typeof", "instanceof", "in", "of", "new", "delete", "case", "do", "else", "void")


def _regex_allowed(out_prefix):
    tail = out_prefix.rstrip()
    if not tail:
        return True
    if tail[-1] in _BEFORE_REGEX:
        return True
    m = re.search(r"[A-Za-z_$][A-Za-z0-9_$]*$", tail)
    return bool(m) and m.group() in _KEYWORD_BEFORE_REGEX


def blank(src, keep_quotes=True, blank_regex=False):
    """文字列の中身を空にし、コメントを消したソースを返す。

    `blank_regex=True` にすると**正規表現リテラルの中身も空にする**（`/[ぁ-ん]/g` → `//g`）。
    2026-08-31 追加。英語版のコードに「文字列でもコメントでもない日本語」——
    つまり**識別子として書かれた日本語**（`収益: { 円: 0 }` のような object のキー）が
    残っていないかを見るために使う。既定を変えていないので、日英のバイト一致の検査には影響しない。
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in ("'", '"', "`"):
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    break
                if src[j] == "\n" and q != "`":
                    break            # 閉じないまま行が終わった＝壊れている。そのまま出す
                j += 1
            if j < n and src[j] == q:
                out.append(q + q if keep_quotes else "")
                i = j + 1
                continue
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and _regex_allowed("".join(out)):
            j, inclass = i + 1, False
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    inclass = True
                elif src[j] == "]":
                    inclass = False
                elif src[j] == "/" and not inclass:
                    break
                elif src[j] == "\n":
                    break
                j += 1
            if j < n and src[j] == "/":
                out.append("//" if blank_regex else src[i:j + 1])
                i = j + 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def literals(src):
    """文字列リテラルの中身を、出てきた順に返す（重複は除かない）。"""
    got = []
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
                got.append((q, src[i + 1:j]))
                i = j + 1
                continue
            i += 1
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
    return got
