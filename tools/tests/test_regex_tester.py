#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正規表現テスタ( docs/regex/ と docs/en/regex-tester.html )の検証。2026-09-02 未明に新設。

★**2026-08-15 公開の道具なのに、検証が1本も無かった**(11本目)。
  **これで「検証の無い道具」は無くなる**(25本すべてに検証が付いた)。

## 参照をどこから取るか

この道具は「ブラウザの `RegExp` に投げて結果を出す」ので、**照合そのものを
ブラウザで検算しても同じものを2回書くだけ**になる。そこで参照を役目で分ける。

| 見るもの | 参照 | どこから来たか |
|---|---|---|
| マッチの有無・位置・グループ | **Python の `re`**(`re.ASCII` で JS 側に寄せる) | 第三者の別実装 |
| **ハイライト** | **入力した文字列そのもの** — 印を外せば入力と一字一句同じはず | 道具のコードと無関係(性質) |
| **表の行** | **位置と文字列の辻褄** — `text[位置:位置+長さ]` が「マッチ」欄と同じか | 画面に出ている数字だけ |
| **読み下し** | **トークンを連結すると元のパターンに戻る** | 性質(取りこぼしを式なしで測れる) |
| 読み下しの中身 | `data-kind`(下記)と、**別に数えたグループ数**(`re.compile().groups`) | 突き合わせ |
| フラグの反映 | 正解を手で握った一覧 | 手で書いた期待値 |
| 妥当/不当なパターン | 正解を手で握った一覧 | 手で書いた期待値 |

★ 上の2〜4番目が、この道具でいちばん効く。**式を写さずに済む**うえ、
  日本語も英語も読まないので**日英どちらのページにもそのまま当たる**。

★ 読み下しの中身だけは言葉なので、**`li` に `data-kind` を持たせて**そこを見る
  (url・headers・jwt の `data-code` と同じ手)。文言が変わっても検査は生き残る。

## JS と Python で **本当に違う**ところ(黙って合わせない)

`re.ASCII` を付けても、次は残る。**差が出ること自体**を `check_engine_gap` で固定する。
- `$` は Python では**末尾の改行の直前にも当たる**(JS は文字列の本当の末尾だけ)
- `\\s` の集合が違う(JS は U+00A0・U+FEFF なども空白、`re.ASCII` の Python は6種だけ)
- `.` は JS では `\\r` と U+2028/U+2029 も除く(Python は `\\n` だけ)
→ 見比べる見本はこの3つを踏まない範囲で作り、踏む形は上の検査に手で置く。

## ★この検証で見つけたこと(2026-09-02)

1. **長さ0のマッチがあると、テスト文字列が画面から消える。**
   `a*` を `bb` に当てると3件マッチし、**ハイライト欄が空になる**。
   印を進める幅を `m[0].length || 1` としていたため、長さ0のとき1文字ぶん飛ばして
   出力から落としていた。利用者が自分で入れた文字が消えるので、いちばん目につく壊れ方。
2. **500件で打ち切っているのに、件数は打ち切った数を出す。**
   600文字の `a` に `a` を当てると「501 件マッチ」と出る。**画面の数字が単に違う。**
3. **`s` フラグを入れても `.` の説明が「改行以外」のまま。**
   同じ画面の件数は改行に当たった数を出しているので、**画面の2か所が食い違う**。
   `i` フラグも同じで、「文字「A」そのもの」と言いながら小文字にも当たる。
4. **存在しないグループ番号の `\\3` を「グループ3と同じ文字列」と説明する。**
   ECMAScript の Annex B では**8進エスケープ**(U+0003)として読まれるので、
   説明は違うし、実際その形は「マッチなし」になる(17本目の鉄道図で通った道)。

