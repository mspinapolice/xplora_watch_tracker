"""Config flow for Xplora Watch Tracker."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import XploraApiClient, XploraAuthError
from .const import (
    CONF_EMAIL,
    CONF_ENDPOINT,
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEZONE,
    CONF_WATCHES,
    DEFAULT_API_KEY,
    DEFAULT_API_SECRET,
    DEFAULT_ENDPOINT,
    DEFAULT_LANGUAGE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEZONE,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL):    str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_TIMEZONE, default=DEFAULT_TIMEZONE): str,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
    }
)


async def _validate_and_login(
    hass: HomeAssistant, data: dict[str, Any]
) -> list[dict[str, str]]:
    """Validate credentials and return discovered watches."""
    client = XploraApiClient(
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        timezone=data.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
        language=data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
    )
    try:
        watches = await client.login()
    except XploraAuthError as err:
        raise InvalidAuth(str(err)) from err
    except Exception as err:
        raise CannotConnect(str(err)) from err
    finally:
        await client.close()

    return watches


class XploraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._watches: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: credentials, timezone, language."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                watches = await _validate_and_login(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                if not watches:
                    errors["base"] = "no_watches"
                else:
                    self._user_input = user_input
                    self._watches    = watches
                    return await self.async_step_watches()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_watches(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: friendly name per watch + poll interval."""
        if user_input is not None:
            named_watches = []
            for watch in self._watches:
                wuid = watch["wuid"]
                friendly = user_input.get(f"name_{wuid}", watch["name"]).strip()
                named_watches.append({"wuid": wuid, "name": friendly})

            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            return self.async_create_entry(
                title=self._user_input[CONF_EMAIL],
                data={
                    **self._user_input,
                    CONF_WATCHES: named_watches,
                },
                options={
                    CONF_SCAN_INTERVAL: scan_interval,
                },
            )

        # One name field per watch + poll interval
        fields: dict[Any, Any] = {}
        for watch in self._watches:
            wuid = watch["wuid"]
            fields[vol.Optional(f"name_{wuid}", default=watch["name"])] = str
        fields[vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL)] = (
            vol.All(vol.Coerce(int), vol.Clamp(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL))
        )

        return self.async_show_form(
            step_id="watches",
            data_schema=vol.Schema(fields),
            description_placeholders={
                "watch_count":    str(len(self._watches)),
                "watches":        ", ".join(w["name"] for w in self._watches),
                "min_interval":   str(MIN_SCAN_INTERVAL),
                "max_interval":   str(MAX_SCAN_INTERVAL),
                "default_interval": str(DEFAULT_SCAN_INTERVAL),
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication when token expires."""
        return await self.async_step_user()

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return XploraOptionsFlow(config_entry)


class XploraOptionsFlow(config_entries.OptionsFlow):
    """Options flow — poll interval and watch renaming after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options form."""
        if user_input is not None:
            # Extract and save updated watch names back into config data
            watches = list(self._entry.data.get(CONF_WATCHES, []))
            updated_watches = []
            for watch in watches:
                wuid = watch["wuid"]
                friendly = user_input.pop(f"name_{wuid}", watch["name"]).strip()
                updated_watches.append({"wuid": wuid, "name": friendly})

            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_WATCHES: updated_watches},
            )

            endpoint = user_input.get(
                CONF_ENDPOINT,
                self._entry.options.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
            ).strip()
            api_key = user_input.get(
                CONF_API_KEY,
                self._entry.options.get(CONF_API_KEY, DEFAULT_API_KEY),
            ).strip()
            api_secret = user_input.get(
                CONF_API_SECRET,
                self._entry.options.get(CONF_API_SECRET, DEFAULT_API_SECRET),
            ).strip()

            # Save poll interval and API connection options — triggers reload
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_ENDPOINT: endpoint,
                    CONF_API_KEY: api_key,
                    CONF_API_SECRET: api_secret,
                },
            )

        current_interval = self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_endpoint = self._entry.options.get(CONF_ENDPOINT, DEFAULT_ENDPOINT)
        current_api_key = self._entry.options.get(CONF_API_KEY, DEFAULT_API_KEY)
        current_api_secret = self._entry.options.get(CONF_API_SECRET, DEFAULT_API_SECRET)
        watches = self._entry.data.get(CONF_WATCHES, [])

        fields: dict[Any, Any] = {
            vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                vol.Coerce(int),
                vol.Clamp(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
            vol.Optional(CONF_ENDPOINT, default=current_endpoint): str,
            vol.Optional(CONF_API_KEY, default=current_api_key): str,
            vol.Optional(CONF_API_SECRET, default=current_api_secret): str,
        }
        for watch in watches:
            wuid = watch["wuid"]
            fields[vol.Optional(f"name_{wuid}", default=watch["name"])] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            description_placeholders={
                "min_interval": str(MIN_SCAN_INTERVAL),
                "max_interval": str(MAX_SCAN_INTERVAL),
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate connection failure."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid credentials."""
