#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「カラーパレット生成」の英語版を、日本語版から作る(2026-09-01 朝)。

`make_en_contrast.py` / `make_en_cron.py` と同じ方式。**日本語版が唯一の原本**。

★この回の理由は「新しく英語版を出す」ではなく **「古い手書きの英語版を置き換える」**。
  同じ枠で新設した `check_en_parity.py`(英語版と日本語版でコードが同じかを見る道具)が、
  **`en/palette.html` にこの道具の看板機能がまるごと無い**ことを見つけた:
    - `readableOn`(白か黒か読めるほうを選ぶ)
    - `nudgeToContrast`(基準を満たす一番近い明るさを二分探索する)
    - `MAX_MOVE`(30ポイントを超えるなら別の色なので寄せない、という線引き)
  英語版は**配色を並べるだけ**の古い版のままで、`test_palette.py` が 3,000 通りで
  確かめている「寄せる」処理が英語の利用者にはそもそも届いていなかった。
  手書きの英語版を作った日(8/21)から、日本語版だけが育った結果。
  → **手で書き足すのではなく、生成に切り替える**。以後この事故は構造的に起きない。

1. HTML(head・本文・footer・ナビ)を英語の版に差し替える
2. スクリプトの中の**文字列リテラルの中身だけ**を英語に差し替える(TR辞書)
3. **「文字列の中身を全部空にすると、日本語版とバイト単位で一致する」**ことを確かめる
   = 色変換・WCAG の比・二分探索・パレット定義は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる

⚠ この検査の効き目の限界(2026-09-01 に自分で気づいたこと):
   `blank()` は**テンプレートリテラルを丸ごと1つの文字列として空にする**ので、
   `` `…${ここの式}…` `` の中身は日英の照合に**入らない**。だから TR で差し替える
   テンプレートの中では、**変数の順番と綴りを勝手に変えない**のが縛りになる。

使い方: python lab/scripts/make_en_palette.py <リポジトリの docs>
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank, literals  # noqa: E402
from en_common import (translate_comments,  # noqa: E402
                       JA_CHARS, code_japanese, script_span,  # noqa: E402
                       translate_literals)

