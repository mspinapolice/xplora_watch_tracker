"""Sensor platform for Xplora Watch Tracker — battery and charging state."""
from __future__ import annotations

import logging
from typing import Any, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XploraCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: XploraCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for watch in coordinator.watches:
        entities.append(XploraBatterySensor(coordinator, watch))
        entities.append(XploraChargingSensor(coordinator, watch))

    async_add_entities(entities)


class _XploraBaseSensor(CoordinatorEntity[XploraCoordinator], SensorEntity):
    """Base class for Xplora sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XploraCoordinator,
        watch: dict[str, str],
    ) -> None:
        super().__init__(coordinator)
        self._wuid       = watch["wuid"]
        self._watch_name = watch["name"]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._wuid)},
            name=self._watch_name,
            manufacturer="Xplora",
            model="Kids Smartwatch",
        )

    def _locate(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get(self._wuid, {})


class XploraBatterySensor(_XploraBaseSensor):
    """Battery percentage sensor."""

    _attr_name              = "Battery"
    _attr_device_class      = SensorDeviceClass.BATTERY
    _attr_state_class       = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: XploraCoordinator, watch: dict[str, str]) -> None:
        super().__init__(coordinator, watch)
        self._attr_unique_id = f"{self._wuid}_battery"

    @property
    def native_value(self) -> int | None:
        val = self._locate().get("battery")
        return int(val) if val is not None else None


class XploraChargingSensor(_XploraBaseSensor):
    """Charging state sensor (Charging / Not charging)."""

    _attr_name         = "Charging"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["charging", "not_charging"]

    def __init__(self, coordinator: XploraCoordinator, watch: dict[str, str]) -> None:
        super().__init__(coordinator, watch)
        self._attr_unique_id = f"{self._wuid}_charging"

    @property
    def native_value(self) -> str | None:
        is_charging = self._locate().get("isCharging")
        if is_charging is None:
            return None
        return "charging" if is_charging else "not_charging"

    @property
    def icon(self) -> str:
        if self.native_value == "charging":
            return "mdi:battery-charging"
        return "mdi:battery"
