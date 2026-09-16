import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from erpnext_sevdesk_sync.env_file import load_env_file


class LoadEnvFileTests(unittest.TestCase):
    def test_loads_simple_key_values(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                '# comment\nFOO=bar\nexport EXPORTED=baz\nQUOTED="hello world"\n'
            )
            for key in ("FOO", "EXPORTED", "QUOTED"):
                os.environ.pop(key, None)
            try:
                load_env_file(env_path)
                self.assertEqual(os.environ["FOO"], "bar")
                self.assertEqual(os.environ["EXPORTED"], "baz")
                self.assertEqual(os.environ["QUOTED"], "hello world")
            finally:
                for key in ("FOO", "EXPORTED", "QUOTED"):
                    os.environ.pop(key, None)

    def test_does_not_override_existing_by_default(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("FOO=fromfile\n")
            os.environ["FOO"] = "fromenv"
            try:
                load_env_file(env_path)
                self.assertEqual(os.environ["FOO"], "fromenv")
            finally:
                os.environ.pop("FOO", None)

    def test_override_true_overwrites_existing(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("FOO=fromfile\n")
            os.environ["FOO"] = "fromenv"
            try:
                load_env_file(env_path, override=True)
                self.assertEqual(os.environ["FOO"], "fromfile")
            finally:
                os.environ.pop("FOO", None)

    def test_missing_file_is_noop(self):
        load_env_file("/nonexistent/path/.env")


if __name__ == "__main__":
    unittest.main()
