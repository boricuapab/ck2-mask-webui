from pathlib import Path
import tempfile
import unittest

from compare_source import find_job_source


class CompareSourceTests(unittest.TestCase):
    def test_saved_source_is_specific_to_render_and_stays_inside_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root/'converted/asset/clip.mp4'
            path.parent.mkdir(parents=True)
            path.touch()
            job = dict(id='job', name='different.mp4', source_relative='converted/asset/clip.mp4')
            self.assertEqual(find_job_source(job, root), path.resolve())
            job['source_relative'] = '../outside.mp4'
            self.assertIsNone(find_job_source(job, root))
            job['source_relative'] = 'missing.mp4'
            self.assertIsNone(find_job_source(job, root))

    def test_legacy_uploaded_and_converted_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            direct = root/'job/source.mov'
            direct.parent.mkdir()
            direct.touch()
            self.assertEqual(find_job_source(dict(id='job', name='original.mov'), root), direct.resolve())
            converted = root/'converted/asset/shot.mp4'
            converted.parent.mkdir(parents=True)
            converted.touch()
            job = dict(id='legacy', name='shot.mp4')
            self.assertEqual(find_job_source(job, root), converted.resolve())
            duplicate = root/'other/shot.mp4'
            duplicate.parent.mkdir()
            duplicate.touch()
            self.assertIsNone(find_job_source(job, root))

    def test_invalid_ids_and_non_video_files_are_not_exposed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'private.json').write_text('{}')
            self.assertIsNone(find_job_source(dict(id='job', source_relative='private.json'), root))
            self.assertIsNone(find_job_source(dict(id='../other', name='clip.mp4'), root))


if __name__ == '__main__':
    unittest.main()
