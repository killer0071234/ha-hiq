# Plan: Standalone HIQ integration (direct A-bus/UDP) + controller discovery

Status: draft for review · Repos: `ha-hiq` (this) and `python-cybro`
Sources: this repo, `temp/CybroEdgeToolkit.zip` (scgi_server v3.4.0 source,
manual v18), `temp/quick_sync.zip`.

## 1. Goal

The integration talks directly to HIQ/Cybro controllers over A-bus (UDP 8442),
so the CybroScgiServer add-on is no longer required. New controllers on the
network are found automatically and offered in **Settings → Devices &
services → Discovered**.

### Decisions (approved)

| Topic | Decision |
|---|---|
| Where the protocol lives | **python-cybro** gets a direct UDP transport (`cybro.abus` + `CybroDirect`), released as a new major version |
| SCGI mode | **Keep both.** Config flow offers *Direct (UDP)* (default) and *SCGI server*. Existing entries keep working unchanged |
| Discovery | **Passive listen on 8442** + **active broadcast probe** + **DHCP (MAC prefix)**. The last two depend on spike results |
| Code reuse | Cybrotech allows reuse. The protocol code may be ported from the Edge Toolkit, with attribution |
| Events | **Polling only** in the first release. Push and socket events are a later phase (§8) |
| Hardware | Maintainer can run probe scripts against a real HIQ controller |
| Source NAD | **1010** for all direct A-bus requests |
| Already configured in SCGI mode | Discovery **offers a switch** to direct mode |
| Minimum HA version | **2026.10** |
| Discovery filter | Offer **only HIQ controllers**: `program_id = 3` (HIQ program, also sets `version_major/minor/release`) |

### Not in scope (first release)

- Live entity updates from Cybro sockets and push (`local_push`)
- Remote controllers behind NAT (push-only mode). Use SCGI mode for that
- The SCGI server's cache, aliases, data logger and TLS

## 2. Findings

### 2.1 Quick Sync does not help

`quick_sync.py` is another SCGI client. It sends HTTP GET to
`localhost:4000/?cNAD.var` and opens a websocket to the same server. It needs
the server just like python-cybro does. Nothing from it is used.

### 2.2 The Edge Toolkit contains the full protocol

`app/scgi_server/local/...` is plain Python, stdlib only (asyncio, struct,
zipfile). Relevant parts:

| Part | Source file(s) | Notes |
|---|---|---|
| Transport frame | `abus/transport_frame.py` | `<2H2L` header: signature `0x55AA` (bytes `AA 55`), length, from_nad, to_nad · data · `<H` transaction id · `<H` CRC. CRC = Σ (byte ^ 0x5A) · PRIM[i & 15], & 0xFFFF |
| Command frame | `abus/command_frame.py` | `<2B` direction + type, then body. Commands PING 0x10, READ_STATUS 0x11, READ_CODE 0x21, WRITE_DATA 0x32, READ_RANDOM 0x33, WRITE_RANDOM 0x34. Directions REQ/ACK/BAD_CMD/…/DENIED |
| Message kinds | `abus/abus_message.py` | push = to_nad 0 + ACK + type 0 · socket = to_nad 0 + ACK + type ≠ 0 · broadcast = type 0x64 |
| Request/response | `abus/abus_exchanger.py` | Match on (from, to, transaction id). Timeout 200 ms, 3 retries. One request in flight per exchanger |
| Password | `plc_client.py` | If an A-bus password is set, **transaction id = password** |
| Source NADs | `defaults.py` | Server uses 1001 (push), 1002 (rw), 1003 (autodetect) |
| PLC head | `plc_head.py` | READ_CODE segment 0x0200, 0x46 bytes. magic 31415/31416 (Cybro-2/3), program timestamp (FAT-style date), file system addr/count |
| Status | `status.py` | 2 bytes: system (loader/kernel) and PLC status (STOP/PAUSE/RUN/NO_PROGRAM/OVERRUN) |
| ALC download | `plc_client.fetch_alc_file` | File table at 0x20040 → 46-byte descriptors → `alc.zip` read in 256-byte code segments → unzip → latin-1 text |
| ALC parsing | `alc_parser.py` | Regex per line: addr, id (bit 1 = user var), array size, offset, size, scope, type (BIT/INT/LONG/REAL), name, description. Arrays expand to `name[i]` |
| Read/write | `plc_client_read_write_util.py` | READ_RANDOM/WRITE_RANDOM grouped by 1/2/4-byte size, little-endian, INT = `h`, LONG = `l`, REAL = `f`. Split so that frames stay ≤ 1000 bytes |
| Program change | `plc_communicator.py` | Head is read before each operation. A new program timestamp invalidates the ALC. Status must be RUN/PAUSE + KERNEL |
| IP detection | `plc_detection_service.py` | Broadcast PING **to a known NAD** on `<bcast>:8442`. Response source address = controller IP. On timeout, the IP is detected again |
| Push ACK | `command_frame.create_push_ack` | WRITE_DATA to 0x0417, value 1 |

