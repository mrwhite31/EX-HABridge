"""DCC sensor class for EX-CommandStation."""

from __future__ import annotations

import re
from typing import Final

from .excs_exceptions import EXCSInvalidResponseError

# <S> lists all defined sensors; responses: "Q id vpin pullup"
CMD_LIST_SENSORS: Final[str] = "S"

# "Q id vpin pullup" — sensor definition response
_RESP_LIST_REGEX: Final[re.Pattern] = re.compile(
    r"Q\s+(?P<id>\d+)\s+(?P<vpin>\d+)\s+(?P<pullup>[01])"
)

# "Q id" (active) or "q id" (inactive) — push state change
_RESP_PUSH_REGEX: Final[re.Pattern] = re.compile(r"[Qq]\s+(?P<id>\d+)$")


class EXCSSensor:
    """Representation of a DCC sensor in the EX-CommandStation."""

    def __init__(self, sensor_id: int, vpin: int = 0, pullup: bool = False) -> None:
        """Initialize the sensor."""
        self.id = sensor_id
        self.vpin = vpin
        self.pullup = pullup  # True = pull-up resistor (ACTIVE=LOW), False = ACTIVE=HIGH
        self.active: bool = False
        self.description: str = f"Sensor {sensor_id}"

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<EXCSSensor id={self.id} vpin={self.vpin} pullup={self.pullup} active={self.active}>"

    def matches_push(self, message: str) -> bool:
        """Return True if this push message belongs to this sensor."""
        if not message or message[0] not in ("Q", "q"):
            return False
        parts = message.split()
        return len(parts) == 2 and parts[1] == str(self.id)

    @classmethod
    def parse_push(cls, message: str) -> tuple[int, bool]:
        """Parse a push message and return (id, active).

        Uppercase Q = active, lowercase q = inactive.
        """
        match = _RESP_PUSH_REGEX.match(message)
        if not match:
            raise EXCSInvalidResponseError(f"Invalid sensor push message: {message}")
        return int(match.group("id")), message[0] == "Q"

    @classmethod
    def from_list_response(cls, message: str) -> EXCSSensor:
        """Create a sensor instance from a <S> list response line."""
        match = _RESP_LIST_REGEX.match(message)
        if not match:
            raise EXCSInvalidResponseError(f"Invalid sensor list response: {message}")
        return cls(
            sensor_id=int(match.group("id")),
            vpin=int(match.group("vpin")),
            pullup=match.group("pullup") == "1",
        )
