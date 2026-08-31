#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「JSON整形・検証」の検証(2026-08-31 昼 新設)。

7本目の道具(2026-08-19 公開)なのに検証スクリプトが1本も無かった。
`test_page_contrast.py`(8/31未明)・`test_diff.py`(8/31朝)に続いて、
**古い道具ほど検証が薄い**という穴を後ろから埋めていく3本目。

★参照の出どころを分ける(1つの参照だけだと、同じ勘違いを2回するので):

  (1) **Python の `json`(標準ライブラリ=第三者の実装)**
      - 受け付ける/拒む が一致するか。★**片方向ではなく iff で見る**
        (「壊れたものを拒む」だけだと、正しいものまで拒む実装が満点を取れてしまう)
      - 読み取った値そのものが一致するか(数は float にそろえて比べる)
      ⚠ `json.loads` は既定で `NaN` / `Infinity` を**受け取る**ので、そのままだと参照にならない。
        `parse_constant` を渡して拒ませてから使う(8/24 に PyJWT で踏んだ「参照が寛容だと
        検査が空振りする」型)。

  (2) **エラー位置(何行目・何文字目)** … 2つの見方を持つ
      (2a) **言い分の中の辻褄**: 道具が返す `index` から行・列を Python で数え直して一致するか
      (2b) **第三者との一致**: Python の `JSONDecodeError` の `lineno` / `colno` と比べる。
           ★ここは**必ず一致する種類のものではない**(どこで諦めるかは実装で変わる)ので、
           一致した数を出すだけにして、合否は (2a) と (3) で取る。

  (3) **正解の分かる壊れ方を手で作り、行と列を名指しできるか**(29件)
      ⚠ この道具は指摘に機械可読な符号(`data-code`)を持たないので、
        **英語版にも当たるように「位置」だけで照合**する。文言の照合は日本語版だけ。

  (4) **統計(キー数・入れ子の深さ等)は Python で独立に書き下した規則**
      … 第三者ではないが、JS と Python が別々に書いて一致するかは見られる。

  (5) **整形結果は Python に読み返させる**(往復) … `json.loads(整形結果) == 値`。
      字下げの幅・1行圧縮も現物の行から測る。
      ⚠ 整形結果の**文字列そのもの**は Python の `json.dumps` と比べない。
        JS は `1.0` を `1` と書き、Python は `1.0` と書くため(規格ではなく書き手の癖の差)。

  (6) **色付けは文字を1つも足し引きしていないか** … `highlight()` の出力からタグを外して
      実体参照を戻すと元に戻るか。別の出どころ(Python の `html.unescape`)で測る。

  (7) **コメント・末尾カンマの除去(`relax`)** … 元の値を正解として、
      **コメントと末尾カンマを足した文**を食わせて同じ値に戻るか。
      ★**文字列の中にコメントらしき字を入れた見本**を必ず混ぜる
        (`relax` が文字列を素通しし損ねると、ここでだけ落ちる)。

`--sabotage` でわざと8種類の傷を入れて、上の検査が本当に落ちるかを見る(空振り確認)。

    python lab/scripts/test_json.py [--n 400] [--sabotage] [--docs <docs>]
    python lab/scripts/test_json.py --page docs/en/json.html   # 英語版にそのまま当たる
