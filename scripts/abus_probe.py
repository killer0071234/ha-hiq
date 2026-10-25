#!/usr/bin/env python3
"""A-bus probe for HIQ / Cybro controllers (hardware spike, Phase 0).

Talks to controllers directly over UDP (A-bus), without the scgi server.
Standard library only, Python 3.11+. Stop the scgi server / add-on first,
at least for "listen" (it needs UDP 8442).

Protocol ported from the Cybro Edge Toolkit scgi_server (with permission).
See tasks/standalone-plan.md, section 4.

Examples:
  abus_probe.py ping --nad 10000              # S1: find the controller by broadcast
  abus_probe.py scan                          # S2: who answers a PING to NAD 0?
  abus_probe.py scan --ip 192.168.1.50        # S2: same, unicast
  abus_probe.py listen --seconds 600          # S3: unsolicited frames on :8442
  abus_probe.py listen --seconds 600 --ack-push   # S7: same, ACK push messages
  abus_probe.py info --nad 10000 --save-alc . # S1/S4/S6: status, head, ALC
  abus_probe.py read --nad 10000 --user       # read all user variables
  abus_probe.py read --nad 10000 lc00_qx00 th00_temperature
  abus_probe.py maxframe --nad 10000          # S6: largest accepted frame

Add "--capture frames.jsonl" to any command to log every raw frame (hex).
Add "--password N" if the controller has an A-bus password.

"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import itertools
import json
import re
import socket
import struct
import subprocess
import sys
import time
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SOURCE_NAD = 1010
ABUS_PORT = 8442
MAX_FRAME_BYTES = 1000

# transport frame
SIGNATURE = 0x55AA
HEADER = struct.Struct("<2H2L")
CRC_TABLE = (
    0x049D, 0x0C07, 0x1591, 0x1ACF, 0x1D4B, 0x202D, 0x2507, 0x2B4B,
    0x34A5, 0x38C5, 0x3D3F, 0x4445, 0x4D0F, 0x538F, 0x5FB3, 0x6BBF,
)  # fmt: skip

# command frame
CMD_PING = 0x10
CMD_READ_STATUS = 0x11
CMD_READ_CODE = 0x21
CMD_WRITE_DATA = 0x32
CMD_READ_RANDOM = 0x33
REQ = 0
ACK = 1
DIRECTIONS = (
    "REQ", "ACK", "INTERNAL", "BAD_CMD", "BAD_PARA", "NOT_READY", "NO_PROG",
    "NO_KERN", "NO_SIGN", "NO_AUTH", "FORCED", "BAD_FLASH", "DENIED",
)  # fmt: skip
TYPE_BROADCAST = 0x64
PUSH_ACK_ADDRESS = 0x0417

# controller memory
SEGMENT_SIZE = 0x100
HEAD_ADDR = 0x20000
HEAD_SIZE = 0x46
FILE_INFO_ADDR = 0x20040
FILE_DESCRIPTOR = struct.Struct("<32sH3L")
MAGICS = {31415: "Cybro-2", 31416: "Cybro-3"}
SYSTEM_STATUS = ("loader active", "kernel active")
PLC_STATUS = ("stop", "pause", "run", "no valid program", "scan overrun")

TYPE_SIZES = {"BIT": 1, "INT": 2, "LONG": 4, "REAL": 4}
TYPE_FORMATS = {"BIT": "<B", "INT": "<h", "LONG": "<l", "REAL": "<f"}
ALC_LINE = re.compile(
    r"^(\w*)\s*(\w*)\s*(\w*)\s*(\w*)\s*(\w*)\s*(\w*)\s*(\w*)\s*([\w.]*)\s*(.*)"
)


class AbusError(Exception):
    """Invalid frame or negative answer."""


# --------------------------------------------------------------------------
# frames
# --------------------------------------------------------------------------


def crc(data: bytes) -> int:
    """Return the A-bus checksum."""
    return sum((b ^ 0x5A) * CRC_TABLE[i & 0x0F] for i, b in enumerate(data)) & 0xFFFF


@dataclass
class Frame:
    """One A-bus message (transport frame + command frame)."""

    from_nad: int
    to_nad: int
    txn: int
    direction: int
    msg_type: int
    body: bytes

    @property
    def kind(self) -> str:
        """Classify the frame like the scgi server router does."""
        if self.to_nad == 0 and self.direction == ACK:
            if self.msg_type == 0:
                return "push"
            if self.msg_type == TYPE_BROADCAST:
                return "broadcast"
            return f"socket {self.msg_type}"
        return "request" if self.direction == REQ else "response"

    def __str__(self) -> str:
        """Return a one-line description."""
        direction = (
            DIRECTIONS[self.direction]
            if self.direction < len(DIRECTIONS)
            else str(self.direction)
        )
        return (
            f"{self.from_nad} -> {self.to_nad} txn={self.txn} {direction} "
            f"type={self.msg_type} body={self.body.hex() or '-'}"
        )


def encode(frame: Frame) -> bytes:
    """Return the bytes of a frame."""
    data = struct.pack("<2B", frame.direction, frame.msg_type) + frame.body
    head = HEADER.pack(SIGNATURE, len(data) + 2, frame.from_nad, frame.to_nad)
    txn = struct.pack("<H", frame.txn)
    return head + data + txn + struct.pack("<H", crc(head + data + txn))


def decode(raw: bytes) -> Frame:
    """Parse and check a received frame."""
    if len(raw) < HEADER.size + 2 + 4:
        raise AbusError(f"frame too short ({len(raw)} bytes)")
    signature, length, from_nad, to_nad = HEADER.unpack_from(raw)
    if signature != SIGNATURE:
        raise AbusError(f"invalid signature {signature:#06x}")
    available = len(raw) - HEADER.size - 4
    if length - 2 > available:
        raise AbusError(f"length {length} > available {available + 2}")
    data = raw[HEADER.size : HEADER.size + available]
    txn, checksum = struct.unpack_from("<2H", raw, HEADER.size + available)
    if checksum != crc(raw[: HEADER.size + available + 2]):
        raise AbusError("invalid crc")
    return Frame(from_nad, to_nad, txn, data[0], data[1], data[2:])


def cybro_datetime(value: int) -> datetime | None:
    """Convert a controller timestamp (FAT style) to a datetime."""
    try:
        return datetime(
            ((value >> 25) & 0x7F) + 1980,
            (value >> 21) & 0x0F,
            (value >> 16) & 0x1F,
            (value >> 11) & 0x1F,
            (value >> 5) & 0x3F,
            (value & 0x1F) * 2,
        )
    except ValueError:
        return None


# --------------------------------------------------------------------------
# transport + client
# --------------------------------------------------------------------------


class Endpoint(asyncio.DatagramProtocol):
    """UDP socket that hands frames to waiters, the rest to a queue."""

    def __init__(self, verbose: bool, capture: io.TextIOBase | None) -> None:
        """Initialize."""
        self.transport: asyncio.DatagramTransport | None = None
        self.waiters: list[tuple[Callable[[Frame], bool], asyncio.Queue]] = []
        self.unsolicited: asyncio.Queue = asyncio.Queue()
        self.verbose = verbose
        self.capture = capture
        self.rx_count = 0
        self.tx_count = 0

    def connection_made(self, transport) -> None:
        """Store the transport."""
        self.transport = transport

    def _log(self, way: str, raw: bytes, addr, note: str = "") -> None:
        if self.capture is not None:
            entry = {"t": time.time(), "dir": way, "addr": list(addr), "hex": raw.hex()}
            if note:
                entry["note"] = note
            self.capture.write(json.dumps(entry) + "\n")
        if self.verbose:
            print(f"  {way} {addr[0]}:{addr[1]} {raw.hex()} {note}")

    def datagram_received(self, data: bytes, addr) -> None:
        """Dispatch a received datagram."""
        self.rx_count += 1
        try:
            frame = decode(data)
        except AbusError as err:
            self._log("rx", data, addr, f"invalid: {err}")
            self.unsolicited.put_nowait((None, addr, data, str(err)))
            return
        self._log("rx", data, addr, str(frame))
        for match, queue in self.waiters:
            if match(frame):
                queue.put_nowait((frame, addr, time.monotonic()))
                return
        self.unsolicited.put_nowait((frame, addr, data, ""))

    def error_received(self, exc: Exception) -> None:
        """Report socket errors (e.g. ICMP port unreachable)."""
        print(f"  socket error: {exc}")

    def send(self, frame: Frame, addr) -> None:
        """Send a frame."""
        raw = encode(frame)
        self.tx_count += 1
        self._log("tx", raw, addr, str(frame))
        self.transport.sendto(raw, addr)


class Client:
    """Request/response on top of an Endpoint."""

    def __init__(self, endpoint: Endpoint, args: argparse.Namespace) -> None:
        """Initialize."""
        self.endpoint = endpoint
        self.password: int | None = args.password
        self.timeout = args.timeout_ms / 1000
        self.retries = args.retries
        self.broadcast = (args.bcast, args.target_port)
        self.target_port = args.target_port
        self._txn = itertools.count()
        self.exchanges = 0
        self.failures = 0
        self.rtts: list[float] = []

    def next_txn(self) -> int:
        """Return the next transaction id (the password, if one is set)."""
        if self.password is not None:
            return self.password
        return next(self._txn) % 0xFFFF + 1

    def request(self, nad: int, cmd: int, body: bytes = b"") -> Frame:
        """Return a request frame."""
        return Frame(SOURCE_NAD, nad, self.next_txn(), REQ, 0, bytes([cmd]) + body)

    async def exchange(self, nad: int, ip: str | None, cmd: int, body: bytes = b""):
        """Send a request, retry on timeout, return (frame, ip)."""
        addr = (ip, self.target_port) if ip else self.broadcast
        for _ in range(self.retries):
            request = self.request(nad, cmd, body)
            queue: asyncio.Queue = asyncio.Queue()

            def match(frame: Frame, request=request) -> bool:
                return (
                    frame.to_nad == SOURCE_NAD
                    and frame.from_nad == nad
                    and frame.txn == request.txn
                    and frame.direction != REQ
                )

            waiter = (match, queue)
            self.endpoint.waiters.append(waiter)
            start = time.monotonic()
            self.exchanges += 1
            try:
                self.endpoint.send(request, addr)
                frame, src, end = await asyncio.wait_for(queue.get(), self.timeout)
            except TimeoutError:
                self.failures += 1
                continue
            finally:
                self.endpoint.waiters.remove(waiter)
            self.rtts.append(end - start)
            if frame.direction != ACK:
                raise AbusError(f"controller answered {DIRECTIONS[frame.direction]}")
            return frame, src[0]
        raise TimeoutError(f"no answer from c{nad} at {addr[0]}:{addr[1]}")

    async def collect(self, nad: int, addr, cmd: int, window: float):
        """Send one request and return every answer within the window."""
        request = self.request(nad, cmd)
        queue: asyncio.Queue = asyncio.Queue()

        def match(frame: Frame) -> bool:
            return frame.to_nad == SOURCE_NAD and frame.txn == request.txn

        waiter = (match, queue)
        self.endpoint.waiters.append(waiter)
        start = time.monotonic()
        self.endpoint.send(request, addr)
        await asyncio.sleep(window)
        self.endpoint.waiters.remove(waiter)
        answers = []
        while not queue.empty():
            frame, src, end = queue.get_nowait()
            answers.append((frame, src, end - start))
        return answers


class Controller:
    """Operations on one controller."""

    def __init__(self, client: Client, nad: int, ip: str | None) -> None:
        """Initialize."""
        self.client = client
        self.nad = nad
        self.ip = ip

    async def call(self, cmd: int, body: bytes = b"") -> bytes:
        """Exchange with the controller, remember its IP."""
        frame, self.ip = await self.client.exchange(self.nad, self.ip, cmd, body)
        return frame.body

    async def ping(self) -> None:
        """Ping (finds the IP if unknown)."""
        await self.call(CMD_PING)

    async def status(self) -> tuple[str, str]:
        """Return (system status, plc status)."""
        system, plc = struct.unpack("<2B", (await self.call(CMD_READ_STATUS))[:2])
        return _name(SYSTEM_STATUS, system), _name(PLC_STATUS, plc)

    async def read_code(self, addr: int, size: int) -> bytes:
        """Read code memory, segment by segment."""
        result = b""
        while size > 0:
            segment, offset = divmod(addr, SEGMENT_SIZE)
            count = min(SEGMENT_SIZE - offset, size)
            body = await self.call(
                CMD_READ_CODE, struct.pack("<2H", segment, offset + count)
            )
            chunk = body[offset : offset + count]
            if len(chunk) != count:
                raise AbusError(
                    f"read_code {addr:#x}: got {len(body)} bytes, need {offset + count}"
                )
            result += chunk
            addr += count
            size -= count
        return result

    async def head(self) -> dict:
        """Read and decode the program head."""
        raw = await self.read_code(HEAD_ADDR, HEAD_SIZE)
        empty, magic, crc_, code_crc, alloc_crc, ret_crc, stamp = struct.unpack_from(
            "<6HL", raw
        )
        (scan_overrun,) = struct.unpack_from("<H", raw, 0x38)
        fs_addr, fs_count = struct.unpack_from("<LH", raw, 0x40)
        return {
            "raw": raw.hex(),
            "empty": empty,
            "magic": magic,
            "model": MAGICS.get(magic, "unknown"),
            "crc": crc_,
            "code_crc": code_crc,
            "alloc_crc": alloc_crc,
            "retentive_crc": ret_crc,
            "program_timestamp": str(cybro_datetime(stamp)),
            "scan_overrun": scan_overrun,
            "file_system_addr": fs_addr,
            "file_count": fs_count,
        }

    async def files(self) -> list[dict]:
        """Read the file table."""
        addr, count = struct.unpack("<LH", await self.read_code(FILE_INFO_ADDR, 6))
        raw = await self.read_code(addr, count * FILE_DESCRIPTOR.size)
        files = []
        for i in range(count):
            name, name_len, f_addr, f_size, f_date = FILE_DESCRIPTOR.unpack_from(
                raw, i * FILE_DESCRIPTOR.size
            )
            files.append(
                {
                    "name": name[:name_len].decode("latin-1"),
                    "address": f_addr,
                    "size": f_size,
                    "timestamp": str(cybro_datetime(f_date)),
                }
            )
        return files

    async def alc_text(self, files: list[dict]) -> str:
        """Download, unzip and decode the allocation table."""
        alc = next((f for f in files if f["name"] == "alc.zip"), None)
        if alc is None:
            raise AbusError("no alc.zip on the controller")
        data = await self.read_code(alc["address"], alc["size"])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            member = next(i for i in archive.infolist() if not i.is_dir())
            return archive.read(member).decode("latin-1")

    async def read_random(self, variables: list[dict]) -> dict[str, object]:
        """Read variables (from parse_alc) in frames of max. MAX_FRAME_BYTES."""
        values: dict[str, object] = {}
        groups = {1: [], 2: [], 4: []}
        for var in variables:
            groups[var["size"]].append(var)
        ordered = groups[1] + groups[2] + groups[4]
        # request: 2 bytes per address, reply: up to 4 bytes per value
        per_frame = (MAX_FRAME_BYTES - 21 - 6) // 4
        for start in range(0, len(ordered), per_frame):
            part = ordered[start : start + per_frame]
            counts = [sum(1 for v in part if v["size"] == s) for s in (1, 2, 4)]
            body = struct.pack("<3H", *counts) + struct.pack(
                f"<{len(part)}H", *(v["address"] for v in part)
            )
            reply = await self.call(CMD_READ_RANDOM, body)
            pos = 0
            for var in part:
                fmt = TYPE_FORMATS[var["type"]]
                (value,) = struct.unpack_from(fmt, reply, pos)
                pos += var["size"]
                values[var["name"]] = value
        return values


def _name(names: tuple[str, ...], value: int) -> str:
    return names[value] if value < len(names) else f"unknown ({value})"


def parse_alc(text: str) -> list[dict]:
    """Parse the allocation table like the scgi server does."""
    variables = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line[0] == ";":
            continue
        match = ALC_LINE.search(line)
        try:
            addr = int(match[1], 16) + int(match[4])
            ident = int(match[2], 16)
            array = int(match[3])
        except ValueError:
            continue  # header or unknown line
        typ = match[7].upper()
        if typ not in TYPE_SIZES:
            continue
        size = TYPE_SIZES[typ]
        names = [match[8]] if array <= 1 else [f"{match[8]}[{i}]" for i in range(array)]
        for i, name in enumerate(names):
            variables.append(
                {
                    "name": name,
                    "address": addr + i * size,
                    "size": size,
                    "type": typ,
                    "user": bool(ident & 0x02),
                    "scope": match[6],
                    "description": match[9],
                }
            )
    return variables


def format_value(value: object, typ: str) -> str:
    """Format a value like the scgi server (REAL always with a decimal point)."""
    text = str(value)  # REAL: float32 widened to double, e.g. -1512.10107421875
    if typ == "REAL" and not any(c in text for c in ".en"):
        text += ".0"
    return text


def mac_of(ip: str) -> str:
    """Return the MAC address of an IP from the ARP cache, if known."""
    with contextlib.suppress(OSError):
        for line in Path("/proc/net/arp").read_text().splitlines()[1:]:
            parts = line.split()
            if parts[0] == ip and parts[3] != "00:00:00:00:00:00":
                return parts[3]
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        out = subprocess.run(
            ["arp", "-a", ip], capture_output=True, text=True, timeout=3, check=False
        ).stdout
        found = re.search(r"([0-9a-fA-F]{1,2}[:-]){5}[0-9a-fA-F]{1,2}", out)
        if found:
            return found[0]
    return "unknown (check the router)"


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


async def cmd_ping(client: Client, args) -> None:
    """S1: find a known NAD by broadcast (or ping a given IP)."""
    addr = (args.ip, args.target_port) if args.ip else client.broadcast
    print(f"PING c{args.nad} via {addr[0]}:{addr[1]}")
    answers = await client.collect(args.nad, addr, CMD_PING, args.window)
    if not answers:
        print("  no answer")
    for frame, src, rtt in answers:
        print(f"  answer from {src[0]}:{src[1]} after {rtt * 1000:.1f} ms: {frame}")
        print(f"  MAC {mac_of(src[0])}")


async def cmd_scan(client: Client, args) -> None:
    """S2: check if anything answers a PING / READ_STATUS to a wildcard NAD."""
    targets = [(args.ip, args.target_port)] if args.ip else [client.broadcast]
    for nad in args.nads:
        for addr in targets:
            for cmd, name in ((CMD_PING, "PING"), (CMD_READ_STATUS, "READ_STATUS")):
                print(f"{name} to NAD {nad} via {addr[0]}:{addr[1]}")
                answers = await client.collect(nad, addr, cmd, args.window)
                if not answers:
                    print("  no answer")
                for frame, src, rtt in answers:
                    print(f"  {src[0]}:{src[1]} after {rtt * 1000:.1f} ms: {frame}")
                    print(f"  MAC {mac_of(src[0])}")


async def cmd_listen(client: Client, args) -> None:
    """S3/S7: print every unsolicited frame for a while."""
    endpoint = client.endpoint
    print(f"Listening on UDP {args.port} for {args.seconds} s (Ctrl+C to stop)")
    seen: Counter = Counter()
    sources: dict[tuple, str] = {}
    nad_ips: dict[int, str] = {}
    deadline = time.monotonic() + args.seconds
    with contextlib.suppress(asyncio.CancelledError, KeyboardInterrupt):
        while (left := deadline - time.monotonic()) > 0:
            try:
                frame, addr, raw, error = await asyncio.wait_for(
                    endpoint.unsolicited.get(), left
                )
            except TimeoutError:
                break
            stamp = datetime.now().strftime("%H:%M:%S")
            if frame is None:
                print(f"{stamp} {addr[0]}:{addr[1]} INVALID ({error}) {raw.hex()}")
                seen[("invalid", addr[0])] += 1
                continue
            print(f"{stamp} {addr[0]}:{addr[1]} {frame.kind}: {frame}")
            key = (frame.kind, frame.from_nad)
            seen[key] += 1
            sources[key] = f"{addr[0]}:{addr[1]}"
            nad_ips[frame.from_nad] = addr[0]
            if args.ack_push and frame.kind == "push":
                body = bytes([CMD_WRITE_DATA]) + struct.pack(
                    "<2HB", PUSH_ACK_ADDRESS, 1, 1
                )
                ack = Frame(SOURCE_NAD, frame.from_nad, client.next_txn(), REQ, 0, body)
                endpoint.send(ack, addr)
                print(f"         push ACK sent to c{frame.from_nad}")
    print("\nSummary (kind, from NAD): count, source")
    for key, count in sorted(seen.items(), key=str):
        print(f"  {key}: {count}, {sources.get(key, '')}")
    for nad, ip in sorted(nad_ips.items()):
        print(f"  c{nad} at {ip}, MAC {mac_of(ip)}")


async def cmd_info(client: Client, args) -> None:
    """S1/S4/S5/S6: status, head, files and ALC download timing."""
    plc = Controller(client, args.nad, args.ip)
    report: dict = {"nad": args.nad}
    start = time.monotonic()
    await plc.ping()
    report["ip"] = plc.ip
    report["mac"] = mac_of(plc.ip)
    report["locate_ms"] = round((time.monotonic() - start) * 1000, 1)
    report["system_status"], report["plc_status"] = await plc.status()
    report["head"] = await plc.head()
    report["files"] = await plc.files()
    exchanges = client.exchanges
    start = time.monotonic()
    text = await plc.alc_text(report["files"])
    report["alc_download_s"] = round(time.monotonic() - start, 2)
    report["alc_download_exchanges"] = client.exchanges - exchanges
    report["alc_text_bytes"] = len(text)
    variables = parse_alc(text)
    report["variables"] = len(variables)
    report["user_variables"] = sum(v["user"] for v in variables)
    report["types"] = dict(Counter(v["type"] for v in variables))
    report["rtt_ms"] = _rtt_stats(client.rtts)
    report["timeouts"] = client.failures
    if args.save_alc:
        path = Path(args.save_alc) / f"c{args.nad}.alc"
        path.write_text(text, encoding="latin-1")
        report["alc_saved"] = str(path)
    print(json.dumps(report, indent=2))


async def cmd_read(client: Client, args) -> None:
    """Read variables by name (uses the controller's ALC)."""
    plc = Controller(client, args.nad, args.ip)
    files = await plc.files()
    variables = {v["name"]: v for v in parse_alc(await plc.alc_text(files))}
    if args.user:
        wanted = [v for v in variables.values() if v["user"]]
    else:
        missing = [n for n in args.names if n not in variables]
        if missing:
            print(f"not in the ALC: {', '.join(missing)}")
        wanted = [variables[n] for n in args.names if n in variables]
    start = time.monotonic()
    values = await plc.read_random(wanted)
    elapsed = (time.monotonic() - start) * 1000
    for var in wanted:
        value = format_value(values[var["name"]], var["type"])
        print(f"c{args.nad}.{var['name']} = {value}")
    print(f"{len(wanted)} variables in {elapsed:.0f} ms, timeouts: {client.failures}")


async def cmd_maxframe(client: Client, args) -> None:
    """S6: find the largest READ_RANDOM the controller accepts."""
    plc = Controller(client, args.nad, args.ip)
    await plc.ping()
    files = await plc.files()
    first = next(v for v in parse_alc(await plc.alc_text(files)) if v["size"] == 4)
    for count in (50, 100, 150, 200, 230, 240, 250, 300, 400):
        request_bytes = 21 + 6 + 2 * count
        reply_bytes = 18 + 4 * count
        body = struct.pack("<3H", 0, 0, count) + struct.pack(
            f"<{count}H", *([first["address"]] * count)
        )
        try:
            reply = await plc.call(CMD_READ_RANDOM, body)
            result = f"ok ({len(reply)} bytes)"
        except (TimeoutError, AbusError) as err:
            result = f"FAILED: {err}"
        print(
            f"{count} x 4-byte values: request {request_bytes} B, "
            f"reply {reply_bytes} B -> {result}"
        )


def _rtt_stats(rtts: list[float]) -> dict:
    if not rtts:
        return {}
    ms = sorted(r * 1000 for r in rtts)
    return {
        "min": round(ms[0], 1),
        "median": round(ms[len(ms) // 2], 1),
        "max": round(ms[-1], 1),
        "count": len(ms),
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--bcast", default="255.255.255.255", help="broadcast address")
    common.add_argument("--port", type=int, default=0, help="local UDP port (0=any)")
    common.add_argument(
        "--target-port", type=int, default=ABUS_PORT, help="controller UDP port"
    )
    common.add_argument("--bind", default="0.0.0.0", help="local address")
    common.add_argument("--password", type=int, help="A-bus password")
    common.add_argument("--timeout-ms", type=int, default=200)
    common.add_argument("--retries", type=int, default=3)
    common.add_argument("--capture", help="append raw frames to this .jsonl file")
    common.add_argument("-v", "--verbose", action="store_true", help="print hex")
    sub = parser.add_subparsers(dest="command", required=True)

    def target(p: argparse.ArgumentParser, nad_required: bool = True) -> None:
        p.add_argument("--nad", type=int, required=nad_required, help="serial no.")
        p.add_argument("--ip", help="controller IP (default: broadcast)")

    p = sub.add_parser("ping", parents=[common], help="S1: locate a NAD")
    target(p)
    p.add_argument("--window", type=float, default=1.0, help="seconds to collect")
    p = sub.add_parser("scan", parents=[common], help="S2: wildcard probe")
    p.add_argument("--ip", help="unicast instead of broadcast")
    p.add_argument("--nads", type=int, nargs="+", default=[0, 0xFFFFFFFF])
    p.add_argument("--window", type=float, default=2.0, help="seconds to collect")
    p = sub.add_parser("listen", parents=[common], help="S3/S7: unsolicited frames")
    p.add_argument("--seconds", type=float, default=600)
    p.add_argument("--ack-push", action="store_true", help="acknowledge pushes")
    p = sub.add_parser("info", parents=[common], help="S1/S4/S6: controller info")
    target(p)
    p.add_argument(
        "--save-alc", metavar="DIR", nargs="?", const=".", help="save the ALC text"
    )
    p = sub.add_parser("read", parents=[common], help="read variables")
    target(p)
    p.add_argument("--user", action="store_true", help="all user variables")
    p.add_argument("names", nargs="*", help="variable names without cNAD.")
    p = sub.add_parser("maxframe", parents=[common], help="S6: max frame size")
    target(p)

    args = parser.parse_args(argv)
    if args.command == "listen" and args.port == 0:
        args.port = ABUS_PORT
    if args.command == "read" and not args.user and not args.names:
        parser.error("read: give variable names or --user")
    return args


async def run(args: argparse.Namespace) -> int:
    """Open the socket and run the command."""
    capture = open(args.capture, "a", encoding="utf-8") if args.capture else None  # noqa: SIM115
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind((args.bind, args.port))
    except OSError as err:
        print(f"Can't bind UDP {args.bind}:{args.port}: {err}")
        if args.port == ABUS_PORT:
            print("Is the scgi server / add-on still running on this host?")
        return 2
    transport, endpoint = await loop.create_datagram_endpoint(
        lambda: Endpoint(args.verbose, capture), sock=sock
    )
    host, port = sock.getsockname()[:2]
    print(f"local UDP {host}:{port}, source NAD {SOURCE_NAD}")
    if Path("/.dockerenv").exists() and (
        args.command == "listen" or not getattr(args, "ip", None)
    ):
        print(
            "WARNING: running in a container. Broadcasts usually don't reach the "
            "LAN, and forwarded frames may show the gateway IP. Use --ip, or run "
            "this script on the host."
        )
    client = Client(endpoint, args)
    commands = {
        "ping": cmd_ping,
        "scan": cmd_scan,
        "listen": cmd_listen,
        "info": cmd_info,
        "read": cmd_read,
        "maxframe": cmd_maxframe,
    }
    try:
        await commands[args.command](client, args)
    except (TimeoutError, AbusError, zipfile.BadZipFile) as err:
        print(f"ERROR: {err}")
        return 1
    finally:
        transport.close()
        if capture is not None:
            capture.close()
        print(f"frames: tx {endpoint.tx_count}, rx {endpoint.rx_count}")
    return 0


def main() -> int:
    """Entry point."""
    args = parse_args(sys.argv[1:])
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
