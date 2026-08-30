#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「テキスト差分(diff)」の検証(2026-08-31 新設)。

この道具には検証スクリプトが1本も無かった(作った 8/20 に手元で1500組を見ただけで、
**再現できる形が残っていない**)。8本目なのに、あとから足した道具のほうが検証が厚い状態だった。

★参照の出どころを5つに分ける(1つの参照だけだと、同じ勘違いを2回するので):

  (1) **`git apply`(第三者の実装)** … 道具が書き出した unified diff を本物の git に食わせ、
      変更前のファイルに当てて、出てきた中身が予定どおりかを見る。
      ⚠ **当てた結果は「変更後」と同じとは限らない**。大文字小文字や空白を無視する設定で
      同じとみなした行は、文脈行として**変更前の字面**が載るため(diff の作法どおり。
      git の `diff -w` も同じ)。期待値は ops から組み立てる。

  (1b) **パッチの見出しが本文と合っているか**(現物の行に照らす) … ★これは
      **git apply では見えない**。git はハンクの開始行がずれていても前後を探して当ててしまう
      ので、開始行を1つずらす傷を仕込んでも黙って通った(この日に実測)。
      「ここの何行が、こう変わる」と書いてある以上、その位置が本当かは別に見る必要がある。

  (2) **最小性(LCS の動的計画法)** … Myers のアルゴリズムの肝は「編集手数が最小」であること。
      道具の出した削除+追加の数が、**まったく別のアルゴリズム**(最長共通部分列のDP)で
      出した理論上の最小値と一致するかを見る。速いか遅いかではなく**正しいか**を測る。
      道具の JS を読み写した参照ではないので、実装が同じ間違いをする余地が無い。
      行の中の差分(文字単位)にも同じ物差しを当てる。

  (3) **編集脚本として辻褄が合うか** … ops を順に当てると変更前が変更後になるか。
      eq の対が本当に同じ行を指しているか。

  (4) **行の分け方・無視する設定は Python で書き下した規則** … 規則そのものは道具と同じ
      (規格ではなく道具の仕様なので)。★ここだけは第三者ではない、と分かるように書いておく。

  さらに画面まで通した経路(textarea に入れて「比較する」を押し、集計と unified を読む)を
  1回だけ通し、**英語版に日本語が1文字も出ないこと**を確かめる。

★この検証で道具のバグを1件見つけて直した(2026-08-31): **単語単位の差分で絵文字が半分に割れる**。
  `tokenize` の単語用の正規表現に `u` フラグが無く、`[^\\sA-Za-z0-9_]` が UTF-16 の1単位に
  当たっていたので、サロゲートペアの前半だけが `<del>` の外に残っていた(画面には壊れた文字が出る)。
  文字単位は `Array.from` なので無事だった。公開した 8/20 からずっとあった傷。

`--sabotage` でわざと6種類の傷を入れて、上の検査が本当に落ちるかを見る(空振り確認)。

    python lab/scripts/test_diff.py [--n 300] [--sabotage] [--docs <docs>]
    python lab/scripts/test_diff.py --page docs/en/diff.html    # 英語版にそのまま当たる
