#!/usr/bin/env bash
# Consumer test: an app that depends on minigraf-android only through its Maven
# coordinates runs the README quick start and the consumer contract as
# instrumented tests on the connected emulator or device.
#
#   run.sh local <m2-dir> <version>   from built artifacts (the dist-aar layout)
#   run.sh registry <version>         from Maven Central, once it has <version>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
GROUP_PATH=io/github/project-minigraf/minigraf-android

# wait_for <seconds> <command...>: run the command every 30 s until it succeeds.
wait_for() {
  local limit="$1"; shift
  local start=$SECONDS
  until "$@"; do
    if (( SECONDS - start >= limit )); then
      echo "::error::gave up after ${limit}s waiting for: $*"
      return 1
    fi
    sleep 30
  done
}

ARGS=()
case "${1:-}" in
  local)
    REPO="$(cd "$2" && pwd)"
    VERSION="$3"
    ARGS+=("-PminigrafRepo=$REPO")
    ;;
  registry)
    VERSION="$2"
    # Maven Central sync is the slowest of the registries (spec §6).
    wait_for 5400 curl -sfI -o /dev/null \
      "https://repo1.maven.org/maven2/$GROUP_PATH/$VERSION/minigraf-android-$VERSION.pom"
    ;;
  *)
    echo "usage: $0 local <m2-dir> <version> | registry <version>" >&2
    exit 2
    ;;
esac
ARGS+=("-PminigrafVersion=$VERSION")

gradle() { "$ROOT/android/gradlew" -p "$HERE" --no-daemon "${ARGS[@]}" "$@"; }

# The resolved dependency is the version under test, and its pom brings JNA.
DEPS="$(gradle -q dependencies --configuration debugRuntimeClasspath)"
echo "$DEPS"
grep -q "io.github.project-minigraf:minigraf-android:$VERSION\b" <<<"$DEPS" \
  || { echo "::error::minigraf-android:$VERSION is not on the runtime classpath"; exit 1; }
grep -q "net.java.dev.jna:jna:" <<<"$DEPS" \
  || { echo "::error::minigraf-android does not bring JNA"; exit 1; }

gradle connectedDebugAndroidTest
