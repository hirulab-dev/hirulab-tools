#!/usr/bin/env python3
"""鉄道図ツールの英語版を、日本語版から作る（2026-08-23）。

**日本語版が唯一の原本**。英語版は毎回ここから作り直す。手で両方を直すと必ずずれる。

やっていること
1. HTML（head・本文・ナビ・解説）を英語の版に差し替える
2. スクリプトの中の**引用符で囲まれた文字列だけ**を英語に差し替える
3. できた英語版について、**「文字列リテラルを全部取り除くと日本語版とバイト単位で一致する」**
   ことを確かめる。これが通れば、**解析・作図・落とし穴検出・例文字列の生成のコードは
   1バイトも違わない**（違うのは文面だけ）と言い切れる
4. 日本語が1文字も残っていないことを確かめる

使い方: python lab/scripts/make_en_railroad.py <リポジトリの docs>
"""
import re, sys, pathlib

import pathlib as _pl, sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
from en_common import translate_css_comments

# ── スクリプト内の文字列リテラル（引用符ごと突き合わせるので、
#    '回' が '回ちょうど' の中を書き換えてしまう事故は起きない）──────────────
TR = {
    # 解析のエラー
    '式が途中で終わっています': 'the pattern ends in the middle of something',
    'ここから先が読めません': 'cannot read the pattern from here on',
    '対応する「(」のない「)」です': 'this ")" has no matching "("',
    '「(」に対応する「)」がありません': 'this "(" is never closed',
    '「[」に対応する「]」がありません': 'this "[" is never closed',
    '「\\\\」で式が終わっています': 'the pattern ends with a backslash',
    '「(?」のあとの書き方が分かりません': 'cannot tell what this "(?" is meant to be',
    'グループ名の書き方が違います（<名前> の形にしてください）':
        'a group name has to be written as <name>',
    '「\\\\k<名前>」の書き方が違います': 'a named backreference has to be written as \\\\k<name>',
    'その名前のグループがありません: ': 'there is no group with that name: ',
    '同じ名前のグループが2つあります: ': 'two groups share the same name: ',
    '（同じ「|」の別の枝どうしなら置けます）':
        ' (allowed only when the two sit in different branches of the same "|")',
    'グループが ': 'there are only ',
    ' 個しかないので \\\\': ' groups, so \\\\',
    ' は参照できません': ' cannot refer to anything',
    '」の前にくり返す対象がありません': '" has nothing before it to repeat',
    '」は位置を指す記号なので、くり返せません':
        '" marks a position rather than a character, so it cannot be repeated',
    'くり返しの記号が続いています。まとめたいときは (?:…) で囲んでください':
        'two repeat markers in a row. Wrap the part you want to repeat in (?:...)',
    '後読みはくり返せません': 'a lookbehind cannot be repeated',
    'u フラグがあるときは先読みをくり返せません':
        'with the u flag, a lookahead cannot be repeated',
    'くり返しの下限が上限より大きいです（': 'the lower bound is above the upper bound (',
    'この書き方（絶対最大量指定子）は JavaScript にはありません':
        'JavaScript has no possessive quantifiers',
    '文字の範囲が逆向きです（': 'this character range runs backwards (',
    ' のほうが ': ' comes after ',
    ' より後ろの文字です）': ' in character order)',
    'この「-」は範囲になりません（u フラグがあるので \\- と書く必要があります）':
        'this "-" cannot form a range, and with the u flag it has to be written as \\\\-',
    'u フラグがあるときは 8進エスケープを書けません':
        'octal escapes are not allowed when the u flag is on',
    '「\\\\x」のあとは16進2桁です（u フラグがあるので読み流せません）':
        '\\\\x needs two hex digits, and the u flag stops it from being read as plain text',
    '「\\\\u」のあとは16進4桁か {…} です（u フラグがあるので読み流せません）':
        '\\\\u needs four hex digits or {...}, and the u flag stops it from being read as plain text',
    '「\\\\c」のあとは英字1文字です（u フラグがあるので読み流せません）':
        '\\\\c needs one letter after it, and the u flag stops it from being read as plain text',
    '符号位置が大きすぎます（上限は 10FFFF）': 'code point is too large (the maximum is 10FFFF)',
    'u フラグがあるときは「': 'with the u flag, "',
    '」をそのまま書けません（\\\\ を前に付けます）': '" has to be escaped with a backslash',
    'u フラグがあるときは「\\\\': 'with the u flag, "\\\\',
    '」とは書けません（意味のないエスケープ）': '" is not a valid escape',
    'ブラウザがこの式を受け付けませんでした: ': 'the browser refused this pattern: ',

    # 箱の中の説明
    '数字': 'a digit',
    '数字以外': 'not a digit',
    '英数字か _': 'letter, digit or _',
    '英数字と _ 以外': 'not a letter, digit or _',
    '空白': 'whitespace',
    '空白以外': 'not whitespace',
    '改行以外の1文字': 'any char but a newline',
    'この分類の1文字': 'one char of this class',
    'どれか1文字': 'one of these',
    '1文字': 'this one char',
    'これ以外の1文字': 'any char but these',
    '先頭': 'start',
    '末尾': 'end',
    '単語の境目': 'word boundary',
    '境目以外': 'not a boundary',
    'と同じ文字列': ' — same text as that group',
    '番': '',
    '① グループ': 'group',
    ' グループ': ' group',
    'グループ': 'group',
    '直後にある（先読み）': 'must follow (lookahead)',
    '直後にない（否定先読み）': 'must not follow (negative lookahead)',
    '直前にある（後読み）': 'must precede (lookbehind)',
    '直前にない（否定後読み）': 'must not precede (negative lookbehind)',

    # くり返しの脇に出る文字
    '0回以上': '0 or more',
    '1回以上': '1 or more',
    '回まで': ' times at most',
    '回ちょうど': ' times exactly',
    '回以上': ' or more times',
    '回': ' times',
    '最小一致': 'lazy',
    '・最小一致': ', lazy',

    # 読み下し
    '<span class="k">（何もない）</span>': '<span class="k">(nothing)</span>',
    ' という文字': ' — this character',
    ' という文字の並び': ' — these characters in this order',
    ' 改行以外の任意の1文字': ' any single character except a newline',
    # 「\d 数字の1文字」の「の1文字」。英語では \d と "a digit" だけで足りるので空にする
    'の1文字': '',
    ' この分類に入る1文字': ' one character in this Unicode class',
    '行または文字列の先頭（文字は消費しません）':
        'the start of the string, or of a line with the m flag (consumes nothing)',
    '行または文字列の末尾（文字は消費しません）':
        'the end of the string, or of a line with the m flag (consumes nothing)',
    '単語の境目（文字は消費しません）': 'a word boundary (consumes nothing)',
    '単語の境目でないところ': 'a position that is not a word boundary',
    ' がマッチしたのと同じ文字列': ' matched, again — the same text',
    'これらのどれか1文字': ' one character from this set',
    'これら以外の1文字': ' one character that is not in this set',
    '次のどれか<ul>': 'any one of the following<ul>',
    '順に並ぶ<ul>': 'these, in order<ul>',
    ' 番のグループ（あとで ': ' capture group (available afterwards as ',
    ' で参照できます）': ')',
    ' 名前つきグループ「': ' named group "',
    'まとめるだけのグループ（番号は付きません）': 'a group used only for grouping (it gets no number)',
    '直後がこうなっていること（先読み・文字は消費しません）':
        'what follows has to look like this (lookahead — consumes nothing)',
    '直後がこうなっていないこと（否定先読み・文字は消費しません）':
        'what follows must not look like this (negative lookahead — consumes nothing)',
    '直前がこうなっていること（後読み・文字は消費しません）':
        'what comes before has to look like this (lookbehind — consumes nothing)',
    '直前がこうなっていないこと（否定後読み・文字は消費しません）':
        'what comes before must not look like this (negative lookbehind — consumes nothing)',
    'あってもなくてもよい': 'optional — it may be there or not',
    '0回以上のくり返し': 'repeated 0 or more times',
    '1回以上のくり返し': 'repeated 1 or more times',
    ' を <b>': ' — <b>',
    '（最小一致＝できるだけ短く取る）': ' (lazy — takes as little as it can)',

    # 落とし穴
    'くり返しの中にくり返しがあります（破滅的バックトラック）':
        'a repeat inside a repeat (catastrophic backtracking)',
    '</code> のように、くり返しの中がさらにくり返しになっていると、':
        '</code> repeats something that already repeats. When that happens, ',
    '<b>マッチしない入力</b>を与えたときに試す組み合わせが指数的に増えることがあります。':
        'the number of ways to split the input can grow exponentially <b>on input that does not match</b>. ',
    '<code>(a+)+$</code> に <code>aaaaaaaaaaaaaaaaaaaaX</code> を当てると固まる、あの形です。':
        'This is the shape that hangs when you run <code>(a+)+$</code> against <code>aaaaaaaaaaaaaaaaaaaaX</code>. ',
    '内側と外側で「どこまで取るか」の分け方が何通りもあるのが原因なので、':
        'The cause is that the inner and outer repeats can divide the same text in many ways, so ',
    '内側を <code>[^…]</code> のように<b>次に来る文字を含まない集合</b>にして、分け方を1通りにするのが定石です。':
        'the usual fix is to make the inner part a set that <b>excludes whatever comes next</b>, such as <code>[^...]</code>, which leaves exactly one way to divide it.',
    '中身が空でも通るのに、くり返しています': 'repeating something that can match nothing',
    '</code> は、中身が0文字でも成立します。':
        '</code> succeeds even when it consumes no characters. ',
    '進まないまま回り続ける形なので、意図しない空マッチや、実装によっては停止しない原因になります。':
        'It can loop without moving forward, which leads to surprise empty matches and, in some engines, to a loop that never ends. ',
    'くり返しの中の <code>?</code> や <code>*</code> を外して、外側だけでくり返す形にできないか確かめてください。':
        'See whether the inner <code>?</code> or <code>*</code> can be dropped so that only the outer part repeats.',
    '<code>.</code> は改行にマッチしません': '<code>.</code> does not match a newline',
    '既定では <code>.</code> は改行（<code>\\\\n</code>）以外の1文字です。':
        'By default <code>.</code> is any character except a newline (<code>\\\\n</code>). ',
    '複数行のテキストを丸ごと取りたいなら <code>s</code> フラグ（dotAll）を付けるか、':
        'To take multi-line text in one go, add the <code>s</code> flag (dotAll), or write ',
    '<code>[\\\\s\\\\S]</code> と書きます。': '<code>[\\\\s\\\\S]</code> instead.',
    '<code>^</code> と <code>$</code> は「文字列の」先頭と末尾です':
        '<code>^</code> and <code>$</code> mean the ends of the <i>string</i>, not of a line',
    '<code>m</code> フラグが無いので、行ごとではなく<b>文字列全体</b>の先頭・末尾を指します。':
        'There is no <code>m</code> flag, so they mark the start and end of <b>the whole string</b>. ',
    '行単位で当てたいなら <code>m</code> を付けてください。':
        'Add <code>m</code> if you want them to work line by line. ',
    'なお <code>$</code> は、<code>m</code> があるときだけ改行の直前にも当たります。':
        'Note that <code>$</code> matches just before a newline only when <code>m</code> is on.',
    '<code>\\\\b</code> の「単語」は英数字と <code>_</code> だけです':
        'the "word" in <code>\\\\b</code> means only letters, digits and <code>_</code>',
    '<code>\\\\b</code> は <code>\\\\w</code>（<code>[A-Za-z0-9_]</code>）とそれ以外の境目を指します。':
        '<code>\\\\b</code> sits between <code>\\\\w</code> (<code>[A-Za-z0-9_]</code>) and anything else. ',
    '日本語には <code>\\\\w</code> に入る文字が無いので、':
        'Scripts without those characters, such as Japanese or Chinese, contain no <code>\\\\w</code> at all, ',
    '<b>ひらがなや漢字の切れ目では思ったところに境目ができません</b>。':
        'so <b>no boundary appears where you would expect one between words</b>.',
    'ASCII 以外の文字があるのに <code>u</code> フラグがありません':
        'there are non-ASCII characters but no <code>u</code> flag',
    '<code>u</code> フラグが無いと、絵文字や一部の漢字（サロゲートペアで表される文字）は':
        'Without the <code>u</code> flag, emoji and other characters made of a surrogate pair are ',
    '<b>2つの単位</b>として扱われます。<code>.</code> が半分だけにマッチしたり、':
        'treated as <b>two units</b>. <code>.</code> can match half of one, and ',
    '文字クラスの範囲指定が思った通りに働かなかったりします。':
        'ranges inside a character class stop behaving the way you expect.',
    '<code>|</code> は式全体を分けます': '<code>|</code> splits the whole pattern',
    '<code>|</code> の優先順位はいちばん低いので、<code>^a|b$</code> は ':
        '<code>|</code> binds the loosest of everything, so <code>^a|b$</code> means ',
    '<code>(^a)|(b$)</code> であって <code>^(a|b)$</code> ではありません。':
        '<code>(^a)|(b$)</code>, not <code>^(a|b)$</code>. ',
    '<b>図の分岐が式全体を割っていないか</b>を上の図で確かめてください。':
        'Check the diagram above to see <b>whether the branch cuts across the entire pattern</b>. ',
    '分けたい範囲は <code>(?:…)</code> で囲みます。':
        'Wrap the part you actually want to split in <code>(?:...)</code>.',
    'グループが ': 'there are ',
    ' 個あります': ' capture groups',
    'まとめたいだけで取り出す気がないグループは <code>(?:…)</code> にしておくと、':
        'Writing <code>(?:...)</code> for the groups you never read back means ',
    '<b>あとから括弧を足したときに番号がずれません</b>。番号は上の一覧のとおりです。':
        '<b>the numbers do not shift when you add another pair of parentheses later</b>. The current numbering is in the table above.',
    '文字クラスの中では <code>. + * ?</code> はただの文字です':
        'inside a character class, <code>. + * ?</code> are ordinary characters',
    '<code>[.]</code> は「任意の1文字」ではなく「ピリオド1文字」です。':
        '<code>[.]</code> means one period, not any character. ',
    '同じく <code>[+*?]</code> はその記号そのものを指します。エスケープは要りません':
        'In the same way <code>[+*?]</code> means those three symbols themselves. No escaping is needed ',
    '（付けても同じ意味になります）。': '(escaping them changes nothing).',
    '文字クラスの末尾の <code>-</code> はハイフンそのものです':
        'a <code>-</code> at the end of a character class is a plain hyphen',
    '<code>-</code> を範囲の意味にしたくないときは、クラスの<b>先頭か末尾</b>に置くか、':
        'To keep <code>-</code> from forming a range, put it <b>first or last</b> in the class, or write ',
    '<code>\\\\-</code> と書きます。': '<code>\\\\-</code>.',
    '最小一致（<code>*?</code>）を使っています': 'this pattern uses a lazy quantifier (<code>*?</code>)',
    '最小一致は「短いほうから試す」だけで、<b>いちばん短い一致を保証するものではありません</b>。':
        'Lazy only means "try the shorter option first"; it <b>does not guarantee the shortest match overall</b>. ',
    '左から順に位置を試すので、開始位置は変わらないまま長さだけが短くなります。':
        'Starting positions are still tried left to right, so only the length gets shorter, never the starting point.',
    '大文字と小文字は別扱いです': 'upper and lower case are different characters here',
    '<code>i</code> フラグが無いので、<code>A</code> と <code>a</code> は違う文字として扱われます。':
        'There is no <code>i</code> flag, so <code>A</code> and <code>a</code> do not match each other.',

    # SVG の代替テキスト
    '" role="img" aria-label="正規表現の鉄道図">':
        '" role="img" aria-label="railroad diagram of the regular expression">',

    # 全角の記号だけの断片（見落としやすいのでまとめて）
    '「': '"',
    '」': '"',
    '）': ')',
    '〜': ' to ',

    # ── ここから下は画面まわり（CORE の外なので、コードの一致には関係しない）──
    '日付': 'Date',
    '郵便番号': 'Postcode',
    '時刻': 'Time of day',
    'メールらしきもの': 'Email-ish',
    '16進の色': 'Hex color',
    'HTMLのタグ': 'HTML tag',
    '分岐と後読み': 'Branch and lookbehind',
    '(?<=¥)\\\\d+(?:,\\\\d{3})*(?:円|エン)?': '(?<=\\\\$)\\\\d+(?:,\\\\d{3})*(?:\\\\.\\\\d{2})?',
    '危ない形': 'A dangerous shape',
    '式が読めないので、例は作れません。': 'The pattern does not parse, so no examples can be built.',
    '<p class="lead">この式は図にするには入り組みすぎています（':
        '<p class="lead">This pattern is too tangled to draw (',
    '）。読み下しのほうを見てください。</p>': '). Read the plain-English version below instead.</p>',
    '<tr><th>番号</th><th>名前</th><th>中身</th></tr>':
        '<tr><th>No.</th><th>Name</th><th>Contents</th></tr>',
    '置換では ': 'In a replacement these are ',
    '・': ', ',
    ' で使えます。番号は<b>開き括弧の出てくる順</b>です。':
        '. Groups are numbered <b>in the order their opening parenthesis appears</b>.',
    '<li class="i"><b>目についた落とし穴はありません</b>この道具が見ているのは':
        '<li class="i"><b>Nothing stood out</b>This page only looks for ',
    'よくある形だけです。安全だと保証するものではありません。</li>':
        'the common traps. That is not a guarantee that the pattern is safe.</li>',
    ' 件は当たりませんでした。</b>この式には<b>文字を消費しない条件</b>':
        ' examples did not match.</b> This pattern contains a <b>condition that consumes no characters</b> ',
    '（先読み・後読み）が入っているので、図に写っている部分だけを組み立てても':
        '(a lookahead or lookbehind), so a string assembled from the visible parts of the diagram alone ',
    'その条件は満たせません。<b>式の誤りではありません。</b>':
        'cannot satisfy it. <b>This is not a fault in your pattern.</b> ',
    '当たった例と当たらなかった例の違いを見ると、その条件が何を要求しているかが分かります。':
        'Comparing the examples that matched against the ones that did not shows what the condition is asking for.',
    ' 件が食い違いました。</b>図の読み方か、この道具の解析のどちらかが間違っています。':
        ' examples disagreed.</b> Either the diagram is being read wrongly or this page parsed the pattern wrongly. ',
    'このページの不具合なので、式のほうは疑わなくて大丈夫です。':
        'That is a bug on this page, so there is no need to doubt your expression.',
    '例を作れませんでした（この式に当てはまる文字列を組み立てられませんでした）。':
        'No examples could be built (no string matching this pattern could be assembled).',
    ' 件すべてマッチしました。</b>': ' examples, all matched.</b> ',
    '先読み・後読みなど「文字を消費しない条件」が入っているので、':
        'The pattern contains conditions that consume no characters, such as a lookahead or lookbehind, so ',
    '例が必ずマッチするとは限りません（マッチしない例が混ざることがあります）。':
        'the examples are not guaranteed to match and some of them may not.',
    '図のとおりに作った文字列は、元の正規表現にそのまま当たります。':
        'Strings assembled by following the diagram land on your original expression as they are.',
    'なおこの式は外れたときに時間が跳ねる形なので、':
        'Note that this pattern is the shape whose running time explodes on a near miss, so ',
    '例は短いものだけに絞っています。': 'only short examples are used here.',
    '<span class="lead">（空文字）</span>': '<span class="lead">(empty string)</span>',
}


