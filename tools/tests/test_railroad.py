#!/usr/bin/env python3
"""正規表現の鉄道図ツールの検証（2026-08-23）。

見るのは4つ。

1. **受け付ける／拒む が、ブラウザの RegExp と一致するか**
   自前パーサが通した式はブラウザも通し、拒んだ式はブラウザも拒む。
   これがパーサの正しさの本体。ランダム生成した式と、それをわざと壊した式の両方を当てる。

2. **図から作った例が、元の正規表現にマッチするか**
   ページ内の自己検査と同じことを大量の式でまとめて回す。
   図（＝解析結果）と式の意味が食い違っていたらここで落ちる。

3. **同じ例を Python の `re` に当てても通るか**
   参照をブラウザだけにすると、ブラウザと自分が同じ勘違いをしたときに気づけない。
   出どころの違う実装（CPython）にも当てる。JS 固有の書き方は対象から外す。

4. **図が描けるか**（SVG が出る・幅高さが正・NaN が混ざらない・読み下しが例外を出さない）

⚠ 2 と 3 は「安全な形」の式だけで回す。
   くり返しの中がくり返しになっている式は、こちらの生成が1つでも外れた瞬間に
   正規表現エンジンが指数時間に入り、ブラウザごと止まる。パーサの検査（1・4）は
   その形も含めて全部当てるが、例文字列を当てるのは安全な形に限る。

使い方: python lab/scripts/test_railroad.py [--n 3000] [--url file:///...]
"""
import argparse, random, re, sys, pathlib

ATOMS = [
    "a", "b", "z", "0", "9", "_", "-", " ", "@", "%",
    r"\d", r"\w", r"\s", r"\D", r"\W", r"\S", ".",
    "[a-z]", "[A-Z0-9]", "[^abc]", r"[\d.]", "[a-fA-F0-9]", "[-a-z]", "[a-z-]",
    r"\.", r"\+", r"\\", r"\t", r"\n", r"\x41", r"\u0062",
]
Q_ALL = ["", "", "", "*", "+", "?", "{2}", "{1,3}", "{2,}", "*?", "+?", "??", "{1,3}?"]
Q_BOUNDED = ["", "", "", "?", "{2}", "{1,3}", "??", "{1,3}?"]   # 上限のあるものだけ


def gen_regex(rnd, safe, depth=0, exotic=False):
    """JS と Python で意味の変わらない範囲でランダムな式を作る。

    safe=True のときは「上限のないくり返し」をグループに掛けない。
    こうすると入れ子の無限くり返しが構文的に作られないので、
    外したときの指数爆発が起きない（例文字列の検査に使えるようになる）。

    exotic=True では、名前つきグループ・後方参照・先読み・アンカーも混ぜる。
    こちらは「受け付ける／拒む」と作図の検査にだけ使う（例文字列は当てない）。
    """
    n = rnd.randint(1, 3 if depth else 4)
    parts = []
    for _ in range(n):
        r = rnd.random()
        if exotic and r < 0.16 and depth < 2:
            body = rnd.choice([
                "(?=" + gen_regex(rnd, safe, depth + 1) + ")",
                "(?!" + gen_regex(rnd, safe, depth + 1) + ")",
                "(?<=" + gen_regex(rnd, safe, depth + 1) + ")",
                "(?<!" + gen_regex(rnd, safe, depth + 1) + ")",
                "(?<g%d>" % rnd.randint(1, 4) + gen_regex(rnd, safe, depth + 1) + ")",
                "^", "$", r"\b", r"\B",
            ])
            parts.append(body)          # アンカーには量指定子を付けられない
            continue
        if r < 0.55 or depth >= 2:
            body, grouped = rnd.choice(ATOMS), False
        elif r < 0.75:
            body = rnd.choice(["(", "(?:", "(?:"]) + gen_regex(rnd, safe, depth + 1, exotic) + ")"
            grouped = True
        else:
            body = ("(?:" + gen_regex(rnd, safe, depth + 1, exotic) + "|"
                    + gen_regex(rnd, safe, depth + 1, exotic) + ")")
            grouped = True
        q = rnd.choice(Q_BOUNDED if (safe and grouped) else Q_ALL)
        # 「空にもなれる中身」に上限なしのくり返しを掛けない（同じ理由）
        if safe and q in ("*", "+", "*?", "+?", "{2,}") and body.endswith(("?", "*")):
            q = ""
        parts.append(body + q)
    return "".join(parts)


