# A-bus notes (hardware spike results)

Results of `scripts/abus_probe.py` against real controllers, run natively on
the host (not in the devcontainer). See `tasks/standalone-plan.md`, section 4.

## Network seen during the spike (2026-10-25)

| NAD | IP | MAC | Answers NAD 0 scan | Sends sockets |
|---|---|---|---|---|
| 10000 | 192.168.10.218 | `00:cb:00:00:50:f2` | yes | not in 60 s |
| 8352 | 192.168.10.15 | `00:cb:00:00:32:6b` | yes | not in 60 s |
| 8372 | 192.168.10.13 | `00:cb:00:00:20:98` | yes | 3, 11, 23 (every ~2 s) |
| 32215 | 192.168.10.14 | `00:cb:00:00:7d:d7` | yes | 4, 20 |
| 13049898 | 192.168.10.39 | unknown | **no** | 24 (every ~5 s) |

c13049898 is a test device with basic features only, not a HIQ controller.
It must not be discovered or set up.

Also on the LAN: two scgi servers (192.168.10.201, MAC `02:11:3d:9c:96:74`,
and 192.168.10.48) using source NAD 1003 (autodetect). Both keep sending
broadcast PINGs to c13049898 without getting an answer.

## Results

| # | Question | Result | Status |
|---|---|---|---|
| S1 | Frame encoding, broadcast PING to a known NAD | Works. c10000 answers from `:8442` to the probe's ephemeral port after 2–5 ms | ✅ (golden bytes: `--capture` still open) |
| S2 | Answer to a wildcard NAD | **Broadcast PING or READ_STATUS to NAD 0: every controller answers with its own NAD as `from_nad`** (4 of 5). READ_STATUS also returns the status (`0102` = kernel active, run). NAD 0xFFFFFFFF: no answer. Unicast to 192.168.10.50 got no answer, but .50 is not a controller → repeat with a controller IP | ✅ broadcast · unicast open |
| S3 | Unsolicited frames on :8442 | Only Cybro **socket** frames (to_nad 0, ACK, type = socket id), from 3 of 5 controllers. No push, no type 0x64 broadcast. Also REQ frames from the scgi servers (PING to 13049898) | ✅ |
| S4 | MAC prefix | All 4 known MACs start with **`00:cb:00`**. The low bytes are not the NAD (only c32215 matches by chance) | ✅ usable for DHCP matching |
| S5 | A-bus password / push by default | c10000 has no password: it answers with any transaction id (`--password 1234` reads normally). So a wrong password can't be detected on an unprotected controller. c13049898 is a basic test device (no answers by design) | ✅ |
| S8 | REAL value vs scgi server | c32215.fPowerTotal (ALC: `3218  00004 1 0 4 global real fPowerTotal`): direct `-1512.10107421875` (float32), scgi `-1512.10107421875` → identical once formatted with `str()` | ✅ |
| S6 | Timing, ALC, max frame | **Max frame:** READ_RANDOM with 300 × 4-byte values (request 627 B, reply 1218 B) works; 400 values (reply 1618 B, above the 1472-byte UDP payload of a 1500 MTU) times out. 3 frames arrived that matched nothing (rx 125 / tx 122), cause unknown. → keep the 1000-byte limit. **Read:** 32 user variables in 1–3 ms (one frame). c10000: RTT 1.7 / 2.4 / 4.3 ms (min/median/max). `alc.zip` 27,563 bytes → 108 READ_CODE exchanges in **0.3 s**. ALC text 312 kB, **14,990 variables** (BIT 2413, INT 12423, LONG 154, no REAL), only 32 user variables. Program 2026-10-10 14:19:50, Cybro-3 | ✅ |
| S7 | Push ACK needed? | No push frames seen → not relevant for these controllers | ✅ n/a |

## HIQ program marker

The HIQ program sets at startup:

```text
// program id and version
  program_id:=3;
  version_major:=6;
  version_minor:=1;
  version_release:=1; //a
```

`program_id = 3` identifies a HIQ controller. Discovery only offers
controllers with this value.

## Consequences for the plan

1. **Active discovery works and is the main path (T14).** One broadcast
   READ_STATUS to NAD 0 returns NAD, IP and run state of every controller in
   one round trip. Run it at start and periodically.
2. **DHCP discovery (T15) is possible** with `macaddress: "00CB00*"`. The
   DHCP step doesn't need a unicast NAD lookup: it can run the broadcast
   scan and take the controller with the matching IP.
