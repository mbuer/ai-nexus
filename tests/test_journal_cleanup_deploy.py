import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

HOST=Path(__file__).resolve().parents[1]/'deploy/journal-host'
sys.path.insert(0,str(HOST))
spec=importlib.util.spec_from_file_location('cleanup_deploy',HOST/'deploy_feedback_cleanup.py')
cleanup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class CleanupDeploymentTests(unittest.TestCase):
    def test_queue_inspection_is_read_only_and_never_creates_missing_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'queue.sqlite'
            with patch.object(cleanup,'QUEUE',path):
                with self.assertRaises(sqlite3.OperationalError):cleanup.queue_count()
                self.assertFalse(path.exists())
                connection=sqlite3.connect(path)
                connection.execute('CREATE TABLE reviews (id INTEGER)')
                connection.execute('INSERT INTO reviews VALUES (1)')
                connection.commit();connection.close()
                before=path.read_bytes()
                self.assertEqual(cleanup.queue_count(),1)
                self.assertEqual(path.read_bytes(),before)

    def test_invalid_staging_cannot_restart_or_publish(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cleanup,'run') as run, patch.object(cleanup,'publish') as publish:
            with self.assertRaises(ValueError):cleanup.deploy(Path(directory))
            run.assert_not_called();publish.assert_not_called()