# 自動生成では出にくい形。ここは人手で並べる（ECMAScript の Annex B まわりが多い）
EDGE_CASES = [
    r"\x4", r"\xZZ", r"\u12", r"\u{41}", r"\u{110000}", r"\c1", r"\cA", r"\k<a>",
    r"(?<a>x)\k<a>", r"(?<a>x)\k<b>", r"(?<1a>x)", "(a)\\1", "(a)\\2", "\\1(a)",
    "{3}", "{3,1}", "a{3,1}", "a**", "a?{2}", "a??", "a???", "{abc}", "a{abc}",
    "[]", "[^]", "[a-]", "[-a]", "[a-z-0]", "[z-a]", r"[\d-x]", r"[\w-\d]",
    "(?:)", "()", "(|)", "a|", "|a", "||", "()*", "(?=a)*", "^*",
    r"\0", r"\08", r"\p{L}", r"\P{L}", "(?<=a)b", "(?<!a)b", "a)", "(a",
    "[a", r"a\\", "*", "+a", "?a", r"\b*", "(?#x)", "(?P<n>a)", "[[]", "[]]",
    # 同じ名前のグループ。「同じ | の別の枝」なら置けて、それ以外は置けない
    "(?<a>x)(?<a>y)", "(?<a>x)|(?<a>y)", "((?<a>x)|(?<a>y))z", "(?<a>x)(?:|(?<a>y))",
    "(?:(?<a>x)|b)|(?<a>y)", "(?<a>x)[(?<a>y)]", "(?<a>x)(?<b>y)(?<a>z)",
    "(?:(?<a>x)|(?<a>y))(?<a>z)", "(?<a>(?<a>x))",
    # くり返しの付けられない相手
    "(?=a)*", "(?<=a)*", "(?<!a)+", "(?:a)*", r"\b?", "^?", "$*",
]


BREAKERS = [
    lambda s: s + "(",
    lambda s: s + ")",
    lambda s: s + "[",
    lambda s: s + "*",
    lambda s: "*" + s,
    lambda s: s + "{3,1}",
    lambda s: s + "[z-a]",
    lambda s: s + "\\",
    lambda s: s + r"\x4",
    lambda s: s + r"\u12",
    lambda s: s + "(?#comment)",
    lambda s: s + r"\k<nope>",
]

JS_ONLY = re.compile(r"\\[cku]|\(\?<|\\k<")

JS = r"""([pats, doSamples, flags]) => {
  const out = {accept: [], draw: [], rows: []};
  for (const src of pats) {
    let mine = null, msg = '';
    try { mine = parseRegex(src, flags); } catch (e) { msg = e.msg || String(e); }
    let theirs = true;
    try { new RegExp(src, flags); } catch (e) { theirs = false; }
    if (!!mine !== theirs) out.accept.push({src, flags, mine: !!mine, theirs, msg});
    if (!mine) continue;
    try {
      const svg = renderDiagram(mine.node);
      const m = /width="(\d+)" height="(\d+)"/.exec(svg);
      if (!m || +m[1] <= 0 || +m[2] <= 0) out.draw.push({src, why: 'サイズが0'});
      else if (svg.indexOf('NaN') >= 0) out.draw.push({src, why: 'NaN が混ざった'});
    } catch (e) { out.draw.push({src, why: '作図: ' + e}); }
    try { readItems(mine.node); } catch (e) { out.draw.push({src, why: '読み下し: ' + e}); }
    try { analyze(mine, src, flags); } catch (e) { out.draw.push({src, why: '落とし穴検出: ' + e}); }
    if (!doSamples) continue;
    const chk = selfCheck(mine, src, flags, 6);
    if (chk.skipped) continue;
    out.rows.push({src, unsure: chk.unsure,
                   ss: chk.rows.map(r => r.s), ok: chk.rows.map(r => r.ok)});
  }
  return out;
}"""


