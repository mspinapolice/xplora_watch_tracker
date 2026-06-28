"""Constants for Xplora Watch Tracker."""

DOMAIN = "xplora_watch_tracker"

# API
ENDPOINT = "https://api.prod.myxplora.com/api"
API_KEY = "63fa1d10289711ea80b5992f808043b2"
API_SECRET = "27ed7670379511eab4a0f367f8eb1312"

# Config entry keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_TIMEZONE = "timezone"
CONF_LANGUAGE = "language"
CONF_WATCHES = "watches"  # list of {wuid, name}
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENDPOINT = "endpoint"
CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"

# Defaults
DEFAULT_ENDPOINT = ENDPOINT
DEFAULT_API_KEY = API_KEY
DEFAULT_API_SECRET = API_SECRET
DEFAULT_SCAN_INTERVAL = 180  # seconds (3 minutes)
MIN_SCAN_INTERVAL = 60  # seconds (1 minute)
MAX_SCAN_INTERVAL = 600  # seconds (10 minutes)
DEFAULT_TIMEZONE = ""
DEFAULT_LANGUAGE = ""

# Platforms
PLATFORMS = ["device_tracker", "sensor"]
