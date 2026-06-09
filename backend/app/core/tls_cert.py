"""TLS 憑證管理：驗證上傳的 cert/key 並原子寫入共用 certs 目錄。

供前端設定頁熱更換 nginx 憑證使用。寫入後由 reloader sidecar 觸發 nginx reload。
不自製密碼學——全用 cryptography 套件（與 crypto.py 同套件，已是相依）。
"""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

# 憑證寫入目錄（prod 設 /certs，與 nginx 的 certs volume 共用）；測試重導 tmp。
CERT_DIR = Path(os.environ.get("TLS_CERT_DIR", "/certs"))
CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"


class CertValidationError(ValueError):
    """憑證或私鑰驗證失敗。"""


def _load_cert(cert_pem: bytes) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(cert_pem)
    except Exception as exc:
        raise CertValidationError("憑證格式錯誤，請提供有效的 PEM 憑證") from exc


def _load_key(key_pem: bytes):
    try:
        return serialization.load_pem_private_key(key_pem, password=None)
    except Exception as exc:
        raise CertValidationError("私鑰格式錯誤，請提供有效的 PEM 私鑰（且未加密）") from exc


def _key_matches_cert(cert: x509.Certificate, private_key) -> bool:
    """確認私鑰與憑證公鑰相符：用私鑰簽一段、用憑證公鑰驗。"""
    cert_pub = cert.public_key()
    priv_pub = private_key.public_key()
    # 公鑰序列化比對（最直接、涵蓋 RSA/EC）
    pub_bytes = cert_pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    priv_pub_bytes = priv_pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return pub_bytes == priv_pub_bytes


def cert_metadata(cert: x509.Certificate) -> dict:
    """擷取憑證資訊（不含私鑰）。"""

    def _cn(name: x509.Name) -> str:
        try:
            attrs = name.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            return attrs[0].value if attrs else ""
        except Exception:
            return ""

    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    subject_cn = _cn(cert.subject)
    issuer_cn = _cn(cert.issuer)
    return {
        "subject_cn": subject_cn,
        "issuer_cn": issuer_cn,
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "is_self_signed": subject_cn == issuer_cn and cert.subject == cert.issuer,
        "is_expired": datetime.now(UTC) > not_after,
    }


def validate_cert_and_key(cert_pem: bytes, key_pem: bytes) -> dict:
    """驗證 cert/key 並回傳憑證 metadata；不通過則 raise CertValidationError。"""
    cert = _load_cert(cert_pem)
    key = _load_key(key_pem)
    if not _key_matches_cert(cert, key):
        raise CertValidationError("私鑰與憑證不相符")
    meta = cert_metadata(cert)
    if meta["is_expired"]:
        raise CertValidationError("憑證已過期")
    return meta


def write_cert(cert_pem: bytes, key_pem: bytes) -> dict:
    """驗證後原子寫入 cert.pem/key.pem（固定檔名，防路徑遍歷），key 權限 0600。

    回傳憑證 metadata。寫入觸發 reloader sidecar 熱重載 nginx。
    """
    meta = validate_cert_and_key(cert_pem, key_pem)
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(CERT_DIR / CERT_FILE, cert_pem, 0o644)
    _atomic_write(CERT_DIR / KEY_FILE, key_pem, 0o600)
    return meta


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    """同目錄暫存檔 + os.replace 原子取代，避免 nginx 讀到半寫入的檔。"""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".pem")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def current_cert_metadata() -> dict | None:
    """讀取目前已部署的憑證資訊；無憑證回 None。"""
    cert_path = CERT_DIR / CERT_FILE
    if not cert_path.exists():
        return None
    try:
        return cert_metadata(_load_cert(cert_path.read_bytes()))
    except Exception:
        return None
