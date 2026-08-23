#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「HTTPヘッダの読み下し」の検証（2026-08-24）。

この道具が主張していることに、それぞれ**別の出どころの正解**を当てる。
参照が1つだと、こちらと参照が同じ勘違いをしたときに気づけないので、4つに分ける。

1. **分解した結果がブラウザの `Headers` と一致するか**
   名前の正規化・値の前後の空白の落とし方・同じ名前が複数来たときの結合を、
   ランダムに組み立てたヘッダの束で突き合わせる。
   ★ `Set-Cookie` は**わざと違う**。fetch の `Headers` は `get()` でカンマ結合するが、
   HTTP では Set-Cookie を結合してはいけない（Expires の値自体にカンマが入るため）。
   その差が出ること自体を最後に1件だけ確かめている。

2. **受け付ける／拒む**
   ★ ここは「この道具 vs ブラウザ」では測れない。**規格と fetch が本当に違う**ため。
   - RFC 9110 の field-value に制御文字は置けないが、fetch が拒むのは 0x00 / 0x0A / 0x0D だけ
   - fetch は前後の「HTTPの空白」を落とすが、**そこに CR と LF が入っている**（規格の OWS は SP と HTAB だけ）
   - fetch は 0xFF を超える符号位置を拒むが、こちらは貼り付けたテキストを読む道具なので通す
   なので **2つのモデルを Python に書き下し、この道具は RFC 側と、ブラウザは fetch 側と
   一致するか**をそれぞれ見る。食い違う形が何件あったかも出す（黙って一致させない）。

3. **HTTP日付の解析が Python の `email.utils` と一致するか**
   IMF-fixdate / RFC 850 / asctime の3つの形。
   ★ **2桁の年の読み方は規格と Python で本当に違う**（RFC 9110 は「50年以上先に
   見えるなら前世紀」、Python は「70未満なら2000年代」）。この道具は RFC 側に合わせてあるので、
   食い違う帯（いまなら 70〜76 年）は**差が出ることを確かめる**形で検査している。

4. **Set-Cookie の属性分解が Python の `http.cookies` と一致するか**
   名前・値・属性の3つ。CPython の `SimpleCookie` は別の言語の別実装なので参照になる。

5. **Content-Type の分解が Python の `email.message` と一致するか**
   種類とパラメータ。`get_params()` は引用符を外した値を返すので、そこまで含めて比べる。

6. **キャッシュの寿命が RFC 9111 の式どおりか**
   ⚠ これだけは**第三者の実装ではなく、規格の式を Python で別に書いたもの**に当てている
   （手元に HTTP キャッシュの実装が無いため）。同じ人が両方を書いている以上、
   1〜5 ほどの強さは無い。そう分かった上で使う。

7. **正解の分かっている落とし穴を名指しできるか**
   こちらが仕込んだ欠陥に対応する指摘が出るかを `data-code` で照合する
   （画面の文言で見ると英語版に当たらないので、最初から機械可読な鍵にしてある）。

わざと壊して検査が空振りしていないかを見る `--sabotage` つき。
対象外にした件数は `skipwatch` で毎回目に見えるところに出す。

使い方:
  python lab/scripts/test_headers.py [--n 500] [--page docs/headers/index.html]
  python lab/scripts/test_headers.py --sabotage