"""
import argparse
import html as htmlmod
import json
import pathlib
import random
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
from skipwatch import SkipWatch  # noqa: E402

JA_CHARS = re.compile("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？　]")


def strict_loads(text):
    """参照(1)。`NaN`/`Infinity` を拒ませた `json.loads`。"""
    def nope(word):
        raise ValueError("JSON では使えない定数: %s" % word)
    return json.loads(text, parse_constant=nope)


def numify(v):
    """数を float にそろえる(JS の数は倍精度しか無いので、int/float の差は意味が無い)。"""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list):
        return [numify(x) for x in v]
    if isinstance(v, dict):
        return {k: numify(x) for k, x in v.items()}
    return v


def finite(v):
    """倍精度で表せない大きさ(inf)が混ざっていないか。"""
    if isinstance(v, bool) or v is None:
        return True
    if isinstance(v, float):
        return v == v and v not in (float("inf"), float("-inf"))
    if isinstance(v, list):
        return all(finite(x) for x in v)
    if isinstance(v, dict):
        return all(finite(x) for x in v.values())
    return True


def ref_stats(v):
    """参照(4)。ページ側の `stats()` と同じ規則を Python で書き下したもの。"""
    out = {"keys": 0, "nodes": 0, "arrays": 0, "objects": 0, "maxDepth": 0}

    def walk(x, d):
        out["nodes"] += 1
        if d > out["maxDepth"]:
            out["maxDepth"] = d
        if isinstance(x, list):
            out["arrays"] += 1
            for e in x:
                walk(e, d + 1)
        elif isinstance(x, dict):
            out["objects"] += 1
            out["keys"] += len(x)
            for e in x.values():
                walk(e, d + 1)

    walk(v, 1)
    return out


def line_col(text, index):
    """参照(2a)。道具が返す添字から、行と「何文字目」を数え直す。

    ⚠ **道具が返す `index` は JS の文字列の添字(UTF-16 の単位)**で、絵文字などは2つぶん。
      いっぽう「何文字目」は人が数える単位(符号位置)で言うべきもの。Python の文字列は
      最初から符号位置で数えるので、ここでは**両方の数え方を同時に進めて**突き合わせる。
    ★この食い違いで実バグを1件見つけた(2026-08-31): 道具は `idx - last` と引き算していたので、
      同じ行の手前に絵文字があると「何文字目」が1つずつ多く出て、`^` の位置も同じだけずれていた。
    """
    line, col, k = 1, 1, 0
    for ch in text:
        if k >= index:
            break
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
        k += 2 if ord(ch) > 0xFFFF else 1
    return line, col


# ---- 見本を作る ---------------------------------------------------------------

WORDS = ["name", "path", "free", "tools", "lab", "count", "note", "id", "tags",
         "値", "説明", "a", "b", "zz", "Key", "x-y", "with space", "引用\"符"]
STRINGS = ["", "hello", "日本語のテキスト", "line1\nline2", "tab\there", "\\backslash",
           'quote"inside', "emoji 🍣 here", "slash/inside", " nbsp",
           "// not a comment", "/* nor this */", "trailing comma , here"]


def rand_value(rnd, depth=0):
    kinds = ["str", "int", "float", "bool", "null"]
    if depth < 4:
        kinds += ["obj", "obj", "arr", "arr"]
    k = rnd.choice(kinds)
    if k == "str":
        return rnd.choice(STRINGS)
    if k == "int":
        return rnd.choice([0, -0, 1, -1, 42, 1000000, -987654321])
    if k == "float":
        return rnd.choice([0.5, -1.25, 3.14159, 1e10, -2.5e-7, 1e-300])
    if k == "bool":
        return rnd.choice([True, False])
    if k == "null":
        return None
    if k == "arr":
        return [rand_value(rnd, depth + 1) for _ in range(rnd.randint(0, 4))]
    keys = rnd.sample(WORDS, rnd.randint(0, min(5, len(WORDS))))
    return {k2: rand_value(rnd, depth + 1) for k2 in keys}


CORRUPT = [
    lambda s, r: s[:r.randrange(len(s))] + s[r.randrange(len(s)) + 1:],       # 1文字消す
    lambda s, r: s.replace(",", "", 1),                                        # カンマを1つ消す
    lambda s, r: s.replace('"', "'", 1),                                       # 引用符を替える
    lambda s, r: s.replace("}", ",}", 1),                                      # 末尾カンマ
    lambda s, r: s.replace("]", ",]", 1),
    lambda s, r: s + "}",                                                      # 後ろに足す
    lambda s, r: s.replace(":", "", 1),                                        # コロンを消す
    lambda s, r: s.replace("true", "True", 1),
    lambda s, r: s.replace("null", "undefined", 1),
    lambda s, r: "﻿" + s,                                                 # BOM
]


def build_cases(n, rnd):
    """(見本の文, 期待, 種別) の一覧。期待は None なら「Python に聞く」。"""
    cases = []
    for text in ["{}", "[]", '""', "0", "-0", "null", "true", "false", " \t\n{ } \n",
                 '{"a":1,"a":2}', '{"a":{"b":{"c":[1,[2,[3]]]}}}', '"\\u3042\\ud83c\\udf63"',
                 '{"":""}', "[1e400]", "[-0.0]", '["\\/\\b\\f\\n\\r\\t"]']:
        cases.append((text, "text"))
    for text in ["", "  ", "{", "[", '{"a"}', '{"a":}', "[1,]", "{,}", "'x'", "{a:1}",
                 "[01]", "[1.]", "[1e]", '["\\x41"]', '["unclosed', '"a"\n"b"',
                 "[NaN]", "[Infinity]", '["\t"]', "[1,2]extra"]:
        cases.append((text, "text"))
    while len(cases) < n:
        v = rand_value(rnd)
        text = json.dumps(v, ensure_ascii=rnd.random() < 0.5,
                          indent=rnd.choice([None, 2, 4]))
        if rnd.random() < 0.45:
            f = rnd.choice(CORRUPT)
            try:
                text = f(text, rnd)
            except (ValueError, IndexError):
                continue
        cases.append((text, "text"))
    return cases[:n]


def jsonc(text, rnd):
    """参照(7)。整形済みの文に、コメントと末尾カンマを混ぜる。

    ★行の**末尾**にしか足さない。字下げして書き出した文は、どの行も
      「文字列の途中」で終わらないので、そこに `//…` を足しても値は変わらない。
    """
    lines = text.split("\n")
    out = []
    for i, ln in enumerate(lines):
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        s = ln
        if nxt[:1] in ("}", "]") and s.rstrip()[-1:] not in (",", "{", "[", ""):
            s = s + ","                       # 末尾カンマ
        if rnd.random() < 0.4:
            s = s + (" // メモ" if rnd.random() < 0.5 else " /* メモ */")
        out.append(s)
    return "\n".join(out)


# ---- 参照(3) 正解の分かる壊れ方(位置は手で数えた) ------------------------------
#   (見本, 期待する行, 期待する列, 日本語版の文言に必ず入る字)
BROKEN = [
    ('{"a" 1}',                     1, 6,  "キーの後には :"),
    ('{"a": 1,}',                   1, 9,  "末尾のカンマ"),
    ('[1, 2,]',                     1, 7,  "末尾のカンマ"),
    # ⚠ `{'a': 1}` は「シングルクォートではなくダブルクォート」ではなく
    #   「キーは " で囲む」と言う。キーの検査が値の検査より先に来るため(正しい挙動)。
    ("{'a': 1}",                    1, 2,  "キーは"),
    ("{a: 1}",                      1, 2,  "キーは"),
    ("[1, 2",                       1, 1,  "閉じられていません"),
    ('{"a": 1',                     1, 1,  "閉じられていません"),
    ('{"a": 1, "b": }',             1, 15, "ここに来られない文字"),
    ("[,]",                         1, 2,  "ここに来られない文字"),
    ("",                            1, 1,  "入力が空です"),
    ("   ",                         1, 4,  "入力が空です"),
    ('"abc" "def"',                 1, 7,  "1つの値で終わりますが"),
    ("[1] extra",                   1, 5,  "1つの値で終わりますが"),
    # ⚠ `[01]` は「0 のあとに 1 が来た」ので配列の区切りの話になる(数値としては 0 を読み終えている)
    ("[01]",                        1, 3,  "ここには , か ]"),
    ("[1.]",                        1, 4,  "小数点の後に数字がありません"),
    ("[1e]",                        1, 4,  "指数部に数字がありません"),
    ("[-]",                         1, 2,  "数値になっていません"),
    ('["\\x41"]',                   1, 3,  "使えないエスケープ"),
    ('["\\u12g4"]',                 1, 3,  "16進4桁"),
    ('["abc',                       1, 2,  "閉じられていません"),
    ('["a\nb"]',                    1, 4,  "改行しています"),
    ('["a\\',                       1, 5,  "後に文字がありません"),
    ("[true, tru]",                 1, 8,  "クォートで囲われていない語"),
    ("[undefined]",                 1, 2,  "使えません"),
    ("[NaN]",                       1, 2,  "使えません"),
    ('{\n  "a": 1,\n  "b" 2\n}',    3, 7,  "キーの後には :"),
    # ⚠ `[` が閉じないまま `}` が来た形。「[ が閉じられていません」は入力が尽きたときだけで、
    #   ここは `}` を見た地点で「, か ] が要る」と言う(どちらも正しい。位置は `}` の上)
    ('{\n  "a": [1,\n  2\n}',       4, 1,  "ここには , か ]"),
    ('[\n1,\n2,\n]',                4, 1,  "末尾のカンマ"),
    # ★同じ行の手前に絵文字がある形。JS の添字では2つぶんなので、
    #   引き算で「何文字目」を出していた頃はここが 8 になっていた(2026-08-31 に直した実バグ)
    ('["🍣", x]',                   1, 7,  "クォートで囲われていない語"),
]


CALL = """
({ text, strip, indent, sort }) => {
  const src = strip ? relax(text) : text;
  const r = { relaxed: src };
  let value;
  try { value = parseJSON(src); }
  catch (e) {
    r.ok = false;
    r.message = e.message;
    r.at = e.at;
    return r;
  }
  r.ok = true;
  if (sort) value = sortDeep(value);
  r.value = value;
  r.stats = stats(value);
  const ind = indent === "tab" ? "\\t" : indent;
  r.formatted = JSON.stringify(value, null, ind);
  r.minified = JSON.stringify(value);
  r.highlighted = highlight(r.formatted);
  r.tree = buildTree(value);
  return r;
}
"""

VIA_UI = """
({ text }) => {
  document.getElementById("src").value = text;
  document.getElementById("strip").checked = false;
  document.getElementById("sortkeys").checked = false;
  document.getElementById("fmt").click();
  return {
    status: document.getElementById("status").textContent,
    stats: document.getElementById("stats").textContent,
    out: document.getElementById("out").textContent,
  };
}
"""

TAGS = re.compile(r"<[^>]*>")


SABOTAGE = {
    # 1. 行を数え上げない(2行目以降の位置が全部1行目になる)
    "pos": lambda s: s.replace('if (text[k] === "\\n") { line++; last = k; }',
                               'if (text[k] === "\\n") { last = k; }'),
    # 1b. 「何文字目」を引き算で出す(=直す前の書き方に戻す)。絵文字の手前でだけ1ずれる
    "codepoint": lambda s: s.replace(
        "return { line, col: Array.from(text.slice(last + 1, idx)).length + 1, index: idx };",
        "return { line, col: idx - last, index: idx };"),
    # 2. 先頭に 0 が続く数値(01)を通してしまう
    #    ⚠ 最初は else 側の下限を "1"→"0" にしたが、**0 は手前の枝で拾われるので何も変わらず**、
    #      仕込みが仕込みになっていなかった(素通りではなく、傷が入っていなかった)。
    "leadzero": lambda s: s.replace('if (text[i] === "0") i++;',
                                    'if (text[i] === "0") { while (text[i] >= "0" && text[i] <= "9") i++; }'),
    # 3. オブジェクトの末尾カンマを黙って受け入れる
    "trailing": lambda s: s.replace(
        'if (text[i] === "}") fail("要素の後に , があるのに次の項目がありません（末尾のカンマ）");',
        'if (text[i] === "}") { i++; return o; }'),
    # 4. \\u のあとを16進でなく10進で読む
    "hex": lambda s: s.replace("out += String.fromCharCode(parseInt(hex, 16));",
                               "out += String.fromCharCode(parseInt(hex, 10));"),
    # 5. キーの数を「オブジェクト1つにつき1」と数える
    "keycount": lambda s: s.replace("keys += k.length;", "keys += 1;"),
    # 6. コメントの除去が文字列の中まで食う
    "relaxstr": lambda s: s.replace("""    if (c === '"') {                       // 文字列はそのまま通す""",
                                    """    if (false) {"""),
    # 7. 色付けが文字を落とす(閉じ引用符を捨てる)
    "highlight": lambda s: s.replace("""'<span class="s">' + str + "</span>";""",
                                     """'<span class="s">' + str.slice(0, -1) + "</span>";"""),
}


