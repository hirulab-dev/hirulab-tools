#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「JWTの読み下し」の検証（2026-08-24）。

この道具が主張していることに、それぞれ**別の出どころの正解**を当てる。
参照が1つだと、こちらと参照が同じ勘違いをしたときに気づけないので、分けてある。

1. **分解した結果が Python と一致するか**
   base64url の復号は `base64.urlsafe_b64decode`、UTF-8 は `bytes.decode`、
   JSON は `json.loads`。**3つとも別の標準ライブラリ**なので、
   この道具の自前実装（atob も TextDecoder も JSON.parse も使っていない）に当てる意味がある。

2. **クレームの判定が PyJWT と一致するか**
   ★ここがいちばん強い参照。PyJWT は別の言語の第三者実装で、
   `exp` が切れているか・`nbf` がまだか・`aud` が合うかを自分で判断する。
   この道具が出す指摘（`exp-past` / `nbf-future`）と、PyJWT が投げる例外が
   同じ形で一致するかを見る。

3. **署名の検証が Python と一致するか**
   HMAC は `hmac`（標準）、RSA と楕円曲線は `cryptography`。
   この道具はブラウザの `crypto.subtle` で検証するので、
   **まったく別の実装どうしの突き合わせ**になる。
   正しい鍵・違う鍵・中身を1バイト変えたもの・DER 形式の署名を混ぜる。

4. **★「規格が拒む形」と「実装が拒む形」は違う**
   RFC 7515 は base64url に詰めの `=` を書いてはいけないと決め、`+` `/` も認めない。
   だが**実装はそれを受け取ってしまうことがある**。
   ここでは (a) 規格どおりの厳しいモデルを Python に書き下し、
   (b) PyJWT が実際にどうするかを測り、(c) この道具がその差をすべて名指しできるかを見る。
   ★ この道具は**拒まない**（貼られたものを読んで説明するのが仕事なので）。
   代わりに `b64-padding` / `b64-standard` / `b64-slack` で名指しする。
   「拒むか」ではなく「名指しできるか」で測るのが正しい、という切り分け。

5. **正解の分かっている落とし穴を名指しできるか**
   57 種類ぜんぶに、その形を持つトークンを1つずつ用意して `data-code` で照合する
   （画面の文言で見ると英語版に当たらないので、最初から機械可読な鍵にしてある）。

6. **ページ内の自己検査が全部通っているか**
   道具自身がその場で atob / TextDecoder / JSON.parse と突き合わせている欄。

わざと壊して検査が空振りしていないかを見る `--sabotage` つき。
対象外にした件数は `skipwatch` で毎回目に見えるところに出す。

使い方:
  python lab/scripts/test_jwt.py [--n 400] [--page docs/jwt/index.html]
  python lab/scripts/test_jwt.py --sabotage
"""
import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os as _os
import pathlib
import random
import sys
import time

_os.sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from skipwatch import SkipWatch

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

import warnings

import jwt as pyjwt                                  # PyJWT（第三者実装）

warnings.filterwarnings("ignore", module="jwt")      # 短い鍵の注意は検査の対象ではない
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding as apad

DEFAULT_PAGE = pathlib.Path("docs/jwt/index.html")


# ---------------------------------------------------------------- 小道具

def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def seg(obj):
    return b64u(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def canon(v):
    """数の書き方の差だけで落とさないための正規化。
    Python の json は 1e10 を 10000000000.0 と書き、JS は 10000000000 と書く。
    値そのものは同じなので、整数で表せる浮動小数点は整数に寄せてから比べる。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        if v == int(v) and abs(v) < 2 ** 53:
            return int(v)
        return v
    if isinstance(v, list):
        return [canon(x) for x in v]
    if isinstance(v, dict):
        return {k: canon(x) for k, x in v.items()}
    return v


def canon_json(v):
    return json.dumps(canon(v), sort_keys=True, ensure_ascii=False)


def mk_hs(header, payload, secret=b"k", alg="HS256"):
    h = seg(header)
    p = seg(payload)
    si = (h + "." + p).encode()
    d = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}[alg]
    return h + "." + p + "." + b64u(hmac.new(secret, si, d).digest())


def mk_raw(header, payload, sig="QUJD"):
    """署名は当てにしない（分解と指摘の検査用）。"""
    return seg(header) + "." + seg(payload) + "." + sig


# ---------------------------------------------------------------- [1] 生成

JP = "あいうえお漢字テスト"
EMOJI = "\U0001F602\U0001F680"
STRANGE = ["", " ", "\n", "\t", "\\", "\"", "/", "<>&", "null", "0", JP, EMOJI, "a" * 40]