def drop_comments(s):
    """コメントを外す。コード中の日本語コメントは英語版でもそのまま残す方針なので、
    「日本語が残っていないか」の検査からは外す（en/csv.html も同じ方針）。"""
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    # 行末コメント。URL の // を巻き込まないよう、直前がコロンのものは外さない
    return re.sub(r'(?m)(?<!:)//.*$', '', s)


def strip_literals(s):
    """引用符で囲まれた中身を消す。コードの骨格だけが残るので、日英で比べられる。"""
    return re.sub(r"'[^'\n]*'", "''", s)


def core_of(html):
    return html.split('/*==CORE-START==*/')[1].split('/*==CORE-END==*/')[0]


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'docs')
    ja_path = docs / 'railroad' / 'index.html'
    en_path = docs / 'en' / 'railroad.html'
    ja = ja_path.read_text(encoding='utf-8')

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit('HTMLの差し替え元が見つかりません:\n' + a[:120])
        en = en.replace(a, b, 1)
    for a, b in sorted(TR.items(), key=lambda kv: -len(kv[0])):
        en = en.replace("'" + a + "'", "'" + b + "'")

    # 1) 画面に出るところに日本語が残っていないか（コメントは対象外）
    # 仮名・漢字だけ見ていると、句読点や全角括弧（、。「」（））が素通りする。
    # 実際に約物を残したまま本番に出した（2026-08-23）ので約物も見る。
    left = re.findall('[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？]+', drop_comments(en))
    if left:
        sys.exit('日本語が %d 箇所残っています: %s' % (len(left), left[:8]))

    # 2) 文字列リテラルを外したコードが日本語版と一致するか
    a, b = strip_literals(core_of(ja)), strip_literals(core_of(en))
    if a != b:
        for k, (x, y) in enumerate(zip(a.split('\n'), b.split('\n'))):
            if x != y:
                sys.exit('コードが一致しません（%d行目）:\n  ja: %s\n  en: %s' % (k + 1, x, y))
        sys.exit('コードの行数が違います（ja %d / en %d）' % (a.count('\n'), b.count('\n')))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    # ★（2026-09-03 夜）CSS のコメントも訳す（<script> の外なので誰も見ていなかった）
    en, css_missing = translate_css_comments(en)
    if css_missing:
        sys.exit("CSS のコメントの訳し漏れ %d 件:\n  %s"
                 % (len(css_missing), "\n  ".join(x[:100] for x in css_missing[:8])))

    en_path.write_text(en, encoding='utf-8')
    print('書き出した: %s' % en_path)
    print('日本語の残り: 0箇所')
    print('文字列リテラルを外したコード: 日英でバイト単位で一致（%d バイト）' % len(a.encode()))


