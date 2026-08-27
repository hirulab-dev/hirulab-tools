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
HTML = (sys.argv[1] if len(sys.argv) > 1 else None) \
    or os.environ.get("QR_HTML") \
    or os.path.join(ROOT, "docs", "qr", "index.html")
REF = os.environ.get("QR_REF") or os.path.join(HERE, "qr-reference.json")


def extract_qr_module(path):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"<script>\s*(.*?)</script>", src, re.S)
    body = m.group(1)
    start = body.index("const QR = (() => {")
    end = body.index("/* ============================================================\n   画面まわり")
    return body[start:end]


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


if __name__ == "__main__":
    main()
