"""TLS 憑證管理 API 測試（G07）。憑證即時生成，寫入路徑重導 tmp（教訓 61）。"""

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from httpx import AsyncClient


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _gen_cert(cn="workflow.local", days_valid=365, not_before_offset_days=0):
    """生成自簽 cert + key（PEM bytes）。days_valid<0 可造已過期憑證。"""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=not_before_offset_days + 1))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem.decode(), key_pem.decode()


@pytest.fixture(autouse=True)
def _redirect_cert_dir(tmp_path, monkeypatch):
    """把 TLS_CERT_DIR 重導到 tmp，避免測試碰真實 /certs。"""
    import app.core.tls_cert as tls_mod

    monkeypatch.setattr(tls_mod, "CERT_DIR", tmp_path / "certs")


@pytest.mark.asyncio
async def test_upload_valid_cert(client: AsyncClient, admin_token: str):
    cert, key = _gen_cert(cn="myorg.example.com")
    resp = await client.post(
        "/api/v1/system-settings/tls-cert",
        json={"cert": cert, "key": key},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["subject_cn"] == "myorg.example.com"
    assert body["is_self_signed"] is True
    assert body["is_expired"] is False
    # 私鑰不應出現在回應
    assert "key" not in body


@pytest.mark.asyncio
async def test_get_cert_after_upload(client: AsyncClient, admin_token: str):
    cert, key = _gen_cert(cn="getme.example.com")
    await client.post(
        "/api/v1/system-settings/tls-cert",
        json={"cert": cert, "key": key},
        headers=_auth(admin_token),
    )
    resp = await client.get("/api/v1/system-settings/tls-cert", headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["subject_cn"] == "getme.example.com"


@pytest.mark.asyncio
async def test_get_cert_when_none(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/system-settings/tls-cert", headers=_auth(admin_token))
    assert resp.status_code == 200
    assert resp.json()["configured"] is False


@pytest.mark.asyncio
async def test_upload_mismatched_key(client: AsyncClient, admin_token: str):
    cert, _ = _gen_cert(cn="a.example.com")
    _, other_key = _gen_cert(cn="b.example.com")  # 不同 key
    resp = await client.post(
        "/api/v1/system-settings/tls-cert",
        json={"cert": cert, "key": other_key},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400
    assert "不相符" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_expired_cert(client: AsyncClient, admin_token: str):
    cert, key = _gen_cert(cn="old.example.com", days_valid=-1, not_before_offset_days=10)
    resp = await client.post(
        "/api/v1/system-settings/tls-cert",
        json={"cert": cert, "key": key},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400
    assert "過期" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_garbage_pem(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/system-settings/tls-cert",
        json={"cert": "not a cert", "key": "not a key"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_requires_admin(client: AsyncClient, member_token: str):
    cert, key = _gen_cert()
    resp = await client.post(
        "/api/v1/system-settings/tls-cert",
        json={"cert": cert, "key": key},
        headers=_auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_cert_requires_admin(client: AsyncClient, member_token: str):
    resp = await client.get("/api/v1/system-settings/tls-cert", headers=_auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_key_file_written_with_strict_perms(client: AsyncClient, admin_token: str, tmp_path):
    import stat

    import app.core.tls_cert as tls_mod

    cert, key = _gen_cert()
    await client.post(
        "/api/v1/system-settings/tls-cert",
        json={"cert": cert, "key": key},
        headers=_auth(admin_token),
    )
    key_path = tls_mod.CERT_DIR / "key.pem"
    assert key_path.exists()
    # 私鑰權限應為 0600（僅擁有者讀寫）
    mode = stat.S_IMODE(key_path.stat().st_mode)
    assert mode == 0o600
