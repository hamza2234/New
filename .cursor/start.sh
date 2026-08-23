#!/usr/bin/env bash
# Per-boot reconciliation: make sure Gradle can find the Android SDK for the
# freshly checked-out repository. Idempotent and returns immediately.
set -euo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$REPO_ROOT/local.properties"
echo "Wrote $REPO_ROOT/local.properties (sdk.dir=$ANDROID_HOME)"
