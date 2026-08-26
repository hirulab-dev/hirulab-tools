#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「Base64・データURLの分解」の検証（2026-08-27）。

この道具が主張していることに、**別の出どころの正解**をそれぞれ当てる。
参照が1つだと、こちらと参照が同じ勘違いをしたときに気づけないので分けてある。

1. **base64 の復号・符号化が Python の `base64` と一致するか**
   この道具は `atob` / `btoa` を使わず自前で書いてある（自己検査でだけ使う）ので、
   Python の標準ライブラリに当てる意味がある。詰めの有無・字表の両方を振る。

2. **★データURLの分解が Python の `urllib.request` と一致するか**
   ここがいちばん強い参照。Python の `urllib.request` には `DataHandler` という
   **データURL専用のパーサ**が標準で入っていて、`urlopen("data:...")` が
   メディア型と中身のバイト列を返す。**別の言語の第三者実装**なので、
   自前の RFC 2397 解析に当てる価値がある。
   ⚠ ただし DataHandler は「厳しすぎる／緩すぎる」ところが実際にあるので
   （下の [2b]）、食い違う形は先に洗い出して分けて数える。

3. **★中身の判定を「本物のファイル」に当てる**
   マジックナンバーの表を手で書くと、表と検査が同じ勘違いをする。
   なので Pillow に**実際に PNG / JPEG / GIF / BMP / TIFF / WebP を書かせて**、
   その生バイトを道具に食わせる。参照は「Pillow がその形式として保存した」という事実。

4. **正解の分かっている落とし穴を名指しできるか**
   26 種類ぜんぶに、その形を持つ入力を1つずつ用意して `data-code` で照合する
   （画面の文言で見ると英語版に当たらないので、最初から機械可読な鍵にしてある）。

5. **ページ内の自己検査が全部通っているか**

わざと壊して検査が空振りしていないかを見る `--sabotage` つき。
対象外にした件数は `skipwatch` で毎回目に見えるところに出す。

使い方:
  python lab/scripts/test_base64.py [--n 400] [--page docs/base64/index.html]
  python lab/scripts/test_base64.py --sabotage
