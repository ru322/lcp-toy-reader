#!/usr/bin/env python3
"""Readium LCP（basic プロファイル）の最小リーダー

    python3 reader.py licensed.epub <passphrase> [decrypted.epub]

license.lcpl を検証してコンテンツ鍵を取り出し、暗号化されたリソースを復号して
DRM なしの EPUB として書き出す。
"""
import base64
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import datetime, timezone
from urllib.parse import unquote

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BASIC_PROFILE = "http://readium.org/lcp/basic-profile"
AES256_CBC = "http://www.w3.org/2001/04/xmlenc#aes256-cbc"
NS = {
    "enc": "http://www.w3.org/2001/04/xmlenc#",
    "comp": "http://www.idpf.org/2016/encryption#compression",
}


class LcpError(Exception):
    pass

def b64(s: str) -> bytes:
    return base64.b64decode(s)


def aes_cbc_decrypt(key: bytes, data: bytes) -> bytes:
    iv, body = data[:16], data[16:]
    d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plain = d.update(body) + d.finalize()
    return plain[: -plain[-1]]


def verify_signature(lic: dict) -> x509.Certificate:
    sig = lic["signature"]
    body = {k: v for k, v in lic.items() if k != "signature"}
    # Go 側（sign/canon.go）と同じ正規化: キーをソート、空白なし、非ASCIIはそのまま
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    cert = x509.load_der_x509_certificate(b64(sig["certificate"]))
    try:
        cert.public_key().verify(
            b64(sig["value"]), canon.encode(), padding.PKCS1v15(), hashes.SHA256()
        )
    except InvalidSignature:
        raise LcpError("署名が一致しません（ライセンスが改ざんされています）")
    # 本来はここで証明書が EDRLab のルート CA で署名されているかも確認する
    return cert


def unlock(lic: dict, passphrase: str) -> tuple[bytes, bytes]:
    enc = lic["encryption"]
    if enc["profile"] != BASIC_PROFILE:
        # production プロファイルはユーザー鍵の作り方が非公開
        raise LcpError(f"未対応のプロファイル: {enc['profile']}")

    # basic プロファイル: ユーザー鍵 = SHA-256(パスフレーズ)
    user_key = hashlib.sha256(passphrase.encode()).digest()

    # key_check = ユーザー鍵でライセンスIDを暗号化したもの
    check = aes_cbc_decrypt(user_key, b64(enc["user_key"]["key_check"]))
    if check != lic["id"].encode():
        raise LcpError(f"パスフレーズが違います（ヒント: {enc['user_key']['text_hint']}）")

    content_key = aes_cbc_decrypt(user_key, b64(enc["content_key"]["encrypted_value"]))
    return user_key, content_key


def check_rights(lic: dict) -> None:
    end = lic.get("rights", {}).get("end")
    if end and datetime.now(timezone.utc) > datetime.fromisoformat(end.replace("Z", "+00:00")):
        raise LcpError(f"利用期限切れです（{end}）")


def decrypt_resources(z: zipfile.ZipFile, content_key: bytes) -> dict[str, bytes]:
    root = ET.fromstring(z.read("META-INF/encryption.xml"))
    out = {}
    for data in root.findall("enc:EncryptedData", NS):
        if data.find("enc:EncryptionMethod", NS).get("Algorithm") != AES256_CBC:
            continue  # フォント難読化など LCP 以外の暗号化
        path = unquote(data.find("enc:CipherData/enc:CipherReference", NS).get("URI"))
        plain = aes_cbc_decrypt(content_key, z.read(path))

        comp = data.find(".//comp:Compression", NS)
        if comp is not None and comp.get("Method") == "8":
            plain = zlib.decompress(plain, -15)  # zlib ヘッダなしの raw deflate
        out[path] = plain
    return out


def write_plain_epub(src: zipfile.ZipFile, decrypted: dict[str, bytes], dst_path: str) -> None:
    with zipfile.ZipFile(dst_path, "w") as dst:
        dst.writestr("mimetype", src.read("mimetype"), compress_type=zipfile.ZIP_STORED)
        for info in src.infolist():
            name = info.filename
            if name in ("mimetype", "META-INF/encryption.xml", "META-INF/license.lcpl"):
                continue
            data = decrypted.get(name, src.read(name))
            dst.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    epub_path, passphrase = sys.argv[1], sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else "decrypted.epub"

    z = zipfile.ZipFile(epub_path)
    lic = json.loads(z.read("META-INF/license.lcpl"))

    try:
        cert = verify_signature(lic)
        print(f"[1] 署名OK      : {cert.subject.rfc4514_string()}")

        check_rights(lic)
        user_key, content_key = unlock(lic, passphrase)
        print(f"[2] 鍵の取り出しOK: content_key = {content_key.hex()[:16]}...")

        for field in lic["user"].get("encrypted", []):
            value = aes_cbc_decrypt(user_key, b64(lic["user"][field])).decode()
            print(f"    user.{field} = {value}")

        decrypted = decrypt_resources(z, content_key)
        print(f"[3] 復号OK      : {len(decrypted)} リソース")
    except LcpError as e:
        sys.exit(f"NG: {e}")

    write_plain_epub(z, decrypted, out_path)
    print(f"    -> {out_path}")


if __name__ == "__main__":
    main()