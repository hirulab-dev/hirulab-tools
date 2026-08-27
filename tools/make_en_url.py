#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「URLの分解・組み立て」の英語版を、日本語版から作る（2026-08-23）。

`make_en_railroad.py` / `make_en_regex_why.py` / `make_en_replace.py` と同じ方式。
**日本語版が唯一の原本**で、英語版は毎回ここから作り直す。手で両方を直すことはしない。

やっていること
1. HTML（head・本文・解説・ナビ・脚注）を英語の版に差し替える
2. スクリプトの中の**引用符で囲まれた文字列だけ**を英語に差し替える
3. できた英語版について、**「文字列リテラルの中身を全部空にすると、
   日本語版とバイト単位で一致する」**ことを確かめる。通れば、URLの解析・ホストの解決・
   punycode・パスの畳み込み・落とし穴の検出は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる（コードのコメントは対象外）

★ 3 の「文字列を空にする」は正規表現ではなく `jsblank.py`（前から1文字ずつ読む）でやる。
   `add("a", "b", "c")` のような並びで `", "` を1つの文字列と読んでしまう境界の事故を
   実際に踏んだため（2026-08-23）。

使い方: python lab/scripts/make_en_url.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank

SITE = "https://hirulab-dev.github.io/hirulab-tools"

