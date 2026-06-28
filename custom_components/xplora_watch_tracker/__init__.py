"""Xplora Watch Tracker integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .api import XploraApiClient, XploraAuthError
from .const import (
    CONF_EMAIL,
    CONF_ENDPOINT,
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_WATCHES,
    DEFAULT_API_KEY,
    DEFAULT_API_SECRET,
    DEFAULT_ENDPOINT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import XploraCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xplora Watch Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = XploraApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        timezone=hass.config.time_zone,
        language=hass.config.language,
        endpoint=entry.options.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
        api_key=entry.options.get(CONF_API_KEY, DEFAULT_API_KEY),
        api_secret=entry.options.get(CONF_API_SECRET, DEFAULT_API_SECRET),
    )

    try:
        discovered_watches = await client.login()
    except XploraAuthError as err:
        await client.close()
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except Exception as err:
        _LOGGER.exception("Unable to initialize Xplora integration")
        await client.close()
        raise ConfigEntryNotReady(f"Cannot connect to Xplora API: {err}") from err

    # Use watches from config (with user-set friendly names)
    watches = entry.data.get(CONF_WATCHES) or [
        {"wuid": w["wuid"], "name": w["name"]} for w in discovered_watches
    ]

    if not watches:
        _LOGGER.error("No watches found for this account")
        await client.close()
        return False

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = XploraCoordinator(hass, client, watches, scan_interval=scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when options change (poll interval, watch names)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: XploraCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.close()

    return unload_ok