def check_all(page, cases, rnd, label):
    """1つの版について全部の検査を回し、(件数の内訳, 食い違いの一覧) を返す。"""
    fails = []
    n = dict(accept=0, value=0, pos=0, poscmp=0, stats=0, roundtrip=0,
             highlight=0, relax=0, named=0, nonfinite=0)

    for idx, (text, _kind) in enumerate(cases):
        want_ok, want_val, want_err = True, None, None
        try:
            want_val = strict_loads(text)
        except (ValueError, RecursionError) as e:
            want_ok = False
            want_err = e

        opts = {"text": text, "strip": False,
                "indent": rnd.choice([2, 4, "tab"]), "sort": False}
        got = page.evaluate(CALL, opts)

        # --- 参照(1) 受け付ける/拒む が一致するか(iff) ---
        if got["ok"] != want_ok:
            fails.append("#%d 受け付ける/拒むが違う(道具 %s / Python %s): %r"
                         % (idx, got["ok"], want_ok, text[:60]))
            continue
        n["accept"] += 1

        if not want_ok:
            # --- 参照(2a) 言い分の中の辻褄 ---
            at = got["at"]
            if (at["line"], at["col"]) == line_col(text, at["index"]):
                n["pos"] += 1
            else:
                fails.append("#%d 行・列が添字と合わない %s: %r" % (idx, at, text[:60]))
                continue
            # --- 参照(2b) 第三者との一致(数えるだけ) ---
            if isinstance(want_err, json.JSONDecodeError) and \
               (at["line"], at["col"]) == (want_err.lineno, want_err.colno):
                n["poscmp"] += 1
            continue

        # --- 参照(1) 読み取った値が一致するか ---
        if numify(got["value"]) != numify(want_val):
            fails.append("#%d 読み取った値が違う: %r" % (idx, text[:60]))
            continue
        n["value"] += 1

        # --- 参照(4) 統計 ---
        if got["stats"] == ref_stats(want_val):
            n["stats"] += 1
        else:
            fails.append("#%d 統計が違う 道具 %s / Python %s"
                         % (idx, got["stats"], ref_stats(want_val)))
            continue

        # --- 参照(5) 整形結果を Python に読み返させる(往復) ---
        # ⚠ `1e400` のように**倍精度で表せない大きさ**は JS では Infinity になり、
        #   JSON に Infinity は無いので `JSON.stringify` は `null` と書く(規格どおり)。
        #   Python も `inf` として読むので値としては一致するが、往復はしない。ここだけ外す。
        if not finite(want_val):
            n["nonfinite"] += 1
            continue
        ind = opts["indent"]
        ok = True
        for out, one_line in ((got["formatted"], False), (got["minified"], True)):
            try:
                back = strict_loads(out)
            except ValueError as e:
                fails.append("#%d 整形結果を Python が読めない: %s" % (idx, e))
                ok = False
                break
            if numify(back) != numify(want_val):
                fails.append("#%d 整形で値が変わった: %r" % (idx, text[:60]))
                ok = False
                break
            if one_line and "\n" in out:
                fails.append("#%d 1行圧縮に改行がある" % idx)
                ok = False
                break
        if not ok:
            continue
        # 字下げの幅が指定どおりか(入れ子がある見本だけ)
        unit = "\t" if ind == "tab" else " " * ind
        heads = [re.match(r"[ \t]*", ln).group(0) for ln in got["formatted"].split("\n")[1:]]
        bad = [h for h in heads if h and (h.replace(unit, "") != "")]
        if bad:
            fails.append("#%d 字下げが %r になっていない: %r" % (idx, unit, bad[:3]))
            continue
        n["roundtrip"] += 1

        # --- 参照(6) 色付けが文字を足し引きしていないか ---
        plain = htmlmod.unescape(TAGS.sub("", got["highlighted"]))
        if plain == got["formatted"]:
            n["highlight"] += 1
        else:
            fails.append("#%d 色付けで文字が変わった" % idx)
            continue

        # ツリーの節の数(<li>)が値の総数と合うか
        if got["tree"].count("<li>") != got["stats"]["nodes"]:
            fails.append("#%d ツリーの節の数が合わない" % idx)
            continue

        # --- 参照(7) コメント・末尾カンマを足しても同じ値に戻るか ---
        pretty = json.dumps(want_val, ensure_ascii=False, indent=2)
        loose = jsonc(pretty, rnd)
        got2 = page.evaluate(CALL, {"text": loose, "strip": True, "indent": 2, "sort": False})
        if not got2["ok"]:
            fails.append("#%d コメント入りを読めない: %s" % (idx, got2.get("message")))
            continue
        if numify(got2["value"]) != numify(want_val):
            fails.append("#%d コメントを外したら値が変わった: %r" % (idx, loose[:80]))
            continue
        n["relax"] += 1

    # --- 参照(7の要) 文字列の中のコメントらしき字を、必ず1回は当てる ---
    #   ランダムな見本任せにすると、この形が1件も入らない回がありうる
    #   (「薄い領域」で毎回踏んでいる型なので、ここは手で置く)
    loose = ('{"note": "// not a comment", /* 本物のコメント */\n'
             ' "url": "http://example.com/a/*b*/c", // 行の終わりのコメント\n'
             ' "n": [1, 2,],\n}')
    want = {"note": "// not a comment", "url": "http://example.com/a/*b*/c", "n": [1, 2]}
    got = page.evaluate(CALL, {"text": loose, "strip": True, "indent": 2, "sort": False})
    if not got["ok"]:
        fails.append("文字列の中のコメントらしき字で落ちた: %s" % got.get("message"))
    elif numify(got["value"]) != numify(want):
        fails.append("文字列の中のコメントらしき字を消してしまった: %r" % (got["value"],))
    else:
        n["relax"] += 1

    # --- 参照(3) 正解の分かる壊れ方を名指しできるか ---
    for text, line, col, word in BROKEN:
        got = page.evaluate(CALL, {"text": text, "strip": False, "indent": 2, "sort": False})
        if got["ok"]:
            fails.append("壊れた見本を通した: %r" % text)
            continue
        at = got["at"]
        if (at["line"], at["col"]) != (line, col):
            fails.append("位置が違う %r: 道具 %d行%d文字目 / 期待 %d行%d文字目"
                         % (text, at["line"], at["col"], line, col))
            continue
        if label == "日本語版" and word not in got["message"]:
            fails.append("文言に %r が入っていない: %r → %s" % (word, text, got["message"]))
            continue
        n["named"] += 1

    return n, fails


