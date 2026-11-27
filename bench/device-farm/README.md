# Android Device Farm harness and #858 qualification

This unpublished harness runs the same 14 exact-result cases on physical Android
and Android emulators. It changes no production binding API or dependency and
makes no RSS claim. Emulator timings are **experimental qualification only**,
never #839 release evidence or an activated nightly lane. No Bencher submission
is performed. Actual matched physical/emulator collections and AC12 decisions
remain necessary to complete mission #858 Part B.

## Three modes

| Mode | Explicit instrumentation selection | Work |
| --- | --- | --- |
| Correctness (default) | `BenchmarkTest#verifyAndMeasure`, no mode argument | 14 untimed cases, exact checks, no samples |
| #839 benchmark | `BenchmarkTest#verifyAndMeasure`, `-e mode benchmark` | Original timings, physical identity required |
| #858 qualification | `BenchmarkTest#testQualificationBaseline` for B1/B2; `BenchmarkTest#testQualificationSlowdown` for V | Timed, physical or emulator identity, experimental only |

Always select **one method**, including correctness runs. Running discovery over
all methods would also execute qualification. B1 and B2 deliberately share a
test method: their labels come from the fixed collection schedule, not an app
argument. V is selected by its distinct test method, never a provider argument.

## Build once for physical and emulator

Use disposable source checkouts, Java 17, Rust (workflow: 1.99.1), cargo-ndk
(workflow: 3.5.4), SDK platform/build-tools 34 and NDK 27.2.12479018:

```sh
export ANDROID_HOME=/path/to/sdk
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/27.2.12479018"
rustup target add aarch64-linux-android x86_64-linux-android
bash bench/device-farm/build.sh /path/to/core-checkout FULL_40_CHARACTER_CORE_SHA
```

`build.sh` requires the explicit pinned SHA, checks clean Git checkouts and core
resolution, and builds both `arm64-v8a` and `x86_64` from the same sources. For
archives without `.git`, supply `CORE_REVISION` and `BINDING_REVISION`; these
are archive provenance assertions, not cryptographic verification of the
archive's revision. Retain the source archives. The harness revision is the
binding revision, augmented by a hash of the harness source tree and workflow.
Use a fresh copy for each build; existing build output is refused.

The one universal Release application APK contains both ABIs; Pixel 7 loads
arm64-v8a and the x86_64 emulator loads its own library. Use the application APK
under `build/outputs/apk/release/` and instrumentation APK under
`build/outputs/apk/androidTest/release/`. `build/evidence/build.json` records
core/binding/harness revisions, source/AAR/Cargo.lock/workflow hashes, separate
native hashes by ABI, Release profile, source flag, Rust, JDK, Gradle, AGP, Kotlin
and NDK versions. Packaging preserves native bytes; the build checks both the
AAR and APK against those hashes. JNI libraries are extracted for runtime
identity verification. This is source-build evidence, not Maven certification.
Builds run only harness JVM tests, never timed instrumentation. Every Gradle
invocation uses `--max-workers=2 -Dorg.gradle.jvmargs=-Xmx2g`, sequentially.

## Runtime identity and boundaries

Every environment record has `platform`, `mode`, `variant`, `double_work` and a
fresh UUID. Environment and runtime records both include Build fingerprint,
hardware, product, model, supported ABIs, SDK and OS, `ro.kernel.qemu`,
`ro.boot.qemu`, and the loaded ABI and native hash. The parser checks they agree. Classification requires corroborating evidence; unknown or
contradictory identities fail. A loaded library is proved by `/proc/self/maps`,
its extracted file's ELF machine supplies the **actually loaded ABI**, and the
SHA-256 of those bytes must match that ABI's build-manifest entry. Unprovable
mappings or hash mismatches fail; the device hash is never reused for x86_64.
The #839 method refuses emulator identity with an explicit physical-only error.

