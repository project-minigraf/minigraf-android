#!/usr/bin/env python3
"""Validate exactly one qualification stream; retain lossless records and schema entries.

Use either external-files JSONL OR one logcat export, never their concatenation. No
latency-based filtering. A failed suite invalidates all fourteen case entries.
Exit 1 means no valid stream (eligible for the protocol's bounded retry).
"""
import argparse
import json
import math
from pathlib import Path
import re
import statistics

CASES = (
    'prepared_execute/1k', 'cursor_batch_1/1k', 'cursor_batch_256/1k',
    'set_roundtrip/2', 'predicate/1k', 'aggregate/1k', 'prepare/point',
    'register_predicate/first', 'register_aggregate/first', 'fact_log_batch_256/1k',
    'options_error/negative_cache', 'options_readonly_open/1k', 'file_transact/1k',
    'log_writer_append_finish/1k',
)
PREFIX = 'binding/android/'
IDENTITY = ('core_revision', 'binding_revision', 'harness_revision', 'harness_sha256')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def finite_float(text):
    value = float(text)
    require(math.isfinite(value), 'nonfinite JSON number')
    return value


def invalid_constant(text):
    raise ValueError('nonfinite JSON constant: ' + text)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def parse_run(stream, build, *, set_name, run_index, attempt, platform, exit_code):
    require(set_name in ('B1', 'B2', 'V'), 'unknown set')
    require(type(run_index) is int and 1 <= run_index <= 6, 'run index outside 1..6')
    require(type(attempt) is int and 1 <= attempt <= 3, 'attempt outside 1..3')
    require(platform in ('physical', 'emulator'), 'unknown platform')
    variant = 'slowdown' if set_name == 'V' else 'baseline'
    records, environment, runtime, reason = [], None, None, ''
    samples = {case: [] for case in CASES}
    try:
        for line in stream.splitlines():
            if 'MinigrafBench' in line:
                match = re.search(r'MinigrafBench(?:\(\s*\d+\))?\s*:\s*(.*)$', line)
                require(match is not None, 'malformed tagged logcat record')
                line = match.group(1)
            elif not line.lstrip().startswith('{'):
                continue
            record = json.loads(line, object_pairs_hook=unique_object,
                                parse_float=finite_float, parse_constant=invalid_constant)
            require(isinstance(record, dict), 'nonobject record')
            records.append(record)
        require(exit_code == 0, f'process/teardown failed (exit {exit_code})')
        require(len(records) == 157, 'missing, extra or duplicate records')
        environment, runtime = records[:2]
        require(environment.get('type') == 'environment', 'missing initial environment')
        require(runtime.get('type') == 'runtime', 'missing runtime identity')
        require(build['profile'] == environment.get('profile') == 'Release', 'not Release')
        require(build.get('slowdown_flag') == 'repeat-timed-operation-twice', 'wrong source flag')
        require(environment.get('double_work') is (set_name == 'V'), 'wrong slowdown flag state')
        for record in (environment, records[-1]):
            require(record.get('mode') == 'qualification', 'mixed/nonqualification mode')
            require(record.get('variant') == variant, 'wrong variant for set')
            require(record.get('platform') == platform, 'wrong platform')
        identity = environment['build']
        require(identity == build, 'embedded build differs from supplied manifest')
        for key in IDENTITY:
            length = 64 if key.endswith('sha256') else 40
            require(re.fullmatch('[0-9a-f]{%d}' % length, identity[key]) is not None,
                    'invalid ' + key)
            require(identity[key] == build[key], 'mismatched ' + key)
        for field in ('fingerprint', 'hardware', 'product', 'ro_kernel_qemu', 'ro_boot_qemu',
                      'abis', 'model', 'sdk', 'os', 'loaded_abi', 'native_sha256'):
            require(environment.get(field) == runtime[field], 'conflicting environment/runtime ' + field)
        abi = runtime['loaded_abi']
        require(abi in ('arm64-v8a', 'x86_64') and abi in runtime['abis'], 'wrong executed ABI')
        artifact = build['native_artifacts'][abi]['sha256']
        require(re.fullmatch('[0-9a-f]{64}', artifact) is not None, 'invalid native hash')
        require(runtime.get('native_sha256') == artifact, 'wrong executed native artifact')
        require(runtime.get('native_identity') == 'proc-maps-extracted-elf', 'missing loaded-library evidence')
        require(runtime.get('platform') == platform, 'runtime platform mismatch')
        for field in ('fingerprint', 'hardware', 'product', 'model', 'os'):
            require(isinstance(runtime.get(field), str) and runtime[field], 'missing runtime ' + field)
        require(type(runtime.get('sdk')) is int and runtime['sdk'] == 34 and runtime['os'] == '14',
                'study requires Android 14 / API 34')
        kernel, boot = runtime['ro_kernel_qemu'], runtime['ro_boot_qemu']
        require(kernel in ('', '0', '1') and boot in ('', '0', '1') and
                {kernel, boot} != {'0', '1'}, 'conflicting qemu properties')
        qemu = kernel == '1' or boot == '1'
        virtual_hardware = runtime['hardware'].lower() in ('ranchu', 'goldfish', 'qemu', 'vbox86')
        virtual_product = any(token in runtime[field].lower() for field in ('product', 'fingerprint', 'model')
                              for token in ('sdk', 'emulator', 'generic', 'vbox', 'goldfish', 'ranchu'))
        if platform == 'emulator':
            require(qemu and (virtual_hardware or virtual_product), 'uncorroborated emulator identity')
        else:
            require(not qemu and not virtual_hardware and not virtual_product and abi == 'arm64-v8a',
                    'uncorroborated physical identity')
            require(runtime['model'] == 'Pixel 7', 'not the pre-registered physical model')
        require(environment.get('run_id'), 'missing process run identity')
        complete = records[-1]
        require(complete.get('type') == 'complete' and complete.get('count') == 14,
                'missing completion after teardown')
        require(complete.get('run_id') == environment['run_id'], 'mixed run identities')
        require(complete.get('ids') == [PREFIX + case for case in CASES], 'wrong completed case IDs')
        offset = 2
        for case in CASES:
            full_id = PREFIX + case
            iterations = 1 if case in ('file_transact/1k', 'log_writer_append_finish/1k') else 20
            for index in range(10):
                sample = records[offset]
                offset += 1
                require(sample.get('type') == 'sample' and sample.get('id') == full_id,
                        'wrong case/sample order')
                require(type(sample.get('sample')) is int and sample['sample'] == index,
                        'missing/duplicate sample')
                require(type(sample.get('iterations')) is int and sample['iterations'] == iterations,
                        'changed logical denominator')
                require(positive(sample.get('total_ns')) and positive(sample.get('ns_per_op')),
                        'nonpositive/nonfinite timing')
                mean = sample['total_ns'] / iterations
                require(mean == sample['ns_per_op'], 'mean differs from total / iterations')
                samples[case].append(mean)
            checked = records[offset]
            offset += 1
            require(checked.get('type') == 'checked' and checked.get('id') == full_id,
                    'missing exact-result check')
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        reason = 'no valid stream: ' + str(error)
    valid = not reason
    cases = {}
    for case in CASES:
        entry = dict(run_index=run_index, attempt=attempt, valid=valid, reason=reason,
                     value_ns=statistics.median(samples[case]) if valid else None)
        if samples[case]:
            entry['sample_means_ns'] = samples[case]
        cases[case] = entry
    return dict(schema_version=1, set=set_name, valid=valid, reason=reason,
                environment=environment, runtime=runtime, cases=cases, records=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stream', type=Path)
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--set', dest='set_name', required=True, choices=('B1', 'B2', 'V'))
    parser.add_argument('--run-index', required=True, type=int)
    parser.add_argument('--attempt', required=True, type=int)
    parser.add_argument('--platform', required=True, choices=('physical', 'emulator'))
    parser.add_argument('--exit-code', required=True, type=int,
                        help='actual instrumentation/provider success status; a stream alone is insufficient')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = parse_run(args.stream.read_text(), json.loads(args.build.read_text()),
                       set_name=args.set_name, run_index=args.run_index, attempt=args.attempt,
                       platform=args.platform, exit_code=args.exit_code)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return 0 if result['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
