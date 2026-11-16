#!/bin/bash
# Studio Tester installer. Paste ONE line in Terminal:
#   curl -fsSL https://raw.githubusercontent.com/kaareyes/studio_tester/release/install.sh | bash
# It downloads the latest release, puts it on the Desktop in the folder "Studio Tester" (a visible 'Studio Tester.command' plus a hidden
# folder with the program), and starts it. Run the same line again any time: it updates the program and keeps your collected projects,
# settings and reports. Files downloaded by curl are not marked "from the internet", so macOS shows no 'cannot verify' window.
#
# Everything is inside main(), which runs only on the last line: if the download is cut off half way, bash never reaches it and nothing runs.
main() {
  set -e
  if [ -d "$HOME/Desktop" ]; then DEFAULT_HOME="$HOME/Desktop/Studio Tester"; else DEFAULT_HOME="$HOME/Studio Tester"; fi
  DEST="${STUDIO_TESTER_HOME:-$DEFAULT_HOME}"
  URL="${STUDIO_TESTER_ZIP_URL:-https://github.com/kaareyes/studio_tester/archive/refs/heads/release.zip}"
  PORT="${STUDIO_TESTER_PORT:-8765}"
  INNER="$DEST/.studio_tester"

  echo
  echo "=============================================="
  echo " Studio Tester: installing"
  echo "=============================================="
  for tool in curl unzip; do
    command -v "$tool" >/dev/null 2>&1 || { echo "  FIX  '$tool' was not found on this Mac. Ask the developers for help."; exit 1; }
  done

  # Never replace the program files under a tester that is running a test or collecting.
  STATE="$(curl -s -m 2 "http://127.0.0.1:$PORT/api/state" 2>/dev/null || true)"
  COLLECT="$(curl -s -m 2 "http://127.0.0.1:$PORT/api/collect-state" 2>/dev/null || true)"
  if echo "$STATE" | grep -q '"suite": "' && echo "$STATE" | grep -q '"finished": null'; then
    echo "  FIX  A test is running in Studio Tester right now. Wait until it finishes (or press Stop on its page), then paste the line again."
    exit 1
  fi
  if echo "$COLLECT" | grep -q '"running": true'; then
    echo "  FIX  Studio Tester is collecting projects right now. Wait until it finishes, then paste the line again."
    exit 1
  fi

  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "[1/3] Downloading the latest version..."
  if ! curl -fsSL "$URL" -o "$TMP/release.zip"; then
    echo "  FIX  Could not download. Check the internet connection and paste the line again."
    exit 1
  fi
  unzip -q "$TMP/release.zip" -d "$TMP/unzipped"
  SRC="$(ls -d "$TMP"/unzipped/*/ | head -1)"
  [ -f "${SRC}tester/launcher.py" ] || { echo "  FIX  The download does not look like Studio Tester. Tell the developers."; exit 1; }

  echo "[2/3] Installing into: $DEST"
  mkdir -p "$INNER"
  # Replace the program files; never touch the data (catalog.json, settings.json, reports, .venv).
  for item in tester suites tests docs NAMES.md README.md requirements.txt VERSION release.json install.sh "Studio Tester.command"; do
    if [ -e "${SRC}${item}" ]; then rm -rf "${INNER:?}/${item}"; cp -R "${SRC}${item}" "$INNER/$item"; fi
  done
  chmod +x "$INNER/Studio Tester.command" "$INNER/install.sh" 2>/dev/null || true

  # The one visible file: double-click it next time (or paste the line again).
  cat > "$DEST/Studio Tester.command" <<'LAUNCH'
#!/bin/bash
# Studio Tester: double-click this file. Everything else is in the hidden folder .studio_tester next to it.
cd "$(dirname "$0")" || exit 1
exec ./.studio_tester/"Studio Tester.command"
LAUNCH
  chmod +x "$DEST/Studio Tester.command"
  xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

  echo "[3/3] Done. Version $(cat "$INNER/VERSION" 2>/dev/null)."
  if [ -n "$STUDIO_TESTER_NO_START" ]; then exit 0; fi
  echo "Starting Studio Tester..."
  echo
  # This script was read from a pipe, so questions must be read from the keyboard (the terminal) instead.
  if [ -r /dev/tty ]; then exec "$INNER/Studio Tester.command" < /dev/tty; else exec "$INNER/Studio Tester.command"; fi
}

main "$@"
