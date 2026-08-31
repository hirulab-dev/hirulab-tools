#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「単位換算」の検証(2026-08-31 夜 新設)。

9本目の道具(2026-08-21 公開)なのに検証スクリプトが1本も無かった。
`test_page_contrast.py`(8/31未明)・`test_diff.py`(8/31朝)・`test_json.py`(8/31昼)に続いて、
**古い道具ほど検証が薄い**という穴を後ろから埋めていく4本目。

★参照の出どころを3つに分ける(1つだけだと、表と検査が同じ勘違いをする)。

  (1) **pint(第三者のPythonライブラリ)** … 尺貫法**以外**の90単位すべて。
      道具の `convert()` の結果を pint の換算と突き合わせる。
      ★**表の数字を写した参照は作らない**。写すと、表が間違っていても検査が同じ数字で通る
      (8/27 に base64 のマジックナンバーで避けたのと同じ型)。

  (2) **1891年の度量衡法の定義から、Python の `Fraction` で組み立てた有理数** … 尺貫法19単位。
      pint は尺貫法を知らないので、ここだけは定義から導く。★**表の float を写すのではなく、
      「1尺＝10/33m」「1間＝6尺」「1坪＝1間四方」…と定義を書き下してから掛け算する**。
      だから表の値が定義とずれていれば、ここで落ちる。

  (3) **「定義」と名乗っている行は本当に定義値か** … `d:true` の単位は (1)(2) の参照と
      **倍精度で1ビットも違わない**ことを要求する。`d:false`(畳・マッハ・月・年)には要求しない。
      ★この道具の売りは「定義値か近似値かを1件ずつ出す」ことなので、**そのラベル自体を測る**。

  ほかに、参照を使わずに道具の中の辻褄を見るもの:
  (4) 往復(A→B→A が元に戻るか)を全ペアで
  (5) `parseNum`(分数・全角・桁区切り)を Python で独立に書き下した規則と照合
  (6) `fmt` の表示を**読み戻して**、有効数字ぶんだけ丸めた真値と一致するか
      (桁区切りのカンマと `×10ⁿ` の上付き数字をほどく = 表示の可逆性も同時に見る)
  (7) 画面のバッジ(定義/近似)が `d` と一致するか(DOM を実際に読む)

`--sabotage` でわざと7種類の傷を入れて、上の検査が本当に落ちるかを見る(空振り確認)。

    python lab/scripts/test_unit.py [--n 300] [--sabotage] [--docs <docs>]
    python lab/scripts/test_unit.py --page docs/en/unit.html   # 英語版にそのまま当たる
