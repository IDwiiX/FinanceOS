#!/usr/bin/env bash
# deploy.sh — idempotent FinanceOS deployment script.
#
# Run INSIDE WSL from the directory containing this script:
#     bash deploy.sh
#
# What it does:
#   1. Syncs project files into ~/finance-os
#   2. (Re)creates the venv and installs requirements
#   3. Runs self-tests on the pricing models
#   4. Installs systemd units (dashboard service + update timer)
#   5. Appends FinanceOS commands to ~/.bashrc (idempotent)
#   6. Prints next-steps and the verification checklist
set -euo pipefail

# --- config ---
PROJECT_DIR="$HOME/finance-os"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="$(whoami)"

# Banner
echo "================================================"
echo "  FinanceOS Deploy"
echo "  user:   ${USER_NAME}"
echo "  target: ${PROJECT_DIR}"
echo "  source: ${SCRIPT_DIR}"
echo "================================================"

# ---------------------------------------------------------------- #
#  0. Preflight
# ---------------------------------------------------------------- #
if [ ! -d "${SCRIPT_DIR}/src" ] || [ ! -f "${SCRIPT_DIR}/main.py" ]; then
    echo "ERROR: must run from the finance-os-deploy folder (contains src/ and main.py)."
    exit 1
fi

if [ ! -d "${PROJECT_DIR}" ]; then
    echo ">> Creating project dir ${PROJECT_DIR}"
    mkdir -p "${PROJECT_DIR}"
fi

# ---------------------------------------------------------------- #
#  1. Sync project files
# ---------------------------------------------------------------- #
echo ">> Syncing project files..."
# Keep .venv and cache across deploys; overwrite everything else.
for item in main.py requirements.txt .gitignore src config; do
    src_path="${SCRIPT_DIR}/${item}"
    if [ -e "${src_path}" ]; then
        if [ -d "${src_path}" ]; then
            mkdir -p "${PROJECT_DIR}/$(dirname "${item}")"
            cp -rT "${src_path}" "${PROJECT_DIR}/${item}"
        else
            cp "${src_path}" "${PROJECT_DIR}/${item}"
        fi
    fi
done

# Ensure runtime dirs exist
mkdir -p "${PROJECT_DIR}/cache" "${PROJECT_DIR}/logs" "${PROJECT_DIR}/tests"

# .env: only copy if absent (don't clobber real keys)
if [ ! -f "${PROJECT_DIR}/config/.env" ]; then
    cp "${SCRIPT_DIR}/config/.env" "${PROJECT_DIR}/config/.env"
    echo ">> Created config/.env from template (edit to add real API keys)."
fi

# ---------------------------------------------------------------- #
#  2. Virtualenv + dependencies
# ---------------------------------------------------------------- #
VENV="${PROJECT_DIR}/.venv"
if [ ! -d "${VENV}" ]; then
    echo ">> Creating virtualenv at ${VENV}"
    python3 -m venv "${VENV}"
fi

echo ">> Upgrading pip tooling"
"${VENV}/bin/python" -m pip install --upgrade pip setuptools wheel >/dev/null

echo ">> Installing requirements (this can take a minute)..."
"${VENV}/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"

# ---------------------------------------------------------------- #
#  3. Self-test pricing models
# ---------------------------------------------------------------- #
echo ">> Running pricing model self-tests..."
( cd "${PROJECT_DIR}" && "${VENV}/bin/python" -m src.models.pricing ) || {
    echo "ERROR: pricing self-tests failed. Inspect output above."
    exit 1
}

# ---------------------------------------------------------------- #
#  4. Systemd units (replace REPLACE_USER placeholder)
# ---------------------------------------------------------------- #
echo ">> Installing systemd units (user=${USER_NAME})..."
for unit_src in dashboard.service update.service update.timer; do
    unit_file="/etc/systemd/system/financeos-${unit_src}"
    sed "s/REPLACE_USER/${USER_NAME}/g" \
        "${SCRIPT_DIR}/systemd/financeos-${unit_src}" | sudo tee "${unit_file}" >/dev/null
done

sudo systemctl daemon-reload
sudo systemctl enable financeos-dashboard.service >/dev/null 2>&1 || true
sudo systemctl enable --now financeos-update.timer >/dev/null 2>&1 || true
sudo systemctl restart financeos-dashboard.service >/dev/null 2>&1 || true

# ---------------------------------------------------------------- #
#  5. ~/.bashrc additions (idempotent: replace block if present)
# ---------------------------------------------------------------- #
MARK_BEGIN="# >>> FinanceOS customizations >>>"
MARK_END="# <<< FinanceOS customizations <<<"

bashrc="${HOME}/.bashrc"
# Strip any previous FinanceOS block
if grep -q "${MARK_BEGIN}" "${bashrc}"; then
    sed -i "/${MARK_BEGIN}/,/${MARK_END}/d" "${bashrc}"
fi

{
    echo ""
    echo "${MARK_BEGIN}"
    cat "${SCRIPT_DIR}/bashrc.additions.sh"
    echo "${MARK_END}"
} >> "${bashrc}"
echo ">> Updated ${bashrc} with FinanceOS commands (idempotent)."

# ---------------------------------------------------------------- #
#  6. Done
# ---------------------------------------------------------------- #
echo ""
echo "================================================"
echo "  ✅ Deploy complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Reload your shell:        source ~/.bashrc"
echo "  2. Try the CLI:              python ~/finance-os/main.py --price AAPL"
echo "  3. Open the dashboard:       http://localhost:8501"
echo "  4. Dashboard service status: systemctl status financeos-dashboard"
echo "  5. Manually run updater:     sudo systemctl start financeos-update.service"
echo "                              sudo journalctl -u financeos-update.service -e --no-pager"
echo ""
