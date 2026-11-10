import asyncio
import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from homehub import lockin_capture


@pytest.fixture
def ca_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(lockin_capture, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lockin_capture, "CA_KEY", tmp_path / "capture-ca.key")
    monkeypatch.setattr(lockin_capture, "CA_CERT", tmp_path / "capture-ca.crt")
    return tmp_path


def test_ca_only_vouches_for_the_lock_cloud(ca_dir):
    cert = x509.load_pem_x509_certificate(lockin_capture.ca_pem())
    ext = cert.extensions.get_extension_for_class(x509.NameConstraints)
    assert ext.critical
    assert ext.value.permitted_subtrees == [x509.DNSName("dding.net")]
    assert lockin_capture.ca_pem() == lockin_capture.ca_pem()


def test_unconstrained_ca_is_replaced(ca_dir):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "old")])
    now = datetime.datetime.now(datetime.timezone.utc)
    old = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
           .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
           .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
           .sign(key, hashes.SHA256()))
    lockin_capture.CA_KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                        serialization.NoEncryption()))
    lockin_capture.CA_CERT.write_bytes(old.public_bytes(serialization.Encoding.PEM))
    cert = x509.load_pem_x509_certificate(lockin_capture.ca_pem())
    assert cert.subject != name
    cert.extensions.get_extension_for_class(x509.NameConstraints)


def test_target_match():
    assert lockin_capture._is_target("dding.net")
    assert lockin_capture._is_target("api.dding.net")
    assert not lockin_capture._is_target("evildding.net")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "0.0.0.0"])
def test_proxy_refuses_loopback(host):
    with pytest.raises(ValueError):
        asyncio.run(lockin_capture._resolve(host, 5037))


def test_proxy_allows_lan_address():
    assert asyncio.run(lockin_capture._resolve("192.168.1.120", 80)) == "192.168.1.120"
