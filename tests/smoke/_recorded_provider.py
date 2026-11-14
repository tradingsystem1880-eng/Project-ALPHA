"""Test-only TLS proxy serving synthetic bytes made in the test.

No real Binance bytes are recorded: Binance's terms forbid redistribution and this
repository is public. The proxy never opens an outbound connection.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import io
import json
import socket
import socketserver
import ssl
import sys
import threading
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from types import TracebackType

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from alpha_data.crypto.providers.binance import archive_url, binance_public_api_url

_HOSTS = ("data.binance.vision", "api.binance.com")
_DAY_MS = 86_400_000


def _certificates(directory: Path) -> ssl.SSLContext:
    directory.mkdir(parents=True)
    (directory / "empty-roots").mkdir()
    ca_key = ec.generate_private_key(ec.SECP256R1())
    server_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ALPHA smoke test CA")])
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2036, 1, 1, tzinfo=UTC)
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(end)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    server = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, _HOSTS[0])]))
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(end)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(host) for host in _HOSTS]), critical=False
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    (directory / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory / "server.pem").write_bytes(server.public_bytes(serialization.Encoding.PEM))
    (directory / "server.key").write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(directory / "server.pem", directory / "server.key")
    return context


class _ProxyServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True

    def __init__(self, provider: RecordedProvider) -> None:
        self.provider = provider
        self.workers: list[threading.Thread] = []
        self.errors: list[BaseException] = []
        super().__init__(("127.0.0.1", 0), _ConnectHandler)

    def process_request(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: tuple[str, int]
    ) -> None:
        worker = threading.Thread(
            target=self.process_request_thread, args=(request, client_address), daemon=True
        )
        self.workers.append(worker)
        worker.start()

    def handle_error(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: tuple[str, int]
    ) -> None:
        error = sys.exception()
        assert error is not None
        with self.provider._lock:
            self.errors.append(error)


class _ConnectHandler(BaseHTTPRequestHandler):
    server: _ProxyServer
    protocol_version = "HTTP/1.1"
    timeout = 10

    def log_message(self, format: str, *args: object) -> None:
        """Keep HTTP access logs out of test output; requests are recorded explicitly."""

    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        if self.command != "CONNECT" or self.path not in {f"{host}:443" for host in _HOSTS}:
            with self.server.provider._lock:
                self.server.provider._refused.append(self.requestline)
            self.send_error(403, "Only recorded provider CONNECT tunnels are allowed")
            return False
        return True

    def do_CONNECT(self) -> None:
        self.send_response(200, "Connection established")
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        host = self.path.removesuffix(":443")
        provider = self.server.provider

        class RecordedHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:
                """The provider keeps its own ordered request log."""

            def parse_request(self) -> bool:
                if not super().parse_request():
                    return False
                if (
                    self.command != "GET"
                    or not self.path.startswith("/")
                    or self.path.startswith("//")
                ):
                    with provider._lock:
                        provider._refused.append(self.requestline)
                    self.send_error(403, "Only recorded provider GET requests are allowed")
                    return False
                return True

            def do_GET(self) -> None:
                url = f"https://{host}{self.path}"
                with provider._lock:
                    provider._requests.append(url)
                    recorded = provider._responses.get(url)
                status, body, content_type = (
                    (200, *recorded)
                    if recorded is not None
                    else (404, b"No synthetic recording for this URL\n", "text/plain")
                )
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

        with provider._tls.wrap_socket(self.connection, server_side=True) as tunnel:
            RecordedHandler(tunnel, self.client_address, self.server)


class RecordedProvider:
    """Serve exact recorded URLs over trusted test TLS without any internet forwarding."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = threading.Lock()
        self._responses: dict[str, tuple[bytes, str]] = {}
        self._requests: list[str] = []
        self._refused: list[str] = []

    @property
    def requests(self) -> list[str]:
        with self._lock:
            return self._requests.copy()

    @property
    def refused(self) -> list[str]:
        with self._lock:
            return self._refused.copy()

    def record(self, url: str, body: bytes, content_type: str) -> None:
        with self._lock:
            self._responses[url] = (body, content_type)

    def __enter__(self) -> RecordedProvider:
        self._tls = _certificates(self.directory)
        self._server = _ProxyServer(self)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._server.shutdown()
        self._server.server_close()
        for thread in [self._thread, *self._server.workers]:
            thread.join(timeout=15)
            if thread.is_alive():
                raise RuntimeError("recorded provider thread did not stop")
        if self._server.errors:
            raise BaseExceptionGroup("recorded provider failed", self._server.errors)

    def env(self) -> dict[str, str]:
        proxy = f"http://127.0.0.1:{self._server.server_address[1]}"
        return {
            "HTTPS_PROXY": proxy,
            "https_proxy": proxy,
            "HTTP_PROXY": proxy,
            "http_proxy": proxy,
            "NO_PROXY": "",
            "no_proxy": "",
            "SSL_CERT_FILE": str(self.directory / "ca.pem"),
            "SSL_CERT_DIR": str(self.directory / "empty-roots"),
        }


