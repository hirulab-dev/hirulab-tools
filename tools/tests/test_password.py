#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「パスワード生成・強度診断」の検証(2026-08-24)。

この道具の主張は3つに分かれる。それぞれ別の出どころで確かめる。

1. **エントロピー計算が手計算(log2)と一致するか** → Python の math.log2 に当てる。
2. **拒否サンプリングは本当に偏らず、素朴な剰余法は本当に偏るか** → これが本題。
   ページの `rejectionIndices` / `naiveModIndices` を実際のブラウザで
   `crypto.getRandomValues` を使って何万回も引かせ、その実測値からχ²統計量を計算する。
   χ²の**p値の近似式(Wilson-Hilferty)自体**も、SciPy の正確な値と突き合わせる
   (近似の精度を主張するなら、近似の精度そのものを検証しないと意味がない)。
3. **落とし穴の名指しができるか** → 正解の分かっている約20種類のパスワードを仕込み、
   `detectPitfalls` が期待した `code` を返すかを照合する。

**あわせて、開発中に実際に踏んだバグの回帰検査も入れてある**(下の [4])。
「選んだ種類を必ず1文字以上含める」機能は、抜けている文字種を埋めるために
ランダムな位置を上書きする実装だったが、**その位置が別の文字種の唯一の出現だった場合、
そちらを新たに欠落させてしまっていた**。2000回に数回の頻度で起きていた実バグで、
このスクリプトを書く過程で見つけて直した。

わざと壊して検査が空振りしていないかを見る `--sabotage` つき。

使い方:
  python lab/scripts/test_password.py [--n 40000] [--page docs/password/index.html]
  python lab/scripts/test_password.py --sabotage