def gen_json_value(rnd, depth=0):
    r = rnd.random()
    if depth > 2 or r < 0.35:
        return rnd.choice(STRANGE)
    if r < 0.50:
        return rnd.choice([0, 1, -1, 1787530000, 1787530000000, 3.5, -0.125, 1e10])
    if r < 0.58:
        return rnd.choice([True, False, None])
    if r < 0.78:
        return [gen_json_value(rnd, depth + 1) for _ in range(rnd.randint(0, 3))]
    return {("k%d" % i): gen_json_value(rnd, depth + 1) for i in range(rnd.randint(0, 3))}


CLAIM_NAMES = ["iss", "sub", "aud", "exp", "nbf", "iat", "jti", "name", "scope", "role",
               "email", "groups", "x-custom", JP, "a" * 30]


def gen_token(rnd):
    hdr = {"alg": rnd.choice(["HS256", "HS384", "HS512", "RS256", "ES256", "none", "hs256", "XX9"])}
    if rnd.random() < 0.7:
        hdr["typ"] = rnd.choice(["JWT", "at+jwt", "JOSE", 1])
    if rnd.random() < 0.3:
        hdr["kid"] = rnd.choice(["k1", "../../etc/passwd", "a" * 20, 5])
    pl = {}
    for _ in range(rnd.randint(0, 6)):
        pl[rnd.choice(CLAIM_NAMES)] = gen_json_value(rnd)
    if rnd.random() < 0.6:
        pl["exp"] = rnd.randint(1500000000, 1900000000)
    return mk_raw(hdr, pl, sig=b64u(bytes(rnd.randrange(256) for _ in range(rnd.choice([0, 3, 32, 48, 64])))))


# ---------------------------------------------------------------- [4] モデル

URLSAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
STDONLY = set("+/")


def rfc_strict_reject(segment):
    """RFC 7515 / RFC 4648 §5 のとおりに厳しく読んだら拒むか。
    ・base64url の字表のみ（+ と / は不可）
    ・詰めの = を書かない
    ・長さを4で割った余りが1にならない
    ・余ったビットは0（正規化されている）"""
    if "=" in segment:
        return True
    for ch in segment:
        if ch not in URLSAFE:
            return True
    if len(segment) % 4 == 1:
        return True
    # 余りビット
    tail = len(segment) % 4
    if tail:
        alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        last = alpha.index(segment[-1])
        if tail == 2 and (last & 0x0F):
            return True
        if tail == 3 and (last & 0x03):
            return True
    return False


def pyjwt_reject(token):
    """PyJWT が「読めない」と言うか（署名は見ない）。"""
    try:
        pyjwt.get_unverified_header(token)
        pyjwt.decode(token, options={"verify_signature": False})
        return False
    except Exception:
        return True


def gen_encoding_case(rnd):
    """符号化が規格から外れた形をわざと作る。"""
    hdr = {"alg": "HS256", "typ": "JWT"}
    pl = {"sub": "1"}
    h, p = seg(hdr), seg(pl)
    s = "QUJD"
    kind = rnd.choice(["clean", "pad", "std", "slack", "slack", "pad", "std"])
    which = rnd.choice([0, 1, 2])
    parts = [h, p, s]
    if kind == "pad":
        raw = b64u_dec(parts[which])
        parts[which] = base64.urlsafe_b64encode(raw).decode()          # = を残す
        if not parts[which].endswith("="):
            kind = "clean"
    elif kind == "std":
        raw = b64u_dec(parts[which])
        std = base64.b64encode(raw).decode().rstrip("=")
        if not (set(std) & STDONLY):
            kind = "clean"
        parts[which] = std
    elif kind == "slack":
        t = parts[which]
        if len(t) % 4 in (2, 3):
            alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            last = alpha.index(t[-1])
            bump = 1 if len(t) % 4 == 3 else 1
            parts[which] = t[:-1] + alpha[last | bump]
            if parts[which] == t:
                kind = "clean"
        else:
            kind = "clean"
    return {"t": ".".join(parts), "kind": kind}


# ---------------------------------------------------------------- [1b] 段そのもの

def py_seg(segment):
    """Python に同じ段を読ませる。base64 は validate=True で厳しく、UTF-8 も厳しく。
    ★ 既定の `urlsafe_b64decode` は字表にない文字を**黙って捨てる**ので参照にならない。
       validate=True を明示して初めて拒む。"""
    body = segment
    pad = body.endswith("=")
    body = body.rstrip("=")
    try:
        raw = base64.b64decode(body + "=" * (-len(body) % 4), altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        # + と / は url-safe の字表に無いので validate=True では拒まれる。
        # 標準 base64 として読み直せるかを別に見る（この道具は読み直す＝拒まない）。
        try:
            raw = base64.b64decode(body + "=" * (-len(body) % 4), validate=True)
        except (binascii.Error, ValueError):
            return {"stage": "b64", "pad": pad}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"stage": "utf8", "pad": pad}
    return {"stage": "ok", "text": text, "pad": pad,
            "canonical": base64.urlsafe_b64encode(raw).decode().rstrip("=")}


