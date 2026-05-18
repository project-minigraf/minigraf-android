# minigraf-android

Android binding for [Minigraf](https://github.com/project-minigraf/minigraf) — zero-config,
single-file, embedded bi-temporal graph database with Datalog queries.

## Installation

```kotlin
dependencies {
    implementation("io.github.project-minigraf:minigraf-android:1.1.1")
}
```

Minimum SDK: 24 (Android 7.0). Supports arm64-v8a, armeabi-v7a, x86_64.

## Quick start

```kotlin
import uniffi.minigraf_ffi.MiniGrafDb

val db = MiniGrafDb.openInMemory()
val result = db.execute("""(transact [[:alice :name "Alice"]])""")
println(result)  // {"transacted":1}
```

## Building from source

Requires Rust stable toolchain, Android NDK, and JDK 17.

```bash
cargo install cargo-ndk --locked
cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 -o android/jniLibs build --release
cargo run --bin uniffi-bindgen -- generate \
  --library target/aarch64-linux-android/release/libminigraf_ffi.so \
  --language kotlin \
  --out-dir android/src/main/java/
cd android && ./gradlew assembleRelease
```

## Cascade release

This repo receives a `core-release` repository_dispatch from the minigraf monorepo
cascade whenever a new version of the `minigraf` core crate is published. The release
workflow pins the new version, builds JNI libraries for all Android ABIs, and
publishes the AAR to Maven Central.

## License

MIT OR Apache-2.0