**Important:** the server's "autodetect" cannot find unknown controllers. It
only finds the IP of a NAD it already knows. Unknown controllers only appear
when they send something: push, socket, or a `0x64` broadcast frame. This is
why the hardware spike (Phase 0) comes first.

### 2.3 What the integration needs from python-cybro today

- `Cybro(host, port, nad, session)`, `update(full_update, device_type=1)`,
  `write_var(name, str)`, `request(dict)`, `.nad`
- `Device.vars[name].value` (**strings**: `"?"` = unreadable), `Device.add_var`
  / `remove_var`, `Device.plc_info.plc_vars` (from the ALC text),
  `plc_info.plc_status` (`"ok"`/`"run"`), `plc_info.nad`,
  `server_info.server_version` (device info), `c<nad>.sys.ip_port` (sensor)
- `VarType`, `CybroError`, `CybroConnectionError`, `CybroConnectionTimeoutError`

`PlcInfo.parse_alc_file()` parses the same ALC text the controller provides.
So a direct backend that fills `sys.alc_file` with the downloaded text keeps
every `plc_vars` lookup in the platforms unchanged.

### 2.4 Integration constraints

- `HiqFlowHandler` is a `SchemaConfigFlowHandler`. It cannot host `dhcp` or
  `integration_discovery` steps → the config flow must become a regular
  `ConfigFlow`, while the options flow stays schema based.
- Entry unique IDs are `c{nad}@host:port` (migrated v1 entries) or not set
  (v2 entries). Discovery needs a stable **`c{nad}`** unique ID → config entry
  migration v2 → v3.
- Entity unique IDs use variable names (`c1000.lc00_qx00`). They don't depend
  on the transport, so switching an entry from SCGI to direct keeps the entities.

## 3. Architecture

```
┌──────────────────── Home Assistant ─────────────────────────────────┐
│ hiq integration                                                     │
│  ├ coordinator ── Cybro (SCGI, aiohttp)  ──HTTP──► scgi server      │
│  │             └─ CybroDirect ─┐                                    │
│  ├ discovery.py (listener + periodic probe) ──► discovery_flow      │
│  └ config_flow (user / dhcp / integration_discovery / reconfigure)  │
│                                │                                    │
│  hass.data[DOMAIN].transport ──┴─ AbusTransport (one UDP socket,    │
│                                    bound :8442, fallback :0)        │
└────────────────────────────────────┬────────────────────────────────┘
                                     │ UDP A-bus (unicast + broadcast)
                         HIQ / Cybro controllers :8442
```

### 3.1 python-cybro (new major version, e.g. 1.0.0)

```
cybro/abus/frame.py      encode/decode transport + command frames, CRC, enums
cybro/abus/transport.py  AbusTransport: asyncio DatagramProtocol, shared socket,
                         futures keyed by (to_nad, from_nad, txn), timeout/retry,
                         on_unsolicited(callback) for discovery
cybro/abus/client.py     AbusClient(transport, nad, ip=None, password=None):
                         ping, read_status, read_head, read_code, fetch_alc,
                         read_random, write_random (with frame splitting)
cybro/abus/alc.py        unzip + parse ALC (typed: addr, type, size, user flag)
cybro/abus/locate.py     locate(nad) via broadcast PING; probe()/scan() per spike
cybro/direct.py          CybroDirect: same public API as Cybro, returns Device
```

`CybroDirect` behaviour:

- **update()**: reads head and status (2 small exchanges). If the program
  timestamp changed → fetch the ALC again. Then one or more READ_RANDOM for
  `user_vars`. Fills `Device.vars` with **strings**, formatted like the SCGI
  server: REAL as `str()` of the float32 widened to a double (`-1512.10107421875`, spike S8), BIT `0`/`1`, unknown → `"?"`.
  `c<nad>.sys.*` values are created locally: `ip_port`, `plc_status`
  (`ok`/`stop`/`pause`/`no program`/`offline`), `timestamp`, `alc_file`,
  `response_time`, `com_error_count`, `bytes_transferred`. `server_info`
  gets `server_version = "direct <lib version>"` and zero counters.
