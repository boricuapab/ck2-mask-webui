from pathlib import Path
import shutil
import subprocess
import unittest


class CompareUiTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is needed for browser-control regression checks')
    def test_wipe_and_synchronized_playback(self):
        script = Path(__file__).with_name('compare_ui_test.cjs')
        result = subprocess.run(['node', str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