BAD_UTF8 = [
    bytes([0xC0, 0x80]),                     # overlong（本当は U+0000）
    bytes([0xE0, 0x80, 0x80]),               # overlong
    bytes([0xF0, 0x80, 0x80, 0x80]),         # overlong
    bytes([0xED, 0xA0, 0x80]),               # サロゲート U+D800
    bytes([0xED, 0xBF, 0xBF]),               # サロゲート U+DFFF
    bytes([0xF5, 0x80, 0x80, 0x80]),         # U+10FFFF より上
    bytes([0xF8, 0x88, 0x80, 0x80, 0x80]),   # 5バイト（もう無い形）
    bytes([0xE3, 0x81]),                     # 途中で切れている
    bytes([0x80]),                           # いきなり続きバイト
    bytes([0xC3]),                           # 先頭だけ
]
GOOD_UTF8 = [
    b"", b"A", b"{}", "あ".encode(), "😂".encode(), "aあ😂".encode(),
    bytes([0x7F]), bytes([0xC2, 0x80]), bytes([0xE0, 0xA0, 0x80]), bytes([0xF0, 0x90, 0x80, 0x80]),
]


def seg_cases():
    """(ラベル, 段, 期待) の並び。期待は Python が出す。"""
    out = []
    for b in GOOD_UTF8:
        out.append(("正しい:" + repr(b), b64u(b)))
    for b in BAD_UTF8:
        out.append(("UTF-8が壊れている:" + repr(b), b64u(b)))
    # 長さが4で割って1余る（base64 としてありえない）
    for n in (1, 5, 9):
        out.append(("長さ%%4==1(%d)" % n, "A" * n))
    # 字表にない文字
    for ch in ("*", "!", " ", "あ", "=", "@"):
        out.append(("字表にない文字:" + ch, "QQ" + ch + "QQ"))
    # 標準 base64 の記号
    out.append(("標準base64の+", base64.b64encode(bytes([0xFB, 0xEF, 0xBE])).decode().rstrip("=")))
    out.append(("標準base64の/", base64.b64encode(bytes([0xFF, 0xFF, 0xFF])).decode().rstrip("=")))
    # 詰めの =
    out.append(("詰めのあり(1)", base64.urlsafe_b64encode(b"AB").decode()))
    out.append(("詰めのあり(2)", base64.urlsafe_b64encode(b"A").decode()))
    # ★ 余ったビットが0でない形。長さ%4 が 2 と 3 の**両方**を作る
    #   （片方しか作らないと、もう片方の枝を壊しても検査が空振りする）
    alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    for raw, mask in ((b"A", 0x0F), (b"AB", 0x03)):          # 1バイト→2文字 / 2バイト→3文字
        t = b64u(raw)
        last = alpha.index(t[-1])
        out.append(("余りビットが0でない(%%4==%d)" % (len(t) % 4), t[:-1] + alpha[last | mask]))
        out.append(("余りビットが0(%%4==%d)" % (len(t) % 4), t))
    return out


# ---------------------------------------------------------------- [5] 落とし穴

NOW = int(time.time())