- **write_var(name, str)**: converts the string to the ALC type (range check),
  then WRITE_RANDOM. Raises `CybroError` for unknown or read-only variables.
- **request(dict)**: batch read/write, same return shape as the SCGI version
  (the integration uses it for refresh-after-write).
- IP: a static IP (optional) is used as given. Otherwise `locate()` runs on
  first use and again after a timeout (same as the server's retry).
- Source NAD: **1010** (not 1001–1003, so it doesn't collide with an SCGI
  server on the same LAN). A constructor argument in the lib, not exposed in
  the HA UI.
- One lock per controller. Requests to different controllers can run in
  parallel on the shared transport.
- ALC kept **in memory** per program timestamp. Spike S6: a 27 kB `alc.zip`
  downloads in 0.3 s, so it isn't stored on disk.
- `scan(broadcast)`: broadcast READ_STATUS to **NAD 0**. Every controller
  answers with its own NAD, its IP (source address) and run state (spike S2).
- Unzip runs in an executor (it blocks).

### 3.2 Integration

| Area | Change |
|---|---|
| `const.py` | `CONF_CONNECTION` (`direct` / `scgi`), `CONF_PASSWORD`, `CONF_IP` (optional), `ABUS_PORT = 8442`, direct scan interval (5 s) |
| `__init__.py` | Shared `AbusTransport` in `hass.data[DOMAIN]`: created with the first direct entry, closed with the last one. Bind 8442; if busy → bind :0 and create a **repair issue** ("Port 8442 in use, e.g. by the SCGI add-on – passive discovery disabled"). Migration **v2 → v3**: `options[CONF_CONNECTION] = "scgi"`, unique_id `c{nad}` (keep the old one if `c{nad}` is already taken) |
| `coordinator.py` | Picks `CybroDirect` or `Cybro` from the options. Error mapping and get_value logic stay the same |
| `config_flow.py` | `HiqConfigFlow(ConfigFlow)` with steps `user` (menu: direct / scgi), `direct` (NAD, optional IP, optional password), `scgi` (current form), `integration_discovery`, `dhcp`, `reconfigure` (switch scgi ↔ direct). `async_set_unique_id(f"c{nad}")` + `_abort_if_unique_id_configured(updates={CONF_IP: ip})`. Options flow stays the schema flow |
| `discovery.py` (new) | **Active scan** (main path): `scan()` at start + every 15 min → for each unknown NAD `discovery_flow.async_create_flow(..., SOURCE_INTEGRATION_DISCOVERY, data={nad, ip})`, deduplicated per NAD. **Passive listener** (extra): socket frames (to_nad 0 + ACK) only update the IP of configured entries and never create flows, so devices that send sockets but don't answer (test device c13049898) are never offered. REQ frames (scgi servers, own broadcasts) are ignored |
| `manifest.json` | `requirements: cybro==1.x`, `dhcp: [{"macaddress": "00CB00*"}]` (spike S4), `iot_class` stays `local_polling` |
| `strings.json`, `en.json`, `de.json` | New steps, errors (`not_found`, `no_program`, `denied`/password), discovery confirm, repair issue |
| `sensor.py` | Nothing needed (`sys.ip_port` is created locally). Optional: hide server-only diagnostics in direct mode |
| README / docs | Prerequisites: SCGI server is optional. Network: same broadcast domain, UDP 8442, Docker needs `network_mode: host`. Discovery and port conflict explained |

## 4. Phase 0: Hardware spike (before writing production code)

Probe script `scripts/abus_probe.py` (in this repo for now, moves to
python-cybro with T1; stdlib only, Python 3.11+). Tested against a fake
controller that encodes frames with the Edge Toolkit's own classes. Run with
the SCGI server **stopped**.

| # | Question | How | Decides |
|---|---|---|---|
| S1 | Does our frame encoding work? Collect golden bytes | Broadcast PING to known NAD, then READ_STATUS, head, a READ_RANDOM | Unit-test vectors for Phase 1 |
| S2 | Does a controller answer a PING to **to_nad 0** / a wildcard (broadcast and unicast)? | Send both, log every response with from_nad | Active probe + DHCP NAD lookup possible? |
| S3 | What does a controller send unsolicited to :8442? | Listen 10 min, decode all frames (push, socket, 0x64 broadcast) | What passive discovery reacts to |
| S4 | Cybrotech MAC OUI | ARP table / router | `dhcp` matcher |
| S5 | Do HIQ controllers have an A-bus password or push configured by default? | CyPro settings / HIQ docs | Password field, push expectations |
| S6 | Response time, max frame size, ALC size and download time | Timing in the probe | Timeouts, frame limit, need for ALC cache |
| S7 | Must received pushes be ACKed or the controller logs errors? | Observe with/without ACK | Whether the listener ACKs pushes |

Exit: results written to `docs/abus-notes.md` (facts + captured hex). Discovery
tasks in Phase 4 are adjusted to these results.

## 5. Task list

Sizes: S ≈ ≤ 1 file / few hours, M ≈ 2–4 files / ~1 day.

### Phase 1: Protocol core (python-cybro)

- [ ] **T1 (S) Frame codec + CRC.** `cybro/abus/frame.py`.
  *Done when:* encode(decode(x)) == x for S1 captures. A wrong CRC, signature or
  length raises `AbusError`. CRC vectors pass.
- [ ] **T2 (M) AbusTransport.** Shared datagram endpoint, futures by
  (nad pair, txn), 200 ms × 3 retries, broadcast enabled, unsolicited callback,
  close().
  *Done when:* tests with a loopback fake peer cover match, timeout and retry,
  ignoring foreign frames, and two controllers in parallel.
- [ ] **T3 (M) AbusClient basics.** ping, read_status, read_head, read_code
  (segmenting), locate().
  *Done when:* fake controller tests pass. Probe run against real hardware
  returns the status and program timestamp.
- [ ] **T4 (M) ALC.** fetch_alc (descriptor table → `alc.zip` → unzip in
  executor) + typed parser (arrays, user flag, BIT/INT/LONG/REAL). Also fix
  `PlcInfo.parse_alc_file()`: skip blank lines, don't cut the last character
  of the name (`line[43:-1]`), see notes "ALC files".
  *Done when:* the real controller's ALC parses and the variable count matches
  `sys.variables` of the SCGI server.
- [ ] **T5 (M) Random read/write.** Group by size, split ≤ 1000 bytes, type
  conversion, password as txn id.
  *Done when:* reading 300 variables gives the same values as the SCGI server
  (one live comparison script). Writing a test variable round-trips.

**Checkpoint 1:** python-cybro `pytest` + lint green. Live comparison script:
direct vs SCGI values identical for all user variables of the HIQ controller.

### Phase 2: CybroDirect facade + test fake (python-cybro)

- [ ] **T6 (M) `CybroDirect`.** Same API as `Cybro`. `Device` with string values
  + local `sys.*`. IP relearn after timeout. Reload the ALC when the program
  timestamp changes. ALC store hooks.
  *Done when:* the existing `Cybro` model tests also pass against `CybroDirect`.
  Changing the program on the controller (or in the fake) triggers a reload.
- [ ] **T7 (S) Reusable fake UDP controller.** `cybro.testing.FakeAbusController`
  (variables + generated ALC zip, optional password, optional push/broadcast
  emission). Used by both repos.
- [ ] **T8 (S) Release `cybro` 1.0.0b1** (pre-release on PyPI) + changelog.

**Checkpoint 2:** beta installable. The `ha-hiq` dev container runs with
`pip install cybro==1.0.0b1`.

### Phase 3: Direct mode in the integration (ha-hiq)

- [x] **T8a (S) Minimum HA 2026.10.** `hacs.json` `homeassistant: 2026.10.0`,
  `requirements.txt` `homeassistant==2026.10.x`, matching
  `pytest-homeassistant-custom-component` in `requirements_test.txt`.
  `via_device_id` always exists from 2026.8, so the `via_device` fallback in
  `coordinator.via_device_info` can go.
  *Done when:* `scripts/test` + `scripts/lint` green on 2026.10.
- [x] **T9 (S) Migration v2 → v3.** Add `connection: scgi`, unique_id `c{nad}`.
  *Done when:* migration tests for v1 → v3 and v2 → v3 pass, including two
  entries with the same NAD on different servers (second one keeps its old
  unique_id).
- [x] **T10 (M) Shared transport + coordinator switch.** Transport lifecycle in
  `__init__.py`, 8442 → :0 fallback + repair issue, coordinator picks the
  backend.
  *Done when:* all existing entity tests pass in both modes. Parametrize
  `fake_controller` fixtures: SCGI mock and `FakeAbusController`.
  *Done (2026-10-25):* `transport.py` (shared socket, 8442 → any port +
  repair issue `port_in_use`), coordinator picks `CybroDirect`, scan interval
  5 s. Deviation: the entity tests were not parametrized over both modes
  (the two fakes have different APIs). `tests/test_direct.py` covers setup,
  value formatting, writes, broadcast locate, timeout/unavailable, setup
  retry, one socket for all entries, and the busy port; the entity logic
  above `request()` is the same in both modes.
- [x] **T11 (M) Config flow rewrite.** `ConfigFlow` + menu (direct/scgi),
  direct step (NAD, optional IP/password, validation via locate + status),
  reconfigure step. Options flow unchanged.
  *Done when:* config flow tests cover direct OK, NAD not found, password
  denied, no program, already configured, and reconfigure scgi → direct (same
  entities).
- [x] **T12 (S) Strings + translations** (en/de) for new steps, errors and repair.
  Consistency tests stay green.

**Checkpoint 3:** `scripts/test` + `scripts/lint` green. `scripts/develop`
with a real controller in direct mode, add-on stopped: all entities available,
writes work, reprogramming the controller reloads the ALC.
*HAOS (2026-10-25), c10000 direct:* polling every 5 s works. After a new
program was sent from CyPro, one poll took 0.368 s (ALC download, other
polls < 0.02 s) and all polls succeeded, no restart. Writes: an automation
set blind `bc00_blinds_position_01` to 30 %, 80 % and open (setpoints 70,
20, 0); the position followed each one within ~35 s, no errors.
**Checkpoint 3 passed.**

### Phase 4: Discovery (ha-hiq, scope set by Phase 0, see docs/abus-notes.md)

- [x] **T13 (M) Active scan + discovery flow.** `discovery.py`: broadcast
  READ_STATUS to NAD 0 at start and every 15 min. Unknown `from_nad` →
  `integration_discovery` flow (deduplicated, ignores configured NADs and
  entries the user ignored). The confirm step shows NAD + IP and checks
  READ_STATUS first (controller in run state); the A-bus password is an
  optional field. **Only HIQ controllers are offered:** before creating the
  flow, the ALC is downloaded (~0.3 s) and `program_id` is read: HIQ
  controllers have `program_id = 3`. No `program_id` in the ALC, or another
  value → skipped silently (can still be added manually). The HIQ program also
  sets `version_major`, `version_minor`, `version_release` (e.g. 6.1.1); the
  confirm step shows it.
  *Done when (filter):* fake controllers with `program_id` 3, 5 and none →
  only the first one gets a flow.
  If the NAD belongs to an entry in **SCGI** mode, the flow offers a switch
  instead: the confirm step "Switch c{nad} to direct connection?" changes that
  entry's options to `connection: direct` (+ IP) and reloads it. Entities and
  custom sensors/selects stay. If the user ignores the flow, it isn't offered
  again for that NAD.
  *Done when:* a fake controller sending a push or broadcast creates exactly one
  discovered flow. Confirming it creates a direct entry. A configured direct NAD
  whose IP changed gets its IP updated. A NAD configured in SCGI mode gets the
  switch offer; accepting keeps all entity IDs.
  *Done (2026-10-25):* `discovery.py` scans after HA started and every
  15 min, `config_flow.py` has `integration_discovery` → `discovery_confirm`
  (NAD, IP, version; optional password) or `discovery_switch` (SCGI entry,
  reason `switched`). `tests/test_discovery.py` covers the done-when items
  above. Decisions and deviations:
  - **A fresh install is only found through DHCP (T15).** HA loads a custom
    integration only once it has an entry, so the scan only finds
    *more* controllers.
  - Discovered entries store **no static IP**: `CybroDirect` finds the
    controller by broadcast and relearns the IP after a timeout. The scan
    only updates entries with a static IP that changed.
  - The scan uses the shared socket if a direct entry has it open, else a
    temporary socket on any port. Opening 8442 itself would raise the
    `port_in_use` repair for SCGI-only users who run the add-on.
  - The switch flow has the unique ID `c{nad}_switch`, so ignoring it
    doesn't clash with the SCGI entry's `c{nad}`.
  - The HIQ check (ALC + `program_id`) runs once per NAD and HA run. A
    stopped controller or a read error is checked again on the next scan.
  - Fixed on the way: the services crashed with `KeyError` once an ignored
    entry existed (`_get_tag_list` now skips ignored entries).
- [x] **T13a (S) Repair for apps on the A-bus port** (from the HAOS test,
  see notes "Home Assistant OS test"). The port is left to running apps
  that declare UDP 8442; the repair stops them, turns off their start on
  boot and reconnects the direct entries. Busy port logged once per run.
- [x] **T14 (S) Passive listener.** Socket frames (to_nad 0 + ACK) from a
  configured NAD with a new IP → update the entry. Unknown NADs are ignored
  (no flow). REQ frames are ignored. Only works while bound to 8442.
  Also retry binding 8442 on each scan while the fallback port is used
  (eg: after the app was stopped by hand), so a reload isn't needed.
  *Done (2026-10-25):* `listener.py` handles frames to NAD 0 with ACK
  (socket, push, broadcast). An entry with static IP gets the new IP (also
  one stuck in setup retry), an entry without static IP uses it right away.
  The scan uses the same update. `transport.async_retry_port` runs before
  each scan: it reconnects the direct entries on 8442 once the port is free
  and no app declares it. HAOS: after the Edge Toolkit was stopped by
  hand, the next scan took 8442 and the repair was gone (no reload). With
  a socket added to c10000 (every 10 s), the debug log shows
  `c10000 sent a socket from 192.168.10.218`. A changed IP isn't tested
  live.
  *Done when:* a socket frame from an unknown NAD creates no flow, one from a
  configured NAD with a new IP updates `CONF_IP`.
- [x] **T15 (S) DHCP discovery.** `manifest.json` matcher `00CB00*` +
  `async_step_dhcp` → broadcast scan, take the answer whose source IP matches
  → same confirm step.
  *Done (2026-10-25):* the scan and the DHCP step share
  `discovery.async_discovery_data` (switch offer for an scgi entry, HIQ
  check otherwise). A direct entry gets the new IP (`already_configured`),
  no answer from that IP or no running HIQ program aborts silently
  (`not_hiq`). The HIQ check isn't cached for DHCP (the integration may
  not be loaded yet).
  HAOS: not matched live yet. The DHCP watcher's startup scan saw only 2
  hosts (no controller); its next network scan is hourly, DHCP requests
  only come from controllers that use DHCP.

