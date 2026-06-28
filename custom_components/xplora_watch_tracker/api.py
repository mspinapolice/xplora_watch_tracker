"""Xplora API client — standalone, no external library dependency."""

from __future__ import annotations

import hashlib
import logging
import math
from time import time
from typing import Any

import aiohttp

from .const import API_KEY, API_SECRET, ENDPOINT

_LOGGER = logging.getLogger(__name__)

# GraphQL mutations and queries
_LOGIN_MUTATION = """
mutation signInWithEmailOrPhone(
    $emailAddress: String $countryPhoneNumber: String $phoneNumber: String
    $password: String! $userLang: String! $timeZone: String! $client: ClientType!
) {
    signInWithEmailOrPhone(
        emailAddress: $emailAddress countryPhoneNumber: $countryPhoneNumber
        phoneNumber: $phoneNumber password: $password userLang: $userLang
        timeZone: $timeZone client: $client
    ) {
        token
        user {
            id
            name
            emailAddress
            children {
                approval
                flag
                ward {
                    id
                    name
                    userId
                }
            }
        }
        w360 { token secret qid }
    }
}"""

_LOCATE_QUERY = """
query WatchLastLocate($uid: String!) {
  watchLastLocate(uid: $uid) {
    tm lat lng rad
    battery isCharging
    locateType
    city country addr
    isInSafeZone safeZoneLabel
    batteryTm
  }
}"""


class XploraAuthError(Exception):
    """Raised when authentication fails."""


class XploraApiError(Exception):
    """Raised when an API query fails."""


class XploraApiClient:
    """Async Xplora API client."""

    def __init__(
        self,
        email: str,
        password: str,
        timezone: str = "America/New_York",
        language: str = "en-US",
        endpoint: str = ENDPOINT,
        api_key: str = API_KEY,
        api_secret: str = API_SECRET,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError(f"Endpoint must use HTTPS, got: {endpoint}")
        self._email = email
        self._password = password
        self._timezone = timezone
        self._language = language
        self._endpoint = endpoint
        self._api_key = api_key
        self._api_secret = api_secret
        self._session = session
        self._own_session = session is None

        # Set after login
        self._session_token: str | None = None
        self._bearer_secret: str = api_secret
        self._user_id: str | None = None
        self._watches: list[dict[str, str]] = []

    def _ts(self) -> str:
        """Millisecond timestamp."""
        return str(math.floor(time() * 1000))

    def _open_headers(self) -> dict[str, str]:
        """Headers for the initial unauthenticated login request."""
        return {
            "content-type": "application/json",
            "h-backdoor-authorization": f"Open {self._api_key}:{self._api_secret}",
            "h-tid": self._ts(),
            "accept": "*/*",
            "origin": "https://goplay.myxplora.com",
        }

    def _bearer_headers(self) -> dict[str, str]:
        """Headers for authenticated requests after login."""
        if not self._session_token:
            raise XploraAuthError("Not logged in")
        return {
            "content-type": "application/json",
            "h-backdoor-authorization": (
                f"Bearer {self._session_token}:{self._bearer_secret}"
            ),
            "h-tid": self._ts(),
            "accept": "*/*",
            "origin": "https://goplay.myxplora.com",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def _post(
        self,
        query: str,
        variables: dict[str, Any],
        headers: dict[str, str],
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query, "variables": variables}
        if operation_name:
            payload["operationName"] = operation_name

        session = await self._get_session()
        async with session.post(
            self._endpoint,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def login(self) -> list[dict[str, str]]:
        """Authenticate and return list of watches [{wuid, name}]."""
        # Xplora API requires MD5-hashed password client-side.  If/when they change this, we'll get a login failure and can update accordingly.
        # codeql[py/weak-sensitive-data-hashing]
        pw_md5 = hashlib.md5(self._password.encode()).hexdigest()  # noqa: S324

        data = await self._post(
            _LOGIN_MUTATION,
            {
                "emailAddress": self._email,
                "countryPhoneNumber": None,
                "phoneNumber": None,
                "password": pw_md5,
                "userLang": self._language,
                "timeZone": self._timezone,
                "client": "WEB",
            },
            self._open_headers(),
            operation_name="signInWithEmailOrPhone",
        )
        _LOGGER.debug("Login response: %s", data)

        errors = data.get("errors")
        if errors:
            msgs = [e.get("message", "") for e in errors]
            raise XploraAuthError(f"Login failed: {msgs}")

        signin = data.get("data", {}).get("signInWithEmailOrPhone")
        if not signin or not signin.get("token"):
            raise XploraAuthError("Login returned no token")

        self._session_token = signin["token"]

        # Use w360 secret if provided, otherwise fall back to the configured API secret
        w360 = signin.get("w360") or {}
        if w360.get("secret"):
            self._bearer_secret = w360["secret"]
        else:
            self._bearer_secret = self._api_secret

        user = signin.get("user", {})
        self._user_id = user.get("id")

        # Extract watches from children
        self._watches = []
        for child in user.get("children", []):
            ward = child.get("ward", {})
            wuid = ward.get("id")
            name = ward.get("name", f"Watch {wuid[:8]}")
            if wuid:
                self._watches.append({"wuid": wuid, "name": name})

        _LOGGER.debug(
            "Logged in as %s, found %d watches", user.get("name"), len(self._watches)
        )
        return self._watches

    async def get_watch_location(self, wuid: str) -> dict[str, Any]:
        """Fetch last known location and battery data for a watch."""
        data = await self._post(
            _LOCATE_QUERY,
            {"uid": wuid},
            self._bearer_headers(),
            operation_name="WatchLastLocate",
        )
        _LOGGER.debug("WatchLastLocate response: %s", data)
        errors = data.get("errors")
        if errors:
            msgs = [e.get("message", "") for e in errors]
            _LOGGER.warning("watchLastLocate error for %s: %s", wuid, msgs)
            raise XploraApiError(f"watchLastLocate failed: {msgs}")

        locate = data.get("data", {}).get("watchLastLocate")
        if not locate:
            raise XploraApiError(f"No location data returned for {wuid}")

        return locate

    @property
    def watches(self) -> list[dict[str, str]]:
        """Return list of watches discovered at login."""
        return self._watches

    @property
    def is_authenticated(self) -> bool:
        return self._session_token is not None

    async def close(self) -> None:
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()