使い方:
    python lab/scripts/test_regex_tester.py                 # 手元の日本語ページ
    python lab/scripts/test_regex_tester.py --both          # 日英ぜんぶ
    python lab/scripts/test_regex_tester.py --page <html>
    python lab/scripts/test_regex_tester.py --n 400
    python lab/scripts/test_regex_tester.py --sabotage
"""
import argparse
import asyncio
import pathlib
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from playwright.async_api import async_playwright  # noqa: E402

DOCS = pathlib.Path.home() / "hirulab-tools" / "docs"
JP_PAGE = DOCS / "regex" / "index.html"
EN_PAGE = DOCS / "en" / "regex-tester.html"

FLAG_IDS = (("fg", "g"), ("fi", "i"), ("fm", "m"), ("fs", "s"))


# ── 参照(Python の re。JS 側に寄せる) ────────────────────────────────

def py_flags(flags):
    f = re.ASCII                      # \d \w \b を JS と同じ ASCII の意味にする
    if "i" in flags:
        f |= re.IGNORECASE
    if "m" in flags:
        f |= re.MULTILINE
    if "s" in flags:
        f |= re.DOTALL
    return f


def py_matches(pattern, text, flags):
    """Python の re で、道具と同じ並びのマッチ一覧を作る。

    g あり → 全部 / g なし → 先頭の1件だけ。

    ⚠ **`finditer` はそのままでは参照にならない**(2026-09-02 に実測して分かった)。
      Python は**長さ0のマッチを見つけたあと、同じ位置でもう一度、中身のあるマッチを探す**。
      `\\w*?` を `abc` に当てると Python は '' , 'a' , '' , 'b' … と返すが、
      JS の `matchAll` は '' , '' , '' … しか返さない(長さ0なら1つ進める規則)。
      → **進め方だけ JS の規則で書き、照合そのものは Python の engine に任せる**。
        こう分けると「参照が第三者」であることは保ったまま、並べ方の差だけを消せる。
        差そのものは消さずに `check_engine_gap` に固定してある。
    """
    rx = re.compile(pattern, py_flags(flags))
    out, pos = [], 0
    while pos <= len(text):
        m = rx.search(text, pos)
        if not m:
            break
        out.append((m.start(), m.group(0), list(m.groups())))
        if "g" not in flags:
            break
        pos = m.end() + 1 if m.end() == m.start() else m.end()
    return out


# ── 見本 ────────────────────────────────────────────────────────

# JS と Python で意味が一致する範囲だけを使う(冒頭の「本当に違うところ」を踏まない)
ATOMS = ["a", "b", "c", "1", "2", "-", "_", ".", r"\d", r"\w", r"\.", r"\-",
         "[a-c]", "[^ab]", "[0-9x]", "(a)", "(ab)", "(?:ab)", "(a|b)", "x", "@"]
QUANTS = ["", "", "", "*", "+", "?", "{2}", "{1,3}", "{2,}", "*?", "+?", "??"]
TEXTS = [
    "abc 123 xyz",
    "aaa bbb ccc",
    "support@example.com and taro.yamada+work@mail.example.co.jp",
    "a1-b2_c3",
    "line one\nline two\nline three",
    "",
    "xxxxxxxxxx",
    "The quick brown fox 2026-09-02",
]


def make_cases(rng, n):
    """(パターン, テキスト, フラグ) を n 組。手で置く形を先に入れる。"""
    cases = [
        (r"([\w.+-]+)@([\w-]+\.[\w.-]+)", TEXTS[2], "g"),   # 既定のパターン
        (r"\d+", "a12b345", "g"),
        (r"\d+", "a12b345", ""),                            # g なし
        ("a*", "bb", "g"),                                  # ★長さ0のマッチ
        ("a*", "bb", ""),                                   # ★長さ0 + g なし
        ("", "abc", "g"),                                   # ★空パターン(全部が長さ0)
        ("(a)|(b)", "ab", "g"),                             # 片方だけ埋まるグループ
        ("A", "aA", "gi"),                                  # i フラグ
        ("^a", "a\nab", "gm"),                              # m フラグ
        (".", "a\nb", "gs"),                                # s フラグ
        (".", "a\nb", "g"),                                 # s なし
        ("z", "abc", "g"),                                  # マッチなし
        ("a", "", "g"),                                     # テキストが空
        (r"(\d)(\d)?", "1 23", "g"),                        # 埋まらないグループ
    ]
    while len(cases) < n:
        pat = "".join(rng.choice(ATOMS) + rng.choice(QUANTS)
                      for _ in range(rng.randint(1, 4)))
        text = rng.choice(TEXTS)
        flags = "g" if rng.random() < 0.8 else ""
        if rng.random() < 0.15:
            flags += "i"
        if rng.random() < 0.15:
            flags += "m"
        if rng.random() < 0.15:
            flags += "s"
        try:
            re.compile(pat, py_flags(flags))
        except re.error:
            continue
        cases.append((pat, text, flags))
    return cases[:n]


class Report:
    def __init__(self, label=""):
        self.label, self.rows, self.bad = label, [], []

    def line(self, name, n, bad):
        self.rows.append((name, n, len(bad)))
        self.bad += [(name, b) for b in bad]

    def ok(self):
        return not self.bad

    def show(self, limit=8):
        print("\n### %s" % self.label)
        print("| 見たもの | 件数 | 食い違い |")
        print("|---|---:|---:|")
        for name, n, b in self.rows:
            print("| %s | %s | %d |" % (name, format(n, ","), b))
        if self.bad:
            print("\n食い違いの中身(先頭 %d 件):" % limit)
            for name, b in self.bad[:limit]:
                print("  [%s] %s" % (name, b))
        print("\n食い違い合計: %d" % len(self.bad))


# ── 画面を読む ───────────────────────────────────────────────────

READ = """() => ({
  pstatus: document.getElementById('pstatus').textContent,
  pclass: document.getElementById('pstatus').className,
  mstatus: document.getElementById('mstatus').textContent,
  hl: document.getElementById('highlight').textContent,
  marks: [...document.querySelectorAll('#highlight mark')].map(
      m => ({ text: m.textContent, cls: m.className })),
  rows: [...document.querySelectorAll('#mrows tr')].map(
      tr => [...tr.children].map(td => td.textContent)),
  explain: [...document.querySelectorAll('#explain li')].map(
      li => ({ text: li.textContent, tok: li.dataset.tok, kind: li.dataset.kind,
               group: li.dataset.group }))
})"""


async def probe(pg, pattern, text, flags):
    await pg.fill("#pattern", pattern)
    await pg.fill("#testtext", text)
    for fid, f in FLAG_IDS:
        el = pg.locator("#" + fid)
        if (f in flags) != await el.is_checked():
            await el.set_checked(f in flags)
    await pg.dispatch_event("#pattern", "input")
    return await pg.evaluate(READ)


def parse_pos(s):
    try:
        return int(s)
    except ValueError:
        return None


# ── 検査 ────────────────────────────────────────────────────────

async def check_cases(pg, rep, cases):
    """本体。1組ごとに4つの角度から見る。"""
    bad_count, bad_rows, bad_hl, bad_self, bad_groups = [], [], [], [], []
    for pattern, text, flags in cases:
        want = py_matches(pattern, text, flags)
        s = await probe(pg, pattern, text, flags)
        tag = "/%s/%s on %r" % (pattern, flags, text[:30])

        if not s["pclass"].endswith("ok"):
            bad_count.append("%s: 妥当なはずのパターンが拒まれた: %s" % (tag, s["pstatus"]))
            continue

        # (1) 表の行を Python の re と突き合わせる
        got = [(parse_pos(r[2]), r[1]) for r in s["rows"]]
        exp = [(st, txt) for st, txt, _ in want]
        if got != exp:
            # ★どこで割れたかを出す(先頭6件だけ出していたら「同じに見える」ことがあった)
            k = next((i for i in range(max(len(got), len(exp)))
                      if got[i:i + 1] != exp[i:i + 1]), 0)
            bad_rows.append("%s: 表が %d 件目で割れた 画面=%r 参照=%r (件数 %d / %d)"
                            % (tag, k + 1, got[k:k + 3], exp[k:k + 3], len(got), len(exp)))

        # (2) ★表の中だけで辻褄が合うか(参照を使わない・画面の数字だけ)
        for r in s["rows"]:
            pos, mtext = parse_pos(r[2]), r[1]
            if pos is None or text[pos:pos + len(mtext)] != mtext:
                bad_self.append("%s: 位置 %s の「%s」がテキストのその場所と違う" % (tag, r[2], mtext))
                break

        # (3) ★ハイライトは印を外せば入力と一字一句同じはず
        if s["hl"] != text:
            bad_hl.append("%s: ハイライト欄の文字列が入力と違う 画面=%r 入力=%r"
                          % (tag, s["hl"], text))

        # (4) グループの中身
        for i, (r, w) in enumerate(zip(s["rows"], want)):
            cell = r[3]
            if not w[2]:
                continue
            for gi, g in enumerate(w[2], 1):
                piece = "$%d=%s" % (gi, "—" if g is None else g)
                if piece not in cell:
                    bad_groups.append("%s: %d件目のグループ 画面=%r に %r が無い"
                                      % (tag, i + 1, cell, piece))
                    break
            else:
                continue
            break
    n = len(cases)
    rep.line("表の行 vs Python の re", n, bad_rows)
    rep.line("★表の中の辻褄(位置と文字列)", n, bad_self)
    rep.line("★ハイライトが入力と同じか", n, bad_hl)
    rep.line("グループの中身", n, bad_groups)
    rep.line("妥当なパターンを拒まないか", n, bad_count)


async def check_count_text(pg, rep):
    """件数の表示が、表の行数と合っているか。

    ★打ち切りがあると合わなくなる。600文字に `a` を当てると本当は600件だが、
      道具は501行で止めたうえで「501」と出す。**画面の数字が単に違う。**
    """
    bad = []
    cases = [("a", "a" * 600, "g", 600), ("a", "a" * 10, "g", 10), ("z", "aaa", "g", 0)]
    for pattern, text, flags, want in cases:
        s = await probe(pg, pattern, text, flags)
        nums = [int(x.replace(",", "")) for x in re.findall(r"[\d,]+", s["mstatus"])]
        if want == 0:
            if nums:
                bad.append("マッチ0件なのに数字が出る: %r" % s["mstatus"])
            continue
        if want not in nums:
            bad.append("%d件のはずだが件数表示に %d が無い: %r" % (want, want, s["mstatus"]))
        if len(s["rows"]) < min(want, 500):
            bad.append("%d件のはずだが表が %d 行しかない" % (want, len(s["rows"])))
    rep.line("★件数の表示が本当の件数か", len(cases), bad)


async def check_zero_length(pg, rep):
    """★長さ0のマッチ。文字が消えないこと + 印が見えること。"""
    bad = []
    cases = [("a*", "bb"), ("", "abc"), (r"\b", "ab cd"), ("x?", "yy")]
    for pattern, text in cases:
        s = await probe(pg, pattern, text, "g")
        if s["hl"] != text:
            bad.append("/%s/ on %r: 文字が消えた 画面=%r" % (pattern, text, s["hl"]))
        zero = [m for m in s["marks"] if m["text"] == ""]
        if zero and not any(m["cls"] for m in zero):
            bad.append("/%s/ on %r: 長さ0の印に目印(class)が無く画面で見えない"
                       % (pattern, text))
    rep.line("★長さ0のマッチ", len(cases), bad)


# 読み下しの「種類」。文言ではなくここを見るので日英どちらでも同じ答えになる
EXPLAIN_KINDS = [
    # (パターン, フラグ, [(トークン, 種類), ...])
    ("a", "g", [("a", "literal")]),
    ("a", "gi", [("a", "literal-i")]),                      # ★i を説明に映す
    (".", "g", [(".", "dot")]),
    (".", "gs", [(".", "dot-all")]),                        # ★s を説明に映す
    ("^a$", "g", [("^", "start"), ("a", "literal"), ("$", "end")]),
    ("^a$", "gm", [("^", "start-line"), ("a", "literal"), ("$", "end-line")]),
    (r"\d", "g", [(r"\d", "class-escape")]),
    (r"(a)\1", "g", [("(", "group-open"), ("a", "literal"),
                     (")", "group-close"), (r"\1", "backref")]),
    # ★ グループが1つしか無いのに \3 → ECMAScript Annex B では8進エスケープ
    (r"(a)\3", "g", [("(", "group-open"), ("a", "literal"),
                     (")", "group-close"), (r"\3", "octal")]),
    ("(?:a)", "g", [("(?:", "group-open-noncapture"), ("a", "literal"), (")", "group-close")]),
    ("(?=a)", "g", [("(?=", "lookahead"), ("a", "literal"), (")", "group-close")]),
    ("(?!a)", "g", [("(?!", "lookahead-neg"), ("a", "literal"), (")", "group-close")]),
    ("(?<=a)", "g", [("(?<=", "lookbehind"), ("a", "literal"), (")", "group-close")]),
    ("(?<!a)", "g", [("(?<!", "lookbehind-neg"), ("a", "literal"), (")", "group-close")]),
    ("(?<y>a)", "g", [("(?<y>", "group-open-named"), ("a", "literal"), (")", "group-close")]),
    ("[a-z]", "g", [("[a-z]", "class")]),
    ("[^a]", "g", [("[^a]", "class-neg")]),
    ("a|b", "g", [("a", "literal"), ("|", "alt"), ("b", "literal")]),
    ("a*", "g", [("a*", "literal")]),
    (r"\.", "g", [(r"\.", "escaped")]),
]


async def check_explain_kinds(pg, rep):
    """★読み下しの種類。文言ではなく `data-kind` を見る(日英で同じ答えになる)。"""
    bad = []
    for pattern, flags, want in EXPLAIN_KINDS:
        s = await probe(pg, pattern, "abc", flags)
        got = [(e["tok"], e["kind"]) for e in s["explain"]]
        if got != want:
            bad.append("/%s/%s: 画面=%r 期待=%r" % (pattern, flags, got, want))
    rep.line("★読み下しの種類(data-kind)", len(EXPLAIN_KINDS), bad)


async def check_explain_roundtrip(pg, rep, rng, n=150):
    """★読み下しのトークンを連結すると元のパターンに戻るか。

    式を写さずに「解析が入力を1文字も取りこぼしていない」を測れる。
    """
    bad = 0
    detail = []
    seen = 0
    for _ in range(n):
        pattern = "".join(rng.choice(ATOMS) + rng.choice(QUANTS)
                          for _ in range(rng.randint(1, 4)))
        s = await probe(pg, pattern, "abc 123", "g")
        if not s["pclass"].endswith("ok"):
            continue
        seen += 1
        toks = [e["tok"] for e in s["explain"]]
        if any(t is None for t in toks):
            detail.append("%r: data-tok が無い" % pattern)
            bad += 1
            continue
        if "".join(toks) != pattern:
            detail.append("%r -> %r" % (pattern, "".join(toks)))
            bad += 1
    rep.line("★読み下しの往復(連結すると元に戻る)", seen, detail[:20] if detail else [])
    return bad


async def check_group_count(pg, rep, rng, n=60):
    """読み下しが数えたグループ数 vs `re.compile().groups`(別の出どころ)。"""
    bad = []
    seen = 0
    pats = [r"(a)(b)", r"(?:a)(b)", r"(a(b))", r"(?<x>a)(b)", r"(a)|(b)", "a", r"(?=a)(b)"]
    while len(pats) < n:
        pats.append("".join(rng.choice(ATOMS) + rng.choice(QUANTS)
                            for _ in range(rng.randint(1, 4))))
    for pattern in pats[:n]:
        # 名前つきグループの綴りだけ Python の書き方に直す(後読み `(?<=` `(?<!` は別物)
        for_py = re.sub(r"\(\?<(?![=!])", "(?P<", pattern)
        try:
            want = re.compile(for_py, re.ASCII).groups
        except re.error:
            continue
        s = await probe(pg, pattern, "abc", "g")
        if not s["pclass"].endswith("ok"):
            continue
        seen += 1
        nums = [e["group"] for e in s["explain"]
                if e["kind"] in ("group-open", "group-open-named")]
        if len(nums) != want:
            bad.append("%r: 読み下しのグループ数=%d 参照=%d" % (pattern, len(nums), want))
        # ★番号そのものも見る。数が合っていても番号がずれていると
        #   「$2 で参照できます」と嘘を教えることになる(9/2 の --sabotage で露見した穴)
        elif nums != [str(k) for k in range(1, want + 1)]:
            bad.append("%r: グループ番号が 1..%d の順になっていない: %r" % (pattern, want, nums))
    rep.line("グループの数と番号 vs Python の re", seen, bad)


# 正解を手で握った「妥当か / 不当か」の一覧
VALIDITY = [
    ("(", False), ("[", False), ("a{2,1}", False), ("*", False), ("\\", False),
    (")", False), ("(?<a>x)(?<a>y)", False),
    ("a", True), ("", True), ("(a)", True), ("[a-z]", True), (r"\d+", True),
    ("a{2,3}", True), ("(?:a|b)", True), ("(?<n>a)", True), ("a**", False),
]


async def check_validity(pg, rep):
    bad = []
    for pattern, want_ok in VALIDITY:
        s = await probe(pg, pattern, "abc", "g")
        got_ok = s["pclass"].endswith("ok")
        if got_ok != want_ok:
            bad.append("%r: 画面=%s 期待=%s (%s)"
                       % (pattern, "OK" if got_ok else "エラー",
                          "OK" if want_ok else "エラー", s["pstatus"][:40]))
    rep.line("妥当/不当の名指し", len(VALIDITY), bad)


async def check_engine_gap(pg, rep):
    """★JS と Python が**本当に違う**ところ。差が出ること自体を固定する。

    黙って合わせない(20〜22本目で通ってきた型)。ここが「一致」になったら
    どちらかの前提が変わったということなので、そのとき考え直す。
    """
    bad = []
    cases = [
        # (パターン, テキスト, フラグ, JS側の件数, Python側の件数, 何が違うか)
        ("a$", "a\n", "g", 0, 1, "$ は Python では末尾の改行の直前にも当たる"),
        (r"\s", "a b", "g", 1, 0, "U+00A0 は JS では空白、re.ASCII の Python では違う"),
        (".", "a\rb", "g", 2, 3, ". は JS では \\r も除く"),
    ]
    # ★長さ0のあとの進め方は `py_matches` で JS に寄せてあるので、
    #   ここだけは**素の `finditer`** に当てて「寄せる前は違う」ことを固定する
    raw = len(list(re.compile(r"\w*?", re.ASCII).finditer("abc")))
    if raw == 3:
        bad.append("素の finditer が長さ0のあと同じ位置で拾わなくなった。"
                   "py_matches の寄せ方(進め方だけ JS の規則)を見直すこと")

    for pattern, text, flags, js_n, py_n, why in cases:
        s = await probe(pg, pattern, text, flags)
        got = len(s["rows"])
        ref = len(py_matches(pattern, text, flags))
        if got != js_n:
            bad.append("%r on %r: 画面=%d 期待(JS)=%d — %s" % (pattern, text, got, js_n, why))
        if ref != py_n:
            bad.append("%r on %r: 参照=%d 期待(Python)=%d — %s" % (pattern, text, ref, py_n, why))
        if js_n == py_n:
            bad.append("%r: 差が消えた。前提が変わったので検査を見直すこと" % pattern)
    rep.line("★JSとPythonの本当の差(固定)", len(cases) + 1, bad)


async def check_presets(pg, rep):
    """プリセットのボタンを押したら、そのパターンが入って解析が通るか。"""
    bad = []
    names = await pg.eval_on_selector_all("#presets button", "els => els.map(e => e.textContent)")
    # ★押す前に**目印**を入れておく。入れずに見ると、押しても何も起きないときに
    #   「前の検査が入れたパターン」が残っていて合格に見える(9/2 の --sabotage で素通りした)
    MARK = "__preset_not_pressed__"
    for i, name in enumerate(names):
        await pg.fill("#pattern", MARK)
        await pg.dispatch_event("#pattern", "input")
        await pg.locator("#presets button").nth(i).click()
        s = await pg.evaluate(READ)
        got = await pg.input_value("#pattern")
        if not got or got == MARK:
            bad.append("%s: 押してもパターンが入らない" % name)
        elif not s["pclass"].endswith("ok"):
            bad.append("%s: 入ったパターンが妥当でない: %s" % (name, s["pstatus"][:40]))
        elif not s["explain"]:
            bad.append("%s: 読み下しが1行も出ない" % name)
    rep.line("プリセット", len(names), bad)


# ── 実行 ────────────────────────────────────────────────────────

async def run(html_path, n, seed, quiet=False, label=""):
    rng = random.Random(seed)
    cases = make_cases(rng, n)
    rep = Report(label or pathlib.Path(html_path).name)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(pathlib.Path(html_path).resolve().as_uri())
        await check_cases(pg, rep, cases)
        await check_count_text(pg, rep)
        await check_zero_length(pg, rep)
        await check_explain_kinds(pg, rep)
        await check_explain_roundtrip(pg, rep, rng)
        await check_group_count(pg, rep, rng)
        await check_validity(pg, rep)
        await check_engine_gap(pg, rep)
        await check_presets(pg, rep)
        if errs:
            rep.line("JSエラー", 0, errs)
        await b.close()
    if not quiet:
        rep.show()
    return rep


# 仕込みごとに「どの検査が捕まえるはずか」まで書く
# (2026-09-01 夜の教訓: 仕込みが1つだと、たまたま最初に当たった検査だけで満点に見える)
SABOTAGE = [
    ("長さ0のとき1文字飛ばす(9/2に直した傷)",
     ("last = m.index + m[0].length;", "last = m.index + (m[0].length || 1);"),
     "★ハイライトが入力と同じか"),
    ("ハイライトの末尾を書かない",
     ("frag.appendChild(document.createTextNode(text.slice(last)));", ""),
     "★ハイライトが入力と同じか"),
    ("表の位置を1ずらす",
     ("[idx + 1, m[0], m.index, groups", "[idx + 1, m[0], m.index + 1, groups"),
     "★表の中の辻褄(位置と文字列)"),
    ("グループを1つ落とす",
     ("m.slice(1).map(", "m.slice(2).map("),
     "グループの中身"),
    ("g フラグを無視して常に全部拾う",
     ("if (re.global) {", "if (true) {"),
     "表の行 vs Python の re"),
    ("件数を表の行数と別に数える(打ち切りを隠す)",
     ("shown = matches.length", "shown = Math.min(matches.length, 501)"),
     "★件数の表示が本当の件数か"),
    ("s フラグを読み下しに映さない(9/2に直した傷)",
     ('dotAll ? "dot-all" : "dot"', '"dot"'),
     "★読み下しの種類(data-kind)"),
    ("i フラグを読み下しに映さない(9/2に直した傷)",
     ('icase ? "literal-i" : "literal"', '"literal"'),
     "★読み下しの種類(data-kind)"),
    ("m フラグを読み下しに映さない(9/2に直した傷)",
     ('multi ? "start-line" : "start"', '"start"'),
     "★読み下しの種類(data-kind)"),
    ("8進エスケープを後方参照と言い張る(9/2に直した傷)",
     ("Number(m[1]) <= nGroups", "true"),
     "★読み下しの種類(data-kind)"),
    ("読み下しでトークンを1文字取りこぼす",
     ("i += lit.length;", "i += lit.length + 1;"),
     "★読み下しの往復(連結すると元に戻る)"),
    ("量指定子を読み下しに付けない",
     ("out[out.length - 1].tok += q[0];", ""),
     "★読み下しの往復(連結すると元に戻る)"),
    ("番号なしグループも数に入れる",
     ('k = "group-open-noncapture"; groupNo--;', 'k = "group-open-noncapture";'),
     "グループの数と番号 vs Python の re"),
    ("捕獲グループを数え違える(8進エスケープの判定が狂う)",
     ('if (pattern[i + 1] !== "?") n++;', 'if (pattern[i + 1] !== "?") n += 3;'),
     "★読み下しの種類(data-kind)"),
    ("壊れたパターンでもOKと出す",
     ('ps.className = "status err";', 'ps.className = "status ok";'),
     "妥当/不当の名指し"),
    ("プリセットを押してもパターンを入れない",
     ('b.onclick = () => { $("pattern").value = p; render(); };',
      'b.onclick = () => { render(); };'),
     "プリセット"),
]


async def sabotage(html_path, n, seed):
    src = pathlib.Path(html_path).read_text(encoding="utf-8")
    tmp = pathlib.Path(html_path).with_name("_sabotage_regex.html")
    print("わざと壊して、**狙った検査が**捕まえるか見る(%d 種)\n" % len(SABOTAGE))
    missed, wrong = [], []
    try:
        for i, (name, (a, b), want_check) in enumerate(SABOTAGE, 1):
            if a not in src:
                print("%2d. %-46s ★仕込めない(差し替え元が見つからない)" % (i, name))
                missed.append(name)
                continue
            tmp.write_text(src.replace(a, b, 1), encoding="utf-8", newline="\n")
            rep = await run(tmp, max(40, n // 4), seed + i, quiet=True)
            caught = sorted({x for x, _ in rep.bad})
            if not caught:
                print("%2d. %-46s ★素通り" % (i, name))
                missed.append(name)
            elif want_check not in caught:
                print("%2d. %-46s △別の検査が捕まえた(%s / 狙い=%s)"
                      % (i, name, caught[0], want_check))
                wrong.append(name)
            else:
                print("%2d. %-46s 検出(%s)" % (i, name, want_check))
    finally:
        if tmp.exists():
            tmp.unlink()
    print("\n素通り: %d / %d   狙いと違う検査が捕まえた: %d"
          % (len(missed), len(SABOTAGE), len(wrong)))
    for m in missed:
        print("  素通り: " + m)
    for m in wrong:
        print("  狙い違い: " + m)
    return 1 if (missed or wrong) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default=None)
    ap.add_argument("--both", action="store_true", help="日英の両方に当てる")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260902)
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()

    if args.sabotage:
        return asyncio.run(sabotage(args.page or str(JP_PAGE), args.n, args.seed))

    pages = [args.page] if args.page else ([str(JP_PAGE), str(EN_PAGE)] if args.both
                                           else [str(JP_PAGE)])
    rc = 0
    for pg in pages:
        rep = asyncio.run(run(pg, args.n, args.seed))
        rc |= 0 if rep.ok() else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
