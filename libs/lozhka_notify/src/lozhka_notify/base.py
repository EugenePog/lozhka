"""The one interface every channel implements."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Message:
    topic: str  # expiry_digest, pipeline_alert, new_order, ...
    body: str
    subject: str | None = None
    # Same key to the same recipient is sent once, e.g. "expiry:lot=42:days=7".
    dedupe_key: str | None = None


class Channel(Protocol):
    name: str  # "email" | "telegram"

    def send(self, recipient: str, message: Message) -> None:
        """Deliver or raise. The caller handles retries and de-duplication (ops.notification)."""
        ...