"""
import argparse
import pathlib
import random
import re
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")


# ---- 参照(4) 行の分け方・無視する設定 ------------------------------------------
# ★これは道具の仕様を Python で書き下したもので、第三者の実装ではない。
#   それでも意味はある: 「JS と Python が同じ規則を別々に書いて一致するか」を見ているので、
#   片方だけの書き換え(CRLF を落とす、行末の空白をいつも削る等)は必ず食い違いになる。
def split_lines(s):
    s = re.sub(r"\r\n?", "\n", s)
    if s == "":
        return []
    out = s.split("\n")
    if out and out[-1] == "":
        out.pop()
    return out


def norm_line(s, o):
    t = s
    if o["tail"]:
        t = re.sub(r"[ \t]+$", "", t)
    if o["ws"]:
        t = re.sub(r"[ \t]+", " ", t).strip()
    if o["cs"]:
        t = t.lower()
    return t


# ---- 参照(2) 最小の編集手数を LCS の DP で出す --------------------------------
def edit_distance(a, b):
    """削除+追加の最小数。Myers とは別のやり方(LCS の動的計画法)で出す。"""
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return n + m
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        ai = a[i - 1]
        for j in range(1, m + 1):
            cur[j] = prev[j - 1] + 1 if ai == b[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    return n + m - 2 * prev[m]


# ---- 見本のテキストを作る ------------------------------------------------------
WORDS = ["alpha", "beta", "gamma", "delta", "value", "count", "index", "name",
         "return", "if", "else", "for", "const", "let", "true", "false", "null"]


def a_text(rnd, n):
    lines = []
    for _ in range(n):
        k = rnd.randint(0, 6)
        line = " ".join(rnd.choice(WORDS) for _ in range(k))
        if rnd.random() < 0.15:
            line = "  " + line
        if rnd.random() < 0.12:
            line += "   "                      # 行末の空白(無視する設定の的)
        if rnd.random() < 0.08:
            line += " " + rnd.choice(["<tag>", "a & b", "x > y", "\"q\"", "'q'"])
        if rnd.random() < 0.06:
            line += " " + rnd.choice(["日本語", "😀🍣", "café", "naïve"])
        lines.append(line)
    return lines


def mutate(rnd, lines):
    """変更後を作る。書き換え・挿入・削除・入れ替え・大文字化を混ぜる。"""
    out = []
    for ln in lines:
        r = rnd.random()
        if r < 0.10:
            continue                                   # 行を消す
        if r < 0.20 and ln:
            i = rnd.randrange(len(ln))
            out.append(ln[:i] + rnd.choice("xyz-_ ") + ln[i + 1:])   # 1文字だけ書き換え
            continue
        if r < 0.26:
            out.append(ln.upper())                     # 大文字だけの違い
            continue
        if r < 0.32:
            out.append(ln + " " + rnd.choice(WORDS))   # 行末に足す
            continue
        out.append(ln)
        if r > 0.94:
            out.append(rnd.choice(WORDS) + " " + rnd.choice(WORDS))  # 行を挿す
    return out


EDGE = [
    ("", ""),
    ("", "one\ntwo\n"),
    ("one\ntwo\n", ""),
    ("same\n", "same\n"),
    ("a\r\nb\r\n", "a\nb\n"),                       # 改行コードだけの違い
    ("a \nb\t\n", "a\nb\n"),                        # 行末の空白だけの違い
    ("A\nB\n", "a\nb\n"),                           # 大文字小文字だけの違い
    ("x  y\n", "x y\n"),                            # 空白の量だけの違い
    ("no newline at end", "no newline at end!"),
    ("😀🍣\n", "😀🍜\n"),                            # サロゲートペア
    ("a\nb\nc\nd\ne\nf\ng\nh\n", "a\nX\nc\nd\ne\nf\nY\nh\n"),
    ("<&>\n", "<&>!\n"),                            # HTML で意味のある文字
    # ★行の中の差分で「左のトークンを右にも書いてしまう」型の傷は、**大文字小文字を
    #   区別しない設定で、なお行が違う**ときにしか現れない(それ以外は左右のトークンが
    #   そもそも同じ字面なので、取り違えても結果が変わらない)。
    #   ランダム生成では `.upper()` した行が丸ごと eq になってしまい、この形が出なかった。
    #   → 手で足す(「薄い領域」の8例目。2026-08-31)
    ("Alpha Beta GAMMA\n", "alpha beta gamma!\n"),
    ("One TWO three\n", "one two THREE four\n"),
]

OPTSETS = [
    {"cs": False, "ws": False, "tail": True},        # 既定
    {"cs": False, "ws": False, "tail": False},
    {"cs": True, "ws": False, "tail": True},
    {"cs": False, "ws": True, "tail": True},
    {"cs": True, "ws": True, "tail": True},
]


# ---- 道具を呼ぶ ---------------------------------------------------------------
CALL = """(arg) => {
  const A = splitLines(arg.a), B = splitLines(arg.b);
  const KA = A.map(s => normLine(s, arg.opts)), KB = B.map(s => normLine(s, arg.opts));
  let ops = myers(KA, KB, MAX_D_LINE);
  const truncated = !ops;
  if (!ops) ops = coarse(KA, KB);
  const rows = buildRows(ops, A, B, arg.mode, arg.opts);
  return {
    A: A, B: B, KA: KA, KB: KB, truncated: truncated,
    ops: ops.map(o => [o.t, o.a === undefined ? -1 : o.a, o.b === undefined ? -1 : o.b]),
    uni: unified(ops, A, B, 3, arg.name, arg.name),
    rows: rows.map(r => ({ t: r.t, a: r.a === undefined ? -1 : r.a,
                           b: r.b === undefined ? -1 : r.b,
                           l: r.html ? r.html.l : null, r: r.html ? r.html.r : null }))
  };
}"""

# 画面まで通す経路(textarea に入れて「比較する」を押す)
VIA_UI = """(arg) => {
  const $ = id => document.getElementById(id);
  $("a").value = arg.a; $("b").value = arg.b;
  $("ig-case").checked = false; $("ig-ws").checked = false; $("ig-tail").checked = true;
  $("gran").value = "char";
  $("run").click();
  return { stats: $("stats").innerText, status: $("status").innerText,
           uni: $("uni").innerText, rows: $("diffbox").querySelectorAll("tr").length };
}"""


# ---- HTML のほどき ------------------------------------------------------------
UNESC = re.compile(r"&(amp|lt|gt);")
TAG = re.compile(r"</?(?:del|ins) ?(?:class=\"x\")?>")
DEL = re.compile(r'<del class="x">(.*?)</del>', re.S)
INS = re.compile(r'<ins class="x">(.*?)</ins>', re.S)


def unesc(s):
    return UNESC.sub(lambda m: {"amp": "&", "lt": "<", "gt": ">"}[m.group(1)], s)


def plain(html):
    return unesc(TAG.sub("", html))


def tokens(s, mode):
    if mode == "word":
        return re.findall(r"\s+|[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", s)
    return list(s)


# ---- 参照(1) git apply --------------------------------------------------------
def git_apply(work, name, before, patch):
    """変更前のファイルにパッチを当てて、出てきた中身を返す(当たらなければ None)。"""
    f = work / name
    f.write_text("\n".join(before) + ("\n" if before else ""), encoding="utf-8", newline="\n")
    p = work / "p.diff"
    p.write_text(patch, encoding="utf-8", newline="\n")
    r = subprocess.run(["git", "apply", "-p0", "--unsafe-paths", "--directory=.", "p.diff"],
                       cwd=work, capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr or "").strip().splitlines()[:1]
    return f.read_text(encoding="utf-8"), None


HUNK = re.compile(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@$")


def patch_structure(A, R, uni):
    """パッチの見出しが本文と合っているかを、現物の行に照らして確かめる。

    A = 変更前の行 / R = **このパッチを当てたら出てくるはずの行**。
    ⚠ R は「変更後」とは限らない。無視する設定で同じとみなした行は、文脈行として
      **変更前の字面**が載るため(diff の作法どおり)。

    ★なぜ git apply と別に要るのか: **git apply はハンクの開始行がずれていても当ててしまう**
      (前後を探しに行くため)。実際、開始行を1つずらす傷を仕込んでも git は黙って通した。
      「ここの何行が、こう変わる」と書いてある以上、その位置が本当かは別に見る必要がある。
    """
    lines = uni.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) < 2 or not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
        return "ファイル名の2行が無い"
    i, n_hunk = 2, 0
    while i < len(lines):
        m = HUNK.match(lines[i])
        if not m:
            return "ハンクの見出しが読めない: %r" % lines[i]
        a0, ac, b0, bc = (int(x) for x in m.groups())
        i += 1
        av, bv = [], []
        while len(av) < ac or len(bv) < bc:
            if i >= len(lines):
                return "ハンクの本文が足りない"
            ln = lines[i]
            i += 1
            if ln.startswith(" "):
                av.append(ln[1:])
                bv.append(ln[1:])
            elif ln.startswith("-"):
                av.append(ln[1:])
            elif ln.startswith("+"):
                bv.append(ln[1:])
            else:
                return "本文の行頭の記号が読めない: %r" % ln
        if len(av) != ac or len(bv) != bc:
            return "見出しの行数が本文と合わない"
        oa = a0 - 1 if ac else a0
        ob = b0 - 1 if bc else b0
        if oa < 0 or ob < 0 or A[oa:oa + ac] != av:
            return "変更前の位置が合わない(@@ -%d,%d)" % (a0, ac)
        if R[ob:ob + bc] != bv:
            return "変更後の位置が合わない(@@ +%d,%d)" % (b0, bc)
        n_hunk += 1
    if n_hunk == 0:
        return "ハンクが1つも無い"
    return None


SABOTAGE = {
    # 1. Myers の「同じ行が続くあいだ進む」を1歩だけにする → 手数が最小でなくなる
    "snake": lambda s: s.replace(
        "while (x < N && y < M && a[x] === b[y]) { x++; y++; }",
        "if (x < N && y < M && a[x] === b[y]) { x++; y++; }"),
    # 2. 改行コードをそろえるのをやめる
    "crlf": lambda s: s.replace('s = s.replace(/\\r\\n?/g, "\\n");', ""),
    # 3. ハンクの開始行を1つずらす(1始まりに直すのを忘れた形)
    "hunk": lambda s: s.replace("const aStart = aCount ? aBefore[i] + 1 : aBefore[i];",
                                "const aStart = aBefore[i];"),
    # 4. 削除の行に + を書く
    "sign": lambda s: s.replace('body.push("-" + A[o.a]);', 'body.push("+" + A[o.a]);'),
    # 5. 行の中の差分で、右側にも左側のトークンを書いてしまう(写し間違いの型)
    "inner": lambda s: s.replace("const s = esc(ta[op.a]); l += s; r += esc(tb[op.b]); eq++;",
                                 "const s = esc(ta[op.a]); l += s; r += s; eq++;"),
    # 6. 行末の空白を、設定に関わらずいつも削る
    "trailws": lambda s: s.replace('if (o.tail) t = t.replace(/[ \\t]+$/, "");',
                                   't = t.replace(/[ \\t]+$/, "");'),
}


def build_cases(n, seed):
    rnd = random.Random(seed)
    cases = []
    for a, b in EDGE:
        cases.append((a, b, OPTSETS[0], "char"))
        cases.append((a, b, OPTSETS[2], "word"))
    while len(cases) < n:
        k = rnd.randint(0, 24)
        A = a_text(rnd, k)
        B = mutate(rnd, A)
        a = "\n".join(A) + ("\n" if A else "")
        b = "\n".join(B) + ("\n" if B else "")
        cases.append((a, b, rnd.choice(OPTSETS), rnd.choice(["char", "word", "none"])))
    return cases[:n]


def check_all(page, cases, work):
    """1つの版について全部の検査を回し、(件数の内訳, 食い違いの一覧) を返す。"""
    fails = []
    n_split = n_norm = n_script = n_min = n_patch = n_inner = n_exact = n_header = 0
    for idx, (a, b, opts, mode) in enumerate(cases):
        got = page.evaluate(CALL, {"a": a, "b": b, "opts": opts, "mode": mode, "name": "f.txt"})
        A, B, KA, KB = got["A"], got["B"], got["KA"], got["KB"]

        # --- 参照(4) 行の分け方・無視する設定 ---
        if A == split_lines(a) and B == split_lines(b):
            n_split += 1
        else:
            fails.append("#%d 行の分け方が違う" % idx)
            continue
        if KA == [norm_line(s, opts) for s in A] and KB == [norm_line(s, opts) for s in B]:
            n_norm += 1
        else:
            fails.append("#%d 無視する設定の効き方が違う %s" % (idx, opts))
            continue

        # --- 参照(3) 編集脚本として辻褄が合うか ---
        out, ai, bi, ok = [], 0, 0, True
        for t, oa, ob in got["ops"]:
            if t == "eq":
                if oa != ai or ob != bi or KA[oa] != KB[ob]:
                    ok = False
                    break
                out.append(B[ob]); ai += 1; bi += 1
            elif t == "del":
                if oa != ai:
                    ok = False
                    break
                ai += 1
            else:
                if ob != bi:
                    ok = False
                    break
                out.append(B[ob]); bi += 1
        if ok and ai == len(A) and bi == len(B) and out == B:
            n_script += 1
        else:
            fails.append("#%d 編集脚本が変更前を変更後にしない" % idx)
            continue

        # --- 参照(2) 手数が最小か(打ち切ったときは対象外) ---
        if got["truncated"]:
            pass
        else:
            d = sum(1 for t, _, _ in got["ops"] if t != "eq")
            want = edit_distance(KA, KB)
            if d == want:
                n_min += 1
            else:
                fails.append("#%d 手数が最小でない: 道具 %d / 参照 %d" % (idx, d, want))

        # --- 参照(1) git apply ---
        # ⚠ 当てた結果は「変更後」と同じとは限らない。無視する設定(大文字小文字・空白)で
        #    同じ行とみなされたところは、unified diff の文脈行が**変更前の字面**で載るため。
        #    これは diff の作法どおり(git の `diff -w` も同じ)なので、
        #    期待値は ops から組み立てる: eq → 変更前 / ins → 変更後 / del → 落とす。
        if got["uni"]:
            after = [A[oa] if t == "eq" else B[ob] for t, oa, ob in got["ops"] if t != "del"]
            want = "".join(x + "\n" for x in after)
            bad = patch_structure(A, after, got["uni"])
            if bad:
                fails.append("#%d パッチの見出しが本文と合わない: %s" % (idx, bad))
            else:
                n_header += 1
            new, err = git_apply(work, "f.txt", A, got["uni"])
            if new is None:
                fails.append("#%d git apply が拒んだ: %s" % (idx, err))
            elif new != want:
                fails.append("#%d git apply の結果が食い違う" % idx)
            else:
                n_patch += 1
                if want == "\n".join(B) + ("\n" if B else ""):
                    n_exact += 1
        elif A != B and [norm_line(s, opts) for s in A] != [norm_line(s, opts) for s in B]:
            fails.append("#%d 違いがあるのに unified diff が空" % idx)

        # --- 行の中の差分 ---
        for row in got["rows"]:
            if row["t"] != "mod" or row["l"] is None:
                continue
            sa, sb = A[row["a"]], B[row["b"]]
            if plain(row["l"]) != sa or plain(row["r"]) != sb:
                fails.append("#%d 行の中の差分が元の行に戻らない" % idx)
                continue
            dels, inss = DEL.findall(row["l"]), INS.findall(row["r"])
            if mode == "none":
                if dels or inss:
                    fails.append("#%d 「付けない」設定なのに行の中に印がある" % idx)
                    continue
                n_inner += 1
                continue

            ka = tokens(sa, mode)
            kb = tokens(sb, mode)
            if opts["cs"]:
                ka, kb = [x.lower() for x in ka], [x.lower() for x in kb]

            if not dels and not inss and sa != sb:
                # 行の中の照合を打ち切ったときは印を付けない(仕様)。本当に打ち切る量か確かめる
                if mode == "char" and edit_distance(ka, kb) <= 300:
                    fails.append("#%d 違うのに行の中の印が1つも付いていない" % idx)
                    continue
                n_inner += 1
                continue

            # 印を外した残りは、左右で同じ(共通部分をどちらも同じに読んでいる)。
            # ⚠ 大文字小文字を区別しない設定のときは、そろっているのは**小文字にした形**まで
            #    (印の外に出るのは元の字面なので `Abc` と `abc` が並びうる)。
            lc, rc = DEL.sub("", row["l"]), INS.sub("", row["r"])
            if opts["cs"]:
                lc, rc = lc.lower(), rc.lower()
            if lc != rc:
                fails.append("#%d 行の中の共通部分が左右で食い違う" % idx)
                continue

            if mode == "char" and len(ka) + len(kb) < 400:
                marked = sum(len(unesc(x)) for x in dels) + sum(len(unesc(x)) for x in inss)
                want = edit_distance(ka, kb)
                if marked != want:
                    fails.append("#%d 行の中の手数が最小でない: 道具 %d / 参照 %d"
                                 % (idx, marked, want))
                    continue
            n_inner += 1
    return {"split": n_split, "norm": n_norm, "script": n_script, "min": n_min,
            "patch": n_patch, "exact": n_exact, "header": n_header,
            "inner": n_inner}, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--page", help="この HTML を見る(既定は日本語版と英語版の両方)")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260831)
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()

    docs = pathlib.Path(args.docs)
    if args.page:
        pages = [(pathlib.Path(args.page), "指定されたページ")]
    else:
        pages = [(docs / "diff" / "index.html", "日本語版"),
                 (docs / "en" / "diff.html", "英語版")]
    for p, _ in pages:
        if not p.exists():
            sys.exit("ページが見つかりません: %s" % p)

    cases = build_cases(args.n, args.seed)
    tmp = tempfile.TemporaryDirectory()
    work = pathlib.Path(tmp.name)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        if args.sabotage:
            src = pages[0][0].read_text(encoding="utf-8")
            small = build_cases(60, args.seed)
            print("--- わざと壊して、検査が落ちるかを見る ---")
            for name, fn in SABOTAGE.items():
                broken = fn(src)
                if broken == src:
                    browser.close()
                    sys.exit("仕込みが当たっていない(元のコードが変わっていない): %s" % name)
                f = work / ("broken-%s.html" % name)
                f.write_text(broken, encoding="utf-8", newline="\n")
                page.goto(f.as_uri())
                _, fails = check_all(page, small, work)
                print("  %-8s → %s" % (name, "検出した(%d件)" % len(fails) if fails else "★素通りした"))
                if not fails:
                    browser.close()
                    sys.exit("空振り: %s を仕込んでも検査が落ちない" % name)
            browser.close()
            print("\n%d 種すべて検出した。" % len(SABOTAGE))
            return 0

        result, fails = {}, []
        ui_ja = None
        for path, label in pages:
            page.goto(path.resolve().as_uri())
            n, f = check_all(page, cases, work)
            result[label] = n
            fails += ["%s %s" % (label, x) for x in f]

            # 画面まで通す経路を1回
            ui = page.evaluate(VIA_UI, {"a": "a\nb\nc\n", "b": "a\nB\nc\nd\n"})
            if label == "日本語版":
                ui_ja = ui
            if "@@ -1,3 +1,4 @@" not in ui["uni"]:
                fails.append("%s 画面の unified diff が出ていない" % label)
            if label == "英語版":
                left = JA_CHARS.findall(ui["stats"] + ui["status"] + ui["uni"])
                if left:
                    fails.append("英語版の画面に日本語が %d 文字: %s" % (len(left), left[:8]))
                for want in ["lines added", "lines removed", "changed lines"]:
                    if want not in (ui["stats"] + ui["status"]):
                        fails.append("英語版の画面に %r が出ていない" % want)
        browser.close()

    print("見本 %d 組 × %d 版" % (len(cases), len(pages)))
    for label, n in result.items():
        print("  %s: 行の分け方 %d / 無視する設定 %d / 編集脚本 %d / 手数が最小 %d / "
              "見出しと本文 %d / git apply %d(うち変更後と完全一致 %d) / 行の中の差分 %d"
              % (label, n["split"], n["norm"], n["script"], n["min"],
                 n["header"], n["patch"], n["exact"], n["inner"]))
    if ui_ja:
        print("画面まで通した経路: 集計 %r" % ui_ja["stats"].replace("\n", " "))
    if fails:
        print("\n★食い違い %d 件" % len(fails))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("\n食い違い 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
