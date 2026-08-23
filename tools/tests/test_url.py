#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「URLの分解・組み立て」の検証（2026-08-23）。

この道具が主張していることに、それぞれ**別の出どころの正解**を当てる。

1. **分解した結果がブラウザの `URL` と一致するか**
   protocol / username / password / host / hostname / port / pathname / search / hash / href
   の10項目を、ランダムに組み立てたURLと手で並べた角のケースで突き合わせる。
   相対URL（基準URLつき）も同じだけ回す。

2. **punycode（`xn--`）が Python と一致するか**
   ブラウザは punycode を単独で見せてくれないので、**RFC 3492 の別実装**（CPython の
   `str.encode("punycode")`）に当てる。ブラウザと自分が同じ勘違いをしたときに気づくため。

3. **クエリの読み分けが Python の `parse_qsl` と一致するか**
   この道具は「%だけ戻した値」と「フォーム式（+も空白にする）値」の2通りを出す。
   後者は `urllib.parse.parse_qsl` がやっていることと同じはずなので、そこに当てる。

4. **組み立て直したものが、元と同じURLに戻るか**
   分解した部品をそのまま組み立て器に入れて、ブラウザの `URL` で正規化した結果が一致するか。

5. **正解の分かっている落とし穴を名指しできるか**
   こちらが仕込んだ欠陥に対応する指摘が出るかを `data-code` で照合する
   （画面の文言で見ると英語版に当たらないので、最初から機械可読な鍵にしてある）。

わざと壊して検査が空振りしていないかを見る `--sabotage` つき。
対象外にした件数は `skipwatch` で毎回目に見えるところに出す。

使い方:
  python lab/scripts/test_url.py [--n 600] [--page docs/url/index.html]
  python lab/scripts/test_url.py --sabotage