def batched(pg, pats, do_samples, flags="", chunk=40):
    acc = {"accept": [], "draw": [], "rows": []}
    for k in range(0, len(pats), chunk):
        part = pats[k:k + chunk]
        try:
            r = pg.evaluate(JS, [part, do_samples, flags])
        except Exception as e:                       # 1回で止まったら犯人が分かるように潰す
            print(f"  !! この束で止まった: {part[:3]} …  ({e})")
            continue
        for key in acc:
            acc[key] += r[key]
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--url", default=None, help="検証するページ（既定は docs/railroad/index.html を探す）")
    ap.add_argument("--seed", type=int, default=20260823)
    args = ap.parse_args()

    if args.url:
        url = args.url
    else:
        cand = sorted(pathlib.Path.cwd().glob("**/docs/railroad/index.html"))
        if not cand:
            sys.exit("ページが見つかりません。--url で指定してください")
        url = cand[0].as_uri()

    rnd = random.Random(args.seed)
    wild = ([gen_regex(rnd, safe=False) for _ in range(args.n // 2)] +
            [gen_regex(rnd, safe=False, exotic=True) for _ in range(args.n // 2)] +
            EDGE_CASES)
    broken = [rnd.choice(BREAKERS)(gen_regex(rnd, safe=False)) for _ in range(args.n // 2)]
    safe = [gen_regex(rnd, safe=True) for _ in range(args.n)]

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(url)
        pg.wait_for_timeout(300)
        if errs:
            sys.exit("ページ読み込みでJSエラー: " + errs[0])
        a = batched(pg, wild + broken, False)
        au = batched(pg, wild + broken, False, flags="u")   # u フラグ付きでも一致するか
        b = batched(pg, safe, True)
        br.close()

    accept = a["accept"] + au["accept"] + b["accept"]
    draw = a["draw"] + au["draw"] + b["draw"]
    fails = 0
    n_checked = (len(wild) + len(broken)) * 2 + len(safe)
    print(f"式 {len(wild)}本（形の制限なし）+ わざと壊した式 {len(broken)}本"
          f" + 安全な形 {len(safe)}本 で検査した"
          f"（前2つは u フラグの有無どちらでも当てたので、のべ {n_checked} 本）\n")

    print("[1] 受け付ける／拒む が RegExp と一致するか … ", end="")
    if accept:
        fails += 1
        print(f"不一致 {len(accept)} 件 / のべ {n_checked} 本中")
        for r in accept[:12]:
            print(f"    {r['src']!r} /{r['flags']}  自前={r['mine']} ブラウザ={r['theirs']}  {r['msg']}")
    else:
        print(f"のべ {n_checked} 本すべて一致")

    print("[2] 図から作った例が元の式にマッチするか … ", end="")
    mismatch, n_samples = [], 0
    for r in b["rows"]:
        for s, ok in zip(r["ss"], r["ok"]):
            n_samples += 1
            if not ok and not r["unsure"]:
                mismatch.append((r["src"], s))
    if mismatch:
        fails += 1
        print(f"不一致 {len(mismatch)} 件 / {n_samples} 件中")
        for src, s in mismatch[:12]:
            print(f"    {src!r} → {s!r}")
    else:
        print(f"{n_samples} 件すべてマッチ")

    print("[3] 同じ例を Python の re に当てる … ", end="")
    py_fail, py_n, py_skip = [], 0, 0
    for r in b["rows"]:
        src = r["src"]
        if JS_ONLY.search(src) or r["unsure"]:
            py_skip += 1
            continue
        try:
            cre = re.compile(src)
        except re.error:
            py_skip += 1
            continue
        for s in r["ss"]:
            py_n += 1
            if not cre.fullmatch(s):
                py_fail.append((src, s))
    if py_fail:
        fails += 1
        print(f"不一致 {len(py_fail)} 件 / {py_n} 件中")
        for src, s in py_fail[:12]:
            print(f"    {src!r} → {s!r}")
    else:
        print(f"{py_n} 件すべて一致（JS固有などで対象外にした式 {py_skip} 本）")

    print("[4] 図・読み下し・落とし穴検出が例外なく出るか … ", end="")
    if draw:
        fails += 1
        print(f"失敗 {len(draw)} 件")
        for r in draw[:12]:
            print(f"    {r['src']!r}  {r['why']}")
    else:
        print("全部通った")

    print("\n結果: " + ("問題なし" if fails == 0 else f"{fails} 項目で失敗"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
