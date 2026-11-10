"""One-shot capture of the Lockin app's access_token through a temporary HTTPS proxy.

The phone points its Wi-Fi proxy at the hub and trusts a CA generated here. Only connections to
dding.net are decrypted; every other host is tunnelled untouched. The first token the Lockin cloud
accepts is handed to the hub, then the proxy stops listening. Tokens are never logged.
"""
import asyncio
import datetime
import ipaddress
import logging
import os
import re
import socket
import ssl
import tempfile
import time
from urllib.parse import unquote, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .drivers.lockin import LockinAuthError
from .store import DATA_DIR

log = logging.getLogger(__name__)

PORT = 8899
TIMEOUT = 600
DONE_GRACE = 1800
TARGET = "dding.net"
TOKEN_RE = re.compile(rb"access_token=([0-9A-Za-z%:._-]{20,})")
CA_KEY = DATA_DIR / "capture-ca.key"
CA_CERT = DATA_DIR / "capture-ca.crt"
CA_NAME = "mi-local 门锁接入证书"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _constrained(cert: x509.Certificate) -> bool:
    try:
        cert.extensions.get_extension_for_class(x509.NameConstraints)
        return True
    except x509.ExtensionNotFound:
        return False


def _load_ca() -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    if CA_KEY.exists() and CA_CERT.exists():
        cert = x509.load_pem_x509_certificate(CA_CERT.read_bytes())
        if _constrained(cert):
            return serialization.load_pem_private_key(CA_KEY.read_bytes(), None), cert
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_NAME),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "mi-local")])
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now() - datetime.timedelta(days=1))
        .not_valid_after(_now() + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        # The phone trusts this CA, so it must be useless for any site but the lock cloud even if the key leaks.
        .add_extension(x509.NameConstraints(permitted_subtrees=[x509.DNSName(TARGET)], excluded_subtrees=None),
                       critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                     key_encipherment=False, data_encipherment=False, key_agreement=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CA_KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    os.chmod(CA_KEY, 0o600)
    CA_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def _is_target(host: str) -> bool:
    return host == TARGET or host.endswith("." + TARGET)


async def _resolve(host: str, port: int) -> str:
    """Address to dial for a proxied request; the hub's own loopback services stay out of reach."""
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for *_, addr in infos:
        ip = ipaddress.ip_address(addr[0].split("%")[0])
        if ip.is_loopback or ip.is_unspecified or ip.is_link_local:
            raise ValueError(f"refused proxy target {host}")
    return infos[0][4][0]


def ca_pem() -> bytes:
    return _load_ca()[1].public_bytes(serialization.Encoding.PEM)


def _server_context(host: str) -> ssl.SSLContext:
    ca_key, ca_cert = _load_ca()
    key = ec.generate_private_key(ec.SECP256R1())
    # iOS rejects server certificates valid for more than 825 days.
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
        .issuer_name(ca_cert.subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_now() - datetime.timedelta(days=1))
        .not_valid_after(_now() + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=False, crl_sign=False, content_commitment=False,
                                     key_encipherment=False, data_encipherment=False, key_agreement=False,
                                     encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # load_cert_chain only takes paths, so the pair lives on disk for a moment.
    with tempfile.NamedTemporaryFile("wb", suffix=".pem", dir=DATA_DIR, delete=False) as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    try:
        ctx.load_cert_chain(f.name)
    finally:
        os.unlink(f.name)
    return ctx


class LockinCapture:
    def __init__(self, on_token):
        self.on_token = on_token
        self.server: asyncio.AbstractServer | None = None
        self.expires = 0.0
        self.seen_any = False
        self.seen_lockin = False
        self.done = False
        self.error = ""
        self._tried: set[str] = set()
        self._contexts: dict[str, ssl.SSLContext] = {}
        self._timer: asyncio.Task | None = None

    def status(self) -> dict:
        return {
            "active": self.server is not None,
            "port": PORT,
            "remaining": max(0, int(self.expires - time.time())) if self.server else 0,
            "seen_any": self.seen_any,
            "seen_lockin": self.seen_lockin,
            "done": self.done,
            "error": self.error,
        }

    async def start(self) -> None:
        self.seen_any, self.seen_lockin, self.done, self.error = False, False, False, ""
        self._tried.clear()
        if self.server:
            self.expires = time.time() + TIMEOUT
            return
        await asyncio.to_thread(_load_ca)
        self.server = await asyncio.start_server(self._handle, "0.0.0.0", PORT)
        self.expires = time.time() + TIMEOUT
        self._timer = asyncio.create_task(self._expire())
        log.info("lockin capture proxy listening on :%d", PORT)

    async def stop(self) -> None:
        server, self.server = self.server, None
        if self._timer and self._timer is not asyncio.current_task():
            self._timer.cancel()
        if server:
            server.close()
            log.info("lockin capture proxy stopped")

    async def _expire(self) -> None:
        while self.server and time.time() < self.expires:
            await asyncio.sleep(5)
        await self.stop()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream: asyncio.StreamWriter | None = None
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
            self.seen_any = True
            method, target, rest = head.split(b"\r\n", 1)[0].decode("latin-1").split(" ", 2)
            if method.upper() == "CONNECT":
                host, _, port = target.rpartition(":")
                scan = not self.done and _is_target(host)
                if scan:
                    self.seen_lockin = True
                    if host not in self._contexts:
                        self._contexts[host] = await asyncio.to_thread(_server_context, host)
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                if scan:
                    # No awaits between the reply and the upgrade: the ClientHello must reach TLS,
                    # not the plain reader buffer.
                    await writer.start_tls(self._contexts[host])
                else:
                    await writer.drain()
                ip = await _resolve(host, int(port or 443))
                up_reader, upstream = await asyncio.wait_for(asyncio.open_connection(
                    ip, int(port or 443), ssl=ssl.create_default_context() if scan else None,
                    server_hostname=host if scan else None), 15)
            else:
                # Plain HTTP through the proxy: absolute URL in the request line.
                url = urlsplit(target)
                scan = _is_target(url.hostname or "")
                if scan:
                    self._scan(head)
                path = (url.path or "/") + (f"?{url.query}" if url.query else "")
                head = f"{method} {path} {rest}".encode("latin-1") + head.split(b"\r\n", 1)[1]
                ip = await _resolve(url.hostname or "", url.port or 80)
                up_reader, upstream = await asyncio.wait_for(asyncio.open_connection(ip, url.port or 80), 15)
                upstream.write(head)
            pumps = [asyncio.create_task(self._pump(reader, upstream, scan)),
                     asyncio.create_task(self._pump(up_reader, writer, False))]
            await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
            for p in pumps:
                p.cancel()
        except (OSError, ValueError, ssl.SSLError, asyncio.TimeoutError, asyncio.IncompleteReadError,
                asyncio.LimitOverrunError):
            pass
        finally:
            for w in (writer, upstream):
                if w:
                    w.close()

    async def _pump(self, src: asyncio.StreamReader, dst: asyncio.StreamWriter, scan: bool) -> None:
        tail = b""
        try:
            while data := await src.read(65536):
                if scan:
                    self._scan(tail + data)
                    tail = data[-300:]
                dst.write(data)
                await dst.drain()
        except (OSError, ssl.SSLError):
            pass

    def _scan(self, data: bytes) -> None:
        for match in TOKEN_RE.finditer(data):
            token = unquote(match.group(1).decode())
            if self.done or token in self._tried:
                continue
            self._tried.add(token)
            asyncio.create_task(self._try(token))

    async def _try(self, token: str) -> None:
        try:
            await self.on_token(token)
        except LockinAuthError:
            log.info("lockin capture: token rejected")
            return
        except RuntimeError as e:
            self.error = str(e)
            return
        except Exception as e:
            log.info("lockin capture: token rejected (%s)", type(e).__name__)
            return
        # The phone still points its proxy here, so keep passing traffic until it is switched back.
        self.done, self.error = True, ""
        self.expires = time.time() + DONE_GRACE