"""
import argparse, json, pathlib, random, sys, urllib.parse
import os as _os
_os.sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from skipwatch import SkipWatch

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

DEFAULT_PAGE = pathlib.Path("docs/url/index.html")

# ---------------------------------------------------------------- 生成
SCHEMES = ["http", "https", "https", "https", "ws", "wss", "ftp", "foo", "myapp"]

# ホスト名に使う文字。**自前の UTS #46 が扱えると分かっている範囲だけ**にする。
# 記号（♥ など）は UTS #46 が禁止していてブラウザが拒むが、こちらは通してしまうので入れない。
# それは実装の穴なので、角のケースのほうに1件だけ置いて「拒む側が正しい」と分かるようにしてある。
HOST_ASCII = "abcdefghijklmnopqrstuvwxyz0123456789-"
HOST_WIDE = "ａｂｃＡＢ０１"          # 全角英数
HOST_JA = "あい日本語カナ"            # かな・漢字
HOST_CY = "абвеор"                  # キリル
HOST_DOT = ["。", "．", "｡"]                         # 3種類の全角ピリオド

PATH_CHARS = "abcXYZ019-._~!$&()*+,;=:@%/ あ日Ａ\\\"<>{}|^`[]?#"
QUERY_CHARS = "abcXYZ019-._~!$&()*+,;=:@%/ あＡ\"<>#'"
INVISIBLE = ["​", "‌", "﻿", " ", "‮", "\t", "\n", "\r"]


def gen_host(rnd):
    r = rnd.random()
    if r < 0.10:                                   # IPv4 のいろいろな書き方
        return rnd.choice([
            "192.168.0.1", "127.0.0.1", "0x7f.1", "2130706433", "0300.0250.0.1",
            "1.2.3.4", "0xC0.0xA8.0.1", "10.1", "255.255.255.255",
        ])
    if r < 0.16:
        return rnd.choice([
            "[2001:db8::1]", "[::1]", "[::]", "[2001:db8:0:0:0:0:2:1]",
            "[::ffff:192.168.0.1]", "[fe80::1%2]" if False else "[fe80::1]",
        ])
    labels = []
    for _ in range(rnd.randint(1, 3)):
        pool = HOST_ASCII
        if rnd.random() < 0.30:
            pool = HOST_ASCII + rnd.choice([HOST_JA, HOST_CY, HOST_WIDE])
        lab = "".join(rnd.choice(pool) for _ in range(rnd.randint(1, 6)))
        lab = lab.strip("-") or "a"
        labels.append(lab)
    labels.append(rnd.choice(["com", "jp", "test", "example", "co"]))
    sep = "."
    if rnd.random() < 0.08:
        sep = rnd.choice(HOST_DOT)
    host = sep.join(labels)
    if rnd.random() < 0.05:
        host += "."
    return host


def gen_path(rnd):
    n = rnd.randint(0, 4)
    segs = []
    for _ in range(n):
        r = rnd.random()
        if r < 0.12:
            segs.append(rnd.choice(["..", ".", "%2e", "%2E%2e"]))
        else:
            segs.append("".join(rnd.choice(PATH_CHARS) for _ in range(rnd.randint(0, 6))))
    return "/" + "/".join(segs) if segs else rnd.choice(["", "/"])


def gen_query(rnd):
    if rnd.random() < 0.25:
        return ""
    n = rnd.randint(1, 3)
    out = []
    for _ in range(n):
        k = "".join(rnd.choice(QUERY_CHARS) for _ in range(rnd.randint(1, 5)))
        v = "".join(rnd.choice(QUERY_CHARS) for _ in range(rnd.randint(0, 6)))
        out.append(k + ("" if rnd.random() < 0.1 else "=" + v))
    return "?" + "&".join(out)


def gen_url(rnd):
    scheme = rnd.choice(SCHEMES)
    s = scheme + ":"
    slashes = "//"
    if rnd.random() < 0.06:
        slashes = rnd.choice(["/", "///", "/\\", "\\\\", "//"])
    s += slashes
    if rnd.random() < 0.18:
        u = "".join(rnd.choice("abcXYZ019-._%@:") for _ in range(rnd.randint(1, 6)))
        s += u + "@"
    s += gen_host(rnd)
    if rnd.random() < 0.25:
        s += ":" + rnd.choice(["80", "443", "8080", "0", "21", "65535", ""])
    s += gen_path(rnd)
    s += gen_query(rnd)
    if rnd.random() < 0.25:
        s += "#" + "".join(rnd.choice(PATH_CHARS) for _ in range(rnd.randint(0, 6)))
    if rnd.random() < 0.10:
        pos = rnd.randint(0, len(s))
        s = s[:pos] + rnd.choice(INVISIBLE) + s[pos:]
    return s


def gen_relative(rnd):
    r = rnd.random()
    if r < 0.15:
        return "//" + gen_host(rnd) + gen_path(rnd)
    if r < 0.30:
        return gen_path(rnd) + gen_query(rnd)
    if r < 0.45:
        return "?" + "".join(rnd.choice(QUERY_CHARS) for _ in range(rnd.randint(1, 6)))
    if r < 0.55:
        return "#" + "".join(rnd.choice(PATH_CHARS) for _ in range(rnd.randint(0, 6)))
    parts = []
    for _ in range(rnd.randint(1, 3)):
        parts.append(rnd.choice(["..", ".", "a", "b%20c", "x.y", "あ"]))
    return "/".join(parts) + (gen_query(rnd) if rnd.random() < 0.3 else "")


# ★ 既知の食い違い（ブラウザ側が仕様とも自分自身とも合っていないところ）。
#    黙って外さず、当てはまった件数を毎回出す。
#    非特別スキームの基準URLに相対URLを当てるとき、Chromium は \ の扱いが一貫しない:
#      "/x\y" + foo://opaque/path → host=opaque, path=/x/y （\ を / と読む）
#      "/\x"  + foo://opaque/path → host が消えて path=/\x  （\ を / と読まない）
#    仕様は後者でも host を引き継ぐ。こちらは仕様どおりにしてある。
def is_known_divergence(inp, base):
    return bool(base) and "\\" in inp and not base.startswith(("http", "ws", "ftp", "file"))


BASES = [
    "https://base.test/dir/page.html?old=1#frag",
    "https://base.test/",
    "http://base.test:8080/a/b/c",
    "foo://opaque/path?q",
    "ftp://base.test/x/y/",
]

# ランダムでは出にくい角。仕様の読みどころを手で並べる。
EDGE_CASES = [
    ("https://example.com:443/a/./b/../c?x=1#f", ""),
    ("https://www.google.com@evil.test/login", ""),
    ("https://a@b@example.com/", ""),
    ("http://0x7f.1/admin", ""),
    ("http://2130706433/", ""),
    ("http://0300.0250.0.1/", ""),
    ("http://999.1/", ""),
    ("http://1.2.3.4.5/", ""),
    ("http://0x/", ""),
    ("https://example。com/", ""),
    ("https://ｅｘａｍｐｌｅ.com/", ""),
    ("https://example.com\\admin", ""),
    ("https:\\\\example.com/x", ""),
    ("HTTPS://Example.COM/Path?A=B#C", ""),
    ("https://日本語.jp/ページ?キー=値", ""),
    ("http://[2001:db8::2:1]:8080/x", ""),
    ("http://[::ffff:1.2.3.4]/", ""),
    ("http://[1:2:3:4:5:6:7:8:9]/", ""),
    ("mailto:a@example.com?subject=hi", ""),
    ("javascript:alert(1)", ""),
    ("data:text/plain,hello world", ""),
    ("foo://host/a/../b", ""),
    ("foo:/a/../b", ""),
    ("foo:a/../b", ""),
    ("https://example.com/a%2520b?x=%252F", ""),
    ("https://example.com/my file.txt", ""),
    ("https://user:pw@example.com:8080/p?q#f", ""),
    ("http://192.168.0.1:80/", ""),
    ("https://example.com.", ""),
    ("https://example.com/%zz%2%41", ""),
    ("https://example.com/a%2Fb/c", ""),
    ("https://example.com/?a=1;b=2", ""),
    ("https://example.com/?a=1&a=2&a=3", ""),
    ("https://example.com/?x=a+b&y=a%20b", ""),
    ("https://example.com//////x", ""),
    ("https://example.com", ""),
    ("https://example.com?q", ""),
    ("https://example.com#h", ""),
    ("http://example.com:0/", ""),
    ("http://example.com:65535/", ""),
    ("https://exa​mple.com/", ""),
    ("https://example.com/‮exe.txt", ""),
    ("https://exaаmple.com/", ""),
    ("  https://example.com/  ", ""),
    ("ht\ttps://example.com/", ""),
    ("https://ex\nample.com/", ""),
    ("", "https://base.test/dir/page.html?old=1#frag"),
    ("//other.test/p", "https://base.test/dir/page"),
    ("../up", "https://base.test/a/b/c"),
    ("../../../../up", "https://base.test/a/b/c"),
    ("?only=query", "https://base.test/a/b?old=1#frag"),
    ("#only", "https://base.test/a/b?q=1"),
    ("", "https://base.test/a/b?q=1#f"),
    ("x", "foo://opaque/path?q"),
    ("#x", "foo://opaque/path?q"),
    ("\\\\a\\b", "https://base.test/dir/"),
    ("https://example.com/あ?い=う#え", ""),
    (r"\\srv\share", ""),
    (r"\\srv", "https://base.test/d/"),
    ("https://ex\u00ADample.com/".replace("\u00AD", "­"), ""),
    ("https://ex‌ample.com/", ""),
    ("https://ex⁠ample.com/", ""),
    ("foo://xоy/", ""),
    ("foo://xаy/", ""),
    ("https://example.com/a|b^c", ""),
]

# ---------------------------------------------------------- ブラウザ側の検査

# [1] 分解 vs ブラウザの URL
JS_PARTS = r"""([cases]) => {
  const bad = [], skip = [];
  for (const [input, base] of cases) {
    let theirs = null, threw = false;
    try { theirs = base ? new URL(input, base) : new URL(input); } catch (e) { threw = true; }
    let mine;
    try { mine = parseURL(input, base); } catch (e) { bad.push({input, base, why: 'こちらが例外: ' + e}); continue; }
    if (threw) {
      if (mine.ok) bad.push({input, base, why: 'ブラウザは拒んだのにこちらは読めた', mine: mine.href});
      continue;                                  /* 両方拒否 = 一致。対象外ではない */
    }
    if (!mine.ok) { bad.push({input, base, why: 'ブラウザは読めたのにこちらは拒んだ: ' + mine.why}); continue; }
    const u = mine.url;
    const pairs = [
      ['protocol', u.scheme + ':', theirs.protocol],
      ['username', u.username, theirs.username],
      ['password', u.password, theirs.password],
      ['host', u.host === null ? '' : u.host + (u.port === null ? '' : ':' + u.port), theirs.host],
      ['hostname', u.host === null ? '' : u.host, theirs.hostname],
      ['port', u.port === null ? '' : u.port, theirs.port],
      ['pathname', pathnameOf(u), theirs.pathname],
      ['search', (u.query === null || u.query === '') ? '' : '?' + u.query, theirs.search],
      ['hash', (u.fragment === null || u.fragment === '') ? '' : '#' + u.fragment, theirs.hash],
      ['href', mine.href, theirs.href]
    ];
    for (const [name, a, b] of pairs)
      if (a !== b) { bad.push({input, base, why: name, mine: a, real: b}); break; }
  }
  return {bad, skip: skip.length};
}"""

# [2] punycode を単独で取り出す（Python と突き合わせるため）
JS_PUNY = r"""([labels]) => labels.map(l => { try { return punyEncode(l); } catch (e) { return null; } })"""

# [3] クエリの読み分けを取り出す
JS_QUERY = r"""([queries]) => queries.map(q => {
  try { return splitQuery(q).map(p => [p.keyForm, p.valueForm, p.keyPct, p.valuePct]); }
  catch (e) { return null; }
})"""

# [4] 分解 → 組み立て直し → 同じURLに戻るか
JS_ROUND = r"""([cases]) => {
  const bad = [], stats = {checked: 0, skip: 0};
  for (const [input, base] of cases) {
    let mine;
    try { mine = parseURL(input, base); } catch (e) { stats.skip++; continue; }
    if (!mine.ok) { stats.skip++; continue; }
    const u = mine.url;
    if (u.opaque || u.host === null) { stats.skip++; continue; }  /* 組み立て欄は権限つきURL向け */
    /* 空のクエリ・断片は、組み立て欄が文字入力なので「無い」と区別できない。
       そこだけ対象外にする（件数は skipwatch に出す）。 */
    if (u.query === '' || u.fragment === '') { stats.skip++; continue; }
    const special = isSpecial(u.scheme);
    let s = u.scheme + ':';
    s += '//';
    const un = utf8PctEncode(u.username, inUserinfoSet);
    const pw = utf8PctEncode(u.password, inUserinfoSet);
    if (un || pw) s += un + (pw ? ':' + pw : '') + '@';
    const hr = parseHost(u.host, !special, null);
    s += hr.err ? u.host : hr.host;
    if (u.port !== null) s += ':' + u.port;
    const segs = pathnameOf(u).split('/');
    for (let i = 0; i < segs.length; i++) segs[i] = utf8PctEncode(segs[i], inPathSet);
    s += segs.join('/');
    if (u.query !== null)
      s += '?' + utf8PctEncode(u.query, special ? inSpecialQuerySet : inQuerySet);
    if (u.fragment !== null)
      s += '#' + utf8PctEncode(u.fragment, inFragmentSet);
    stats.checked++;
    /* 組み立て直したものが元と同じ場所を指すかを、
       「ブラウザで解析した結果が一致するか」で見る（文字列の一致ではない）。 */
    let a, b;
    try { a = new URL(s).href; b = new URL(mine.href).href; } catch (e) { stats.skip++; stats.checked--; continue; }
    if (a !== b) bad.push({input, base, built: s, mine: mine.href, a, b});
  }
  return {bad, stats};
}"""

# [5] 仕込んだ落とし穴の名指し
JS_TRAPS = r"""([cases]) => cases.map(([input, base, want]) => {
  let res;
  try { res = parseURL(input, base); } catch (e) { return {input, want, codes: [], skip: 1}; }
  let codes;
  try { codes = diagnose(input, base, res).map(n => n.code); }
  catch (e) { return {input, want, codes: [], skip: 1}; }
  return {input, base, want, codes, found: codes.indexOf(want) >= 0, skip: 0};
})"""

# 正解をこちらが握っている落とし穴（url, base, 出るべき data-code）
TRAPS = [
    ("https://www.google.com@evil.test/login", "", "userinfo-host"),
    ("https://user:secret@example.com/", "", "credentials"),
    ("https://example。com/", "", "dot-lookalike"),
    ("https://ｅｘａ.com/", "", "width-folded"),
    ("https://日本語.jp/", "", "idn-punycode"),
    ("https://exaаmple.com/", "", "mixed-script"),
    ("http://0x7f.1/", "", "ipv4-shorthand"),
    ("http://2130706433/", "", "ipv4-shorthand"),
    ("https://example.com\\admin", "", "backslash"),
    ("https://example.com./", "", "trailing-dot-host"),
    ("https://example.com:443/", "", "default-port-dropped"),
    ("https://example.com/a/../b", "", "dot-segments"),
    ("https://example.com/a%2520b", "", "double-encoded"),
    ("https://example.com/%zz", "", "bad-percent"),
    ("https://example.com/a%2Fb", "", "encoded-slash"),
    ("https://example.com/my file", "", "space-in-url"),
    ("https://example.com/?x=a+b", "", "plus-in-query"),
    ("https://example.com/?a=1&a=2", "", "dup-query-key"),
    ("https://example.com/?a=1;b=2", "", "semicolon-query"),
    ("https://example.com/?flag", "", "query-no-equals"),
    ("https://example.com/#tok", "", "fragment-not-sent"),
    ("myapp:some/path", "", "non-special-scheme"),
    ("HTTPS://example.com/", "", "case-fold"),
    ("https://exa​mple.com/", "", "invisible-chars"),
    ("https://example.com/‮cod.exe", "", "invisible-chars"),
    ("https://exa\tmple.com/", "", "tab-newline-removed"),
    ("https://example.com/あ", "", "unicode-path-utf8"),
    ("https://example.com/a|b", "", "browser-specific-encoding"),
    (r"\\srv\share", "", "unc-to-file"),
]

# ------------------------------------------------------------- わざと壊す
SABOTAGE = [
    ("IPv4 の 16進を読まない",
     'if (s.length >= 2 && (s.slice(0, 2) === "0x" || s.slice(0, 2) === "0X")){ ve = true; s = s.slice(2); radix = 16; }',
     'if (false){ ve = true; }'),
    ("既定のポートを落とさない",
     'rec.portDropped = String(port); url.port = null;',
     'rec.portDropped = String(port); url.port = String(port);'),
    ("パスの .. を畳み込まない",
     'if (isDoubleDot(buffer)){\n          rec.dotSegments = true;\n          shorten();',
     'if (isDoubleDot(buffer)){\n          rec.dotSegments = true;\n          if (false) shorten();'),
    ("punycode の bias を更新しない",
     'bias = punyAdapt(delta, h + 1, h === b);',
     'bias = bias;'),
    ("クエリの + を空白に戻さない",
     'keyForm: pctDecode(k.split("+").join(" ")),',
     'keyForm: pctDecode(k),'),
    ("@ より前を利用者名として扱わない指摘を消す",
     'if (u.username !== "" || u.password !== ""){\n    add("userinfo-host"',
     'if (false){\n    add("userinfo-host"'),
]


def chunked(pg, js, items, size, merge):
    acc = None
    for i in range(0, len(items), size):
        part = items[i:i + size]
        try:
            r = pg.evaluate(js, [part])
        except Exception as e:
            print("  !! この束で止まった: %s … (%s)" % (part[:2], e))
            continue
        acc = r if acc is None else merge(acc, r)
    return acc if acc is not None else merge_empty(js)


def merge_empty(js):
    return {"bad": [], "skip": 0}


def merge_parts(a, b):
    a["bad"] += b["bad"]; a["skip"] += b["skip"]; return a


def merge_round(a, b):
    a["bad"] += b["bad"]
    a["stats"]["checked"] += b["stats"]["checked"]
    a["stats"]["skip"] += b["stats"]["skip"]
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--page", default=None)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true")
    args = ap.parse_args()

    page = pathlib.Path(args.page) if args.page else DEFAULT_PAGE
    if not page.exists():
        cand = sorted(pathlib.Path.cwd().glob("**/docs/url/index.html"))
        if not cand:
            sys.exit("ページが見つかりません。--page で指定してください")
        page = cand[0]
    text = page.read_text(encoding="utf-8")

    rnd = random.Random(args.seed)
    cases = [[gen_url(rnd), ""] for _ in range(args.n)]
    cases += [[gen_relative(rnd), rnd.choice(BASES)] for _ in range(args.n // 2)]
    cases += [list(c) for c in EDGE_CASES]

    labels = []
    for _ in range(400):
        pool = rnd.choice([HOST_JA, HOST_CY, HOST_WIDE, HOST_JA + HOST_ASCII, HOST_CY + HOST_ASCII])
        labels.append("".join(rnd.choice(pool) for _ in range(rnd.randint(1, 8))))
    labels += ["日本語", "あ", "aあb", "ü", "ß", "рф"]

    queries = []
    for c in cases:
        q = c[0].split("?", 1)
        if len(q) == 2:
            queries.append(q[1].split("#", 1)[0])
    queries += ["a=1&b=2", "a=a+b&b=a%20b", "a=1;b=2", "flag", "=v", "a=%zz", "a=1&a=2",
                "あ=い", "x=%E3%81%82", "a=+", "a", "&&", "a=b&", "%41=%42"]

    variants = [("そのまま", text)]
    if args.sabotage:
        for name, old, new in SABOTAGE:
            if old not in text:
                print("  !! 仕込み先が見つからない: %s" % name)
                continue
            variants.append(("壊した: " + name, text.replace(old, new, 1)))

    exit_code = 0
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for label, body in variants:
            pg = br.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.set_content(body)
            pg.wait_for_timeout(250)
            print("\n=== %s ===" % label)
            if errs:
                print("  JSエラー:", errs[:3])
            # 基準の鍵に変種の名前を入れない。壊した回を正常時の基準と比べるため
            sw = SkipWatch("test_url")
            ng = 0

            r1 = chunked(pg, JS_PARTS, cases, 120, merge_parts)
            known = [b for b in r1["bad"] if is_known_divergence(b["input"], b.get("base") or "")]
            r1["bad"] = [b for b in r1["bad"] if not is_known_divergence(b["input"], b.get("base") or "")]
            print("[1] 分解 vs ブラウザの URL: %d 件中 %d 件が一致"
                  % (len(cases) - len(known), len(cases) - len(known) - len(r1["bad"])))
            if known:
                print("    ※ 既知の食い違い（非特別スキームの基準URL + 相対URL に \\ が入るもの。"
                      "Chromium の読み方が仕様とも自分自身とも合わない）: %d 件を別枠にした" % len(known))
            for b in r1["bad"][:8]:
                print("    ✗ %s%s : %s（こちら %s / ブラウザ %s）"
                      % (json.dumps(b["input"], ensure_ascii=False),
                         ("  基準 " + b["base"]) if b.get("base") else "",
                         b["why"], json.dumps(b.get("mine"), ensure_ascii=False),
                         json.dumps(b.get("real"), ensure_ascii=False)))
            if r1["bad"]:
                ng += 1

            got = pg.evaluate(JS_PUNY, [labels])
            puny_bad, puny_skip = [], 0
            for lab, mine in zip(labels, got):
                try:
                    want = lab.encode("punycode").decode("ascii")
                except Exception:
                    puny_skip += 1
                    continue
                if mine != want:
                    puny_bad.append((lab, mine, want))
            print("[2] punycode vs Python: %d 件中 %d 件が一致（対象外 %d）"
                  % (len(labels) - puny_skip, len(labels) - puny_skip - len(puny_bad), puny_skip))
            for lab, mine, want in puny_bad[:8]:
                print("    ✗ %s : こちら %s / Python %s" % (json.dumps(lab, ensure_ascii=False), mine, want))
            if puny_bad:
                ng += 1

            gotq = pg.evaluate(JS_QUERY, [queries])
            q_bad, q_skip, q_n = [], 0, 0
            for q, mine in zip(queries, gotq):
                if mine is None:
                    q_skip += 1
                    continue
                want = urllib.parse.parse_qsl(q, keep_blank_values=True)
                have = [(p[0], p[1]) for p in mine]
                q_n += 1
                if have != [(k, v) for k, v in want]:
                    q_bad.append((q, have, want))
            print("[3] クエリの読み分け vs Python parse_qsl: %d 件中 %d 件が一致（対象外 %d）"
                  % (q_n, q_n - len(q_bad), q_skip))
            for q, have, want in q_bad[:8]:
                print("    ✗ %s : こちら %s / Python %s"
                      % (json.dumps(q, ensure_ascii=False),
                         json.dumps(have, ensure_ascii=False), json.dumps(want, ensure_ascii=False)))
            if q_bad:
                ng += 1

            r4 = chunked(pg, JS_ROUND, cases, 120, merge_round)
            st = r4["stats"]
            print("[4] 分解して組み立て直すと同じURLに戻るか: %d 件中 %d 件（対象外 %d）"
                  % (st["checked"], st["checked"] - len(r4["bad"]), st["skip"]))
            for b in r4["bad"][:8]:
                print("    ✗ %s : 組み立て %s / 元 %s"
                      % (json.dumps(b["input"], ensure_ascii=False), b["a"], b["b"]))
            if r4["bad"]:
                ng += 1

            r5 = pg.evaluate(JS_TRAPS, [[list(t) for t in TRAPS]])
            done = [x for x in r5 if not x["skip"]]
            miss = [x for x in done if not x["found"]]
            print("[5] 仕込んだ落とし穴の名指し: %d 件中 %d 件で当てた"
                  % (len(done), len(done) - len(miss)))
            for m in miss[:10]:
                print("    ✗ %s : 「%s」が出なかった → %s"
                      % (json.dumps(m["input"], ensure_ascii=False), m["want"], m["codes"]))
            if miss:
                ng += 1

            sw.check("[2] punycode に当てなかった名前", puny_skip, len(labels))
            sw.check("[3] クエリで読めなかったもの", q_skip, len(queries))
            sw.check("[4] 組み立て直しの対象外", st["skip"], st["skip"] + st["checked"])
            sw.check("[5] 落とし穴の対象外", len(r5) - len(done), len(r5))
            if sw.report():
                ng += 1

            print("結果: " + ("問題なし" if ng == 0 else "%d 項目で失敗" % ng))
            if label == "そのまま" and ng:
                exit_code = 1
            if label != "そのまま" and ng == 0:
                print("  ★ 壊したのにどの検査も落ちなかった。検査に穴がある")
                exit_code = 1
            pg.close()
        br.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