# ── HTML の差し替え（長いのでファイル末尾に置く）────────────────────────────
SITE = 'https://hirulab-dev.github.io/hirulab-tools'
HTML_PARTS = [
 ('<html lang="ja">', '<html lang="en">'),

 ('<title>正規表現を鉄道図にする — 図・読み下し・落とし穴の検出</title>',
  '<title>Regex Railroad Diagrams — draw it, read it, and catch the traps</title>'),

 ('<meta name="description" content="正規表現を鉄道図（railroad diagram）に描き、日本語に読み下し、キャプチャ番号を並べます。破滅的バックトラックや「日と曜日」ならぬ「. は改行にマッチしない」といった落とし穴も自動で指摘します。さらに図から例文字列を作り、その場でマッチするか確かめて図と式が食い違っていないことを見せます。ブラウザ内で完結し、データはどこにも送信されません。">',
  '<meta name="description" content="Turn a regular expression into a railroad diagram, read it back in plain English, and list its capture groups. Traps such as catastrophic backtracking, or the fact that . never matches a newline, are pointed out automatically. The page then builds example strings from the diagram and tests them against your pattern, so you can see the drawing and the expression agree. Everything runs in the browser and nothing is uploaded.">'),

 ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/railroad/">',
  '<link rel="canonical" href="%s/en/railroad.html">' % SITE),

 ('<link rel="alternate" hreflang="ja" href="%s/railroad/">' % SITE,
  '<link rel="alternate" hreflang="ja" href="%s/railroad/">' % SITE),
 ('<meta property="og:locale" content="ja_JP">', '<meta property="og:locale" content="en_US">'),
 ('<meta property="og:site_name" content="クロードの昼ラボ">',
  '<meta property="og:site_name" content="Claude\'s Daytime Lab">'),
 ('<meta property="og:title" content="正規表現を鉄道図にする — 図・読み下し・落とし穴の検出">',
  '<meta property="og:title" content="Regex Railroad Diagrams — draw it, read it, and catch the traps">'),
 ('<meta property="og:description" content="正規表現を鉄道図に描き、日本語に読み下し、キャプチャ番号を並べます。破滅的バックトラック等の落とし穴も自動指摘。図から例文字列を作って、その場で図と式が食い違っていないか確かめます。ブラウザ内で完結します。">',
  '<meta property="og:description" content="Draw a regular expression as a railroad diagram, read it back in plain English, and list its capture groups. Traps are flagged automatically, and example strings built from the diagram are tested against the pattern on the spot. Runs entirely in your browser.">'),
 ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/railroad/">',
  '<meta property="og:url" content="%s/en/railroad.html">' % SITE),
 ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-railroad.png">',
  '<meta property="og:image" content="%s/ogp/ogp-railroad-en.png">' % SITE),
 ('<meta name="twitter:title" content="正規表現を鉄道図にする — 図・読み下し・落とし穴の検出">',
  '<meta name="twitter:title" content="Regex Railroad Diagrams">'),
 ('<meta name="twitter:description" content="正規表現を鉄道図に描いて日本語に読み下し、落とし穴を自動で指摘します。図から例文字列を作って、その場で図と式が合っているか確かめます。ブラウザ内で完結します。">',
  '<meta name="twitter:description" content="Draw a regular expression as a railroad diagram, read it back in plain English, and catch the traps. Example strings built from the diagram are tested against the pattern on the spot.">'),
 ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-railroad.png">',
  '<meta name="twitter:image" content="%s/ogp/ogp-railroad-en.png">' % SITE),

 ('''  "name": "正規表現を鉄道図にする",
  "url": "https://hirulab-dev.github.io/hirulab-tools/railroad/",
  "description": "正規表現を鉄道図（railroad diagram）に描き、日本語に読み下し、キャプチャ番号を一覧にします。破滅的バックトラックや、. が改行にマッチしないといった落とし穴を自動で検出します。図から例文字列を生成してその場でマッチを確かめるため、図と式が食い違っていないことを確認できます。ブラウザ内で完結します。",''',
  '''  "name": "Regex Railroad Diagrams",
  "url": "%s/en/railroad.html",
  "description": "Turn a regular expression into a railroad diagram, read it back in plain English, and list its capture groups. Traps such as catastrophic backtracking, or the fact that . never matches a newline, are detected automatically. Example strings are generated from the diagram and tested against the pattern, so you can confirm the drawing and the expression agree. Runs entirely in the browser.",''' % SITE),
 ('  "inLanguage": "ja",', '  "inLanguage": "en",'),
 ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
  '  "browserRequirements": "A modern browser with JavaScript enabled",'),
 ('  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "JPY" },',
  '  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },'),
 ('  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },',
  '  "author": { "@type": "Organization", "name": "Claude\'s Daytime Lab", "url": "%s/en/" },' % SITE),
 ('  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }',
  '  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — Tools", "url": "%s/en/" }' % SITE),

 ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>正規表現を鉄道図にする</h1>
  <p class="lead">正規表現を<strong>鉄道図</strong>（線路のように分岐とループで描いた図）にして、
    <strong>日本語の読み下し</strong>と<strong>キャプチャ番号</strong>を並べます。
    <code>(a+)+</code> のような<strong>破滅的バックトラック</strong>や、
    <code>.</code> が改行にマッチしないことなど、当てはまる落とし穴は自動で指摘します。
    さらに<strong>図から例文字列を作って、その場でマッチするか確かめます</strong>
    （図と式が食い違っていたら、そこで分かります）。</p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    解析も作図もすべてブラウザの中でやっています。読み込んだあとは機内モードでも動きます。
    入力した正規表現がどこかに送られることはありません。
  </div>''',
  '''  <a class="hl-back" href="./">&larr; Claude\'s Daytime Lab — Tools</a>
  <h1>Regex Railroad Diagrams</h1>
  <p class="lead">Turn a regular expression into a <strong>railroad diagram</strong> &mdash; branches and loops
    drawn like track &mdash; next to a <strong>plain-English reading</strong> and its
    <strong>capture groups</strong>. Traps that apply to your pattern are called out:
    <strong>catastrophic backtracking</strong> in shapes like <code>(a+)+</code>, the fact that
    <code>.</code> never matches a newline, and more.
    The page also <strong>builds example strings from the diagram and tests them against your pattern</strong>,
    so if the drawing and the expression disagree, you find out here.</p>

  <div class="privacy">
    <strong>This page makes no network requests.</strong>
    Parsing and drawing both happen inside your browser. Once loaded it works offline,
    and the pattern you type is never sent anywhere.
  </div>'''),

 ('''      <input type="text" id="pat" spellcheck="false" autocapitalize="off" autocorrect="off"
             autocomplete="off" value="^(\\d{4})-(\\d{2})-(\\d{2})$">''',
  '''      <input type="text" id="pat" spellcheck="false" autocapitalize="off" autocorrect="off"
             autocomplete="off" value="^(\\d{4})-(\\d{2})-(\\d{2})$" aria-label="regular expression">'''),

 ('    <label for="pat" class="hide">正規表現</label>\n    <label for="flags" class="hide">フラグ</label>',
  '    <label for="pat" class="hide">Regular expression</label>\n    <label for="flags" class="hide">Flags</label>'),

 ('    <h2>鉄道図</h2>', '    <h2>Railroad diagram</h2>'),
 ('    <h2>読み下し</h2>', '    <h2>In plain English</h2>'),
 ('    <h2>キャプチャ</h2>', '    <h2>Capture groups</h2>'),
 ('    <h2>気をつけるところ</h2>', '    <h2>Things to watch out for</h2>'),
 ('    <h2>図から作った例で確かめる</h2>', '    <h2>Check it with examples built from the diagram</h2>'),

 ('''    <p class="lead" style="margin:10px 0 0">
      図（＝解析した構造）だけを見て文字列を組み立て、それを<strong>元の正規表現そのもの</strong>に
      当てています。全部 ✓ なら、図の読み方と式の意味はここまでは食い違っていません。
      文字列を入れて試したいときは <a href="../regex/">正規表現テスタ</a> へ。
    </p>''',
  '''    <p class="lead" style="margin:10px 0 0">
      Each example is assembled from the parsed structure alone &mdash; the same structure the diagram
      is drawn from &mdash; and then tested against <strong>your original expression</strong>.
      All ticks means the way the diagram reads and the way the pattern behaves have not diverged.
      To try your own strings, use the <a href="./regex-tester.html">Regex Tester</a>.
    </p>'''),

 ('''    <summary>この図の読み方と、作りの話</summary>
    <ul>
      <li><b>線をたどれる形にマッチする</b>: 左の <code>▶</code> から右の <code>◀</code> まで、
        線に沿って通った箱の中身をつなげたものが、この正規表現にマッチする文字列です。
        分岐はどれか1つを選び、ループは戻ってきた回数だけくり返します。</li>
      <li><b>上が既定の道</b>: 分岐は上から順に試されます（正規表現の <code>|</code> は左から順）。
        ループの脇に「最小一致」と出ているときは、<code>*?</code> のように
        <b>できるだけ回らない</b>ほうを先に試します。</li>
      <li><b>破線の箱</b>: グループです。丸数字が付いているものは
        <code>\\1</code> や <code>$1</code> で後から参照できます。
        オレンジの破線は<b>先読み・後読み</b>で、
        <b>条件を見るだけで文字を消費しません</b>（通っても位置が進みません）。</li>
      <li><b>作り</b>: 正規表現の解析も作図もライブラリなしの自前です。
        図は SVG を組み立てて描いています。箱の幅は
        <code>canvas</code> の文字幅測定で実際に測っているので、フォントが変わってもはみ出しません。</li>
      <li><b>確かめかた</b>: 解析結果から例文字列を作り、
        <b>元の正規表現に当て直して</b>マッチするかをその場で見ています（上の欄）。
        加えて、ランダムに作った正規表現で
        「自前の解析が受け付ける／拒む」がブラウザの <code>RegExp</code> と一致するかを
        まとめて突き合わせる検証を <a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>側に置いています。</li>
      <li><b>対応していないもの</b>: <code>v</code> フラグの文字クラスの集合演算、
        <code>\\p{...}</code> の細かい分類は、図では1つの箱にまとめて表示します。
        図が描けないほど複雑なときは、その旨を出します。</li>
    </ul>''',
  '''    <summary>How to read the diagram, and how it is built</summary>
    <ul>
      <li><b>Anything you can trace matches</b>: follow the line from the <code>&#9654;</code> on the left
        to the <code>&#9664;</code> on the right, and the boxes you pass through, concatenated,
        form a string this expression matches. At a branch you take exactly one path;
        at a loop you repeat as many times as you go around.</li>
      <li><b>The top path is tried first</b>: branches are attempted top to bottom, matching the way
        <code>|</code> is tried left to right. Where a loop is labelled <b>lazy</b>, as with
        <code>*?</code>, the engine tries <b>going around as few times as possible</b> first.</li>
      <li><b>Dashed boxes</b> are groups. Numbered ones can be referred to afterwards as
        <code>\\1</code> or <code>$1</code>. An orange dashed box is a <b>lookahead or lookbehind</b>:
        it <b>checks a condition without consuming any characters</b>, so passing through it
        does not move the position forward.</li>
      <li><b>How it is built</b>: the parser and the drawing are both written from scratch, no libraries.
        The diagram is assembled as SVG, and every box is sized by <b>measuring the text</b> with
        <code>canvas</code>, so nothing overflows when the font differs.</li>
      <li><b>How it is checked</b>: examples are built from the parse result and tested against
        <b>your original expression</b> on the spot (the panel above). On top of that, a script in the
        <a href="https://github.com/hirulab-dev/hirulab-tools">source repository</a> feeds thousands of
        randomly generated patterns through both this parser and the browser&#39;s own
        <code>RegExp</code>, and checks that they accept and reject exactly the same ones.</li>
      <li><b>Not covered</b>: set operations in <code>v</code>-flag character classes and the finer
        <code>\\p{...}</code> categories are shown as a single box rather than expanded.
        If a pattern is too tangled to draw, the page says so instead of drawing something wrong.</li>
    </ul>'''),

 ('''  <nav class="hl-nav">
    <h2>ほかの道具</h2>
    <ul>
      <li><a href="../regex/">正規表現テスタ</a></li>
      <li><a href="../char-counter/">文字数カウンタ</a></li>
      <li><a href="../contrast/">コントラスト比チェッカー</a></li>
      <li><a href="../date/">日付計算機</a></li>
      <li><a href="../image/">画像リサイズ・圧縮</a></li>
      <li><a href="../take-home/">手取り計算機</a></li>
      <li><a href="../json/">JSON整形・検証</a></li>
      <li><a href="../diff/">テキスト差分（diff）</a></li>
      <li><a href="../unit/">単位換算</a></li>
      <li><a href="../page-contrast/">ページまるごとコントラスト診断</a></li>
      <li><a href="../qr/">QRコード作成</a></li>
      <li><a href="../palette/">カラーパレット生成</a></li>
      <li><a href="../frima-profit/">フリマ利益計算機</a></li>
      <li><a href="../cron/">cron式の読み下し</a></li>
      <li><a href="../tz/">タイムゾーン変換</a></li>
      <li><a href="../csv/">CSVプレビュー・診断</a></li>
      <li><a href="../url/">URLの分解・組み立て</a></li>
      <li><a href="../headers/">HTTPヘッダの読み下し</a></li>
      <li><a href="../regex-why/">正規表現がなぜマッチしないか診断</a></li>
      <li><a href="../replace/">正規表現の置換プレビュー</a></li>
      <li><a href="../jwt/">JWTの読み下し</a></li>
      <li><a href="../password/">パスワード生成・強度診断</a></li>
      <li><a href="../base64/">Base64・データURLの分解</a></li>
      <li><a href="../pattern/">和柄シームレスパターン作成</a></li>
      <li><a href="../en/railroad.html">English version</a></li>
    </ul>
    <p class="hl-links">
      <a href="../">道具箱のトップ</a> ・
      <a href="https://note.com/hirulab">実験ログ（note）</a> ・
      <a href="https://x.com/hirulab_ai">X</a> ・
      <a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>
    </p>
  </nav>

  <footer>
    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    図は JavaScript の正規表現（ECMAScript）の書き方に合わせています。
    Python や PCRE では意味が違う記号があるので、他の言語で使うときは確かめてください。
  </footer>''',
  '''  <nav class="hl-nav">
    <h2>Other tools</h2>
    <ul>
      <li><a href="./regex-why.html">Why doesn&#39;t my regex match?</a></li>
      <li><a href="./replace.html">Regex Replacement Preview</a></li>
      <li><a href="./regex-tester.html">Regex Tester</a></li>
      <li><a href="./char-counter.html">Character Counter</a></li>
      <li><a href="./palette.html">Color Palette Generator</a></li>
      <li><a href="./timezone.html">Time Zone Converter</a></li>
      <li><a href="./csv.html">CSV Preview &amp; Diagnostics</a></li>
      <li><a href="./url.html">URL Parser &amp; Builder</a></li>
      <li><a href="./headers.html">HTTP Header Explainer</a></li>
      <li><a href="./jwt.html">JWT Explainer</a></li>
      <li><a href="./password.html">Password Generator &amp; Strength Check</a></li>
      <li><a href="./base64.html">Base64 &amp; Data URL Explainer</a></li>
      <li><a href="./qr.html">QR Code Generator</a></li>
      <li><a href="./cron.html">Cron Expression Explainer</a></li>
      <li><a href="./contrast.html">Contrast Ratio Checker</a></li>
      <li><a href="./image.html">Image Resizer &amp; Compressor</a></li>
      <li><a href="./page-contrast.html">Whole-Page Contrast Audit</a></li>
      <li><a href="./diff.html">Text Diff</a></li>
      <li><a href="./json.html">JSON Formatter &amp; Validator</a></li>
      <li><a href="./unit.html">Unit Converter</a></li>
      <li><a href="./pattern.html">Japanese Pattern Generator</a></li>
      <li><a href="./date.html">Japanese Date Calculator</a></li>
      <li><a href="./take-home.html">Japan Take-Home Pay Calculator</a></li>
      <li><a href="./frima-profit.html">Flea-Market Profit Calculator</a></li>
      <li><a href="../railroad/">Japanese version</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">All tools</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>

  <footer>
    Built by Claude&#39;s Daytime Lab (an AI, Claude). Free, no sign-up.
    The diagram follows JavaScript&#39;s flavour of regular expressions (ECMAScript).
    A few symbols mean something different in Python or PCRE, so check before carrying a pattern across.
  </footer>'''),
]

if __name__ == '__main__':
    main()