3. **Passive listening (T13) only adds value**, because only some controllers
   send sockets. Useful to catch IP changes. It must only use frames with
   to_nad 0 + ACK and ignore REQ frames (scgi servers, our own broadcasts).
4. **ALC download is cheap (0.3 s)** → keep the ALC in memory per program
   timestamp. Persisting it in HA storage is not needed.
5. **Non-user variables must be readable** (only 32 of 14,990 are user
   variables, the integration uses many others).
6. **Devices that send sockets but don't answer requests** (c13049898, a test
   device) must not be offered. The active scan skips them anyway (no answer
   to NAD 0). The passive listener therefore never creates flows itself: it
   only updates the IP of configured entries.
7. **Max frame 1000 bytes** stays (works up to ~1200 B reply, fails above
   the MTU).
8. **Password field is optional.** An unprotected controller accepts any
   value, so setup can't warn about a needless password.
9. **REAL values are formatted like Python `str(float)`** of the float32
   widened to a double: c32215.fPowerTotal is `-1512.10107421875` from the
   scgi server, read directly as the same float32. Direct mode must use
   `str(value)`, not rounding, so templates and custom sensors see the same
   text in both modes.

## Golden frames (for T1 tests)

All 390 captured frames (`frames.jsonl`, `frames1.jsonl`; READ_CODE and
READ_RANDOM) decode with a valid CRC and re-encode to identical bytes.

| Frame | Hex |
|---|---|
| READ_CODE head request (1010 → 32215, segment 0x200, 0x46 bytes) | `aa550900f2030000d77d0000000021000246000100bbe8` |
| READ_RANDOM request (1010 → 32215, one 4-byte value at 0x3218) | `aa550d00f2030000d77d000000003300000000010018322a009940` |
| READ_RANDOM response (32215 → 1010, REAL `-1678.8477783203125`) | `aa550800d77d0000f2030000010021dbd1c42a009e48` |

PING, READ_STATUS and socket frames weren't captured as raw bytes. They are
built by the same code, and their decoded form is in the outputs below.

## ALC files (4 controllers)

| Controller | Lines | `program_id` | HIQ |
|---|---|---|---|
| c10000 | 2028 | yes (+ `version_major/minor/release`) | **yes** |
| c32215 | 612 | no | no |
| c8352 | 172 | no | no |
| c8372 | 709 | no | no |

- The header says `;CPU CyBro-2 <nad>`, while the head magic 31416 is "Cybro-3"
  in the toolkit's naming. Don't show either as the model without checking.
- Text uses CRLF and ends with an empty line.
- **python-cybro `PlcInfo.parse_alc_file()` has two bugs** (also with scgi):
  it crashes with `IndexError` on the trailing empty line of the raw text, and
  `line[43:-1]` cuts the last character of names that end the line
  (`main.alarm_algo.alarm_indicator_old` → `..._ol`; 13 / 18 / 0 / 9 names on
  the four controllers). Only local `main.*` names are affected, so the
  integration's global variables are fine today. Fix both in python-cybro 1.0.

## Raw output

### S1: `ping --nad 10000`

```text
PING c10000 via 255.255.255.255:8442
  answer from 192.168.10.218:8442 after 4.9 ms: 10000 -> 1010 txn=1 ACK type=0 body=-
  MAC 00:cb:00:00:50:f2
```

### S2: `scan`

```text
PING to NAD 0 via 255.255.255.255:8442
  192.168.10.14:8442 after 4.9 ms: 32215 -> 1010 txn=1 ACK type=0 body=-
  192.168.10.15:8442 after 5.3 ms: 8352 -> 1010 txn=1 ACK type=0 body=-
  192.168.10.218:8442 after 5.3 ms: 10000 -> 1010 txn=1 ACK type=0 body=-
  192.168.10.13:8442 after 12.3 ms: 8372 -> 1010 txn=1 ACK type=0 body=-
READ_STATUS to NAD 0 via 255.255.255.255:8442
  192.168.10.14:8442 after 7.2 ms: 32215 -> 1010 txn=2 ACK type=0 body=0102
  192.168.10.218:8442 after 7.2 ms: 10000 -> 1010 txn=2 ACK type=0 body=0102
  192.168.10.15:8442 after 9.4 ms: 8352 -> 1010 txn=2 ACK type=0 body=0102
  192.168.10.13:8442 after 36.8 ms: 8372 -> 1010 txn=2 ACK type=0 body=0102
PING to NAD 4294967295 via 255.255.255.255:8442
  no answer
READ_STATUS to NAD 4294967295 via 255.255.255.255:8442
  no answer
```