TR = {
    # ── 解析のエラー ──────────────────────────────────────────────
    "IPv6 の閉じ括弧がありません": "the closing bracket of the IPv6 address is missing",
    "IPv6 アドレスとして読めません": "this is not a readable IPv6 address",
    "ホストに使えない文字があります": "the host contains a character that is not allowed there",
    "このブラウザはこの文字をホストに使えない文字と判定します（下位バイトが ":
        "this browser treats that character as forbidden in a host (its low byte is ",
    " のため）": ")",
    "ホストが空です": "the host is empty",
    "ホスト名に幅ゼロ接合子（ZWNJ / ZWJ）が入っています":
        "the host name contains a zero-width joiner or non-joiner",
    "ホスト名に書字方向の制御文字が入っています":
        "the host name contains a bidirectional control character",
    "ホストが空です（見えない文字だけでした）":
        "the host is empty (it was nothing but invisible characters)",
    "ホスト名に使えない文字があります": "the host name contains a character that is not allowed there",
    "IPv4 アドレスとして読めません": "this is not a readable IPv4 address",
    "スキーム（http: など）がありません。相対URLなら基準URLを入れてください":
        "there is no scheme (http: and so on). For a relative URL, fill in the base URL",
    "基準URLのパスが不透明なので、これは解決できません":
        "the base URL has an opaque path, so this cannot be resolved against it",
    "@ の後ろにホストがありません": "there is no host after the @",
    "ポート番号が大きすぎます": "the port number is too large",
    "ポート番号に数字でない文字があります": "the port number contains something that is not a digit",
    "基準URLが読めません（": "the base URL cannot be read (",
    "）": ")",

    # ── 文字体系の名前 ────────────────────────────────────────────
    "ラテン": "Latin",
    "キリル": "Cyrillic",
    "ギリシャ": "Greek",
    "漢字かな": "Han/Kana",
    "ハングル": "Hangul",

    # ── 指摘 ──────────────────────────────────────────────────────
    "タブや改行が黙って取り除かれました": "Tabs and newlines were silently removed",
    "URLの中のタブ・改行・復帰は ": "Tab, line feed and carriage return inside a URL are dropped ",
    " 文字ぶん、エラーにならずに削られます。": " times over, without raising an error. ",
    "行をまたいで貼ったURLが、見た目と違うアドレスとしてつながることがあります。":
        "A URL pasted across two lines can therefore reach an address you never saw.",
    "前後の空白や制御文字が落とされました": "Leading and trailing whitespace was dropped",
    " 文字ぶんの前後の余白は無視されます。": " characters of surrounding whitespace are ignored.",
    "幅ゼロの文字": "zero-width character",
    "書字方向の制御文字": "bidirectional control character",
    "ノーブレークスペース": "no-break space",
    "目に見えない文字が混ざっています": "There are invisible characters in this URL",
    "。画面では普通のURLに見えますが、別のアドレスです。":
        ". On screen this looks like an ordinary URL. It is a different address.",
    "@ より前は利用者名です。つながる先は @ の後ろ":
        "Everything before the @ is a user name. The address it connects to is after the @",
    "このURLがつながるのは ": "This URL connects to ",
    "（ホストなし）": "(no host)",
    " です。": ". ",
    "「": "The part reading ",
    "」の部分は利用者名で、行き先ではありません。": " is a user name, not a destination. ",
    "本物のドメインを @ の前に置いて信用させる古典的な手口があります。":
        "Putting a real domain before the @ to win trust is a classic trick.",
    "URLにパスワードが書かれています": "There is a password in this URL",
    "アクセスログ・履歴・Referer に残ります。多くのブラウザはこの形の入力自体を拒みます。":
        "It ends up in access logs, browser history and the Referer header. "
        "Most browsers refuse this form when it is typed in.",
    "Windows のネットワークパスが file:// として読まれました":
        "A Windows network path was read as a file:// URL",
    "\\\\\\\\サーバ名\\\\共有名 という書き方は、規格のURLではありません。":
        "\\\\\\\\server\\\\share is not a URL under any standard. ",
    "それでもブラウザは file://サーバ名/共有名 として読みます（読み込み時に実測して確かめています）。":
        "Browsers read it as file://server/share anyway (measured in this browser on load). ",
    "社内の共有フォルダのパスを貼ると、意図せずリンクとして成立します。":
        "Paste an internal file-share path and it quietly becomes a working link.",
    "ピリオドに見える別の文字が、本物のピリオドに直りました":
        "A character that looks like a dot was turned into a real dot",
    "全角のピリオド（。．｡）はホスト名の解析でふつうのピリオドに直されます。":
        "Fullwidth and ideographic full stops are mapped to an ordinary dot while the host is parsed. ",
    "つまり見た目と区切りの位置が変わり、別のドメインになります。実際の行き先は ":
        "The label boundaries move, so the domain is not the one you see. The real destination is ",
    "全角の文字がホスト名で半角に直りました": "Fullwidth characters in the host were folded to ASCII",
    "ホスト名は全角ASCIIを半角に直してから解決されます。実際の行き先は ":
        "Host names are folded from fullwidth to ASCII before they are resolved. The real destination is ",
    "国際化ドメインなので punycode に変換されます":
        "This is an internationalised domain, so it is converted to punycode",
    "DNS に問い合わせるのは ": "The name actually looked up in DNS is ",
    " です。メールや設定ファイルにはこちらの形で書くほうが安全です。":
        ". In mail and configuration files, this form is the safer one to write.",
    "ホスト名の1つの区切りに複数の文字体系が混ざっています":
        "One label of the host name mixes more than one script",
    "」に ": " contains ",
    " と ": " and ",
    " が混ざっています。": " together. ",
    "同じ形の別の文字を使ってドメインを見せかける手口があります。":
        "Using look-alike characters from another script to impersonate a domain is a known trick.",
    "IPアドレスの珍しい書き方です": "This is an unusual way of writing an IP address",
    "16進・8進・省略形はふつうの10進の形に直されます。実際の行き先は ":
        "Hex, octal and shortened forms are all normalised to ordinary dotted decimal. "
        "The real destination is ",
    "文字列の見た目で危ないIPをはじく仕掛けは、この形をすり抜けます。":
        "A filter that blocks dangerous addresses by matching text will not see this one.",
    "バックスラッシュがスラッシュとして扱われました": "A backslash was treated as a slash",
    "http などのスキームでは \\\\ は / と同じ意味になります（":
        "Under http and the other special schemes, \\\\ means the same as / (",
    " か所）。": " of them here). ",
    "サーバ側のライブラリは RFC 3986 に沿って別の読み方をすることがあり、そこが食い違いの元です。":
        "Server-side libraries often follow RFC 3986 instead and read it differently. "
        "That gap is where the accidents happen.",
    "ホスト名がピリオドで終わっています": "The host name ends with a dot",
    "DNS 上は正しい書き方（root を明示した形）ですが、証明書の照合や仮想ホストの設定では別名として扱われ、":
        "In DNS this is correct (it names the root explicitly), but certificate matching and "
        "virtual-host configuration treat it as a different name, ",
    "同じサイトなのにつながらないことがあります。": "so the same site can fail to load.",
    "既定のポート番号が消えました": "The default port number disappeared",
    " は ": " is the default for ",
    " の既定なので、正規化すると書かれなくなります。": ", so normalising the URL removes it. ",
    "URLを文字列で突き合わせている仕掛けでは、同じ場所が別物として扱われます。":
        "Anything that compares URLs as text will see the same place as two different ones.",
    "パスの . と .. が畳み込まれました": "The . and .. in the path were resolved away",
    "結果のパスは ": "The resulting path is ",
    "文字列のまま権限を判定していると、畳み込む前と後で結果が変わります。":
        "If access is decided from the raw text, the answer changes depending on when it is resolved.",
    "二重に符号化されている疑いがあります": "This looks like it was percent-encoded twice",
    "%25 は % そのものを表します。%2520 のような並びは、すでに符号化されたものをもう一度符号化したときに出ます。":
        "%25 stands for a literal %. A sequence such as %2520 appears when something already "
        "encoded is encoded again. ",
    "受け手が1回しか戻さないと、%20 という文字列がそのまま値になります。":
        "If the receiver decodes only once, the literal text %20 becomes the value.",
    "% のあとに16進2桁が続いていないところがあります":
        "There is a % that is not followed by two hex digits",
    " か所。エラーにはならず、% がそのままの文字として残ります。":
        " of them. This is not an error; the % simply stays as a character. ",
    "サーバ側の実装によってはここで例外を投げるものもあり、挙動が割れます。":
        "Some server-side implementations throw here instead, so behaviour splits.",
    "パスの中に %2F があります": "There is a %2F inside the path",
    "%2F は「区切りではないスラッシュ」です。ブラウザは区切りとして扱いませんが、":
        "%2F means a slash that is not a separator. The browser keeps it that way, but ",
    "前段のサーバが先に戻してから振り分けると、意図しないパスに届きます。拒否する設定のサーバもあります。":
        "a front-end server that decodes before routing will send it somewhere else entirely. "
        "Some servers reject it outright.",
    "空白がそのまま書かれています": "There are raw spaces in this URL",
    " か所。ブラウザは %20 に直しますが、": " of them. The browser turns them into %20, but ",
    "メールソフトやチャットはそこでURLが終わったと判断してリンクを切ることがあります。":
        "mail clients and chat apps often decide the URL ended there and cut the link short.",
    "クエリの + は受け手によって意味が変わります": "A + in the query means different things to different readers",
    "フォームの形（application/x-www-form-urlencoded）で読むと空白、":
        "Read as form data (application/x-www-form-urlencoded) it is a space; ",
    "URLの規格どおりに読むとプラス記号そのものです。": "read by the URL standard it is a plus sign. ",
    "同じURLでも読む側で値が変わるので、空白は %20 と書くほうが安全です。":
        "The same URL yields different values on different sides, so write %20 for a space.",
    "同じキーが複数回あります": "The same key appears more than once",
    "」「": " and ",
    "」。最初を取る実装、最後を取る実装、配列にする実装があり、規格は決めていません。":
        ". Some implementations take the first, some the last, some collect them into a list. "
        "No standard settles it. ",
    "1つだけ効くと思って書いていると、通る値が入れ替わります。":
        "If you assume only one of them counts, the value that wins can flip.",
    "クエリに ; があります": "There is a ; in the query",
    "昔は & の代わりに使えましたが、いまの標準の読み方（URLSearchParams など）では":
        "It used to work as an alternative to &, but the modern reading (URLSearchParams and friends) ",
    "ただの文字として扱われ、キーの一部になります。": "treats it as an ordinary character and folds it into the key.",
    "= が無い項目があります": "There is a field with no =",
    "」。多くの実装は空文字の値として読みますが、無視する実装もあります。":
        ". Most implementations read it as an empty value; some drop it entirely.",
    "この文字は、ブラウザによって送られ方が変わります":
        "How this character is sent depends on the browser",
    "」。WHATWG の符号化の一覧には入っていないのに、": ". It is not in the WHATWG percent-encode sets, and yet ",
    "いま見ているブラウザは符号化しました（読み込み時に実測）。":
        "the browser you are reading this in encoded it (measured on load). ",
    "別のブラウザはそのまま送ることがあり、サーバのアクセスログやルーティングで":
        "Another browser may send it untouched, and access logs and routing will then ",
    "別のパスとして扱われます。": "see two different paths.",
    "# より後ろはサーバに送られません": "Nothing after the # is sent to the server",
    "断片（fragment）はブラウザの中だけで使われます。サーバのアクセスログにも残りません。":
        "The fragment stays inside the browser. It never appears in a server access log. ",
    "アクセストークンを # の後ろに置く設計はこれを利用したものです。":
        "Putting an access token after the # is a design that relies on exactly this.",
    "見慣れないスキームなので、読み方が変わります": "This is not a special scheme, so it is read differently",
    ": は http などの特別扱いを受けないので、": ": gets none of the treatment http and friends get, so ",
    "パスは分解されず1本の文字列として扱われます（. や .. も畳み込まれません）。":
        "the path is one opaque string rather than segments (. and .. are not resolved).",
    "スキームとホスト名は小文字に直されます": "The scheme and host name are lower-cased",
    "パス・クエリ・断片はそのままです。つまり同じ場所を指すURLでも、文字列としては一致しません。":
        "The path, query and fragment are left alone. Two URLs pointing at the same place "
        "therefore need not match as text.",
    "パスの日本語は UTF-8 として符号化されます": "Non-ASCII characters in the path are encoded as UTF-8",
    "1文字が3バイト（=%XX が3つ）になります。古い仕掛けが Shift_JIS で戻そうとすると化けます。":
        "One character becomes several %XX bytes. Anything old enough to decode them as a "
        "legacy encoding will produce mojibake.",

    # ── プリセット ────────────────────────────────────────────────
    "よくある形": "an ordinary one",
    "https://example.com:8080/a/b/../c/d?q=1&q=2&name=山田+太郎#top":
        "https://example.com:8080/a/b/../c/d?q=1&q=2&name=Ada+Lovelace#top",
    "@ の手品": "the @ trick",
    "全角ピリオド": "fullwidth dot",
    "https://example。com/": "https://example。com/",
    "混ざった文字体系": "mixed scripts",
    "16進のIP": "hex IP address",
    "バックスラッシュ": "backslash",
    "二重符号化": "double encoding",
    "国際化ドメイン": "internationalised domain",
    "https://日本語.jp/ページ?キー=値": "https://münchen.example/straße?größe=3",
    "既定のポート": "default port",
    "相対URL": "relative URL",
    "空白入り": "with a space",

    # ── 画面 ──────────────────────────────────────────────────────
    "スキーム": "scheme",
    "利用者名": "user name",
    "パスワード": "password",
    "ホスト": "host",
    "ポート": "port",
    "パス": "path",
    "クエリ": "query",
    "断片（#）": "fragment (#)",
    "断片": "fragment",
    "このURLは読めません: ": "This URL cannot be read: ",
    "（なし）": "(none)",
    "（空）": "(empty)",
    "色が付いた行は、書いたものと実際に使われるものが違うところです。":
        "The highlighted rows are where what you wrote and what gets used differ. ",
    "正規化した全体: ": "Normalised: ",
    "\\n<span class=\\\"dim\\\">（利用者名とパスワードは Authorization ヘッダに回るか、そもそも送られません）</span>":
        "\\n<span class=\\\"dim\\\">(the user name and password move to an Authorization header, "
        "or are simply not sent)</span>",
    " は送られません</span>": " is not sent</span>",
    "つなぐ相手を決めるのは Host 行ではなく ": "What decides where the request goes is not the Host line but ",
    "（と、名前解決の結果）です。ポートは ": " (and what it resolves to). The port is ",
    "色が付いた行は、読み方によって値が変わるところです（+ を空白と見るかどうか）。":
        "The highlighted rows change value depending on the reading (whether + means a space).",
    "この2つの読み方では同じ値になります。": "Both readings give the same values here.",
    "https://日本語.jp/ページ": "https://münchen.example/straße",
    "こちらは読めたがブラウザは拒んだ": "this page read it, the browser refused",
    "拒否": "refused",
    "ブラウザは読めたがこちらは拒んだ: ": "the browser read it, this page refused: ",
    ": こちら ": ": here ",
    " / ブラウザ ": " / browser ",
    " <span class=\\\"dim\\\">（基準 ": " <span class=\\\"dim\\\">(base ",
    "）</span>": ")</span>",
    "自前の解析とブラウザの <code class=\\\"mono\\\">URL</code> を突き合わせた結果: ":
        "The parser on this page against this browser&#39;s own <code class=\\\"mono\\\">URL</code>: ",
    " 一致</b>": " agree</b>",
    "。食い違ったところはブラウザのほうが正しいです。":
        ". Where they disagree, the browser is the one to trust.",
    "符号化: 規格の一覧に無い「": "Encoding: this browser also encodes ",
    "」も符号化します。": ", which the standard sets do not list.",
    "符号化: 規格の一覧どおりでした。": "Encoding: exactly as the standard sets describe.",
    "\\\\\\\\サーバ名\\\\共有名 は file:// として読まれます（規格には無い決まり）。":
        "\\\\\\\\server\\\\share is read as a file:// URL here (a rule no standard defines).",
    "\\\\\\\\サーバ名\\\\共有名 はURLとして読まれません。":
        "\\\\\\\\server\\\\share is not read as a URL here.",
    "ホスト名の判定に癖があります: http 以外のスキーム（foo: など）で、":
        "Host names have a quirk here: under schemes other than http (foo: and the like), ",
    "ふつうの文字なのに拒まれるものがあります。拒まれるのは「符号位置の下位1バイトが":
        "some perfectly ordinary characters are refused. The ones refused are exactly those whose ",
    "禁止文字と同じもの」で、たとえばキリル文字の о（U+043E、下位バイトが > と同じ）が":
        "low byte equals a forbidden host character - Cyrillic о (U+043E, low byte the same as >) ",
    "そうです。この道具は、あなたのブラウザに合わせて同じところで拒みます。":
        "is one. This page refuses in the same places your browser does.",
    "ホスト名の判定に既知の癖はありませんでした。": "Host names showed none of the known quirks.",
}


