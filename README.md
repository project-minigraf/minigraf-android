# minigraf-android

Android binding for [Minigraf](https://github.com/project-minigraf/minigraf) — zero-config,
single-file, embedded bi-temporal graph database with Datalog queries.

## Installation

```kotlin
dependencies {
    implementation("io.github.project-minigraf:minigraf-android:1.2.0")
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

## Open options, cursors, the fact log and the log writer

```kotlin
import uniffi.minigraf_ffi.*

// Read-only: shared lock, nothing written; writes throw MiniGrafException (API-014).
val src = MiniGrafDb.openWithOptions(path, OpenOptions(readOnly = true, pageCacheSize = 4096))

// A cursor's answer is fixed when it opens. Each batch is a JSON array of rows,
// encoded like execute()'s "results"; null at the end.
src.query("(query [:find ?n :where [?e :name ?n]])").use { cursor ->
    while (true) {
        val batch = cursor.nextBatch(1000) ?: break
        // parse batch
    }
}

// Copy every fact version, keeping tx and valid-time bounds, into a new file.
MiniGrafLogWriter.create(newPath, OpenOptions()).use { out ->
    src.factLog(FactFilter()).use { log ->
        while (true) {
            val records = log.nextBatch(1000) ?: break
            out.appendBatch(records.filter { !it.attribute.startsWith(":secret/") })
        }
    }
    out.advanceTxCount(src.currentTxCount())
    out.finish()
}   // closing without finish() abandons the build and leaves no file
```

UniFFI objects are `AutoCloseable`: `close()` (or `use`) frees the native object. The
shim's own close methods are named `release()` (cursor, fact log) and `abandon()` (log
writer) here, because `close()` is taken. A record's value is a `MiniGrafValue`
(`Text`, `Int64`, `Float64`, `Bool`, `Ref`, `Keyword`, `Null`); a `validTo` of
`Long.MAX_VALUE` means forever. Error messages start with their code, such as `[API-015]`.

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
