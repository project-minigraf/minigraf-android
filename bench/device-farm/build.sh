#!/usr/bin/env bash
# Build in a disposable copy of the binding checkout with a disposable core
# checkout. Android SDK/NDK, Java 17, Rust and cargo-ndk must already be installed.
set -euo pipefail
binding_dir=$(cd "$(dirname "$0")/../.." && pwd)
core_dir=$(cd "${1:?usage: build.sh /path/to/core}" && pwd)
cd "$binding_dir"
: "${ANDROID_HOME:?set ANDROID_HOME}"
: "${ANDROID_NDK_HOME:?set ANDROID_NDK_HOME}"
core_revision=${CORE_REVISION:-$(git -C "$core_dir" rev-parse HEAD)}
binding_revision=${BINDING_REVISION:-$(git rev-parse HEAD)}
export CARGO_BUILD_JOBS=${CARGO_BUILD_JOBS:-4}
test ! -e .cargo/config.toml
mkdir -p .cargo
python3 - "$core_dir" <<'PY'
import json, pathlib, sys
pathlib.Path('.cargo/config.toml').write_text(
    '[patch."https://github.com/project-minigraf/minigraf"]\n'
    'minigraf = { path = ' + json.dumps(sys.argv[1]) + ' }\n')
PY
cargo update -p minigraf
mkdir -p bench/device-farm/build/evidence
evidence="$binding_dir/bench/device-farm/build/evidence"
cargo metadata --format-version 1 > "$evidence/cargo-metadata.json"
python3 - "$core_dir" "$evidence/cargo-metadata.json" <<'PY'
import json, pathlib, sys
packages = json.load(open(sys.argv[2]))['packages']
core = [p for p in packages if p['name'] == 'minigraf']
assert len(core) == 1 and core[0]['source'] is None
assert pathlib.Path(core[0]['manifest_path']).parent == pathlib.Path(sys.argv[1])
PY
cargo test --lib
cargo build --release --bin uniffi-bindgen
cargo ndk -t arm64-v8a --platform 24 build --release --lib
mkdir -p android/jniLibs/arm64-v8a
cp target/aarch64-linux-android/release/libminigraf_ffi.so android/jniLibs/arm64-v8a/
target/release/uniffi-bindgen generate \
    --library target/aarch64-linux-android/release/libminigraf_ffi.so \
    --language kotlin --no-format --out-dir android/src/main/java/
bash android/gradlew -p android --no-daemon assembleRelease
mkdir -p bench/device-farm/libs bench/device-farm/src/main/assets
cp android/build/outputs/aar/minigraf-android-release.aar bench/device-farm/libs/minigraf.aar
python3 - "$core_revision" "$binding_revision" <<'PY'
import hashlib, json, os, pathlib, subprocess, sys
root = pathlib.Path('bench/device-farm')
files = sorted(p for p in root.rglob('*') if p.is_file() and
    not any(part in ('build', 'libs', '.gradle', 'assets') for part in p.relative_to(root).parts))
digest = hashlib.sha256()
for p in files:
    digest.update(str(p.relative_to(root)).encode() + b'\0' + p.read_bytes() + b'\0')
def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
record = dict(core_revision=sys.argv[1], binding_revision=sys.argv[2],
    evidence_kind='source-build', harness_sha256=digest.hexdigest(),
    binding_aar_sha256=sha(root / 'libs/minigraf.aar'),
    native_sha256=sha('android/jniLibs/arm64-v8a/libminigraf_ffi.so'),
    cargo_lock_sha256=sha('Cargo.lock'),
    rustc=subprocess.check_output(['rustc', '--version'], text=True).strip(),
    abi='arm64-v8a', profile='release',
    ndk=next(line.split('=', 1)[1].strip() for line in
        (pathlib.Path(os.environ['ANDROID_NDK_HOME']) / 'source.properties').read_text().splitlines()
        if line.startswith('Pkg.Revision')),
    java=subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True).splitlines()[0],
    gradle='8.4', android_gradle_plugin='8.2.2', kotlin='2.0.21',
    compile_sdk=34, min_sdk=24)
(root / 'src/main/assets/build.json').write_text(json.dumps(record, indent=2) + '\n')
PY
bash android/gradlew -p bench/device-farm --no-daemon testReleaseUnitTest assembleRelease assembleReleaseAndroidTest
cp Cargo.lock "$evidence/Cargo.lock"
cp bench/device-farm/src/main/assets/build.json "$evidence/build.json"
sha256sum bench/device-farm/build/outputs/apk/release/*.apk \
    bench/device-farm/build/outputs/apk/androidTest/release/*.apk > "$evidence/apks.sha256"
printf 'APKs and provenance: %s/bench/device-farm/build\n' "$binding_dir"
