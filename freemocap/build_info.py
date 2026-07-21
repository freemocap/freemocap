"""Build metadata and secrets populated by CI at build time.

During local development these remain at their default values. The CI workflow
(.github/workflows/build-installers-pyinstaller.yml) overwrites this file before
PyInstaller runs. The placeholder telemetry secret fails HMAC validation on the
server, so dev / from-source builds send unverified telemetry.
"""

# ── Build metadata ──
BUILD_GIT_SHA: str = "dev"
BUILD_GIT_SHA_SHORT: str = "dev"
BUILD_NUMBER: str = "local"
BUILD_TIMESTAMP: str = "unknown"
BUILD_TAG: str = "untagged"

# ── Telemetry ──
SKELLYPINGS_SERVER_URL: str = "https://skellypings-401698866387.northamerica-northeast1.run.app"
SKELLYPINGS_SECRET: str = "not-configured"
