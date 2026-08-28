#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「画像リサイズ・圧縮」を、実際に変換させて確かめる(2026-08-28 新設)。

この道具だけ検証スクリプトが1本も無かった。ページを開いて本物の画像を食わせ、
**出てきた画像を Pillow で読み直して**、寸法・形式・透過の扱い・削減率の表示を見る。

参照はページの中の値ではなく**別の出どころ**にする:
  - 目標の寸法 … Python で独立に計算した値(`expect_size`)
  - 実際の寸法・形式 … Pillow が出力画像を読んだ値
  - 削減率の表示 … 出力の実バイト数から計算した値

使い方:
    python lab/scripts/test_image.py                       # 手元の docs/image/index.html
    python lab/scripts/test_image.py <ページのURLかパス>    # 英語版・本番にも同じものを当てる
"""
import base64, io, math, pathlib, sys, tempfile

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
from playwright.sync_api import sync_playwright

# 公開版はリポジトリの中を見る(手元版だけ既定パスが違う)
DEFAULT = pathlib.Path(__file__).resolve().parents[2] / "docs" / "image" / "index.html"

# (名前, 幅, 高さ, 透過あり)
SOURCES = [
    ("wide", 1200, 400, False),
    ("tall", 400, 1200, False),
    ("square", 900, 900, True),
    ("small", 120, 90, False),
    # ★2026-08-28: 上の4枚は割り切れる寸法ばかりで、**目標の寸法に小数が出る組み合わせが
    #   1つも無かった**。そのせいで「四捨五入を切り捨てにする」バグが空振り確認を素通りした
    #   (Math.round と Math.floor の結果が全部同じだった)。半端な寸法を1枚足して塞いだ。
    #   例: 幅250 → 高さ 667×250/1001 = 166.58…(round 167 / floor 166)
    #       150% → 1001×1.5 = 1501.5(round 1502 / floor 1501)
    ("odd", 1001, 667, False),
]

# (モード, 入力値, 形式, 画質)
CASES = [
    ("longest", 300, "image/jpeg", 0.82),
    ("longest", 5000, "image/jpeg", 0.82),   # 引き伸ばさない = 元のまま
    ("width", 250, "image/webp", 0.7),
    ("height", 250, "image/png", 1.0),
    ("percent", 50, "image/jpeg", 0.9),
    ("percent", 150, "image/webp", 0.8),
    ("none", 1600, "image/jpeg", 0.5),
]


def make_source(w, h, alpha):
    """毎回同じ絵を作る(乱数を使わないので結果が揺れない)。"""
    img = Image.new("RGBA" if alpha else "RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            r = (x * 255) // max(1, w - 1)
            g = (y * 255) // max(1, h - 1)
            b = ((x + y) * 255) // max(1, w + h - 2)
            if alpha:
                px[x, y] = (r, g, b, 0 if (x // 60 + y // 60) % 2 else 255)
            else:
                px[x, y] = (r, g, b)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def expect_size(ow, oh, mode, n):
    """ページと同じ規則を Python 側で独立に書き下す(ページの値は見ない)。"""
    if mode == "none" or n <= 0:
        return ow, oh
    if mode == "percent":
        w, h = ow * n / 100, oh * n / 100
    elif mode == "width":
        w, h = n, oh * (n / ow)
    elif mode == "height":
        h, w = n, ow * (n / oh)
    else:                                    # longest
        scale = n / max(ow, oh)
        if scale >= 1:
            return ow, oh                    # 引き伸ばさない
        w, h = ow * scale, oh * scale
    return (max(1, min(20000, round_half_up(w))),
            max(1, min(20000, round_half_up(h))))


def round_half_up(v):
    """JS の Math.round は .5 を上に丸める(Python の round は偶数丸め)。"""
    return math.floor(v + 0.5)


def pct_text(before, after):
    if not before:
        return ""
    d = 1 - after / before
    if d >= 0:
        return min(99, round_half_up(d * 100))
    return -round_half_up(-d * 100)


def run(url):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="imgtest-"))
    paths = {}
    for name, w, h, alpha in SOURCES:
        p = tmp / ("%s.png" % name)
        p.write_bytes(make_source(w, h, alpha))
        paths[name] = p

    ok = bad = 0
    notes = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url, wait_until="load")

        for mode, n, fmt, q in CASES:
            pg.reload(wait_until="load")
            pg.set_input_files("#file", [str(p) for p in paths.values()])
            pg.select_option("#mode", mode)
            if mode != "none":
                pg.fill("#size", str(n))
            pg.select_option("#format", fmt)
            pg.eval_on_selector("#quality",
                                "(el, v) => { el.value = v; el.dispatchEvent(new Event('input')); }", str(q))
            pg.click("#run")
            pg.wait_for_function("() => !document.getElementById('run').disabled", timeout=60000)

            # 出力を blob から取り出して base64 で持ち帰る
            outs = pg.evaluate("""async () => {
                const rows = [...document.querySelectorAll('.item')];
                const out = [];
                for (const row of rows) {
                    const a = row.querySelector('a.dl');
                    if (!a) { out.push(null); continue; }
                    const buf = await (await fetch(a.href)).arrayBuffer();
                    let s = ''; const b = new Uint8Array(buf);
                    for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
                    out.push({ b64: btoa(s), name: a.getAttribute('download'),
                               meta: row.innerText });
                }
                return out;
            }""")

            for (name, w, h, alpha), got in zip(SOURCES, outs):
                label = "%s %s=%s %s q=%s" % (name, mode, n, fmt.split("/")[1], q)
                if got is None:
                    notes.append("!! 出力が無い: " + label); bad += 1; continue
                data = base64.b64decode(got["b64"])
                im = Image.open(io.BytesIO(data))
                ew, eh = expect_size(w, h, mode, n)
                if (im.width, im.height) != (ew, eh):
                    notes.append("!! 寸法が違う %s: 期待 %dx%d / 実際 %dx%d"
                                 % (label, ew, eh, im.width, im.height))
                    bad += 1
                    continue
                want_fmt = {"image/jpeg": "JPEG", "image/webp": "WEBP", "image/png": "PNG"}[fmt]
                if im.format != want_fmt:
                    notes.append("!! 形式が違う %s: 期待 %s / 実際 %s" % (label, want_fmt, im.format))
                    bad += 1
                    continue
                # 透過: JPEG は白で埋まる(アルファのチャンネルが残らない)
                if want_fmt == "JPEG" and im.mode not in ("RGB", "L"):
                    notes.append("!! JPEG なのに %s モード: %s" % (im.mode, label)); bad += 1; continue
                # 画面に出ている削減率が、実バイト数から計算した値と合うか
                before = paths[name].stat().st_size
                p = pct_text(before, len(data))
                want = ("%d%% smaller" % p) if isinstance(p, int) and p >= 0 else None
                if want and ("smaller" in got["meta"] or "削減" in got["meta"]):
                    ja = "%d%%削減" % p
                    if want not in got["meta"] and ja not in got["meta"]:
                        notes.append("!! 削減率の表示が合わない %s: 期待 %s / 画面 %r"
                                     % (label, want, got["meta"][-60:]))
                        bad += 1
                        continue
                ok += 1
        br.close()

    for s in notes[:20]:
        print(" ", s)
    print()
    print("見たページ: %s" % url)
    print("試した組み合わせ: %d 件 / 一致: %d / 食い違い: %d" % (ok + bad, ok, bad))
    print("JSエラー: %d 件" % len(errs))
    return 0 if (bad == 0 and not errs) else 1


# わざと入れるバグ。(名前, 元の断片, 差し替える断片)
# ★これを通さないと、検査が本当に何かを見ているのか分からない。
SABOTAGE = [
    ("引き伸ばさない規則を外す",
     "    if (scale >= 1) return [ow, oh];            // 引き伸ばさない",
     "    if (false) return [ow, oh];"),
    ("四捨五入を切り捨てにする",
     "  w = Math.max(1, Math.min(MAXW, Math.round(w)));",
     "  w = Math.max(1, Math.min(MAXW, Math.floor(w)));"),
    ("幅指定で高さを比率で決めない",
     "  else if (m === \"width\")  { w = n; h = oh * (n / ow); }",
     "  else if (m === \"width\")  { w = n; h = oh; }"),
    ("形式の指定を無視する",
     "  const type = $(\"format\").value, q = +$(\"quality\").value;",
     "  const type = \"image/png\", q = +$(\"quality\").value;"),
    ("削減率を1割ずらす",
     "  if (d >= 0) return Math.min(99, Math.round(d * 100)) + \"%削減\";",
     "  if (d >= 0) return Math.min(99, Math.round(d * 100) + 10) + \"%削減\";"),
]


def sabotage(path):
    src = pathlib.Path(path).read_text(encoding="utf-8")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="imgsab-"))
    caught = missed = 0
    for name, old, new in SABOTAGE:
        if old not in src:
            print("  !! 壊す場所が見つからない: %s" % name); missed += 1; continue
        p = tmp / "index.html"
        p.write_text(src.replace(old, new, 1), encoding="utf-8")
        rc = run(p.resolve().as_uri())
        if rc:
            print("  捕まえた: %s\n" % name); caught += 1
        else:
            print("  ★ 素通りした: %s\n" % name); missed += 1
    print("空振り確認: %d/%d を検出" % (caught, len(SABOTAGE)))
    return 0 if missed == 0 else 1


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sabotage"]
    arg = args[0] if args else str(DEFAULT)
    if "--sabotage" in sys.argv:
        sys.exit(sabotage(arg))
    url = arg if arg.startswith("http") else pathlib.Path(arg).resolve().as_uri()
    sys.exit(run(url))
