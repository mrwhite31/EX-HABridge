"""Text platform for EX-CommandStation — raw serial command input."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.text import TextEntity, TextEntityDescription, TextMode
from homeassistant.core import callback

from .const import DOMAIN, LOGGER, SIGNAL_DATA_PUSHED
from .entity import EXCSEntity
from .excs_exceptions import EXCSError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .excs_client import EXCSClient


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the EX-CommandStation text platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    client = data["client"]
    async_add_entities([CommandInputText(client)])


class CommandInputText(EXCSEntity, TextEntity):
    """Text entity for sending raw DCC-EX serial commands to the CommandStation.

    The user can type any DCC-EX command, with or without angle brackets.
    Examples:
        Q       → queries all sensors
        <Q>     → same (brackets are stripped automatically)
        s       → status
        1       → turn tracks on
        0       → turn tracks off
    """

    def __init__(self, client: EXCSClient) -> None:
        """Initialize the serial command text entity."""
        super().__init__(client)

        self.entity_description = TextEntityDescription(
            key="serial_command",
            icon="mdi:console",
        )
        self._attr_name = "Serial Command"
        self._attr_unique_id = f"{client.entry_id}_serial_command"
        self._attr_mode = TextMode.TEXT
        self._attr_native_min = 1
        self._attr_native_max = 255
        self._attr_native_value = ""
        self._last_response: str = ""

    @property
    def extra_state_attributes(self) -> dict:
        """Return the last response received from the CommandStation."""
        return {"last_response": self._last_response}

    @callback
    def _handle_push(self, message: str) -> None:
        """Store the latest push message as last_response."""
        self._last_response = f"<{message}>"
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register signal callbacks."""
        await super().async_added_to_hass()
        self._unsub_callbacks.append(
            self._client.register_signal_handler(SIGNAL_DATA_PUSHED, self._handle_push)
        )

    async def async_set_value(self, value: str) -> None:
        """Send a raw DCC-EX command to the CommandStation.

        Angle brackets are optional — both ``Q`` and ``<Q>`` are accepted.
        """
        command = value.strip()

        # Strip angle brackets if the user typed them, e.g. <Q> → Q
        if command.startswith("<") and command.endswith(">"):
            command = command[1:-1].strip()

        if not command:
            LOGGER.warning("Serial Command: empty command ignored")
            return

        LOGGER.debug("Serial Command: sending <%s>", command)
        try:
            await self._client.send_command(command)
            # Store the normalised representation as the entity value
            self._attr_native_value = f"<{command}>"
            self.async_write_ha_state()
        except EXCSError:
            LOGGER.exception("Serial Command: failed to send <%s>", command)