def core_of(html):
    return html.split("<script>")[1].split("</script>")[0]


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "url" / "index.html"
    en_path = docs / "en" / "url.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:200])
        en = en.replace(a, b, 1)
    for a, b in sorted(TR.items(), key=lambda kv: -len(kv[0])):
        en = en.replace('"' + a + '"', '"' + b + '"')

    # 画面に出るところに日本語が残っていないか。
    # 仮名・漢字だけ見ていると約物（、。「」（））が素通りするので、そこも見る。
    body = re.sub(r"/\*.*?\*/", "", en, flags=re.S)
    body = re.sub(r"(?m)(?<!:)//.*$", "", body)
    left = re.findall("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？]+", body)
    # プリセットの見本URL（日本語のドメインとパス）は、英語版でも見本として残す
    # 全角ピリオドの見本だけは英語版でも残す（それを見せるためのプリセットなので）
    left = [x for x in left if x not in ("。",)]
    if left:
        sys.exit("日本語が %d 箇所残っています: %s" % (len(left), left[:12]))

    a, b = blank(core_of(ja)), blank(core_of(en))
    if a != b:
        for k, (x, y) in enumerate(zip(a.split("\n"), b.split("\n"))):
            if x != y:
                sys.exit("コードが一致しません（%d行目）:\n  ja: %s\n  en: %s" % (k + 1, x, y))
        sys.exit("コードの行数が違います（ja %d / en %d）" % (a.count("\n"), b.count("\n")))

    en_path.parent.mkdir(parents=True, exist_ok=True)
    en_path.write_text(en, encoding="utf-8", newline="\n")
    print("書き出した: %s" % en_path)
    print("日本語の残り: 0箇所")
    print("文字列の中身を空にしたコード: 日英でバイト単位で一致（%d バイト）" % len(a.encode()))


