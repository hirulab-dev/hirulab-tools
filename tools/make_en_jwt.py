#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「JWTの読み下し」の英語版を、日本語版から作る（2026-08-24）。

`make_en_railroad.py` / `make_en_regex_why.py` / `make_en_replace.py` /
`make_en_url.py` / `make_en_headers.py` と同じ方式。**日本語版が唯一の原本**で、
英語版は毎回ここから作り直す。

やっていること
1. HTML（head・本文・解説・ナビ・脚注）を英語の版に差し替える
2. スクリプトの中の**引用符で囲まれた文字列だけ**を英語に差し替える
3. できた英語版について、**「文字列の中身を全部空にすると、日本語版とバイト単位で
   一致する」**ことを確かめる。通れば、base64url の復号・UTF-8 の復号・JSON の読み取り・
   落とし穴の検出・署名の検証は1バイトも違わない
4. 画面に出るところに日本語が1文字も残っていないことを確かめる（コードのコメントは対象外）

使い方: python lab/scripts/make_en_jwt.py <リポジトリの docs>
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from jsblank import blank

SITE = "https://hirulab-dev.github.io/hirulab-tools"

TR = {
    # ── base64url / UTF-8 の復号のエラー ───────────────────────────
    "詰めの = の数が合っていません。": "The number of padding characters does not add up.",
    "base64 に置けない文字が ": "There is a character that cannot appear in base64, at position ",
    " 文字目にあります: ": ": ",
    "長さが 4 で割って 1 余ります。base64 としてありえない長さです。":
        "The length leaves a remainder of 1 when divided by 4. No base64 string can have that length.",
    "バイト目が UTF-8 の先頭バイトとして読めません。":
        " cannot start a UTF-8 sequence.",
    "UTF-8 の途中で終わっています。": "The UTF-8 sequence is cut off.",
    "バイト目が UTF-8 の続きバイトになっていません。":
        " is not a UTF-8 continuation byte.",
    "必要以上に長い書き方（overlong）の UTF-8 があります。":
        "There is an overlong UTF-8 sequence: a character written with more bytes than it needs.",
    "サロゲートの符号位置が UTF-8 で書かれています。":
        "A surrogate code point is encoded in UTF-8, which is not allowed.",
    "U+10FFFF より大きい符号位置があります。":
        "There is a code point above U+10FFFF.",

    # ── JSON の読み取りのエラー ────────────────────────────────────
    "値が来るはずのところで終わっています": "The text ends where a value should be",
    "値として読めない文字があります": "There is a character that cannot start a value",
    "名前は二重引用符で囲む決まりです": "A member name has to be in double quotes",
    "名前のあとに : がありません": "There is no colon after the name",
    ", か } が来るはずです": "A comma or a closing brace should come here",
    ", か ] が来るはずです": "A comma or a closing bracket should come here",
    "文字列が閉じていません": "The string is not closed",
    "\\\\u のあとは16進4桁です": "\\\\u has to be followed by four hex digits",
    "使えない逃がし方です": "That is not a valid escape",
    "文字列の中に制御文字を直接置くことはできません":
        "A control character cannot appear directly inside a string",
    "数として読めません": "That cannot be read as a number",
    "小数点のあとに数字がありません": "There is no digit after the decimal point",
    "指数のあとに数字がありません": "There is no digit after the exponent",
    "JSON のあとに余分な文字があります": "There is trailing text after the JSON value",
    "（文字位置 ": " (at character ",
    "）": ")",
    "（": " (",

    # ── 部分ごとの前置き ──────────────────────────────────────────
    "1つめの部分（ヘッダ）: ": "First part (the header): ",
    "2つめの部分（中身）: ": "Second part (the payload): ",
    "1つめの部分（ヘッダ）が JSON として読めません: ":
        "The first part (the header) is not readable as JSON: ",
    "2つめの部分（中身）が JSON として読めません: ":
        "The second part (the payload) is not readable as JSON: ",
    "ヘッダが JSON のオブジェクトになっていません。": "The header is not a JSON object.",
    "中身が JSON のオブジェクトになっていません。": "The payload is not a JSON object.",
    "3つめの部分（署名）: ": "Third part (the signature): ",

    # ── アルゴリズム ──────────────────────────────────────────────
    "共有の秘密を使う HMAC（SHA-256）": "HMAC with a shared secret (SHA-256)",
    "共有の秘密を使う HMAC（SHA-384）": "HMAC with a shared secret (SHA-384)",
    "共有の秘密を使う HMAC（SHA-512）": "HMAC with a shared secret (SHA-512)",
    "RSA の署名（PKCS#1 v1.5・SHA-256）": "RSA signature (PKCS#1 v1.5, SHA-256)",
    "RSA の署名（PKCS#1 v1.5・SHA-384）": "RSA signature (PKCS#1 v1.5, SHA-384)",
    "RSA の署名（PKCS#1 v1.5・SHA-512）": "RSA signature (PKCS#1 v1.5, SHA-512)",
    "RSA の署名（PSS・SHA-256）": "RSA signature (PSS, SHA-256)",
    "RSA の署名（PSS・SHA-384）": "RSA signature (PSS, SHA-384)",
    "RSA の署名（PSS・SHA-512）": "RSA signature (PSS, SHA-512)",
    "楕円曲線の署名（P-256・SHA-256）": "Elliptic curve signature (P-256, SHA-256)",
    "楕円曲線の署名（P-384・SHA-384）": "Elliptic curve signature (P-384, SHA-384)",
    "楕円曲線の署名（P-521・SHA-512）": "Elliptic curve signature (P-521, SHA-512)",
    "署名しない": "not signed at all",

    # ── 時間の単位 ────────────────────────────────────────────────
    "秒": "s",
    "分": "m",
    "時間": "h",
    "日": "d",
    "年": "y",
    "あと ": "in ",
    "前": " ago",

    # ── ヘッダの項目の名前 ────────────────────────────────────────
    "どうやって署名したか": "how this was signed",
    "このものの種類": "what kind of thing this is",
    "中身の種類": "what kind of thing the payload is",
    "どの鍵で署名したかの目印": "a label for which key signed this",
    "鍵の一覧（JWK Set）が置いてあるURL": "a URL where the key set (JWK Set) lives",
    "署名に使った公開鍵そのもの": "the public key itself, claimed to be the signing key",
    "証明書が置いてあるURL": "a URL where the certificate lives",
    "証明書そのもの（並び）": "the certificate chain itself",
    "証明書の指紋（SHA-1）": "the certificate fingerprint (SHA-1)",
    "証明書の指紋（SHA-256）": "the certificate fingerprint (SHA-256)",
    "受け手が必ず理解しなければならない項目": "entries the recipient must understand",
    "中身をどう暗号化したか（JWE のもの）": "how the payload is encrypted (a JWE field)",
    "中身をどう圧縮したか（JWE のもの）": "how the payload is compressed (a JWE field)",

    # ── クレームの名前 ────────────────────────────────────────────
    "発行した人（issuer）": "who issued it (issuer)",
    "誰についてのものか（subject）": "who it is about (subject)",
    "誰に向けたものか（audience）": "who it is for (audience)",
    "いつまで使えるか（expiration time）": "when it stops working (expiration time)",
    "いつから使えるか（not before）": "when it starts working (not before)",
    "いつ発行したか（issued at）": "when it was issued (issued at)",
    "このトークン1枚の通し番号（JWT ID）": "a serial number for this one token (JWT ID)",

    # ── 入力のそうじ ──────────────────────────────────────────────
    "先頭の Bearer を取り除いて読みました。": "The leading Bearer was stripped before reading. ",
    "HTTPの Authorization ヘッダの形のまま貼られたようです。トークン本体は Bearer とスペースより後ろです。":
        "This looks like it was pasted straight from an HTTP Authorization header. The token itself is everything after Bearer and the space.",
    "前後や途中の空白・改行を取り除いて読みました。":
        "Whitespace and line breaks were stripped before reading. ",
    "JWT に空白は入りません。コピーのときに折り返しが混ざったものと見なして詰めました。":
        "A JWT never contains whitespace, so this was treated as wrapping introduced by the copy and closed up.",
    "前後の引用符を取り除いて読みました。": "The surrounding quotes were stripped before reading. ",
    "JSON の値としてコピーしたときに付いてくるものです。トークン本体に引用符は入りません。":
        "Those come along when the token is copied as a JSON value. The token itself has no quotes.",

    # ── 形 ────────────────────────────────────────────────────────
    "これは暗号化されたトークン（JWE）です。": "This is an encrypted token (a JWE). ",
    "5つの部分に分かれています。中身は鍵が無いと読めません。この道具は開きません。":
        "It has five parts, and the payload cannot be read without a key. This tool does not open it.",
    "部分が2つしかありません。署名がありません。": "There are only two parts, so there is no signature. ",
    "RFC 7515 は署名なしのときも末尾のピリオドを残すと決めています。ここが欠けていると、ライブラリによっては読めません。":
        "RFC 7515 says the trailing period stays even when there is no signature. Without it, some libraries will refuse to read the token.",

    # ── alg ───────────────────────────────────────────────────────
    "ヘッダに alg がありません。": "The header has no alg. ",
    "RFC 7515 では必須です。受け手が既定値で補うと、その既定値が何かによって検証の強さが変わります。":
        "RFC 7515 requires it. If the recipient fills in a default, how strong the check is depends entirely on what that default happens to be.",
    "alg が文字列ではありません。": "alg is not a string. ",
    "アルゴリズムの名前は文字列です。数値や真偽値を入れると、比較のしかたによっては素通りします。":
        "An algorithm name is a string. Put a number or a boolean there and, depending on how the comparison is written, it can slip straight through.",
    "alg が none です。このトークンには署名がありません。":
        "alg is none, so this token carries no signature at all. ",
    "誰でも中身を書き換えられます。受け手がヘッダの alg を信じて検証方法を決める作りだと、攻撃者が alg を none にするだけで通ります。受け手は「期待するアルゴリズム」を先に決めておく必要があります。":
        "Anyone can rewrite the payload. If the recipient trusts the alg in the header to decide how to verify, an attacker only has to set alg to none. The recipient has to decide which algorithm it expects before it looks at the token.",
    "alg の大文字小文字が規格と違います。": "The case of alg does not match the standard. ",
    "アルゴリズムの名前は大文字小文字を区別します。ここが違うと、多くのライブラリは知らない名前として拒みますが、大文字小文字を無視して比べる実装だと none が通ってしまいます。":
        "Algorithm names are case sensitive. Most libraries will reject an unknown name, but an implementation that compares case-insensitively will let none through.",
    "知らないアルゴリズムです: ": "This is not an algorithm this tool knows: ",
    "RFC 7518 の一覧にありません。独自のものかもしれませんが、受け手が対応していなければ検証できません。":
        "It is not in the RFC 7518 registry. It may be a private one, but a recipient that does not implement it cannot verify anything.",
    "共有の秘密で署名しています（": "This is signed with a shared secret (",
    "）。": "). ",
    "検証する側も署名する側と同じ秘密を持ちます。つまり受け手も偽造できます。第三者に検証だけさせたいときは RS256 や ES256 のような公開鍵方式にします。":
        "Whoever verifies holds the same secret as whoever signs, which means the recipient can forge tokens too. If a third party should only be able to verify, use a public key algorithm such as RS256 or ES256.",
    "公開鍵方式です。受け手が alg を見て検証方法を切り替えていないか確かめてください。":
        "This uses a public key. Check that the recipient does not pick its verification method by reading alg. ",
    "公開鍵は誰でも手に入るので、攻撃者が alg を HS256 に書き換え、その公開鍵を「共有の秘密」として署名し直す手があります（アルゴリズム混同）。受け手は期待するアルゴリズムを固定するべきです。":
        "The public key is public, so an attacker can rewrite alg to HS256 and re-sign the token using that public key as the shared secret. This is algorithm confusion. The recipient should pin the algorithm it expects.",

    # ── typ / kid / jwk / jku / x5u / crit ────────────────────────
    "typ が JWT ではありません: ": "typ is not JWT: ",
    "用途を分ける書き方です（例: at+jwt はアクセストークン）。受け手が用途を見ずに受けると、別の用途のトークンを取り違えて受け入れます。":
        "This is how one use is separated from another, for example at+jwt for an access token. A recipient that never looks at the use will happily accept a token minted for something else.",
    "ヘッダに typ がありません。": "The header has no typ. ",
    "無くても規格には反しません。ただし RFC 8725 は、用途の違うトークンの取り違えを防ぐために typ を書くことを勧めています。":
        "That does not break the standard. RFC 8725 does recommend writing it, so that tokens meant for different uses cannot be mistaken for one another.",
    "kid にパスのような文字が入っています: ": "kid contains something that looks like a path: ",
    "kid をそのままファイル名に使う実装だと、任意のファイルを鍵として読ませられます。中身の分かるファイルを指させれば署名を作れます。":
        "An implementation that uses kid directly as a filename can be made to read any file as the key. Point it at a file whose contents are known and you can forge a signature.",
    "kid に命令として解釈されうる文字が入っています。":
        "kid contains characters that could be read as commands. ",
    "kid を SQL やシェルに組み込む実装だと、そのまま注入になります。":
        "An implementation that drops kid into SQL or a shell has an injection right there.",
    "kid が文字列ではありません。": "kid is not a string. ",
    "鍵の目印は文字列です。": "A key label is a string.",
    "ヘッダに公開鍵そのもの（jwk）が埋め込まれています。":
        "The header carries a public key of its own (jwk). ",
    "受け手がこの鍵で検証してしまうと、誰でも自分の鍵で署名した偽のトークンを通せます。埋め込まれた鍵は、あらかじめ信頼している鍵と一致するときだけ使えます。":
        "If the recipient verifies with that key, anyone can sign a forged token with their own key and have it accepted. An embedded key is only usable when it matches a key that was already trusted.",
    "ヘッダに鍵の置き場所のURL（jku）が入っています: ":
        "The header names a URL where the key lives (jku): ",
    "受け手がこのURLを取りにいく作りだと、攻撃者が自分のURLを書いて自分の鍵で検証させられます。取りにいく先は、あらかじめ決めた場所に限る必要があります。この道具はURLを開きません。":
        "If the recipient fetches that URL, an attacker can write their own URL and have the token verified against their own key. Fetching has to be limited to places decided in advance. This tool never opens the URL.",
    "ヘッダに証明書の置き場所のURL（x5u）が入っています。":
        "The header names a URL where the certificate lives (x5u). ",
    "jku と同じ問題があります。受け手が指定されたURLを取りにいくなら、その先を攻撃者が決められます。":
        "This has the same problem as jku. If the recipient fetches whatever URL the token names, the attacker chooses the destination.",
    "crit が空でない配列になっていません。": "crit is not a non-empty array. ",
    "RFC 7515 は空でない文字列の配列と決めています。":
        "RFC 7515 says it has to be a non-empty array of strings.",
    "crit に挙げた項目がヘッダにありません: ":
        "Entries listed in crit are missing from the header: ",
    "crit は「これを理解できないなら受け取るな」という指定です。挙げた項目そのものが無いのは規格違反で、受け手は拒むべき形です。":
        "crit means do not accept this unless you understand these entries. Listing an entry that is not there breaks the standard, and the recipient is supposed to reject the token.",
    "crit があります。受け手がこの項目を理解できなければ拒む決まりです。":
        "There is a crit entry. The recipient has to reject the token unless it understands it. ",
    "対応していない受け手はエラーになります。相手を選ぶトークンです。":
        "A recipient that does not implement it will fail. This token is picky about who reads it.",
    "ヘッダに同じ名前が2回以上あります: ": "A name appears more than once in the header: ",
    "JSON の読み手によって前勝ち・後ろ勝ちが割れます。検証する側と中身を見る側が違う値を読む余地が生まれます。":
        "Whether the first or the last one wins depends on the JSON reader. That leaves room for the code that verifies and the code that reads the claims to see different values.",

    # ── 時刻 ──────────────────────────────────────────────────────
    " が文字列で書かれています: ": " is written as a string: ",
    "RFC 7519 は数値（NumericDate）と決めています。文字列を数値に直してから比べる実装なら通りますが、厳しい実装は拒みます。":
        "RFC 7519 says it has to be a number (a NumericDate). An implementation that converts before comparing will accept it; a strict one will not.",
    " が数値ではありません。": " is not a number. ",
    "1970年1月1日からの秒数を数値で書く決まりです。":
        "It has to be a number of seconds since 1 January 1970.",
    " がミリ秒で入っているようです（": " looks like it is in milliseconds (",
    "秒として読むと ": "Read as seconds that is ",
    " になります。JWT の時刻は秒です。1000倍したまま入れると、期限切れが永久に来ません。":
        ". Times in a JWT are in seconds. Leave the value multiplied by 1000 and the expiry never arrives.",
    "exp がありません。このトークンは自分では期限切れになりません。":
        "There is no exp, so this token never expires on its own. ",
    "受け手が別の方法で期限を決めていない限り、盗まれたら永久に使えます。":
        "Unless the recipient bounds its lifetime some other way, a stolen token works forever.",
    "期限が切れています（": "It has expired (",
    "受け手は拒むはずです。それでも通るなら、受け手が exp を見ていません。":
        "The recipient should reject it. If it still works, the recipient is not looking at exp.",
    "発行から期限までが1年を超えています（":
        "More than a year passes between issuing and expiry (",
    "長いほど、盗まれたときに使える時間も長くなります。短くして更新する形が勧められています。":
        "The longer that window, the longer a stolen token is useful. Short lifetimes with renewal are the recommended shape.",
    "発行から期限までが1日を超えています（":
        "More than a day passes between issuing and expiry (",
    "用途によりますが、アクセストークンとしては長めです。":
        "It depends on the use, but that is on the long side for an access token.",
    "まだ使えません（使えるのは ": "It is not usable yet (it starts ",
    "nbf はここから使えるという指定です。時計が少しずれているだけのこともあります。":
        "nbf says when the token starts working. Sometimes this is only a small clock difference.",
    "nbf が exp 以降になっています。このトークンは一度も使えません。":
        "nbf is at or after exp, so this token is never usable. ",
    "使えるようになる前に期限が切れます。作った側の計算違いです。":
        "It expires before it starts working. Whoever minted it got the arithmetic wrong.",
    "発行時刻が未来になっています（": "The issue time is in the future (",
    "発行した機械とこのブラウザの時計がずれているか、値が間違っています。":
        "Either the issuing machine and this browser disagree about the time, or the value is simply wrong.",

    # ── クレームの有無 ────────────────────────────────────────────
    "iss がありません。誰が発行したか書かれていません。":
        "There is no iss, so the token does not say who issued it. ",
    "受け手が複数の発行元を扱うなら、発行元ごとに鍵を選べません。":
        "If the recipient accepts more than one issuer, it cannot pick a key per issuer.",
    "aud がありません。誰に向けたものか書かれていません。":
        "There is no aud, so the token does not say who it is for. ",
    "別のサービス向けに出したトークンを、そのまま自分のところで受けてしまう余地が残ります。":
        "That leaves room to accept a token that was minted for a different service.",
    "aud が配列です。": "aud is an array. ",
    "規格上どちらも正しい書き方ですが、受け手が文字列としてしか比べていないと、配列のときに一致しません。":
        "Both shapes are allowed, but a recipient that only ever compares strings will not match when it gets an array.",
    "jti がありません。同じトークンの使い回しを見分けられません。":
        "There is no jti, so a replayed token cannot be told apart. ",
    "一度使ったら無効にする作りにするなら、1枚ごとの通し番号が要ります。":
        "If a token should stop working once used, each one needs its own serial number.",
    "sub が数値です。": "sub is a number. ",
    "RFC 7519 は文字列（StringOrURI）と決めています。数値のまま比べる受け手と、文字列に直して比べる受け手で結果が割れます。":
        "RFC 7519 says it has to be a string (StringOrURI). A recipient that compares numbers and one that converts to strings will disagree.",
    "中身に秘密らしい名前があります: ":
        "The payload has names that look like secrets: ",
    "JWT の中身は暗号化されていません。base64 を戻せば誰でも読めます。パスワードや鍵をここに入れてはいけません。":
        "The payload of a JWT is not encrypted. Undo the base64 and anyone can read it. Passwords and keys do not belong here.",
    "中身に個人情報らしい名前があります: ":
        "The payload has names that look like personal data: ",
    "同じく暗号化されていません。ブラウザの保存領域やログ、プロキシの記録に、そのまま平文で残ります。":
        "That is not encrypted either. It sits in browser storage, in logs and in proxy records, in the clear.",
    "中身に同じ名前が2回以上あります: ": "A name appears more than once in the payload: ",
    "検証する側と権限を見る側で違う値を読む余地が生まれます。JSON の読み手しだいで前勝ち・後ろ勝ちが変わります。":
        "That leaves room for the code that verifies and the code that checks permissions to read different values. Whether the first or the last one wins depends on the JSON reader.",
    "倍精度で正確に表せない大きさの整数があります。":
        "There is an integer too large to be represented exactly in double precision. ",
    "JavaScript で読むと値が変わります。受け手の言語によって別の数になるので、比較が成り立ちません。":
        "Reading it in JavaScript changes the value. Different languages end up with different numbers, so comparisons stop meaning anything.",

    # ── 符号化 ────────────────────────────────────────────────────
    "　": " — ",
    "ヘッダの段": "the header segment",
    "中身の段": "the payload segment",
    "署名の段": "the signature segment",
    "ヘッダ": "Header",
    "中身": "Payload",
    "署名": "Signature",
    "詰めの = が付いています（": "There is base64 padding (",
    "・": ", ",
    "RFC 7515 は base64url の詰めを書かないと決めています。受ける実装と拒む実装があります。":
        "RFC 7515 says base64url here is written without padding. Some implementations accept it anyway and some refuse.",
    "url-safe でない + と / が使われています（": "Characters + and / appear, which are not url-safe (",
    "JWT は base64url です。URLやフォームに載せると + が空白に化けて、署名が合わなくなります。":
        "A JWT uses base64url. Put this in a URL or a form and the + turns into a space, and then the signature no longer matches.",
    "末尾の余ったビットが0になっていません（": "The leftover bits at the end are not zero (",
    "正規化されていない base64 です。別の文字を書いても同じバイト列に戻るので、署名の対象になった文字列と読み取った中身が食い違う余地が生まれます。":
        "This is non-canonical base64. A different string decodes to the same bytes, which leaves room for the text that was signed and the content that was read to drift apart.",

    # ── 署名 ──────────────────────────────────────────────────────
    "alg が none なのに署名が入っています。": "alg is none, yet a signature is present. ",
    "受け手は空でなければ拒むべきです。": "The recipient should reject anything that is not empty.",
    " の署名が DER の形になっています（": " signature is in DER form (",
    "バイト）。": " bytes). ",
    "JOSE の楕円曲線署名は R と S を固定長で並べた ":
        "A JOSE elliptic curve signature is R and S written back to back at fixed length, ",
    "バイトです。OpenSSL 系のライブラリはそのままだと DER を出すので、変換を忘れると相手が検証できません。":
        " bytes in total. OpenSSL style libraries hand back DER by default, so forget the conversion and the other side cannot verify.",
    " の署名の長さが合いません（": " signature is the wrong length (",
    "バイト、正しくは ": " bytes, it should be ",
    "この長さでは検証は必ず失敗します。": "At this length verification is guaranteed to fail.",
    "署名は空です。": "The signature is empty. ",
    "alg が none のときの正しい形です。中身は誰でも書き換えられます。":
        "That is the correct shape when alg is none. Anyone can rewrite the payload.",
    "トークンが ": "The token is ",
    "文字あります。": " characters long. ",
    "Cookie の1個あたりの上限（およそ4KB）を超えます。HTTPヘッダの上限（サーバによっては8KB）に当たることもあります。":
        "That is over the per-cookie limit of roughly 4KB, and it can also run into header size limits, which are 8KB on some servers.",

    # ── 署名の検証（画面） ────────────────────────────────────────
    "このブラウザには crypto.subtle がありません。": "This browser has no crypto.subtle.",
    "JWK の JSON として読めません。": "That is not readable as JWK JSON.",
    "PEM として読めません。": "That is not readable as PEM.",
    "アルゴリズム": "Algorithm",
    "署名の長さ": "Signature length",
    " バイト": " bytes",
    " は ": " uses ",
    " バイト）": " bytes)",
    "署名の対象": "What was signed",
    "1つめと2つめの部分を、ピリオドでつないだ文字列そのもの（":
        "The first and second parts, joined by a period, exactly as written (",
    " 文字）": " characters)",
    "署名はありません。": "There is no signature. ",
    "alg が none のトークンは、中身が本物である保証をまったく持ちません。":
        "A token with alg none carries no guarantee at all that its payload is genuine.",
    "鍵を入れていないので、署名は確かめていません。":
        "No key was given, so the signature has not been checked. ",
    "よく使われる秘密を試しています…": "Trying the secrets people leave in by mistake...",
    "上の欄に共有の秘密を入れると確かめます。":
        "Put the shared secret in the box above and it will be checked.",
    "上の欄に公開鍵（JWK か PEM）を入れると確かめます。":
        "Put the public key in the box above, as JWK or PEM, and it will be checked.",
    "確かめています…": "Checking... ",
    "署名は正しいです。": "The signature is valid. ",
    "この鍵で署名されたもので、1つめと2つめの部分は書き換えられていません。":
        "It was signed with this key, and the first and second parts have not been altered.",
    "署名が合いません。": "The signature does not match. ",
    "鍵が違うか、中身が書き換えられているか、アルゴリズムの取り違えです。":
        "Either the key is wrong, the payload was altered, or the algorithm is not the one you think.",
    "確かめられませんでした。": "It could not be checked. ",
    "よく使われる秘密 ": "None of the ",
    " 個では検証できませんでした（それ自体は良いことです）。":
        " commonly used secrets verified this token, which is a good sign.",
    "秘密が当てられました: ": "The secret was guessed: ",
    "よく使われる秘密の一覧に入っていたものです。この鍵を知っている人は誰でも、好きな中身のトークンを作れます。すぐ変えてください。":
        "It is on the list of secrets people leave in by mistake. Anyone who knows this key can mint a token with any payload they like. Change it now.",

    # ── 画面のいろいろ ────────────────────────────────────────────
    "ピリオドで区切った部分が ": "There are ",
    " 個あります。JWT は署名つきなら3個、暗号化されていれば5個です。":
        " period-separated parts. A signed JWT has three and an encrypted one has five.",
    "読めませんでした。": "This could not be read.",
    "暗号化した鍵": "Encrypted key",
    "初期化ベクトル": "Initialisation vector",
    "暗号文": "Ciphertext",
    "認証タグ": "Authentication tag",
    "中身（クレーム）": "Payload (the claims)",
    "文字）": " characters)",
    "です。": ". ",
    "検証する側も同じ秘密を持ちます。": "Whoever verifies holds the same secret.",
    "署名が無いという指定です。": "This says there is no signature.",
    "公開鍵で検証できます。": "Anyone with the public key can verify it.",
    "RFC 7518 の一覧にない名前です。": "This name is not in the RFC 7518 registry.",
    "この文字列を見て、用途の違うトークンを取り違えないようにします。":
        "Reading this is how a recipient avoids mistaking a token minted for another use.",
    "受け手はこの目印で鍵を選びます。目印であって、鍵そのものではありません。":
        "The recipient picks a key by this label. It is a label, not the key.",
    "受け手がここを取りにいく作りだと、取りにいく先を書いた人が決めることになります。":
        "If the recipient fetches this, whoever wrote the token decides where it goes.",
    "署名に使ったと主張している公開鍵です。主張であって、信頼の根拠にはなりません。":
        "This is a public key claiming to be the signing key. A claim is not a reason to trust it.",
    "受け手がこの項目を理解できないなら、受け取らない決まりです。":
        "The rule is that a recipient which does not understand these entries must not accept the token.",
    "中身がさらに別の形式（入れ子の JWT など）のときに書きます。":
        "This is written when the payload is itself something else, such as a nested JWT.",
    "数値ではないので時刻として読めません。": "This is not a number, so it cannot be read as a time.",
    "。ミリ秒を入れたものと思われます（1000で割ると ":
        ". It looks like milliseconds were used; divided by 1000 it is ",
    "ここまで使えます": "That is when it stops working",
    "ここから使えます": "That is when it starts working",
    "ここで発行されました": "That is when it was issued",
    "（このブラウザの時計で ": " (on this browser clock, ",
    "。": ". ",
    "配列で書かれています。受け手は自分の名前がこの中にあるかを見ます。":
        "Written as an array. The recipient looks for its own name in it.",
    "誰についてのトークンかです。受け手のシステムでの利用者IDが入るのがふつうです。":
        "Who the token is about. Usually the user id in the recipient system.",
    "発行元です。受け手はこれを見て、どの鍵で検証するかを決められます。":
        "Who issued it. The recipient can use this to decide which key to verify with.",
    "1枚ごとの通し番号です。使い回しを弾くのに使えます。":
        "A serial number for this one token. Useful for rejecting replays.",

    # ── 自己検査 ──────────────────────────────────────────────────
    "base64url の復号が atob と一致する": "base64url decoding agrees with atob",
    "、外れた例 ": ", a case that missed: ",
    "復号してから書き戻すと元の文字列に戻る":
        "decoding and re-encoding gives back the original string",
    "UTF-8 の復号が TextDecoder と一致する": "UTF-8 decoding agrees with TextDecoder",
    "JSON の読み取りが JSON.parse と一致する": "JSON reading agrees with JSON.parse",
    "同じ名前が2回あることを拾える（JSON.parse は黙って潰す）":
        "duplicate names are noticed (JSON.parse drops them silently)",
    "拾えた": "noticed",
    "拾えなかった": "not noticed",
    "読み込み後にこのページが出した通信は0件":
        "requests made by this page after loading: none",
    " 件": "",
    "自前の復号と読み取りを、いまこのブラウザのものと突き合わせました: ":
        "The hand-written decoding and reading were just checked against this browser: ",
    " 一致": " agree",
    "。食い違ったところはブラウザのほうが正しいです。":
        ". Where they differ, the browser is right.",

    # ── 例 ────────────────────────────────────────────────────────
    "ふつうのトークン": "an ordinary token",
    "期限が切れている": "expired",
    "exp をミリ秒で入れた": "exp in milliseconds",
    "弱い秘密で署名されている": "signed with a weak secret",
    "alg が none": "alg is none",
    "詰めの = が付いている": "with base64 padding",
    "ヘッダに同じ名前が2回": "a name twice in the header",
    "暗号化されたトークン（JWE）": "an encrypted token (JWE)",
    "上の4つは、いまこの場でブラウザに署名させて作っています（秘密は ":
        "The first four were signed by this browser just now, with the secret ",
    "）。だから期限の表示がいつ見ても意味のある値になりますし、通信していないことの証明も兼ねています。":
        ". That is why the expiry always reads as something meaningful, and it doubles as proof that nothing was fetched. ",
    "署名の欄にこの秘密を入れると、正しいと出るのが確かめられます。":
        "Put that secret in the signature box and you can watch it come back valid.",
}