Three warmups precede ten sample means per case. Each mean is the sum of 20
individually timed logical invocations divided by 20 (storage writes use one).
The clock is `SystemClock.elapsedRealtimeNanos`. Setup, full exact-result
validation, teardown and reporting remain outside timing. Completion is emitted
only after all fixture and scratch cleanup succeeds.

The harness-only `doubleWork` switch is set **only** by the slowdown method.
It wraps two real action executions in one timed interval without changing the
logical denominator. Both returned results are retained and fully validated
outside timing. First registrations, file transactions and LogWriter operations
receive two independent fixtures prepared outside timing; read-only opens use
two independently seeded equivalent files. Read-only queries share their
unchanging source fixture. Expected fractional slowdown is approximately +1.0
(documentation range 0.7–1.3 for compute/callback and allocation/conversion;
storage may differ); this expectation is not an extra gate.

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
selection pins a model/OS, not necessarily a unique physical unit. Historical
#839 acceptance and its recorded limitations remain unchanged; this new
qualification harness implies no further release or maintainer sign-off.

## Hosted workflow and acceleration

`.github/workflows/qualification-858-android.yml` runs on `ubuntu-24.04` from
`workflow_dispatch` or a push to `feat/858-qualification` touching
`bench/device-farm/qualification/run-config.json`. Dispatch inputs override the
file; push uses its `core_ref` (full lowercase SHA), `schedule: "B1,V,B2"`, and
boolean `collect`. **Default `collect: false` builds and runs correctness only.**
The initial core pin comes from this binding snapshot's Cargo.toml; choose the
matched study core pin and commit the configuration before collection.

The candidate is Google APIs **API 34 / Android 14, x86_64, pixel_7** on an
x86_64 host, with two emulator CPUs and 2048 MB guest memory. SDK package
revisions are resolved and recorded before timing (`source.properties` for
both emulator and image, plus full `emulator -version` output). They are held
fixed throughout the collection and compared before every attempt. These
resolved versions, runner image, host kernel, guest fingerprint and build
manifest define the configuration; a later job resolving different versions
needs a new configuration ID and qualification, never pooled data.

The workflow enables KVM. The collector records `/dev/kvm` presence,
`emulator -accel-check` output/status, guest properties, and **open `/dev/kvm`,
KVM VM and vCPU descriptors in the running QEMU process**. Collection fails
unless all evidence agrees on active KVM and x86_64 guest/host. This is an
empirical active-VM check, not merely `-accel on` or availability. Translation
is explicitly recorded as none for x86_64 on x86_64; other architectures are
refused. If procfs permissions hide evidence, collection fails closed.

One cold boot uses `-wipe-data -no-snapshot -accel on`, no snapshot restore/save.
The same warm guest remains for smoke and all batches. This measures fresh
**app processes**, not cold guest/OS startup. Before every attempt both app and
test packages are force-stopped, stale JSONL is removed, logcat is cleared,
and a fresh sequential `adb shell am instrument` starts. No parallel tests.
The fixed order is `(B1,V,B2) × 6`, six independent runs per set. Retry only an
invalid stream, at most two retries (three attempts), in its original slot.
Every attempt gets an initial interrupted receipt, raw logcat, instrumentation
output, runtime evidence, parsed JSON, elapsed time and final reason. Valid
streams are never retried, discarded, or selected by latency.

Artifacts include raw logs, per-run JSON, manifests, APKs, unit-test reports,
build/runtime metadata and `SHA256SUMS`, even after failure. Build and collection
durations are observed; queue time is unavailable locally (retain Actions
queue timestamps separately). Archive beyond the 90-day Actions retention and
verify checksums before deleting scratch.

## Device Farm selection and what is verified

Target **Pixel 7 / Android 14 / arm64-v8a**, test type Android Instrumentation.
Upload the same built app/test APKs. Run correctness first. Select only the
fully qualified method `io.github.project_minigraf.benchmark.BenchmarkTest#verifyAndMeasure`.
For qualification select `...BenchmarkTest#testQualificationBaseline` for B1
and B2 or `...BenchmarkTest#testQualificationSlowdown` for V. Do not send a
variant parameter. Preserve the same `(B1,V,B2) × 6` order and retry policy on
physical hardware, each attempt a fresh instrumentation/app process.