**Checkpoint 4:** a new controller on the LAN appears in "Discovered" without
user action (at least through one of the three ways).

### Phase 5: Docs and release

- [ ] **T16 (S) README + docs/abus-notes.md:** direct mode, network
  requirements, Docker host networking, port 8442 conflict, discovery, when to
  still use SCGI mode (remote/NAT).
- [ ] **T17 (S) Release:** python-cybro 1.0.0 final → `manifest.json` pin →
  ha-hiq 0.7.0. Attribution for the ported Edge Toolkit code in the
  python-cybro README/NOTICE.

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Devices that send sockets but don't answer requests (test device c13049898) | Offered but can't be set up | Only the active scan and DHCP create flows. The passive listener only updates IPs of configured entries |
| Port 8442 already used on the HA host (SCGI add-on) | Passive discovery off | :0 fallback (polling works) + repair issue telling the user to stop the add-on |
| HA in Docker without host networking / VLANs | Broadcasts don't arrive | Optional static IP per entry. Documented |
| Devcontainer on Docker Desktop (bridge + NAT) | No broadcasts to/from the LAN. UDP 8442 is published (`runArgs`), but the forwarded frames carry the gateway IP, not the controller's | Hardware spike runs natively on the host. In the devcontainer, live tests of direct mode use `--ip` / a static IP. Discovery is verified on a real HA install (HAOS or Linux with host networking) |
| SCGI server and HA polling the same controller | Response mix-ups | Different source NAD (1010) + transaction id matching |
| Password = constant transaction id | Weaker matching of responses | One request in flight per controller (lock). Match on the NAD pair too |
| Large ALC (312 kB text, 15k variables) | Parsing time at start | Download measured at 0.3 s (S6). Parse in an executor, keep in memory |
| Behaviour differences vs SCGI (formatting of REAL, error codes) | Wrong entity states | T5 live comparison + `CybroDirect` must pass the existing model tests |
| Unzip / large ALC parsing blocks the event loop | HA warnings | Executor for unzip and parsing |
| Breaking change in python-cybro | Other users of the lib | New major version. `Cybro` API kept unchanged, `CybroDirect` is added |

## 7. Open questions

None at the moment. Answered 2026-10-25: source NAD 1010, offer a switch for
SCGI entries, minimum HA 2026.10 (see §1).


## 8. Later (not in this plan)

- Socket and push events → instant entity updates (`local_push`). Requires
  socket definitions per controller (as in `[ETH] socket = …`) and a push ACK
  service.
- Remote controllers through push/NAT in direct mode.
