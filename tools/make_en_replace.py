#!/usr/bin/env python3
"""「正規表現の置換プレビュー」の英語版を、日本語版から作る（2026-08-23）。

`make_en_railroad.py` / `make_en_regex_why.py` と同じ方式。
**日本語版が唯一の原本**で、英語版は毎回ここから作り直す。手で両方を直すことはしない。

やっていること
1. HTML（head・本文・解説・ナビ・脚注）を英語の版に差し替える
2. スクリプトの中の**引用符で囲まれた文字列だけ**を英語に差し替える
   （解析器は鉄道図と同じソースなので、**訳語も鉄道図の表をそのまま使う**）
3. できた英語版について、**「文字列リテラルを全部取り除くと日本語版とバイト単位で一致する」**
   ことを確かめる。通れば、テンプレートの読み取り・置換・落とし穴の検出は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる（コードのコメントは対象外）

使い方: python lab/scripts/make_en_replace.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from make_en_railroad import TR as PARSER_TR   # 解析器の訳語は鉄道図と共有する

SITE = "https://hirulab-dev.github.io/hirulab-tools"

# ── この道具だけが持つ文字列 ───────────────────────────────────────────────
OWN = {
    # テンプレートの読み取りで出る説明
    '末尾の ': 'a trailing ',
    ' はそのまま文字として出ます': ' is emitted as a plain character',
    'グループ番号は 1 から始まります（マッチ全体は ': 'group numbers start at 1 (the whole match is ',
    '& です）。': '&). ',
    'そのまま文字として出ます': 'It is emitted as plain characters',
    'このグループはありません（式のグループは ': 'there is no such group (the pattern has ',
    ' 個）。そのまま文字として出ます': ' of them). It is emitted as plain characters',
    '式に名前つきグループが1つも無いので、': 'the pattern has no named groups at all, so ',
    '< は特別扱いされません。': '< is not treated specially. ',
    '閉じる > がありません。そのまま文字として出ます':
        'there is no closing >. It is emitted as plain characters',
    ' のあとが ': ' is followed by ',
    ' なので特別扱いされません。': ', which is not a special form. ',
    'そのまま文字として出ます（確実に ': 'It is emitted as a plain character (to be sure of getting a ',
    ' を出すなら ': ', write ',

    # 見えない文字・紛らわしい文字
    'BOM（ファイルの先頭に付く見えない印）': 'BOM (an invisible marker at the start of a file)',
    '幅ゼロの空白': 'zero-width space',
    '幅ゼロの非結合子': 'zero-width non-joiner',
    '幅ゼロの結合子': 'zero-width joiner',
    'ノーブレークスペース（半角スペースに見えます）': 'no-break space (looks exactly like a plain space)',
    '全角スペース': 'ideographic space',
    'ダッシュ（半角ハイフンではありません）': 'dash (not an ASCII hyphen)',
    'マイナス記号（半角ハイフンではありません）': 'minus sign (not an ASCII hyphen)',
    '始まりの引用符': 'left single quotation mark',
    '終わりの引用符（アポストロフィではありません）': 'right single quotation mark (not an apostrophe)',
    '始まりの二重引用符': 'left double quotation mark',
    '終わりの二重引用符': 'right double quotation mark',
    '改行コード CR（Windows の改行の片割れ）': 'carriage return (half of a Windows line ending)',
    '全角の記号・英数字（半角ではありません）': 'fullwidth letter, digit or symbol (not the ASCII one)',
    '異体字セレクタ（見た目には出ません）': 'variation selector (draws nothing of its own)',

    # 自己検査の内部ラベル
    '式が読めない': 'unparsable',
    '当てられない': 'cannot run',
    '件数が多い': 'too many matches',

    # 落とし穴
    '1件も当たっていません': 'Nothing matched',
    'この式は対象の文字列に当たらないので、置換後は元のままです。':
        'The pattern does not match the subject, so the result is the original text. ',
    'なぜ当たらないかは<a href="../regex-why/">なぜマッチしないか診断</a>で調べられます。':
        'To find out why, try <a href="./regex-why.html">the "why doesn&#39;t my regex match" tool</a>.',
    'g が無いので最初の1件だけ置き換わります': 'Without g, only the first match is replaced',
    '対象には ': 'There are ',
    ' 件当たる場所がありますが、置き換わるのは1件目だけです。':
        ' places that match, but only the first one is replaced. ',
    '全部変えるならフラグに <code>g</code> を足してください。エラーは出ません。':
        'Add the <code>g</code> flag to replace them all. No error is raised either way.',
    '</code> は特別扱いされていません': '</code> is not treated specially',
    '</code> という名前のグループはありません': '</code> is not the name of any group',
    '式にある名前は ': 'The names in the pattern are ',
    ' です。<b>綴りが違うとエラーにならず、空文字になります</b>（黙って消えます）。':
        '. <b>A misspelled name is not an error — it becomes the empty string</b> and disappears silently.',
    '置換文字列の <code>\\\\1</code> は後方参照ではありません':
        '<code>\\\\1</code> in a replacement string is not a back-reference',
    'JavaScript の置換文字列では <code>\\\\</code> に意味がありません。':
        'A <code>\\\\</code> means nothing in a JavaScript replacement string. ',
    'グループを差し込むなら <code>': 'To insert a group, write <code>',
    '1</code> と書きます。': '1</code>. ',
    'sed や Python の <code>re.sub</code> の癖で書くとここで外れます。':
        'This is the habit that carries over from sed and Python <code>re.sub</code>.',
    '{...}</code> は特別扱いされません': '{...}</code> is not treated specially',
    'そのまま文字として出ます。番号なら <code>': 'It is emitted verbatim. For a number write <code>',
    '名前なら <code>': 'for a name write <code>',
    '&lt;名前&gt;</code> と書きます。': '&lt;name&gt;</code>.',
    'Python の書き方が混ざっています': 'This is Python syntax, not JavaScript',
    '<code>\\\\g&lt;名前&gt;</code> は JavaScript では効きません。<code>':
        '<code>\\\\g&lt;name&gt;</code> does nothing in JavaScript. Use <code>',
    '&lt;名前&gt;</code> です。': '&lt;name&gt;</code>.',
    '長さ0のマッチが ': 'There are ',
    ' 件あります': ' zero-length matches',
    '長さ0のマッチは文字と文字の<b>あいだ</b>に入ります。':
        'A zero-length match lands <b>between</b> characters. ',
    '<code>&quot;abc&quot;.replace(/x*/g, &quot;-&quot;)</code> が ':
        'That is why <code>&quot;abc&quot;.replace(/x*/g, &quot;-&quot;)</code> gives ',
    '<code>-a-b-c-</code> になるのと同じ形です。': '<code>-a-b-c-</code>.',
    '</code> と <code>': '</code> and <code>',
    '</code> は元の文字列を指します': '</code> refer to the original string',
    '置換しかけの文字列ではなく、<b>置換前の文字列全体</b>の前半・後半です。':
        'Not the half-replaced string — they are the parts of <b>the string as it was before replacing</b>. ',
    '<code>g</code> と組み合わせると、同じ内容が何度も出ます。':
        'Combined with <code>g</code>, the same text comes out over and over.',
    '<code>y</code>（先頭固定）が付いています': 'The <code>y</code> (sticky) flag is set',
    '前の終わりから<b>続けて</b>当たる間だけ置換されます。1か所でも外れるとそこで止まり、':
        'Replacement only continues while matches are <b>adjacent</b> to the previous one. '
        'The first gap stops it, ',
    '後ろに同じ形があっても置き換わりません。': 'and later occurrences are left alone.',
    '<code>i</code> が効くのは探すときだけです': '<code>i</code> only affects the search',
    '大文字小文字を無視して当たりますが、<b>入る文字は書いたままの大小</b>です。':
        'Matching ignores case, but <b>the text you insert keeps the case you typed</b>. ',
    '元の大小に合わせたければ、置換文字列だけでは足りません。':
        'To follow the case of the original, a replacement string is not enough.',
    '<code>u</code> が無いので、絵文字などが2つに割れます':
        'Without <code>u</code>, emoji are split in half',
    '対象にサロゲートペア（絵文字や一部の漢字）が入っています。':
        'The subject contains surrogate pairs (emoji and some CJK characters). ',
    '<code>u</code> が無いと <code>.</code> が半分だけ食べて、壊れた文字が出ます。':
        'Without <code>u</code>, <code>.</code> eats only half of one and broken characters come out.',
    '当たった場所が多すぎるので途中で止めました': 'Too many matches, so this was cut off',
    ' 件で打ち切っています。画面の置換後はそこまでの結果です。':
        ' matches were processed. The result above stops there.',
    '置換しても文字列が変わっていません': 'Replacing changed nothing',
    '当たってはいますが、入れ替えた結果が元と同じです。':
        'The pattern matches, but what goes back in is identical to what came out. ',
    'テンプレートが元の文字をそのまま戻している可能性があります。':
        'The template may simply be putting the original text back.',

    # プリセット
    '納期は 2026-08-23、予備日は 2026-12-31 です。': 'Due 2026-08-23, backup date 2026-12-31.',
    '2026-08-23 と 2026-12-31': '2026-08-23 and 2026-12-31',
    '日付の並べ替え': 'reorder a date',
    '$<y>年$<m>月': '$<m>/$<y>',
    '2026-08 と 2027-01 の対比': 'compare 2026-08 with 2027-01',
    '名前つきグループ': 'named groups',
    '$<year>年$<m>月': '$<year>/$<m>',
    '名前の綴り違い（黙って空になる）': 'misspelled name (silently empty)',
    '(\\\\d+)円': '(\\\\d+) yen',
    '$2円': '$2 yen',
    '300円と1200円': '300 yen and 1200 yen',
    '無い番号を書いた（文字として出る）': 'a group number that does not exist',
    '\\\\2 の \\\\1': '\\\\2 at \\\\1',
    '$2 の $1': '$2 at $1',
    'sed の癖で書いた': 'written the sed way',
    'りんご,みかん,ぶどう': 'apple,orange,grape',
    'g の付け忘れ': 'forgot the g flag',
    '長さ0のマッチ': 'zero-length matches',
    'マッチ全体を囲む': 'wrap the whole match',
    '値段は 300 と 1200': 'prices are 300 and 1200',
    'ドル記号を出す': 'emit a dollar sign',
    'あ\\u{1f600}b': 'a\\u{1f600}b',
    'u なしで絵文字を切る': 'cut an emoji without u',
    '  空白が    ばらばら\\tな   文字列  ': '  ragged   spacing\\there  and    there  ',
    '空白の詰め直し': 'collapse whitespace',
    'オレンジ': 'ORANGE',
    'Apple と APPLE と apple': 'Apple and APPLE and apple',
    'i は探すときだけ': 'i only affects the search',
    '(かな)': '(kana)',
    'あいう漢字えお': 'kana and kanji mixed',

    # トークンの意味
    'マッチした部分ぜんぶ': 'the whole matched text',
    'マッチより前（元の文字列の先頭から）': 'everything before the match (from the start of the original)',
    'マッチより後ろ（元の文字列の末尾まで）': 'everything after the match (to the end of the original)',
    ' の文字そのもの': ' as a literal character',

    # 画面のかけら
    '<span class="empty">（無し）</span>': '<span class="empty">(none)</span>',
    '<span class="empty">（空）</span>': '<span class="empty">(empty)</span>',
    '読めません': 'cannot be read',
    '式が読めないので突き合わせていません。': 'The pattern cannot be read, so nothing was compared.',
    '</b> か所を置き換えました': '</b> replacements made',
    '（元 ': ' (original ',
    ' 文字 → 置換後 ': ' characters, result ',
    ' 文字）。': ' characters).',
    ' 件で打ち切っています。': ' matches, then cut off.',
    '<tr><th>書いたもの</th><th>意味</th><th>1件目での中身</th></tr>':
        '<tr><th>what you wrote</th><th>what it means</th><th>value at match 1</th></tr>',
    '<tr><td colspan="3"><span class="empty">置換テンプレートが空です（当たった場所が削除されます）</span></td></tr>':
        '<tr><td colspan="3"><span class="empty">The replacement template is empty, '
        'so every match is deleted</span></td></tr>',
    'そのままの文字': 'literal text',
    ' 個あるグループの ': ' of the ',
    ' 番目': ' capture groups',
    '（このマッチでは通っていません → 空文字）': ' (did not take part in this match, so empty)',
    '名前つきグループ ': 'named group ',
    'その名前のグループが無いので<b>空文字</b>になります':
        'no group has that name, so this becomes <b>the empty string</b>',
    '<span class="empty">（マッチ無し）</span>': '<span class="empty">(no match)</span>',
    '行にさわると、置換後のどこがそこから来たかに印が付きます。':
        'Point at a row to highlight the part of the result it produced.',
    '<tr><th>#</th><th>位置</th><th>当たった文字</th>':
        '<tr><th>#</th><th>at</th><th>matched text</th>',
    '<th>置き換えたあと</th></tr>': '<th>replaced with</th></tr>',
    '"><span class="empty">当たった場所がありません</span></td></tr>':
        '"><span class="empty">nothing matched</span></td></tr>',
    '">ほか ': '">and ',
    ' 件（表は先頭 ': ' more (the table shows the first ',
    ' 件まで）</td></tr>': ')</td></tr>',
    '<tr><th>場所</th><th>文字</th><th>これは何か</th></tr>':
        '<tr><th>where</th><th>character</th><th>what it is</th></tr>',
    '式': 'pattern',
    'テンプレート': 'template',
    '対象': 'subject',
    'の ': ', char ',
    ' 文字目</td><td class="src">': '</td><td class="src">',
    '<b>✗ 食い違いが ': '<b>&#10007; ',
    ' 件あります。</b>': ' mismatches.</b> ',
    'この画面より、ブラウザの <code>replace</code> の結果のほうが正しいです。<br>':
        'Trust the browser&#39;s own <code>replace</code> over what is shown here.<br>',
    ' 件すべて一致</b>': ' cases agree</b>',
    '（自前で組み立てた置換結果と、ブラウザの <code>String.prototype.replace</code> の結果を':
        ' (the result assembled here is compared against '
        '<code>String.prototype.replace</code> in this browser',
    '突き合わせています': '',
    '。ほかに ': '; a further ',
    ' 件は対象外': ' are out of scope',
    'いま画面に出している入力もこの中に入っています。':
        'The input on screen right now is one of the cases.',
    # ★ 約物は「日本語が残っているか」の網から漏れる（U+3001 U+3002 U+FF09 など）。
    # ここを取りこぼして本番に出したので、下の判定も広げてある。
    '、': '; ',
    '1</code>、': '1</code>, ',
    '。': '.',
    '）。': '). ',
    'コピーしました': 'copied',
    'コピーできませんでした': 'could not copy',
}

TR = dict(PARSER_TR)
TR.update(OWN)


def drop_comments(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)(?<!:)//.*$', '', s)


def strip_literals(s):
    return re.sub(r"'[^'\n]*'", "''", s)


def core_of(html):
    return html.split('<script>')[1].split('</script>')[0]


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'docs')
    ja_path = docs / 'replace' / 'index.html'
    en_path = docs / 'en' / 'replace.html'
    ja = ja_path.read_text(encoding='utf-8')

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit('HTMLの差し替え元が見つかりません:\n' + a[:160])
        en = en.replace(a, b, 1)
    for a, b in sorted(TR.items(), key=lambda kv: -len(kv[0])):
        en = en.replace("'" + a + "'", "'" + b + "'")

    # 仮名・漢字だけ見ていると、句読点や全角括弧（、。「」（））が素通りする。
    # 実際に '）。' を残したまま本番に出した（2026-08-23）ので約物も見る。
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

 ('<title>正規表現の置換プレビュー — $1 が何に化けるかを1つずつ見せる</title>',
  '<title>Regex Replacement Preview — see what $1 turns into, one token at a time</title>'),

 ('<meta name="description" content="正規表現の置換を、置き換わる前に見せる道具です。置換テンプレートの $1 $&amp; $&lt;name&gt; を1つずつ読み下し、マッチごとに何がどこから来たかを対応づけて表示します。番号の無いグループがそのまま文字として出る、名前の綴り違いが黙って空文字になる、g を付け忘れて1件しか変わらない、といった落とし穴を自動で指摘します。ブラウザ内で完結し、データはどこにも送信されません。">',
  '<meta name="description" content="Preview a regex replacement before you run it. Every $1, $&amp; and $&lt;name&gt; in the template is spelled out, and each piece of the result is traced back to the token that produced it. The traps that raise no error are called out: a group number that does not exist is emitted verbatim, a misspelled group name silently becomes the empty string, and without the g flag only the first match is replaced. Everything runs in the browser and nothing is uploaded.">'),

 ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/replace/">',
  '<link rel="canonical" href="%s/en/replace.html">' % SITE),

 ('<meta property="og:locale" content="ja_JP">', '<meta property="og:locale" content="en_US">'),
 ('<meta property="og:site_name" content="クロードの昼ラボ">',
  '<meta property="og:site_name" content="Claude\'s Daytime Lab">'),
 ('<meta property="og:title" content="正規表現の置換プレビュー — $1 が何に化けるかを1つずつ見せる">',
  '<meta property="og:title" content="Regex Replacement Preview — see what $1 turns into, one token at a time">'),
 ('<meta property="og:description" content="置換テンプレートを1つずつ読み下し、マッチごとに何がどこから来たかを対応づけます。番号の無いグループがそのまま文字として出る、名前の綴り違いが黙って空文字になる、といった落とし穴を自動で指摘します。ブラウザ内で完結します。">',
  '<meta property="og:description" content="Every token of the replacement template is spelled out, and each piece of the result is traced back to the token that produced it. Traps that raise no error — a group number that does not exist, a misspelled group name — are called out. Runs entirely in your browser.">'),
 ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/replace/">',
  '<meta property="og:url" content="%s/en/replace.html">' % SITE),
 ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-replace.png">',
  '<meta property="og:image" content="%s/ogp/ogp-replace-en.png">' % SITE),
 ('<meta name="twitter:title" content="正規表現の置換プレビュー — $1 が何に化けるかを1つずつ見せる">',
  '<meta name="twitter:title" content="Regex Replacement Preview — see what $1 turns into, one token at a time">'),
 ('<meta name="twitter:description" content="置換テンプレートを1つずつ読み下し、マッチごとに何がどこから来たかを対応づけます。落とし穴も自動で指摘します。ブラウザ内で完結します。">',
  '<meta name="twitter:description" content="Every token of the replacement template is spelled out and traced to the part of the result it produced. The traps that raise no error are called out. Runs entirely in your browser.">'),
 ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-replace.png">',
  '<meta name="twitter:image" content="%s/ogp/ogp-replace-en.png">' % SITE),

 # JSON-LD
 ('''  "name": "正規表現の置換プレビュー",
  "url": "https://hirulab-dev.github.io/hirulab-tools/replace/",
  "description": "正規表現の置換を、置き換わる前に見せる道具です。置換テンプレートの記号を1つずつ読み下し、マッチごとに置換後の文字がどこから来たかを対応づけて表示します。番号の無いグループがそのまま文字として出る、名前の綴り違いが黙って空文字になる、g を付け忘れて1件しか変わらない、といった落とし穴を自動で指摘します。ブラウザ内で完結します。",''',
  '''  "name": "Regex Replacement Preview",
  "url": "%s/en/replace.html",
  "description": "Preview a regular expression replacement before you run it. Every token of the replacement template is spelled out, and each piece of the result is traced back to the token that produced it. Traps that raise no error are called out: a group number that does not exist is emitted verbatim, a misspelled group name silently becomes the empty string, and without the g flag only the first match is replaced. Everything runs in the browser.",''' % SITE),
 ('  "inLanguage": "ja",', '  "inLanguage": "en",'),
 ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
  '  "browserRequirements": "A modern browser with JavaScript enabled",'),
 ('  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-replace.png",',
  '  "image": "%s/ogp/ogp-replace-en.png",' % SITE),
 ('  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },\n'
  '  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }',
  '  "author": { "@type": "Organization", "name": "Claude\'s Daytime Lab", "url": "https://note.com/hirulab" },\n'
  '  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — browser-only tools", "url": "%s/" }' % SITE),

 # 本文
 ('''  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>
  <h1>正規表現の置換プレビュー</h1>
  <p class="lead">正規表現の置換を、<strong>置き換える前に</strong>見せる道具です。
    置換テンプレートに書いた <code>$1</code> や <code>$&amp;</code> を<strong>1つずつ読み下し</strong>、
    <strong>置換後のどの文字がどこから来たか</strong>を対応づけて表示します。
    JavaScript の置換には<strong>エラーにならずに黙って別物になる</strong>書き方がいくつもあります。
    そこを名指しするのがこの道具の目的です。</p>

  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    解析も置換もすべてブラウザの中でやっています。読み込んだあとは機内モードでも動きます。
    入力した正規表現や文字列がどこかに送られることはありません。
  </div>''',
  '''  <a class="hl-back" href="./">← Claude's Daytime Lab — tools</a>
  <h1>Regex Replacement Preview</h1>
  <p class="lead">See what a regex replacement will do <strong>before you run it</strong>.
    Every <code>$1</code> and <code>$&amp;</code> in the replacement template is
    <strong>spelled out one at a time</strong>, and
    <strong>each piece of the result is traced back to the token that produced it</strong>.
    JavaScript replacement strings have several forms that
    <strong>quietly turn into something else without raising an error</strong>.
    Naming those is the point of this page.</p>

  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    Parsing and replacing both happen inside your browser. Once loaded, it works in airplane mode.
    Nothing you type is sent anywhere.
  </div>'''),

 ('''    <label for="pat" class="hide">正規表現</label>
    <label for="flags" class="hide">フラグ</label>''',
  '''    <label for="pat" class="hide">regular expression</label>
    <label for="flags" class="hide">flags</label>'''),

 ('''    <p class="sublabel"><label for="tmpl">置換テンプレート（<code class="mono">$1</code>
       <code class="mono">$&amp;</code> <code class="mono">$&lt;名前&gt;</code> が使えます）</label></p>''',
  '''    <p class="sublabel"><label for="tmpl">replacement template (<code class="mono">$1</code>,
       <code class="mono">$&amp;</code> and <code class="mono">$&lt;name&gt;</code> work here)</label></p>'''),

 ('    <p class="sublabel"><label for="subj">置換する対象の文字列</label></p>',
  '    <p class="sublabel"><label for="subj">the text to replace in</label></p>'),

 ('    <h2>式が読めません</h2>', '    <h2>This pattern cannot be read</h2>'),
 ('    <h2>置換後</h2>', '    <h2>Result</h2>'),
 ('      <button type="button" id="copy">置換後をコピー</button>',
  '      <button type="button" id="copy">Copy the result</button>'),
 ('    <h2>元の文字列（当たった場所）</h2>', '    <h2>The original (with matches marked)</h2>'),
 ('    <h2>テンプレートの読み下し</h2>', '    <h2>The template, spelled out</h2>'),
 ('    <h2>マッチごとの中身</h2>', '    <h2>What each match captured</h2>'),
 ('    <h2>気をつけるところ</h2>', '    <h2>Things to watch out for</h2>'),
 ('    <h2>見えない文字・紛らわしい文字</h2>', '    <h2>Invisible and look-alike characters</h2>'),
 ('    <h2>自己検査</h2>', '    <h2>Self-check</h2>'),

 ('''    <summary>JavaScript の置換で、エラーにならずに別物になるところ</summary>
    <ul>
      <li><code>$1</code> に<b>対応するグループが無いと、エラーにならず <code>$1</code> という文字がそのまま出ます</b>。
        グループを1つ減らしたときに気づかないのはこれです。</li>
      <li><code>$&lt;名前&gt;</code> は、式に名前つきグループが<b>1つでもあれば</b>特別扱いされます。
        そのうえで<b>名前の綴りが違うと、エラーにならず空文字になります</b>（黙って消えます）。
        名前つきグループが1つも無い式なら、逆に <code>$&lt;名前&gt;</code> がそのまま文字として出ます。</li>
      <li><code>\\1</code> は後方参照ではありません。JavaScript の置換文字列では<b>ただの <code>1</code></b>です
        （<code>\\</code> は文字列リテラルの段階で消えます）。sed や Python の癖で書くとここで外れます。</li>
      <li><code>${1}</code> も特別扱いされません。<b>そのまま <code>${1}</code> と出ます</b>。</li>
      <li><code>$`</code> と <code>$&#39;</code> はマッチの前・後ろを指しますが、
        <b>どちらも「元の文字列」を指します</b>。置換しかけの文字列ではありません。</li>
      <li><code>g</code> が無ければ<b>最初の1件しか置き換わりません</b>。エラーは出ません。</li>
      <li>長さ0のマッチ（<code>x*</code> など）は<b>文字と文字の間に入ります</b>。
        <code>&quot;abc&quot;.replace(/x*/g, &quot;-&quot;)</code> は <code>-a-b-c-</code> になります。</li>
    </ul>''',
  '''    <summary>Replacement forms that change meaning without raising an error</summary>
    <ul>
      <li>If <b>no group matches <code>$1</code>, there is no error — the characters <code>$1</code>
        are emitted verbatim</b>. This is what bites you after deleting one capture group.</li>
      <li><code>$&lt;name&gt;</code> is only special if the pattern has <b>at least one</b> named group.
        Given that, <b>a misspelled name is not an error — it becomes the empty string</b> and disappears.
        In a pattern with no named groups at all, <code>$&lt;name&gt;</code> comes out as plain text instead.</li>
      <li><code>\\1</code> is not a back-reference. In a JavaScript replacement string it is
        <b>just <code>1</code></b> (the <code>\\</code> is consumed by the string literal).
        This is the habit that carries over from sed and Python.</li>
      <li><code>${1}</code> is not special either. <b>It comes out as <code>${1}</code></b>.</li>
      <li><code>$`</code> and <code>$&#39;</code> mean the text before and after the match, but
        <b>both refer to the original string</b> — not to the half-replaced one.</li>
      <li>Without <code>g</code>, <b>only the first match is replaced</b>. No error is raised.</li>
      <li>Zero-length matches (from <code>x*</code> and friends) land <b>between</b> characters:
        <code>&quot;abc&quot;.replace(/x*/g, &quot;-&quot;)</code> gives <code>-a-b-c-</code>.</li>
    </ul>'''),

 ('''    <summary>この道具の作りと、確かめ方</summary>
    <ul>
      <li><b>正規表現の解析器は<a href="../railroad/">鉄道図の道具</a>・<a href="../regex-why/">なぜマッチしないか診断</a>と同じものです</b>。
        3ページで1バイトも違わないことを、公開のたびに機械で照合しています。</li>
      <li><b>置換テンプレートの展開は自前で書いています。</b>
        ブラウザの <code>String.prototype.replace</code> は結果の文字列しか返さないので、
        「どの文字がどのトークンから来たか」を出すには自分で組み立てるしかありません。</li>
      <li>自前である以上ずれる可能性があります。だから<b>毎回その場でブラウザの
        <code>replace</code> と突き合わせ、結果を自己検査の欄に出しています</b>。
        食い違ったらブラウザのほうが正しいと表示します。</li>
      <li>組み込みの検査ケースも同時に回しています。いま画面に出している入力もその中に入ります。</li>
    </ul>''',
  '''    <summary>How this page is built, and how it is checked</summary>
    <ul>
      <li><b>The pattern parser is the same one used by
        <a href="./railroad.html">the railroad diagram tool</a> and
        <a href="./regex-why.html">the "why doesn&#39;t my regex match" tool</a></b>.
        A script checks that all three copies are byte-identical before anything is published.</li>
      <li><b>The template expansion is written from scratch here.</b>
        <code>String.prototype.replace</code> only hands back the finished string, so tracing
        each character to the token that produced it means assembling the result yourself.</li>
      <li>Anything written from scratch can drift. So <b>every keystroke, the assembled result is
        compared against the browser&#39;s own <code>replace</code></b> and the outcome is shown in
        the self-check box. If they disagree, the browser is the one to trust.</li>
      <li>A set of built-in cases runs at the same time — including whatever is on screen right now.</li>
    </ul>'''),

 ('''  <nav class="hl-nav">
    <h2>ほかの道具</h2>
    <ul>
      <li><a href="../regex/">正規表現テスタ</a></li>
      <li><a href="../regex-why/">正規表現がなぜマッチしないか診断</a></li>
      <li><a href="../railroad/">正規表現を鉄道図にする</a></li>
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
      <li><a href="../en/replace.html">English version</a></li>
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
      <li><a href="./regex-why.html">Why doesn&#39;t my regex match?</a></li>
      <li><a href="./railroad.html">Regex Railroad Diagrams</a></li>
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
      <li><a href="../replace/">Japanese version</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">All tools (English)</a> ·
      <a href="../">Japanese site</a> ·
      <a href="https://x.com/hirulab_ai">X</a> ·
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''),

 ('''    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    置換の規則は JavaScript（ECMAScript）に合わせています。
    Python の <code class="mono">re.sub</code> や sed とは記号の意味が違うので、
    他の言語で使うときは確かめてください。''',
  '''    Built by Claude's Daytime Lab (Claude, an AI). Free, no sign-up.
    The replacement rules follow JavaScript (ECMAScript).
    Python's <code class="mono">re.sub</code> and sed give the same symbols different meanings,
    so check before you carry a template across.'''),
]


if __name__ == '__main__':
    main()
