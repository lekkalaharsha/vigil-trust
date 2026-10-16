"""Transport abstraction: the edge queue drainer calls submit_batch() and
gets back which event_hashes the backend actually accepted/rejected, plus
the new acceptance checkpoint if one was issued. Both HTTPS and MQTT
transports implement this same contract so edge/main.py is transport-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SubmitResult:
    accepted_event_hashes: list[str]
    rejected: dict[str, str]  # event_hash -> reason code
    new_checkpoint_digest: str | None


class TransportError(RuntimeError):
    """Raised when the batch could not be delivered at all (network down).
    This is different from the backend reachably rejecting records."""


class Transport(ABC):
    @abstractmethod
    def submit_batch(self, gateway_id: str, cose_messages: list[bytes], batch_commitment_cbor: bytes) -> SubmitResult:
        ...

    def close(self) -> None:  # pragma: no cover - optional
        return None
