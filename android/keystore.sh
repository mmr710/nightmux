#!/usr/bin/env bash
# One-time: make the release key and keep it. Android only installs an update signed by the same
# key as the app already on the phone, so a CI that signs with a fresh key every run (the debug
# fallback) makes every release "uninstall first, then pair again". With the key in two repository
# secrets, each APK updates the one before it.
set -euo pipefail
out="${1:-nightmux-release.jks}"
[ -e "$out" ] && { echo "$out exists: not overwriting a key" >&2; exit 1; }
pass="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)"
keytool -genkeypair -keystore "$out" -alias nightmux -keyalg RSA -keysize 4096 -validity 36500 \
  -storepass "$pass" -keypass "$pass" -dname "CN=nightmux" 2>/dev/null
echo "wrote $out. Back it up: if it is lost, every user must uninstall the app and pair again."
echo "Then set the secrets the Android workflow reads (run these from the repository):"
echo "  base64 -w0 $out | gh secret set NIGHTMUX_KEYSTORE_B64"
echo "  printf %s '$pass' | gh secret set NIGHTMUX_KEYSTORE_PASSWORD"
