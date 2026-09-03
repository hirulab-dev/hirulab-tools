#!/usr/bin/env python3
"""「正規表現がなぜマッチしないか診断」の検証（2026-08-23）。

この道具の中身は2つある。
  (A) 自前のバックトラック照合器（止まった位置を出すため）
  (B) 「1か所だけ変えて当て直す」（直し方を名指しするため）
それぞれに、別の出どころの正解を当てる。

見るのは4つ。

1. **自前の照合器 vs ブラウザの RegExp**
   マッチするか・どこからどこまで・各グループの中身、を全部突き合わせる。
   ページ内の自己検査と同じことを大量にやる。ここが (A) の正しさの本体。

2. **「止まった位置」の主張が本当か**
   道具は「N文字目で止まった。ここで待っていたのは X だ」と言う。
   その X を**ブラウザの RegExp に作り直して**、N文字目の文字に当ててみる。
   当たってしまったら、待っていたという主張が嘘（＝止まる理由がない）。
   自前の照合器を使わずに主張を検算するので、1 とは独立した検査になる。

3. **欠陥を1つ仕込んだら、その直し方を名指しできるか**
   「当たる」組み合わせを用意し、**正解の分かっている壊し方**（末尾に空白／全角化／
   BOM を足す／CRLF／ノーブレークスペース／似たダッシュ／大文字化／ゼロ幅文字）を
   1つだけ適用する。壊れてマッチしなくなったら、道具が**その壊し方に対応する直し方**を
   出せるかを見る。ここが (B) の正しさの本体で、正解は生成側が握っている。
   正解の文言は日英どちらでもよい形にしてあるので、英語版のページにもそのまま当てられる。

4. **解析器が鉄道図ツールと1バイトも違わないか**
   この道具は 17本目（鉄道図）の解析器をそのまま使っている。
   「同じものを使っている」と画面に書いてある以上、機械で確かめる。

わざと壊して検査が空振りしていないことを見る `--sabotage` も入っている。

使い方:
  python lab/scripts/test_regex_why.py [--n 400] [--page <path or url>]
  python lab/scripts/test_regex_why.py --sabotage
"""
import argparse, html, json, pathlib, random, re, sys
import os as _os
_os.sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from skipwatch import SkipWatch

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_PAGE = pathlib.Path("docs/regex-why/index.html")   # リポジトリの根から動かす想定

# ---------------------------------------------------------------- 式の生成
# 鉄道図の検証（test_railroad.py）と同じ考え方。ただしここは「照合」を見るので、
# 上限のないくり返しの入れ子は作らない（指数爆発でブラウザが止まるため）。
ATOMS = [
    "a", "b", "z", "0", "9", "_", "-", " ", "@", "%",
    r"\d", r"\w", r"\s", r"\D", r"\W", r"\S", ".",
    "[a-z]", "[A-Z0-9]", "[^abc]", r"[\d.]", "[a-fA-F0-9]", "[-a-z]",
    r"\.", r"\+", r"\t", r"\x41", r"b",
]
Q_ALL = ["", "", "", "*", "+", "?", "{2}", "{1,3}", "{2,}", "*?", "+?", "??", "{1,3}?"]
Q_BOUNDED = ["", "", "", "?", "{2}", "{1,3}", "??", "{1,3}?"]
# 全角・ノーブレークスペース・BOM・似たハイフンも混ぜる。
# ここに入れていなかったせいで「\d が全角数字にも当たる」バグを
# 仕込んでも検査が捕まえられなかった（--sabotage で発覚。2026-08-23）。
ALPHABET = ("abz09_-. @%AB\t\n"
            "\uff11\uff21\uff41\u3000\u00a0\ufeff\u2011\u200b")



# ★2026-09-03 夜: 鉄道図の解析器は**コメントの見出しで挟んで**取り出している。
#   この日にコメントも訳したので、**英語ページでは日本語の見出しが存在しない**。
#   日英どちらの見出しでも当たる形にする(訳を変えたら、ここも直すことになる)。
RAIL_HEAD = ("/* ---- 正規表現の解析", "/* ---- Parsing the pattern")
RAIL_TAIL = ("/* ---- 鉄道図のレイアウト", "/* ---- Laying out the railroad diagram")


def _find_any(text, cands, what):
    for c in cands:
        i = text.find(c)
        if i >= 0:
            return i
    raise ValueError("%s の見出しが見つかりません(日英どちらも): %s" % (what, cands))


