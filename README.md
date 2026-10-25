# minigraf-android

Android binding for [Minigraf](https://github.com/project-minigraf/minigraf) — zero-config,
single-file, embedded bi-temporal graph database with Datalog queries.

## Installation

```kotlin
dependencies {
    implementation("io.github.project-minigraf:minigraf-android:2.0.8")
}
```

Minimum SDK: 24 (Android 7.0). Supports arm64-v8a, armeabi-v7a, x86_64.

## Quick start

```kotlin
import io.github.project_minigraf.minigraf.MiniGrafDb

val db = MiniGrafDb.openInMemory()
val result = db.execute("""(transact [[:alice :name "Alice"]])""")
println(result)  // {"transacted":<tx id>}
```

From v3.0.0 the classes are in `io.github.project_minigraf.minigraf`, the same package as
[minigraf-jvm](https://github.com/project-minigraf/minigraf-java). 2.x used `uniffi.minigraf_ffi`;
upgrading means changing those imports.

## Open options, cursors, the fact log and the log writer

```kotlin
import io.github.project_minigraf.minigraf.*

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
`Long.MAX_VALUE` means forever. `walCheckpointThreshold = Long.MAX_VALUE` turns off automatic
checkpoints and the checkpoint on close. Error messages start with their code, such as `[API-015]`.

`OpenOptions(queryMemoryLimit = bytes)` caps the bytes one query may hold, counted per
entry by the operators that keep state (join build sides, negation and `or` tables,
distinct sets, aggregate groups, window rows, rule-derived facts). A query that would hold
more throws `MiniGrafException.Query` with QRY-012 and frees what it held. The default, and
`Long.MAX_VALUE`, is no limit. Rows a cursor returns are not counted, so read a large
answer with `query()`.

## Prepared queries

`db.prepare(text)` parses a query once; run it with its `$slots` bound (names without
the `$`). Each run reads the database as it is then, and a prepared query keeps its
database open until both are closed.

```kotlin
val pq = db.prepare("(query [:find ?n :where [?e :age \$age] [?e :name ?n]])")
val thirty = pq.execute("age" to 30)
pq.query("age" to 40).use { cursor -> /* nextBatch() */ }
```

`Boolean`, `Byte`/`Short`/`Int`/`Long`, `Float`/`Double`, `String`, `null` and
`java.util.UUID` (an entity, which also fits value slots as a ref) bind as they are.
For the other kinds pass a `MiniGrafValue` (`Keyword`, `Ref`, a whole-number `Float64`)
or a `MiniGrafBindValue` (`Entity`, `TxCount` or `Timestamp` for `:as-of`,
`AnyValidTime` for `:valid-at`). Any other type throws `IllegalArgumentException`. A
missing slot is `MiniGrafException.Api` with `[API-022]`, a slot in an attribute
position `[API-023]`, and a value of the wrong kind `[API-024]`.

A `Set` binds a set value, for `in?` and the other set predicates or a set-valued
attribute: `pq.execute("ids" to setOf(1, 2, 3))`. Its elements are the plain values above
or a `MiniGrafValue` (`MiniGrafValue.Keyword(":role/admin")`), and a `UUID` element is a
ref. A set inside a set is `MiniGrafException.Api` with `[API-021]`; another kind of
element, or a `List`, throws `IllegalArgumentException`. Set values come back as JSON
arrays from `execute` and as `MiniGrafValue.Set` in fact records.

Errors are `MiniGrafException.Parse`, `.Query`, `.Storage`, `.Api` (a bad argument, a
closed object, a bind mistake) or `.Other`.

## User functions

A predicate implements `MiniGrafPredicate` (`test(value): Boolean`) and is called in
Datalog as `[(name ?v)]`. An aggregate implements `MiniGrafAggregate`; its
`accumulator()` returns a new `MiniGrafAccumulator` (`step(value)`, `finish(count)`) for
each group or window partition, and it is used as `(name ?v)` in `:find` or with
`:over`. Values arrive as `MiniGrafValue` (`Int64`, `Text`, …, with the value in
`value`), and `finish` returns one.

```kotlin
object Adult : MiniGrafPredicate {
    override fun test(value: MiniGrafValue): Boolean = when (value) {
        is MiniGrafValue.Int64 -> value.value >= 18
        else -> throw MiniGrafUdfException.Failed("age is not an integer")
    }
}

object Product : MiniGrafAggregate {
    override fun accumulator(): MiniGrafAccumulator = object : MiniGrafAccumulator {
        private var product = 1L
        override fun step(value: MiniGrafValue) { product *= (value as MiniGrafValue.Int64).value }
        override fun finish(count: Long): MiniGrafValue = MiniGrafValue.Int64(product) // count: values stepped
    }
}

db.registerPredicate("adult?", Adult)
db.registerAggregate("product", Product)
db.execute("(query [:find ?n :where [?e :age ?a] [(adult? ?a)] [?e :name ?n]])")
db.execute("(query [:find ?g (product ?a) :where [?e :group ?g] [?e :age ?a]])")
db.execute("(query [:find ?a (product ?a :over (:order-by ?a)) :where [?e :age ?a]])")
```

- **Failures.** A callback that throws stops the query with `QRY-014`, raised as
  `MiniGrafException.Query`; it is never read as `false` or a missing value. Throw
  `MiniGrafUdfException.Failed(msg)` to choose the message. Any other exception also
  fails the call, with its first line (class and message, such as
  `java.lang.IllegalArgumentException: bad`) as the message. A `MiniGrafValue.Ref` from
  `finish` whose value is not a UUID is a failing call too.
- **Lifecycle.** The database keeps a strong reference to each registered object until
  the database and every cursor and prepared query opened from it are closed. There is
  no unregister. Predicates and aggregates have separate names, and registering a name
  twice in either is an error (`INT-040`). A query sees the functions registered when it
  opened; a prepared query, those registered when each run starts.
- **Threading.** A callback runs on the thread that calls `execute` (of the database or
  a prepared query) or a cursor's `nextBatch`, including a prepared query's cursor.
  Queries on different threads may call the same object at once, so it must be
  thread-safe. One accumulator is used by one query on one thread at a time. Keep
  callbacks short: a query on the main thread blocks it for as long as they run.
- **Cost.** Each call crosses the FFI once: one JNA call per value.
- **Re-entry.** A callback may query the same database, open a cursor or register another
  function. Inside a write transaction, the calls the core refuses there still return
  `INT-001`.

## Building from source

Requires Rust stable toolchain, Android NDK, and JDK 17.

```bash
cargo install cargo-ndk --locked
cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 build --release
for pair in arm64-v8a:aarch64-linux-android armeabi-v7a:armv7-linux-androideabi x86_64:x86_64-linux-android; do
  mkdir -p "android/jniLibs/${pair%%:*}"
  cp "target/${pair#*:}/release/libminigraf_ffi.so" "android/jniLibs/${pair%%:*}/"
done
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
