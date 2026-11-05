# Android Device Farm qualification (#839)

This unpublished app measures the Android binding on a physical arm64 device.
It adds no production dependency or API. It aligns with Minigraf's reliability,
portability and simplicity principles. It does not establish a binding RSS bound.

Build from disposable core and Android binding checkouts with Java 17, Rust,
`cargo-ndk`, Android SDK platform/build-tools 34 and NDK 27.2.12479018:

```sh
export ANDROID_HOME=/path/to/sdk
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/27.2.12479018"
rustup target add aarch64-linux-android
bash bench/device-farm/build.sh /path/to/core-checkout
```

The script patches the core dependency only in the disposable checkout and
checks Cargo metadata. `CORE_REVISION` and `BINDING_REVISION` may identify
source archives that have no `.git`; otherwise git supplies their revisions.
Keep those archives with the build evidence. This is source-build evidence,
not verification of a published Maven package.

## First run: correctness

Upload the application APK under `build/outputs/apk/release/` and the test APK
under `build/outputs/apk/androidTest/release/` to Device Farm. Select Android
**Instrumentation**, the standard environment, one physical arm64 device
(Android API 24 or later), metered billing, and a 10-minute job timeout.
Keep the model and OS version fixed for subsequent runs.

The default mode is **smoke**. The sole JUnit test, `verifyAndMeasure`, executes
all 14 cases once and validates every result. It emits **no timing samples**.
Success requires both Device Farm's passing test status and the final
`MinigrafBench` JSON record with `type: complete`, `mode: smoke`, and 14 IDs.
A partial log or merely a successful install is not evidence of completion.

## Timed run

After smoke passes, use a custom instrumentation test specification and pass
`-e mode benchmark` to its `adb shell am instrument` invocation. Preserve the
AWS-provided installation, runner selection and reporting commands. The runner
is `io.github.project_minigraf.benchmark.test/androidx.test.runner.AndroidJUnitRunner`.

Each case runs three warmups and ten samples. In-memory cases average 20
individually timed invocations per sample; storage writes use one invocation.
The clock is `SystemClock.elapsedRealtimeNanos`. Fixture setup, validation,
cleanup and reporting are outside timing; host result conversion is inside.
Prepared objects and callbacks are created before the execution cases.

| Suffix under `binding/android/` | Timed work |
| --- | --- |
| `prepared_execute/1k` | Host integer bind, prepared point execution, JSON decoding |
| `cursor_batch_1/1k`, `cursor_batch_256/1k` | Prepared cursor open, full 1k-row drain and JSON decoding, close |
| `set_roundtrip/2` | Kotlin set bind, exact set lookup, returned set decoding |
| `predicate/1k` | Query, 1k Kotlin predicate callbacks and returned-row decoding |
| `aggregate/1k` | Query, Kotlin accumulator lifecycle and result decoding |
| `prepare/point` | Prepare a point query; execute and close outside timing |
| `register_predicate/first`, `register_aggregate/first` | Register once on a fresh database; fixture setup, query validation and close outside timing |
| `fact_log_batch_256/1k` | Open, drain and close a filtered fact log with typed host conversion |
| `options_error/negative_cache` | Reject negative page cache size and convert/catch API-017 |
| `options_readonly_open/1k` | Open a checkpointed file with read-only/cache/memory options; query and close outside timing |
| `file_transact/1k` | Commit 1k facts to a fresh file; open, validation and close outside timing |
| `log_writer_append_finish/1k` | Convert/append 1k typed records and finish; create and reopen verification outside timing |

The scalar fixture contains values 0 through 999, with count 1,000 and sum
499,500. Predicate results are exactly the 500 even values, sum 249,500. All
scalar rows are checked as an exact sorted list, preserving multiplicities.
The set is exactly `{1, 2}`. LogWriter output is checked against every input
record, including entity and temporal metadata. Storage uses the app's internal
files directory. Cache dropping and cold OS startup are not measured.

Raw JSONL is emitted to logcat with tag `MinigrafBench` and also saved at the
app's external-files path as `minigraf-bench.jsonl`. Retain the device log, JUnit
result, run/job/device metadata, both APKs, `build/evidence/`, the harness source,
and all samples. The embedded `build.json` identifies core/binding revisions,
the harness/AAR/native/Cargo.lock hashes, Rust version, ABI and build profile.

Record device model/OS/build, thermal and power conditions where available,
vendor instrumentation, session timestamps and any retries. Keep each runtime,
model/OS and build configuration in a separate history. Shared Device Farm
selection pins a model/OS, not necessarily a unique physical unit; obtain
maintainer disposition of that limitation before claiming #839's fixed-device
acceptance. No release or binding-maintainer sign-off is implied by this harness.

## Remaining scope

These are representative Android cases. Other options and error codes,
wider FactLog/LogWriter shapes, and sustained
storage/pinned-reader scaling remain unmeasured. Deliberate callback failures
remain correctness scope. The binding has no `transaction_chunk_facts` option.
JVM, Swift, WASI and browser follow-ups require their own evidence and sign-off.
