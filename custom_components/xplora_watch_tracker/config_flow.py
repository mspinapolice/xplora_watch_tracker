"""Config flow for Xplora Watch Tracker."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import XploraApiClient, XploraAuthError
from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEZONE,
    CONF_WATCHES,
    DEFAULT_API_KEY,
    DEFAULT_API_SECRET,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_and_login(
    hass: HomeAssistant, data: dict[str, Any]
) -> list[dict[str, str]]:
    """Validate credentials and return discovered watches."""
    client = XploraApiClient(
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        timezone=hass.config.time_zone,
        language=hass.config.language,
    )

    try:
        return await client.login()
    except XploraAuthError as err:
        raise InvalidAuth(str(err)) from err
    except Exception as err:
        raise CannotConnect(str(err)) from err
    finally:
        await client.close()


class XploraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._watches: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

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
                    self._watches = watches
                    return await self.async_step_watches()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_watches(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: watch naming + scan interval."""
        if user_input is not None:
            named_watches: list[dict[str, str]] = []

            for watch in self._watches:
                wuid = watch["wuid"]
                name = user_input.get(f"name_{wuid}", watch["name"]).strip()
                named_watches.append({"wuid": wuid, "name": name})

            return self.async_create_entry(
                title=self._user_input[CONF_EMAIL],
                data={
                    CONF_EMAIL: self._user_input[CONF_EMAIL],
                    CONF_PASSWORD: self._user_input[CONF_PASSWORD],
                    CONF_TIMEZONE: self.hass.config.time_zone,
                    CONF_LANGUAGE: self.hass.config.language,
                    CONF_WATCHES: named_watches,
                },
                options={
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    )
                },
            )

        fields: dict[Any, Any] = {}

        for watch in self._watches:
            fields[vol.Optional(f"name_{watch['wuid']}", default=watch["name"])] = str

        fields[
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=DEFAULT_SCAN_INTERVAL,
            )
        ] = vol.All(
            vol.Coerce(int),
            vol.Clamp(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
        )

        return self.async_show_form(
            step_id="watches",
            data_schema=vol.Schema(fields),
            description_placeholders={
                "watch_count": str(len(self._watches)),
                "watches": ", ".join(w["name"] for w in self._watches),
                "min_interval": str(MIN_SCAN_INTERVAL),
                "max_interval": str(MAX_SCAN_INTERVAL),
                "default_interval": str(DEFAULT_SCAN_INTERVAL),
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Reauth flow."""
        return await self.async_step_user(entry_data)


class XploraOptionsFlow(config_entries.OptionsFlow):
    """Options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options."""
        if user_input is not None:
            watches = list(self._entry.data.get(CONF_WATCHES, []))
            updated: list[dict[str, str]] = []

            for watch in watches:
                wuid = watch["wuid"]
                updated.append(
                    {
                        "wuid": wuid,
                        "name": user_input.get(f"name_{wuid}", watch["name"]).strip(),
                    }
                )

            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_WATCHES: updated},
            )

            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_API_KEY: user_input.get(CONF_API_KEY, DEFAULT_API_KEY).strip(),
                    CONF_API_SECRET: user_input.get(
                        CONF_API_SECRET, DEFAULT_API_SECRET
                    ).strip(),
                },
            )

        fields: dict[Any, Any] = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self._entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Clamp(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
        }

        for watch in self._entry.data.get(CONF_WATCHES, []):
            fields[vol.Optional(f"name_{watch['wuid']}", default=watch["name"])] = str

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            errors={},
            description_placeholders={
                "min_interval": str(MIN_SCAN_INTERVAL),
                "max_interval": str(MAX_SCAN_INTERVAL),
            },
        )


class CannotConnect(HomeAssistantError):
    """Connection error."""


class InvalidAuth(HomeAssistantError):
    """Auth error."""