# ── HTML の差し替え ────────────────────────────────────────────────────────
HTML_PARTS = [
 ('<html lang="ja">', '<html lang="en">'),
 ('<title>URLの分解・組み立て — 本当にどこへつながるかを見せる</title>',
  '<title>URL Parser &amp; Builder — see where a URL really goes</title>'),
 ('<meta name="description" content="URLを部品に分けて、ブラウザとサーバが実際にどう読むかを見せる道具です。@ より前は利用者名なので本当の接続先は後ろ、全角のピリオドが普通のピリオドに直って別のドメインになる、バックスラッシュがスラッシュとして扱われる、%2520 の二重符号化、クエリの + が空白になるかどうかが受け手で割れる、といった「エラーにならないので気づけない」ところを名指しします。ブラウザ内で完結し、データはどこにも送信されません。">',
  '<meta name="description" content="Breaks a URL into its parts and shows how a browser and a server actually read it. Everything before the @ is a user name, so the real destination is after it. A fullwidth dot becomes a real dot and changes the domain. A backslash counts as a slash. %2520 is double encoding. A + in the query means a space to one reader and a plus to another. The traps that raise no error get named. Runs entirely in your browser; nothing is uploaded.">'),
 ('<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/url/">',
  '<link rel="canonical" href="https://hirulab-dev.github.io/hirulab-tools/en/url.html">'),
 ('<meta property="og:locale" content="ja_JP">', '<meta property="og:locale" content="en_US">'),
 ('<meta property="og:title" content="URLの分解・組み立て — 本当にどこへつながるかを見せる">',
  '<meta property="og:title" content="URL Parser &amp; Builder — see where a URL really goes">'),
 ('<meta property="og:description" content="URLを部品に分けて、ブラウザとサーバが実際にどう読むかを見せます。@ より前は利用者名、全角ピリオドが普通のピリオドに直る、バックスラッシュがスラッシュになる、二重符号化、クエリの + の解釈割れ。エラーにならない落とし穴を名指しします。">',
  '<meta property="og:description" content="Breaks a URL into its parts and shows how a browser and a server actually read it. The @ trick, fullwidth dots, backslashes, double encoding, and the + that means two different things. The traps that raise no error get named.">'),
 ('<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/url/">',
  '<meta property="og:url" content="https://hirulab-dev.github.io/hirulab-tools/en/url.html">'),
 ('<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-url.png">',
  '<meta property="og:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-url-en.png">'),
 ('<meta name="twitter:title" content="URLの分解・組み立て — 本当にどこへつながるかを見せる">',
  '<meta name="twitter:title" content="URL Parser &amp; Builder — see where a URL really goes">'),
 ('<meta name="twitter:description" content="URLを部品に分けて、ブラウザとサーバが実際にどう読むかを見せます。エラーにならない落とし穴を名指しします。ブラウザ内で完結します。">',
  '<meta name="twitter:description" content="Breaks a URL into its parts and shows how a browser and a server actually read it. The traps that raise no error get named. Runs entirely in your browser.">'),
 ('<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-url.png">',
  '<meta name="twitter:image" content="https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-url-en.png">'),
 ('  "name": "URLの分解・組み立て",\n  "url": "https://hirulab-dev.github.io/hirulab-tools/url/",\n  "description": "URLを部品に分けて、ブラウザとサーバが実際にどう読むかを見せる道具です。@ より前は利用者名なので本当の接続先は後ろ、全角のピリオドが普通のピリオドに直って別のドメインになる、バックスラッシュがスラッシュとして扱われる、%2520 の二重符号化、クエリの + が空白になるかどうかが受け手で割れる、といったエラーにならない落とし穴を名指しします。ブラウザ内で完結します。",',
  '  "name": "URL Parser & Builder",\n  "url": "https://hirulab-dev.github.io/hirulab-tools/en/url.html",\n  "description": "Breaks a URL into its parts and shows how a browser and a server actually read it. Everything before the @ is a user name, a fullwidth dot becomes a real dot and changes the domain, a backslash counts as a slash, %2520 is double encoding, and a + in the query means a space to one reader and a plus to another. The traps that raise no error get named. Runs entirely in your browser.",'),
 ('  "inLanguage": "ja",', '  "inLanguage": "en",'),
 ('  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-url.png",',
  '  "image": "https://hirulab-dev.github.io/hirulab-tools/ogp/ogp-url-en.png",'),
 ('  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },\n  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "https://hirulab-dev.github.io/hirulab-tools/" }',
  '  "author": { "@type": "Organization", "name": "Claude\'s Daytime Lab", "url": "https://note.com/hirulab" },\n  "isPartOf": { "@type": "WebSite", "name": "Claude\'s Daytime Lab — tools", "url": "https://hirulab-dev.github.io/hirulab-tools/en/" }'),
 ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
  '  "browserRequirements": "A modern browser with JavaScript enabled",'),
 ('<meta property="og:site_name" content="クロードの昼ラボ">',
  '<meta property="og:site_name" content="Claude\'s Daytime Lab">'),

 ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>\n  <h1>URLの分解・組み立て</h1>',
  '  <a class="hl-back" href="./">← Claude&#39;s Daytime Lab tools</a>\n  <h1>URL Parser &amp; Builder</h1>'),

 ('''  <p class="lead">URLを部品に分けて、<strong>ブラウザとサーバが実際にどう読むか</strong>を見せる道具です。
    URLの読み方には<strong>エラーが出ないまま、書いた人の思っているのと違う場所を指す</strong>書き方が
    いくつもあります。<code>https://example.com@evil.test/</code> がつながる先は
    <code>evil.test</code> です。この道具は、そういうところを名指しします。</p>''',
  '''  <p class="lead">Breaks a URL into its parts and shows <strong>how a browser and a server
    actually read it</strong>. Plenty of URLs point somewhere other than their author expected
    <strong>without raising a single error</strong>. <code>https://example.com@evil.test/</code>
    connects to <code>evil.test</code>. This page names those places.</p>'''),

 ('''  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    解析はすべてブラウザの中でやっています。読み込んだあとは機内モードでも動きます。
    入力したURL（社内のアドレスやトークン付きのリンクを含みます）がどこかに送られることはありません。
    <strong>入れたURLを開きにいくこともありません。</strong>
  </div>''',
  '''  <div class="privacy">
    <strong>This page makes no network requests.</strong>
    All parsing happens in your browser; once loaded it works offline.
    Nothing you paste — internal addresses, links carrying tokens — is sent anywhere.
    <strong>The URL you enter is never fetched either.</strong>
  </div>'''),

 ('      <label for="base">基準URL（相対URLを解決したいときだけ）</label>',
  '      <label for="base">Base URL (only needed to resolve a relative URL)</label>'),
 ('    <label for="src" class="hide">URL</label>', '    <label for="src" class="hide">URL</label>'),

 ('    <h2>分解した結果</h2>', '    <h2>The parts</h2>'),
 ('        <thead><tr><th>部品</th><th>書いたもの</th><th>実際に使われるもの</th></tr></thead>',
  '        <thead><tr><th>part</th><th>what you wrote</th><th>what gets used</th></tr></thead>'),
 ('    <h2>サーバにはこう届く</h2>', '    <h2>What the server receives</h2>'),
 ('    <h2>クエリ文字列</h2>', '    <h2>The query string</h2>'),
 ('        <thead><tr><th>#</th><th>キー</th><th>値（%だけ戻す）</th><th>値（フォーム式・+も空白に）</th></tr></thead>',
  '        <thead><tr><th>#</th><th>key</th><th>value (percent only)</th><th>value (form style, + as space)</th></tr></thead>'),
 ('    <h2>気をつけるところ</h2>', '    <h2>Things to watch out for</h2>'),
 ('    <p class="none" id="notesNone">いまのところ指摘はありません。</p>',
  '    <p class="none" id="notesNone">Nothing to flag right now.</p>'),
 ('    <h2>組み立て直す</h2>', '    <h2>Rebuild it</h2>'),
 ('    <p class="none">部品を書き換えると、必要なところだけ符号化して組み立て直します。</p>',
  '    <p class="none">Edit any part and the URL is reassembled, encoding only what has to be encoded.</p>'),
 ('    <h2>このブラウザの符号化</h2>', '    <h2>What this browser does</h2>'),
 ('    <h2>自己検査</h2>', '    <h2>Self-check</h2>'),

 ('''    <summary>この道具は何を自分で計算しているのか</summary>
    <ul>
      <li><b>URLの解析はブラウザの <code>URL</code> を使わず、自分で書いています。</b>
        WHATWG URL Standard の手順（scheme の読み取り、ホストの解析、パスの
        <code>.</code> <code>..</code> の畳み込み、部品ごとに違う符号化の範囲）をなぞった実装です。</li>
      <li>ホスト名の <b>punycode（<code>xn--</code>）の変換も自前</b>です（RFC 3492）。
        <b>IPv4 の変な書き方</b>（<code>0x7f.1</code> や <code>2130706433</code>）や
        <b>IPv6 の圧縮</b>もこちらで解いています。</li>
      <li>自前である以上ずれる可能性があります。だから<b>毎回その場でブラウザの
        <code>URL</code> と突き合わせ、結果を自己検査の欄に出しています</b>。
        食い違ったらブラウザのほうが正しいと表示します。</li>
      <li><b>できていないところも書いておきます。</b>
        国際化ドメインの文字変換（UTS #46）は、よく出る対応（全角→半角、大文字→小文字、
        3種類の全角ピリオド）だけを実装しています。すべての文字の対応表は持っていません。
        取りこぼしがあれば自己検査に ✗ が出ます。</li>
    </ul>''',
  '''    <summary>What this page computes for itself</summary>
    <ul>
      <li><b>The URL parsing does not use the browser&#39;s <code>URL</code> — it is written here.</b>
        It follows the WHATWG URL Standard: reading the scheme, parsing the host, resolving
        <code>.</code> and <code>..</code> in the path, and the different percent-encode set each
        component uses.</li>
      <li><b>The punycode conversion (<code>xn--</code>) is written here too</b> (RFC 3492), along with
        <b>the odd ways of writing an IPv4 address</b> (<code>0x7f.1</code>, <code>2130706433</code>)
        and <b>IPv6 compression</b>.</li>
      <li>Anything written from scratch can drift. So <b>every keystroke, the result is compared
        against this browser&#39;s own <code>URL</code></b> and the outcome is shown in the
        self-check box. If they disagree, the browser is the one to trust.</li>
      <li><b>Here is what is missing.</b> Of the IDNA character mapping (UTS #46), only the common
        cases are implemented: fullwidth to ASCII, upper to lower case, the three fullwidth full
        stops, and the characters that map to nothing. There is no complete mapping table here.
        Anything missed shows up as a ✗ in the self-check.</li>
    </ul>'''),

 ('''  <nav class="hl-nav">
    <h2>ほかの道具</h2>
    <ul>
      <li><a href="../regex/">正規表現テスタ</a></li>
      <li><a href="../regex-why/">正規表現がなぜマッチしないか診断</a></li>
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
      <li><a href="../headers/">HTTPヘッダの読み下し</a></li>
      <li><a href="../jwt/">JWTの読み下し</a></li>
      <li><a href="../en/url.html">English version</a></li>
      <li><a href="../password/">パスワード生成・強度診断</a></li>
      <li><a href="../base64/">Base64・データURLの分解</a></li>
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
      <li><a href="./replace.html">Regex Replacement Preview</a></li>
      <li><a href="./regex-tester.html">Regex Tester</a></li>
      <li><a href="./char-counter.html">Character Counter</a></li>
      <li><a href="./palette.html">Color Palette</a></li>
      <li><a href="./timezone.html">Time Zone Converter</a></li>
      <li><a href="./csv.html">CSV Preview &amp; Diagnostics</a></li>
      <li><a href="./headers.html">HTTP Header Explainer</a></li>
      <li><a href="./jwt.html">JWT Explainer</a></li>
      <li><a href="../url/">Japanese version</a></li>
      <li><a href="./password.html">Password Generator &amp; Strength Check</a></li>
      <li><a href="./base64.html">Base64 &amp; Data URL Explainer</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">All tools (English)</a> ·
      <a href="../">Japanese site</a> ·
      <a href="https://x.com/hirulab_ai">X</a> ·
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''),

 ('''    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    読み方は WHATWG URL Standard（ブラウザが従っているもの）に合わせています。
    サーバ側のライブラリは RFC 3986 に沿った別の読み方をすることがあり、
    <b>その食い違い自体が事故のもと</b>です。指摘欄ではそこも書いています。''',
  '''    Built by Claude&#39;s Daytime Lab (Claude, an AI). Free, no sign-up.
    The reading follows the WHATWG URL Standard, which is what browsers implement.
    Server-side libraries often follow RFC 3986 instead, and
    <b>that gap is itself where the accidents come from</b> — the notes above say where.'''),
]


if __name__ == "__main__":
    main()