"""
import argparse
import base64
import binascii
import io
import os as _os
import pathlib
import random
import sys
import tempfile
import urllib.request

_os.sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from skipwatch import SkipWatch

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

DEFAULT_PAGE = pathlib.Path("docs/base64/index.html")

STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
URLSAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


# ================================================================== ページ側に投げる JS

# 分解して、道具が出す答えを機械可読な形で返す。
# 画面の HTML ではなく analyze() を直接呼ぶ（文言に依存しないため）。
JS_ANALYZE = """
(inputs) => inputs.map(src => {
  try {
    const a = analyze(src);
    return {
      bytes: Array.from(a.bytes),
      codes: a.notes.map(n => n.code),
      isData: a.du.isData,
      type: a.du.isData ? a.du.type : null,
      base64Flag: a.du.isData ? a.du.base64 : null,
      kindMime: a.kind.mime,
      kindName: a.kind.name,
      threw: null
    };
  } catch (e) { return { threw: String(e) }; }
})
"""

JS_ENCODE = """
(cases) => cases.map(c => {
  try { return b64Encode(new Uint8Array(c.bytes), c.alpha, c.pad); }
  catch (e) { return "THREW:" + e; }
})
"""

JS_DECODE = """
(strs) => strs.map(s => {
  try {
    const r = b64Decode(s);
    return { bytes: Array.from(r.bytes), dropped: r.dropped, pads: r.pads,
             slackBits: r.slackBits, slackValue: r.slackValue };
  } catch (e) { return { threw: String(e) }; }
})
"""

JS_SELF = """
() => {
  const rows = [];
  document.querySelectorAll('#selfOut .row').forEach(r => {
    rows.push({ ok: !!r.querySelector('.mark.ok'), text: r.textContent.trim() });
  });
  return rows;
}
"""


# ================================================================== 生成器

def rand_bytes(rnd, n):
    return bytes(rnd.randrange(256) for _ in range(n))


def gen_b64_case(rnd):
    """符号化・復号の突き合わせ用。長さ・字表・詰めの有無を振る。"""
    n = rnd.choice([0, 1, 2, 3, 4, 5, 6, 7, 8, 15, 16, 17, 31, 64, 100])
    data = rand_bytes(rnd, n)
    alpha = rnd.choice(["std", "url"])
    pad = rnd.choice([True, False])
    return {"bytes": data, "alpha": alpha, "pad": pad}


def py_b64encode(data, alpha, pad):
    s = (base64.urlsafe_b64encode(data) if alpha == "url" else base64.b64encode(data)).decode()
    if not pad:
        s = s.rstrip("=")
    return s


def py_b64decode(s, alpha):
    """Python 側の復号。字表をそろえ、詰めを補ってから validate=True で厳しく読む。"""
    t = s
    if alpha == "url":
        t = t.replace("-", "+").replace("_", "/")
    t = t.rstrip("=")
    t += "=" * (-len(t) % 4)
    return base64.b64decode(t, validate=True)


# --------------------------------------------------------------- データURL

def gen_dataurl_case(rnd):
    """データURLの分解を Python の DataHandler と突き合わせるための素材。

    ⚠ ここで作るのは「両者が同じ答えを出すはずの、素直な形」だけ。
       規格の縁にある形は [4] の落とし穴で別に見る。
    """
    # ★ "comma" は 2026-08-27 の --sabotage で見つかった穴。
    #    本体にコンマを含む形が1件も無かったので、コンマを後ろから探す壊しかたが
    #    どの検査にも捕まらなかった（indexOf と lastIndexOf の結果が常に同じだった）。
    kind = rnd.choice(["b64", "pct", "plain", "comma"])
    mime = rnd.choice(["text/plain", "image/png", "application/json",
                       "text/plain;charset=UTF-8", "application/octet-stream"])
    n = rnd.choice([0, 1, 2, 3, 5, 12, 40])
    data = rand_bytes(rnd, n)
    if kind == "b64":
        return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode()), data, mime
    if kind == "pct":
        body = "".join("%%%02X" % b for b in data)
        return "data:%s,%s" % (mime, body), data, mime
    if kind == "comma":
        # 本体そのものにコンマが入る形（RFC 2397 では最初のコンマだけが区切り）
        txt = ",".join("".join(rnd.choice("abcXYZ019-._~") for _ in range(rnd.randrange(4)))
                       for _ in range(rnd.randrange(2, 5)))
        return "data:%s,%s" % (mime, txt), txt.encode(), mime
    # 安全な ASCII だけの生書き
    txt = "".join(rnd.choice("abcXYZ019-._~") for _ in range(n))
    return "data:%s,%s" % (mime, txt), txt.encode(), mime


def py_dataurl(url):
    """Python 標準の DataHandler で読む（第三者実装の参照）。"""
    with urllib.request.urlopen(url) as f:
        return f.read(), f.headers.get_content_type()


# --------------------------------------------------------------- 本物のファイル

def real_files():
    """Pillow に実際に書かせた本物の画像 + 手元で作れる非画像。

    参照は「そのライブラリがその形式として保存した」という事実。
    マジックナンバーの表を手で書き写した値ではない。
    """
    out = []
    try:
        from PIL import Image
    except ImportError:
        print("  !! Pillow が無いので [3] は動かせません")
        return out

    for fmt, mime, name in [("PNG", "image/png", "PNG"), ("JPEG", "image/jpeg", "JPEG"),
                            ("GIF", "image/gif", "GIF"), ("BMP", "image/bmp", "BMP"),
                            ("TIFF", "image/tiff", "TIFF"), ("WEBP", "image/webp", "WebP")]:
        for size in [(1, 1), (8, 5), (32, 32)]:
            im = Image.new("RGB", size, (200, 30, 90))
            buf = io.BytesIO()
            try:
                im.save(buf, format=fmt)
            except Exception:
                continue
            out.append((buf.getvalue(), mime, "%s %dx%d" % (name, size[0], size[1])))

    # 画像以外は、その形式の定義そのものから組み立てる
    import gzip
    import zipfile
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "hello")
    out.append((z.getvalue(), "application/zip", "ZIP（zipfile が作ったもの）"))
    out.append((gzip.compress(b"hello world" * 5), "application/gzip", "gzip（gzip が作ったもの）"))
    out.append((b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n",
                "application/pdf", "PDF（最小の骨格）"))
    out.append(("こんにちは、世界。\n2行目。".encode("utf-8"), "text/plain", "UTF-8 テキスト"))
    out.append((b'{"a":1,"b":[2,3]}', "application/json", "JSON"))
    out.append(('<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"></svg>'.encode(),
                "image/svg+xml", "SVG"))
    out.append((b"<!doctype html><html><body>x</body></html>", "text/html", "HTML"))
    return out


# --------------------------------------------------------------- 落とし穴

def pitfall_cases():
    """(コード, 説明, 入力) — その入力を貼ったら必ずそのコードが出るはず。"""
    png = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
           "IQAAAABJRU5ErkJggg==")
    jpeg = base64.b64encode(bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10]) + b"JFIF" + b"\x00" * 20).decode()
    cases = [
        ("du-no-comma", "コンマが無い", "data:image/png;base64"),
        ("du-base64-flag-missing", ";base64 の書き忘れ", "data:image/png," + png),
        ("du-plus-space", "+ は空白にならない", "data:text/plain,1+1"),
        ("du-percent-bad", "% のあとが16進2桁でない", "data:text/plain,100%discount"),
        ("du-mediatype-default", "型を省略したときの既定", "data:,hello"),
        ("du-newline", "中に改行", "data:text/plain;base64,aGVs\nbG8="),
        ("du-mime-mismatch", "宣言と中身の食い違い", "data:image/png;base64," + jpeg),
        ("du-svg-script", "SVG にスクリプト", "data:image/svg+xml;base64," + base64.b64encode(
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>').decode()),
        ("du-html-nav", "data:text/html はリンクで開けない", "data:text/html;base64," + base64.b64encode(
            b"<!doctype html><html><body>hi</body></html>").decode()),
        ("du-size", "データURLが長すぎる", "data:text/plain;base64," + base64.b64encode(b"x" * 30000).decode()),
        ("du-charset-odd", "宣言された文字コードと中身", "data:text/plain;charset=Shift_JIS;base64," +
            base64.b64encode("日本語".encode("utf-8")).decode()),

        ("b64-mixed", "字表の混在", "ab-d+f_hi/kAAAA"),
        ("b64-bad", "字表にない文字", "aGVsbG8h@#$="),
        ("b64-percent", "％が混ざっている（二重符号化）", "aGVsbG8%2Fdw=="),
        ("b64-len1", "4で割った余りが1", "aGVsbG8xY"),
        ("b64-pad-mid", "詰めのあとにデータ", "aGVs=bG8="),
        ("b64-pad-missing", "詰めが無い", "aGVsbG8"),
        ("b64-pad-count", "詰めの数が合わない", "aGVsbG8h===="),
        ("b64-ws", "空白が入っている", "aGVs bG8="),
        ("b64-slack", "余ったビットが0でない", "QR=="),
        ("b64-not-encryption", "base64 は暗号ではない", "c2VjcmV0"),

        ("dec-bom", "先頭に BOM", "data:text/plain;base64," + base64.b64encode(
            b"\xef\xbb\xbfhello").decode()),
        ("dec-utf8-bad", "UTF-8 として読めない", "data:text/plain;base64," + base64.b64encode(
            b"abc\xc3\x28def").decode()),
        # ★ 下の2件は 2026-08-27 の --sabotage で見つかった穴。
        #    dec-utf8-bad の入力が「継続バイトが来ない」形だけだったので、
        #    overlong を見逃す壊しかたがどの検査にも捕まらなかった。
        #    UTF-8 が不正になる道は1本ではない、という当たり前の話。
        ("dec-utf8-bad", "overlong な UTF-8（C0 AF は 2F の遠回りな書き方）",
            "data:text/plain;base64," + base64.b64encode(
                b"ok" + bytes([0xC0, 0xAF]) + b"ok").decode()),
        ("dec-utf8-bad", "サロゲートの符号位置がそのまま符号化されている",
            "data:text/plain;base64," + base64.b64encode(
                b"ok" + bytes([0xED, 0xA0, 0x80]) + b"ok").decode()),
        ("dec-nul", "NUL バイト", "data:text/plain;base64," + base64.b64encode(
            b"abc\x00def").decode()),
        ("dec-ctrl", "画面に出ない制御文字", "data:text/plain;base64," + base64.b64encode(
            b"abc\x01\x02def").decode()),
    ]
    return cases


# --------------------------------------------------------------- わざと壊す

SABOTAGE = [
    # 1. 詰めの計算をずらす → [1] の復号か [4] の b64-pad-* が落ちるはず
    ("var wantPad = rem === 0 ? 0 : 4 - rem;",
     "var wantPad = rem === 0 ? 0 : 3 - rem;",
     "詰めの本数の計算を1ずらす"),
    # 2. 余ったビットを見ない → [4] の b64-slack が落ちるはず
    ("r.slackValue = nbits ? (acc & ((1 << nbits) - 1)) : 0;",
     "r.slackValue = 0;",
     "余ったビットを常に0とみなす"),
    # 3. 復号でビットを1つずらす → [1] が落ちるはず
    ("out[o++] = (acc >> nbits) & 0xff;",
     "out[o++] = (acc >> nbits) & 0xfe;",
     "復号したバイトの最下位ビットを落とす"),
    # 4. JPEG のマジックを1バイト変える → [3] が落ちるはず
    ("return startsWith(b, [0xff, 0xd8, 0xff]);",
     "return startsWith(b, [0xff, 0xd8, 0xfe]);",
     "JPEG のマジックナンバーを間違える"),
    # 5. 宣言との突き合わせを止める → [4] の du-mime-mismatch が落ちるはず
    ("if (actual && declared && declared !== actual) {",
     "if (actual && declared && false) {",
     "宣言と中身の突き合わせを止める"),
    # 6. データURLのコンマ探しを最後から探す → [2] が落ちるはず
    ("var ci = rest.indexOf(\",\");",
     "var ci = rest.lastIndexOf(\",\");",
     "データURLのコンマを後ろから探す"),
    # 7. 符号化の最終ブロックを取りこぼす → [1] が落ちるはず
    ("var left = bytes.length - i;",
     "var left = 0;",
     "符号化で最後の半端なブロックを捨てる"),
    # 8. UTF-8 の overlong を見ない → [4] の dec-utf8-bad が落ちるはず
    ("if (cp < min) { r.ok = false; r.overlong = true;",
     "if (false) { r.ok = false; r.overlong = true;",
     "overlong な UTF-8 を見逃す"),
]


# ================================================================== 本体

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--page", default=None)
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true")
    args = ap.parse_args()

    page = pathlib.Path(args.page) if args.page else DEFAULT_PAGE
    if not page.exists():
        cand = sorted(pathlib.Path.cwd().glob("**/docs/base64/index.html"))
        if not cand:
            sys.exit("ページが見つかりません。--page で指定してください")
        page = cand[0]
    text = page.read_text(encoding="utf-8")

    rnd = random.Random(args.seed)
    b64_cases = [gen_b64_case(rnd) for _ in range(args.n)]
    du_cases = [gen_dataurl_case(rnd) for _ in range(args.n)]
    files = real_files()
    pits = pitfall_cases()

    variants = [("そのまま", text)]
    if args.sabotage:
        for old, new, name in SABOTAGE:
            if old not in text:
                print("  !! 仕込み先が見つからない: %s" % name)
                continue
            variants.append(("壊した: " + name, text.replace(old, new, 1)))

    tmpdir = tempfile.mkdtemp(prefix="b64-test-")
    exit_code = 0

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for vi, (label, body) in enumerate(variants):
            fp = pathlib.Path(tmpdir) / ("v%d.html" % vi)
            fp.write_text(body, encoding="utf-8")
            pg = br.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(fp.as_uri())
            pg.wait_for_timeout(300)
            print("\n=== %s ===" % label)
            if errs:
                print("  !! JSエラー: %s" % errs[:3])
            ng = 0
            sw = SkipWatch("test_base64", update=args.update_skip_baseline)

            # ------------------------------------------------ [1] 符号化・復号 vs Python base64
            enc_got = pg.evaluate(JS_ENCODE, [{"bytes": list(c["bytes"]), "alpha": c["alpha"],
                                               "pad": c["pad"]} for c in b64_cases])
            strs = [py_b64encode(c["bytes"], c["alpha"], c["pad"]) for c in b64_cases]
            dec_got = pg.evaluate(JS_DECODE, strs)

            bad_enc, bad_dec, skip1 = [], [], 0
            for c, want_s, got_s, got_d in zip(b64_cases, strs, enc_got, dec_got):
                if got_s != want_s:
                    bad_enc.append((c["alpha"], c["pad"], len(c["bytes"]), want_s, got_s))
                try:
                    want_b = py_b64decode(want_s, c["alpha"])
                except binascii.Error:
                    skip1 += 1
                    continue
                if got_d.get("threw") or bytes(got_d["bytes"]) != want_b:
                    bad_dec.append((want_s[:40], want_b[:12], bytes(got_d.get("bytes", []))[:12]))
            n1 = len(b64_cases)
            ok1 = not bad_enc and not bad_dec
            print("  [1] 符号化 vs base64.b64encode / 復号 vs b64decode(validate=True): "
                  "%d 件 → 符号化ちがい %d / 復号ちがい %d" % (n1, len(bad_enc), len(bad_dec)))
            for r in bad_enc[:3]:
                print("      符号化: 字表=%s 詰め=%s %dB  期待 %s / 実際 %s" % r)
            for r in bad_dec[:3]:
                print("      復号: %s  期待 %r / 実際 %r" % r)
            sw.check("[1] base64 の符号化・復号", skipped=skip1, total=n1)
            if not ok1:
                ng += 1

            # ------------------------------------------------ [2] データURL vs Python urllib
            urls = [u for u, _d, _m in du_cases]
            du_got = pg.evaluate(JS_ANALYZE, urls)
            bad2, skip2, n2 = [], 0, 0
            for (url, want_bytes, want_mime), g in zip(du_cases, du_got):
                try:
                    py_bytes, py_mime = py_dataurl(url)
                except Exception:
                    # DataHandler が読めない形は、参照が無いので対象外
                    skip2 += 1
                    continue
                n2 += 1
                if g.get("threw"):
                    bad2.append((url[:50], "例外", g["threw"]))
                    continue
                if bytes(g["bytes"]) != py_bytes:
                    bad2.append((url[:50], py_bytes[:12], bytes(g["bytes"])[:12]))
                    continue
                # メディア型は「本体」だけ比べる（引数の持ち方が違うため）
                if g["type"].split(";")[0].strip().lower() != py_mime.lower():
                    bad2.append((url[:50], py_mime, g["type"]))
            print("  [2] データURLの分解 vs Python の urllib(DataHandler): %d 件 → ちがい %d"
                  % (n2, len(bad2)))
            for r in bad2[:3]:
                print("      %s  参照 %r / 道具 %r" % r)
            sw.check("[2] データURLの分解", skipped=skip2, total=len(du_cases))
            if bad2:
                ng += 1

            # ------------------------------------------------ [3] 中身の判定 vs 本物のファイル
            if files:
                inputs = ["data:application/octet-stream;base64," + base64.b64encode(b).decode()
                          for b, _m, _n in files]
                k_got = pg.evaluate(JS_ANALYZE, inputs)
                bad3 = []
                for (raw, want_mime, name), g in zip(files, k_got):
                    if g.get("threw") or g.get("kindMime") != want_mime:
                        bad3.append((name, want_mime, g.get("kindMime")))
                    elif bytes(g["bytes"]) != raw:
                        bad3.append((name, "バイト列が変わった", len(g["bytes"])))
                print("  [3] 中身の判定 vs 本物のファイル(Pillow ほかが実際に保存したもの): "
                      "%d 件 → ちがい %d" % (len(files), len(bad3)))
                for r in bad3[:5]:
                    print("      %s: 期待 %s / 実際 %s" % r)
                sw.check("[3] 中身の判定", skipped=0, total=len(files))
                if bad3:
                    ng += 1

            # ------------------------------------------------ [4] 落とし穴の名指し
            p_got = pg.evaluate(JS_ANALYZE, [src for _c, _d, src in pits])
            miss = []
            for (code, desc, _src), g in zip(pits, p_got):
                if g.get("threw") or code not in (g.get("codes") or []):
                    miss.append((code, desc, (g.get("codes") or [])[:4]))
            print("  [4] 落とし穴の名指し: %d/%d" % (len(pits) - len(miss), len(pits)))
            for r in miss[:8]:
                print("      名指しできず: %s（%s）出たのは %s" % r)
            sw.check("[4] 落とし穴の名指し", skipped=0, total=len(pits))
            if miss:
                ng += 1

            # ------------------------------------------------ [5] ページ内の自己検査
            rows = pg.evaluate(JS_SELF)
            bad5 = [r for r in rows if not r["ok"]]
            print("  [5] ページ内の自己検査: %d 項目中 %d 項目 一致" % (len(rows), len(rows) - len(bad5)))
            for r in bad5[:5]:
                print("      %s" % r["text"])
            if bad5 or not rows:
                ng += 1

            skip_rc = sw.report()
            print("  → %s" % ("すべて通った" if ng == 0 else "%d 項目で食い違い" % ng))
            if vi == 0:
                if ng or skip_rc:
                    exit_code = 1
            else:
                # 壊した版は「落ちる」のが正しい
                if ng == 0:
                    print("  !! この壊しかたは、どの検査にも捕まらなかった（＝検査が空振り）")
                    exit_code = 1
            pg.close()
        br.close()

    print("\n%s" % ("OK" if exit_code == 0 else "要確認"))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
