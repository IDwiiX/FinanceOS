# ===== FinanceOS customizations (append to ~/.bashrc) =====

# --- project path + shortcut ---
export FINANCE_OS_HOME="$HOME/finance-os"
alias fos="cd $FINANCE_OS_HOME"

# --- custom commands ---

# finance          -> launch interactive CLI menu
finance() {
    ( cd "$FINANCE_OS_HOME" && .venv/bin/python main.py --menu "$@" )
}

# price AAPL       -> latest price + trading signal
price() {
    if [ -z "$1" ]; then echo "Usage: price <SYMBOL>"; return 1; fi
    ( cd "$FINANCE_OS_HOME" && .venv/bin/python main.py --price "$1" \
        && .venv/bin/python main.py --signal "$1" )
}

# dashboard        -> launch Streamlit in background + open Windows browser
dashboard() {
    ( cd "$FINANCE_OS_HOME" && .venv/bin/python main.py --dashboard ) &
    local pid=$!
    echo "FinanceOS dashboard starting (pid $pid)..."
    sleep 4
    # Forward to Windows browser if cmd.exe is available (WSL interop)
    if command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start http://localhost:8501 >/dev/null 2>&1
    fi
}

# --- auto-activate venv ---
if [ -d "$HOME/finance-os/.venv" ]; then
    source "$HOME/finance-os/.venv/bin/activate"
fi

# --- custom prompt ---
force_color_prompt=yes
PS1='\[\e[1;32m\]FinanceOS\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '
