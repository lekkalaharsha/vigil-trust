# Third-Party Notices

Original code in this repository is Apache-2.0 (see LICENSE). This project
depends on the following third-party packages, pinned in `pyproject.toml`.
Versions/licenses below were captured directly from the installed packages'
metadata on 2026-10-16 (`pip show <package>`); re-verify before any
redistribution decision, since a package's declared license can change
between releases.

| Package | Version | License | Role |
|---|---|---|---|
| fastapi | 0.115.6 | MIT | Backend REST API framework |
| uvicorn[standard] | 0.34.0 | BSD-3-Clause | ASGI server |
| pydantic | 2.10.4 | MIT | Request/response validation |
| cryptography | 44.0.0 | Apache-2.0 OR BSD-3-Clause | ECDSA signing/verification, X.509 demo PKI |
| cbor2 | 5.6.5 | MIT | Canonical CBOR encoding |
| paho-mqtt | 2.1.0 | EPL-2.0 OR BSD-3-Clause | MQTT 5 transport |
| python-can | 4.5.0 | **LGPL-3.0** | PCAN / SocketCAN acquisition |
| cantools | 39.4.6 | MIT | Optional DBC decoding |
| httpx | 0.28.1 (dev/test only) | BSD-3-Clause | HTTPS transport client, test harness |
| pytest | 8.3.4 (dev only) | MIT | Test runner |

## LGPL-3.0 notice: python-can

`python-can` is licensed LGPL-3.0. This project uses it as an unmodified
library dependency (dynamic import, no vendored/modified copy of its
source), which keeps this project's own code under Apache-2.0 without
LGPL "work as a whole" obligations, consistent with LGPL-3.0 section 4-5
library-linkage provisions. If python-can is ever vendored, patched, or
statically bundled rather than installed as a normal dependency, this
notice must be revisited and LGPL section 4/5 obligations (e.g. providing
modified source, allowing relinking) re-evaluated.

Per CLAUDE_CODE_ONE_SHOT_VIGIL_TRUST.md rule 9 and the hackathon
CLAUDE.md's licensing-awareness guidance: do not add further
copyleft/AGPL dependencies to this project without revisiting this file,
and do not silently swap python-can for another CAN library without
re-running the acquisition tests.

## Eclipse Mosquitto (docker-compose.yml, not vendored)

Eclipse Mosquitto is referenced as a container image (`eclipse-mosquitto:2`)
for the optional MQTT transport demo, not built into this repository.
Mosquitto itself is EPL-2.0 OR EDL-1.0 licensed; see
https://mosquitto.org/license/ for its own terms.

## Regenerating this inventory

```bash
.venv/Scripts/python.exe -m pip show <package-name>
```

No automated SBOM tool (e.g. `pip-licenses`, `cyclonedx-py`) was available
to run in this environment; this table was produced manually from `pip
show` output. If an SBOM tool is available in your environment, prefer
regenerating this file with it for anything beyond the hackathon demo.