def gen_regex(rnd, depth=0, exotic=False):
    n = rnd.randint(1, 3 if depth else 4)
    parts = []
    for _ in range(n):
        r = rnd.random()
        if exotic and r < 0.14 and depth < 2:
            parts.append(rnd.choice([
                "(?=" + gen_regex(rnd, depth + 1) + ")",
                "(?!" + gen_regex(rnd, depth + 1) + ")",
                "(?<=" + gen_regex(rnd, depth + 1) + ")",
                "(?<!" + gen_regex(rnd, depth + 1) + ")",
                "^", "$", r"\b", r"\B",
            ]))
            continue
        if r < 0.55 or depth >= 2:
            body, grouped = rnd.choice(ATOMS), False
        elif r < 0.78:
            body = rnd.choice(["(", "(?:", "("]) + gen_regex(rnd, depth + 1, exotic) + ")"
            grouped = True
        else:
            body = ("(" + gen_regex(rnd, depth + 1, exotic) + "|"
                    + gen_regex(rnd, depth + 1, exotic) + ")")
            grouped = True
        q = rnd.choice(Q_BOUNDED if grouped else Q_ALL)
        # 「空にもなれる中身」に上限なしのくり返しを掛けない
        if q in ("*", "+", "*?", "+?", "{2,}") and body.endswith(("?", "*")):
            q = ""
        parts.append(body + q)
    return "".join(parts)


def gen_subject(rnd):
    n = rnd.randint(0, 12)
    return "".join(rnd.choice(ALPHABET) for _ in range(n))


# 自動生成では出にくい形は手で並べる（後方参照・名前つき・アンカーの絡み）
EDGE_PAIRS = [
    ("(a)\\1", ["aa", "ab", "a"]),
    ("(?<g>ab)-\\k<g>", ["ab-ab", "ab-ba"]),
    ("(a|ab)(c|bcd)", ["abcd", "acbcd"]),
    ("(a*)*b", ["aaab", "b", "aaa"]),
    ("(a?)*b", ["b", "aab", "c"]),
    ("(?:(a)|b)+", ["ab", "ba", "bb"]),
    ("^$", ["", "a"]),
    ("(?=.*a)\\w+", ["xxa", "xxx"]),
    ("(?<=ab)c", ["abc", "axc"]),
    ("(?<!ab)c", ["abc", "axc"]),
    ("a{2,4}?b", ["aaaab", "ab", "aab"]),
    ("x*?y", ["xxxy", "y", "xxx"]),
    ("(foo)?bar\\1", ["bar", "foobarfoo", "foobar"]),
    ("\\bword\\b", ["a word here", "sword"]),
    ("[\\d-x]", ["-", "x", "5", "a"]),
    ("\\x4", ["x4", "\x04"]),
    ("(?<a>x)|(?<a>y)", ["x", "y", "z"]),
    ("^(\\d{4})-(\\d{2})-(\\d{2})$", ["2026-08-23", "2026/08/23", "26-08-23"]),
    ("^[\\w.+-]+@[\\w-]+\\.[a-z]{2,}$", ["a.b@c-d.com", "a b@c.com", "a@b"]),
    ("(\\w+)\\s+\\1", ["the the", "the them"]),
    # 全角・見えない文字。ランダム生成では薄い領域なので手で置く
    ("^\\d+$", ["123", "\uff11\uff12\uff13", "1\uff12"]),
    ("^\\w+$", ["abc", "\uff41\uff42", "ab\u200b"]),
    ("\\s", [" ", "\u3000", "\u00a0", "\ufeff", "a"]),
    ("^[a-z]+$", ["abc", "\uff41\uff42", "ABC"]),
    ("^\\d-\\d$", ["1-2", "1\u20112"]),
    ("^[0-9]{2}$", ["12", "\uff11\uff12"]),
]

FLAG_SETS = ["", "", "i", "m", "s", "im", "u"]

