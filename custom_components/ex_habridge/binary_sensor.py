"""Binary sensor platform for EX-CommandStation DCC sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import callback

from .const import DOMAIN, SIGNAL_DATA_PUSHED
from .entity import EXCSEntity
from .sensor_dcc import EXCSSensor

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .excs_client import EXCSClient


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the EX-CommandStation binary sensor platform."""
    client: EXCSClient = hass.data[DOMAIN][entry.entry_id]["client"]
    if client.sensors:
        async_add_entities(
            DccSensorBinaryEntity(client, sensor) for sensor in client.sensors
        )


class DccSensorBinaryEntity(EXCSEntity, BinarySensorEntity):
    """Binary sensor entity representing a DCC input sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, client: EXCSClient, sensor: EXCSSensor) -> None:
        """Initialize the DCC sensor entity."""
        super().__init__(client)
        self._sensor = sensor
        self._attr_name = sensor.description
        self._attr_unique_id = f"{client.entry_id}_sensor_{sensor.id}"
        self._attr_extra_state_attributes = {
            "dcc_id": sensor.id,
            "vpin": sensor.vpin,
            "pullup": sensor.pullup,
        }

    @property
    def is_on(self) -> bool:
        """Return True when the sensor is active."""
        return self._sensor.active

    @callback
    def _handle_push(self, message: str) -> None:
        """Handle a push message from the EX-CommandStation."""
        if not self._sensor.matches_push(message):
            return
        self._sensor.active = message[0] == "Q"
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register push callback once added to HA."""
        await super().async_added_to_hass()
        self._unsub_callbacks.append(
            self._client.register_signal_handler(SIGNAL_DATA_PUSHED, self._handle_push)
        )