def pitfall_cases():
    """(code, token) を返す。57 件ぜんぶ。"""
    C = []

    def add(code, tok):
        C.append((code, tok))

    base_h = {"alg": "HS256", "typ": "JWT"}
    base_p = {"iss": "x", "aud": "y", "jti": "z", "sub": "1",
              "iat": NOW - 60, "exp": NOW + 600}

    def P(**kw):
        d = dict(base_p)
        d.update(kw)
        return d

    def H(**kw):
        d = dict(base_h)
        d.update(kw)
        return d

    ok = mk_raw(base_h, base_p)

    # --- 入力のそうじ
    add("input-bearer", "Bearer " + ok)
    add("input-space", "  " + ok + "  ")
    add("input-quote", "\"" + ok + "\"")

    # --- 形
    add("jwe", "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkEyNTZHQ00ifQ.OKOa.48V1.5eym.XFBo")
    add("two-parts", seg(base_h) + "." + seg(base_p))

    # --- alg
    add("alg-missing", mk_raw({"typ": "JWT"}, base_p))
    add("alg-not-string", mk_raw({"alg": 1, "typ": "JWT"}, base_p))
    add("alg-none", seg({"alg": "none", "typ": "JWT"}) + "." + seg(base_p) + ".")
    add("alg-case", mk_raw(H(alg="hs256"), base_p))
    add("alg-unknown", mk_raw(H(alg="ZZ999"), base_p))
    add("alg-hmac", ok)
    add("alg-confusion", mk_raw(H(alg="RS256"), base_p))

    # --- ヘッダの項目
    add("typ-other", mk_raw(H(typ="at+jose"), base_p))
    add("typ-missing", mk_raw({"alg": "HS256"}, base_p))
    add("kid-path", mk_raw(H(kid="../../etc/passwd"), base_p))
    add("kid-inject", mk_raw(H(kid="k1; DROP TABLE keys"), base_p))
    add("kid-not-string", mk_raw(H(kid=7), base_p))
    add("hdr-jwk", mk_raw(H(jwk={"kty": "oct", "k": "AAAA"}), base_p))
    add("hdr-jku", mk_raw(H(jku="https://evil.test/keys.json"), base_p))
    add("hdr-x5u", mk_raw(H(x5u="https://evil.test/c.pem"), base_p))
    add("crit-shape", mk_raw(H(crit=[]), base_p))
    add("crit-missing", mk_raw(H(crit=["exp"]), base_p))
    add("crit-present", mk_raw(H(crit=["kid"], kid="k1"), base_p))
    # ヘッダに同じ名前が2回（JSON を手で組む）
    dup_h = b64u(b"{\"alg\":\"HS256\",\"alg\":\"none\"}")
    add("hdr-dup", dup_h + "." + seg(base_p) + ".QUJD")

    # --- 時刻
    for nm in ("exp", "nbf", "iat"):
        add("time-string-" + nm, mk_raw(base_h, P(**{nm: "1787530000"})))
        add("time-type-" + nm, mk_raw(base_h, P(**{nm: True})))
        add("time-millis-" + nm, mk_raw(base_h, P(**{nm: (NOW + 600) * 1000})))

    add("exp-missing", mk_raw(base_h, {"iss": "x", "aud": "y", "jti": "z", "sub": "1", "iat": NOW - 60}))
    add("exp-past", mk_raw(base_h, P(exp=NOW - 3600)))
    add("exp-long", mk_raw(base_h, P(iat=NOW - 60, exp=NOW + 86400 * 400)))
    add("exp-longish", mk_raw(base_h, P(iat=NOW - 60, exp=NOW + 86400 * 3)))
    add("nbf-future", mk_raw(base_h, P(nbf=NOW + 3600)))
    add("nbf-after-exp", mk_raw(base_h, P(nbf=NOW + 7200, exp=NOW + 3600)))
    add("iat-future", mk_raw(base_h, P(iat=NOW + 3600)))

    # --- クレームの有無
    add("iss-missing", mk_raw(base_h, {"aud": "y", "jti": "z", "sub": "1", "exp": NOW + 600}))
    add("aud-missing", mk_raw(base_h, {"iss": "x", "jti": "z", "sub": "1", "exp": NOW + 600}))
    add("aud-array", mk_raw(base_h, P(aud=["a", "b"])))
    add("jti-missing", mk_raw(base_h, {"iss": "x", "aud": "y", "sub": "1", "exp": NOW + 600}))
    add("sub-number", mk_raw(base_h, P(sub=42)))
    add("payload-secret", mk_raw(base_h, P(password="hunter2")))
    add("payload-pii", mk_raw(base_h, P(email="a@example.com")))
    dup_p = b64u(b"{\"sub\":\"a\",\"sub\":\"b\"}")
    add("payload-dup", seg(base_h) + "." + dup_p + ".QUJD")
    big_p = b64u(b"{\"n\":123456789012345678901}")
    add("bigint", seg(base_h) + "." + big_p + ".QUJD")

    # --- 符号化
    # 詰めの = が出るのは JSON の長さが3の倍数でないときだけ。詰め物で長さをずらす。
    h_pad = None
    for pad_n in range(0, 6):
        hh = dict(base_h)
        hh["p"] = "x" * pad_n
        cand = base64.urlsafe_b64encode(
            json.dumps(hh, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).decode()
        if cand.endswith("="):
            h_pad = cand
            break
    assert h_pad, "詰めの = が出る形が作れなかった"
    add("b64-padding", h_pad + "." + seg(base_p) + ".QUJD")
    # 標準 base64 の記号（+ /）が出るまで詰め物を伸ばす。
    std_h = None
    for pad_n in range(1, 40):
        raw_h = json.dumps({"alg": "HS256", "typ": "JWT", "x": "ÿþ" * pad_n},
                           separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        cand = base64.b64encode(raw_h).decode().rstrip("=")
        if set(cand) & STDONLY:
            std_h = cand
            break
    assert std_h, "標準base64の記号が出る形が作れなかった"
    add("b64-standard", std_h + "." + seg(base_p) + ".QUJD")
    add("b64-slack", seg(base_h) + "." + seg(base_p) + ".QUJE")   # 4文字=3バイト。末尾に余りが無い形なので別に作る

    # --- 署名
    add("sig-none-nonempty", seg({"alg": "none", "typ": "JWT"}) + "." + seg(base_p) + ".QUJD")
    add("sig-len", seg(base_h) + "." + seg(base_p) + "." + b64u(b"\x00" * 10))
    der = bytes([0x30, 0x44]) + b"\x00" * 66
    add("sig-der", seg(H(alg="ES256")) + "." + seg(base_p) + "." + b64u(der))
    add("sig-empty", seg({"alg": "none", "typ": "JWT"}) + "." + seg(base_p) + ".")
    add("size-big", mk_raw(base_h, P(pad="Z" * 4200)))
    return C


def fix_slack_case(cases):
    """b64-slack は「余ったビットが0でない」形が要る。長さ%4 が 2 か 3 の段を作る。"""
    out = []
    for code, tok in cases:
        if code == "b64-slack":
            h = seg({"alg": "HS256", "typ": "JWT"})
            p = seg({"iss": "x", "aud": "y", "jti": "z", "sub": "1", "exp": NOW + 600})
            # 署名を 3 文字（= 2 バイト）にして、最後の文字の下位2ビットを立てる
            sig = "QUJD"[:3]                       # "QUJ"
            alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            last = alpha.index(sig[-1])
            sig = sig[:-1] + alpha[last | 0x03]
            tok = h + "." + p + "." + sig
        out.append((code, tok))
    return out


# ---------------------------------------------------------------- JS

JS_PARSE = """(items) => items.map(function(it){
  var P, notes, thrown = null;
  try { P = parseJwt(it.t); } catch(e){ return { threw: String(e && e.message || e) }; }
  try { notes = pitfalls(P, it.now).map(function(n){ return n.code; }); }
  catch(e2){ notes = null; thrown = String(e2 && e2.message || e2); }
  return {
    threw: thrown,
    kind: P.kind,
    errors: P.errors,
    headerText: P.headerText === undefined ? null : P.headerText,
    payloadText: P.payloadText === undefined ? null : P.payloadText,
    header: P.header === undefined ? null : P.header,
    payload: P.payload === undefined ? null : P.payload,
    sigLen: P.sigBytes ? P.sigBytes.length : null,
    notes: notes
  };
})"""

JS_VERIFY = """async (items) => {
  var out = [];
  for (var i = 0; i < items.length; i++){
    var it = items[i], r;
    try {
      var P = parseJwt(it.t);
      var spec = ALGS[P.header.alg];
      var k = await importVerifyKey(spec, it.key, false);
      r = await verifySig(spec, k, P.sigBytes, P.parts[0] + "." + P.parts[1]);
    } catch(e){ r = "ERR:" + String(e && e.message || e); }
    out.push(r);
  }
  return out;
}"""

JS_SELF = """() => selfCheck().map(function(r){ return { ok: !!r.ok, t: r.t, detail: r.detail }; })"""

# 段そのものを直接読ませる（分解の手前。壊れた符号化をどう扱うかを測るため）
JS_SEG = """(segs) => segs.map(function(s){
  var r = b64uToBytes(s);
  if (r.err) return { stage:"b64", pad:r.pad, std:r.std, slack:r.slack };
  var u = utf8Decode(r.bytes);
  if (u.err) return { stage:"utf8", pad:r.pad, std:r.std, slack:r.slack };
  return { stage:"ok", text:u.text, pad:r.pad, std:r.std, slack:r.slack,
           roundtrip: bytesToB64u(r.bytes) };
})"""


# ---------------------------------------------------------------- [3] 鍵と署名

def build_sig_cases():
    """(ラベル, トークン, 鍵テキスト, Python の答え) の並び。"""
    cases = []
    hdr_p = {"sub": "1", "exp": NOW + 600}

    # HMAC
    for alg, dig in (("HS256", hashlib.sha256), ("HS384", hashlib.sha384), ("HS512", hashlib.sha512)):
        secret = b"correct horse battery staple"
        t = mk_hs({"alg": alg, "typ": "JWT"}, hdr_p, secret, alg)
        cases.append((alg + "/正しい鍵", t, secret.decode(), True))
        cases.append((alg + "/違う鍵", t, "wrong secret", False))
        h, p, s = t.split(".")
        tampered = h + "." + seg({"sub": "2", "exp": NOW + 600}) + "." + s
        cases.append((alg + "/中身を書き換え", tampered, secret.decode(), False))

    # RSA
    rk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = rk.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    rk2 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem2 = rk2.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    for alg, h in (("RS256", hashes.SHA256()), ("RS384", hashes.SHA384()), ("RS512", hashes.SHA512())):
        head = seg({"alg": alg, "typ": "JWT"})
        pay = seg(hdr_p)
        si = (head + "." + pay).encode()
        sig = rk.sign(si, apad.PKCS1v15(), h)
        t = head + "." + pay + "." + b64u(sig)
        cases.append((alg + "/正しい鍵", t, pub_pem, True))
        cases.append((alg + "/別の鍵", t, pub_pem2, False))
    for alg, h, slen in (("PS256", hashes.SHA256(), 32), ("PS384", hashes.SHA384(), 48)):
        head = seg({"alg": alg, "typ": "JWT"})
        pay = seg(hdr_p)
        si = (head + "." + pay).encode()
        sig = rk.sign(si, apad.PSS(mgf=apad.MGF1(h), salt_length=slen), h)
        t = head + "." + pay + "." + b64u(sig)
        cases.append((alg + "/正しい鍵", t, pub_pem, True))
        cases.append((alg + "/別の鍵", t, pub_pem2, False))

    # 楕円曲線（JOSE は R||S の固定長。DER をそのまま入れた形も混ぜる）
    for alg, curve, h, n in (("ES256", ec.SECP256R1(), hashes.SHA256(), 32),
                             ("ES384", ec.SECP384R1(), hashes.SHA384(), 48)):
        ek = ec.generate_private_key(curve)
        epub = ek.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        head = seg({"alg": alg, "typ": "JWT"})
        pay = seg(hdr_p)
        si = (head + "." + pay).encode()
        der = ek.sign(si, ec.ECDSA(h))
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        r, s = decode_dss_signature(der)
        raw = r.to_bytes(n, "big") + s.to_bytes(n, "big")
        cases.append((alg + "/正しい鍵", head + "." + pay + "." + b64u(raw), epub, True))
        cases.append((alg + "/DERのまま", head + "." + pay + "." + b64u(der), epub, False))
    return cases


# ---------------------------------------------------------------- [2] PyJWT

def gen_claim_case(rnd):
    """exp / nbf / aud / iss をふった HS256 トークン。PyJWT が何と言うかを正解にする。"""
    secret = "s3cr3t-for-claims"
    pl = {"sub": "1"}
    r = rnd.random()
    if r < 0.30:
        pl["exp"] = NOW - rnd.randint(60, 86400)
    elif r < 0.70:
        pl["exp"] = NOW + rnd.randint(60, 86400)
    if rnd.random() < 0.35:
        pl["nbf"] = NOW + rnd.choice([-3600, -60, 60, 3600])
    if rnd.random() < 0.5:
        pl["iat"] = NOW - rnd.randint(1, 3600)
    if rnd.random() < 0.4:
        pl["aud"] = rnd.choice(["api", ["api", "web"]])
    if rnd.random() < 0.4:
        pl["iss"] = "https://auth.example.com"
    return {"t": mk_hs({"alg": "HS256", "typ": "JWT"}, pl, secret.encode()), "secret": secret, "pl": pl}


def pyjwt_verdict(case):
    """PyJWT に判定させる。leeway=0、aud/iss の検査は切っておく（時刻だけを見る）。"""
    try:
        pyjwt.decode(case["t"], case["secret"], algorithms=["HS256"], leeway=0,
                     options={"verify_aud": False, "verify_iss": False})
        return "ok"
    except pyjwt.ExpiredSignatureError:
        return "expired"
    except pyjwt.ImmatureSignatureError:
        return "immature"
    except Exception as e:
        return "other:" + type(e).__name__


# ---------------------------------------------------------------- 壊す

SABOTAGE = [
    ("base64の余りビットの検査を外す",
     "if ((vals[i+1] & 15) !== 0) r.slack = true;",
     "if (false) r.slack = true;"),
    ("base64の長さ検査を外す",
     "if ((vals.length % 4) === 1){ r.err =",
     "if (false){ r.err ="),
    ("UTF-8 の overlong 検査を外す",
     "if (cp < min) return { err:",
     "if (false) return { err:"),
    ("JSON の重複名の記録をやめる",
     "if (Object.prototype.hasOwnProperty.call(seen, \"$\" + k)) dups.push(path ? path + \".\" + k : k);",
     "if (false) dups.push(k);"),
    ("ミリ秒の判定のけたを1つ増やす",
     "function looksMillis(v){ return typeof v === \"number\" && v > 1e12; }",
     "function looksMillis(v){ return typeof v === \"number\" && v > 1e13; }"),
    ("期限切れの判定を逆にする",
     "if (exp * 1000 <= nowMs)",
     "if (exp * 1000 > nowMs)"),
    ("楕円曲線の署名の長さ検査を外す",
     "if (spec.len && P.sigBytes.length !== spec.len){",
     "if (false){"),
    ("秘密らしい名前の検出をやめる",
     "var sec = keyHits(C, SECRET_KEYS);",
     "var sec = [];"),
]


# ---------------------------------------------------------------- 本体

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--page", default=None)
    ap.add_argument("--seed", type=int, default=20260824)
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true")
    args = ap.parse_args()

    page = pathlib.Path(args.page) if args.page else DEFAULT_PAGE
    if not page.exists():
        cand = sorted(pathlib.Path.cwd().glob("**/docs/jwt/index.html"))
        if not cand:
            sys.exit("ページが見つかりません。--page で指定してください")
        page = cand[0]
    text = page.read_text(encoding="utf-8")

    rnd = random.Random(args.seed)
    tokens = [gen_token(rnd) for _ in range(args.n)]
    enc_cases = [gen_encoding_case(rnd) for _ in range(args.n)]
    claim_cases = [gen_claim_case(rnd) for _ in range(args.n)]
    sig_cases = build_sig_cases()
    pits = fix_slack_case(pitfall_cases())

    now_ms = int(time.time() * 1000)

    variants = [("そのまま", text)]
    if args.sabotage:
        for name, old, new in SABOTAGE:
            if old not in text:
                print("  !! 仕込み先が見つからない: %s" % name)
                continue
            variants.append(("壊した: " + name, text.replace(old, new, 1)))

    # ★ crypto.subtle は「安全な文脈」でしか生えない。set_content の about:blank では
    #   使えないので、いったんファイルに書き出して file:// で開く（署名の検証がそこに要る）。
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="jwt-test-")

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
            pg.wait_for_timeout(400)
            print("\n=== %s ===" % label)
            if errs:
                print("  !! JSエラー: %s" % errs[:3])
            ng = 0
            sw = SkipWatch("test_jwt", update=args.update_skip_baseline)

            # ---------------- [1] 分解 vs Python
            got = pg.evaluate(JS_PARSE, [{"t": t, "now": now_ms} for t in tokens])
            bad1, skip1, n1 = [], 0, 0
            for t, g in zip(tokens, got):
                h, p, _s = t.split(".")
                try:
                    ph = json.loads(b64u_dec(h).decode("utf-8"))
                    pp = json.loads(b64u_dec(p).decode("utf-8"))
                except Exception:
                    skip1 += 1
                    continue
                n1 += 1
                if g.get("threw") or g.get("header") is None:
                    bad1.append((t[:50], "読めなかった", g.get("threw") or g.get("errors")))
                    continue
                if canon_json(g["header"]) != canon_json(ph):
                    bad1.append((t[:50], "ヘッダ", g["header"]))
                elif canon_json(g["payload"]) != canon_json(pp):
                    bad1.append((t[:50], "中身", g["payload"]))
            print("[1] 分解した結果 vs Python の base64/UTF-8/JSON: %d 件中 %d 件が一致（対象外 %d）"
                  % (n1, n1 - len(bad1), skip1))
            for b in bad1[:5]:
                print("    ✗ %s … %s: %s" % (b[0], b[1], json.dumps(b[2], ensure_ascii=False)[:160]))
            if bad1:
                ng += 1
            sw.check("[1] 分解", skipped=skip1, total=len(tokens))

            # ---------------- [1b] 段そのもの（壊れた符号化）vs Python
            segs = seg_cases()
            gotb = pg.evaluate(JS_SEG, [s for _lbl, s in segs])
            badb, badslack = [], []
            for (lbl, s), g in zip(segs, gotb):
                want = py_seg(s)
                if g["stage"] != want["stage"]:
                    badb.append((lbl, s, g["stage"], want["stage"]))
                elif want["stage"] == "ok" and g.get("text") != want["text"]:
                    badb.append((lbl, s, repr(g.get("text")), repr(want["text"])))
                # 余ったビットが0でない ＝ 書き戻すと別の文字列になる、で定義できる。
                # Python の base64 は黙って受け取る（拒まない）ので、往復で測る。
                if want["stage"] == "ok":
                    want_slack = (want["canonical"] != s.rstrip("="))
                    if bool(g["slack"]) != want_slack:
                        badslack.append((lbl, s, g["slack"], want_slack))
            print("[1b] 壊れた符号化の扱い vs Python（base64 は validate=True、UTF-8 は strict）: "
                  "%d 件中 %d 件が一致" % (len(segs), len(segs) - len(badb)))
            for b in badb[:8]:
                print("    ✗ %s（%s）: こちら %s / Python なら %s" % (b[0], b[1], b[2], b[3]))
            print("     余ったビットが0でないことの検出（書き戻すと別の文字列になるか）: "
                  "%d 件中 %d 件が一致" % (len(segs), len(segs) - len(badslack)))
            for b in badslack[:8]:
                print("    ✗ %s（%s）: こちら %s / 往復で見ると %s" % (b[0], b[1], b[2], b[3]))
            if badb or badslack:
                ng += 1

            # ---------------- [2] クレームの判定 vs PyJWT
            got2 = pg.evaluate(JS_PARSE, [{"t": c["t"], "now": now_ms} for c in claim_cases])
            bad2, n2 = [], 0
            for c, g in zip(claim_cases, got2):
                want = pyjwt_verdict(c)
                if want.startswith("other:"):
                    continue
                n2 += 1
                codes = set(g["notes"] or [])
                mine_expired = "exp-past" in codes
                mine_immature = "nbf-future" in codes
                if want == "expired" and not mine_expired:
                    bad2.append((c["pl"], "PyJWT は期限切れ、こちらは黙っている"))
                elif want == "immature" and not mine_immature:
                    bad2.append((c["pl"], "PyJWT はまだ使えない、こちらは黙っている"))
                elif want == "ok" and (mine_expired or mine_immature):
                    bad2.append((c["pl"], "PyJWT は通す、こちらは切れている/まだと言う"))
            print("[2] クレームの判定 vs PyJWT（第三者実装）: %d 件中 %d 件が一致"
                  % (n2, n2 - len(bad2)))
            for b in bad2[:5]:
                print("    ✗ %s : %s" % (json.dumps(b[0], ensure_ascii=False), b[1]))
            if bad2:
                ng += 1
            sw.check("[2] クレームの判定", skipped=len(claim_cases) - n2, total=len(claim_cases))

            # ---------------- [3] 署名の検証 vs Python
            got3 = pg.evaluate(JS_VERIFY, [{"t": c[1], "key": c[2]} for c in sig_cases])
            bad3 = []
            for c, g in zip(sig_cases, got3):
                want = c[3]
                if g is not want:
                    bad3.append((c[0], g, want))
            print("[3] 署名の検証（ブラウザの crypto.subtle） vs Python の hmac / cryptography: "
                  "%d 件中 %d 件が一致" % (len(sig_cases), len(sig_cases) - len(bad3)))
            for b in bad3[:8]:
                print("    ✗ %s : こちら %s / Python なら %s" % (b[0], b[1], b[2]))
            if bad3:
                ng += 1

            # ---------------- [4] 規格が拒む形 vs 実装が拒む形
            # ★ 参照が「何も拒まない」だけだと、この検査は空振りする。
            #   先に、明らかに壊れたものを PyJWT が本当に拒むことを確かめる。
            guards = ["", "abc", "a.b", "a.b.c.d", "!!!.???.###", "eyJ9.eyJ9.QUJD"]
            not_rejected = [g for g in guards if not pyjwt_reject(g)]
            if not_rejected:
                print("    !! 参照（PyJWT）が壊れたものを拒んでいない: %s" % not_rejected)
                ng += 1

            got4 = pg.evaluate(JS_PARSE, [{"t": c["t"], "now": now_ms} for c in enc_cases])
            strict_reject = impl_reject = both = named = 0
            bad4 = []
            for c, g in zip(enc_cases, got4):
                parts = c["t"].split(".")
                sr = any(rfc_strict_reject(x) for x in parts)
                ir = pyjwt_reject(c["t"])
                strict_reject += 1 if sr else 0
                impl_reject += 1 if ir else 0
                both += 1 if (sr and ir) else 0
                codes = set(g["notes"] or [])
                said = bool(codes & {"b64-padding", "b64-standard", "b64-slack"}) or bool(g["errors"])
                if sr and not said:
                    bad4.append((c["kind"], c["t"][:60], sorted(codes)))
                if sr and said:
                    named += 1
            print("[4] 規格（RFC 7515）が拒む形 %d 件 / PyJWT が実際に拒んだ %d 件（重なり %d 件）。"
                  % (strict_reject, impl_reject, both))
            print("    → この道具はそのうち %d / %d 件を名指しした（拒まずに名指しするのが仕事）"
                  % (named, strict_reject))
            for b in bad4[:5]:
                print("    ✗ %s : %s → %s" % (b[0], b[1], b[2]))
            if bad4:
                ng += 1

            # ---------------- [5] 落とし穴の名指し
            got5 = pg.evaluate(JS_PARSE, [{"t": t, "now": now_ms} for _c, t in pits])
            bad5 = []
            for (code, tok), g in zip(pits, got5):
                codes = set(g["notes"] or [])
                if code not in codes:
                    bad5.append((code, sorted(codes)[:8]))
            print("[5] 仕込んだ落とし穴の名指し: %d 件中 %d 件"
                  % (len(pits), len(pits) - len(bad5)))
            for b in bad5[:10]:
                print("    ✗ %s が出なかった（出たのは %s）" % (b[0], b[1]))
            if bad5:
                ng += 1

            # ---------------- [6] ページ内の自己検査
            got6 = pg.evaluate(JS_SELF)
            bad6 = [r for r in got6 if not r["ok"]]
            print("[6] ページ内の自己検査: %d 件中 %d 件が ✓" % (len(got6), len(got6) - len(bad6)))
            for b in bad6:
                print("    ✗ %s（%s）" % (b["t"], b["detail"]))
            if bad6:
                ng += 1

            if errs:
                ng += 1
            print("--- %s: %s" % (label, "問題なし" if ng == 0 else ("%d 項目が落ちた" % ng)))
            if label == "そのまま":
                sw_code = sw.report()
                if ng or sw_code:
                    exit_code = 1
            else:
                if ng == 0:
                    print("  !! 壊したのに検査が通った（空振りしている）")
                    exit_code = 1
            pg.close()
        br.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