# ------------------------------------------------------- ブラウザ側の検査
JS_COMPARE = r"""([cases]) => {
  const bad = [], skip = [];
  for (const [src, flags, subj] of cases) {
    let parsed = null;
    try { parsed = parseRegex(src, flags); } catch (e) { skip.push('式が読めない'); continue; }
    if (!engineHandles(parsed, flags)) { skip.push('対象外'); continue; }
    if (nestedUnbounded(parsed.node)) { skip.push('危険な形'); continue; }
    let re;
    try { re = new RegExp(src, flags.replace(/g/g, '')); }
    catch (e) { skip.push('ブラウザが拒む'); continue; }
    const mine = runMatch(parsed, flags, subj);
    if (mine.aborted || mine.deep) { skip.push('打ち切り'); continue; }
    let real;
    try { re.lastIndex = 0; real = re.exec(subj); } catch (e) { skip.push('当てられない'); continue; }
    const rec = {src, flags, subj};
    if (!!real !== mine.matched) { bad.push(Object.assign(rec, {why: 'マッチするかが違う',
        mine: mine.matched, real: !!real})); continue; }
    if (!real) continue;
    if (real.index !== mine.res.index) {
      bad.push(Object.assign(rec, {why: '始まる位置が違う', mine: mine.res.index, real: real.index}));
      continue;
    }
    if (real[0].length !== mine.res.end - mine.res.index) {
      bad.push(Object.assign(rec, {why: '長さが違う',
        mine: mine.res.end - mine.res.index, real: real[0].length}));
      continue;
    }
    let gbad = null;
    for (let g = 1; g < real.length; g++) {
      const c = mine.res.caps[g];
      const ms = c ? subj.slice(c[0], c[1]) : undefined;
      if (real[g] !== ms) { gbad = {why: 'グループ' + g + 'が違う', mine: ms, real: real[g]}; break; }
    }
    if (gbad) bad.push(Object.assign(rec, gbad));
  }
  return {bad, skip: skip.length};
}"""

# 「止まった位置」の主張を、ブラウザだけで検算する。
JS_STOP = r"""([cases]) => {
  const bad = [], stats = {checked: 0, claims: 0, skip: 0};
  for (const [src, flags, subj] of cases) {
    let parsed = null;
    try { parsed = parseRegex(src, flags); } catch (e) { stats.skip++; continue; }
    if (!engineHandles(parsed, flags) || nestedUnbounded(parsed.node)) { stats.skip++; continue; }
    let re;
    try { re = new RegExp(src, flags.replace(/g/g, '')); } catch (e) { stats.skip++; continue; }
    re.lastIndex = 0;
    if (re.exec(subj)) { stats.skip++; continue; }        // マッチする組は対象外
    const mine = runMatch(parsed, flags, subj);
    if (mine.aborted || mine.deep || mine.far.pos < 0) { stats.skip++; continue; }
    stats.checked++;
    const pos = mine.far.pos;
    if (pos >= subj.length) continue;                     // 文字が無いので落ちて当然
    const ch = subj.charAt(pos);
    for (const node of mine.far.nodes) {
      // 待っていたものを、ブラウザの RegExp に作り直して1文字に当てる
      let mini = null;
      if (node.t === 'esc' || node.t === 'class') mini = node.raw;
      else if (node.t === 'char') mini = node.raw;
      else if (node.t === 'any' && flags.indexOf('s') < 0) mini = '.';
      if (mini === null) continue;
      let r2;
      try { r2 = new RegExp('^(?:' + mini + ')$', flags.replace(/[gmys]/g, '')); }
      catch (e) { continue; }
      stats.claims++;
      if (r2.test(ch))
        bad.push({src, flags, subj, pos, ch, want: node.raw,
                  why: '待っていたはずのものが、その文字に当たってしまう'});
    }
  }
  return {bad, stats};
}"""

# 欠陥を1つ仕込んで、その直し方を名指しできるか
JS_FIX = r"""([cases]) => {
  const out = [];
  for (const [src, flags, subj, want] of cases) {
    let hit = false;
    try { hit = new RegExp(src, flags).test(subj); } catch (e) { hit = null; }
    if (hit !== false) { out.push({src, flags, subj, want, skip: true}); continue; }
    const fixes = buildFixes(src, flags, subj);
    const labels = fixes.map(f => (f.label + ' ' + f.why).replace(/<[^>]*>/g, ''));
    out.push({src, flags, subj, want, skip: false,
              found: labels.some(l => want.some(w => l.indexOf(w) >= 0)), labels});
  }
  return out;
}"""

# ------------------------------------------------------- 3 の壊し方（正解つき）
BASE_PAIRS = [
    ("^(\\d{4})-(\\d{2})-(\\d{2})$", "2026-08-23"),
    ("^[a-z]+@[a-z]+\\.[a-z]+$", "hiru@example.com"),
    ("^\\d{3}-\\d{4}$", "251-0001"),
    ("^[\\w.]+$", "hiru.lab"),
    ("^name: (\\w+)$", "name: hirulab"),
    ("^[a-z]+ [a-z]+$", "hiru lab"),
    ("^v(\\d+)\\.(\\d+)$", "v1.25"),
    ("^\\d+ yen$", "1200 yen"),
    ("^(a|b)+-(c|d)+$", "aab-ccd"),
    ("^[a-z]{2,8}$", "hirulab"),
]

