#!/usr/bin/env python3
"""QRツールの符号化器を、独立実装(segno)の出力と1モジュールずつ突き合わせる検証。

- docs/qr/index.html から QR モジュールのソースだけを切り出す(改変しない=公開物そのものを試す)
- dukpy(Duktape)でそのJSを実行し、行列を得る
- segno で作った参照行列と完全一致するかを見る(型番・マスク・全モジュール)
"""
import json, re, sys, os, dukpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
# 検証対象は公開物そのもの。既定はリポジトリの docs/qr/index.html
# 第1引数か QR_HTML で差し替えられる
# ★ここ(既定のパスの決め方)だけは手元の `lab/scripts/test_qr.py` とわざと違う。
#   手元は公開リポジトリの外にあるので docs/ を相対では指せない。
#   差が「ここだけ」であることは `sync_tools_mirror.py --check` が毎回数える。
_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
HTML = _arg or os.environ.get("QR_HTML") or os.path.join(ROOT, "docs", "qr", "index.html")
REF = os.environ.get("QR_REF") or os.path.join(HERE, "qr-reference.json")


# 符号化器の終わりの目印。**日本語版と英語版で見出しが違う**。
# ★2026-09-04: ここは日本語の見出し1つだけを見ていたので、9/3 に英語ページの
#   コメントを訳した時点から **`test_qr.py docs/en/qr.html` が ValueError で止まっていた**。
#   9/3 夕に `test_replace` / `test_regex_why` で踏んだのとまったく同じ形
#   (「**目印にしたものを、動かせないものだと思い込んでいた**」)。
#   あのとき直したのは踏んだ2本だけで、**同じ形の3本目がここに残っていた**
#   = 今日の `check_ogp_overlap` と同じ「名指しされたファイルだけを直した」形。
END_MARKS = ("画面まわり", "Screen plumbing")


def extract_qr_module(path):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"<script>\s*(.*?)</script>", src, re.S)
    body = m.group(1)
    start = body.index("const QR = (() => {")
    for mark in END_MARKS:
        end = body.find("/* ============================================================\n   " + mark)
        if end >= 0:
            return body[start:end]
    raise SystemExit("符号化器の終わりの目印が見つからない(見た目印: %s)。"
                     "ページの見出しを変えたなら END_MARKS に足すこと" % " / ".join(END_MARKS))


def main():
    js = extract_qr_module(HTML)
    ref = json.load(open(REF, encoding="utf-8"))

    runner = js + """
function __run(text, ecl) {
  var r = QR.encode(text, ecl, { boost: false });
  var rows = [];
  for (var y = 0; y < r.size; y++) {
    var s = "";
    for (var x = 0; x < r.size; x++) s += r.matrix[y][x] ? "1" : "0";
    rows.push(s);
  }
  return { version: r.version, mask: r.mask, size: r.size, matrix: rows,
           mode: r.mode, used: r.usedBits, cap: r.capacityBits };
}
__run(dukpy['t'], dukpy['e']);
"""
    fails, checked_modules = [], 0
    for i, c in enumerate(ref):
        got = dukpy.evaljs(runner, t=c["text"], e=c["ecl"])
        why = []
        if got["version"] != c["version"]:
            why.append("version %s != %s" % (got["version"], c["version"]))
        if got["mask"] != c["mask"]:
            why.append("mask %s != %s" % (got["mask"], c["mask"]))
        if got["size"] != c["size"]:
            why.append("size %s != %s" % (got["size"], c["size"]))
        elif got["matrix"] != c["matrix"]:
            diff = sum(1 for a, b in zip("".join(got["matrix"]), "".join(c["matrix"])) if a != b)
            why.append("modules differ: %d" % diff)
        checked_modules += c["size"] * c["size"]
        if why:
            fails.append((i, c["text"][:30], c["ecl"], "; ".join(why)))

    print("cases: %d / modules compared: %d" % (len(ref), checked_modules))
    if fails:
        print("FAIL: %d" % len(fails))
        for f in fails[:20]:
            print("  ", f)
        sys.exit(1)
    print("ALL PASS — 参照実装(segno)と完全一致")
    if check_claims(len(ref), checked_modules):
        sys.exit(1)


# ---------------------------------------------------------------- 名乗りの見張り
#
# 2026-09-04。**この数(111件 / 587,455モジュール)を出しているのはこの検証だけ**なのに、
# ページに書いてある数を誰も突き合わせていなかった。しかも書いてあったのは
# **英語のトップページ1枚だけ**で、日本語側には同じ主張が無かった
# (= 片方の言語にしか無い数は誰も比べられない。9/3 昼の 132,996 と同じ形)。
# → 日本語のトップにも同じ主張を置いたうえで、**数を出した当人がここで見張る**。
# ⚠ 「どこにも書いていない」も黙らずに言う(黙る検査は同じだけ情報を運ばない)。

CLAIM_PATTERNS = [
    re.compile(r"([0-9][0-9,]*)\s*件[・, ]\s*([0-9][0-9,]*)\s*モジュール"),
    re.compile(r"([0-9][0-9,]*)\s*cases,\s*([0-9][0-9,]*)\s*modules", re.I),
]


def find_docs_dir(page):
    """検証したページから公開フォルダ(docs)を遡って探す。見つからなければ None。"""
    d = os.path.dirname(os.path.abspath(page))
    for _ in range(6):
        if os.path.basename(d) == "docs":
            return d
        nxt = os.path.dirname(d)
        if nxt == d:
            break
        d = nxt
    return None


def check_claims(n_cases, n_modules):
    docs = find_docs_dir(HTML)
    if docs is None:
        print("名乗りの見張り: 公開フォルダが分からないので見ていない (%s)" % HTML)
        return 0
    found, bad = [], []
    for dirpath, _dirs, files in os.walk(docs):
        for fn in sorted(files):
            if not fn.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), docs).replace(os.sep, "/")
            text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            for pat in CLAIM_PATTERNS:
                for m in pat.finditer(text):
                    got = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")))
                    found.append(rel)
                    if got != (n_cases, n_modules):
                        bad.append((rel, got))
    if not found:
        print("★ 名乗りの見張り: この数を書いてあるページが1枚も無い"
              "(%d件 / %d モジュール)。書くならページ側にも置くこと" % (n_cases, n_modules))
        return 1
    print("名乗りの見張り: %d 枚が名乗っている (%s)" % (len(found), " / ".join(sorted(set(found)))))
    for rel, got in bad:
        print("  ★ %s の名乗り %s ≠ 実測 (%d, %d)" % (rel, got, n_cases, n_modules))
    if bad:
        return 1
    # 空振り確認: 1つずらしたら鳴るか(鳴らない検査は「一致」と言い続ける)
    if not _would_complain(n_cases + 1, n_modules, docs):
        print("  !! 数をずらしても鳴らない(名乗りの見張りが空振りしている)")
        return 1
    print("  (件数を1ずらすと鳴ることも確認)")
    return 0


def _would_complain(n_cases, n_modules, docs):
    for dirpath, _dirs, files in os.walk(docs):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
            for pat in CLAIM_PATTERNS:
                for m in pat.finditer(text):
                    got = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")))
                    if got != (n_cases, n_modules):
                        return True
    return False


if __name__ == "__main__":
    main()
