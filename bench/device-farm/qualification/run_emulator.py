#!/usr/bin/env python3
"""Single-emulator #858 collection. No Bencher; all attempts retained, no latency filtering."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

from parse_samples import parse_run

APP = 'io.github.project_minigraf.benchmark'
RUNNER = APP + '.test/androidx.test.runner.AndroidJUnitRunner'
TEST_CLASS = APP + '.BenchmarkTest#'
IMAGE = 'system-images;android-34;google_apis;x86_64'
AVD = 'minigraf858'
BOOT_POLICY = 'one cold boot with -no-snapshot; warm guest retained; force-stop app and test package before every attempt'


def slots(schedule):
    if schedule != 'B1,V,B2':
        raise ValueError('pre-registered schedule is (B1,V,B2) x6')
    return [(index, name) for index in range(1, 7) for name in ('B1', 'V', 'B2')]


def collect(schedule, execute):
    complete = True
    for index, name in slots(schedule):
        for attempt in range(1, 4):
            if execute(index, name, attempt):
                break
        else:
            complete = False
    return complete


def resolve_config(config, event, inputs):
    if event == 'workflow_dispatch':
        config = dict(core_ref=inputs['core_ref'], schedule=inputs['schedule'],
                      collect={'true': True, 'false': False}[inputs['collect']])
    elif event != 'push':
        raise ValueError('unsupported event')
    if not re.fullmatch('[0-9a-f]{40}', config.get('core_ref', '')):
        raise ValueError('core_ref must be a full lowercase SHA')
    slots(config['schedule'])
    if type(config.get('collect')) is not bool:
        raise ValueError('collect must be a boolean')
    return config


def acceleration_active(*, kvm_exists, accel_code, accel_output, host, guest,
                        kernel_qemu, boot_qemu, hardware, fd_targets):
    return (kvm_exists and accel_code == 0 and 'KVM' in accel_output and
            'usable' in accel_output.lower() and host == guest == 'x86_64' and
            kernel_qemu in ('', '1') and boot_qemu in ('', '1') and
            '1' in (kernel_qemu, boot_qemu) and hardware in ('ranchu', 'goldfish') and
            '/dev/kvm' in fd_targets and any('kvm-vm' in x for x in fd_targets) and
            any('kvm-vcpu' in x for x in fd_targets))


def instrumentation_ok(text, code):
    return (code == 0 and re.search(r'^OK \(1 test\)\s*$', text, re.M) is not None and
            re.search(r'^INSTRUMENTATION_CODE: -1\s*$', text, re.M) is not None and
            not any(s in text for s in ('FAILURES!!!', 'INSTRUMENTATION_FAILED', 'shortMsg=')))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def command(*args, timeout=120):
    return subprocess.check_output(args, text=True, stdin=subprocess.DEVNULL,
                                   stderr=subprocess.STDOUT, timeout=timeout).strip()


def adb(*args, timeout=120):
    return command('adb', '-e', *args, timeout=timeout)


def properties(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines()
                if '=' in line and not line.startswith('#'))


def evidence(sdk):
    emulator = sdk / 'emulator/emulator'
    accel = subprocess.run([str(emulator), '-accel-check'], text=True, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    guest = {key: adb('shell', 'getprop', key) for key in (
        'ro.kernel.qemu', 'ro.boot.qemu', 'ro.hardware', 'ro.product.cpu.abi',
        'ro.product.cpu.abilist', 'ro.build.fingerprint', 'ro.product.model',
        'ro.product.name', 'ro.build.version.sdk', 'ro.build.version.release')}
    # Availability alone is insufficient: the live QEMU must own a KVM VM and vCPU.
    targets = set()
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            cmdline = (process/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if 'qemu-system-x86_64' not in cmdline or AVD not in cmdline:
                continue
            for fd in (process/'fd').iterdir():
                try:
                    target = os.readlink(fd)
                    if 'kvm' in target:
                        targets.add(target)
                except OSError:
                    pass
        except OSError:
            continue
    active = acceleration_active(kvm_exists=Path('/dev/kvm').exists(), accel_code=accel.returncode,
        accel_output=accel.stdout, host=platform.machine(), guest=guest['ro.product.cpu.abi'],
        kernel_qemu=guest['ro.kernel.qemu'], boot_qemu=guest['ro.boot.qemu'],
        hardware=guest['ro.hardware'], fd_targets=targets)
    version_output = command(str(emulator), '-version')
    version = re.search(r'Android emulator version[^\n]+', version_output)
    if version is None:
        raise ValueError('cannot identify exact emulator version/build')
    return dict(kvm_present=Path('/dev/kvm').exists(), accel_check_exit=accel.returncode,
        accel_check_output=accel.stdout, live_kvm_fd_targets=sorted(targets), acceleration_active=active,
        backend='KVM', host_kernel=platform.release(), host_arch=platform.machine(), guest=guest,
        translation='none: x86_64 guest on x86_64 host' if platform.machine() == guest['ro.product.cpu.abi'] == 'x86_64'
                    else 'unsupported architecture or translation; collection forbidden',
        emulator_version=version.group(0), emulator_version_output=version_output,
        emulator_package=properties(sdk/'emulator/source.properties'),
        system_image_package=properties(sdk/'system-images/android-34/google_apis/x86_64/source.properties'),
        image=IMAGE, device_profile='pixel_7', boot_policy=BOOT_POLICY,
        runner_image=os.environ.get('ImageVersion', 'unavailable'))


def execute_test(method, destination):
    """Force-stop both packages; every invocation launches a new instrumentation process."""
    status, failure = 1, ''
    cmd = ['adb', '-e', 'shell', 'am', 'instrument', '-w', '-r', '-e', 'class', TEST_CLASS+method, RUNNER]
    capture = None
    raw_path = destination/'raw.log'
    with (destination/'instrumentation.log').open('w') as log, raw_path.open('w') as raw:
        try:
            for package in (APP, APP+'.test'):
                adb('shell', 'am', 'force-stop', package)
            # A failed prior attempt must not leave an external-files JSONL eligible for reuse.
            adb('shell', 'rm', '-f', '/sdcard/Android/data/'+APP+'/files/minigraf-bench.jsonl')
            adb('logcat', '-c')
            # Stream continuously: long cases must not lose environment records to ring-buffer wrap.
            capture = subprocess.Popen(['adb', '-e', 'logcat', '-v', 'threadtime',
                '-s', 'MinigrafBench:I', '*:S'], stdin=subprocess.DEVNULL,
                stdout=raw, stderr=log)
            status = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, timeout=1200).returncode
            # Drain already emitted records before stopping logcat. This is outside all timers.
            deadline = time.monotonic()+5
            while time.monotonic() < deadline:
                if capture.poll() is not None:
                    raise RuntimeError('logcat capture exited before collection finished')
                if re.search(r'"type"\s*:\s*"complete"', raw_path.read_text(errors='replace')):
                    break
                time.sleep(0.1)
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            failure = f'no valid stream: infrastructure failure: {type(error).__name__}: {error}'
            log.write('\n'+failure+'\n')
        finally:
            if capture is not None:
                capture.terminate()
                try:
                    capture.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    capture.kill()
                    capture.wait()
    text = (destination/'instrumentation.log').read_text(errors='replace')
    return (0 if not failure and instrumentation_ok(text, status) else 1), failure, cmd


def run(args):
    config = json.loads(args.config.read_text())
    slots(config['schedule'])
    if type(config['collect']) is not bool:
        raise ValueError('collect must be boolean')
    build = json.loads(args.build.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'config.json', config)
    sdk = Path(os.environ['ANDROID_HOME'])
    emulator = sdk/'emulator/emulator'
    cmd = [str(emulator), '-avd', AVD, '-port', '5554', '-no-window', '-no-audio',
           '-no-boot-anim', '-no-snapshot', '-wipe-data', '-accel', 'on', '-gpu', 'swiftshader_indirect',
           '-cores', '2', '-memory', '2048']
    write_json(args.output/'boot.json', dict(command=cmd, policy=BOOT_POLICY,
        started_utc=datetime.now(timezone.utc).isoformat()))
    with (args.output/'emulator.log').open('w') as log:
        process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            command('adb', 'start-server')
            adb('wait-for-device', timeout=240)
            deadline = time.monotonic()+240
            while adb('shell', 'getprop', 'sys.boot_completed') != '1':
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('emulator boot failed or timed out')
                time.sleep(2)
            pinned = evidence(sdk)
            write_json(args.output/'runtime.json', pinned)
            if config['collect'] and (not pinned['acceleration_active'] or pinned['runner_image'] == 'unavailable'):
                raise RuntimeError('qualification requires empirically active KVM and recorded runner image')
            if pinned['guest']['ro.build.version.sdk'] != '34' or pinned['guest']['ro.build.version.release'] != '14':
                raise RuntimeError('executing guest is not pinned API 34 / Android 14')
            adb('install', '-r', str(args.app))
            adb('install', '-r', str(args.test_apk))
            smoke = args.output/'smoke'
            smoke.mkdir()
            code, reason, _ = execute_test('verifyAndMeasure', smoke)
            records = []
            for line in (smoke/'raw.log').read_text().splitlines():
                if 'MinigrafBench:' in line:
                    records.append(json.loads(line.split('MinigrafBench:',1)[1]))
            if code or not records or records[-1].get('type') != 'complete' or records[-1].get('mode') != 'smoke' or records[-1].get('count') != 14 or any(r.get('type') == 'sample' for r in records):
                raise RuntimeError('correctness smoke failed: '+reason)
            if not config['collect']:
                return 0
            seen_ids = set()
            pinned_runtime = None

            def execute(index, name, attempt):
                nonlocal pinned_runtime
                destination = args.output/f'{index:02d}-{name}-attempt-{attempt}'
                destination.mkdir()
                started = datetime.now(timezone.utc).isoformat()
                begin = time.monotonic()
                method = 'testQualificationSlowdown' if name == 'V' else 'testQualificationBaseline'
                pending = parse_run('', build, set_name=name, run_index=index, attempt=attempt,
                                    platform='emulator', exit_code=1)
                pending['reason'] = 'no valid stream: attempt started; final result not recorded (interrupted if retained)'
                for entry in pending['cases'].values():
                    entry['reason'] = pending['reason']
                write_json(destination/'run.json', pending)
                receipt = dict(run_index=index, set=name, attempt=attempt, valid=False, reason=pending['reason'],
                    started_utc=started, test=method, boot_policy=BOOT_POLICY)
                write_json(destination/'attempt.json', receipt)
                code, reason, cmd = 1, '', []
                try:
                    current = evidence(sdk)
                    write_json(destination/'runtime.json', current)
                    stable = lambda record: {k:v for k,v in record.items() if k != 'emulator_version_output'}
                    if stable(current) != stable(pinned) or not current['acceleration_active']:
                        raise ValueError('runtime configuration or active acceleration changed')
                    code, reason, cmd = execute_test(method, destination)
                except (OSError, subprocess.SubprocessError, ValueError) as error:
                    reason = f'no valid stream: infrastructure failure: {error}'
                raw = destination/'raw.log'
                raw.touch(exist_ok=True)
                result = parse_run(raw.read_text(errors='replace'), build, set_name=name,
                    run_index=index, attempt=attempt, platform='emulator', exit_code=code)
                if result['valid']:
                    run_id = result['environment']['run_id']
                    if run_id in seen_ids:
                        reason = 'no valid stream: duplicate process run identity'
                    seen_ids.add(run_id)
                    runtime = result['runtime']
                    guest = pinned['guest']
                    if (runtime['fingerprint'] != guest['ro.build.fingerprint'] or
                        runtime['loaded_abi'] != guest['ro.product.cpu.abi']):
                        reason = 'no valid stream: instrumentation runtime differs from observed guest'
                    if pinned_runtime is None:
                        pinned_runtime = runtime
                    elif pinned_runtime != runtime:
                        reason = 'no valid stream: runtime drift during collection'
                if reason:
                    result.update(valid=False, reason=reason)
                    for entry in result['cases'].values():
                        entry.update(valid=False, reason=reason, value_ns=None)
                write_json(destination/'run.json', result)
                receipt.update(valid=result['valid'], reason=result['reason'], elapsed_seconds=time.monotonic()-begin,
                    exit_code=code, command=cmd)
                write_json(destination/'attempt.json', receipt)
                with (args.output/'attempts.jsonl').open('a') as output:
                    output.write(json.dumps(receipt, sort_keys=True)+'\n')
                print(f'{index} {name} attempt {attempt}: {"valid" if result["valid"] else result["reason"]}', flush=True)
                return result['valid']

            return 0 if collect(config['schedule'], execute) else 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('config', 'build', 'output', 'app', 'test-apk'):
        parser.add_argument('--'+field, type=lambda p: Path(p).resolve(), required=True)
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as error:
        if args.output.is_dir():
            write_json(args.output/'failure.json', dict(valid=False, reason=str(error),
                finished_utc=datetime.now(timezone.utc).isoformat()))
        raise


if __name__ == '__main__':
    raise SystemExit(main())
