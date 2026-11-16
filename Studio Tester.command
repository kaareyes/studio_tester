#!/bin/bash
# Studio Tester: double-click this one file. It checks what is missing, asks, installs, checks again and starts the tester.
cd "$(dirname "$0")" || exit 1
printf '\n'

# Finds a Python 3.9 or newer. (/usr/bin/python3 is only tried when Apple's command line tools exist: without them macOS opens an
# install window just because it is run.)
find_python() {
  for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /usr/bin/python3 python3; do
    if [ "$candidate" = "/usr/bin/python3" ] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; then continue; fi
    command -v "$candidate" >/dev/null 2>&1 || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then echo "$candidate"; return 0; fi
  done
  return 1
}

PY="$(find_python)"
if [ -z "$PY" ]; then
  echo "[0/5] Python 3.9 or newer was not found on this Mac."
  echo "  Apple's free 'command line tools' include it. The install takes a few minutes and needs internet."
  read -r -p "  ? Install them now? [Y/n] " answer
  case "$answer" in [nN]*) echo "  Not installed. Run this file again when you are ready."; read -n 1 -s -r -p "Press any key to close."; exit 1;; esac
  /usr/bin/xcode-select --install >/dev/null 2>&1
  echo "  A window from Apple opened: click Install, then Agree. I wait here and continue by myself."
  waited=0
  while [ -z "$PY" ]; do
    sleep 5; waited=$((waited + 5))
    PY="$(find_python)"
    [ $((waited % 30)) -eq 0 ] && echo "  still installing... (${waited}s)"
    if [ "$waited" -gt 3600 ]; then echo "  This took more than an hour. Run this file again later."; read -n 1 -s -r -p "Press any key to close."; exit 1; fi
  done
  echo "  Python found: $PY"
fi

"$PY" tester/launcher.py
STATUS=$?
if [ $STATUS -ne 0 ]; then echo; read -n 1 -s -r -p "Studio Tester stopped. Press any key to close."; fi
exit $STATUS
