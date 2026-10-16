# Arduino UNO Q Setup

STATUS: mixed -- see the table in `firmware/uno_q_mcu/README.md` for the
authoritative per-module breakdown. No UNO Q board was available in this
environment, so nothing here has been flashed or run on real hardware, but
the Bridge wire protocol itself IS implemented and cross-verified between
the Python (Linux) side and the C (MCU) side (see
`firmware/uno_q_mcu/tests/README.md`). This document describes the
remaining bring-up procedure for what still requires real hardware.

## What exists today

- `edge/acquisition/unoq_protocol.py` -- Bridge wire framing (CRC16,
  CAN/health frame encode-decode, resyncing reassembler). **Implemented
  and unit-tested** (`tests/unit/test_unoq_protocol.py`), no hardware
  needed -- this is pure byte-level parsing logic.
- `edge/acquisition/unoq.py::UnoQBridgeSource` -- opens a serial port and
  feeds bytes through the protocol module above into `CanFrame` objects.
  **Implemented**, but its serial I/O has **not** been exercised against a
  real board; it raises a clear `UnoQBridgeUnavailableError` (not a raw
  traceback) when no device is present, which is what happens in this
  environment (`tests/hardware/test_unoq_hardware.py`).
- `firmware/uno_q_mcu/bridge_protocol/`, `capture_counter/`, `health/` --
  **implemented and host-verified** (compiled and run with gcc, no
  hardware needed; byte-for-byte cross-checked against the Python side --
  see `firmware/uno_q_mcu/tests/README.md`).
- `firmware/uno_q_mcu/signer_interface/` -- interface implemented;
  `unoq_secure_signer.c` is a stub that compiles but every operation
  returns failure (not implemented).
- `firmware/uno_q_mcu/can_rx/` and `vigil_uno_q_firmware.ino` -- written
  against the Arduino_CAN API as the best available assumption, **not**
  compiled under a real Arduino Core toolchain or run on hardware.

## Intended bring-up procedure (not yet executed)

### Linux (QRB2210) side

1. Flash/boot the UNO Q's Debian image per
   https://docs.arduino.cc/tutorials/uno-q/user-manual/.
2. Confirm Wi-Fi connectivity and that the edge Python environment
   (`pyproject.toml` deps) installs and runs on the board's architecture.
3. Confirm the edge service can reach the backend over the intended
   network path (Wi-Fi 5, per the hackathon's own platform note).
4. Confirm the durable SQLite queue persists across an application
   restart on the board's filesystem (same test as
   `tests/unit/test_queue_persistence.py`, run manually on-device).

### MCU (STM32U585) side

1. Connect an external CAN transceiver with appropriate protection
   (isolation/termination) to an **isolated CAN bench only** -- never an
   operating vehicle network with an unvalidated prototype.
2. Flash the firmware skeleton in `firmware/uno_q_mcu/` (receive-only).
3. Validate received frame timestamps/IDs/payloads against a PCAN
   reference capture (see docs/PCAN_SETUP.md) on the same bench.
4. Validate the Bridge protocol framing (see
   `firmware/uno_q_mcu/README.md#bridge-wire-protocol`) end-to-end into
   the Linux-side `UnoQBridgeSource`.

### Secure signer stretch goal

Attempt to move long-term signing operations into the STM32U585's
TrustZone/secure domain using supported Zephyr/Arduino Core APIs. If this
cannot be completed in the time available, state plainly:

> Hardware-backed signer: architecture defined; implementation/hardware
> validation pending.

Do not claim hardware-backed signing is active unless
`edge/trust/identity.py` is actually backed by a hardware signer and that
has been tested on the board.

## Definition of done for this component (not yet met)

- [ ] `UnoQBridgeSource.frames()` returns real frames from the board.
- [ ] Frames cross-validated against a PCAN reference capture on the same
      bench.
- [ ] Queue persistence verified on-device across a restart.
- [ ] Either a working hardware-backed signer, or an explicit
      `HARDWARE_PENDING` statement with no partial/fake implementation.
