"""Bounded blocking UDP and DNS contracts for M1.67."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import socket

from .network import NetworkAddress, NetworkError, NetworkFamily
from .results import Result


class UdpErrorCode(Enum):
    INVALID_ADDRESS = "invalid_address"
    INVALID_DATA = "invalid_data"
    TIMEOUT = "timeout"
    CLOSED = "closed"
    RESOURCE_LIMIT = "resource_limit"
    HOST_FAILURE = "host_failure"
    DNS_FAILURE = "dns_failure"


@dataclass(frozen=True, slots=True)
class UdpError:
    code: UdpErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class UdpDatagram:
    data: bytes
    address: NetworkAddress


def _socket_address(address: NetworkAddress) -> tuple[str, int]:
    if not isinstance(address, NetworkAddress):
        raise TypeError("UDP address must be NetworkAddress")
    return address.host, address.port


def _network_address(host: str, port: int) -> NetworkAddress:
    return NetworkAddress.numeric(host, port)


class UdpSocket:
    """An owned blocking UDP socket with bounded datagrams and idempotent close."""

    def __init__(self, sock: socket.socket, *, max_datagram: int) -> None:
        self._socket = sock
        self._max_datagram = max_datagram
        self._closed = False

    @classmethod
    def bind(
        cls,
        address: NetworkAddress,
        *,
        max_datagram: int = 65507,
    ) -> Result[UdpSocket, UdpError]:
        if isinstance(max_datagram, bool) or not isinstance(max_datagram, int) or not 1 <= max_datagram <= 65507:
            return Result.err(UdpError(UdpErrorCode.RESOURCE_LIMIT, "bind", "max_datagram is outside [1, 65507]"))
        if not isinstance(address, NetworkAddress):
            return Result.err(UdpError(UdpErrorCode.INVALID_ADDRESS, "bind", "address must be NetworkAddress"))
        family = socket.AF_INET if address.family is NetworkFamily.IPV4 else socket.AF_INET6
        sock = socket.socket(family, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(_socket_address(address))
            return Result.ok(cls(sock, max_datagram=max_datagram))
        except OSError as error:
            sock.close()
            return Result.err(UdpError(UdpErrorCode.HOST_FAILURE, "bind", str(error)))

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def max_datagram(self) -> int:
        return self._max_datagram

    def bound_address(self) -> Result[NetworkAddress, UdpError]:
        if self._closed:
            return Result.err(UdpError(UdpErrorCode.CLOSED, "bound_address", "socket is closed"))
        try:
            return Result.ok(_network_address(*self._socket.getsockname()[:2]))
        except (OSError, ValueError) as error:
            return Result.err(UdpError(UdpErrorCode.HOST_FAILURE, "bound_address", str(error)))

    def send_to(
        self,
        data: bytes,
        address: NetworkAddress,
        timeout_ms: int,
    ) -> Result[int, UdpError]:
        if self._closed:
            return Result.err(UdpError(UdpErrorCode.CLOSED, "send_to", "socket is closed"))
        if not isinstance(data, bytes) or len(data) > self._max_datagram:
            return Result.err(UdpError(UdpErrorCode.RESOURCE_LIMIT, "send_to", "datagram exceeds configured limit"))
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0:
            return Result.err(UdpError(UdpErrorCode.TIMEOUT, "send_to", "timeout must be non-negative"))
        try:
            self._socket.settimeout(timeout_ms / 1000)
            return Result.ok(self._socket.sendto(data, _socket_address(address)))
        except (TimeoutError, BlockingIOError) as error:
            return Result.err(UdpError(UdpErrorCode.TIMEOUT, "send_to", str(error)))
        except (OSError, TypeError, ValueError) as error:
            return Result.err(UdpError(UdpErrorCode.HOST_FAILURE, "send_to", str(error)))

    def receive(self, timeout_ms: int) -> Result[UdpDatagram, UdpError]:
        if self._closed:
            return Result.err(UdpError(UdpErrorCode.CLOSED, "receive", "socket is closed"))
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0:
            return Result.err(UdpError(UdpErrorCode.TIMEOUT, "receive", "timeout must be non-negative"))
        try:
            self._socket.settimeout(timeout_ms / 1000)
            data, raw_address = self._socket.recvfrom(self._max_datagram)
            return Result.ok(UdpDatagram(data, _network_address(raw_address[0], raw_address[1])))
        except (TimeoutError, BlockingIOError) as error:
            return Result.err(UdpError(UdpErrorCode.TIMEOUT, "receive", str(error)))
        except (OSError, ValueError) as error:
            return Result.err(UdpError(UdpErrorCode.HOST_FAILURE, "receive", str(error)))

    def close(self) -> None:
        if not self._closed:
            self._socket.close()
            self._closed = True

    def __enter__(self) -> UdpSocket:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False


class DnsResolver:
    """Blocking resolver with stable, sorted, duplicate-free results."""

    def resolve(self, host: str, port: int) -> Result[tuple[NetworkAddress, ...], UdpError]:
        if not isinstance(host, str) or not host or "\x00" in host:
            return Result.err(UdpError(UdpErrorCode.DNS_FAILURE, "resolve", "host is invalid"))
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            return Result.err(UdpError(UdpErrorCode.INVALID_ADDRESS, "resolve", "port is outside [0, 65535]"))
        try:
            records = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_DGRAM)
        except socket.gaierror as error:
            return Result.err(UdpError(UdpErrorCode.DNS_FAILURE, "resolve", str(error)))
        addresses: dict[bytes, NetworkAddress] = {}
        for family, _kind, _protocol, _canonname, raw_address in records:
            try:
                address = _network_address(raw_address[0], raw_address[1])
            except (NetworkError, ValueError, IndexError):
                continue
            addresses[address.to_bytes()] = address
        ordered = tuple(sorted(addresses.values(), key=lambda item: (item.family.tag, item.host, item.port)))
        if not ordered:
            return Result.err(UdpError(UdpErrorCode.DNS_FAILURE, "resolve", "resolver returned no numeric address"))
        return Result.ok(ordered)