def core_of(html):
    return html.split("<script>")[1].split("</script>")[0]


# ── HTML の差し替え ────────────────────────────────────────────────────────
JA_DESC = ("JWT（JSON Web Token）を貼ると、3つの部分に分けて1つずつ日本語に読み下し、"
           "有効期限がいつ切れるか・署名が本当に正しいか・危ない書き方をしていないかを"
           "見せる道具です。exp をミリ秒で入れて数万年先になっている、alg が none、"
           "ペイロードにパスワードが入っている、ES256 の署名が DER 形式になっている、"
           "といった「エラーにならないので気づけない」ところを名指しします。"
           "ブラウザ内で完結し、貼ったトークンはどこにも送信されません。")
EN_DESC = ("Paste a JWT and this page splits it into its three parts and reads each one back: "
           "when it expires, whether the signature really checks out, and whether it is written "
           "in a way that will hurt later. exp given in milliseconds so the expiry sits tens of "
           "thousands of years away, alg set to none, a password sitting in the payload, an ES256 "
           "signature left in DER form: the traps that raise no error get named. "
           "It runs entirely in your browser and the token you paste is never uploaded.")

HTML_PARTS = [
 ('<html lang="ja">', '<html lang="en">'),

 ('<title>JWTの読み下し — 中身は暗号化されていない、を目で見る道具</title>',
  '<title>JWT Explainer — see for yourself that the payload is not encrypted</title>'),

 ('<meta name="description" content="' + JA_DESC + '">',
  '<meta name="description" content="' + EN_DESC + '">'),

 ('<link rel="canonical" href="' + SITE + '/jwt/">',
  '<link rel="canonical" href="' + SITE + '/en/jwt.html">'),

 ('<meta property="og:locale" content="ja_JP">',
  '<meta property="og:locale" content="en_US">'),

 ('<meta property="og:site_name" content="クロードの昼ラボ">',
  '<meta property="og:site_name" content="Claude&#39;s Daytime Lab">'),

 ('<meta property="og:title" content="JWTの読み下し — 中身は暗号化されていない、を目で見る道具">',
  '<meta property="og:title" content="JWT Explainer — see for yourself that the payload is not encrypted">'),

 ('<meta property="og:description" content="JWTを貼ると3つの部分に分けて読み下し、期限がいつ切れるか・署名が正しいか・危ない書き方をしていないかを見せます。exp をミリ秒で入れて数万年先、alg が none、ペイロードにパスワード。エラーにならない落とし穴を名指しします。">',
  '<meta property="og:description" content="Paste a JWT and it is split into three parts and read back: when it expires, whether the signature checks out, whether it is written in a way that will hurt. exp in milliseconds, alg none, a password in the payload. The traps that raise no error get named.">'),

 ('<meta property="og:url" content="' + SITE + '/jwt/">',
  '<meta property="og:url" content="' + SITE + '/en/jwt.html">'),

 ('<meta property="og:image" content="' + SITE + '/ogp/ogp-jwt.png">',
  '<meta property="og:image" content="' + SITE + '/ogp/ogp-jwt-en.png">'),

 ('<meta name="twitter:title" content="JWTの読み下し — 中身は暗号化されていない、を目で見る道具">',
  '<meta name="twitter:title" content="JWT Explainer — see for yourself that the payload is not encrypted">'),

 ('<meta name="twitter:description" content="JWTを3つの部分に分けて読み下し、期限・署名・危ない書き方を見せます。エラーにならない落とし穴を名指しします。貼ったトークンはどこにも送信されません。">',
  '<meta name="twitter:description" content="A JWT split into three parts and read back: expiry, signature, and the writing that will hurt later. The traps that raise no error get named. The token you paste is never uploaded.">'),

 ('<meta name="twitter:image" content="' + SITE + '/ogp/ogp-jwt.png">',
  '<meta name="twitter:image" content="' + SITE + '/ogp/ogp-jwt-en.png">'),

 ('  "name": "JWTの読み下し",\n  "url": "' + SITE + '/jwt/",\n  "description": "' + JA_DESC + '",',
  '  "name": "JWT Explainer",\n  "url": "' + SITE + '/en/jwt.html",\n  "description": "' + EN_DESC + '",'),

 ('  "browserRequirements": "JavaScript が有効なモダンブラウザ",',
  '  "browserRequirements": "A modern browser with JavaScript enabled",'),

 ('  "inLanguage": "ja",', '  "inLanguage": "en",'),

 ('"image": "' + SITE + '/ogp/ogp-jwt.png",\n  "author": { "@type": "Organization", "name": "クロードの昼ラボ", "url": "https://note.com/hirulab" },\n  "isPartOf": { "@type": "WebSite", "name": "クロードの昼ラボ — ツール置き場", "url": "' + SITE + '/" }',
  '"image": "' + SITE + '/ogp/ogp-jwt-en.png",\n  "author": { "@type": "Organization", "name": "Claude&#39;s Daytime Lab", "url": "https://note.com/hirulab" },\n  "isPartOf": { "@type": "WebSite", "name": "Claude&#39;s Daytime Lab — Tools", "url": "' + SITE + '/" }'),

 ('  <a class="hl-back" href="../">← クロードの昼ラボ 道具箱</a>\n  <h1>JWTの読み下し</h1>',
  '  <a class="hl-back" href="./">&larr; Claude&#39;s Daytime Lab tools</a>\n  <h1>JWT Explainer</h1>'),

 ('''  <p class="lead">JWT を貼ると、<strong>3つの部分に分けて1つずつ日本語に読み下し、実際に何が起きるか</strong>を見せる道具です。
    JWT でいちばん多い誤解は<strong>「中身は暗号化されている」</strong>で、実際は
    <strong>base64 で書いてあるだけ</strong>です。誰でも読めます。
    <code>exp</code> をミリ秒で入れて期限が数万年先になっていても、エラーは出ません。
    この道具は、そういうところを名指しします。</p>''',
  '''  <p class="lead">Paste a JWT and this page <strong>splits it into its three parts and reads each one back,
    saying what will actually happen</strong>.
    The most common misunderstanding about JWTs is that <strong>the payload is encrypted</strong>. It is not:
    it is <strong>written in base64</strong>, and anyone can read it.
    Put <code>exp</code> in milliseconds so the expiry lands tens of thousands of years from now, and
    nothing raises an error. This page names that kind of thing.</p>'''),

 ('''  <div class="privacy">
    <strong>このページは通信を一切行いません。</strong>
    解析も署名の検証もすべてブラウザの中でやっています。読み込んだあとは機内モードでも動きます。
    <strong>貼り付けたトークンと秘密鍵がどこかに送られることはありません。</strong>
    トークンは資格情報そのものなので、他人のページに貼る前に、
    そのページが通信していないことを開発者ツールの Network で確かめる癖をつけてください。
    このページでも、いま同じことを確かめられます。
  </div>''',
  '''  <div class="privacy">
    <strong>This page makes no network requests at all.</strong>
    The parsing and the signature check both happen inside your browser. Once loaded it works in aeroplane mode.
    <strong>The token and the key you paste are never sent anywhere.</strong>
    A token is a credential, so before pasting one into anybody else&#39;s page, get into the habit of
    opening the Network tab and watching what that page actually does.
    You can do exactly that here, right now.
  </div>'''),

 ('    <label for="src" class="hide">JWT</label>', '    <label for="src" class="hide">JWT</label>'),

 ('''  <div class="panel">
    <h2>署名を確かめる（任意）</h2>
    <label for="key" class="hide">鍵</label>
    <textarea id="key" spellcheck="false" autocapitalize="off" autocomplete="off"
      placeholder="HS256 なら共有の秘密（そのまま文字として読みます）。RS256 / ES256 / PS256 なら公開鍵を JWK の JSON か PEM（-----BEGIN PUBLIC KEY-----）で。"></textarea>
    <div class="siderow">
      <label><input type="checkbox" id="b64key"> 秘密を base64url として読む（HMAC のとき）</label>
      <label><input type="checkbox" id="weak" checked> よく使われる秘密を試す（HMAC のとき）</label>
    </div>
  </div>''',
  '''  <div class="panel">
    <h2>Check the signature (optional)</h2>
    <label for="key" class="hide">Key</label>
    <textarea id="key" spellcheck="false" autocapitalize="off" autocomplete="off"
      placeholder="For HS256, the shared secret, read as literal text. For RS256 / ES256 / PS256, the public key as JWK JSON or PEM (-----BEGIN PUBLIC KEY-----)."></textarea>
    <div class="siderow">
      <label><input type="checkbox" id="b64key"> read the secret as base64url (for HMAC)</label>
      <label><input type="checkbox" id="weak" checked> try commonly used secrets (for HMAC)</label>
    </div>
  </div>'''),

 ('    <h2>3つの部分に分ける</h2>', '    <h2>The three parts</h2>'),
 ('    <h2>ヘッダ（どう署名したか）</h2>', '    <h2>Header (how it was signed)</h2>'),
 ('    <h2>中身（クレーム）</h2>', '    <h2>Payload (the claims)</h2>'),
 ('    <h2>署名</h2>', '    <h2>Signature</h2>'),
 ('    <h2>気をつけるところ</h2>', '    <h2>Things worth knowing</h2>'),
 ('    <p class="none" id="notesNone">いまのところ指摘はありません。</p>',
  '    <p class="none" id="notesNone">Nothing to flag so far.</p>'),
 ('    <h2>自己検査</h2>', '    <h2>Self-check</h2>'),

 ('''  <details>
    <summary>この道具は何を自分で計算しているのか</summary>
    <ul>
      <li><b>base64url の復号は、ブラウザの <code>atob</code> を使わず自分で書いています。</b>
        RFC 4648 の 5 節（url-safe な字表）と RFC 7515 の決まり（詰めの <code>=</code> を書かない）
        をなぞった実装です。<b>余ったビットが0でない</b>ときも見ています。
        そこが0でないと、<b>別の文字列を書いても同じバイト列に戻る</b>ので、
        署名の対象と読んだ中身が食い違う余地が生まれます。</li>
      <li><b>UTF-8 の復号も自分で書いています。</b>
        必要以上に長い書き方（overlong）、サロゲートの符号位置、
        U+10FFFF より上を、それぞれ誤りとして扱います。</li>
      <li><b>JSON の読み取りも自分で書いています。</b>
        <code>JSON.parse</code> は<b>同じ名前が2回出てきたことを教えてくれない</b>（後ろ勝ちで黙って潰す）ためです。
        受け手のライブラリによって前勝ち・後ろ勝ちが割れるので、そこは名指ししたい。</li>
      <li>自前である以上ずれる可能性があります。だから<b>毎回その場でブラウザの
        <code>atob</code>・<code>TextDecoder</code>・<code>JSON.parse</code> と突き合わせ、
        結果を自己検査の欄に出しています</b>。</li>
      <li><b>署名の検証だけはブラウザの <code>crypto.subtle</code> を使います。</b>
        暗号の実装を自前で書くのは、この道具の目的（読み下し）に対して危ないほうに倒れるからです。
        <b>鍵もトークンも外に出ません</b>（<code>crypto.subtle</code> はブラウザの中の計算です）。</li>
      <li><b>できていないところも書いておきます。</b>
        暗号化されたトークン（JWE、5つの部分に分かれるもの）は、
        <b>そうだと言うだけで中身は開きません</b>。鍵が要るうえ、この道具の目的から外れます。
        <code>x5c</code> の証明書の中身も見ていません。</li>
    </ul>
  </details>''',
  '''  <details>
    <summary>What this page works out for itself</summary>
    <ul>
      <li><b>The base64url decoding is hand-written; the browser&#39;s <code>atob</code> is not used.</b>
        It follows section 5 of RFC 4648 (the url-safe alphabet) and the rule in RFC 7515 that the
        <code>=</code> padding is not written. It also watches for <b>leftover bits that are not zero</b>.
        When they are not, <b>a different string decodes to the same bytes</b>, which leaves room for
        what was signed and what was read to drift apart.</li>
      <li><b>The UTF-8 decoding is hand-written too.</b>
        Overlong sequences, surrogate code points and anything above U+10FFFF are each treated as errors.</li>
      <li><b>The JSON reading is hand-written as well.</b>
        <code>JSON.parse</code> <b>will not tell you that a name appeared twice</b>; it keeps the last one
        and drops the rest without a word. Which one wins differs between libraries, so it is worth naming.</li>
      <li>Anything hand-written can be wrong. So <b>every time the page loads it checks itself against the
        browser&#39;s own <code>atob</code>, <code>TextDecoder</code> and <code>JSON.parse</code>,
        and prints the result in the self-check panel</b>.</li>
      <li><b>Only the signature check uses the browser, through <code>crypto.subtle</code>.</b>
        Hand-writing cryptography would fail in the dangerous direction for a page whose job is to explain.
        <b>Neither the key nor the token leaves the page</b>; <code>crypto.subtle</code> is a computation
        inside the browser.</li>
      <li><b>What it does not do, stated plainly.</b>
        An encrypted token (a JWE, the kind with five parts) is <b>named as such and left closed</b>.
        That needs a key, and it is outside what this page is for.
        The contents of an <code>x5c</code> certificate are not examined either.</li>
    </ul>
  </details>'''),

 ('''  <footer>
    作ったのは「クロードの昼ラボ」（AIのClaude）です。使用は無料・登録不要。
    読み方は RFC 7515（JWS）・RFC 7516（JWE）・RFC 7517（JWK）・RFC 7518（アルゴリズム）・
    RFC 7519（JWT）と、RFC 8725（JWT を安全に使うための現在の推奨）に合わせています。
    ライブラリごとに受け付ける範囲が違い、<b>その食い違い自体が事故のもと</b>です。
    指摘欄ではそこも書いています。
  </footer>''',
  '''  <footer>
    Built by Claude&#39;s Daytime Lab (Claude, an AI). Free to use, no sign-up.
    The reading follows RFC 7515 (JWS), RFC 7516 (JWE), RFC 7517 (JWK), RFC 7518 (algorithms) and
    RFC 7519 (JWT), together with RFC 8725, the current advice on using JWTs safely.
    Libraries differ in what they will accept, and <b>that gap is itself a source of accidents</b>.
    The notes say where.
  </footer>'''),
]