def _kline_row(open_ms: int) -> list[str | int]:
    day = datetime.fromtimestamp(open_ms / 1000, UTC).day
    price = 42000 + day
    return [
        open_ms,
        str(price),
        str(price + 100),
        str(price - 100),
        str(price + 50),
        "10",
        open_ms + _DAY_MS - 1,
        str(10 * (price + 50)),
        42,
        "5",
        str(5 * (price + 50)),
        "0",
    ]


def binance_monthly_klines(symbol: str, year: int, month: int) -> tuple[str, bytes, str, bytes]:
    """Build a deterministic synthetic daily CSV archive and its exact SHA-256 sidecar."""
    period = f"{year:04d}-{month:02d}"
    url = archive_url("spot", "klines", symbol, "1d", period)
    start_ms = int(datetime(year, month, 1, tzinfo=UTC).timestamp() * 1000)
    csv_output = io.StringIO(newline="")
    writer = csv.writer(csv_output, lineterminator="\n")
    for day in range(calendar.monthrange(year, month)[1]):
        writer.writerow(_kline_row(start_ms + day * _DAY_MS))
    output = io.BytesIO()
    member = zipfile.ZipInfo(f"{symbol}-1d-{period}.csv", date_time=(2024, 1, 1, 0, 0, 0))
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(member, csv_output.getvalue().encode())
    payload = output.getvalue()
    checksum = f"{hashlib.sha256(payload).hexdigest()}  {url.rsplit('/', 1)[1]}\n".encode()
    return url, payload, f"{url}.CHECKSUM", checksum


def binance_spot_exchange_info(symbols: Sequence[str]) -> bytes:
    """Build the active spot membership fields needed by the Binance parser."""
    rows = []
    for symbol in symbols:
        if not symbol.endswith("USDT") or len(symbol) <= 4:
            raise ValueError("synthetic spot membership requires a USDT pair")
        rows.append(
            {
                "symbol": symbol,
                "status": "TRADING",
                "baseAsset": symbol[:-4],
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
            }
        )
    return json.dumps({"symbols": rows}, sort_keys=True, separators=(",", ":")).encode()


def binance_rest_klines(symbol: str, start_ms: int, end_ms: int) -> tuple[str, bytes]:
    """Build the exact first daily REST page requested by the acquisition command."""
    url = binance_public_api_url(
        "spot",
        "klines",
        {
            "symbol": symbol,
            "interval": "1d",
            "limit": 1000,
            "startTime": start_ms,
            "endTime": end_ms,
        },
    )
    rows = [_kline_row(open_ms) for open_ms in range(start_ms, end_ms + 1, _DAY_MS)]
    return url, json.dumps(rows, separators=(",", ":")).encode()
