"""Device tracker platform for Xplora Watch Tracker."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
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
    """Set up device tracker entities from a config entry."""
    coordinator: XploraCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        XploraDeviceTracker(coordinator, watch) for watch in coordinator.watches
    )


class XploraDeviceTracker(CoordinatorEntity[XploraCoordinator], TrackerEntity):
    """Tracks a single Xplora watch on the HA map."""

    _attr_has_entity_name = True
    _attr_name = None  # device name is the entity name

    def __init__(
        self,
        coordinator: XploraCoordinator,
        watch: dict[str, str],
    ) -> None:
        super().__init__(coordinator)
        self._wuid = watch["wuid"]
        self._watch_name = watch["name"]
        self._attr_unique_id = f"{self._wuid}_tracker"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._wuid)},
            name=self._watch_name,
            manufacturer="Xplora",
            model="Kids Smartwatch",
        )

    def _locate(self) -> dict[str, Any]:
        """Return current location data or empty dict."""
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get(self._wuid, {})

    @property
    def latitude(self) -> float | None:
        lat = self._locate().get("lat")
        try:
            return float(lat) if lat else None
        except (ValueError, TypeError):
            return None

    @property
    def longitude(self) -> float | None:
        lng = self._locate().get("lng")
        try:
            return float(lng) if lng else None
        except (ValueError, TypeError):
            return None

    @property
    def source_type(self) -> SourceType:
        locate_type = self._locate().get("locateType", "")
        # GPS = GPS fix, WIFI = wifi positioning, LBS = cell tower
        if locate_type == "GPS":
            return SourceType.GPS
        return SourceType.ROUTER

    @property
    def location_accuracy(self) -> int:
        """Return accuracy radius in metres."""
        return int(self._locate().get("rad", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        locate = self._locate()
        attrs: dict[str, Any] = {}

        locate_type = locate.get("locateType")
        if locate_type:
            attrs["locate_type"] = locate_type

        tm = locate.get("tm")
        if tm:
            attrs["last_seen"] = tm

        city = locate.get("city")
        if city:
            attrs["city"] = city

        country = locate.get("country")
        if country:
            attrs["country"] = country

        addr = locate.get("addr")
        if addr:
            attrs["address"] = addr

        attrs["watch_id"] = self._wuid

        return attrs
