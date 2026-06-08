# Xplora Watch Tracker

A Home Assistant custom integration for tracking Xplora kids smartwatches. Provides GPS location, battery percentage, and charging state for all watches linked to your Xplora account.

![Xplora](https://raw.githubusercontent.com/mspinapolice/xplora_watch_tracker/main/custom_components/xplora_watch_tracker/brand/icon.png)

## Features

- 📍 **GPS tracking** — live location for each watch displayed on the HA map
- 🔋 **Battery level** — percentage sensor with standard HA battery device class
- ⚡ **Charging state** — `charging` / `not_charging` sensor
- 👤 **Person integration** — device trackers can be assigned to HA People
- 🔄 **Configurable poll interval** — 60 to 600 seconds (default 180 seconds)
- 🏷️ **Custom watch names** — set friendly names during setup or via the options flow
- 🔧 **Configurable API settings** — override the Xplora API endpoint, key, and secret through the integration options if upstream values change
- 🔁 **Auto-discovery** — watches are discovered from your account at login; adding or removing a watch takes effect on next HA restart

## Requirements

- Home Assistant 2024.1 or newer
- An Xplora account with at least one watch linked, accessible via [goplay.myxplora.com](https://goplay.myxplora.com)
- Your Xplora account must use **email + password** login (not phone number)

## Installation

### Manual

1. Download the latest release zip from the [Releases](https://github.com/mspinapolice/xplora_watch_tracker/releases) page
2. Extract and copy the `xplora_watch_tracker` folder into your HA `config/custom_components/` directory:
   ```
   config/
   └── custom_components/
       └── xplora_watch_tracker/
           ├── __init__.py
           ├── api.py
           ├── config_flow.py
           ├── ...
           └── brand/
               └── icon.png
   ```
3. Restart Home Assistant fully (Settings → System → Restart)

### HACS (Custom Repository)

1. In HACS, go to Integrations → ⋮ → Custom repositories
2. Add `https://github.com/mspinapolice/xplora_watch_tracker` as an **Integration**
3. Search for "Xplora Watch Tracker" and install
4. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Xplora Watch Tracker**
3. Enter your credentials:
   - **Email address** — the email on your Xplora account
   - **Password** — your Xplora account password
   - **Timezone** — your local timezone (e.g. `America/New_York`)
   - **Language** — your preferred language code (e.g. `en-US`)
4. On the next screen, set a friendly name for each discovered watch and choose your poll interval
5. Click **Submit** — the integration will appear under Devices & Services

## Entities

For each watch, the integration creates three entities grouped under one device:

| Entity | Type | Example |
|--------|------|---------|
| `device_tracker.<name>` | Device Tracker | `home` / `not_home` |
| `sensor.<name>_battery` | Sensor | `79` % |
| `sensor.<name>_charging` | Sensor | `not_charging` |

The device tracker also exposes these attributes:
- `latitude` / `longitude`
- `locate_type` — `GPS`, `WIFI`, or `LBS` (cell tower)
- `location_accuracy` — radius in metres
- `last_seen` — Unix timestamp of the last location fix
- `city`, `country`, `address` — when available from the API

## Options

After setup, click **Configure** on the integration card to adjust:
- **Poll interval** — how often to request updated location and battery data (60–600 seconds)
- **Watch names** — rename any watch without removing and re-adding the integration
- **API endpoint / API key / API secret** — override the connection details used to reach Xplora's backend

Changes take effect immediately via an automatic integration reload.

## Assigning Watches to People

1. Go to **Settings → People**
2. Edit or create a person (e.g. "YourNameHere")
3. Under **Tracking devices**, select `device_tracker.yournamehere`
4. HA will use the watch location to determine `home` / `not_home` state for that person

## Troubleshooting

**Authentication failed on setup**
- Confirm you can log into [goplay.myxplora.com](https://goplay.myxplora.com) with the same email and password
- Ensure you are using email address + password login, not a phone number - in my testing, it seems the new API only accepts email addresses now
- Check that your password does not need to be reset (the account may lock after repeated failed attempts)

**Location not updating**
- Check that the watch has GPS or WiFi signal
- The `locate_type` attribute shows the fix method — `LBS` (cell tower) is least accurate and may not update as frequently
- Increase poll interval if you are seeing API errors in the HA logs (and to prevent potential IP bans from Xplora)

**Icon not showing**
- Requires a full HA restart (not just an integration reload) followed by a hard browser refresh (`Ctrl+Shift+R`)

**No watches found**
- Ensure the watches are linked to your account in the Xplora app
- Try removing and re-adding the integration to trigger fresh discovery

## Known Limitations

- **No real-time push** — location is polled on a schedule, not pushed from the watch
- **GPS accuracy varies** — the watch reports `GPS`, `WIFI`, or `LBS` fix types with varying accuracy
- **API dependency** — this integration uses Xplora's private API. If Xplora changes their API, the integration may stop working until updated
- **Email + password only** — accounts using Google or Apple SSO cannot authenticate via the API

## License

MIT License — see [LICENSE](LICENSE) for details.
