#!/usr/bin/env bash
#
# Hachi one-liner installer (macOS / Linux)
#
#   curl -fsSL https://raw.githubusercontent.com/OpenGigantic/hachi/main/install.sh | bash
#
# Bootstraps uv (which manages Python), fetches Hachi, installs deps, and
# launches the guided setup. Override the source repo or install location with
# the HACHI_REPO / HACHI_HOME environment variables.
set -euo pipefail

REPO_URL="${HACHI_REPO:-https://github.com/OpenGigantic/hachi}"
# Pin what you install. Empty means "the default branch", so re-running this
# installer later silently upgrades to whatever main is at that moment. Set
# HACHI_REF=v0.1.0 for a reproducible install.
HACHI_REF="${HACHI_REF:-}"
INSTALL_DIR="${HACHI_HOME:-$HOME/.hachi-src}"
BIN_DIR="$HOME/.local/bin"

# Never let git block on a credential prompt. Under `curl … | bash` this
# script's stdin IS the pipe, so an interactive git prompt consumes the rest of
# the script and the install hangs forever with no output. Fail fast instead.
export GIT_TERMINAL_PROMPT=0

info() { printf "\033[36m==>\033[0m %s\n" "$1"; }
err() { printf "\033[31mError:\033[0m %s\n" "$1" >&2; }

# 1. Preconditions first — no point bootstrapping a Python toolchain only to
#    discover git is missing afterwards.
if ! command -v git >/dev/null 2>&1; then
  err "git is required but not installed. Install git and re-run."
  exit 1
fi

# 2. Ensure uv (it provisions a suitable Python automatically).
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv (Python toolchain manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # The upstream installer writes to ~/.local/bin but does NOT refresh this
  # shell's PATH, so `uv` would be "not found" on every later line.
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    err "uv was installed but is not on PATH. Add \$HOME/.local/bin to PATH and re-run."
    exit 1
  fi
fi

# 3. Fetch (or update) the source.
#    `< /dev/null` is load-bearing: under `curl … | bash` the script's stdin is
#    the pipe, so git inheriting it swallows the remaining script text — every
#    line after the clone silently never executes — and can block on a
#    credential prompt forever. With GIT_TERMINAL_PROMPT=0 that hang becomes a
#    clean, reportable failure instead.
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating Hachi in $INSTALL_DIR..."
  if ! git -C "$INSTALL_DIR" pull --ff-only </dev/null; then
    err "Could not update $INSTALL_DIR (local changes, detached HEAD, or a rewritten history)."
    err "Remove that directory and re-run, or set HACHI_HOME to a fresh path."
    exit 1
  fi
else
  info "Cloning Hachi into $INSTALL_DIR..."
  clone_args=(--depth 1)
  if [ -n "$HACHI_REF" ]; then
    clone_args+=(--branch "$HACHI_REF")
  fi
  if ! git clone "${clone_args[@]}" "$REPO_URL" "$INSTALL_DIR" </dev/null; then
    err "git clone failed. If the repository is private, this installer cannot fetch it."
    exit 1
  fi
fi

# 4. Install dependencies. Report a failure explicitly rather than letting
#    `set -e` abort with a bare uv error after we have already claimed success.
cd "$INSTALL_DIR"
info "Installing dependencies (this can take a minute)..."
if ! uv sync; then
  err "Dependency install failed. Run 'uv sync' in $INSTALL_DIR to see the full error."
  exit 1
fi

# 4. Drop a friendly launcher on PATH.
mkdir -p "$BIN_DIR"
cat >"$BIN_DIR/hachi" <<EOF
#!/usr/bin/env bash
exec uv run --project "$INSTALL_DIR" hachi "\$@"
EOF
chmod +x "$BIN_DIR/hachi"

# 5. Launch the guided setup — only when a human is actually present.
#    `quickstart` is entirely interactive: with no TTY it either EOFs or hangs.
#
#    Test stdout, not stdin. Under `curl … | bash` — the only advertised
#    invocation — fd0 IS the pipe, so `-t 0` is always false and gating on it
#    meant setup never ran even for a human at a terminal. Reattach the real
#    terminal from /dev/tty instead, and fall back to skipping when there is
#    genuinely no terminal (CI, Docker, cron).
if [ -t 1 ] && { : </dev/tty; } 2>/dev/null; then
  info "Installed! Launching setup..."
  "$BIN_DIR/hachi" quickstart </dev/tty \
    || info "Setup exited early — run 'hachi quickstart' when ready."
else
  info "Installed (no terminal — skipping guided setup; run 'hachi quickstart' later)."
fi

cat <<EOF

────────────────────────────────────────────────────────
Hachi is installed. If the 'hachi' command isn't found,
add this to your shell profile (~/.bashrc or ~/.zshrc):

  export PATH="\$HOME/.local/bin:\$PATH"

Then start chatting:

  hachi run
────────────────────────────────────────────────────────
EOF
