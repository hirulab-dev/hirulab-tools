#!/usr/bin/env python3
"""「正規表現の置換プレビュー」の検証（2026-08-23）。

この道具が主張していることは3つある。それぞれに別の出どころの正解を当てる。

1. **置換後の文字列は、ブラウザの `String.prototype.replace` と同じか**
   自前でテンプレートを展開して組み立てているので、本物とずれたら道具の意味がない。
   ランダムな式・テンプレート・対象文字列で総当たりして突き合わせる。

2. **「この文字はこのトークンから来た」という主張が本当か**
   道具は置換後の1文字1文字に「どのトークンが生んだか」を付けている。
   これを **ブラウザの `replace` に関数を渡して**、本物のエンジンが渡してくる
   マッチ・グループ・オフセットから組み直して突き合わせる。
   1 とは別の経路（自前の照合を1行も通らない）で主張を検算することになる。

3. **正解の分かっている落とし穴を、道具が名指しできるか**
   「g を付け忘れた」「\\1 と書いた」「無い番号を書いた」「名前を綴り間違えた」など、
   **こちらが仕込んだ**欠陥に対して、道具が対応する指摘を出すかを見る。
   指摘は画面の文言ではなく `data-code` で照合するので、英語版にもそのまま当たる。

4. **解析器が鉄道図・なぜマッチしないか診断と1バイトも違わないか**
   3ページで同じ解析器を使っていると画面に書いてある以上、機械で確かめる。

わざと壊して検査が空振りしていないかを見る `--sabotage` つき。

使い方:
  python lab/scripts/test_replace.py [--n 500] [--page <path or url>]
  python lab/scripts/test_replace.py --sabotage
"""
import argparse, json, pathlib, random, sys
import os as _os
_os.sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from skipwatch import SkipWatch

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

DEFAULT_PAGE = pathlib.Path("docs/replace/index.html")

# ---------------------------------------------------------------- 式の生成
ATOMS = [
    "a", "b", "z", "0", "9", "_", "-", " ", "@", "%", ",",
    r"\d", r"\w", r"\s", r"\D", r"\W", r"\S", ".",
    "[a-z]", "[A-Z0-9]", "[^abc]", r"[\d.]", "[a-fA-F0-9]", "[-a-z]",
    r"\.", r"\+", r"\t",
]
Q_ALL = ["", "", "", "*", "+", "?", "{2}", "{1,3}", "{2,}", "*?", "+?", "??"]
Q_BOUNDED = ["", "", "", "?", "{2}", "{1,3}", "??"]
# 全角・見えない文字・サロゲートも混ぜる。18本目のときに
# 「検証の文字集合が薄いと、仕込んだバグが捕まらない」を踏んだので最初から入れる。
ALPHABET = ("abz09_-. @%,AB\t\n"
            "１Ａａ　 ﻿‑​\U0001f600")



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


def gen_regex(rnd, depth=0):
    n = rnd.randint(1, 3 if depth else 4)
    parts = []
    for _ in range(n):
        r = rnd.random()
        if r < 0.08 and depth < 2:
            parts.append(rnd.choice(["^", "$", r"\b", r"\B"]))
            continue
        if r < 0.55 or depth >= 2:
            body, grouped = rnd.choice(ATOMS), False
        elif r < 0.80:
            body = rnd.choice(["(", "(?:", "(", "(?<g%d>" % rnd.randint(0, 3)]) \
                   + gen_regex(rnd, depth + 1) + ")"
            grouped = True
        else:
            body = "(" + gen_regex(rnd, depth + 1) + "|" + gen_regex(rnd, depth + 1) + ")"
            grouped = True
        q = rnd.choice(Q_BOUNDED if grouped else Q_ALL)
        if q in ("*", "+", "*?", "+?", "{2,}") and body.endswith(("?", "*")):
            q = ""
        parts.append(body + q)
    return "".join(parts)


def gen_subject(rnd):
    return "".join(rnd.choice(ALPHABET) for _ in range(rnd.randint(0, 14)))


D, BQ, AP = "$", "`", "'"

TEMPLATE_PIECES = [
    "-", "[", "]", "<", ">", "x", "あ", " ", "",
    D + "&", D + "1", D + "2", D + "3", D + "9", D + "12", D + "0",
    D + D, D, D + BQ, D + AP,
    D + "<g0>", D + "<g1>", D + "<nope>", D + "<", D + "{1}",
    "\\1", "\\g<1>", "$ ", "$z",
]


def gen_template(rnd):
    return "".join(rnd.choice(TEMPLATE_PIECES) for _ in range(rnd.randint(0, 5)))


FLAG_SETS = ["g", "g", "g", "", "gi", "gm", "gu", "gs", "i", "gy", "y", "u", "m"]

# ランダムでは出にくい形は手で並べる（仕様の角）
EDGE_CASES = [
    (r"(\d{4})-(\d{2})-(\d{2})", "g", "$3/$2/$1", "2026-08-23 と 2026-12-31"),
    (r"(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)(l)", "", "$12|$11|$1", "abcdefghijkl"),
    (r"(a)", "", "$12", "ab"),                      # 2桁が範囲外 → 1桁+文字
    (r"(a)", "", "$2", "ab"),                       # 範囲外 → そのまま文字
    (r"(a)", "", "$0", "ab"),                       # 0 番は無い
    (r"a", "", "$1", "ab"),                         # グループ0個
    (r"(?<y>\d{4})-(?<m>\d{2})", "g", "$<m>/$<y>", "2026-08 2027-01"),
    (r"(?<y>\d{4})", "g", "$<year>", "2026 2027"),  # 名前の綴り違い → 空文字
    (r"(\d{4})", "g", "$<y>", "2026"),              # 名前つきが無い式 → そのまま文字
    (r"(?<y>\d+)", "g", "$<y", "2026"),             # 閉じる > が無い
    (r"(?<y>\d+)", "g", "$<>", "2026"),             # 空の名前
    ("b", "g", "[$&]", "abcb"),
    ("b", "g", "<" + D + BQ + ">", "abcb"),
    ("b", "g", "<" + D + AP + ">", "abcb"),
    (r"(\d+)", "g", D + D + "$1", "a 12 b 340"),
    ("x*", "g", "-", "abc"),
    ("", "g", ".", "abc"),
    ("a*", "g", "<$&>", "baac"),
    (",", "", "、", "a,b,c"),
    ("apple", "gi", "ORANGE", "Apple APPLE apple"),
    (".", "g", "<$&>", "a\U0001f600b"),
    (".", "gu", "<$&>", "a\U0001f600b"),
    (r"(foo)?bar", "g", "[$1]", "bar foobar"),      # 通らなかったグループ
    (r"(a)|(b)", "g", "[$1|$2]", "ab"),
    ("a", "gy", "X", "aab a"),
    ("a", "y", "X", "aab a"),
    ("^", "gm", "> ", "one\ntwo"),
    ("$", "gm", " <", "one\ntwo"),
    (r"(\w)", "g", "\\1", "ab"),
    (r"(\w)", "g", "${1}", "ab"),
    (r"(\w)", "g", "$", "ab"),
    (r"(\w)", "g", "a$", "ab"),
    (r"(\w)", "g", "$ ", "ab"),
    (r"(?<a>x)(?<b>y)", "g", "$<b>$<a>$1$2", "xy"),
    (r"[぀-ゟ]+", "g", "(かな)", "あいう漢字えお"),
    (r"(\d)", "g", "$1$1$1", "12"),
    (r"\s+", "g", " ", "  a   b\t\tc "),
    (r"(.)(.)", "g", "$2$1", "abcdef"),
    (r"()", "g", "[$1]", "ab"),                     # 空のグループ
    (r"(?:no)(cap)", "g", "[$1]", "nocap"),
]

# ------------------------------------------------------- ブラウザ側の検査

# [1] 自前の展開 vs 本物の replace
JS_OUT = r"""([cases]) => {
  const bad = [], skip = [];
  for (const [pat, flags, tmpl, subj] of cases) {
    let parsed;
    try { parsed = parseRegex(pat, flags); } catch (e) { skip.push(1); continue; }
    let re;
    try { re = new RegExp(pat, flags); } catch (e) { skip.push(1); continue; }
    const tokens = parseTemplate(tmpl, parsed.capCount, parsed.names);
    let mine;
    try { mine = runReplace(pat, flags, tokens, subj); } catch (e) { skip.push(1); continue; }
    /* 打ち切りを「対象外」に落とすと、長さ0のマッチで前に進まなくなるバグが
       まるごと検査の外に出る（--sabotage で実際に空振りした）。
       ここで使う対象は高々14文字なので、5000件に達すること自体が異常。失敗として数える。 */
    let real;
    try { re.lastIndex = 0; real = subj.replace(re, tmpl); } catch (e) { skip.push(1); continue; }
    if (mine.truncated) {
      bad.push({pat, flags, tmpl, subj, mine: '（' + mine.matches.length + ' 件で打ち切り）', real});
      continue;
    }
    if (mine.out !== real) bad.push({pat, flags, tmpl, subj, mine: mine.out, real});
  }
  return {bad, skip: skip.length};
}"""

# [2] 「この文字はこのトークンから来た」を、本物のエンジンが渡してくる値で検算する。
#     replace に関数を渡すと (match, p1..pn, offset, string, groups) が来る。
#     自前の照合・自前の展開を1行も通らない経路なので、独立した確かめになる。
JS_ORIGIN = r"""([cases]) => {
  const bad = [], stats = {checked: 0, claims: 0, skip: 0};
  for (const [pat, flags, tmpl, subj] of cases) {
    let parsed, re;
    try { parsed = parseRegex(pat, flags); } catch (e) { stats.skip++; continue; }
    try { re = new RegExp(pat, flags); } catch (e) { stats.skip++; continue; }
    const tokens = parseTemplate(tmpl, parsed.capCount, parsed.names);
    let mine;
    try { mine = runReplace(pat, flags, tokens, subj); } catch (e) { stats.skip++; continue; }
    if (mine.truncated) {
      bad.push({pat, flags, tmpl, subj, why: '打ち切りに掛かった（前に進んでいない疑い）',
                mine: String(mine.matches.length), real: ''});
      continue;
    }

    /* 本物のエンジンから、マッチごとの引数をそのまま集める */
    const seen = [];
    try {
      re.lastIndex = 0;
      subj.replace(re, function () {
        const a = Array.prototype.slice.call(arguments);
        let groups = undefined;
        if (typeof a[a.length - 1] === 'object' && a[a.length - 1] !== null) groups = a.pop();
        const string = a.pop(), offset = a.pop(), m0 = a.shift();
        seen.push({m0, caps: a, offset, string, groups});
        return '';
      });
    } catch (e) { stats.skip++; continue; }

    if (seen.length !== mine.matches.length) {
      bad.push({pat, flags, tmpl, subj, why: 'マッチの数が違う',
                mine: mine.matches.length, real: seen.length});
      continue;
    }
    stats.checked++;

    /* 道具が「このトークンが生んだ」と言っている並びを、本物の値から組み直す */
    let ng = null;
    let mi = -1, ti = 0;
    for (const sg of mine.segs) {
      if (sg.keep) continue;
      if (sg.mi !== mi) { mi = sg.mi; ti = 0; }
      const tk = tokens[sg.k];
      const s = seen[mi];
      let want;
      if (tk.t === 'lit') want = tk.s;
      else if (tk.t === 'dollar') want = '$';
      else if (tk.t === 'match') want = s.m0;
      else if (tk.t === 'before') want = subj.slice(0, s.offset);
      else if (tk.t === 'after') want = subj.slice(s.offset + s.m0.length);
      else if (tk.t === 'group') want = s.caps[tk.n - 1] === undefined ? '' : s.caps[tk.n - 1];
      else want = (s.groups && s.groups[tk.name] !== undefined) ? s.groups[tk.name] : '';
      stats.claims++;
      if (want !== sg.s) {
        ng = {pat, flags, tmpl, subj, why: 'トークン ' + tk.raw + ' の中身が違う',
              mine: sg.s, real: want};
        break;
      }
    }
    if (ng) { bad.push(ng); continue; }

    /* 元のまま残したと言っている部分が、本当にどのマッチにも当たっていないか */
    let pos = 0, keepBad = null;
    for (let j = 0; j < seen.length; j++) {
      const s = seen[j];
      if (s.offset < pos) { keepBad = 'マッチが重なっている'; break; }
      pos = s.offset + s.m0.length;
    }
    if (keepBad) bad.push({pat, flags, tmpl, subj, why: keepBad, mine: '', real: ''});
  }
  return {bad, stats};
}"""

# [3] 仕込んだ落とし穴を名指しできるか（画面の文言ではなく data-code で見る）
JS_TRAPS = r"""([cases]) => {
  const out = [];
  for (const [pat, flags, tmpl, subj, want] of cases) {
    let parsed;
    try { parsed = parseRegex(pat, flags); } catch (e) { out.push({want, codes: [], skip: 1}); continue; }
    let tokens = parseTemplate(tmpl, parsed.capCount, parsed.names);
    let res;
    try { res = runReplace(pat, flags, tokens, subj); }
    catch (e) { out.push({want, codes: [], skip: 1}); continue; }
    const traps = findTraps(pat, flags, tmpl, subj, parsed, tokens, res);
    const codes = traps.map(t => t[1]);
    out.push({pat, flags, tmpl, subj, want, codes, found: codes.indexOf(want) >= 0, skip: 0});
  }
  return out;
}"""


def build_trap_cases():
    """正解をこちらが握る形で、落とし穴を1つずつ仕込む。"""
    return [
        # g の付け忘れ（当たる場所が2つ以上あるときだけ指摘されるべき）
        (",", "", "、", "a,b,c", "no-g"),
        (r"\d", "", "N", "1 2 3", "no-g"),
        # 置換文字列にバックスラッシュ後方参照
        (r"(\w+)@(\w+)", "g", "\\2 の \\1", "a@b", "backslash-ref"),
        # ${1} 記法
        (r"(\w)", "g", "${1}", "ab", "brace-ref"),
        # Python の \g<1>
        (r"(\w)", "g", "\\g<1>", "ab", "python-ref"),
        # 無い番号 → そのまま文字
        (r"(\d+)円", "g", "$2円", "300円", "literal-token"),
        (r"(\d+)", "g", "$0", "300", "literal-token"),
        (r"\d+", "g", "$1", "300", "literal-token"),
        # 名前つきグループはあるが綴りが違う
        (r"(?<y>\d{4})", "g", "$<year>", "2026", "unknown-name"),
        (r"(?<a>x)(?<b>y)", "g", "$<c>", "xy", "unknown-name"),
        # 名前つきが1つも無い式で $<...> → そのまま文字
        (r"(\d{4})", "g", "$<y>", "2026", "literal-token"),
        # 長さ0のマッチ
        ("x*", "g", "-", "abc", "zero-length"),
        (r"\b", "g", "|", "ab cd", "zero-length"),
        ("^", "gm", "> ", "a\nb", "zero-length"),
        # $` と $'
        ("b", "g", "<" + D + BQ + ">", "abc", "context-token"),
        ("b", "g", "<" + D + AP + ">", "abc", "context-token"),
        # y フラグ
        ("a", "gy", "X", "aab a", "sticky"),
        # i フラグと置換文字列の大小
        ("apple", "gi", "ORANGE", "Apple APPLE", "ignorecase"),
        # u が無くてサロゲート
        (".", "g", "<$&>", "a\U0001f600b", "surrogate"),
        (r"\w", "g", "-", "a\U0001f600b", "surrogate"),
        # 1件も当たらない
        (r"\d+", "g", "N", "abc", "no-match"),
        (r"^abc$", "g", "X", "x\nabc\ny", "no-match"),
        # 置換しても変わらない
        (r"(\w)", "g", "$1", "abc", "no-change"),
        (r"(a)(b)", "g", "$1$2", "ab", "no-change"),
        # 末尾の $
        (r"(\w)", "g", "a$", "ab", "literal-token"),
        (r"(\w)", "g", "$ ", "ab", "literal-token"),
    ]


def check_parser_identity(page_path, others):
    """解析器が他のページと1バイトも違わないか。"""
    mine = page_path.read_text(encoding="utf-8")
    try:
        c = mine.index("/*==PARSER-START==*/") + len("/*==PARSER-START==*/")
        d = mine.index("/*==PARSER-END==*/")
    except ValueError:
        return None, "PARSER-START / PARSER-END の印が無い", []
    got = mine[c:d].strip()
    rows = []
    ok = True
    for label, path in others:
        if not path.exists():
            rows.append((label, None, "ページが無い")); ok = False; continue
        text = path.read_text(encoding="utf-8")
        if "/*==PARSER-START==*/" in text:
            a = text.index("/*==PARSER-START==*/") + len("/*==PARSER-START==*/")
            b = text.index("/*==PARSER-END==*/")
            ref = text[a:b].strip()
        else:
            # 鉄道図は印を持たない（コメントの見出しで挟む）
            a = _find_any(text, RAIL_HEAD, "解析器の先頭")
            b = _find_any(text, RAIL_TAIL, "解析器の末尾")
            ref = text[a:b].strip()
        same = ref == got
        ok = ok and same
        rows.append((label, same, "%d バイト" % len(ref.encode("utf-8"))
                     if same else "食い違う（%d / %d バイト）"
                     % (len(ref.encode("utf-8")), len(got.encode("utf-8")))))
    return ok, "%d バイト" % len(got.encode("utf-8")), rows


SABOTAGE = [
    ("2桁のグループ番号を先に見ない（$12 が必ず $1+2 になる）",
     "      if (two >= 1 && two <= capCount) {",
     "      if (false) {"),
    ("範囲外の $n をエラーにせず空文字にする",
     "      /* ここが落とし穴。番号が範囲外だと「そのまま文字」になる。 */",
     "      flush(); out.push({ t: 'group', n: one, raw: D + nx }); i += 2; continue;\n"
     "      /* ここが落とし穴。番号が範囲外だと「そのまま文字」になる。 */"),
    ("長さ0のマッチのあとに進まない（無限ループ避けに件数上限で止まる）",
     "      if (m[0] === '') re.lastIndex = advance(input, re.lastIndex, uni);",
     "      if (m[0] === '') re.lastIndex = re.lastIndex;"),
    ("$` と $' を「置換しかけの文字列」から取る",
     "    else if (tk.t === 'before') s = input.slice(0, m.index);",
     "    else if (tk.t === 'before') s = input.slice(0, m.index).toUpperCase();"),
    ("名前つきグループの綴り違いを黙って通す",
     "      out.push({ t: 'named', name: nm, raw: D + '<' + nm + '>', known: names.indexOf(nm) >= 0 });",
     "      out.push({ t: 'named', name: nm, raw: D + '<' + nm + '>', known: true });"),
]


def chunked(pg, js, cases, size, merge):
    acc = None
    for i in range(0, len(cases), size):
        r = pg.evaluate(js, [cases[i:i + size]])
        acc = r if acc is None else merge(acc, r)
    return acc


def merge_out(a, b):
    a["bad"] += b["bad"]; a["skip"] += b["skip"]; return a


def merge_origin(a, b):
    a["bad"] += b["bad"]
    for k in a["stats"]:
        a["stats"][k] += b["stats"][k]
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="ランダムに作る式の本数")
    ap.add_argument("--page", default=None)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()

    page = pathlib.Path(args.page).resolve() if args.page else DEFAULT_PAGE.resolve()
    if not page.exists():
        sys.exit("ページが見つかりません: %s（--page で指定してください）" % page)
    root = page.parent.parent
    others = [("鉄道図", root / "railroad" / "index.html"),
              ("なぜマッチしないか診断", root / "regex-why" / "index.html")]
    if page.parent.name == "en":
        others = [("鉄道図（英語版）", page.parent / "railroad.html"),
                  ("なぜマッチしないか診断（英語版）", page.parent / "regex-why.html")]

    rnd = random.Random(args.seed)
    cases = []
    for _ in range(args.n):
        pat = gen_regex(rnd)
        fl = rnd.choice(FLAG_SETS)
        for _ in range(3):
            cases.append([pat, fl, gen_template(rnd), gen_subject(rnd)])
    for c in EDGE_CASES:
        for fl in {c[1], c[1].replace("g", ""), c[1] + "i" if "i" not in c[1] else c[1]}:
            cases.append([c[0], fl, c[2], c[3]])
    trap_cases = build_trap_cases()

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
            # 基準の鍵は変種の名前を含めない。わざと壊した回が正常時の基準と比べられるようにする
            # （壊した分だけ「対象外」に流れて検査から消える、という穴を見つけるため）
            sw = SkipWatch("test_replace")

            r1 = chunked(pg, JS_OUT, cases, 80, merge_out)
            n1 = len(cases) - r1["skip"]
            print("[1] 置換後の文字列 vs ブラウザの replace: %d 件中 %d 件が一致（対象外 %d）"
                  % (n1, n1 - len(r1["bad"]), r1["skip"]))
            for b in r1["bad"][:6]:
                print("    ✗ /%s/%s → %s × %s : 自前 %s / 本物 %s"
                      % (b["pat"], b["flags"], b["tmpl"],
                         json.dumps(b["subj"], ensure_ascii=False),
                         json.dumps(b["mine"], ensure_ascii=False),
                         json.dumps(b["real"], ensure_ascii=False)))

            r2 = chunked(pg, JS_ORIGIN, cases, 80, merge_origin)
            st = r2["stats"]
            print("[2] 出どころの主張を本物の値で検算: %d 組・%d 個のトークンを当て直して "
                  "食い違い %d 件（対象外 %d）"
                  % (st["checked"], st["claims"], len(r2["bad"]), st["skip"]))
            for b in r2["bad"][:6]:
                print("    ✗ /%s/%s → %s × %s : %s（自前 %s / 本物 %s）"
                      % (b["pat"], b["flags"], b["tmpl"],
                         json.dumps(b["subj"], ensure_ascii=False), b["why"],
                         json.dumps(b["mine"], ensure_ascii=False),
                         json.dumps(b["real"], ensure_ascii=False)))

            r3 = pg.evaluate(JS_TRAPS, [[list(c) for c in trap_cases]])
            done = [x for x in r3 if not x["skip"]]
            miss = [x for x in done if not x["found"]]
            print("[3] 仕込んだ落とし穴の名指し: %d 件中 %d 件で当てた"
                  % (len(done), len(done) - len(miss)))
            for m in miss[:8]:
                print("    ✗ /%s/%s → %s × %s : 「%s」が出なかった → %s"
                      % (m["pat"], m["flags"], m["tmpl"],
                         json.dumps(m["subj"], ensure_ascii=False), m["want"], m["codes"]))

            sw.check("[1] 置換結果の照合", r1["skip"], len(cases))
            sw.check("[2] 出どころの検算", st["skip"], len(cases))
            sw.check("[3] 落とし穴の名指し", len(r3) - len(done), len(r3))
            sw.report()
            pg.close()
        br.close()

    ok, size, rows = check_parser_identity(page, others)
    print("\n[4] 解析器が他のページと同一か（こちら %s）" % size)
    for label, same, why in rows:
        print("    %s %s: %s" % ("✓" if same else "✗", label, why))


if __name__ == "__main__":
    main()
