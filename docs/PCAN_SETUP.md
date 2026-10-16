# PCAN Setup

STATUS: this document describes the intended, documented procedure.
**It has not been executed in this environment** because no PEAK PCAN-USB
adapter or driver was available. `edge/acquisition/pcan.py` is implemented
against the `python-can` `pcan` interface and will raise a clear
`PcanUnavailableError` (not a raw traceback) if the driver/adapter is
missing -- confirmed by `tests/hardware/test_pcan_hardware.py`.

## Prerequisites

1. Install the PEAK PCAN driver for your OS (Windows: PCAN-Basic /
   PCAN-View from peak-system.com; Linux: `peak-linux-driver` or the
   in-kernel `peak_usb` module).
2. Confirm `python-can` is installed (it's in `pyproject.toml`).
3. Connect the PCAN-USB adapter.

## Phase A: validate hardware independently (PCAN-View)

Before trusting VIGIL-TRUST's own output, confirm with PEAK's own tool:

1. Open PCAN-View.
2. Select the correct channel/bitrate matching `.env`'s `CAN_CHANNEL` /
   `CAN_BITRATE`.
3. Confirm frames are received from your authorized bench/simulator source
   (not a real vehicle).
4. Confirm you do **not** need to transmit anything for VIGIL-TRUST's use
   case -- this project only ever receives.

## Phase B: validate VIGIL-TRUST's PCAN mode

```bash
# .env or environment variables:
export CAN_INTERFACE=pcan
export CAN_CHANNEL=PCAN_USBBUS1
export CAN_BITRATE=500000
export CAN_FD=false
export CAN_LISTEN_ONLY=true

.venv/Scripts/python.exe -m edge.main --mode pcan
```

Confirm, by comparing against the PCAN-View capture from Phase A:

- [ ] Frame timestamps are reasonable (not all zero/identical).
- [ ] CAN IDs match what PCAN-View shows.
- [ ] DLC/data bytes match.
- [ ] Frame rate roughly matches the bus load.
- [ ] `edge/main.py` logs show `drain: attempted=N accepted=N rejected=0`
      for the backend ingestion (confirms signing + queue + transport are
      not losing frames at this load).
- [ ] Record a trace (e.g. via PCAN-View's own logging) for use as a
      regression fixture under `data/`.

## Linux SocketCAN (including PEAK-over-SocketCAN)

```bash
sudo ip link set can0 up type can bitrate 500000
export CAN_INTERFACE=socketcan
export CAN_CHANNEL=can0
.venv/bin/python -m edge.main --mode socketcan
```

## If the driver/adapter is missing

`edge/acquisition/pcan.py::PcanSource.frames()` raises
`PcanUnavailableError` with a message pointing back to this file instead of
a raw `OSError`/traceback -- this is itself tested
(`tests/hardware/test_pcan_hardware.py::test_pcan_source_raises_clear_error_without_hardware`,
which passes in this environment precisely because no adapter is present).