FW = {chr(c): chr(c - 0x20 + 0xFF00) for c in range(0x21, 0x7F)}


def to_fullwidth(s):
    return "".join(FW.get(c, "\u3000" if c == " " else c) for c in s)


# 壊し方 → その壊し方に対して道具が出すべき文言。
# 見えない文字は必ず \u で書く（原稿に貼ると消えるため）。
DEFECTS = [
    ("末尾に空白", lambda s: s + " ", ["前後の空白", "trim the whitespace"]),
    ("先頭に空白", lambda s: " " + s, ["前後の空白", "trim the whitespace"]),
    ("全角化", to_fullwidth, ["NFKC"]),
    ("BOM を足す", lambda s: "\ufeff" + s, ["ゼロ幅文字", "zero-width"]),
    ("ゼロ幅スペースを挟む", lambda s: s[:1] + "\u200b" + s[1:], ["ゼロ幅文字", "zero-width"]),
    ("CRLF にする", lambda s: s + "\r", ["改行コード", "CRLF line ending"]),
    ("ノーブレークスペース", lambda s: s.replace(" ", "\u00a0"), ["ノーブレークスペース", "no-break space"]),
    ("似たダッシュ", lambda s: s.replace("-", "\u2011"), ["ダッシュ", "look-alike dashes"]),
    ("大文字にする", lambda s: s.upper(), ["i フラグを付ける", "add the i flag"]),
    ("異体字セレクタ", lambda s: s + "\ufe0f", ["異体字セレクタ", "variation selector"]),
]


def build_fix_cases():
    out = []
    for pat, subj in BASE_PAIRS:
        for name, fn, want in DEFECTS:
            broken = fn(subj)
            if broken == subj:
                continue
            out.append((pat, "", broken, want, name))
    return out


# ------------------------------------------------------------------ 実行
def chunked(pg, js, items, chunk, merge):
    acc = None
    for k in range(0, len(items), chunk):
        part = items[k:k + chunk]
        try:
            r = pg.evaluate(js, [part])
        except Exception as e:
            print(f"  !! この束で止まった: {part[:2]} … ({e})")
            continue
        acc = r if acc is None else merge(acc, r)
    return acc


def merge_bad(a, b):
    return {"bad": a["bad"] + b["bad"], "skip": a["skip"] + b["skip"]}


def merge_stop(a, b):
    st = {k: a["stats"][k] + b["stats"][k] for k in a["stats"]}
    return {"bad": a["bad"] + b["bad"], "stats": st}


def check_parser_identity(page_path, railroad_path):
    """解析器が鉄道図ツールと1バイトも違わないか。"""
    if not railroad_path.exists():
        return None, "鉄道図のページが見つからない: %s" % railroad_path
    rail = railroad_path.read_text(encoding="utf-8")
    mine = page_path.read_text(encoding="utf-8")
    a = _find_any(rail, RAIL_HEAD, "解析器の先頭")
    b = _find_any(rail, RAIL_TAIL, "解析器の末尾")
    ref = rail[a:b].rstrip()
    try:
        c = mine.index("/*==PARSER-START==*/")
        d = mine.index("/*==PARSER-END==*/")
    except ValueError:
        return False, "PARSER-START / PARSER-END の印が無い"
    got = mine[c + len("/*==PARSER-START==*/"):d].strip()
    if got == ref:
        return True, "%d バイト一致" % len(ref.encode("utf-8"))
    return False, "食い違う（参照 %d バイト / こちら %d バイト）" % (
        len(ref.encode("utf-8")), len(got.encode("utf-8")))


