"""
scripts/run_unified_py_tests.py
AASHA AIOS Unified Python Test Suite Runner
Executes all unit tests across tests/test_*.py deterministically.
"""
import glob
import importlib.util
import unittest
import sys

def run_all_tests():
    files = sorted(glob.glob('tests/test_*.py'))
    total = 0
    for f in files:
        spec = importlib.util.spec_from_file_location('m', f)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        for k, fn in sorted(vars(m).items()):
            if k.startswith('test_') and callable(fn):
                fn()
                total += 1
            elif isinstance(fn, type) and issubclass(fn, unittest.TestCase) and fn is not unittest.TestCase:
                suite = unittest.defaultTestLoader.loadTestsFromTestCase(fn)
                res = unittest.TextTestRunner(verbosity=0).run(suite)
                assert res.wasSuccessful(), f'Failed in {f}'
                total += res.testsRun
    print(f'Executed {total} unit tests across {len(files)} suites')
    return total

if __name__ == '__main__':
    run_all_tests()
