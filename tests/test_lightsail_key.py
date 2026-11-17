"""Verify SSH secret formats with temporary, unregistered key fixtures only.

No SSH connection, GitHub secret, or user key is read by these tests.
"""

import base64
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER = PROJECT_ROOT / "scripts" / "prepare-lightsail-key.sh"


def find_bash():
    candidates = [os.environ.get("BASH_BIN")]
    candidates.append(r"C:\Program Files\Git\bin\bash.exe" if os.name == "nt" else "/bin/bash")
    candidates.append(shutil.which("bash"))
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def bash_path(path):
    path = Path(path).resolve()
    if os.name == "nt":
        return "/" + path.drive[0].lower() + path.as_posix()[2:]
    return str(path)


BASH = find_bash()


@unittest.skipUnless(BASH, "Bash is required; set BASH_BIN to its executable")
class LightsailKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_directory = tempfile.TemporaryDirectory(prefix="nididhya-key-fixture-")
        cls.addClassCleanup(cls.fixture_directory.cleanup)
        cls.fixture_path = Path(cls.fixture_directory.name) / "unregistered_ed25519"
        environment = cls.clean_environment()
        environment["FIXTURE_KEY_PATH"] = bash_path(cls.fixture_path)
        generated = cls.run_bash(
            "ssh-keygen -q -t ed25519 -N '' -C nididhya-unregistered-test -f \"$FIXTURE_KEY_PATH\"",
            environment,
        )
        if generated.returncode == 127:
            raise unittest.SkipTest("ssh-keygen is required for temporary key fixtures")
        if generated.returncode != 0:
            raise RuntimeError("Could not generate the temporary unregistered SSH fixture")
        cls.private_key = cls.fixture_path.read_text(encoding="utf-8")
        cls.public_key = cls.fixture_path.with_suffix(".pub").read_text(encoding="utf-8")
        cls.expected_public_identity = cls.public_key.split()[:2]

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="nididhya-key-output-")
        self.addCleanup(self.directory.cleanup)
        self.output_path = Path(self.directory.name) / "prepared key"

    @staticmethod
    def clean_environment():
        environment = os.environ.copy()
        for name in ("BASH_ENV", "ENV", "LIGHTSAIL_SSH_KEY"):
            environment.pop(name, None)
        return environment

    @staticmethod
    def run_bash(command, environment):
        return subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", command],
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def prepare(self, secret):
        environment = self.clean_environment()
        environment.update({
            "LIGHTSAIL_SSH_KEY": secret,
            "TEST_KEY_HELPER": bash_path(HELPER),
            "TEST_KEY_OUTPUT": bash_path(self.output_path),
        })
        result = self.run_bash('exec bash "$TEST_KEY_HELPER" "$TEST_KEY_OUTPUT"', environment)
        self.assert_no_key_material(result, secret)
        return result

    def assert_no_key_material(self, result, secret):
        logs = result.stdout + result.stderr
        # Check payload fragments, not generic format markers or status text.
        tokens = re.findall(r"[A-Za-z0-9+/=]{40,}", secret)
        tokens.extend(self.private_key.splitlines()[1:-1])
        for token in tokens:
            self.assertFalse(token in logs, "Key payload appeared in helper output")

    def assert_private_identity_preserved(self):
        environment = self.clean_environment()
        environment["TEST_KEY_OUTPUT"] = bash_path(self.output_path)
        derived = self.run_bash('ssh-keygen -y -P \'\' -f "$TEST_KEY_OUTPUT"', environment)
        self.assertEqual(derived.returncode, 0, "Prepared key could not derive a public key")
        self.assertEqual(derived.stdout.split()[:2], self.expected_public_identity)
        self.assertTrue(self.output_path.read_bytes().endswith(b"\n"))
        if os.name != "nt":
            self.assertEqual(self.output_path.stat().st_mode & 0o777, 0o600)

    def test_raw_openssh_private_key_is_accepted_without_logging_it(self):
        result = self.prepare(self.private_key)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_private_identity_preserved()

    def test_raw_crlf_key_without_final_newline_is_normalized(self):
        copied = self.private_key.rstrip("\n").replace("\n", "\r\n")
        result = self.prepare(copied)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b"\r", self.output_path.read_bytes())
        self.assert_private_identity_preserved()

    def test_single_line_base64_preserves_private_key_identity(self):
        encoded = base64.b64encode(self.private_key.encode("utf-8")).decode("ascii")
        result = self.prepare(encoded)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_private_identity_preserved()

    def test_base64_with_copy_whitespace_is_accepted(self):
        encoded = base64.b64encode(self.private_key.encode("utf-8")).decode("ascii")
        copied = " \t\r\n".join(encoded[index:index + 53] for index in range(0, len(encoded), 53))
        result = self.prepare("\n\t" + copied + " \r\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_private_identity_preserved()

    def test_invalid_text_is_rejected_and_created_output_is_removed(self):
        result = self.prepare("THIS-IS-NOT-A-PRIVATE-SSH-KEY-OR-VALID-BASE64")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output_path.exists())

    def test_truncated_private_key_is_rejected_and_removed(self):
        truncated = "\n".join(self.private_key.splitlines()[:3])
        result = self.prepare(truncated)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output_path.exists())

    def test_public_key_is_rejected_and_removed(self):
        result = self.prepare(self.public_key)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output_path.exists())

    def test_base64_public_key_is_also_rejected(self):
        encoded_public = base64.b64encode(self.public_key.encode("utf-8")).decode("ascii")
        result = self.prepare(encoded_public)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output_path.exists())

    def test_empty_secret_does_not_create_output(self):
        result = self.prepare("")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output_path.exists())

    def test_existing_output_is_not_overwritten_or_deleted(self):
        sentinel = b"existing test file must remain untouched\n"
        self.output_path.write_bytes(sentinel)
        result = self.prepare(self.private_key)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output_path.read_bytes(), sentinel)

    def test_original_workflow_pipeline_also_accepts_a_fresh_valid_key(self):
        environment = self.clean_environment()
        environment.update({
            "LIGHTSAIL_SSH_KEY": self.private_key,
            "TEST_KEY_OUTPUT": bash_path(self.output_path),
        })
        result = self.run_bash(
            "set -euo pipefail; umask 077; "
            "printf '%s\\n' \"$LIGHTSAIL_SSH_KEY\" | tr -d '\\r' > \"$TEST_KEY_OUTPUT\"; "
            "ssh-keygen -y -P '' -f \"$TEST_KEY_OUTPUT\" > /dev/null",
            environment,
        )
        self.assert_no_key_material(result, self.private_key)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_private_identity_preserved()


if __name__ == "__main__":
    unittest.main()