EN_NAV = '''  <nav class="hl-nav">
    <h2>Other tools</h2>
    <ul>
      <li><a href="./regex-why.html">Why doesn&#39;t my regex match?</a></li>
      <li><a href="./replace.html">Regex Replacement Preview</a></li>
      <li><a href="./railroad.html">Regex Railroad Diagrams</a></li>
      <li><a href="./regex-tester.html">Regex Tester</a></li>
      <li><a href="./char-counter.html">Character Counter</a></li>
      <li><a href="./palette.html">Color Palette Generator</a></li>
      <li><a href="./timezone.html">Time Zone Converter</a></li>
      <li><a href="./csv.html">CSV Preview &amp; Diagnostics</a></li>
      <li><a href="./url.html">URL Parser &amp; Builder</a></li>
      <li><a href="./headers.html">HTTP Header Explainer</a></li>
      <li><a href="../jwt/">Japanese version</a></li>
      <li><a href="./password.html">Password Generator &amp; Strength Check</a></li>
      <li><a href="./base64.html">Base64 &amp; Data URL Explainer</a></li>
    </ul>
    <p class="hl-links">
      <a href="./">Tools index</a> &middot;
      <a href="https://note.com/hirulab">Experiment log (JP)</a> &middot;
      <a href="https://x.com/hirulab_ai">X</a> &middot;
      <a href="https://github.com/hirulab-dev/hirulab-tools">Source</a>
    </p>
  </nav>'''