def check_sort(page):
    """キーを名前順にする処理。小文字の英字だけで見る(大文字の順は照合順序の話なので別扱い)。"""
    text = json.dumps({"pear": 1, "apple": {"zeta": 1, "beta": 2}, "fig": [{"c": 1, "a": 2}]})
    got = page.evaluate(CALL, {"text": text, "strip": False, "indent": 2, "sort": True})
    order = json.loads(got["formatted"], object_pairs_hook=lambda p: [k for k, _ in p])
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--page", help="この HTML を見る(既定は日本語版と英語版の両方)")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=20260831)
    ap.add_argument("--sabotage", action="store_true")
    args = ap.parse_args()

    docs = pathlib.Path(args.docs)
    if args.page:
        pages = [(pathlib.Path(args.page), "指定されたページ")]
    else:
        pages = [(docs / "json" / "index.html", "日本語版"),
                 (docs / "en" / "json.html", "英語版")]
    for p, _ in pages:
        if not p.exists():
            sys.exit("ページが見つかりません: %s" % p)

    cases = build_cases(args.n, random.Random(args.seed))

    import tempfile
    tmp = tempfile.TemporaryDirectory()
    work = pathlib.Path(tmp.name)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        if args.sabotage:
            src = pages[0][0].read_text(encoding="utf-8")
            small = build_cases(80, random.Random(args.seed))
            print("--- わざと壊して、検査が落ちるかを見る ---")
            for name, fn in SABOTAGE.items():
                broken = fn(src)
                if broken == src:
                    browser.close()
                    sys.exit("仕込みが当たっていない(元のコードが変わっていない): %s" % name)
                f = work / ("broken-%s.html" % name)
                f.write_text(broken, encoding="utf-8", newline="\n")
                page.goto(f.as_uri())
                _, fails = check_all(page, small, random.Random(args.seed), "日本語版")
                print("  %-10s → %s" % (name, "検出した(%d件)" % len(fails)
                                        if fails else "★素通りした"))
                if not fails:
                    browser.close()
                    sys.exit("空振り: %s を仕込んでも検査が落ちない" % name)
            browser.close()
            print("\n%d 種すべて検出した。" % len(SABOTAGE))
            return 0

        result, fails, orders = {}, [], {}
        for path, label in pages:
            page.goto(path.resolve().as_uri())
            got, f = check_all(page, cases, random.Random(args.seed), label)
            result[label] = got
            fails += ["%s %s" % (label, x) for x in f]
            orders[label] = check_sort(page)

            ui = page.evaluate(VIA_UI, {"text": '{"b":1,"a":[1,2,{"c":null}]}'})
            if label == "英語版":
                left = JA_CHARS.findall(ui["status"] + ui["stats"] + ui["out"])
                if left:
                    fails.append("英語版の画面に日本語が %d 文字: %s" % (len(left), left[:8]))
                for want in ["valid JSON", "keys", "deepest level"]:
                    if want not in (ui["status"] + ui["stats"]):
                        fails.append("英語版の画面に %r が出ていない" % want)
                ui2 = page.evaluate(VIA_UI, {"text": '{"a" 1}'})
                if "[line 1, column 6]" not in ui2["status"]:
                    fails.append("英語版の位置の書き方が違う: %r" % ui2["status"][:60])
        browser.close()

    print("見本 %d 通り × %d 版" % (len(cases), len(pages)))
    for label, g in result.items():
        print("  %s: 受理/拒否 %d / 値 %d / 位置の辻褄 %d(Python と同じ位置 %d) / "
              "統計 %d / 整形の往復 %d / 色付け %d / コメント除去 %d / 名指し %d"
              % (label, g["accept"], g["value"], g["pos"], g["poscmp"], g["stats"],
                 g["roundtrip"], g["highlight"], g["relax"], g["named"]))
    for label, order in orders.items():
        print("  %s: キーを名前順に → %s" % (label, order))

    # 除外がバグを隠していないか(8/22 に skipwatch を作った動機そのもの)。
    # ★ここでいちばん怖いのは「値・統計・整形の検査が、拒否ばかりになって空になる」こと。
    #   受理/拒否は iff で見ているので普通は先に落ちるが、母数そのものを目に見えるところに出す。
    g = result[pages[0][1]]
    sw = SkipWatch("test_json")
    sw.check("[1] 値の検査に回らなかった見本(拒否されたもの)", len(cases) - g["value"], len(cases))
    sw.check("[5] 整形の往復に回さなかった(倍精度で表せない大きさ)", g["nonfinite"], g["value"])
    skip_code = sw.report()

    if fails:
        print("\n★食い違い %d 件" % len(fails))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("\n食い違い 0")
    return skip_code


if __name__ == "__main__":
    sys.exit(main())