"""
import argparse
import math
import pathlib
import random
import re
import sys
import tempfile
from fractions import Fraction as F

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from skipwatch import SkipWatch  # noqa: E402

import pint  # noqa: E402

UREG = pint.UnitRegistry()

# ---------------------------------------------------------------------------
# 参照(1)(2)。**カテゴリの id と行の番号**で引く(記号は日英で違うため)。
#   ("pint", 名前)      … pint に基準単位まで換算させる
#   ("exact", Fraction) … 定義から組み立てた有理数(基準単位いくつぶんか)
#   ("approx", 値 or None) … 定義値ではない行。倍精度一致は要求しない
#   ("skip",)           … ここでは測らない(温度・勾配・燃費は別枠)
#
# ★2つの参照は**役目が違う**(最初は pint だけで済むと思って書いて、間違えた):
#   - pint は**第三者**だが、換算を何段も掛けるので**最後の1ビットがずれる**
#     (ft を 0.30479999999999996 と出す)。だから許容つきでしか使えない。
#   - 「定義」と名乗る行が本当に定義値かは、**有理数**でしか測れない。
#   → `EXACT` を別に持ち、d:true の行はこちらと**1ビットも違わない**ことを要求する。
#     pint は同じ行に対して「別の出どころから見ても合っているか」を許容つきで見る。
# ---------------------------------------------------------------------------

SHAKU = F(10, 33)                 # 1891年の度量衡法: 1尺 = 10/33 m
KEN = 6 * SHAKU                   # 1間 = 6尺
KAN = F(15, 4)                    # 1貫 = 3.75 kg
MONME = KAN / 1000                # 1匁 = 1/1000 貫
TSUBO = KEN * KEN                 # 1坪 = 1間四方
SHO = F(2401, 1331)               # 1升 = 1立方メートルの 2401/1331000 = 2401/1331 L

REF = {
    "length": [                                     # 基準 m
        ("pint", "millimeter"), ("pint", "centimeter"), ("pint", "meter"),
        ("pint", "kilometer"), ("pint", "micrometer"), ("pint", "nanometer"),
        ("pint", "inch"), ("pint", "foot"), ("pint", "yard"), ("pint", "mile"),
        ("pint", "nautical_mile"),
        ("exact", SHAKU / 10),        # 寸
        ("exact", SHAKU),             # 尺
        ("exact", KEN),               # 間
        ("exact", 10 * SHAKU),        # 丈
        ("exact", 360 * SHAKU),       # 町 = 60間 = 360尺
        ("exact", 36 * 360 * SHAKU),  # 里 = 36町
        ("pint", "astronomical_unit"), ("pint", "light_year"),
    ],
    "mass": [                                       # 基準 kg
        ("pint", "milligram"), ("pint", "gram"), ("pint", "kilogram"),
        ("pint", "metric_ton"), ("pint", "ounce"), ("pint", "pound"),
        ("pint", "stone"), ("pint", "carat"),
        ("exact", MONME), ("exact", KAN), ("exact", 160 * MONME),   # 匁 / 貫 / 斤
    ],
    "area": [                                       # 基準 m²
        ("pint", "centimeter**2"), ("pint", "meter**2"), ("pint", "are"),
        ("pint", "hectare"), ("pint", "kilometer**2"), ("pint", "foot**2"),
        ("pint", "acre"), ("pint", "mile**2"),
        ("exact", TSUBO),               # 坪
        ("approx", 1.62),               # 畳(地域で違う。既定は表示基準)
        ("exact", 30 * TSUBO),          # 畝
        ("exact", 300 * TSUBO),         # 反
        ("exact", 3000 * TSUBO),        # 町歩
    ],
    "volume": [                                     # 基準 L
        ("pint", "milliliter"), ("pint", "liter"), ("pint", "meter**3"),
        ("pint", "centimeter**3"),
        ("exact", F(1, 200)),           # 小さじ 5mL
        ("exact", F(3, 200)),           # 大さじ 15mL
        ("exact", F(1, 5)),             # 計量カップ(日本) 200mL
        ("pint", "cup"), ("pint", "fluid_ounce"), ("pint", "gallon"),
        ("pint", "imperial_gallon"), ("pint", "oil_barrel"),
        ("exact", SHO / 100),           # 勺
        ("exact", SHO / 10),            # 合
        ("exact", SHO),                 # 升
        ("exact", 10 * SHO),            # 斗
        ("exact", 100 * SHO),           # 石
    ],
    "temp": [("skip",)] * 4,
    "speed": [                                      # 基準 m/s
        ("pint", "meter/second"), ("pint", "kilometer/hour"),
        ("pint", "mile/hour"), ("pint", "foot/second"), ("pint", "knot"),
        ("approx", 340.29),             # マッハ(気温で変わる)
    ],
    "time": [                                       # 基準 s
        ("pint", "millisecond"), ("pint", "second"), ("pint", "minute"),
        ("pint", "hour"), ("pint", "day"), ("pint", "week"),
        ("approx", 2629746.0),          # 1か月(グレゴリオ暦の平均 30.436875日)
        ("approx", 31556952.0),         # 1年(グレゴリオ暦の平均 365.2425日)
    ],
    "data": [                                       # 基準 B
        ("pint", "bit"), ("pint", "byte"), ("pint", "kilobyte"),
        ("pint", "megabyte"), ("pint", "gigabyte"), ("pint", "terabyte"),
        ("pint", "kibibyte"), ("pint", "mebibyte"), ("pint", "gibibyte"),
        ("pint", "tebibyte"),
    ],
    "pressure": [                                   # 基準 Pa
        ("pint", "pascal"), ("pint", "hectopascal"), ("pint", "kilopascal"),
        ("pint", "megapascal"), ("pint", "bar"), ("pint", "atmosphere"),
        ("pint", "mmHg"), ("pint", "psi"),
    ],
    "energy": [                                     # 基準 J
        ("pint", "joule"), ("pint", "kilojoule"), ("pint", "calorie"),
        ("pint", "kilocalorie"), ("pint", "watt_hour"), ("pint", "kilowatt_hour"),
        ("pint", "Btu"), ("pint", "electron_volt"),
    ],
    "angle": [                                      # 基準 °
        ("pint", "degree"), ("pint", "radian"), ("pint", "arcminute"),
        ("pint", "arcsecond"), ("pint", "gradian"), ("pint", "turn"),
        ("skip",),                      # 勾配(％)は比例しないので別枠
    ],
    "fuel": [("skip",)] * 4,
}

# 基準単位(pint 側の書き方)。カテゴリの base をここに写さず、pint の語で持つ
BASE = {
    "length": "meter", "mass": "kilogram", "area": "meter**2", "volume": "liter",
    "speed": "meter/second", "time": "second", "data": "byte",
    "pressure": "pascal", "energy": "joule", "angle": "degree",
}

# 「近似」と名乗ってよい行(それ以外で d:false なら、ラベルが緩すぎるとみなす)
APPROX_OK = {("area", 9), ("speed", 5), ("time", 6), ("time", 7)}

# 「定義」でよいが**有理数では書けない**行(定義そのものに π が入る)。
# ここは pint との一致(許容つき)だけで測る。
IRRATIONAL_OK = {("angle", 1)}

# ---------------------------------------------------------------------------
# ★定義から組み立てた有理数。**表の float を写したのではなく、条約・法令の言葉から掛け算する。**
#   国際ヤード・ポンド協定(1959): 1 yd = 0.9144 m ちょうど / 1 lb = 0.45359237 kg ちょうど
#   度量衡法(1891): 1尺 = 10/33 m / 1貫 = 3.75 kg / 1升 = 2401/1331000 m³
# ---------------------------------------------------------------------------
YD = F(9144, 10000)              # 1ヤード
FT = YD / 3
IN = FT / 12
LB = F(45359237, 100000000)      # 1ポンド
OZ = LB / 16
GAL_US = 231 * IN ** 3 * 1000    # 1米ガロン = 231立方インチ(L)
GAL_UK = F(454609, 100000)       # 1英ガロン = 4.54609 L ちょうど
ATM = 101325                     # 標準大気圧 Pa

EXACT = {
    "length": {0: F(1, 1000), 1: F(1, 100), 2: F(1), 3: F(1000),
               4: F(1, 10 ** 6), 5: F(1, 10 ** 9),
               6: IN, 7: FT, 8: YD, 9: 1760 * YD, 10: F(1852),
               11: SHAKU / 10, 12: SHAKU, 13: KEN, 14: 10 * SHAKU,
               15: 360 * SHAKU, 16: 36 * 360 * SHAKU,
               17: F(149597870700), 18: F(9460730472580800)},
    "mass": {0: F(1, 10 ** 6), 1: F(1, 1000), 2: F(1), 3: F(1000),
             4: OZ, 5: LB, 6: 14 * LB, 7: F(2, 10000),
             8: MONME, 9: KAN, 10: 160 * MONME},
    "area": {0: F(1, 10000), 1: F(1), 2: F(100), 3: F(10000), 4: F(10 ** 6),
             5: FT ** 2, 6: 4840 * YD ** 2, 7: (1760 * YD) ** 2,
             8: TSUBO, 10: 30 * TSUBO, 11: 300 * TSUBO, 12: 3000 * TSUBO},
    "volume": {0: F(1, 1000), 1: F(1), 2: F(1000), 3: F(1, 1000),
               4: F(1, 200), 5: F(3, 200), 6: F(1, 5),
               7: GAL_US / 16, 8: GAL_US / 128, 9: GAL_US, 10: GAL_UK,
               11: 42 * GAL_US,
               12: SHO / 100, 13: SHO / 10, 14: SHO, 15: 10 * SHO, 16: 100 * SHO},
    "speed": {0: F(1), 1: F(1, 1) * 1000 / 3600, 2: 1760 * YD / 3600,
              3: FT, 4: F(1852, 3600)},
    "time": {0: F(1, 1000), 1: F(1), 2: F(60), 3: F(3600),
             4: F(86400), 5: F(604800)},
    "data": {0: F(1, 8), 1: F(1), 2: F(1000), 3: F(10 ** 6), 4: F(10 ** 9),
             5: F(10 ** 12), 6: F(1024), 7: F(1024 ** 2), 8: F(1024 ** 3),
             9: F(1024 ** 4)},
    "pressure": {0: F(1), 1: F(100), 2: F(1000), 3: F(10 ** 6), 4: F(100000),
                 5: F(ATM), 6: F(ATM, 760), 7: LB * F(980665, 100000) / IN ** 2},
    "energy": {0: F(1), 1: F(1000), 2: F(4184, 1000), 3: F(4184),
               4: F(3600), 5: F(36, 10) * 10 ** 6,
               6: F(105505585262, 100000000),      # BTU(IT)
               7: F(1602176634, 10 ** 28)},        # 電子ボルト(2019年のSI改定で定義値)
    "angle": {0: F(1), 2: F(1, 60), 3: F(1, 3600), 4: F(9, 10), 5: F(360)},
}

# ★pint と食い違うことが分かっている行(**どちらも実在する別の定義**。道具は右側)
#   ここは「差が出ること自体」を検査する(8/21 の croniter・8/24 の PyJWT と同じ扱い)。
PINT_DIFFERS = {
    ("area", 6): "acre — pint は米国測量フィート系の survey acre、道具は国際エーカー(4840平方ヤード)",
    ("pressure", 6): "mmHg — pint は水銀柱の密度から、道具は Torr(標準大気圧の1/760)",
    ("energy", 6): "BTU — 定義が何種類もある。道具は国際蒸気表(IT)の 1055.05585262 J",
}


def ref_base_per_one(cat_id, i):
    """基準単位に直したときの「1単位ぶん」の値を参照から出す。無ければ None。"""
    kind = REF[cat_id][i]
    if kind[0] == "pint":
        return float(UREG.Quantity(1, kind[1]).to(BASE[cat_id]).magnitude)
    if kind[0] == "exact":
        return float(kind[1])
    if kind[0] == "approx":
        return kind[1]
    return None


# ---------------------------------------------------------------------------
# 参照(5)。parseNum を Python で独立に書き下したもの(JS を読み写したのではなく、
# 「全角を半角に / 桁区切りのカンマを落とす / 帯分数 / 分数 / 10進」の規則から書く)
# ---------------------------------------------------------------------------
Z2H = {ord(c): ord("0") + i for i, c in enumerate("０１２３４５６７８９")}
Z2H.update({ord("．"): ord("."), ord("。"): ord(".")})
Z2H.update({ord(c): ord("-") for c in "－ー−―‐"})
Z2H.update({ord("／"): ord("/"), ord("，"): ord(","), ord("、"): ord(",")})


def py_parse_num(src):
    if src is None:
        return None
    s = str(src).translate(Z2H)
    s = re.sub(r"[\s　]+", " ", s).strip()
    if s == "":
        return None
    s = re.sub(r"(\d),(?=\d{3}(\D|$))", r"\1", s)
    m = re.fullmatch(r"(-?)(\d+) (\d+)/(\d+)", s)
    if m:
        den = int(m.group(4))
        if den == 0:
            return None
        v = int(m.group(2)) + int(m.group(3)) / den
        return -v if m.group(1) == "-" else v
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", s)
    if m:
        if float(m.group(2)) == 0:
            return None
        return float(m.group(1)) / float(m.group(2))
    if re.fullmatch(r"-?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?", s):
        return float(s)
    return None


SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def read_back(text):
    """参照(6)。画面の表示を数に読み戻す(桁区切りと ×10ⁿ をほどく)。"""
    if text in ("—", "∞", "-∞"):
        return None
    t = text.replace(",", "")
    if "×10" in t:
        mant, exp = t.split("×10")
        neg = exp.startswith("⁻")
        exp = exp.lstrip("⁻")
        digits = "".join(str(SUP.index(c)) for c in exp)
        return float(mant) * (10 ** (-int(digits) if neg else int(digits)))
    return float(t)


def sig_round(v, sig):
    if v == 0 or sig == 0:
        return v
    return float("%.*e" % (sig - 1, v))


# ---------------------------------------------------------------------------
# ページを叩くコード
# ---------------------------------------------------------------------------
DUMP = """
() => C.map(c => ({
  id: c.id,
  base: c.base,
  units: c.units.map(u => ({ s: u.s, d: !!u.d, jp: !!u.jp, tat: !!u.tat,
                             base1: toBase(u, 1), fn: !!u.to }))
}))
"""

CONVERT = """
(job) => {
  const c = C.find(x => x.id === job.cat);
  const a = c.units[job.i], b = c.units[job.j];
  return convert(a, b, job.x);
}
"""

PARSE = """(s) => { const r = parseNum(s); return r.ok ? r.v : null; }"""
FMT = """(job) => fmt(job.v, job.sig)"""

BADGES = """
(cat) => {
  const btns = Array.from(document.querySelectorAll('.cats button'));
  const idx = C.findIndex(c => c.id === cat);
  btns[idx].click();
  document.getElementById('value').value = '1';
  document.getElementById('value').dispatchEvent(new Event('input'));
  return Array.from(document.querySelectorAll('#out tr')).map(tr => {
    const b = tr.querySelector('.badge');
    return b ? (b.className.indexOf('def') >= 0 ? 'def' : 'apx') : '?';
  });
}
"""

SABOTAGE = {
    # 1. インチの倍率をわずかにずらす → pint と食い違うはず
    "inch": lambda s: s.replace("{s:'in', nm:", "{s:'in', f_bogus:1, nm:")
                       .replace("f:0.0254,", "f:0.02540001,"),
    # 2. 尺を「10/33」でなく丸めた値にする → 定義から組んだ有理数と食い違うはず
    "shaku": lambda s: s.replace("f:10/33,", "f:0.30303,"),
    # 3. 基準から戻すときに掛けてしまう → 往復と参照の両方が落ちるはず
    "fromBase": lambda s: s.replace("return u.from ? u.from(b) : b / u.f;",
                                    "return u.from ? u.from(b) : b * u.f;"),
    # 4. 摂氏の絶対零度を1つずらす → 温度の参照が落ちるはず
    "kelvin": lambda s: s.replace("to:x=>x+273.15, from:b=>b-273.15",
                                  "to:x=>x+273.16, from:b=>b-273.16"),
    # 5. 桁区切りのカンマを落とさない → parseNum が落ちるはず
    "comma": lambda s: s.replace("s = s.replace(/(\\d),(?=\\d{3}(\\D|$))/g, '$1');", ""),
    # 6. 帯分数(5 3/8)の整数部と分数部を引いてしまう
    "mixed": lambda s: s.replace("const v = (+m[2]) + (+m[3]) / den;",
                                 "const v = (+m[2]) - (+m[3]) / den;"),
    # 7. 有効数字を1桁多く出す → 読み戻した値が丸めた真値と食い違うはず
    "sig": lambda s: s.replace("let s = v.toPrecision(sig);",
                               "let s = v.toPrecision(sig + 1);"),
}


def close(a, b, tol=1e-12):
    if a == b:
        return True
    if a is None or b is None:
        return False
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    scale = max(abs(a), abs(b), 1e-300)
    return abs(a - b) <= tol * scale


def run_checks(page, n, rnd):
    fails = []
    cnt = dict(ref=0, exact=0, differs=0, trip=0, parse=0, fmt=0, badge=0,
               temp=0, fuel=0, grade=0)
    skipped = dict(ref=0)

    cats = page.evaluate(DUMP)
    by_id = {c["id"]: c for c in cats}

    # --- (1)(2)(3) 1単位ぶんの値を参照と突き合わせる ---
    for c in cats:
        table = REF.get(c["id"])
        if table is None or len(table) != len(c["units"]):
            fails.append("カテゴリ %s の行数が参照と違う(道具 %d / 参照 %s)"
                         % (c["id"], len(c["units"]),
                            len(table) if table else "無し"))
            continue
        for i, u in enumerate(c["units"]):
            got = u["base1"]
            kind = REF[c["id"]][i]

            # --- 参照(1) pint(第三者)。何段も掛けるので許容つきで見る ---
            want = ref_base_per_one(c["id"], i)
            if want is None:
                skipped["ref"] += 1
            elif (c["id"], i) in PINT_DIFFERS:
                # ★差が出ること自体を検査する(合っていたら、こちらの理解が古い)
                cnt["differs"] += 1
                if close(got, want, 1e-9):
                    fails.append("[想定差] %s[%d] %s は pint と違うはずなのに一致した(%s)"
                                 % (c["id"], i, u["s"], PINT_DIFFERS[(c["id"], i)]))
            else:
                cnt["ref"] += 1
                if not close(got, want, 1e-12):
                    fails.append("[参照] %s[%d] %s: 道具 %r / 参照 %r"
                                 % (c["id"], i, u["s"], got, want))

            # --- 参照(2)(3) 定義から組み立てた有理数。d:true は1ビットも違わないこと ---
            ex = EXACT.get(c["id"], {}).get(i)
            if ex is not None:
                cnt["exact"] += 1
                if got != float(ex):
                    fails.append("[定義] %s[%d] %s: 道具 %r / 定義から組んだ値 %r (%s)"
                                 % (c["id"], i, u["s"], got, float(ex), ex))
            elif u["d"] and kind[0] != "skip" and (c["id"], i) not in IRRATIONAL_OK:
                fails.append("[定義] %s[%d] %s は「定義」と出しているのに、"
                             "定義から組み立てた参照が無い" % (c["id"], i, u["s"]))

            if not u["d"] and (c["id"], i) not in APPROX_OK and kind[0] != "skip":
                fails.append("[近似] %s[%d] %s が「近似」になっているが、"
                             "近似でよい行の一覧に無い" % (c["id"], i, u["s"]))

    # --- (4) 往復。全カテゴリの全ペア ---
    for c in cats:
        m = len(c["units"])
        for i in range(m):
            for j in range(m):
                x = rnd.choice([1.0, 2.5, 0.125, 1234.5, 0.0007])
                b = page.evaluate(CONVERT, {"cat": c["id"], "i": i, "j": j, "x": x})
                if b is None or not math.isfinite(b) or b == 0:
                    continue
                back = page.evaluate(CONVERT, {"cat": c["id"], "i": j, "j": i, "x": b})
                cnt["trip"] += 1
                if not close(back, x, 1e-9):
                    fails.append("[往復] %s %s→%s→%s: %r が %r で戻った"
                                 % (c["id"], c["units"][i]["s"], c["units"][j]["s"],
                                    c["units"][i]["s"], x, back))

    # --- 温度は pint に直接 ---
    TEMP = ["degC", "degF", "kelvin", "degR"]
    for i in range(4):
        for j in range(4):
            for x in (-40.0, 0.0, 36.6, 100.0, 451.0):
                got = page.evaluate(CONVERT, {"cat": "temp", "i": i, "j": j, "x": x})
                want = UREG.Quantity(x, TEMP[i]).to(TEMP[j]).magnitude
                cnt["temp"] += 1
                if not close(got, want, 1e-10):
                    fails.append("[温度] %s→%s x=%r: 道具 %r / pint %r"
                                 % (TEMP[i], TEMP[j], x, got, want))

    # --- 燃費。mile と gallon の換算は pint から取り、式は独立に書き下す ---
    MI = float(UREG.Quantity(1, "mile").to("kilometer").magnitude)
    GU = float(UREG.Quantity(1, "gallon").to("liter").magnitude)
    GI = float(UREG.Quantity(1, "imperial_gallon").to("liter").magnitude)
    def fuel_base(i, x):            # L/100km に直す
        return [lambda v: 100 / v,
                lambda v: v,
                lambda v: 100 * GU / (v * MI),
                lambda v: 100 * GI / (v * MI)][i](x)
    for i in range(4):
        for x in (5.0, 12.0, 20.0, 45.0):
            got = page.evaluate(CONVERT, {"cat": "fuel", "i": i, "j": 1, "x": x})
            want = fuel_base(i, x)
            cnt["fuel"] += 1
            if not close(got, want, 1e-10):
                fails.append("[燃費] 行%d x=%r: 道具 %r / 参照 %r" % (i, x, got, want))

    # --- 勾配(％)。atan の式を独立に書く ---
    for x in (0.0, 1.0, 8.0, 100.0, 1000.0):
        got = page.evaluate(CONVERT, {"cat": "angle", "i": 6, "j": 0, "x": x})
        want = math.degrees(math.atan(x / 100))
        cnt["grade"] += 1
        if not close(got, want, 1e-12):
            fails.append("[勾配] %r%%: 道具 %r / 参照 %r" % (x, got, want))
    for deg in (95.0, -120.0):       # 坂として表せない角度は NaN のはず
        got = page.evaluate(CONVERT, {"cat": "angle", "i": 0, "j": 6, "x": deg})
        cnt["grade"] += 1
        if got is not None and math.isfinite(got):
            fails.append("[勾配] %r° は坂にできないはずなのに %r が出た" % (deg, got))

    # --- (5) parseNum ---
    samples = ["1", "1.5", "-2.25", ".5", "3/8", "-3/8", "5 3/8", "1,200", "12,345,678",
               "１２３", "１，２３４", "５ ３／８", "1e3", "2.5E-3", "  7  ", "1/0",
               "5 3/0", "abc", "", "1,20", "1,2345", "3/8/2", "１.５", "0.1"]
    for _ in range(n):
        a = rnd.randint(-9999, 9999)
        b = rnd.randint(1, 999)
        samples.append(rnd.choice(["%d" % a, "%d/%d" % (a, b), "%d %d/%d" % (abs(a), b % 7, 8),
                                   "{:,}".format(a), "%.4f" % (a / 7)]))
    for s in samples:
        got = page.evaluate(PARSE, s)
        want = py_parse_num(s)
        cnt["parse"] += 1
        if (got is None) != (want is None) or (want is not None and not close(got, want, 1e-15)):
            fails.append("[入力] %r: 道具 %r / 参照 %r" % (s, got, want))

    # --- (6) fmt の表示を読み戻す ---
    for _ in range(n):
        v = rnd.choice([rnd.uniform(-1e6, 1e6), rnd.uniform(-1, 1),
                        rnd.uniform(1e-9, 1e-4), rnd.uniform(1e12, 1e18)])
        sig = rnd.choice([4, 6, 8, 12])
        shown = page.evaluate(FMT, {"v": v, "sig": sig})
        cnt["fmt"] += 1
        back = read_back(shown)
        if back is None:
            fails.append("[表示] %r(有効数字%d) が読み戻せない: %r" % (v, sig, shown))
            continue
        want = sig_round(v, sig)
        if not close(back, want, 1e-12):
            fails.append("[表示] %r(有効数字%d): 表示 %r → %r / 参照 %r"
                         % (v, sig, shown, back, want))

    # --- (7) 画面のバッジが d と一致するか ---
    for c in cats:
        got = page.evaluate(BADGES, c["id"])
        want = ["def" if u["d"] else "apx" for u in c["units"]]
        cnt["badge"] += len(want)
        if got != want:
            fails.append("[バッジ] %s: 画面 %r / 定義 %r" % (c["id"], got, want))

    return cnt, skipped, fails, by_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--docs", default=str(pathlib.Path.home() / "hirulab-tools" / "docs"))
    ap.add_argument("--page", default=None, help="当てるページ(既定は docs/unit/index.html)")
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--seed", type=int, default=20260831)
    a = ap.parse_args()

    docs = pathlib.Path(a.docs)
    path = pathlib.Path(a.page) if a.page else docs / "unit" / "index.html"
    src = path.read_text(encoding="utf-8")
    print("見るページ: %s" % path)

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        page = br.new_page()

        if a.sabotage:
            print("\n--- 空振り確認(わざと傷を入れて、検査が落ちるか) ---")
            caught = 0
            for name, hurt in SABOTAGE.items():
                bad = hurt(src)
                if bad == src:
                    print("  × %-9s 仕込みが入っていない(差し替え元が見つからない)" % name)
                    continue
                with tempfile.TemporaryDirectory() as d:
                    f = pathlib.Path(d) / "unit.html"
                    f.write_text(bad, encoding="utf-8")
                    page.goto(f.as_uri())
                    _, _, fails, _ = run_checks(page, 40, random.Random(a.seed))
                if fails:
                    print("  ✅ %-9s 検出(%d件): %s" % (name, len(fails), fails[0][:88]))
                    caught += 1
                else:
                    print("  × %-9s **素通り**" % name)
            print("\n仕込み %d 種のうち検出 %d 種" % (len(SABOTAGE), caught))
            br.close()
            return 0 if caught == len(SABOTAGE) else 1

        page.goto(path.resolve().as_uri())
        cnt, skipped, fails, by_id = run_checks(page, a.n, random.Random(a.seed))
        br.close()

    print("\n--- 突き合わせた件数 ---")
    print("  参照(1) pint(第三者)と一致      : %d 件" % cnt["ref"])
    print("  参照(2) 定義から組んだ有理数と**1ビットも違わない**: %d 件" % cnt["exact"])
    print("  ★pint と食い違うことを確かめた行: %d 件" % cnt["differs"])
    print("  往復(A→B→A)                    : %d 件" % cnt["trip"])
    print("  温度(pint)                      : %d 件" % cnt["temp"])
    print("  燃費(mile/gallon は pint、式は独立): %d 件" % cnt["fuel"])
    print("  勾配(atan を独立に)             : %d 件" % cnt["grade"])
    print("  入力の読み取り(Python で独立に) : %d 件" % cnt["parse"])
    print("  表示を読み戻して丸めた真値と照合: %d 件" % cnt["fmt"])
    print("  画面のバッジと d の一致         : %d 件" % cnt["badge"])

    sw = SkipWatch("test_unit")
    total_units = sum(len(c["units"]) for c in by_id.values())
    sw.check("参照が無くて突き合わせなかった単位(温度・勾配・燃費)", skipped["ref"], total_units)
    skip_code = sw.report()

    if fails:
        print("\n★食い違い %d 件" % len(fails))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("\n✅ 食い違い 0")
    return skip_code


if __name__ == "__main__":
    sys.exit(main())