"""
import argparse
import math
import os
import pathlib
import re
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skipwatch import SkipWatch  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright  # noqa: E402

DEFAULT_PAGE = pathlib.Path("docs/password/index.html")

# ---------------------------------------------------------------- [5] sabotage
SABOTAGE = [
    ("各文字種を必ず含める機能が、別の文字種の唯一の出現を上書きして新たに欠落させる"
     "(2026-08-24に実際に踏んだバグ)",
     '''      var safePositions = [];
      for (var pi = 0; pi < chars.length; pi++){
        var k = classOf[pi];
        if (k !== null && countByClass[k] > 1) safePositions.push(pi);
      }
      if (safePositions.length === 0) break; // 鳩の巣原理でここには来ないはず
      var choice = rejectionIndices(safePositions.length, 1)[0];
      var pos = safePositions[choice];''',
     '''      var choice = rejectionIndices(chars.length, 1)[0];
      var pos = choice;'''),
    ("拒否サンプリングの上限計算を外し、剰余法と同じ偏りを持ち込む",
     "var limit = rejectionThreshold(n);",
     "var limit = 256;"),
    ("キーボード配列判定を無効化する",
     "function hasKeyboardWalk(pw, minLen){",
     "function hasKeyboardWalk(pw, minLen){ return null;"),
    ("よく使われるパスワード判定を無効化する",
     "if (COMMON_SET[low]){",
     "if (false && COMMON_SET[low]){"),
    ("連続文字列の判定を無効化する",
     "function hasSequentialRun(pw, minLen){",
     "function hasSequentialRun(pw, minLen){ return null;"),
]


def apply_sabotage(text, i):
    label, needle, replacement = SABOTAGE[i]
    if needle not in text:
        sys.exit("sabotage %d: 差し替え元が見つからない(ページの実装が変わった?)" % i)
    return text.replace(needle, replacement, 1), label


# ---------------------------------------------------------------- [1] エントロピー
def check_entropy(pg, sw):
    combos = [(n, L) for n in (10, 16, 26, 32, 62, 64, 94, 95) for L in (4, 8, 12, 20, 32, 64, 128)]
    got = pg.evaluate(
        "(cs) => cs.map(([n, L]) => entropyBits(n, L))", [list(c) for c in combos]
    )
    bad = []
    for (n, L), g in zip(combos, got):
        want = L * math.log2(n)
        if abs(g - want) > 1e-6:
            bad.append((n, L, g, want))
    print("[1] エントロピー計算 vs Python log2: %d/%d 一致" % (len(combos) - len(bad), len(combos)))
    for b in bad[:5]:
        print("   NG n=%d L=%d got=%r want=%r" % b)
    sw.check("[1] エントロピー計算", skipped=0, total=len(combos))
    return len(bad) == 0


# ---------------------------------------------------------------- [2] p値近似の精度
def check_pvalue_approx(pg, sw):
    pairs = []
    rnd = np.random.RandomState(20260824)
    for df in (1, 2, 5, 9, 15, 25, 31, 61, 63, 93, 94, 127):
        for _ in range(12):
            # 期待される付近(df前後)から、極端な値まで幅広く振る
            chi2 = max(0.01, rnd.gamma(df / 2.0, 2.0) * rnd.choice([0.3, 1.0, 1.0, 2.0, 5.0]))
            pairs.append((chi2, df))

    got = pg.evaluate(
        "(ps) => ps.map(([c, d]) => chiSquarePValue(c, d))", [list(p) for p in pairs]
    )
    errs = []
    agree = 0
    for (chi2, df), p_approx in zip(pairs, got):
        p_exact = float(stats.chi2.sf(chi2, df))
        errs.append(abs(p_approx - p_exact))
        # 実用上の判定(有意/非有意)が0.01と0.05のしきい値で一致するかも見る
        def bucket(p):
            return 0 if p < 0.01 else (1 if p < 0.05 else 2)
        if bucket(p_approx) == bucket(p_exact):
            agree += 1

    errs_arr = np.array(errs)
    print("[2a] χ²のp値近似(Wilson-Hilferty) vs SciPy 正確値: %d件" % len(pairs))
    print("     平均絶対誤差 %.4f / 最大絶対誤差 %.4f / 有意判定(0.01,0.05)の一致 %d/%d"
          % (errs_arr.mean(), errs_arr.max(), agree, len(pairs)))
    sw.check("[2a] p値近似の判定一致", skipped=len(pairs) - agree, total=len(pairs))
    # 判定の一致率が低いと実用上まずいので、9割以上を合格ラインにする
    return agree / len(pairs) >= 0.90


# ---------------------------------------------------------------- [2b] 実測での偏り検証(本題)
def run_draws(pg, n, count, method, trials):
    """method: 'rejectionIndices' か 'naiveModIndices'。ブラウザの実装をそのまま何度も呼ぶ。"""
    js = "(args) => { var [n, count, trials] = args; var out = []; for (var t=0;t<trials;t++){ out.push(%s(n, count)); } return out; }" % method
    return pg.evaluate(js, [n, count, trials])


def chi2_of_counts(idxs, n, count):
    counts = np.bincount(idxs, minlength=n)
    expected = count / n
    return float(np.sum((counts - expected) ** 2 / expected))


ALPHA = 0.01  # 「偏りがある」と判定するp値のしきい値(ツール本体と揃える)


def theoretical_naive_power(n, count, alpha=ALPHA):
    """v % n の理論上の分布から、この回数(count)引いたときにχ²検定(有意水準alpha)が
    偏りを検出できる確率(検定力)を、非心χ²分布で計算する。256%n==0ならalphaそのもの
    (=理論上まったく偏らないので、検出は誤検出の確率と同じになる)。"""
    e = 1.0 / n
    over = 256 % n
    under = n - over
    df = n - 1
    if over == 0:
        lam = 0.0
    else:
        po = (256 // n + 1) / 256.0
        pu = (256 // n) / 256.0
        lam = count * (over * (po - e) ** 2 / e + under * (pu - e) ** 2 / e)
    thresh = stats.chi2.ppf(1 - alpha, df)
    return float(1 - stats.ncx2.cdf(thresh, df, lam)), lam


def consistent_with(observed_k, trials, p, tol=1e-4):
    """観測された検出回数(observed_k / trials)が、確率pの二項分布として
    無理なく起こりうるか(有意水準tolの両側検定で棄却されないか)。"""
    return stats.binomtest(observed_k, trials, p, alternative="two-sided").pvalue > tol


def check_bias_naive_vs_rejection(pg, sw, count, trials):
    # 256を割り切らないn(理論上は偏るはずだが、その大きさはnごとに違う)と、
    # 割り切るn(理論上まったく偏らない)の両方を見る。
    # 判定は固定のしきい値ではなく、非心χ²分布で計算した「理論上の検定力」と、
    # 実測の検出回数が二項分布として矛盾しないかで行う。
    # (n=3やn=10は剰余の取り方によって理論上の偏りがそもそも小さく、
    #  固定の「9割は検出されるはず」という決め打ちは統計的に不適切だった)
    NON_DIVISORS = [62, 26, 95, 10, 94, 3]
    DIVISORS = [16, 64, 2, 4, 8, 32, 128]

    print("[2b] 実測: 剰余法 vs 拒否サンプリング(1試行あたり %d 回引く、各 %d 試行)" % (count, trials))

    all_ok = True
    checked = 0

    for n in NON_DIVISORS + DIVISORS:
        naive_runs = run_draws(pg, n, count, "naiveModIndices", trials)
        df = n - 1
        naive_sig = sum(1 for run in naive_runs if stats.chi2.sf(chi2_of_counts(run, n, count), df) < ALPHA)
        power, lam = theoretical_naive_power(n, count)
        ok = consistent_with(naive_sig, trials, power)
        checked += 1
        print("  n=%-3d (256%%n=%2d, 理論検定力%5.1f%%)  剰余法の検出: %d/%d 試行  %s"
              % (n, 256 % n, power * 100, naive_sig, trials, "OK" if ok else "★理論と食い違う"))
        if not ok:
            all_ok = False

        # 拒否サンプリングはどのnでも理論上偏らない(検定力=ALPHAそのもの)はず
        reject_runs = run_draws(pg, n, count, "rejectionIndices", trials)
        reject_sig = sum(1 for run in reject_runs if stats.chi2.sf(chi2_of_counts(run, n, count), df) < ALPHA)
        ok2 = consistent_with(reject_sig, trials, ALPHA)
        checked += 1
        if not ok2:
            print("    ★ 拒否サンプリングの検出回数(%d/%d)が、有意水準%.0f%%として不自然(n=%d)"
                  % (reject_sig, trials, ALPHA * 100, n))
            all_ok = False

    # 実際に使う文字種の広さ(60〜95程度)では、剰余法の偏りが極端に大きいことも
    # 数字で見せておく(n=3やn=10のような小さいnより実務上の意味が大きい)
    for n in (62, 95, 94):
        power, lam = theoretical_naive_power(n, count)
        print("  参考: n=%d での理論上の非心度 λ=%.1f(大きいほど少ない回数でも偏りが見える)" % (n, lam))

    sw.check("[2b] 剰余法/拒否サンプリングの試行", skipped=0, total=checked)
    return all_ok


# ---------------------------------------------------------------- [3] 落とし穴の名指し
PITFALL_CASES = [
    ("aaa1234X", "repeat-run"),
    ("qX9mabcdY2", "sequential"),
    ("qwertyASD1", "keyboard-walk"),
    ("ab12ab12", "repeated-substring"),
    ("password", "common-password"),
    ("p4ssw0rd", "common-password-leet"),
    ("Summer2026!", "word-plus-digit"),
    ("account2019x", "year-substring"),
    ("aaaaaaaa", "low-class-diversity"),
    ("ababababab", "low-unique-ratio"),
    ("abccba", "palindrome"),
    ("8charsX!", "just-minimum"),
    ("passw0rd1", "ambiguous-chars"),
]


def check_pitfalls(pg, sw):
    pw_list = [c[0] for c in PITFALL_CASES]
    results = pg.evaluate(
        "(pws) => pws.map(pw => detectPitfalls(pw, {}).map(n => n.code))", pw_list
    )
    bad = []
    for (pw, want_code), codes in zip(PITFALL_CASES, results):
        if want_code not in codes:
            bad.append((pw, want_code, codes))
    print("[3] 落とし穴の名指し: %d/%d 一致" % (len(PITFALL_CASES) - len(bad), len(PITFALL_CASES)))
    for b in bad:
        print("   NG pw=%r 期待=%s 実際=%r" % b)
    sw.check("[3] 落とし穴の名指し", skipped=0, total=len(PITFALL_CASES))
    return len(bad) == 0


# ------------------------------------------------- [7] 名乗っている種類の数の見張り
# 2026-09-04 昼 新設。きっかけ: **トップページが「約20種類の名指し」と書いていたが、
# 道具が持っている種類は 13 だった**(日英とも。`約` が付いているので嘘とまでは言えないが、
# 5割増しは「だいたい」の範囲を超えている)。
# しかもこの数は**トップページにしか無い**ので、道具側を見ても比べる相手がいない
# = 9/3 の timezone・9/4 未明の jwt 57 / qr 111 と同じ形の5本目。
# → **数を出した当人(この検証)に見張らせる**。見るのは3つ:
#     (a) ページの `add()` が名乗りうる code を、この検証が全部試しているか
#     (b) 逆に、この検証が試している code がページに実在するか
#     (c) 一覧ページ(日英)が名乗っている数が、実際の種類の数と合っているか
# ⚠ (c) は**一覧ページを読む**ので、この検証はパスワードのページだけを見ていれば
#   よいわけではない。見つからないときは黙って通さず「見ていない」と言う。
ADD_RE = re.compile(r'add\(\s*"([a-z0-9-]+)"')
CLAIM_RE = re.compile(r"(?:約)?\s*([0-9]+)\s*種類|(?:about\s+)?([0-9]+)\s+named traps")


def check_kind_count(text, page, sw):
    on_page = sorted(set(ADD_RE.findall(text)))
    tested = sorted({c for _, c in PITFALL_CASES})
    ok = True
    miss = [c for c in on_page if c not in tested]
    extra = [c for c in tested if c not in on_page]
    print("[7] 落とし穴の種類: ページ %d 種 / この検証が試している %d 種"
          % (len(on_page), len(tested)))
    if miss:
        ok = False
        print("   ★ページにあるのに試していない: %s" % ", ".join(miss))
    if extra:
        ok = False
        print("   ★試しているのにページに無い: %s" % ", ".join(extra))

    # (c) 一覧ページの名乗り。docs/ を上にたどって探す
    docs = page.resolve().parent.parent
    seen = 0
    for rel in ("index.html", "en/index.html"):
        p = docs / rel
        if not p.exists():
            print("   ⚠ 一覧ページが見つからないので見ていません: %s" % p)
            continue
        # パスワードの札の中だけを見る(ほかの道具の「◯種類」に当たらないように)。
        # ⚠ 最初は `password/` を素朴に探したが、**日本語は `./password/`・英語は
        #   `./password.html`** で綴りが違い、しかも先に別の所で当たって短い切り出しになった。
        #   → href から札の `<a …>…</a>` を丸ごと切り出す。
        html = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'href="\./password(?:/|\.html)"', html)
        i = html.rfind("<a ", 0, m.start()) if m else -1
        j = html.find("</a>", i) if i >= 0 else -1
        if i < 0 or j < 0:
            print("   ⚠ %s にパスワードの札が見つかりません" % rel)
            continue
        card = html[i:j]
        for m in CLAIM_RE.finditer(card):
            seen += 1
            n = int(m.group(1) or m.group(2))
            if n != len(on_page):
                ok = False
                print("   ★%s の名乗り %d 種類 ≠ 実際の %d 種類" % (rel, n, len(on_page)))
            else:
                print("   %s の名乗り %d 種類 = 実際 と一致" % (rel, n))
        # ★毎回「1ずらすと鳴るか」を確かめる(2026-09-04 未明の申し送り)。
        #   数が合っていることだけを見ていると、**読んでいる場所がそもそも違っても
        #   通ってしまう**(9/4 未明に色指定の中の数字を拾っていた実例がある)。
        if seen:
            bumped = CLAIM_RE.sub(lambda m: (m.group(0).replace(
                m.group(1) or m.group(2), str(len(on_page) + 1), 1)), card, count=1)
            hit = [int(x.group(1) or x.group(2)) for x in CLAIM_RE.finditer(bumped)]
            if len(on_page) + 1 not in hit:
                ok = False
                print("   ★%s: 数を1ずらしても読み取りが変わらない(見ている場所が違う)" % rel)
    if seen == 0:
        print("   ⚠ どの一覧ページも種類の数を名乗っていません(名乗るなら %d)" % len(on_page))
    sw.check("[7] 名乗っている種類の数", skipped=0, total=max(len(on_page), 1))
    return ok


# ---------------------------------------------------------------- [4] eachClass 回帰検査
def check_each_class(pg, sw, trials):
    configs = [
        {"lower": True, "upper": True, "digit": True, "symbol": True, "noAmbig": False, "eachClass": True, "length": 4},
        {"lower": True, "upper": True, "digit": True, "symbol": True, "noAmbig": False, "eachClass": True, "length": 8},
        {"lower": True, "upper": True, "digit": True, "symbol": False, "noAmbig": False, "eachClass": True, "length": 6},
        {"lower": True, "upper": False, "digit": True, "symbol": True, "noAmbig": True, "eachClass": True, "length": 5},
    ]
    js = """(args) => {
      var [configs, trials] = args;
      var fails = 0, total = 0;
      configs.forEach(function(opts){
        for (var t = 0; t < trials; t++){
          total++;
          var p = generatePassword(opts);
          var ok = true;
          if (opts.lower && !/[a-z]/.test(p)) ok = false;
          if (opts.upper && !/[A-Z]/.test(p)) ok = false;
          if (opts.digit && !/[0-9]/.test(p)) ok = false;
          if (opts.symbol && !/[^a-zA-Z0-9]/.test(p)) ok = false;
          if (!ok) fails++;
        }
      });
      return { fails: fails, total: total };
    }"""
    res = pg.evaluate(js, [configs, trials])
    print("[4] 各文字種を必ず含める(回帰検査): %d/%d 件で欠落" % (res["fails"], res["total"]))
    sw.check("[4] eachClassの欠落", skipped=res["fails"], total=res["total"])
    return res["fails"] == 0


# ---------------------------------------------------------------- [6] 自己検査
def check_self_check(pg):
    res = pg.evaluate("() => selfCheck()")
    ok = sum(1 for r in res if r["ok"])
    print("[6] ページ内の自己検査: %d/%d" % (ok, len(res)))
    for r in res:
        if not r["ok"]:
            print("   NG:", r["t"])
    return ok == len(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40000, help="偏り検証1試行あたりの引く回数")
    ap.add_argument("--trials", type=int, default=25, help="偏り検証の試行回数(χ²は毎回ゆれるので複数回見る)")
    ap.add_argument("--page", default=None)
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--update-skip-baseline", action="store_true")
    args = ap.parse_args()

    page = pathlib.Path(args.page) if args.page else DEFAULT_PAGE
    if not page.exists():
        cand = sorted(pathlib.Path.cwd().glob("**/docs/password/index.html"))
        if not cand:
            sys.exit("ページが見つかりません。--page で指定してください")
        page = cand[0]
    text = page.read_text(encoding="utf-8")

    if args.sabotage:
        print("=== --sabotage: わざと壊して検査が空振りしないか確認 ===\n")
        caught = 0
        for i, (label, _, _) in enumerate(SABOTAGE):
            broken, _ = apply_sabotage(text, i)
            with sync_playwright() as pw:
                br = pw.chromium.launch()
                pg = br.new_page()
                pg.set_content(broken)
                pg.wait_for_timeout(100)
                ok_entropy = check_entropy(pg, SkipWatch("test_password", update=False))
                ok_bias = check_bias_naive_vs_rejection(pg, SkipWatch("test_password", update=False),
                                                         count=min(args.n, 15000), trials=min(args.trials, 10))
                ok_pit = check_pitfalls(pg, SkipWatch("test_password", update=False))
                ok_each = check_each_class(pg, SkipWatch("test_password", update=False), trials=800)
                br.close()
            found = not (ok_entropy and ok_bias and ok_pit and ok_each)
            print("[%d] %s → %s\n" % (i, label, "検査で捕まった" if found else "★空振り(検査が気づかなかった)"))
            if found:
                caught += 1
        print("=== sabotage %d/%d 件を検査が捕まえた ===" % (caught, len(SABOTAGE)))
        return 0 if caught == len(SABOTAGE) else 1

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page()
        errors = []
        pg.on("pageerror", lambda exc: errors.append(str(exc)))
        pg.set_content(text)
        pg.wait_for_timeout(200)

        sw = SkipWatch("test_password", update=args.update_skip_baseline)
        results = []
        results.append(check_entropy(pg, sw))
        results.append(check_pvalue_approx(pg, sw))
        results.append(check_bias_naive_vs_rejection(pg, sw, count=args.n, trials=args.trials))
        results.append(check_pitfalls(pg, sw))
        results.append(check_each_class(pg, sw, trials=3000))
        results.append(check_self_check(pg))
        results.append(check_kind_count(text, page, sw))
        br.close()

    print("\nページの実行時エラー:", len(errors))
    for e in errors[:5]:
        print("  ", e)

    ok = all(results) and not errors
    skip_bad = sw.report()
    print("\n=== 総合:", "PASS" if (ok and skip_bad == 0) else "NG", "===")
    return 0 if (ok and skip_bad == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