HTML_PARTS = [
    ('<html lang="ja">', '<html lang="en">'),

    ('<title>カラーパレット生成 — 配色を作って、読める明るさまで寄せる</title>',
     '<title>Color Palette Generator — build a scheme, then nudge it until it is readable</title>'),

    ('<meta name="description" content="基準色から配色理論に沿ったパレット(類似色・補色・トライアドなど)を作り、載せる文字色に対するコントラスト比を1色ずつ表示します。AAに足りない色は、色みを保ったまま明るさだけを動かして基準を満たす位置まで自動で寄せられます。ブラウザ内で完結し、データはどこにも送信されません。">',
     '<meta name="description" content="Builds color-theory palettes (analogous, complementary, triadic and more) from one base color and shows the WCAG contrast ratio of every swatch against the text color you will put on it. Swatches that miss AA can be nudged: only the lightness moves, the hue stays. Built by an AI (Claude); everything runs in the browser and nothing is ever sent anywhere.">'),

    ('''    /* リンク色は白地で 4.5:1 を超える濃さにしている（明るい #c47f16 だと 3.28:1 しか出ない）。
       --on-accent はアクセント色を背景に敷いたときの文字色。 */''',
     '''    /* The link color is dark enough to clear 4.5:1 on white (the lighter #c47f16 only reaches 3.28:1).
       --on-accent is the text color to use when the accent color is the background. */'''),

    ('  /* 色を指定しないとブラウザ既定の青になり、ダークモードで 1.89:1 まで落ちる */',
     '  /* Without an explicit color these fall back to the browser default blue, which is 1.89:1 in dark mode */'),

    ('''  /* 選択肢の文が長いと select がそのまま伸びて、375px 幅で横スクロールが出る
     (英語版の「Automatic (white or black)」で実際に 43px はみ出した)。
     flex の子は既定で内容より縮まないので min-width:0 も要る。 */''',
     '''  /* A long option makes the select grow to fit it, which overflows at 375px wide
     (the English "Automatic (white or black)" pushed 43px past the edge).
     A flex child does not shrink below its content, so min-width:0 is needed too. */'''),

    ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/palette/">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/palette/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/palette.html">',
     '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/palette.html">\n'
     '<link rel="alternate" hreflang="ja" href="https://hirulab-dev.github.io/hirulab-tools/palette/">\n'
     '<link rel="alternate" hreflang="en" href="https://hirulab-dev.github.io/hirulab-tools/en/palette.html">'),

    ('<meta property="og:site_name" content="クロードの昼ラボ">\n'
     '<meta property="og:locale" content="ja_JP">\n'
     '<meta property="og:title" content="カラーパレット生成 — 配色を作って、読める明るさまで寄せる">\n'
     '<meta property="og:description" content="基準色から配色を作り、載せる文字に対するコントラスト比を1色ずつ表示。AAに足りない色は色みを保ったまま明るさだけ動かして基準まで寄せられます。ブラウザ内で完結します。">\n'
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/palette/">\n'
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-palette.png">',
     '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">\n'
     '<meta property="og:locale" content="en_US">\n'
     '<meta property="og:title" content="Color Palette Generator — with contrast checks on every swatch">\n'
     '<meta property="og:description" content="Color-theory palettes from any base color, with the WCAG contrast ratio shown on every swatch. Swatches that miss the target can be nudged by lightness alone.">\n'
     '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/palette.html">\n'
     '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-en-palette.png">'),

    ('<meta name="twitter:title" content="カラーパレット生成 — 配色を作って、読める明るさまで寄せる">\n'
     '<meta name="twitter:description" content="配色を作り、コントラスト比を1色ずつ表示。AAに足りない色は明るさだけ動かして基準まで寄せられます。">\n'
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-palette.png">',
     '<meta name="twitter:title" content="Color Palette Generator — with contrast checks on every swatch">\n'
     '<meta name="twitter:description" content="Color-theory palettes with the WCAG contrast ratio on every swatch, and a nudge that moves lightness only.">\n'
     '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-en-palette.png">'),

    ('''  "name": "カラーパレット生成",
  "url": "https://hirulab-dev.github.io/hirulab-tools/palette/",
  "description": "基準色から配色理論に沿ったパレットを作り、載せる文字色に対するコントラスト比を1色ずつ表示します。AAに足りない色は色みを保ったまま明るさだけを動かして基準を満たす位置まで自動で寄せられます。ブラウザ内で完結します。",
  "applicationCategory": "DesignApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "JavaScript が有効なモダンブラウザ",
  "inLanguage": "ja",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-palette.png",
  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }''',
     '''  "name": "Color Palette Generator",
  "url": "https://hirulab-dev.github.io/hirulab-tools/en/palette.html",
  "description": "Builds color-theory palettes from one base color and shows the WCAG contrast ratio of every swatch against the text color you will put on it. Swatches that miss the target can be nudged by moving lightness only, so the hue stays. Runs entirely in the browser.",
  "applicationCategory": "DesignApplication",
  "operatingSystem": "Web browser",
  "browserRequirements": "A modern browser with JavaScript enabled",
  "inLanguage": "en",
  "isAccessibleForFree": true,
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-en-palette.png",
  "author": { "@type": "Organization", "name": "Claude's Daytime Lab", "url": "https://note.com/hirulab" },
  "isPartOf": { "@type": "WebSite", "name": "Claude's Daytime Lab — Tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'''),

    ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>カラーパレット生成</h1>
  <p class="lead">基準色をひとつ選ぶと、配色理論に沿った組み合わせが出ます。
    そのうえで<strong>その色に文字を載せたとき読めるか</strong>を1色ずつ判定し、
    <strong>足りない色は、色みを変えずに明るさだけ動かして基準を満たす位置まで寄せられます。</strong>
    きれいな配色を出す道具は山ほどあるので、この道具は「出した色が使えるか」のほうに寄せてあります。</p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    配色もコントラスト比の計算もすべてブラウザの中でやっています。
    読み込んだあとは機内モードでも動きます。
  </div>''',
     '''  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab — Tools</a>
  <h1>Color Palette Generator</h1>
  <p class="lead">Pick one base color and you get the combinations classic color theory suggests.
    On top of that, every swatch is judged on <strong>whether text on it would actually be readable</strong>, and
    <strong>the ones that fall short can be nudged up to the target by moving lightness only, leaving the hue alone.</strong>
    There is no shortage of tools that produce pretty palettes, so this one leans on the other question: can you use the colors it gave you?</p>

  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    The palettes and the contrast maths all happen inside your browser.
    Once it has loaded, it works in aeroplane mode.
  </div>'''),

    ('''      <input type="color" id="base" value="#2b6cb0" aria-label="基準色">
      <input type="text" id="hex" value="#2b6cb0" spellcheck="false" aria-label="基準色（16進数）">
      <button class="mini" id="rand">ランダムに選ぶ</button>''',
     '''      <input type="color" id="base" value="#2b6cb0" aria-label="Base color">
      <input type="text" id="hex" value="#2b6cb0" spellcheck="false" aria-label="Base color (hex)">
      <button class="mini" id="rand">Pick one at random</button>'''),

    ('''      <label for="fg">載せる文字の色
        <select id="fg">
          <option value="#ffffff">白 #ffffff</option>
          <option value="#1a1a1a" selected>黒 #1a1a1a</option>
          <option value="auto">明るさで自動（白か黒か読めるほう）</option>
        </select>
      </label>
      <label for="level">満たしたい基準
        <select id="level">
          <option value="4.5" selected>AA 本文（4.5:1）</option>
          <option value="3">AA 大きな文字（3:1）</option>
          <option value="7">AAA 本文（7:1）</option>
        </select>
      </label>
      <label for="fix"><input type="checkbox" id="fix"> 足りない色を基準まで寄せる</label>''',
     '''      <label for="fg">Text color on top
        <select id="fg">
          <option value="#ffffff">White #ffffff</option>
          <option value="#1a1a1a" selected>Black #1a1a1a</option>
          <option value="auto">Automatic (white or black)</option>
        </select>
      </label>
      <label for="level">Target to meet
        <select id="level">
          <option value="4.5" selected>AA body text (4.5:1)</option>
          <option value="3">AA large text (3:1)</option>
          <option value="7">AAA body text (7:1)</option>
        </select>
      </label>
      <label for="fix"><input type="checkbox" id="fix"> Nudge failing colors up to the target</label>'''),

    ('  <h2>CSS変数として書き出し</h2>', '  <h2>Export as CSS variables</h2>'),

    ('''    <summary>どうやって「寄せて」いるか、と、この道具の限界</summary>
    <ul>
      <li><b>動かすのは明るさ(HSL の L)だけです。</b>色相と彩度はそのままにして、
        基準を満たす一番近い明るさを二分探索で探します。色みが変わらないので、
        配色としてのまとまりが崩れにくい。</li>
      <li><b>上にも下にも探して、動く量が少ないほうを採ります。</b>暗くして満たせるなら暗く、
        明るくしたほうが近いなら明るく。移動量は「L を何ポイント動かしたか」で表示します。</li>
      <li><b>動かす量には上限（30ポイント）を置いています。</b>HSL は明るさ 0 が黒・1 が白なので、
        理屈のうえでは<b>どんな色でも必ず基準を満たせます</b>。ただし満たせることと、
        満たしていいことは別です。たとえば黄色 <code>#ffff00</code> に白い文字を載せて 4.5:1 に
        届かせるには明るさを 26 ポイント下げることになり、出てくるのは <code>#7a7a00</code>、
        もう黄色ではありません。<b>上限を超えるものは寄せずに、必要な量だけをお伝えします。</b>
        黙って別の色に差し替えることはしません。</li>
      <li><b>コントラスト比の式は WCAG 2.1 のものです。</b>相対輝度を求めて
        <code>(明るいほう + 0.05) / (暗いほう + 0.05)</code>。4.5:1 以上で本文、3:1 以上で
        大きな文字(24px 以上、または 18.66px 以上の太字)が AA を満たします。</li>
      <li><b>この式は万能ではありません。</b>WCAG 2.x のコントラスト比は、
        濃い背景に薄い文字を載せたときの見え方を実感より高く評価する傾向が知られています。
        数字を満たしたうえで、最後は自分の目で見てください。</li>
      <li><b>色覚特性のシミュレーションはこの道具には入れていません。</b>
        同じ場所で公開している<a href="../contrast/">コントラスト比チェッカー</a>のほうに入っています。
        2色を突き合わせて詰めるときはそちらへどうぞ。</li>
      <li><b>スウォッチをクリックすると16進数をコピーします。</b>
        「寄せる」を有効にしているときは、寄せたあとの値をコピーします。</li>
    </ul>''',
     '''    <summary>How the nudge works, and where this tool stops</summary>
    <ul>
      <li><b>Only the lightness (the L of HSL) moves.</b> Hue and saturation stay exactly where they
        were, and a binary search finds the nearest lightness that meets the target. Because the hue
        does not move, the palette still hangs together.</li>
      <li><b>It searches both up and down and takes the smaller move.</b> Darker if darker gets there,
        lighter if lighter is closer. The label tells you how many points of L it moved.</li>
      <li><b>There is a ceiling on the move (30 points).</b> In HSL, lightness 0 is black and 1 is white,
        so in principle <b>any color can be made to meet any target</b>. But being able to and being
        allowed to are different things. Take yellow <code>#ffff00</code> with white text: reaching 4.5:1
        means dropping the lightness by 26 points, and what comes out is <code>#7a7a00</code>, which is
        not yellow any more. <b>Anything past the ceiling is left alone, and you are told how much it
        would have taken.</b> It never quietly swaps in a different color.</li>
      <li><b>The contrast ratio is the WCAG 2.1 formula.</b> Relative luminance, then
        <code>(lighter + 0.05) / (darker + 0.05)</code>. 4.5:1 or above passes AA for body text, 3:1 or
        above for large text (24px or larger, or 18.66px or larger in bold).</li>
      <li><b>That formula is not the last word.</b> The WCAG 2.x ratio is known to flatter light text on
        a dark background — it scores better than it looks. Meet the number, then look at it yourself.</li>
      <li><b>Color vision deficiency simulation is not in this tool.</b> It is in the
        <a href="./contrast.html">Contrast Ratio Checker</a> published in the same place.
        That is the one to use when you are pinning down two specific colors.</li>
      <li><b>Click a swatch to copy its hex.</b> With the nudge turned on, what you copy is the
        nudged value.</li>
    </ul>'''),

    ('''  <footer>
    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    コントラスト比は WCAG 2.1 の計算式です（4.5:1 以上=本文 OK、3:1 以上=大きな文字 OK）。
  </footer>''',
     '''  <footer>
    Built by Claude&#39;s Daytime Lab (an AI, Claude). Free to use, no sign-up.
    The contrast ratio is the WCAG 2.1 formula (4.5:1 or above = body text OK, 3:1 or above = large text OK).
  </footer>'''),

    ('<div class="toast" id="toast">コピーしました</div>',
     '<div class="toast" id="toast">Copied</div>'),
]

TR = {
    # ---- パレットの名前(CSS変数の名前にもなる)と、ひとことの説明 ----
    "類似色": "Analogous",
    "隣り合う色相でそろえる。まとまりが出るぶん、めりはりは弱い":
        "Neighbouring hues only. Cohesive, but short on contrast.",
    "補色": "Complementary",
    "真反対の色相を当てる。目を引くが、面積を同じにすると喧嘩する":
        "The hue straight across the wheel. Eye-catching, but the two fight if you give them equal area.",
    "分裂補色": "Split complementary",
    "反対色の両隣を使う。対比を残しつつ、補色ほどぶつからない":
        "The two hues either side of the opposite one. Keeps the contrast without the clash.",
    "トライアド": "Triadic",
    "色相を三等分する。にぎやかになるので、1色を主役に決めて使う":
        "The hue wheel cut in three. Lively, so pick one to lead and keep the others small.",
    "明暗バリエーション": "Shades and tints",
    "同じ色の濃淡だけで組む。UIの階層を作るときはこれが安全":
        "One hue, light to dark. The safe choice for building hierarchy in a UI.",
    "くすみトーン": "Muted tones",
    "彩度を落として明度を上げる。文字を載せる面には向くことが多い":
        "Less saturation, more lightness. Usually the easiest surface to put text on.",

    # ---- スウォッチの下に出る「寄せた/寄せられなかった」 ----
    '<span class="moved">${r && r.tooFar ? "要 " + r.tooFar + " ・寄せず" : "寄せられません"}</span>':
        '<span class="moved">${r && r.tooFar ? "needs " + r.tooFar + " · left as is" : "cannot reach it"}</span>',
    '<span class="moved">明るさ ${r.moved > 0 ? "+" : ""}${r.moved} 寄せた</span>':
        '<span class="moved">lightness ${r.moved > 0 ? "+" : ""}${r.moved} pts</span>',

    # ---- スウォッチ本体(読み上げ用のラベルと、白/黒のバッジ) ----
    '''<button class="sw" type="button" data-hex="${c}"
                 aria-label="${esc(c)} をコピー（コントラスト比 ${ratio.toFixed(2)}）">
        <div class="chip" style="background:${c}">
          ${badge(c, fg, fg === "#ffffff" ? "白" : "黒", need)}
          ${badge(c, other, other === "#ffffff" ? "白" : "黒", need)}
        </div>
        <div class="meta">${esc(c)}${movedText}</div>
      </button>''':
        '''<button class="sw" type="button" data-hex="${c}"
                 aria-label="Copy ${esc(c)} (contrast ratio ${ratio.toFixed(2)})">
        <div class="chip" style="background:${c}">
          ${badge(c, fg, fg === "#ffffff" ? "White" : "Black", need)}
          ${badge(c, other, other === "#ffffff" ? "White" : "Black", need)}
        </div>
        <div class="meta">${esc(c)}${movedText}</div>
      </button>''',

    # ---- 下の説明文(4通り) ----
    "いまは配色理論どおりの色をそのまま出しています。○ が基準（${need}:1）を満たす色、× が足りない色です。":
        "Right now these are the colors straight out of the color theory. ○ meets the target (${need}:1), × falls short.",
    "「足りない色を基準まで寄せる」を入れると、色みを変えずに明るさだけ動かして直します。":
        "Tick “Nudge failing colors up to the target” and they get fixed by moving lightness only, with the hue left alone.",
    "${nTotal} 色のうち ${nFixed} 色を寄せました。${nImpossible} 色は、${need}:1 に届かせるには ":
        "${nTotal} colors in all, ${nFixed} nudged. For ${nImpossible} of them, reaching ${need}:1 would take ",
    "明るさを 30 ポイント以上動かす必要があります。それはもう別の色なので、寄せずにそのまま出しています。":
        "a lightness move of 30 points or more. That is a different color by then, so they are left as they are.",
    "文字色を変えるか、基準を「大きな文字（3:1）」にするほうが早いかもしれません。":
        "Changing the text color, or aiming at “large text (3:1)”, may well be the quicker way out.",
    "${nTotal} 色のうち ${nFixed} 色を寄せました。残りは元から ${need}:1 を満たしています。":
        "${nTotal} colors in all, ${nFixed} nudged. The rest already met ${need}:1 on their own.",
    "${nTotal} 色すべてが元から ${need}:1 を満たしていました。寄せる必要はありません。":
        "All ${nTotal} colors already met ${need}:1 on their own. Nothing needed nudging.",
}

KEEP = set()

# ★2026-09-03 夜 追加(コメントも訳す)。⚠ 訳は行数を変えない・訳の中に日本語を書かない。
COMMENTS = {
    '/* ---- 色変換 ---- */': '/* ---- Color conversion ---- */',
    '/* ---- WCAG 2.1 のコントラスト比 ---- */': '/* ---- WCAG 2.1 contrast ratio ---- */',

    '/* ---- 基準を満たす一番近い明るさを探す --------------------------------\n'
    '   色相と彩度は動かさない。L だけを二分探索する。上下どちらにも探して、\n'
    '   満たせたほうのうち移動量が小さいほうを採る。\n'
    '\n'
    '   HSL は L=0 が黒・L=1 が白なので、理屈のうえでは **どんな色でも必ず満たせる**。\n'
    '   だが黄色に白文字を載せる例だと、4.5:1 に届くには L を 26 ポイント下げることになり、\n'
    '   出てくるのは #7a7a00 のオリーブで、もう黄色ではない。\n'
    '   「必ず直せる」は「必ず直していい」ではないので、動かす量に上限を置いて、\n'
    '   超えるものは **直さずに、必要な量を伝える** ことにした。 */':
    '/* ---- Find the nearest lightness that meets the target ------------------\n'
    '   Hue and saturation stay put; only L is searched, by bisection. Both\n'
    '   directions are tried and the smaller move wins.\n'
    '\n'
    '   In HSL, L=0 is black and L=1 is white, so in theory **any color can be fixed**.\n'
    '   But white text on yellow needs L to drop 26 points to reach 4.5:1, and what\n'
    '   comes out is the olive #7a7a00, which is no longer yellow.\n'
    '   "Can always be fixed" is not "should always be fixed", so the move is capped and\n'
    '   anything past the cap is **left alone, with the required amount reported**. */',

    '// L を 30 ポイント以上動かすなら、それは別の色':
    '// Moving L by 30 points or more makes it a different color',
    '// lo 側が未達、hi 側が達成、である前提で詰める':
    '// Narrows on the assumption that lo fails and hi passes',
    '// 暗くして満たす': '// Darken until it passes',
    '// 明るくして満たす': '// Lighten until it passes',
    '/* ---- パレット定義 ---- */': '/* ---- Palette definitions ---- */',

    '/* data-contrast-demo は「わざと不合格の例を見せている」印。\n'
    '   自前のコントラスト検査スクリプトはこの印が付いた要素を数えない。 */':
    '/* data-contrast-demo marks a swatch that fails on purpose, shown as an example.\n'
    '   Our own contrast-checking script does not count elements carrying this mark. */',

    '// 長い文にするとスウォッチの高さが揃わなくなるので、ここは短く。':
    '// Keep this short: long sentences leave the swatch heights uneven.',
    '// 事情は下の説明文（fixnote）と details に書いてある。':
    '// The reasoning is spelled out in the fixnote below and in the details block.',
    '// 区切りは落とさずハイフンにする(英語版の "Split complementary" が1語に潰れないように)':
    '// Turn the separator into a hyphen instead of dropping it (so "Split complementary" survives)',
}


def en_nav(docs):
    import en_nav as _en_nav
    return _en_nav.build(docs, "contrast.html", "Contrast Ratio Checker",
                         "palette.html", "../palette/")






def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "palette" / "index.html"
    en_path = docs / "en" / "palette.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    nav = re.search(r'  <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not nav:
        sys.exit("ナビが見つかりません")
    en = en[:nav.start()] + en_nav(docs) + en[nav.end():]

    s, e = script_span(en)
    core_en, missing = translate_comments(en[s:e], COMMENTS)
    if missing:
        sys.exit("訳されていないコメントが %d 件あります:\n  %s"
                 % (len(missing), "\n  ".join(m[:100] for m in missing[:8])))
    core_en, missing = translate_literals(core_en, TR, KEEP)
    if missing:
        sys.exit("訳されていない文字列が %d 件あります:\n  %s"
                 % (len(missing), "\n  ".join(sorted(set(missing))[:12])))
    en = en[:s] + core_en + en[e:]

    # (1) 画面に出るところ: スクリプトの外に日本語が1文字も無いこと
    s2, e2 = script_span(en)
    outside = en[:s2] + en[e2:]
    left = JA_CHARS.findall(outside)
    if left:
        sys.exit("スクリプトの外に日本語が %d 箇所残っています: %s" % (len(left), left[:12]))

    # (2) スクリプトの中: 日本語を含むリテラルは KEEP のものだけ
    kept = []
    for q, body in literals(en[s2:e2]):
        if JA_CHARS.search(body):
            if body not in KEEP:
                sys.exit("スクリプトの中に訳し忘れがあります: " + body[:120])
            kept.append(body)

    # (3) 識別子として書かれた日本語
    ident = code_japanese(en[s2:e2])
    if ident:
        sys.exit("識別子として書かれた日本語が %d 箇所あります:\n  %s"
                 % (len(ident), "\n  ".join(ident[:6])))

    # (4) 文字列の中身を空にすると、日英でコードがバイト単位で一致すること
    sj, ej = script_span(ja)
    a, b = blank(ja[sj:ej]), blank(en[s2:e2])
    if a != b:
        for k, (x, y) in enumerate(zip(a.split("\n"), b.split("\n"))):
            if x != y:
                sys.exit("コードが一致しません(%d行目):\n  ja: %s\n  en: %s" % (k + 1, x, y))
        sys.exit("コードの行数が違います(ja %d / en %d)" % (a.count("\n"), b.count("\n")))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("訳した文字列: %d 件" % len(TR))
    print("わざと日本語のまま残したリテラル: %d 件" % len(kept))
    print("画面に出るところの日本語: 0箇所")
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致(%d バイト)" % len(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
