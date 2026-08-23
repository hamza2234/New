#!/usr/bin/env bash
# Idempotent environment bootstrap for the NativeLudo Android/Gradle project.
# Installs the Android SDK packages Gradle needs to run tests and build the APK.
set -euo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
export ANDROID_HOME

# Android SDK command-line tools build id (see developer.android.com/tools/releases/cmdline-tools).
CMDLINE_TOOLS_VERSION="14742923"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$ANDROID_HOME"

if [ ! -x "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" ]; then
  echo "Installing Android command-line tools ${CMDLINE_TOOLS_VERSION}..."
  tmp_dir="$(mktemp -d)"
  curl -fsSL -o "$tmp_dir/cmdline-tools.zip" \
    "https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip"
  unzip -q "$tmp_dir/cmdline-tools.zip" -d "$tmp_dir/extracted"
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  rm -rf "$ANDROID_HOME/cmdline-tools/latest"
  mv "$tmp_dir/extracted/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
  rm -rf "$tmp_dir"
fi

SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"

# Accept all SDK licenses so Gradle's Android plugin can (re)install packages non-interactively.
yes | "$SDKMANAGER" --licenses >/dev/null

# platforms/android-34 matches compileSdk/targetSdk in app/build.gradle.kts.
# build-tools 34.0.0 matches that SDK; 36.0.0 is what AGP 9.2.0 resolves to by default.
"$SDKMANAGER" \
  "platform-tools" \
  "platforms;android-34" \
  "build-tools;34.0.0" \
  "build-tools;36.0.0" >/dev/null

# Point Gradle at the SDK for the current checkout. start.sh rewrites this on every boot.
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$REPO_ROOT/local.properties"

echo "Android SDK ready at $ANDROID_HOME"
