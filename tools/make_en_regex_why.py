#!/usr/bin/env python3
"""「なぜマッチしないか診断」の英語版を、日本語版から作る（2026-08-23）。

`make_en_railroad.py` と同じ方式。**日本語版が唯一の原本**で、英語版は毎回ここから作り直す。

やっていること
1. HTML（head・本文・ナビ・解説）を英語の版に差し替える
2. スクリプトの中の**引用符で囲まれた文字列だけ**を英語に差し替える
   （解析器の部分は鉄道図と同じソースなので、**訳語も鉄道図の表をそのまま使う**）
3. できた英語版について、**「文字列リテラルを全部取り除くと日本語版とバイト単位で一致する」**
   ことを確かめる。通れば、照合器・診断・当て直しのコードは1バイトも違わないと言い切れる
4. 画面に出るところに日本語が1文字も残っていないことを確かめる（コードのコメントは対象外）

使い方: python lab/scripts/make_en_regex_why.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from make_en_railroad import TR as PARSER_TR   # 解析器の訳語は鉄道図と共有する

SITE = "https://hirulab-dev.github.io/hirulab-tools"

# ── この道具だけが持つ文字列 ───────────────────────────────────────────────
OWN = {
    # 待っていたものの言い方
    '数字（0〜9）': 'a digit (0-9)',
    '数字以外の文字': 'a character that is not a digit',
    '英数字か <code>_</code>': 'a letter, a digit, or <code>_</code>',
    '英数字と <code>_</code> 以外の文字': 'a character other than a letter, digit, or <code>_</code>',
    '空白': 'whitespace',
    '空白以外の文字': 'a character that is not whitespace',
    '任意の1文字（<code>s</code> フラグがあるので改行も含む）':
        'any single character (the <code>s</code> flag makes newlines count too)',
    '任意の1文字（改行以外）': 'any single character except a newline',
    '</code> に当てはまる1文字': '</code>',
    '行の先頭': 'the start of a line',
    '文字列の先頭': 'the start of the string',
    '行の末尾': 'the end of a line',
    '文字列の末尾': 'the end of the string',
    '単語の境目': 'a word boundary',
    '単語の境目でないこと': 'not a word boundary',
    '前に取ったグループと同じ文字列': 'the same text a group captured earlier',
    '</code>（先読み）が成り立つこと': '</code> (lookahead) to hold here',
    '</code>（否定先読み）が成り立たないこと': '</code> (negative lookahead) not to hold here',
    '</code>（後読み）が成り立つこと': '</code> (lookbehind) to hold here',
    '</code>（否定後読み）が成り立たないこと': '</code> (negative lookbehind) not to hold here',

    # 文字の名前
    'タブ': 'tab',
    '改行（LF）': 'line feed (LF)',
    '復帰（CR）': 'carriage return (CR)',
    '半角スペース': 'space',
    'ノーブレークスペース': 'no-break space',
    '全角スペース': 'ideographic space',
    'ゼロ幅スペース': 'zero-width space',
    'ゼロ幅非接合子': 'zero-width non-joiner',
    'ゼロ幅接合子': 'zero-width joiner',
    'ワードジョイナー': 'word joiner',
    'BOM／ゼロ幅ノーブレークスペース': 'BOM / zero-width no-break space',
    'ハイフン（U+2010）': 'hyphen (U+2010)',
    'ノーブレークハイフン': 'non-breaking hyphen',
    'フィギュアダッシュ': 'figure dash',
    'エヌダッシュ': 'en dash',
    'エムダッシュ': 'em dash',
    '水平バー': 'horizontal bar',
    'マイナス記号（U+2212）': 'minus sign (U+2212)',
    '全角ハイフンマイナス': 'fullwidth hyphen-minus',
    '左シングルクォート': 'left single quotation mark',
    '右シングルクォート': 'right single quotation mark',
    '左ダブルクォート': 'left double quotation mark',
    '右ダブルクォート': 'right double quotation mark',
    '制御文字（': 'control character (',
    '」全角（': '" fullwidth (',
    '」（': '" (',
    '。</li>': '.</li>',
    '異体字セレクタ（': 'variation selector (',

    # 紛れている文字の説明
    '改行コードが CRLF です。<code>$</code> や <code>\\\\n</code> の前に残ります':
        'the line ending is CRLF, so this stays in front of <code>$</code> and <code>\\\\n</code>',
    '全角スペースです。<code>\\\\s</code> には当たりますが半角スペースとは別の字です':
        'an ideographic space. <code>\\\\s</code> matches it, but it is not the same character as a plain space',
    'ノーブレークスペースです。見た目は半角スペースと同じです':
        'a no-break space. It looks exactly like a plain space',
    '幅を持たない文字です。画面には出ませんが1文字として数えられます':
        'a character with no width. Nothing is drawn, but it still counts as one character',
    '異体字セレクタです。直前の字の見た目を変えるだけの1文字です':
        'a variation selector: one character whose only job is to restyle the one before it',
    '全角の英数字・記号です。半角とは別の字です':
        'a fullwidth letter, digit, or symbol. Not the same character as the ASCII one',
    '見た目の似た別の記号です': 'a different symbol that looks almost the same',
    '制御文字です': 'a control character',

    # 直し方
    '<code>i</code> フラグを付ける': 'add the <code>i</code> flag',
    '大文字・小文字の違いだけで外れています。': 'only the letter case is different.',
    '<code>s</code> フラグ（dotAll）を付ける': 'add the <code>s</code> flag (dotAll)',
    '<code>.</code> は既定では改行に当たりません。改行をまたぎたいときは <code>s</code> を付けます。':
        '<code>.</code> does not match a newline by default. Add <code>s</code> to let it cross lines.',
    '<code>m</code> フラグを付ける': 'add the <code>m</code> flag',
    '<code>^</code> <code>$</code> は既定では文字列全体の端です。行ごとの端にしたいときは <code>m</code> を付けます。':
        '<code>^</code> and <code>$</code> mean the ends of the whole string by default. Add <code>m</code> to make them the ends of each line.',
    '<code>u</code> フラグを付ける': 'add the <code>u</code> flag',
    '<code>\\\\u{…}</code> や絵文字を1文字として扱いたいときに要ります。':
        'needed to treat <code>\\\\u{...}</code> and emoji as single characters.',
    '<code>u</code>（<code>v</code>）フラグを外す': 'drop the <code>u</code> (or <code>v</code>) flag',
    '<code>u</code> があると書けない書き方が増えます。':
        '<code>u</code> makes several otherwise-legal spellings illegal.',
    '<code>y</code>（sticky）フラグを外す': 'drop the <code>y</code> (sticky) flag',
    'sticky は決まった位置からしか試しません。どこでもよいなら外します。':
        'sticky only tries one fixed position. Drop it if any position will do.',
    '<code>^</code> <code>$</code> を外す': 'drop <code>^</code> and <code>$</code>',
    '端の指定を外すと当たります。＝<b>部分文字列としては入っている</b>けれど、':
        'it matches once the anchors are gone, which means <b>the text is in there as a substring</b> — ',
    '文字列全体がこの形ではない、ということです。': 'the whole string just is not shaped like this.',
    ' 文字目から「': ', matching "',
    '」に当たります': '"',
    '前後の空白を取り除く': 'trim the whitespace at the ends',
    '入力の前か後ろに空白（全角スペースを含む）が付いています。':
        'there is whitespace (an ideographic space counts) before or after the input.',
    '改行コードの <code>\\\\r</code> を取り除く': 'remove the <code>\\\\r</code> of a CRLF line ending',
    '改行が CRLF です。行末に <code>\\\\r</code> が残るので <code>$</code> や <code>\\\\n</code> の直前で外れます。':
        'the line endings are CRLF. The stray <code>\\\\r</code> sits right before <code>$</code> or <code>\\\\n</code> and breaks the match.',
    '全角の英数字・記号を半角にする（NFKC 正規化）':
        'convert fullwidth letters and symbols to ASCII (NFKC normalization)',
    '<code>\\uff11</code> や <code>\\uff0d</code> のような全角文字が混ざっています。<code>\\\\d</code> や <code>-</code> は当たりません。':
        'fullwidth characters such as <code>\\uff11</code> and <code>\\uff0d</code> are mixed in. <code>\\\\d</code> and <code>-</code> do not match them.',
    'ノーブレークスペースを半角スペースにする': 'replace no-break spaces with plain spaces',
    '見た目は半角スペースですが別の字（U+00A0）です。':
        'it looks like a space but it is a different character (U+00A0).',
    'ゼロ幅文字・BOM を取り除く': 'remove zero-width characters and the BOM',
    '画面に出ない文字が入っています。ファイルの先頭やコピー元から紛れ込みます。':
        'characters that draw nothing are in the input. They usually arrive from the top of a file or from whatever you copied.',
    '異体字セレクタを取り除く': 'remove variation selectors',
    '直前の字の見た目を変えるだけの文字が付いています。':
        'a character is attached whose only job is to restyle the one before it.',
    '見た目の似たダッシュを半角ハイフンにする': 'replace look-alike dashes with an ASCII hyphen',
    '<code>\\u2010</code> <code>\\u2013</code> <code>\\u2212</code> などは半角ハイフン <code>-</code> とは別の字です。':
        '<code>\\u2010</code>, <code>\\u2013</code> and <code>\\u2212</code> are not the ASCII hyphen <code>-</code>.',
    '引用符を半角にする': 'replace curly quotes with straight ones',
    '\\u201c \\u201d \\u2018 \\u2019 は <code>"</code> <code>&#39;</code> とは別の字です。':
        '\\u201c \\u201d \\u2018 \\u2019 are not <code>"</code> or <code>&#39;</code>.',
    'NFC 正規化する': 'apply NFC normalization',
    '濁点や記号が「合成前」の形で入っています（見た目は同じです）。':
        'some characters are in decomposed form (they look identical on screen).',
    '正規表現のほうの全角文字を半角にする': 'convert the fullwidth characters in the pattern',
    '<b>式の中に全角文字が混ざっています。</b> 括弧やハイフンを全角で書いていないか確かめてください。':
        '<b>the pattern itself contains fullwidth characters.</b> Check the brackets and hyphens.',
    '入力を直す: ': 'fix the input: ',
    '直したあと: <code>': 'after the fix: <code>',

    # 判定
    'フラグに使えない文字があります: ': 'this is not a valid flag: ',
    '<b>式が読めません:</b> ': '<b>the pattern does not parse:</b> ',
    '<b>式そのものが正規表現として読めません。</b>':
        '<b>the pattern itself is not a valid regular expression.</b>',
    'まずは上のエラーを直してください。': 'Fix the error above first.',
    '式が読めないので照合していません。': 'Nothing was matched, because the pattern does not parse.',
    '<b>本物の正規表現には当てていません。</b>': '<b>The real engine was not run.</b>',
    'この式は<b>くり返しの中にくり返し</b>があり、外れた瞬間に試す組み合わせが跳ねます。':
        'This pattern has a <b>repeat inside a repeat</b>, so the moment it fails the number of combinations explodes. ',
    '入力が ': 'The input is ',
    ' 文字あるので、当てるとこのページが長時間止まります。':
        ' characters long, so running it here would freeze this page for a long time.',
    '<span class="sub">自前の照合器だけで診断しています（下の「どこまで進んだか」）。':
        '<span class="sub">The diagnosis below comes from the built-in matcher alone (see "how far it got"). ',
    '入力を ': 'Shorten the input to ',
    ' 文字以下にすると、本物にも当てて確かめます。</span>':
        ' characters or fewer and the real engine is run as well.</span>',
    '<b>ブラウザが式を受け付けませんでした:</b> ':
        '<b>the browser refused the pattern:</b> ',
    '<b>マッチします。</b>': '<b>It matches.</b> ',
    '空文字列に当たっています（': 'It matches the empty string (at character ',
    ' 文字目）。': ').',
    ' 文字目から ': 'Characters ',
    ' 文字目まで、<code>': ' through ',
    '</code> に当たっています。': ' match.',
    '<span class="sub">ただし<b>文字列全体ではありません</b>。':
        '<span class="sub">But <b>not the whole string</b>. ',
    '全体に当てたいときは <code>^</code> と <code>$</code> で挟みます。</span>':
        'Wrap the pattern in <code>^</code> and <code>$</code> to require the whole thing.</span>',
    '<span class="sub">グループ: ': '<span class="sub">Groups: ',
    '（無し）': '(none)',
    '<b>マッチしません。</b>': '<b>It does not match.</b> ',
    '下に、照合がどこで止まったかと、直せば当たる一手を出しています。':
        'Below: where the match stopped, and the single change that makes it work.',

    # どこまで進んだか
    '<li class="w"><b>試行の上限（': '<li class="w"><b>Stopped after the step limit (',
    ' 回）に達したので打ち切りました。</b>': ' steps).</b> ',
    'この式は入力に対して<b>組み合わせ爆発</b>を起こしています。':
        'This pattern <b>explodes combinatorially</b> on this input. ',
    'くり返しの中にくり返しがある形（<code>(a+)+</code> など）は、':
        'A repeat inside a repeat (<code>(a+)+</code> and friends) is ',
    '<b>当たっている間は速いのに、外れた瞬間に全部の分け方を試します</b>。':
        '<b>fast while it matches, and tries every possible split the moment it fails</b>. ',
    '内側を「次に来る文字を含まない集合」にすると分け方が1通りになって解消します。':
        'Making the inner part a set that excludes the next character leaves exactly one split, which fixes it. ',
    'ここまでの記録では ': 'Up to the cutoff it had reached character ',
    ' 文字目まで進んでいました。</li>': '.</li>',
    ' 文字目で止まりました。</b>': '.</b>',
    '<li class="w"><b>': '<li class="w"><b>Stopped at character ',
    '（': ' (started at character ',
    ' 文字目から試したときが、いちばん先まで進みました）': ', which is the attempt that got furthest)',
    '<br>ここで待っていたのは ': '<br>What it wanted here: ',
    ' です。実際にあるのは ': '. What is actually there: ',
    '<li class="i"><b>試した回数: ': '<li class="i"><b>Steps tried: ',
    ' 回</b>': '</b>',
    '（当たらないと分かるまでに、この回数だけ道を試しました）</li>':
        ' (that is how many paths were tried before giving up)</li>',
    '<li class="w"><b>1文字も進めませんでした。</b>':
        '<li class="w"><b>It could not advance a single character.</b> ',
    '先頭から合っていません。</li>': 'Nothing lines up from the very start.</li>',
    '<b>文字列の終わり</b>（もう文字がありません）':
        '<b>the end of the string</b> (there are no characters left)',

    # 「こうすればマッチします」の枠
    '<li class="i"><b>1か所だけ変えて当たるものは見つかりませんでした。</b>':
        '<li class="i"><b>No single change made it match.</b> ',
    'フラグ・空白・全角・改行コード・見えない文字はどれも原因ではないようです。':
        'Flags, whitespace, fullwidth characters, line endings and invisible characters are all ruled out. ',
    '上の「どこまで進んだか」で、式と入力のどちらを直すか決めてください。</li>':
        'Use "how far it got" above to decide whether to change the pattern or the input.</li>',

    # 表の見出し
    '足したところ': 'added',
    '枝': 'branch',
    '本目の枝': 'branch ',

    # 自己検査
    '<b>✗ 食い違いが ': '<b>&#10007; ',
    ' 件あります。</b>': ' disagreements.</b> ',
    '診断より、ブラウザの結果のほうが正しいです。<br>':
        'Where they differ, trust the browser, not this diagnosis.<br>',
    '<b>この式は自前の照合器では扱いません。</b>':
        '<b>The built-in matcher does not handle this pattern.</b> ',
    'ブラウザの結果だけで診断しています。': 'The diagnosis uses the browser only.',
    '<b>✓ ': '<b>&#10003; ',
    ' 件すべて一致</b>': ' of them agree</b>',
    '（自前の照合器とブラウザの <code>RegExp</code> で、マッチするか・どこからどこまで・':
        # ★アポストロフィは使わない。JS の '…' の中に \\' が入ると、
        #   strip_literals（'[^'\\n]*' で剥がす）が日英で違う剥がれ方をして
        #   「文字列を外すとコードが一致」の検査が通らなくなる
        ' — the built-in matcher and the <code>RegExp</code> of this browser were compared on whether it matches, where the match starts and ends, and ',
    '各グループの中身を突き合わせた結果です': 'what each group captured',
    '。ほかに ': '. A further ',
    ' 件は対象外': ' were out of scope',
    '）。': '. ',
    'いま画面に出している式もこの中に入っています。':
        'The pattern currently on screen is one of them.',

    # プリセットの見出し
    '区切りが違う': 'wrong separator',
    '大文字が入っている': 'uppercase letters',
    '全角の数字': 'fullwidth digits',
    '空白が入っている': 'a space in the middle',
    '末尾に空白': 'trailing space',
    '. が改行に当たらない': '. skips newlines',
    'BOM が先頭にある': 'BOM at the start',
    '見た目の似たハイフン': 'look-alike hyphen',
    '^ $ は行の端ではない': '^ $ are not line ends',
    '組み合わせ爆発': 'combinatorial explosion',

    # 自己検査の内部ラベル（画面に出るのは食い違ったときだけ）
    '式が読めない': 'unparsable',
    '対象外': 'out of scope',
    '危険な形': 'explosive shape',
    '打ち切り': 'cut off',
    '当てられない': 'cannot run',
    'マッチするかどうかが違う': 'disagree on whether it matches',
    '始まる位置が違う': 'disagree on where it starts',
    '長さが違う': 'disagree on the length',
    'グループ ': 'group ',
    ' の中身が違う': ' differs',
    # 自己検査に使う組。日本語の見本は同じ文字を u 書きで持つ
    'あ+い': '\\u3042+\\u3044',
    'ああい': '\\u3042\\u3042\\u3044',
    'ひらがな': '\\u3072\\u3089\\u304c\\u306a',
    '<p>ひと\\nこと</p>': '<p>two\\nlines</p>',
    # 画面のかけら
    '<span class="rest">（空の文字列）</span>': '<span class="rest">(empty string)</span>',
    '\\\\p{...} か v フラグを使っているので、自前の照合器では追っていません。</span>':
        '\\\\p{...} or the v flag is used here, so the built-in matcher did not trace it.</span>',
    '<span class="rest">入力が長すぎて、自前の照合器では最後まで追えませんでした。': '<span class="rest">The input is too long for the built-in matcher to trace all the way. ',
    '短い入力で試すと止まった位置が出ます。</span>': 'Try a shorter input to see where it stopped.</span>',
    ' か ': ' or ',
    ' ／ ': ' / ',
    '本目の枝': ' — alternation branch',
    '</th><th>ここまでの式</th><th>当たるか</th></tr>': '</th><th>pattern so far</th><th>matches?</th></tr>',
    '<tr><th>場所</th><th>文字</th><th>なぜ拾ったか</th></tr>': '<tr><th>where</th><th>character</th><th>why it was flagged</th></tr>',
    '<tr><td class="n">式の ': '<tr><td class="n">pattern, char ',
    '<tr><td class="n">入力の ': '<tr><td class="n">input, char ',
    ' 文字目</td><td class="src">': '</td><td class="src">',
}

TR = dict(PARSER_TR)
TR.update(OWN)


def drop_comments(s):
    """コメントを外す。コード中の日本語コメントは英語版でもそのまま残す方針。"""
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)(?<!:)//.*$', '', s)


def strip_literals(s):
    return re.sub(r"'[^'\n]*'", "''", s)


def core_of(html):
    """ページの JavaScript 全体。csv や鉄道図より広い範囲を突き合わせる。"""
    return html.split('<script>')[1].split('</script>')[0]


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'docs')
    ja_path = docs / 'regex-why' / 'index.html'
    en_path = docs / 'en' / 'regex-why.html'
    ja = ja_path.read_text(encoding='utf-8')

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit('HTMLの差し替え元が見つかりません:\n' + a[:160])
        en = en.replace(a, b, 1)
    for a, b in sorted(TR.items(), key=lambda kv: -len(kv[0])):
        en = en.replace("'" + a + "'", "'" + b + "'")

    # 仮名・漢字だけ見ていると、句読点や全角括弧（、。「」（））が素通りする。
    # 実際に約物を残したまま本番に出した（2026-08-23）ので約物も見る。
    left = re.findall('[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？]+', drop_comments(en))
    if left:
        sys.exit('日本語が %d 箇所残っています: %s' % (len(left), left[:10]))

    a, b = strip_literals(core_of(ja)), strip_literals(core_of(en))
    if a != b:
        for k, (x, y) in enumerate(zip(a.split('\n'), b.split('\n'))):
            if x != y:
                sys.exit('コードが一致しません（%d行目）:\n  ja: %s\n  en: %s' % (k + 1, x, y))
        sys.exit('コードの行数が違います（ja %d / en %d）' % (a.count('\n'), b.count('\n')))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(en, encoding='utf-8', newline='\n')
    print('書き出した: %s' % en_path)
    print('日本語の残り: 0箇所')
    print('文字列リテラルを外したコード: 日英でバイト単位で一致（%d バイト）' % len(a.encode()))


# ── HTML の差し替え ────────────────────────────────────────────────────────
HTML_PARTS = [
 ('<html lang="ja">', '<html lang="en">'),

 ('<title>正規表現がなぜマッチしないか診断 — 止まった位置と、直せばマッチする一手</title>',
  '<title>Why doesn\'t my regex match? — where it stopped, and the one change that fixes it</title>'),

 ('<meta name="description" content="正規表現と試したい文字列を入れると、マッチしない理由を診断します。照合が何文字目で止まったか、そこで何を待っていて実際には何があったかを名指しし、フラグや入力を1か所だけ変えて「こうすればマッチします」を実際に試して示します。全角・見えない文字・改行コードの混入も検出。ブラウザ内で完結し、データはどこにも送信されません。">',
  '<meta name="description" content="Paste a regular expression and the string you expect it to match, and this page tells you why it does not. It names the character where matching stopped, what the pattern wanted there and what is actually in the way, then changes one flag or one detail of the input at a time and re-runs the real engine to show you the single fix that works. Fullwidth characters, invisible characters and CRLF line endings are detected too. Everything runs in the browser and nothing is uploaded.">'),

 # hreflang と icon は日本語版にも同じものが入っているので、canonical だけ差し替える
 ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/regex-why/">',
  '<link rel="canonical" href="%s/en/regex-why.html">' % SITE),

 ('<meta property="og:locale" content="ja_JP">', '<meta property="og:locale" content="en_US">'),
 ('<meta property="og:site_name" content="クロードの昼ラボ">',
  '<meta property="og:site_name" content="Claude\'s Daytime Lab">'),
 ('<meta property="og:title" content="正規表現がなぜマッチしないか診断 — 止まった位置と、直せばマッチする一手">',
  '<meta property="og:title" content="Why doesn\'t my regex match? — where it stopped, and the one change that fixes it">'),
 ('<meta property="og:description" content="マッチしない理由を診断します。照合が何文字目で止まり、そこで何を待っていて実際には何があったかを名指しし、フラグや入力を1か所だけ変えて「こうすればマッチします」を実際に試して示します。ブラウザ内で完結します。">',
  '<meta property="og:description" content="Find out why a regex does not match. This page names the character where matching stopped and what the pattern wanted there, then changes one flag or one detail of the input at a time and re-runs the real engine to show the fix that works. Runs entirely in your browser.">'),
 ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/regex-why/">',
  '<meta property="og:url" content="%s/en/regex-why.html">' % SITE),
 ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-regex-why.png">',
  '<meta property="og:image" content="%s/ogp/ogp-regex-why-en.png">' % SITE),
 ('<meta name="twitter:title" content="正規表現がなぜマッチしないか診断 — 止まった位置と、直せばマッチする一手">',
  '<meta name="twitter:title" content="Why doesn\'t my regex match? — where it stopped, and the one change that fixes it">'),
 ('<meta name="twitter:description" content="照合が何文字目で止まり、そこで何を待っていたかを名指しします。フラグや入力を1か所だけ変えて「こうすればマッチします」を実際に試して示します。ブラウザ内で完結します。">',
  '<meta name="twitter:description" content="Names the character where matching stopped and what the pattern wanted there, then changes one thing at a time and re-runs the real engine to show the fix that works. Runs entirely in your browser.">'),
 ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-regex-why.png">',
  '<meta name="twitter:image" content="%s/ogp/ogp-regex-why-en.png">' % SITE),

 # JSON-LD
 ('''  "name": "正規表現がなぜマッチしないか診断",
  "url": "https://hirulab-dev.github.io/hirulab-tools/regex-why/",
  "description": "正規表現と試したい文字列を入れると、マッチしない理由を診断します。照合が何文字目で止まったか、そこで何を待っていて実際には何があったかを名指しします。フラグや入力を1か所だけ変えて実際に試し、こうすればマッチするという一手を示します。全角文字・ゼロ幅文字・改行コードの混入も検出します。ブラウザ内で完結します。",''',
  '''  "name": "Why doesn't my regex match?",
  "url": "%s/en/regex-why.html",
  "description": "Paste a regular expression and the string you expect it to match, and this page tells you why it does not. It names the character where matching stopped and what the pattern wanted there, then changes one flag or one detail of the input at a time and re-runs the real engine to show the single fix that works. Fullwidth characters, zero-width characters and CRLF line endings are detected too. Everything runs in the browser.",''' % SITE),
 ('  "inLanguage": "ja",', '  "inLanguage": "en",'),
 ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
  '  "browserRequirements": "A modern browser with JavaScript enabled",'),
 ('  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-regex-why.png",',
  '  "image": "%s/ogp/ogp-regex-why-en.png",' % SITE),
 ('  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },\n'
  '  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }',
  '  "author": { "@type": "Organization", "name": "Claude\'s Daytime Lab", "url": "https://note.com/hirulab" },\n'
  '  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — browser-only tools", "url": "%s/" }' % SITE),

 # 本文
 ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>正規表現がなぜマッチしないか診断</h1>
  <p class="lead">「当たるはずなのに当たらない」を調べる道具です。
    照合が<strong>何文字目で止まったか</strong>、そこで<strong>何を待っていて、実際には何があったか</strong>を名指しします。
    さらに<strong>フラグや入力を1か所だけ変えて実際に試し</strong>、
    「これを直せばマッチします」という一手を出します。
    全角文字・ゼロ幅文字・改行コード（<code>\\r</code>）の混入も見ます。</p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    解析も照合もすべてブラウザの中でやっています。読み込んだあとは機内モードでも動きます。
    入力した正規表現や文字列がどこかに送られることはありません。
  </div>''',
  '''  <a class="hl-back" href="./">← Claude's Daytime Lab — tools</a>
  <h1>Why doesn't my regex match?</h1>
  <p class="lead">For when a pattern <em>should</em> match and doesn't.
    This page names <strong>the character where matching stopped</strong>, and
    <strong>what the pattern wanted there versus what is actually in the way</strong>.
    Then it <strong>changes one flag, or one detail of the input, and runs the real engine again</strong>
    to show you the single fix that works.
    Fullwidth characters, zero-width characters and CRLF line endings (<code>\\r</code>) are checked too.</p>

  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    Parsing and matching both happen inside your browser. Once loaded, it works in airplane mode.
    Nothing you type is sent anywhere.
  </div>'''),

 ('''    <p class="sublabel" id="subjLabel">当たってほしい文字列（改行も入れられます）</p>
    <label for="subj" class="hide">試す文字列</label>''',
  '''    <p class="sublabel" id="subjLabel">The string you expect it to match (newlines are fine)</p>
    <label for="subj" class="hide">test string</label>'''),
 ('    <label for="pat" class="hide">正規表現</label>\n    <label for="flags" class="hide">フラグ</label>',
  '    <label for="pat" class="hide">regular expression</label>\n    <label for="flags" class="hide">flags</label>'),

 ('    <h2>判定</h2>', '    <h2>Verdict</h2>'),

 ('''    <h2>どこまで進んだか</h2>''', '''    <h2>How far it got</h2>'''),
 ('''      上が<strong>試した文字列</strong>、下が<strong>正規表現</strong>です。
      緑が通ったところ、赤が止まったところ。正規表現の側の赤は、そこで待っていた部分です。''',
  '''      The top row is <strong>your test string</strong>, the bottom row is <strong>the pattern</strong>.
      Green is what got through, red is where it stopped. The red in the pattern is the part that was waiting.'''),

 ('    <h2>式のどこまでなら当たるか</h2>', '    <h2>How much of the pattern still matches</h2>'),
 ('''      正規表現を前から少しずつ伸ばして、<strong>ブラウザの <code>RegExp</code> に当てています</strong>。
      ✓ から ✗ に変わるところが、式が入力を追い越した地点です。
      上の「どこまで進んだか」とは<strong>別の調べ方</strong>なので、両方が同じ場所を指していれば確かです。''',
  '''      The pattern is grown one piece at a time and each prefix is
      <strong>run through the browser's own <code>RegExp</code></strong>.
      Where ✓ turns into ✗ is where the pattern outran the input.
      This is a <strong>completely different method</strong> from "how far it got" above,
      so if both point at the same place, you can trust it.'''),

 ('    <h2>こうすればマッチします</h2>', '    <h2>What would make it match</h2>'),
 ('''      フラグか入力を<strong>1か所だけ</strong>変えて、その場で当て直した結果です。
      「変えたらマッチした」ものだけを出しています（推測ではなく実測です）。''',
  '''      Each row is <strong>one single change</strong> to a flag or to the input, re-run through the real engine.
      Only changes that actually made it match are listed — these are measurements, not guesses.'''),

 ('    <h2>入力に紛れている文字</h2>', '    <h2>Characters hiding in the input</h2>'),
 ('''      見た目では気づきにくい文字です。全角の英数字・記号、ノーブレークスペース、
      ゼロ幅文字、BOM、<code>\\r</code>、異体字セレクタを拾います。''',
  '''      Characters that are hard to spot by eye: fullwidth letters and symbols, no-break spaces,
      zero-width characters, a BOM, <code>\\r</code>, and variation selectors.'''),

 ('    <h2>自己検査</h2>', '    <h2>Self-check</h2>'),
 ('''      止まった位置を出すために、この道具は<strong>自前の照合器</strong>を動かしています。
      その結果（マッチするか・どこからどこまで・各グループの中身）を、
      <strong>ブラウザの <code>RegExp</code> の結果とその場で突き合わせています</strong>。
      食い違えばここに ✗ が出ます。診断のほうを信じる前に、まずここを見てください。''',
  '''      To report where matching stopped, this page runs <strong>its own matcher</strong>.
      Its answers — whether it matches, where the match starts and ends, and what each group captured —
      are <strong>compared against the browser's <code>RegExp</code> right here, every time you type</strong>.
      If they ever disagree, a ✗ appears in this box. Check it before you believe the diagnosis above.'''),

 ('    <summary>この診断の読み方と、作りの話</summary>',
  '    <summary>How to read the diagnosis, and how it is built</summary>'),

 ('''      <li><b>「止まった位置」の意味</b>: 正規表現の照合は、うまくいかないと前に戻って別の道を試します（バックトラック）。
        ここで出しているのは<b>いちばん先まで進めたときの記録</b>です。
        たいていの「当たらない」は、この地点の1文字を直せば通ります。</li>
      <li><b>待っていたものが複数出ることがあります</b>: 同じ位置で
        <code>|</code> の枝が何本も試されて、全部落ちた場合です。そのときは待っていた候補を並べます。</li>
      <li><b>2つの調べ方を突き合わせています</b>: 自前の照合器で「止まった位置」を出す方法と、
        式を前から伸ばしてブラウザに当てる方法（「式のどこまでなら当たるか」）は独立です。
        片方だけが正しい場所を指していたら、そこは疑ってください。</li>
      <li><b>「こうすればマッチします」は実測です</b>: フラグや入力を1か所変えた式・文字列を作り、
        <b>本物の <code>RegExp</code> で当て直しています</b>。当たったものだけを出します。</li>
      <li><b>解析器は<a href="../railroad/">鉄道図の道具</a>と同じものです</b>。
        同じソースを共有していて、<b>2つのページで一致していることを機械で照合しています</b>
        （<a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>側の検証スクリプト）。</li>
      <li><b>試行回数に上限があります</b>: <code>(a+)+$</code> のような式は、外れた瞬間に
        組み合わせが爆発します。上限に達したら打ち切って、その旨と回数を出します
        （＝<b>打ち切られること自体が診断結果</b>です）。</li>
      <li><b>対応していないもの</b>: <code>\\p{...}</code> と <code>v</code> フラグの集合演算は
        自前の照合器では扱いません。その場合は「止まった位置」を出さず、
        ブラウザの結果だけで診断します（自己検査に「対象外」と出ます）。</li>
      <li><b>後読みは右から左へ読んでいます</b>: <code>(?&lt;=…)</code> は、
        仕様どおり<b>逆向きに照合</b>しています。はじめは「その位置で終わる開始点を左から探す」
        近似で書いていたのですが、7,697 件をブラウザと突き合わせたら
        <b>3 件だけグループの中身がずれ、原因が全部これでした</b>。近似をやめて書き直してあります。</li>''',
  '''      <li><b>What "where it stopped" means</b>: when matching fails, a regex engine backs up and
        tries another path (backtracking). What is reported here is <b>the furthest it ever got</b>.
        Most "it doesn't match" problems are fixed by changing one character at that spot.</li>
      <li><b>Sometimes several things were wanted</b>: that happens when more than one
        <code>|</code> branch was tried at the same position and all of them failed.
        In that case every candidate is listed.</li>
      <li><b>Two independent methods are cross-checked</b>: tracing with the built-in matcher, and
        growing the pattern one piece at a time and handing each prefix to the browser
        ("how much of the pattern still matches"). If only one of them points at a spot, be suspicious.</li>
      <li><b>"What would make it match" is measured</b>: a modified pattern or input is built and
        <b>run through the real <code>RegExp</code></b>. Only the ones that actually matched are shown.</li>
      <li><b>The parser is the same one used by
        <a href="./railroad.html">the railroad diagram tool</a></b>.
        Both pages share the source, and <b>a script checks that the two copies are byte-identical</b>
        (see the tests in the <a href="https://github.com/hirulab-dev/hirulab-tools">source</a>).</li>
      <li><b>There is a step limit</b>: a pattern like <code>(a+)+$</code> explodes combinatorially the
        moment it fails. When the limit is hit, the trace stops and says so, with the step count
        — <b>being cut off is itself the diagnosis</b>.</li>
      <li><b>Not supported</b>: <code>\\p{...}</code> and the set operations of the <code>v</code> flag
        are not handled by the built-in matcher. For those patterns, "where it stopped" is skipped and
        the diagnosis relies on the browser alone (the self-check reports them as out of scope).</li>
      <li><b>Lookbehind is matched right to left</b>: <code>(?&lt;=…)</code> is matched
        <b>backwards, as the specification describes</b>. The first version approximated it by scanning
        for a start position from the left; comparing 7,697 cases against the browser turned up
        <b>3 where the captured groups differed, all from that approximation</b>. It was rewritten.</li>'''),

 ('''  <nav class="hl-nav">
    <h2>ほかの道具</h2>
    <ul>
      <li><a href="../regex/">正規表現テスタ</a></li>
      <li><a href="../railroad/">正規表現を鉄道図にする</a></li>
      <li><a href="../replace/">正規表現の置換プレビュー</a></li>
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
      <li><a href="../frima-profit/">フリマ手取り計算機</a></li>
      <li><a href="../cron/">cron式の読み下し</a></li>
      <li><a href="../tz/">タイムゾーン変換</a></li>
      <li><a href="../csv/">CSVプレビュー・診断</a></li>
      <li><a href="../url/">URLの分解・組み立て</a></li>
      <li><a href="../headers/">HTTPヘッダの読み下し</a></li>
      <li><a href="../jwt/">JWTの読み下し</a></li>
      <li><a href="../password/">パスワード生成・強度診断</a></li>
      <li><a href="../base64/">Base64・データURLの分解</a></li>
      <li><a href="../pattern/">和柄シームレスパターン作成</a></li>
      <li><a href="../en/regex-why.html">English version</a></li>
    </ul>
    <p class="hl-links">
      <a href="../">道具箱のトップ</a> ・
      <a href="https://note.com/hirulab">実験ログ（note）</a> ・
      <a href="https://x.com/hirulab_ai">X</a> ・
      <a href="https://github.com/hirulab-dev/hirulab-tools">ソース</a>
    </p>
  </nav>''',
  '''  <nav class="hl-nav">
    <h2>Other tools</h2>
    <ul>
      <li><a href="./railroad.html">Regex Railroad Diagrams</a></li>
      <li><a href="./replace.html">Regex Replacement Preview</a></li>
      <li><a href="./regex-tester.html">Regex Tester</a></li>
      <li><a href="./char-counter.html">Character Counter</a></li>
      <li><a href="./palette.html">Color Palette</a></li>
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
      <li><a href="../regex-why/">Japanese version</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">All tools (English)</a> ·
      <a href="../">Japanese site</a> ·
      <a href="https://x.com/hirulab_ai">X</a> ·
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''),

 ('''    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    診断は JavaScript の正規表現（ECMAScript）の書き方に合わせています。
    Python や PCRE では意味が違う記号があるので、他の言語で使うときは確かめてください。''',
  '''    Built by Claude's Daytime Lab (Claude, an AI). Free, no sign-up.
    The diagnosis follows JavaScript regular expressions (ECMAScript).
    Some syntax means something different in Python or PCRE, so check before you carry a pattern across.'''),
]


if __name__ == '__main__':
    main()
