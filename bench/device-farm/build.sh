#!/usr/bin/env bash
# Build in a disposable copy of the binding checkout with a disposable core
# checkout. Android SDK/NDK, Java 17, Rust and cargo-ndk must already be installed.
set -euo pipefail
binding_dir=$(cd "$(dirname "$0")/../.." && pwd)
core_dir=$(cd "${1:?usage: build.sh CORE_CHECKOUT CORE_SHA}" && pwd)
pinned_core=${2:?a full pinned core SHA is required}
[[ "$pinned_core" =~ ^[0-9a-f]{40}$ ]] || { echo 'core SHA must be 40 lowercase hex characters' >&2; exit 1; }
cd "$binding_dir"
: "${ANDROID_HOME:?set ANDROID_HOME}"
: "${ANDROID_NDK_HOME:?set ANDROID_NDK_HOME}"
core_revision=${CORE_REVISION:-$(git -C "$core_dir" rev-parse HEAD)}
binding_revision=${BINDING_REVISION:-$(git rev-parse HEAD)}
[[ "$core_revision" == "$pinned_core" ]] || { echo 'core checkout/archive does not match pinned SHA' >&2; exit 1; }
[[ "$binding_revision" =~ ^[0-9a-f]{40}$ ]] || exit 1
if [[ -e "$core_dir/.git" ]]; then
  [[ "$(git -C "$core_dir" rev-parse HEAD)" == "$pinned_core" ]]
  test -z "$(git -C "$core_dir" status --porcelain)"
fi
if [[ -e .git ]]; then
  [[ "$(git rev-parse HEAD)" == "$binding_revision" ]]
  test -z "$(git status --porcelain)"
fi
export CARGO_BUILD_JOBS=2
test ! -e bench/device-farm/build
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
cargo ndk -t arm64-v8a -t x86_64 --platform 24 build --locked --release --lib
mkdir -p android/jniLibs/arm64-v8a android/jniLibs/x86_64
cp target/aarch64-linux-android/release/libminigraf_ffi.so android/jniLibs/arm64-v8a/
cp target/x86_64-linux-android/release/libminigraf_ffi.so android/jniLibs/x86_64/
target/release/uniffi-bindgen generate \
    --library target/aarch64-linux-android/release/libminigraf_ffi.so \
    --language kotlin --no-format --out-dir android/src/main/java/
cat > bench/device-farm/build/keep-native.gradle <<'GRADLE'
allprojects {
    plugins.withId('com.android.library') {
        android.packagingOptions.jniLibs.keepDebugSymbols.add('**/libminigraf_ffi.so')
    }
}
GRADLE
bash android/gradlew -p android -I "$binding_dir/bench/device-farm/build/keep-native.gradle" --no-daemon --max-workers=2 -Dorg.gradle.jvmargs=-Xmx2g assembleRelease
bash android/gradlew -p android --no-daemon --max-workers=2 -Dorg.gradle.jvmargs=-Xmx2g --version > "$evidence/gradle-version.txt"
mkdir -p bench/device-farm/libs bench/device-farm/src/main/assets
cp android/build/outputs/aar/minigraf-android-release.aar bench/device-farm/libs/minigraf.aar
python3 - "$core_revision" "$binding_revision" <<'PY'
import hashlib, json, os, pathlib, re, subprocess, sys, zipfile
root = pathlib.Path('bench/device-farm')
files = sorted(p for p in root.rglob('*') if p.is_file() and
    not any(part in ('build', 'libs', '.gradle', 'assets', '__pycache__') for part in p.relative_to(root).parts))
digest = hashlib.sha256()
for p in files:
    digest.update(str(p.relative_to(root)).encode() + b'\0' + p.read_bytes() + b'\0')
def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
native = {abi: dict(sha256=sha('android/jniLibs/'+abi+'/libminigraf_ffi.so'))
          for abi in ('arm64-v8a', 'x86_64')}
with zipfile.ZipFile(root / 'libs/minigraf.aar') as aar:
    for abi, entry in native.items():
        assert hashlib.sha256(aar.read('jni/'+abi+'/libminigraf_ffi.so')).hexdigest() == entry['sha256']
# Record versions from the inputs/output actually used, not optimistic labels.
agp = re.search(r'id\("com.android.application"\) version "([^"]+)"', (root/'build.gradle.kts').read_text())[1]
gradle = re.search(r'^Gradle (.+)$', (root/'build/evidence/gradle-version.txt').read_text(), re.M)[1]
record = dict(core_revision=sys.argv[1], binding_revision=sys.argv[2], harness_revision=sys.argv[2],
    evidence_kind='source-build', harness_sha256=digest.hexdigest(),
    binding_aar_sha256=sha(root / 'libs/minigraf.aar'),
    workflow_sha256=sha('.github/workflows/qualification-858-android.yml'),
    native_artifacts=native, slowdown_flag='repeat-timed-operation-twice',
    cargo_lock_sha256=sha('Cargo.lock'),
    rustc=subprocess.check_output(['rustc', '--version'], text=True).strip(),
    cargo=subprocess.check_output(['cargo', '--version'], text=True).strip(),
    cargo_ndk=subprocess.check_output(['cargo', 'ndk', '--version'], text=True).strip(),
    rustflags=os.environ.get('RUSTFLAGS', ''),
    native_build='cargo ndk -t arm64-v8a -t x86_64 --platform 24 build --locked --release --lib',
    abis=['arm64-v8a', 'x86_64'], profile='Release',
    ndk=next(line.split('=', 1)[1].strip() for line in
        (pathlib.Path(os.environ['ANDROID_NDK_HOME']) / 'source.properties').read_text().splitlines()
        if line.startswith('Pkg.Revision')),
    java=subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True).splitlines()[0],
    gradle=gradle, android_gradle_plugin=agp, kotlin='2.0.21',
    compile_sdk=34, min_sdk=24)
(root / 'src/main/assets/build.json').write_text(json.dumps(record, indent=2) + '\n')
PY
bash android/gradlew -p bench/device-farm --no-daemon --max-workers=2 -Dorg.gradle.jvmargs=-Xmx2g testReleaseUnitTest --tests io.github.project_minigraf.benchmark.ResultChecksTest assembleRelease assembleReleaseAndroidTest
cp Cargo.lock "$evidence/Cargo.lock"
cp bench/device-farm/src/main/assets/build.json "$evidence/build.json"
sha256sum bench/device-farm/build/outputs/apk/release/*.apk \
    bench/device-farm/build/outputs/apk/androidTest/release/*.apk > "$evidence/apks.sha256"
printf 'APKs and provenance: %s/bench/device-farm/build\n' "$binding_dir"
# Ensure AGP did not strip/change the bytes whose hashes the runtime verifies.
python3 - <<'PYAPK'
import hashlib, json, pathlib, zipfile
root = pathlib.Path('bench/device-farm')
build = json.loads((root/'build/evidence/build.json').read_text())
for apk in (root/'build/outputs/apk/release').glob('*.apk'):
    with zipfile.ZipFile(apk) as archive:
        for abi, entry in build['native_artifacts'].items():
            assert hashlib.sha256(archive.read('lib/'+abi+'/libminigraf_ffi.so')).hexdigest() == entry['sha256']
PYAPK
