import copy
import json
import unittest
from parse_samples import CASES, parse_run


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.build = dict(core_revision='a'*40, binding_revision='b'*40,
            harness_revision='b'*40, harness_sha256='c'*64, profile='Release',
            slowdown_flag='repeat-timed-operation-twice',
            native_artifacts={'arm64-v8a': {'sha256': 'd'*64}, 'x86_64': {'sha256': 'e'*64}})
        self.runtime = dict(type='runtime', platform='emulator', fingerprint='google/sdk_gphone64_x86_64:14',
            hardware='ranchu', product='sdk_gphone64_x86_64', ro_kernel_qemu='1', ro_boot_qemu='1',
            abis=['x86_64'], model='sdk_gphone64_x86_64', sdk=34, os='14',
            loaded_abi='x86_64', native_sha256='e'*64, native_identity='proc-maps-extracted-elf')
        self.env = dict(type='environment', mode='qualification', variant='baseline', platform='emulator',
            run_id='synthetic-run', profile='Release', double_work=False, build=self.build)
        self.env.update({key: self.runtime[key] for key in ('fingerprint', 'hardware', 'product',
            'ro_kernel_qemu', 'ro_boot_qemu', 'abis', 'model', 'sdk', 'os', 'loaded_abi', 'native_sha256')})
        self.records = [self.env, self.runtime]
        for case in CASES:
            iterations = 1 if case in ('file_transact/1k', 'log_writer_append_finish/1k') else 20
            for i in range(10):
                self.records.append(dict(type='sample', id='binding/android/'+case, sample=i,
                    iterations=iterations, total_ns=(i+1)*iterations, ns_per_op=float(i+1)))
            self.records.append(dict(type='checked', id='binding/android/'+case))
        self.records.append(dict(type='complete', mode='qualification', variant='baseline',
            platform='emulator', run_id='synthetic-run', count=14, ids=['binding/android/'+c for c in CASES]))

    def parse(self, records=None, platform='emulator', set_name='B1', exit_code=0, prefix='I/MinigrafBench(123): '):
        stream = '\n'.join(prefix+json.dumps(r) for r in (self.records if records is None else records))
        return parse_run(stream, self.build, set_name=set_name, run_index=1, attempt=1,
                         platform=platform, exit_code=exit_code)

    def test_median_and_original_samples_for_jsonl_and_logcat(self):
        for prefix in ('', 'I/MinigrafBench(123): ', '11-19 10:00:00.000 123 123 I MinigrafBench: '):
            result = self.parse(prefix=prefix)
            self.assertTrue(result['valid'], result['reason'])
            self.assertEqual(result['records'], self.records)
            for case in CASES:
                self.assertEqual(result['cases'][case]['value_ns'], 5.5)
                self.assertEqual(result['cases'][case]['sample_means_ns'], list(range(1, 11)))

    def test_physical_and_slowdown(self):
        self.runtime.update(platform='physical', fingerprint='google/panther/panther:14/release-keys',
            hardware='panther', product='panther', ro_kernel_qemu='', ro_boot_qemu='',
            abis=['arm64-v8a'], loaded_abi='arm64-v8a', model='Pixel 7', native_sha256='d'*64)
        self.env.update({key: self.runtime[key] for key in ('fingerprint', 'hardware', 'product',
            'ro_kernel_qemu', 'ro_boot_qemu', 'abis', 'model', 'sdk', 'os', 'loaded_abi', 'native_sha256')})
        self.env.update(platform='physical', variant='slowdown', double_work=True)
        self.records[-1].update(platform='physical', variant='slowdown')
        self.assertTrue(self.parse(platform='physical', set_name='V')['valid'])

    def test_invalid_streams_never_have_valid_case_values(self):
        bad = [self.records[:-1], self.records*2, self.records+[self.records[2]]]
        for index, field, value in ((0,'mode','smoke'), (0,'double_work',True), (0,'variant','slowdown'), (0,'loaded_abi','arm64-v8a'),
                (1,'native_sha256','d'*64), (1,'loaded_abi','arm64-v8a'), (1,'ro_kernel_qemu','0'),
                (1,'platform','physical'), (2,'iterations',40), (2,'ns_per_op',3),
                (2,'sample',1), (2,'total_ns',0), (-1,'ids',[]), (-1,'run_id','stale')):
            records = copy.deepcopy(self.records)
            records[index][field] = value
            bad.append(records)
        for records in bad:
            result = self.parse(records)
            self.assertFalse(result['valid'], records[:2])
            self.assertTrue(result['reason'])
            self.assertTrue(all(not c['valid'] and c['value_ns'] is None for c in result['cases'].values()))
        self.assertFalse(self.parse(exit_code=1)['valid'])

    def test_embedded_build_must_match_full_manifest(self):
        for key, value in (('profile', 'Debug'), ('slowdown_flag', 'other'),
                           ('native_artifacts', {'x86_64': {'sha256': 'f'*64}})):
            records = copy.deepcopy(self.records)
            records[0]['build'][key] = value
            self.assertFalse(self.parse(records)['valid'], key)

    def test_bad_json_and_nonfinite_values_are_invalid(self):
        for stream in ('MinigrafBench: {broken', 'MinigrafBench: {"x":NaN}',
                       'MinigrafBench: {"x":1e400}', 'MinigrafBench: {"x":1,"x":2}'):
            result = parse_run(stream, self.build, set_name='B1', run_index=1, attempt=1,
                               platform='emulator', exit_code=0)
            self.assertFalse(result['valid'])
            json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