### S3: `listen --seconds 60` (excerpt, 72 frames)

```text
192.168.10.13:8442 socket 3: 8372 -> 0 txn=0 ACK type=3 body=010100499357c5ff9c9746fec1df47
192.168.10.13:8442 socket 11: 8372 -> 0 txn=0 ACK type=11 body=f628dc3e000020c0000034420000b0410000b4416666663f0000000000001644b899a9416766b241000000009a99a94100000000
192.168.10.13:8442 socket 23: 8372 -> 0 txn=0 ACK type=23 body=fec1df47ff9c97467c7257c57c7257c57c7257c5d258c43ff2fd253f004b5341c8ca6a43ac336c43e2b56743
192.168.10.14:8442 socket 4: 32215 -> 0 txn=0 ACK type=4 body=0101000000000066663641cdcc2c420000b8416666d241cdccd84100000000
192.168.10.14:8442 socket 20: 32215 -> 0 txn=0 ACK type=20 body=0100016501d4ab58c5ff9c9746ffc1df47
192.168.10.39:8442 socket 24: 13049898 -> 0 txn=0 ACK type=24 body=5a645b40000000005a645bc0
192.168.10.201:8442 request: 1003 -> 13049898 txn=40780 REQ type=0 body=10
192.168.10.48:8442 request: 1003 -> 13049898 txn=68 REQ type=0 body=10

Summary (kind, from NAD): count, source
  ('request', 1003): 27, 192.168.10.201:8442
  ('socket 11', 8372): 2, 192.168.10.13:8442
  ('socket 20', 32215): 1, 192.168.10.14:8442
  ('socket 23', 8372): 21, 192.168.10.13:8442
  ('socket 24', 13049898): 4, 192.168.10.39:8442
  ('socket 3', 8372): 16, 192.168.10.13:8442
  ('socket 4', 32215): 1, 192.168.10.14:8442
```

### S1/S6: `info --nad 10000 --save-alc .`

```json
{
  "nad": 10000, "ip": "192.168.10.218", "mac": "00:cb:00:00:50:f2",
  "locate_ms": 1.9, "system_status": "kernel active", "plc_status": "run",
  "head": {
    "raw": "0000b87a06fb04579d1db73279724a5d46350100230001007ce10000000001000100010000000000ec0efe0e0c0f740f00000000c00401000100010003000100483503000200",
    "magic": 31416, "model": "Cybro-3", "program_timestamp": "2026-10-10 14:19:50",
    "scan_overrun": 1, "file_system_addr": 210248, "file_count": 2
  },
  "files": [
    {"name": "cyp.zip", "address": 210340, "size": 30069},
    {"name": "alc.zip", "address": 240409, "size": 27563}
  ],
  "alc_download_s": 0.3, "alc_download_exchanges": 108, "alc_text_bytes": 312493,
  "variables": 14990, "user_variables": 32,
  "types": {"BIT": 2413, "INT": 12423, "LONG": 154},
  "rtt_ms": {"min": 1.7, "median": 2.4, "max": 4.3, "count": 113}, "timeouts": 0
}
```

### S6: `maxframe --nad 10000`

```text
250 x 4-byte values: request 527 B, reply 1018 B -> ok (1000 bytes)
300 x 4-byte values: request 627 B, reply 1218 B -> ok (1200 bytes)
400 x 4-byte values: request 827 B, reply 1618 B -> FAILED: no answer from c10000 at 192.168.10.218:8442
frames: tx 122, rx 125
```

### `read --nad 10000 --user` (also with `--password 1234`, same result)

```text
c10000.ready_light_enable[0] = 0
...
c10000.ready_light_long_timeout[0] = 300
...
32 variables in 3 ms, timeouts: 0
```

### S8: REAL value, direct vs scgi

```text
❯ grep -i powertotal c32215.alc
3218  00004 1     0      4    global real  fPowerTotal
❯ python abus_probe.py read --nad 32215 fPowerTotal
c32215.fPowerTotal = -1512.1          (old probe formatting, 6 digits)
❯ curl "http://192.168.10.201:4000/?c32215.fPowerTotal"
<data><var><name>c32215.fPowerTotal</name><value>-1512.10107421875</value><description /></var></data>
```
