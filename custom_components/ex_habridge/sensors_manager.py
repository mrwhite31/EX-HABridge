"""Manager for interacting with EX-CommandStation DCC sensors."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from .const import LOGGER, SIGNAL_DATA_PUSHED
from .excs_exceptions import EXCSConnectionError, EXCSError, EXCSInvalidResponseError
from .sensor_dcc import CMD_LIST_SENSORS, EXCSSensor

if TYPE_CHECKING:
    from .excs_base import EXCSBaseClient

# How long to wait for responses before considering the list complete
_COLLECTION_WINDOW = 1.0


class EXCSSensorsManager:
    """Manager for EX-CommandStation DCC sensors."""

    def __init__(self, client: EXCSBaseClient) -> None:
        """Initialize the sensors manager."""
        self.client = client
        self.sensors: list[EXCSSensor] = []

    async def _collect_responses(
        self, command: str, predicate: Callable[[str], bool]
    ) -> list[str]:
        """Send command and collect matching push messages within the collection window."""
        collected: list[str] = []

        def _handler(message: str) -> None:
            if predicate(message):
                collected.append(message)

        unsub = self.client.register_signal_handler(SIGNAL_DATA_PUSHED, _handler)
        try:
            await self.client.send_command(command)
            await asyncio.sleep(_COLLECTION_WINDOW)
        except EXCSError as err:
            LOGGER.warning("Error sending <%s>: %s", command, err)
        finally:
            unsub()
        return collected

    async def get_sensors(self) -> list[EXCSSensor]:
        """Discover DCC sensors and fetch their current state.

        Phase 1 — <S>: Collect "Q id vpin pullup" responses to build the sensor list.
        Phase 2 — <Q>: Collect "Q id" / "q id" push messages to set the initial state.
        """
        if not self.client.connected:
            raise EXCSConnectionError("Not connected to EX-CommandStation")

        # Phase 1: discover sensors via <S>
        LOGGER.debug("Discovering DCC sensors via <S>")
        self.sensors.clear()

        for message in await self._collect_responses(
            CMD_LIST_SENSORS,
            lambda msg: msg.startswith("Q ") and len(msg.split()) == 4,
        ):
            try:
                sensor = EXCSSensor.from_list_response(message)
                self.sensors.append(sensor)
                LOGGER.debug("Found sensor: %s", sensor)
            except EXCSInvalidResponseError as err:
                LOGGER.warning("Could not parse sensor definition '%s': %s", message, err)

        if not self.sensors:
            LOGGER.debug("No DCC sensors found")
            return self.sensors

        LOGGER.debug("Discovered %d DCC sensor(s)", len(self.sensors))

        # Phase 2: fetch current states via <Q>
        LOGGER.debug("Fetching initial sensor states via <Q>")
        sensor_map = {s.id: s for s in self.sensors}

        for message in await self._collect_responses(
            "Q",
            lambda msg: len(msg.split()) == 2 and msg[0] in ("Q", "q"),
        ):
            try:
                sensor_id, active = EXCSSensor.parse_push(message)
                if sensor_id in sensor_map:
                    sensor_map[sensor_id].active = active
                    LOGGER.debug("Initial state sensor %d: %s", sensor_id, active)
            except EXCSInvalidResponseError as err:
                LOGGER.warning("Could not parse sensor state '%s': %s", message, err)

        return self.sensors