def main():
    docs = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    ja_path = docs / "jwt" / "index.html"
    en_path = docs / "en" / "jwt.html"
    ja = ja_path.read_text(encoding="utf-8")

    en = ja
    for a, b in HTML_PARTS:
        if a not in en:
            sys.exit("HTMLの差し替え元が見つかりません:\n" + a[:240])
        en = en.replace(a, b, 1)

    # ナビは日本語版の一覧をまるごと英語版のものに差し替える
    ja_nav = re.search(r'  <nav class="hl-nav">.*?\n  </nav>', en, re.S)
    if not ja_nav:
        sys.exit("ナビが見つかりません")
    en = en[:ja_nav.start()] + EN_NAV + en[ja_nav.end():]

    for a, b in sorted(TR.items(), key=lambda kv: -len(kv[0])):
        en = en.replace('"' + a + '"', '"' + b + '"')

    # 画面に出るところに日本語が残っていないか。
    # 仮名・漢字だけ見ていると約物（、。「」（））が素通りするので、そこも見る。
    body = re.sub(r"/\*.*?\*/", "", en, flags=re.S)
    body = re.sub(r"(?m)(?<!:)//.*$", "", body)
    left = re.findall("[぀-ヿ㐀-鿿、。「」『』（）［］｛｝！？]+", body)
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


if __name__ == "__main__":
    main()
