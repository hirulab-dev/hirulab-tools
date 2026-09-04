#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSVプレビュー・診断ツールを Python の csv モジュールと突き合わせて検証する。

    python lab/scripts/test_csv.py --page <docs/csv/index.html のパス> [--cases 400]

見るのは3つ:
  1. **解析**: 同じ本文を Python の csv.reader と読み比べて、全セルが一致するか
  2. **文字コードの判定**: UTF-8 / UTF-8 BOM / Shift_JIS(CP932) / EUC-JP / UTF-16 で
     書き出したものを、判定器が当てられるか
  3. **区切り文字の推定**: , タブ ; | のどれで書いたかを当てられるか

方針(2026-08-22 の反省より): **参照側は別の探し方にする**。
ブラウザ側と同じ手順を Python で書き直しても、同じ間違いを見逃すだけなので、
セルの正解は「自分が書き出す前に持っていた元の行」そのものを使う。
csv.writer で書いて csv.reader で読み戻せることは Python 側で別に確認する。
"""
import argparse
import csv
import io
import json
import os
import random
import re
import sys

from playwright.sync_api import sync_playwright

# 各文字コードで確実に表せる文字だけを使う(cp932 と euc-jp の共通部分)
JP = "あいうえおカキクケコ漢字日本語表計算経理担当山田佐藤東京都千代田区"
ASCII = "abcXYZ0123456789 -_.@"
TRICKY = ['"', ",", "\t", ";", "|", "\r\n", "\n", "  ", "　", "=SUM(A1)", "0123", "1-2",
          "12345678901234567890"]


def make_cell(rng, allow_jp=True, allow_tricky=True):
    r = rng.random()
    if allow_tricky and r < 0.18:
        base = rng.choice(TRICKY)
    elif r < 0.30:
        base = ""
    else:
        pool = ASCII + (JP if allow_jp else "")
        base = "".join(rng.choice(pool) for _ in range(rng.randint(1, 12)))
    if allow_tricky and rng.random() < 0.15:
        base = base + rng.choice(TRICKY)
    return base


def make_rows(rng, allow_jp=True):
    ncols = rng.randint(1, 6)
    nrows = rng.randint(1, 12)
    rows = []
    for _ in range(nrows):
        rows.append([make_cell(rng, allow_jp) for _ in range(ncols)])
    # 全部空の行はファイル上「空行」になり、CSVの規格でも扱いが割れるので避ける
    rows = [r for r in rows if any(c != "" for c in r)]
    if not rows:
        rows = [["a", "b"]]
    return rows


def write_csv(rows, delim, quoting):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, quoting=quoting, lineterminator="\r\n")
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def python_roundtrip(text, delim):
    return [r for r in csv.reader(io.StringIO(text, newline=""), delimiter=delim)]


ISSUE_COUNT = """(bytes) => {
  window.__csvTool.loadBytes(bytes);
  if (typeof decodeAndRender === 'function') decodeAndRender(); else render();
  // ⚠ 「壊れているところは見つかりませんでした」も li で出る(class="i")ので、
  //    警告(class="w")だけ数える。文言を見ないので日英どちらでも同じに測れる。
  return document.querySelectorAll('#issues li.w').length;
}"""


def check_dup_rows(page):
    """★「まったく同じ内容の行」の名指しを、**言語に依らない形**で見る(2026-09-01 追加)。

    踏んだ実バグ: 行をつなげる区切りが、日本語版は U+0001、**英語版は空文字**だった。
    そのため英語版だけ `["ab","c"]` と `["a","bc"]` を「同じ行」と言っていた。
    どちらもソースの見た目は `r.join("…")` で、生の制御文字は画面にも diff にも出ない。

    文言は言語で違うので、**指摘の本数の差**で測る(3通りを同じページに食わせる)。
    """
    def n_issues(text):
        return page.evaluate(ISSUE_COUNT, list(text.encode("utf-8")))

    base = n_issues("a,b\nx,y\nz,w\n")            # 何も起きない
    same = n_issues("a,b\nx,y\nx,y\n")            # 同じ行が2つ → 1件増える
    split = n_issues("a,b\nxy,z\nx,yz\n")         # つなげると同じだが行としては違う
    out = []
    if same != base + 1:
        out.append("同じ行を名指ししていない(指摘の数 %d → %d)" % (base, same))
    if split != base:
        out.append("つなげると同じなだけの行を「同じ」と言っている(指摘の数 %d → %d)"
                   % (base, split))
    return out


# ---------------------------------------------------------------- 名乗りの見張り
#
# 2026-09-04 18:00枠。**英語版のページだけが「over 2,300 generated files and 52,353 cells」と
# 名乗っていて、日本語版には数が1つも無かった**(訳すときに原文に無い数を足していた)。
# しかもその数は、README の使い方(`--cases 800`)では**二度と出ない数**だった
# = 9/3 の 132,996・9/4 未明の jwt 57 / qr 111 と同じ形の6本目。
# → 日英の両方に「使い方どおりに回したときの数」を置き、**数を出した当人がここで見張る**。
#
# ⚠ この数は `--cases` に依る。**設定が違う回では比べずに「比べていない」と言う**
#   (黙って通すと合っているように読める。9/4 昼の `test_timezone` と同じ決まり)。
CLAIM_CASES = 800          # 名乗りを出す設定(= README の使い方)
CLAIM_PATTERNS = [
    re.compile(r"([0-9][0-9,]*)\s*ファイル[・, ]\s*([0-9][0-9,]*)\s*セル"),
    re.compile(r"([0-9][0-9,]*)\s+(?:generated\s+)?files\s+and\s+([0-9][0-9,]*)\s+cells", re.I),
]


def _docs_dir(page):
    d = os.path.dirname(os.path.abspath(page))
    for _ in range(6):
        if os.path.basename(d) == "docs":
            return d
        nxt = os.path.dirname(d)
        if nxt == d:
            break
        d = nxt
    return None


def check_claims(page, arg_cases, n_cases, n_cells):
    """公開フォルダの全ページから「N ファイル・M セル」の名乗りを拾って実測と比べる。"""
    if arg_cases != CLAIM_CASES:
        print("名乗りの見張り: 比べていない(名乗りは --cases %d の数。この回は %d)"
              % (CLAIM_CASES, arg_cases))
        return []
    docs = _docs_dir(page)
    if docs is None:
        print("名乗りの見張り: 公開フォルダが分からないので見ていない (%s)" % page)
        return []
    found, bad = [], []
    for dirpath, _dirs, files in os.walk(docs):
        for fn in sorted(files):
            if not fn.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), docs).replace(os.sep, "/")
            text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            for pat in CLAIM_PATTERNS:
                for m in pat.finditer(text):
                    got = (int(m.group(1).replace(",", "")),
                           int(m.group(2).replace(",", "")))
                    found.append(rel)
                    if got != (n_cases, n_cells):
                        bad.append("%s の名乗り %s ≠ 実測 (%d, %d)"
                                   % (rel, got, n_cases, n_cells))
    if not found:
        return ["名乗りの見張り: この数(%d ファイル・%d セル)を書いてあるページが1枚も無い。"
                "書くなら日英の両方に置くこと" % (n_cases, n_cells)]
    print("名乗りの見張り: %d 枚が名乗っている (%s)"
          % (len(found), " / ".join(sorted(set(found)))))
    if bad:
        return bad
    # 空振り確認: 1つずらしたら鳴るか(読んでいる場所が本当にそこか)
    if not _would_complain(docs, n_cases + 1, n_cells):
        return ["!! 数をずらしても鳴らない(名乗りの見張りが空振りしている)"]
    print("  (件数を1ずらすと鳴ることも確認)")
    return []


def _would_complain(docs, n_cases, n_cells):
    """この数を実測だと思って読み直したら、どれかのページと食い違うか。"""
    for dirpath, _dirs, files in os.walk(docs):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            for pat in CLAIM_PATTERNS:
                for m in pat.finditer(text):
                    got = (int(m.group(1).replace(",", "")),
                           int(m.group(2).replace(",", "")))
                    if got != (n_cases, n_cells):
                        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", required=True, help="docs/csv/index.html のパス")
    ap.add_argument("--cases", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20260822)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    encodings = [("utf-8", "utf-8"), ("utf-8-sig", "utf-8"), ("cp932", "shift_jis"),
                 ("euc_jp", "euc-jp"), ("utf-16", "utf-16le")]
    delims = [",", "\t", ";", "|"]

    stats = {"cases": 0, "cells": 0, "parse_ng": 0, "enc_ng": 0, "enc_ascii": 0,
             "delim_ng": 0, "delim_skip": 0}
    failures = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto("file:///" + args.page.replace("\\", "/"))
        page.wait_for_timeout(400)

        for i in range(args.cases):
            py_enc, want_enc = encodings[i % len(encodings)]
            delim = delims[(i // len(encodings)) % len(delims)]
            quoting = csv.QUOTE_ALL if rng.random() < 0.25 else csv.QUOTE_MINIMAL
            allow_jp = py_enc not in ("utf-8",) or rng.random() < 0.8
            rows = make_rows(rng, allow_jp=allow_jp)
            text = write_csv(rows, delim, quoting)
            try:
                data = text.encode(py_enc)
            except UnicodeEncodeError:
                continue
            stats["cases"] += 1

            # --- ブラウザ側に読ませる ---
            got = page.evaluate(
                """([bytes, delim]) => {
                     const r = window.__csvTool.loadBytes(bytes);
                     const p = window.__csvTool.parseCSV(r.text, delim);
                     const s = window.__csvTool.sniffDelimiter(r.text);
                     return { enc: r.enc, text: r.text, rows: p.rows,
                              errors: p.errors, delim: s.best.d };
                   }""",
                [list(data), delim])

            # 1. 文字コードの判定
            ascii_only = all(b < 0x80 for b in data)
            if ascii_only:
                stats["enc_ascii"] += 1
            elif got["enc"] != want_enc:
                stats["enc_ng"] += 1
                failures.append("enc: 期待 %s → %s (py=%s, %d bytes)"
                                % (want_enc, got["enc"], py_enc, len(data)))

            # 2. 解析(セル単位)
            grows = got["rows"]
            while grows and grows[-1] == [""]:
                grows.pop()                      # 末尾の改行でできる空行
            if grows != rows:
                stats["parse_ng"] += 1
                if len(failures) < 40:
                    failures.append("parse: delim=%r py=%s\n  期待 %r\n  実際 %r"
                                    % (delim, py_enc, rows[:3], grows[:3]))
            else:
                stats["cells"] += sum(len(r) for r in rows)

            # 3. 区切り文字の推定
            #    1列しかない・全行1列になるデータでは区切りを当てようがないので数えない
            if len(rows[0]) >= 2 and all(len(r) == len(rows[0]) for r in rows):
                if got["delim"] != delim:
                    stats["delim_ng"] += 1
                    if len(failures) < 60:
                        failures.append("delim: 期待 %r → %r" % (delim, got["delim"]))
            else:
                stats["delim_skip"] += 1

            # 参照側の裏取り: Python 自身で書いて読み戻せることを確認しておく
            if python_roundtrip(text, delim) != rows:
                failures.append("参照側が壊れている(csv.reader で戻らない): %r" % (rows[:2],))

        dup_problems = check_dup_rows(page)
        failures += dup_problems

        browser.close()

    print("試した件数: %d / 一致したセル: %d" % (stats["cases"], stats["cells"]))
    failures += check_claims(args.page, args.cases, stats["cases"], stats["cells"])
    print("行の重複の名指し: %s" % ("OK" if not dup_problems else "★NG"))
    print("解析の不一致: %d" % stats["parse_ng"])
    print("文字コードの誤判定: %d (ASCIIのみで判定不要だったもの: %d)"
          % (stats["enc_ng"], stats["enc_ascii"]))
    print("区切りの誤推定: %d (判定できない形なので除外: %d)"
          % (stats["delim_ng"], stats["delim_skip"]))
    for f in failures[:30]:
        print("  ★ " + f)
    ng = stats["parse_ng"] + stats["enc_ng"] + stats["delim_ng"] + len(dup_problems)
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