SABOTAGE = [
    (r"\d を全角数字にも当てる",
     "case 'd': return isDigitCh(ch);",
     "case 'd': return isDigitCh(ch) || (ch >= '\\uff10' && ch <= '\\uff19');"),
    ("くり返しの貪欲と最小一致を入れ替える",
     "if (node.lazy) return stop() ? true : more();",
     "if (!node.lazy) return stop() ? true : more();"),
    ("全角を直す手当てを消す",
     "function (s) { return s.normalize ? s.normalize('NFKC') : s; }],",
     "function (s) { return s; }],"),
    ("文字クラスの照合を常に外す",
     "case 'class': return one(node, pos, k, function (ch) { return inClass(node, ch); }, dir);",
     "case 'class': return one(node, pos, k, function (ch) { return false; }, dir);"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400, help="ランダムに作る式の本数")
    ap.add_argument("--page", default=None)
    ap.add_argument("--railroad", default=None)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--sabotage", action="store_true", help="わざと壊して検査が働くか見る")
    args = ap.parse_args()

    page = pathlib.Path(args.page).resolve() if args.page else DEFAULT_PAGE.resolve()
    # ★2026-09-03 夜: 既定の相手を**同じ言語の**鉄道図にする。
    #   英語ページを見ているのに既定が日本語版を指していたので、`--railroad` を
    #   毎回手で渡さないと必ず食い違った(渡し忘れると「解析器が違う」と出る)。
    railroad = (pathlib.Path(args.railroad).resolve() if args.railroad
                else (page.parent / "railroad.html" if page.parent.name == "en"
                      else page.parent.parent / "railroad" / "index.html"))
    if not page.exists():
        sys.exit("ページが見つかりません: %s（--page で指定してください）" % page)

    rnd = random.Random(args.seed)
    cases = []
    for _ in range(args.n):
        src = gen_regex(rnd, exotic=rnd.random() < 0.35)
        fl = rnd.choice(FLAG_SETS)
        for _ in range(3):
            cases.append([src, fl, gen_subject(rnd)])
    for src, subs in EDGE_PAIRS:
        for fl in ("", "i", "m"):
            for s in subs:
                cases.append([src, fl, s])
    fix_cases = build_fix_cases()

    html_text = page.read_text(encoding="utf-8")
    variants = [("そのまま", html_text)]
    if args.sabotage:
        variants = []
        for name, old, new in SABOTAGE:
            if old not in html_text:
                print("  !! 仕込み先が見つからない: %s" % name)
                continue
            variants.append(("わざと壊す: " + name, html_text.replace(old, new, 1)))

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for label, text in variants:
            pg = br.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.set_content(text)
            pg.wait_for_timeout(200)

            print("\n=== %s ===" % label)
            if errs:
                print("  JSエラー:", errs[:3])

            # 基準の鍵に変種の名前を入れない。わざと壊した回を正常時の基準と比べるため
            sw = SkipWatch("test_regex_why")

            cmp_ = chunked(pg, JS_COMPARE, cases, 60, merge_bad)
            n_cmp = len(cases) - cmp_["skip"]
            print("[1] 自前の照合器 vs ブラウザ: %d 件中 %d 件が一致（対象外 %d）"
                  % (n_cmp, n_cmp - len(cmp_["bad"]), cmp_["skip"]))
            for b in cmp_["bad"][:8]:
                print("    ✗ /%s/%s × %s : %s (自前 %r / 本物 %r)"
                      % (b["src"], b["flags"], json.dumps(b["subj"], ensure_ascii=False),
                         b["why"], b.get("mine"), b.get("real")))

            stop = chunked(pg, JS_STOP, cases, 60, merge_stop)
            st = stop["stats"]
            print("[2] 止まった位置の主張: %d 組を検算、%d 個の「待っていたもの」を当て直して "
                  "食い違い %d 件" % (st["checked"], st["claims"], len(stop["bad"])))
            for b in stop["bad"][:8]:
                print("    ✗ /%s/%s × %s : %d 文字目 %r に対して %s"
                      % (b["src"], b["flags"], json.dumps(b["subj"], ensure_ascii=False),
                         b["pos"] + 1, b["ch"], b["want"]))

            fix_in = [[c[0], c[1], c[2], c[3]] for c in fix_cases]
            res = pg.evaluate(JS_FIX, [fix_in])
            done = [r for r in res if not r["skip"]]
            miss = [r for r in done if not r["found"]]
            skipped = len(res) - len(done)
            print("[3] 欠陥を仕込んで直し方を名指し: %d 件中 %d 件で当てた"
                  "（%d 件は壊してもマッチしたので対象外）"
                  % (len(done), len(done) - len(miss), skipped))
            for m in miss[:8]:
                print("    ✗ /%s/ × %s : 「%s」を挙げられなかった → %s"
                      % (m["src"], json.dumps(m["subj"], ensure_ascii=False),
                         " / ".join(m["want"]), m["labels"][:3]))

            sw.check("[1] 照合器の突き合わせ", cmp_["skip"], len(cases))
            sw.check("[2] 止まった位置の検算", st["skip"], len(cases))
            sw.check("[3] 直し方の名指し", skipped, len(res))
            sw.report()
            pg.close()
        br.close()

    ok, why = check_parser_identity(page, railroad)
    print("\n[4] 解析器が鉄道図と同一か: %s（%s）"
          % ("✓ 一致" if ok else ("✗ 違う" if ok is False else "— 確かめられず"), why))


if __name__ == "__main__":
    main()