**Verified locally:** these are distinct public JUnit test methods; the
collector constructs AndroidJUnitRunner's `-e class CLASS#METHOD` selection;
the synthetic parser checks exact case coverage, flags, ABI/hash, complete
stream and caller-supplied provider success. The existing local #839 archive
(`minigraf/docs/benchmarks/839-bindings/results.md`) records that iOS selection
used top-level `test.filter`, and that `test.parameters.filter` failed to select.
That iOS observation does **not** verify Android selection.

**Assumed, not verified here:** Device Farm's current Android Instrumentation
`ScheduleRun.test.filter` accepts/passes a single `CLASS#METHOD` filter (or the
console's equivalent selection). No network/provider/API documentation was
queried under this task's offline constraint. Confirm this exact syntax and
selected-test count against Device Farm's current Instrumentation filter
options before timing. A custom test specification may invoke the explicit
AndroidJUnitRunner class/method command while retaining provider installation
and reporting steps, but that provider integration also needs verification.
Never use `test.parameters.filter` as an assumed substitute. The #839 custom
spec's `-e mode benchmark` remains available for physical-only historical mode.

No timing from an unfiltered job is eligible. A Device Farm PASS alone is
insufficient: retain provider/JUnit success plus exactly one complete stream.
Record actual device model/OS/fingerprint, public provider configuration,
queue/run minutes and available thermal/power conditions. Private device,
account and provider IDs must not enter public artifacts. Physical selection
availability and matching builds are not established by this local change.

## Parsing and local controls

```sh
python3 -B -m unittest discover -s bench/device-farm/qualification -p 'test_*.py'
bash android/gradlew -p bench/device-farm --no-daemon --max-workers=2 \
  -Dorg.gradle.jvmargs=-Xmx2g testReleaseUnitTest \
  --tests io.github.project_minigraf.benchmark.ResultChecksTest
# SDK-free alternative: Gradle 8.11, using its bundled Kotlin compiler/JUnit.
gradle -p bench/device-farm/unit-tests --offline --no-daemon --max-workers=2 \
  -Dorg.gradle.jvmargs=-Xmx2g test
python3 bench/device-farm/qualification/parse_samples.py raw.log \
  --build bench/device-farm/build/evidence/build.json --platform physical \
  --set B1 --run-index 1 --attempt 1 --exit-code 0 --output run.json
```

Use `--platform emulator` for hosted streams. `--exit-code 0` asserts actual
provider/test success **including teardown**; never infer it from samples or
an adb transport exit alone. Parse exactly one JSONL file OR one logcat export,
not their concatenation. Invalid/mixed/truncated/duplicated streams invalidate
all fourteen cases and retain reasons and any parsed partial samples.

`run.json.cases[CASE]` is the SCHEMA.md per-run entry: `run_index`, `attempt`,
`valid`, `reason`, `value_ns` (median of ten original means), `sample_means_ns`.
Append every attempt to the matching configuration's `cases[CASE].sets[SET]`
in the canonical raw-samples envelope, retaining all original logs. The
configuration uses `platform: android`, `kind: physical` or `simulated`, and
its build uses the **executed ABI hash** for B1/B2/V. Flatten public runtime
pins to nonempty string values as SCHEMA.md requires; include the host/KVM/
image evidence from `runtime.json` alongside instrumentation identity. Review
immutable provenance before merging attempts. This converter does not decide
qualification, change pre-registered thresholds, or activate nightly lanes.

These representative cases leave other options/errors, broader FactLog shapes,
scaling and memory bounds unmeasured. The binding has no
`transaction_chunk_facts` option. Historical #839 sign-offs are unchanged.
