# Plan: HIQ socket 1 for directly connected controllers (cybro 1.1.0)

Follows up §8 of [standalone-plan.md](standalone-plan.md) ("Socket and push
events → instant entity updates").

## 1. What cybro 1.1.0 adds

Only `CybroDirect` (A-bus/UDP) changes. The scgi client `Cybro` is unchanged.

| API | Used here |
|---|---|
| `CybroDirect.add_socket(def)` | Yes. Decodes frames of this socket id **from this NAD**, writes the values into `device.vars` |
| `CybroDirect.on_socket(cb)` | Yes. `cb(SocketMessage(nad, socket_id, values, addr))` runs in the datagram handler (must not block) and returns an unsubscribe |
| `CybroDirect.disconnect()` | Yes. Removes the handler from the shared transport |
| `send_socket` / `send_socket_values` | No (HA doesn't send to the HIQ sync socket) |

Limits from the library:

- Sockets only arrive while the transport is bound to UDP **8442**. If
  `transport.py` falls back to port 0 because of a port conflict, no sockets
  arrive.
- Frames before the first `update()` (no ALC yet) are dropped, and sockets can
  be missed, so polling stays.

The version bump is done (`manifest.json`, `requirements_test.txt`).
`scripts/test` passes with 384 passed and 11 skipped. `scripts/lint` is clean.
No code changes were needed.

## 2. Socket 1 in the HIQ program (MC-IQ v3.20)

Source: [MC-IQ-v320.cyp](https://cybrotech.com/wp-content/uploads/2024/05/MC-IQ-v320.cyp),
`[Socket00]` "HIQ-to-HIQ sync", and the ALC of c10000 (an HIQ controller).

The variables and their types:

```
socket_req: bit · socket_from, socket_to: long ·
socket_command, socket_argument_0..3: int
```

As a cybro definition (bits; ints; longs). The body is 1 + 5×2 + 2×4 = 19 bytes:

```
1; socket_req; socket_command, socket_argument_0, socket_argument_1, socket_argument_2, socket_argument_3; socket_from, socket_to
```

Every message is a broadcast: `socket_from` = the sender's NAD and
`socket_to` = 0.

| `socket_command` | Meaning | arg0 | arg1 |
|---|---|---|---|
| 0 | Input event | input number | 0 short press, 1 short release, 2 long press, 3 long release |
| 1 | Scene sync enable | scene 0..31 | 1 enable, 0 disable |
| 2 | Scene request | scene | 1 scene, 0 inverse |
| 3 | Scene memory request | scene | — |
| 4 | Scene status | scene | status |
| 5 | Presence indicator | 0/1 | — |

- **Input numbers:** 0..79 = `lc00..lc07_ix00..ix09` (`lcNN` = n // 10,
  `ixNN` = n % 10), and 100..139 = `ld00..ld03_ix00..ix09` (n − 100).
- **Long press:** an input that is held for 1 s or more.
- **Long release:** the release after a long press.

## 3. Objective

Users of a direct connection get HIQ button events and faster scene and
presence states, without any setup:

- **Button events:** every LC/LD button input becomes an HA `event` entity
  with `short_press`, `short_release`, `long_press` and `long_release`.
  Automations trigger on it like any other event entity. This is the "read by
  event" from the blueprint.
- **Faster updates:** every socket 1 message (all commands) triggers a
  refresh 1 s later, instead of waiting up to 5 s. Messages within that
  second share one refresh (decided 2026-10-26).

Not in scope:

- Sockets for scgi entries (they don't reach HA).
- User-defined sockets, sending sockets, and push frames.
- Changing `iot_class`.

## 4. Design decisions

1. **Socket 1 is set up automatically** after the first refresh of a direct
   entry, if all nine socket 1 variables are in the controller's ALC (the HIQ
   program). Controllers with another program never get it, so another socket
   1 layout can't be decoded wrongly. A constant `HIQ_SOCKET` holds the
   definition. There is no option and no UI.
2. **Message handling** is done in `HiqDataUpdateCoordinator._socket_received`,
   a `@callback`:
   - Command 0 calls the event entity of that input through a
     registry in the coordinator, `{input_number: callback}`. This only
     happens when `socket_from` is the sender. `socket_req` is ignored: it only
     makes the PLC send the socket, and a receive always happens.
   - Every message schedules a refresh on its own `Debouncer` (cooldown 1 s,
     `immediate=False`). The coordinator's request debouncer for writes stays
     unchanged.
   - It does **not** call `async_set_updated_data()`, because that resets the
     poll timer.
3. **A new `event` platform** (`event.py`):
   - It creates one entity per `lcNN_ixNN` / `ldNN_ixNN` input in the ALC of a
     module that works (`is_general_error_ok`, like the lights).
   - It only exists for direct entries with socket 1.
   - The device class is `button`. The translation key is `button_input` with
     the name "Input ixZZ". The unique id is `cNAD.lcYY_ixZZ_event`. Each module
     gets one device, `Inputs cNAD.lcYY`, instead of one device per input,
     which would mean up to 120 devices.
   - **Disabled by default** (decided 2026-10-26).
4. **`coordinator.async_shutdown()` calls `cybro.disconnect()`.** HA runs it
   when the entry is unloaded. Without it, an entry that reloads leaves its
   handler, and with it the old coordinator, on the shared transport.
   `Cybro.disconnect()` doesn't close HA's shared aiohttp session, so calling it
   for every entry is safe.
5. **`listener.py` stays as it is.** It still uses all socket frames for IP
   tracking. Both handlers see each frame.

## 5. Tasks

- [x] **T1 (S) Version bump** to `cybro==1.1.0`. Tests and lint are green.
- [x] **T2 (M) Receive socket 1.** Add `HIQ_SOCKET` and the command constants
  in `const.py`, the setup in `coordinator.py` / `__init__.py`, the
  `disconnect()` on unload, and the delayed refresh.
  *Done when:* tests with the sender from `tests/fake_abus.py` (as in
  `test_listener.py`) and a 19-byte body show the following:
  - Messages refresh the values once, after 1 s and not before.
  - A frame from another NAD changes nothing.
  - A controller whose ALC has no socket 1 variables gets no socket.
  - After a reload, exactly one handler is left on the transport.
  - scgi entries are unchanged.
- [x] **T3 (M) Event platform.** `event.py`, the input number ↔ variable
  mapping, `Platform.EVENT`, entity translations (en/de), and the event type
  names.
  *Done when:* tests show the following:
  - Short and long press/release frames fire the right event type on the
    right entity, for LC (input 23 → `lc02_ix03`) and LD (input 131 →
    `ld03_ix01`).
  - There are no entities for a module with a general error, or for scgi
    entries.
  - The entities are disabled by default.
  - `tests/test_consistency.py` passes.
- [x] **T4 (S) Docs.** README: button events, direct connection only, and port
  8442 must be bound (link to the existing troubleshooting section), with an
  automation example. Add the entities to `docs/entities.md`. Add the
  socket 1 layout to `docs/abus-notes.md`.
- [ ] **Checkpoint:** run `scripts/test` and `scripts/lint`, then a live test
  on c10000 (the HIQ program):
  - Short and long presses on an LC/LD input show the right event.
  - A scene switched on a wall button shows up in HA at once.
  - The body length (19 bytes) is confirmed, because no socket 1 frame has
    been captured yet.

## 6. Notes

1. **Scene sync sockets from other controllers** arrive with the sender's NAD.
   cybro only passes on frames of the entry's own NAD. Scene states of other
   controllers update through their own entry. This is fine as long as every
   HIQ controller is set up.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Port 8442 is taken by the scgi/Edge Toolkit app: no events | The README explains it, and the port repair issue already exists |
| A missed socket means a lost button event | The library can't detect lost frames. This is documented. States still come from polling |
| A different socket 1 layout in other HIQ program versions | The socket is only set up when all nine variables are in the ALC. cybro checks the types and the length and drops frames that don't fit |
