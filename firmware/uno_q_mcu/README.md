# UNO Q MCU Firmware (STM32U585, receive-only)

STATUS: mixed, and this section is the authoritative summary -- trust it
over any older description elsewhere.

| Component | Status | Evidence |
|---|---|---|
| `bridge_protocol/` (wire framing, CRC16) | **IMPLEMENTED, HOST-VERIFIED** | Compiled & run with gcc in this environment; byte-for-byte cross-checked against the Python reference encoder. See `tests/README.md`. |
| `capture_counter/` (monotonic frame counter) | **IMPLEMENTED, HOST-VERIFIED** | Compiled & run with gcc; wraparound behavior tested. See `tests/README.md`. |
| `health/` (uptime/dropped-frame reporting) | **IMPLEMENTED, HOST-VERIFIED** (reporting logic); watchdog hardware kick is a `TODO(HARDWARE_PENDING)` | Compiled & run with gcc, including a millis()-wraparound case. See `tests/README.md`. |
| `signer_interface/` (SecureSigner contract) | Interface **IMPLEMENTED**; `unoq_secure_signer.c` stub **compiles** but every operation returns failure (**NOT_IMPLEMENTED**) | `gcc -c unoq_secure_signer.c` succeeds in this environment; no hardware crypto behind it |
| `can_rx/` (CAN peripheral receive) | **NOT HARDWARE-VALIDATED** -- written against the Arduino_CAN API as the best available assumption, not built under a real Arduino Core toolchain here | None -- requires Arduino Core + board support package this environment does not have |
| `vigil_uno_q_firmware.ino` (top-level sketch) | **NOT HARDWARE-VALIDATED** -- wires the above together, has not been compiled under the Arduino IDE/CLI | None |

No code in this directory has been flashed to or run on a real Arduino UNO
Q board -- no board was available in this environment. "Host-verified"
above means compiled and run as plain C on a development machine (gcc),
which is possible only for the hardware-independent modules. See
docs/UNO_Q_SETUP.md for the bring-up procedure the hardware-dependent
pieces still need.

## Scope

The MCU side (STM32U585, Cortex-M33, Zephyr/Arduino Core) is a **passive
CAN receive boundary only**:

- Receive CAN frames (11-bit and 29-bit IDs).
- Timestamp + monotonic counter assignment.
- Optional hardware CAN filtering.
- Frame normalization into the Bridge wire format below.
- Forward frames to the Linux (QRB2210) side over the Bridge.
- Health/watchdog reporting.

**No CAN transmit capability is in scope.** Per
CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md rule 3 and
VIGIL_TRUST_Research_and_Architecture.md section 14.3, this project never
exposes an arbitrary CAN transmit API, on the MCU or anywhere else.

## Directory structure (populated)

```text
firmware/uno_q_mcu/
├── can_rx/
│   ├── can_rx.h            -- init/poll contract (receive-only, no transmit fn exists)
│   └── can_rx.cpp           -- Arduino_CAN-based sketch, NOT hardware-validated
├── capture_counter/
│   ├── capture_counter.h
│   └── capture_counter.c    -- monotonic counter + wraparound, HOST-VERIFIED
├── signer_interface/
│   ├── signer_interface.h   -- SecureSigner vtable contract
│   ├── unoq_secure_signer.h
│   └── unoq_secure_signer.c -- stub, compiles, every op returns failure
├── bridge_protocol/
│   ├── bridge_protocol.h
│   └── bridge_protocol.c    -- framing/CRC16, HOST-VERIFIED against the Python side
├── health/
│   ├── health.h
│   └── health.c             -- uptime/dropped-count reporting, HOST-VERIFIED
├── tests/                   -- host-buildable tests + captured output, see tests/README.md
└── vigil_uno_q_firmware.ino -- top-level sketch wiring the above together
```

## Bridge wire protocol (implemented, cross-checked against the Python side)

One frame per message over the Arduino UNO Q's MCU<->Linux Bridge
mechanism (modeled here as a serial link -- see `vigil_uno_q_firmware.ino`'s
header comment for why that assumption needs hardware confirmation).
Full byte-level format: `bridge_protocol.h`'s header comment and
`edge/acquisition/unoq_protocol.py`'s module docstring (kept in sync --
if you change one, change the other and re-run
`firmware/uno_q_mcu/tests/run_host_tests.sh` plus
`tests/unit/test_unoq_protocol.py`).

In-memory MCU representation of one CAN frame before encoding
(`bridge_protocol.h::bridge_can_frame_t`):

```c
typedef struct {
    uint32_t mcu_timestamp_us;   // MCU-local monotonic timer, not wall clock
    uint32_t mcu_frame_counter;  // monotonic, wraps are detectable by the Linux side
    uint32_t can_id;             // low 29 bits used
    uint8_t  flags;              // bit0: extended id, bit1: fd
    uint8_t  dlc;                // 0-64
    uint8_t  data[64];
} bridge_can_frame_t;
```

On the wire, only `dlc` bytes of `data` are actually sent (see
`bridge_protocol.h`'s frame-format comment) -- the fixed 64-byte array
above is just the in-memory capacity.

`edge/acquisition/unoq.py::UnoQBridgeSource` is the Linux-side consumer:
it is implemented (opens a serial port, feeds bytes through the same
framing logic) but its *hardware* I/O path is not hardware-validated,
while the framing logic itself is verified identical in both languages
(see `firmware/uno_q_mcu/tests/README.md`).

## SecureSigner interface

```text
class SecureSigner:
    def sign(self, canonical_event_bytes: bytes) -> bytes: ...   # raw r||s ECDSA signature
    def public_key_der(self) -> bytes: ...
```

(`signer_interface.h` is the C vtable equivalent of this.)

- **In the current prototype, signing happens on Linux, not the MCU** --
  `edge/trust/identity.py` + `edge/trust/cose_signer.py` (a normal P-256
  keypair loaded from a PEM file). This is what the demo actually uses;
  nothing in this firmware directory signs anything today.
- `unoq_secure_signer.c` -- target: perform the ECDSA signing operation
  inside the STM32U585's TrustZone secure domain, so the long-term private
  key material never appears in Linux-side (normal-world) memory. **Not
  implemented** -- every function returns a failure code, matching
  CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md rule 6 ("no fake test results"). ST
  documents hardware-unique-key-derived secure storage, a public-key
  accelerator, and a hardware RNG on the STM32U585
  (https://www.st.com/en/microcontrollers-microprocessors/stm32u585ai.html);
  whether/how these are reachable from Zephyr's Arduino Core on this board
  needs to be verified against the actual supported API surface before any
  implementation attempt, not assumed.

## What was actually verified, and how

`firmware/uno_q_mcu/tests/run_host_tests.sh` builds and runs three test
binaries with plain `gcc` (no Arduino toolchain) against
`bridge_protocol.c`, `capture_counter.c`, and `health.c` -- the three
modules with no hardware dependency. All checks passed; captured output
and a byte-for-byte cross-check against the Python reference
implementation are in `tests/README.md`. `unoq_secure_signer.c` was also
confirmed to compile standalone (`gcc -c`).

`can_rx.cpp` and `vigil_uno_q_firmware.ino` depend on Arduino Core /
Arduino_CAN APIs this environment does not have, and so could not be
built or run here -- see docs/UNO_Q_SETUP.md for what must happen on real
hardware before those are trusted.
