#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# run_tests.sh — Run all backend + frontend tests
#
# Usage:
#   ./scripts/run_tests.sh           Run everything
#   ./scripts/run_tests.sh backend   Backend only
#   ./scripts/run_tests.sh frontend  Frontend only
#   ./scripts/run_tests.sh sync      Just the frontend/backend sync tests
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RESET='\033[0m'

passed=0
failed=0

run_step() {
    local label="$1"
    shift
    echo -e "\n${CYAN}━━━ ${label} ━━━${RESET}\n"
    if "$@"; then
        echo -e "\n${GREEN}✓ ${label} passed${RESET}"
        ((passed++))
    else
        echo -e "\n${RED}✗ ${label} FAILED${RESET}"
        ((failed++))
    fi
}

run_backend() {
    cd "$REPO_ROOT"
    run_step "Backend: Schema contract tests" \
        uv run pytest freemocap/tests/test_schema_contract.py -v
    run_step "Backend: SettingsManager unit tests" \
        uv run pytest freemocap/tests/test_settings_manager.py -v
    run_step "Backend: HTTP endpoint integration tests" \
        uv run pytest freemocap/tests/test_http_config_endpoints.py -v
    run_step "Backend: WebSocket protocol tests" \
        uv run pytest freemocap/tests/test_websocket_settings_protocol.py -v
}

run_frontend() {
    cd "$REPO_ROOT/freemocap-ui"
    run_step "Frontend: Vitest suite" \
        npx vitest run
}

run_sync() {
    cd "$REPO_ROOT"
    run_step "Sync tests (schema + settings + HTTP + WebSocket)" \
        uv run pytest \
            freemocap/tests/test_schema_contract.py \
            freemocap/tests/test_settings_manager.py \
            freemocap/tests/test_http_config_endpoints.py \
            freemocap/tests/test_websocket_settings_protocol.py \
            -v
}

# --- Main ---

target="${1:-all}"

echo -e "${CYAN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║   FreeMoCap Test Runner                  ║${RESET}"
echo -e "${CYAN}║   Target: ${target}$(printf '%*s' $((29 - ${#target})) '')║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${RESET}"

case "$target" in
    backend)  run_backend ;;
    frontend) run_frontend ;;
    sync)     run_sync ;;
    all)      run_backend; run_frontend ;;
    *)
        echo "Unknown target: $target"
        echo "Usage: $0 [all|backend|frontend|sync]"
        exit 1
        ;;
esac

echo -e "\n${CYAN}━━━ Summary ━━━${RESET}"
echo -e "${GREEN}Passed: ${passed}${RESET}"
if [ "$failed" -gt 0 ]; then
    echo -e "${RED}Failed: ${failed}${RESET}"
    exit 1
else
    echo -e "${GREEN}All test groups passed!${RESET}"
fi
