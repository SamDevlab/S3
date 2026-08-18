from __future__ import annotations

import ssl

from bootstrap.s3.tls_client import (
    TlsClient,
    TlsClientConfig,
    TlsErrorCode,
)


class _FakeRaw:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeTls:
    def __init__(self) -> None:
        self.closed = False
        self.received = b"reply"

    def recv(self, amount: int) -> bytes:
        return self.received[:amount]

    def send(self, data: bytes) -> int:
        return len(data)

    def close(self) -> None:
        self.closed = True


class _FakeContext:
    def __init__(self, wrapped: _FakeTls) -> None:
        self.wrapped = wrapped
        self.minimum_version = None
        self.maximum_version = None
        self.verify_mode = None
        self.check_hostname = None
        self.server_hostname = None

    def wrap_socket(self, raw, *, server_hostname: str) -> _FakeTls:
        del raw
        self.server_hostname = server_hostname
        return self.wrapped


def test_tls_context_requires_certificate_and_hostname_validation(monkeypatch) -> None:
    raw = _FakeRaw()
    tls = _FakeTls()
    context = _FakeContext(tls)
    monkeypatch.setattr("bootstrap.s3.tls_client.socket.create_connection", lambda *args, **kwargs: raw)
    monkeypatch.setattr("bootstrap.s3.tls_client.ssl.create_default_context", lambda **kwargs: context)

    result = TlsClient.connect("example.test", 443)
    assert result.is_ok
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version is ssl.TLSVersion.TLSv1_2
    assert context.maximum_version is ssl.TLSVersion.TLSv1_3
    assert context.server_hostname == "example.test"


def test_tls_bounded_io_and_clean_close() -> None:
    client = TlsClient(_FakeTls(), config=TlsClientConfig(max_read_write=4))
    assert client.read(4).value_or(b"") == b"repl"
    assert client.write(b"data").value_or(-1) == 4
    assert client.write(b"toolong").error_or(None).code is TlsErrorCode.INVALID_DATA
    client.close()
    client.close()
    assert client.closed
    assert client.read(1).error_or(None).code is TlsErrorCode.CLOSED


def test_wrong_hostname_is_explicit_and_provider_is_vetted(monkeypatch) -> None:
    raw = _FakeRaw()

    class WrongHostContext(_FakeContext):
        def wrap_socket(self, raw, *, server_hostname: str):
            del raw, server_hostname
            raise ssl.CertificateError("hostname mismatch")

    context = WrongHostContext(_FakeTls())
    monkeypatch.setattr("bootstrap.s3.tls_client.socket.create_connection", lambda *args, **kwargs: raw)
    monkeypatch.setattr("bootstrap.s3.tls_client.ssl.create_default_context", lambda **kwargs: context)
    result = TlsClient.connect("wrong.example", 443)
    assert result.is_err
    assert result.error_or(None).code is TlsErrorCode.HOSTNAME
    assert raw.closed
    assert TlsClient.provider_available()


def test_connection_failure_is_mapped_without_secret_logging(monkeypatch) -> None:
    def fail(*args, **kwargs):
        del args, kwargs
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr("bootstrap.s3.tls_client.socket.create_connection", fail)
    result = TlsClient.connect("127.0.0.1", 443)
    assert result.is_err
    assert result.error_or(None).code is TlsErrorCode.CONNECTION
    assert "private" not in result.error_or(None).detail.lower()
