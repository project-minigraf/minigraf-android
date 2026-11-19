import unittest
from run_emulator import slots, collect, acceleration_active, instrumentation_ok, resolve_config


class CollectionTests(unittest.TestCase):
    def test_order_and_no_retry_after_valid(self):
        seen = []
        self.assertTrue(collect('B1,V,B2', lambda i, s, a: seen.append((i,s,a)) or True))
        self.assertEqual(seen, [(i,s,1) for i in range(1,7) for s in ('B1','V','B2')])
        with self.assertRaises(ValueError):
            slots('B1,B2,V')

    def test_retry_cap_and_exhaustion(self):
        seen = []
        self.assertFalse(collect('B1,V,B2', lambda i,s,a: seen.append((i,s,a)) or False))
        self.assertEqual(len(seen), 54)
        self.assertEqual(seen[:4], [(1,'B1',1),(1,'B1',2),(1,'B1',3),(1,'V',1)])
        self.assertTrue(collect('B1,V,B2', lambda i,s,a: a == 3))

    def test_kvm_requires_active_vm_and_vcpu_not_just_available(self):
        kwargs = dict(kvm_exists=True, accel_code=0, accel_output='KVM is installed and usable',
            host='x86_64', guest='x86_64', kernel_qemu='1', boot_qemu='1', hardware='ranchu')
        self.assertFalse(acceleration_active(fd_targets=['/dev/kvm'], **kwargs))
        self.assertTrue(acceleration_active(fd_targets=['/dev/kvm','anon_inode:kvm-vm','anon_inode:kvm-vcpu'], **kwargs))
        for key,value in [('kvm_exists',False),('accel_code',1),('guest','arm64-v8a'),('kernel_qemu','0')]:
            changed = dict(kwargs, **{key:value})
            self.assertFalse(acceleration_active(fd_targets=['/dev/kvm','anon_inode:kvm-vm','anon_inode:kvm-vcpu'], **changed))

    def test_instrumentation_exit_requires_junit_success(self):
        self.assertTrue(instrumentation_ok('OK (1 test)\nINSTRUMENTATION_CODE: -1', 0))
        for text,code in [('INSTRUMENTATION_CODE: -1',0), ('FAILURES!!!\nINSTRUMENTATION_CODE: -1',0),
                          ('OK (1 test)\nINSTRUMENTATION_CODE: -1',1), ('OK (2 tests)\nINSTRUMENTATION_CODE: -1',0)]:
            self.assertFalse(instrumentation_ok(text,code))

    def test_config_dispatch_and_push_defaults(self):
        config = dict(core_ref='a'*40, schedule='B1,V,B2', collect=False)
        self.assertEqual(resolve_config(config, 'push', {}), config)
        self.assertEqual(resolve_config(config, 'workflow_dispatch',
            dict(core_ref='b'*40, schedule='B1,V,B2', collect='true'))['collect'], True)
        with self.assertRaises(ValueError):
            resolve_config(dict(config, collect='false'), 'push', {})


if __name__ == '__main__':
    unittest.main()