"""
import argparse
import datetime
import email.message
import email.utils
import http.cookies
import json
import os as _os
import pathlib
import random
import sys

_os.sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from skipwatch import SkipWatch

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

DEFAULT_PAGE = pathlib.Path("docs/headers/index.html")

# ---------------------------------------------------------------- 生成

COMMON_NAMES = [
    "Content-Type", "content-type", "CONTENT-TYPE", "Cache-Control", "Vary", "Accept",
    "Accept-Encoding", "Age", "Date", "ETag", "Server", "Link", "X-Request-Id",
    "Access-Control-Allow-Origin", "Content-Length", "Location", "Retry-After",
]
TOKEN_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&*+-.^_`|~"
# 値に使う文字。0x80〜0xFF（obs-text）も入れる。ブラウザの Headers はここまで受け取る。
VALUE_CHARS = "abcXYZ019 -_.,;:=/*+()[]{}<>?@!#$%&\"" + "éüßÿ"


def gen_name(rnd):
    if rnd.random() < 0.55:
        return rnd.choice(COMMON_NAMES)
    return "".join(rnd.choice(TOKEN_CHARS) for _ in range(rnd.randint(1, 12)))


def gen_value(rnd):
    n = rnd.randint(0, 24)
    v = "".join(rnd.choice(VALUE_CHARS) for _ in range(n))
    if rnd.random() < 0.25:
        v = " " * rnd.randint(1, 3) + v
    if rnd.random() < 0.25:
        v = v + "\t" * rnd.randint(1, 2)
    return v


def gen_block(rnd):
    """[名前, 値] の並び。Set-Cookie はここには入れない（わざと違う扱いなので別に見る）。"""
    pairs = []
    for _ in range(rnd.randint(1, 5)):
        pairs.append([gen_name(rnd), gen_value(rnd)])
    if rnd.random() < 0.35 and pairs:                 # 重複をわざと作る
        pairs.append([pairs[0][0], gen_value(rnd)])
    return pairs


# --- [2] 受け付ける/拒む 用。名前も値も壊れたものを混ぜる
BAD_NAME_CHARS = " :()<>@,;\\\"/[]?={}\téあ"
CTL_CHARS = ["\x00", "\x01", "\x07", "\x0a", "\x0d", "\x1f", "\x7f"]


def gen_validity(rnd):
    name = gen_name(rnd)
    if rnd.random() < 0.45:
        pos = rnd.randint(0, len(name))
        name = name[:pos] + rnd.choice(BAD_NAME_CHARS) + name[pos:]
    value = gen_value(rnd)
    r = rnd.random()
    if r < 0.30:
        pos = rnd.randint(0, len(value))
        value = value[:pos] + rnd.choice(CTL_CHARS) + value[pos:]
    elif r < 0.40:
        value = value + rnd.choice(["あ", "€", "\U0001f600"])
    return [name, value]


TOKEN_SET = set(TOKEN_CHARS)


def rfc_reject(name, value):
    """RFC 9110 の field-line として拒むか。この道具はこちらに従う。"""
    if not name or any(c not in TOKEN_SET for c in name):
        return True
    for ch in value.strip(" \t"):                        # OWS は SP と HTAB だけ
        c = ord(ch)
        if c != 0x09 and (c < 0x20 or c == 0x7F):
            return True
    return False


# fetch が「HTTP の空白」として前後から落とす文字。**CR と LF が入っている**のが規格との差。
FETCH_WS = "\t\n\r "


def fetch_reject(name, value):
    """fetch の Headers.append が投げるか（こちらの理解を書き下したもの）。"""
    if not name or any(c not in TOKEN_SET for c in name):
        return True
    if any(ord(ch) > 0xFF for ch in value):              # バイト列に落とせない
        return True
    for ch in value.strip(FETCH_WS):
        if ch in ("\x00", "\n", "\r"):
            return True
    return False


# RFC 9110 5.6.7 の3つの形。桁が合っていても存在しない日付は拒む。
RE_IMF = r"^[A-Za-z]{3}, (\d{2}) ([A-Za-z]{3}) (\d{4}) (\d{2}):(\d{2}):(\d{2}) GMT$"
RE_850 = r"^[A-Za-z]+, (\d{2})-([A-Za-z]{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2}) GMT$"
RE_ASC = r"^[A-Za-z]{3} ([A-Za-z]{3}) ([ \d]\d) (\d{2}):(\d{2}):(\d{2}) (\d{4})$"


def rfc_date_ok(s):
    """RFC の3つの形として読めるか（読めれば True）。Python の緩さと切り分けるために使う。"""
    import re
    for pat, order in ((RE_IMF, "dmyHMS"), (RE_850, "dmyHMS"), (RE_ASC, "mdHMSy")):
        m = re.match(pat, s.strip(" \t"))
        if not m:
            continue
        g = m.groups()
        if order == "dmyHMS":
            d, mon, y, hh, mm, ss = int(g[0]), g[1], int(g[2]), int(g[3]), int(g[4]), int(g[5])
            if pat == RE_850:
                y = 2000 + y
                if y - datetime.datetime.now(datetime.timezone.utc).year > 50:
                    y -= 100
        else:
            mon, d, hh, mm, ss, y = g[0], int(g[1]), int(g[2]), int(g[3]), int(g[4]), int(g[5])
        if mon not in MONTHS or hh > 23 or mm > 59 or ss > 59:
            return False
        try:
            datetime.datetime(y, MONTHS.index(mon) + 1, d)
        except ValueError:
            return False
        return True
    return False


# --- [3] 日付
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WDAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def gen_dates(rnd, n):
    out, two_digit = [], []
    for _ in range(n):
        y = rnd.randint(1970, 2038)
        mo = rnd.randint(1, 12)
        d = rnd.randint(1, 28)
        hh, mm, ss = rnd.randint(0, 23), rnd.randint(0, 59), rnd.randint(0, 59)
        wd = datetime.date(y, mo, d).weekday()
        form = rnd.randint(0, 2)
        if form == 0:
            out.append("%s, %02d %s %04d %02d:%02d:%02d GMT" % (WDAYS[wd], d, MONTHS[mo - 1], y, hh, mm, ss))
        elif form == 1:
            out.append("%s %s %2d %02d:%02d:%02d %04d" % (WDAYS[wd], MONTHS[mo - 1], d, hh, mm, ss, y))
        else:
            two_digit.append("%s, %02d-%s-%02d %02d:%02d:%02d GMT"
                             % (WDAYS_LONG[wd], d, MONTHS[mo - 1], y % 100, hh, mm, ss))
    out += ["", "not a date", "Mon, 32 Aug 2026 03:00:00 GMT", "Mon, 24 Foo 2026 03:00:00 GMT",
            "Mon, 24 Aug 2026 03:00:00", "0", "-1", "Thu, 01 Jan 1970 00:00:00 GMT"]
    return out, two_digit


# --- [4] Set-Cookie（SimpleCookie が知っている属性だけを使う）
COOKIE_NAMES = ["sess", "uid", "token", "_ga", "CSRF-TOKEN", "a"]
COOKIE_VALUES = ["abc123", "", "1", "eyJhbGciOiJIUzI1NiJ9", "x-y_z.0", "%E3%81%82"]


def gen_setcookie(rnd):
    s = rnd.choice(COOKIE_NAMES) + "=" + rnd.choice(COOKIE_VALUES)
    attrs = []
    if rnd.random() < 0.6:
        attrs.append("Path=/" + "".join(rnd.choice("abc") for _ in range(rnd.randint(0, 3))))
    if rnd.random() < 0.4:
        attrs.append("Domain=example.com")
    if rnd.random() < 0.4:
        attrs.append("Max-Age=" + str(rnd.randint(0, 100000)))
    if rnd.random() < 0.3:
        attrs.append("Expires=Mon, 24 Aug 2026 03:00:00 GMT")
    if rnd.random() < 0.5:
        attrs.append("Secure")
    if rnd.random() < 0.5:
        attrs.append("HttpOnly")
    if rnd.random() < 0.5:
        attrs.append("SameSite=" + rnd.choice(["Strict", "Lax", "None"]))
    rnd.shuffle(attrs)
    return "; ".join([s] + attrs)


# --- [5] Content-Type
CT_TYPES = ["text/html", "application/json", "text/plain", "image/png",
            "multipart/form-data", "application/vnd.api+json", "TEXT/HTML"]


def gen_contenttype(rnd):
    s = rnd.choice(CT_TYPES)
    if rnd.random() < 0.6:
        s += "; charset=" + rnd.choice(["utf-8", "UTF-8", "\"utf-8\"", "iso-8859-1", "Shift_JIS"])
    if rnd.random() < 0.3:
        s += "; boundary=" + rnd.choice(["xy", "\"a b\"", "----WebKitFormBoundary7MA4"])
    if rnd.random() < 0.2:
        s += "; profile=" + rnd.choice(["x", "\"y\""])
    return s


# --- [6] キャッシュの寿命
def gen_cache(rnd):
    """[ヘッダの本文, 共有キャッシュか, 期待する {store, lifetime}] を返す。
    期待値は RFC 9111 の式を Python で別に書いたもの。"""
    lines = ["HTTP/1.1 200 OK"]
    date = datetime.datetime(2026, 8, 24, 3, 0, 0, tzinfo=datetime.timezone.utc)
    lines.append("Date: " + email.utils.format_datetime(date, usegmt=True))
    shared = rnd.random() < 0.5
    cc, exp_secs, lm_secs = [], None, None
    if rnd.random() < 0.25:
        cc.append("no-store")
    if rnd.random() < 0.20:
        cc.append("private")
    if rnd.random() < 0.20:
        cc.append("no-cache")
    if rnd.random() < 0.55:
        cc.append("max-age=" + str(rnd.randint(0, 100000)))
    if rnd.random() < 0.35:
        cc.append("s-maxage=" + str(rnd.randint(0, 100000)))
    if rnd.random() < 0.30:
        exp_secs = rnd.randint(-1000, 100000)
        lines.append("Expires: " + email.utils.format_datetime(
            date + datetime.timedelta(seconds=exp_secs), usegmt=True))
    if rnd.random() < 0.30:
        lm_secs = rnd.randint(1, 1000000)
        lines.append("Last-Modified: " + email.utils.format_datetime(
            date - datetime.timedelta(seconds=lm_secs), usegmt=True))
    if rnd.random() < 0.15:
        lines.append("Vary: *")
    if cc:
        rnd.shuffle(cc)
        lines.append("Cache-Control: " + ", ".join(cc))

    dirs = {}
    for d in cc:
        if "=" in d:
            k, v = d.split("=", 1)
            dirs[k] = v
        else:
            dirs[d] = ""
    want = {"store": True, "lifetime": None}
    if "no-store" in dirs:
        want["store"] = False
    elif shared and "private" in dirs:
        want["store"] = False
    elif "Vary: *" in lines:
        want["store"] = False
    else:
        if shared and "s-maxage" in dirs:
            want["lifetime"] = int(dirs["s-maxage"])
        elif "max-age" in dirs:
            want["lifetime"] = int(dirs["max-age"])
        elif exp_secs is not None:
            want["lifetime"] = exp_secs
        elif lm_secs is not None:
            want["lifetime"] = max(0, lm_secs // 10)      # 端数は切り捨て（規格は丸め方を決めていない）
        if "no-cache" in dirs:
            want["lifetime"] = 0
    return ["\n".join(lines), shared, want]


# ---------------------------------------------------------------- 落とし穴（正解を握る）
R = "HTTP/1.1 200 OK\n"
TRAPS = [
    ("space-before-colon", R + "Content-Type : text/html", False),
    ("obs-fold", R + "X-Note: a\n  b\nContent-Type: text/html", False),
    ("dup-singleton", R + "Content-Type: text/html\nContent-Type: text/plain", False),
    ("set-cookie-multi", R + "Set-Cookie: a=1\nSet-Cookie: b=2", False),
    ("nonascii-value", R + "X-Name: 日本語", False),
    ("req-host-missing", "GET / HTTP/1.1\nAccept: */*", False),
    ("req-host-multi", "GET / HTTP/1.1\nHost: a.example\nHost: b.example", False),
    ("cc-no-cache", R + "Cache-Control: no-cache", False),
    ("cc-nostore-conflict", R + "Cache-Control: no-store, max-age=60", False),
    ("cc-maxage-vs-expires", R + "Cache-Control: max-age=60\nExpires: Mon, 24 Aug 2026 03:00:00 GMT", False),
    ("expires-invalid", R + "Expires: 0", False),
    ("cookie-shared-cache", R + "Cache-Control: max-age=60\nSet-Cookie: uid=1", True),
    ("vary-star", R + "Vary: *", False),
    ("vary-ua", R + "Vary: User-Agent", False),
    ("cors-vary-origin", R + "Access-Control-Allow-Origin: https://a.example\nVary: Accept-Encoding", False),
    ("vary-missing-ae", R + "Content-Encoding: gzip\nVary: Origin", False),
    ("age-over-maxage", R + "Cache-Control: max-age=60\nAge: 600", False),
    ("no-cache-directive", R + "Content-Type: text/html; charset=utf-8\nX-Content-Type-Options: nosniff", False),
    ("cc-immutable", R + "Cache-Control: max-age=60, immutable", False),
    ("cookie-none-insecure", R + "Set-Cookie: a=1; SameSite=None", False),
    ("cookie-samesite-missing", R + "Set-Cookie: a=1; Secure", False),
    ("cookie-samesite-bad", R + "Set-Cookie: a=1; Secure; SameSite=Laxx", False),
    ("cookie-no-secure", R + "Set-Cookie: a=1; SameSite=Lax", False),
    ("cookie-no-httponly", R + "Set-Cookie: session=1; Secure; SameSite=Lax", False),
    ("cookie-domain", R + "Set-Cookie: a=1; Domain=example.com; Secure; SameSite=Lax", False),
    ("cookie-maxage-expires",
     R + "Set-Cookie: a=1; Max-Age=60; Expires=Mon, 24 Aug 2026 03:00:00 GMT; Secure; SameSite=Lax", False),
    ("cookie-bad-value", R + "Set-Cookie: a=x y; Secure; SameSite=Lax", False),
    ("cookie-too-big", R + "Set-Cookie: a=" + ("z" * 4200) + "; Secure; SameSite=Lax", False),
    ("ct-missing", R + "Content-Length: 10", False),
    ("ct-no-charset", R + "Content-Type: text/html", False),
    ("ct-json-charset", R + "Content-Type: application/json; charset=utf-8", False),
    ("nosniff-missing", R + "Content-Type: text/html; charset=utf-8", False),
    ("cd-nonascii", R + "Content-Type: application/pdf\nContent-Disposition: attachment; filename=\"請求書.pdf\"", False),
    ("cl-and-te", R + "Content-Length: 10\nTransfer-Encoding: chunked", False),
    ("xfo-allow-from", R + "X-Frame-Options: ALLOW-FROM https://a.example", False),
    ("xfo-and-csp", R + "X-Frame-Options: DENY\nContent-Security-Policy: frame-ancestors 'none'", False),
    ("hsts-zero", R + "Strict-Transport-Security: max-age=0", False),
    ("hsts-preload-bad", R + "Strict-Transport-Security: max-age=86400; preload", False),
    ("csp-report-only", R + "Content-Security-Policy-Report-Only: default-src 'self'", False),
    ("csp-two", R + "Content-Security-Policy: default-src 'self'\nContent-Security-Policy: img-src *", False),
    ("csp-unsafe-inline", R + "Content-Security-Policy: script-src 'self' 'unsafe-inline'", False),
    ("csp-no-fallback", R + "Content-Security-Policy: default-src 'self'", False),
    ("cors-star-credentials",
     R + "Access-Control-Allow-Origin: *\nAccess-Control-Allow-Credentials: true", False),
    ("cors-multi-origin", R + "Access-Control-Allow-Origin: https://a.example, https://b.example", False),
    ("cors-expose-missing", R + "Access-Control-Allow-Origin: *", False),
    ("referrer-unsafe", R + "Referrer-Policy: unsafe-url", False),
    ("permissions-old-syntax", R + "Permissions-Policy: geolocation 'none'", False),
    ("version-banner", R + "Server: nginx/1.24.0", False),
]

# ---------------------------------------------------------------- ページ側で回すもの

JS_PARSE = """(cases) => cases.map(pairs => {
  const text = pairs.map(p => p[0] + ": " + p[1]).join("\\n") + "\\n";
  const mine = parseBlock(text);
  const ours = {};
  for (const n of mine.order) ours[n] = combined(mine, n);
  let theirs = null, threw = false;
  try {
    const h = new Headers();
    for (const p of pairs) h.append(p[0], p[1]);
    theirs = {};
    for (const p of pairs) theirs[p[0].toLowerCase()] = h.get(p[0].toLowerCase());
  } catch (e) { threw = true; }
  return {ours: ours, theirs: theirs, threw: threw, errs: mine.errors.length};
})"""

JS_VALID = """(pairs) => pairs.map(p => {
  let they = false;
  try { const h = new Headers(); h.append(p[0], p[1]); } catch (e) { they = true; }
  const we = !isToken(p[0]) || badValueCharAt(trimOWS(p[1])) >= 0;
  return {we: we, they: they};
})"""

JS_DATE = """(list) => list.map(s => parseHttpDate(s))"""

JS_COOKIE = """(list) => list.map(s => {
  const parts = splitParams(s);
  if (!parts.length) return null;
  const head = parts[0];
  const attrs = {};
  for (let i = 1; i < parts.length; i++) {
    attrs[parts[i].k.toLowerCase()] = parts[i].v === null ? true : unquote(parts[i].v);
  }
  return {name: head.k, value: head.v === null ? null : unquote(head.v), attrs: attrs};
})"""

JS_CT = """(list) => list.map(s => {
  const parts = splitParams(s);
  const type = parts.length ? parts[0].raw.toLowerCase() : "";
  const params = [];
  for (let i = 1; i < parts.length; i++) {
    params.push([parts[i].k.toLowerCase(), unquote(parts[i].v === null ? "" : parts[i].v)]);
  }
  return {type: type, params: params};
})"""

JS_CACHE = """(cases) => cases.map(c => {
  const P = parseBlock(c[0]);
  const m = cacheModel(P, c[1]);
  return {store: m.store, lifetime: m.lifetime};
})"""

JS_TRAPS = """(list) => list.map(t => {
  const P = parseBlock(t[1]);
  const codes = pitfalls(P, t[2]).map(x => x.code);
  return {want: t[0], codes: codes, found: codes.indexOf(t[0]) >= 0};
})"""

JS_SETCOOKIE_DIFF = """() => {
  const text = "HTTP/1.1 200 OK\\nSet-Cookie: a=1; Expires=Mon, 24 Aug 2026 03:00:00 GMT\\nSet-Cookie: b=2\\n";
  const P = parseBlock(text);
  const h = new Headers();
  h.append("Set-Cookie", "a=1; Expires=Mon, 24 Aug 2026 03:00:00 GMT");
  h.append("Set-Cookie", "b=2");
  return {ours: combined(P, "set-cookie"), count: P.map["set-cookie"].length, theirs: h.get("set-cookie")};
}"""

# ---------------------------------------------------------------- わざと壊す

SABOTAGE = [
    ("同じ名前をカンマだけで繋ぐ（空白を落とす）",
     'return a.join(", ");',
     'return a.join(",");'),
    ("値の前の空白しか落とさない",
     'while (b > a && (s.charAt(b - 1) === " " || s.charAt(b - 1) === "\\t")) b--;',
     ''),
    ("名前に置ける記号から ~ を外す",
     'var TOKEN_EXTRA = "!#$%&*+-.^_`|~" + APOS;',
     'var TOKEN_EXTRA = "!#$%&*+-.^_`|" + APOS;'),
    ("2桁の年をいつでも2000年代として読む",
     'if (full - new Date().getUTCFullYear() > 50) full -= 100;',
     ''),
    ("Set-Cookie の属性を最初の = で割らない",
     'else res.push({ k:trimOWS(t.slice(0, e)), v:trimOWS(t.slice(e + 1)), raw:t });',
     'else res.push({ k:trimOWS(t.slice(0, e)), v:trimOWS(t.slice(e + 2)), raw:t });'),
    ("共有キャッシュで s-maxage を見ない",
     'if (shared && d("s-maxage") && /^\\d+$/.test(dir["s-maxage"])){',
     'if (false && d("s-maxage")){'),
    ("SameSite=None に Secure が要ることを忘れる",
     'if (ss === "none" && !Object.prototype.hasOwnProperty.call(attrs, "secure")){',
     'if (false){'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--page", default=None)
    ap.add_argument("--seed", type=int, default=20260824)
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true")
    args = ap.parse_args()

    page = pathlib.Path(args.page) if args.page else DEFAULT_PAGE
    if not page.exists():
        cand = sorted(pathlib.Path.cwd().glob("**/docs/headers/index.html"))
        if not cand:
            sys.exit("ページが見つかりません。--page で指定してください")
        page = cand[0]
    text = page.read_text(encoding="utf-8")

    rnd = random.Random(args.seed)
    blocks = [gen_block(rnd) for _ in range(args.n)]
    valids = [gen_validity(rnd) for _ in range(args.n)]
    dates, two_digit = gen_dates(rnd, args.n)
    cookies = [gen_setcookie(rnd) for _ in range(args.n)]
    ctypes = [gen_contenttype(rnd) for _ in range(args.n)]
    caches = [gen_cache(rnd) for _ in range(args.n)]

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
            pg.wait_for_timeout(200)
            print("\n=== %s ===" % label)
            if errs:
                print("  !! JSエラー: %s" % errs[:3])
            ng = 0
            sw = SkipWatch("test_headers" if label == "そのまま" else "test_headers", update=args.update_skip_baseline)

            # [1] 分解 vs Headers
            got = pg.evaluate(JS_PARSE, blocks)
            bad1, skip1, n1 = [], 0, 0
            for pairs, g in zip(blocks, got):
                if g["threw"] or g["theirs"] is None:
                    skip1 += 1                       # ブラウザ側が受け付けなかった束は比べようがない
                    continue
                n1 += 1
                for k, v in g["theirs"].items():
                    if g["ours"].get(k) != v:
                        bad1.append((pairs, k, g["ours"].get(k), v))
                        break
            print("[1] 分解した結果 vs ブラウザの Headers: %d 件中 %d 件が一致（対象外 %d）"
                  % (n1, n1 - len(bad1), skip1))
            for b in bad1[:6]:
                print("    ✗ %s : %s こちら %s / ブラウザ %s"
                      % (json.dumps(b[0], ensure_ascii=False), b[1],
                         json.dumps(b[2], ensure_ascii=False), json.dumps(b[3], ensure_ascii=False)))
            if bad1:
                ng += 1

            # [2] 受け付ける/拒む
            gotv = pg.evaluate(JS_VALID, valids)
            bad2, bad2b, gap2 = [], [], 0
            for pair, g in zip(valids, gotv):
                want_rfc, want_fetch = rfc_reject(pair[0], pair[1]), fetch_reject(pair[0], pair[1])
                if g["we"] != want_rfc:
                    bad2.append((pair, g["we"], want_rfc))
                if g["they"] != want_fetch:
                    bad2b.append((pair, g["they"], want_fetch))
                if want_rfc != want_fetch:
                    gap2 += 1
            print("[2] 受け付ける／拒む: この道具 vs RFC 9110 → %d 件中 %d 件 / "
                  "ブラウザ vs fetch の決まり → %d 件中 %d 件（両者が食い違う形 %d 件）"
                  % (len(valids), len(valids) - len(bad2), len(valids), len(valids) - len(bad2b), gap2))
            for b in bad2[:6]:
                print("    ✗ この道具: %s : 拒否=%s / RFC なら %s"
                      % (json.dumps(b[0], ensure_ascii=False), b[1], b[2]))
            for b in bad2b[:6]:
                print("    ✗ ブラウザ: %s : 拒否=%s / fetch の決まりなら %s"
                      % (json.dumps(b[0], ensure_ascii=False), b[1], b[2]))
            if bad2 or bad2b:
                ng += 1

            # [3] 日付
            gotd = pg.evaluate(JS_DATE, dates)
            bad3, skip3, n3, lenient = [], 0, 0, 0
            for s, mine in zip(dates, gotd):
                try:
                    dt = email.utils.parsedate_to_datetime(s)
                except (TypeError, ValueError):
                    dt = None
                if rfc_date_ok(s):
                    if dt is None:
                        skip3 += 1            # 規格では読めるのに Python が読めない形（無ければ0のはず）
                        continue
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    n3 += 1
                    want = int(dt.timestamp() * 1000)
                    if mine != want:
                        bad3.append((s, mine, want))
                else:
                    # 規格では読めない形。この道具は None を返さなければならない。
                    if mine is not None:
                        bad3.append((s, mine, "規格では読めない形なので None のはず"))
                    if dt is not None:
                        lenient += 1          # Python のほうが緩い（GMT が無い形など）
            print("[3] HTTP日付 vs Python email.utils: %d 件中 %d 件が一致"
                  "（規格では読めないのに Python が読む形 %d 件 / Python が読めない形 %d 件）"
                  % (n3, n3 - len([b for b in bad3 if not isinstance(b[2], str)]), lenient, skip3))
            for b in bad3[:6]:
                print("    ✗ %s : こちら %s / Python %s" % (json.dumps(b[0]), b[1], b[2]))
            if bad3:
                ng += 1

            # [3b] 2桁の年（規格と Python が本当に違うところ）
            gott = pg.evaluate(JS_DATE, two_digit)
            agree, differ, wrong = 0, 0, []
            now_year = datetime.datetime.now(datetime.timezone.utc).year
            for s, mine in zip(two_digit, gott):
                yy = int(s.split("-")[2].split(" ")[0])
                rfc_year = 2000 + yy - (100 if (2000 + yy) - now_year > 50 else 0)
                py = email.utils.parsedate_to_datetime(s)
                if py.tzinfo is None:
                    py = py.replace(tzinfo=datetime.timezone.utc)
                if mine is None:
                    wrong.append((s, "読めなかった", rfc_year))
                    continue
                got_year = datetime.datetime.fromtimestamp(mine / 1000, datetime.timezone.utc).year
                if got_year != rfc_year:
                    wrong.append((s, got_year, rfc_year))
                elif py.year == rfc_year:
                    agree += 1
                else:
                    differ += 1
            print("[3b] 2桁の年（RFC 9110 の読み方）: %d 件中 %d 件が正しい"
                  "（うち Python と一致 %d / 規格どおり食い違った %d）"
                  % (len(two_digit), len(two_digit) - len(wrong), agree, differ))
            for w in wrong[:6]:
                print("    ✗ %s : こちら %s / 規格どおりなら %s" % (json.dumps(w[0]), w[1], w[2]))
            if wrong:
                ng += 1

            # [4] Set-Cookie
            gotc = pg.evaluate(JS_COOKIE, cookies)
            bad4, skip4, n4 = [], 0, 0
            for s, mine in zip(cookies, gotc):
                sc = http.cookies.SimpleCookie()
                try:
                    sc.load(s)
                except http.cookies.CookieError:
                    skip4 += 1
                    continue
                if len(sc) != 1 or mine is None:
                    skip4 += 1
                    continue
                key = list(sc.keys())[0]
                m = sc[key]
                want_attrs = {}
                for a, v in m.items():
                    if v == "" or v is False:
                        continue
                    want_attrs[a] = True if v is True else v
                have_attrs = dict(mine["attrs"])
                n4 += 1
                if mine["name"] != key or mine["value"] != m.value or have_attrs != want_attrs:
                    bad4.append((s, (mine["name"], mine["value"], have_attrs), (key, m.value, want_attrs)))
            print("[4] Set-Cookie の属性 vs Python http.cookies: %d 件中 %d 件が一致（対象外 %d）"
                  % (n4, n4 - len(bad4), skip4))
            for b in bad4[:6]:
                print("    ✗ %s\n        こちら %s\n        Python %s"
                      % (b[0], json.dumps(b[1], ensure_ascii=False), json.dumps(b[2], ensure_ascii=False)))
            if bad4:
                ng += 1

            # [5] Content-Type
            gotct = pg.evaluate(JS_CT, ctypes)
            bad5 = []
            for s, mine in zip(ctypes, gotct):
                msg = email.message.EmailMessage()
                msg["Content-Type"] = s
                want_type = msg.get_content_type()
                want_params = [(k, v) for k, v in msg.get_params()[1:]]
                have_params = [(k, v) for k, v in mine["params"]]
                if mine["type"] != want_type or have_params != want_params:
                    bad5.append((s, (mine["type"], have_params), (want_type, want_params)))
            print("[5] Content-Type vs Python email.message: %d 件中 %d 件が一致"
                  % (len(ctypes), len(ctypes) - len(bad5)))
            for b in bad5[:6]:
                print("    ✗ %s\n        こちら %s\n        Python %s"
                      % (b[0], json.dumps(b[1], ensure_ascii=False), json.dumps(b[2], ensure_ascii=False)))
            if bad5:
                ng += 1

            # [6] キャッシュの寿命
            gotk = pg.evaluate(JS_CACHE, caches)
            bad6 = []
            for c, mine in zip(caches, gotk):
                want = c[2]
                if mine["store"] != want["store"] or (want["store"] and mine["lifetime"] != want["lifetime"]):
                    bad6.append((c[0].replace("\n", " / "), c[1], mine, want))
            print("[6] キャッシュの寿命 vs RFC 9111 の式（Python で別に書いたもの）: %d 件中 %d 件が一致"
                  % (len(caches), len(caches) - len(bad6)))
            for b in bad6[:6]:
                print("    ✗ 共有=%s %s\n        こちら %s / 期待 %s"
                      % (b[1], b[0], json.dumps(b[2]), json.dumps(b[3])))
            if bad6:
                ng += 1

            # [7] 落とし穴の名指し
            gotp = pg.evaluate(JS_TRAPS, [list(t) for t in TRAPS])
            miss = [x for x in gotp if not x["found"]]
            print("[7] 仕込んだ落とし穴の名指し: %d 件中 %d 件で当てた"
                  % (len(gotp), len(gotp) - len(miss)))
            for m in miss[:10]:
                print("    ✗ 「%s」が出なかった → %s" % (m["want"], ",".join(m["codes"])))
            if miss:
                ng += 1

            # [8] Set-Cookie だけはブラウザとわざと違う
            d = pg.evaluate(JS_SETCOOKIE_DIFF)
            ok8 = (d["count"] == 2 and d["ours"] == "a=1; Expires=Mon, 24 Aug 2026 03:00:00 GMT"
                   and d["theirs"] != d["ours"])
            print("[8] Set-Cookie を結合しない（ブラウザとわざと違う）: %s"
                  % ("そうなっている" if ok8 else "✗ " + json.dumps(d, ensure_ascii=False)))
            if not ok8:
                ng += 1

            sw.check("[1] ブラウザが受け付けなかった束", skip1, len(blocks))
            # [2] は「対象外」ではない（両方のモデルを全件見ている）ので skipwatch には入れない。
            # 最初ここに入れていたが、母数の引きかたでゆれるだけの数に ★ が付いて紛らわしかった。
            sw.check("[3] Python が読めなかった規格どおりの日付", skip3, len(dates))
            sw.check("[4] SimpleCookie が読めなかったもの", skip4, len(cookies))
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
