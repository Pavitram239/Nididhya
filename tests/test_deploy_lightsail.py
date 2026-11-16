"""Exercise deployment orchestration with isolated command stubs, never a server.

Run: python -m unittest discover -s tests -p 'test_deploy_lightsail.py' -v
Set BASH_BIN if Bash is not on PATH (for example, Git for Windows' bash.exe).
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "deploy-lightsail.sh"
TARGET = "a" * 40
PREVIOUS = "b" * 40


def find_bash():
    candidates = [os.environ.get("BASH_BIN")]
    if os.name == "nt":
        candidates.append(r"C:\Program Files\Git\bin\bash.exe")
    else:
        candidates.append("/bin/bash")
    candidates.append(shutil.which("bash"))
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def bash_path(path):
    path = Path(path).resolve()
    if os.name == "nt":
        return "/" + path.drive[0].lower() + path.as_posix()[2:]
    return str(path)


BASH = find_bash()
STUB = r'''#!/usr/bin/env bash
set -eu
command_name="${0##*/}"
{
  printf '%s' "$command_name"
  for argument in "$@"; do printf '\t%s' "$argument"; done
  printf '\n'
} >> "$DEPLOY_TEST_LOG"
scenario="$DEPLOY_TEST_SCENARIO"

case "$command_name" in
  git)
    case "$1" in
      branch)
        if [[ "$scenario" == wrong_branch ]]; then printf 'feature\n'; else printf 'master\n'; fi
        ;;
      diff)
        if [[ "$2" == --cached ]]; then
          [[ "$scenario" != staged_changes ]]
        elif [[ "$scenario" == source_edits ]]; then
          exit 1
        elif [[ "$scenario" == database_edits ]]; then
          # A dirty tracked database is ignored only when explicitly excluded.
          [[ " $* " == *" :(exclude)backend/Data/vachanamrut_db/** "* ]]
        fi
        ;;
      fetch)
        [[ "$scenario" != fetch_failure ]]
        ;;
      cat-file) ;;
      rev-parse)
        IFS= read -r current < "$DEPLOY_TEST_STATE"
        printf '%s\n' "$current"
        ;;
      merge-base)
        if [[ "$4" == refs/remotes/origin/master ]]; then
          exit 0
        fi
        [[ "$scenario" == superseded ]]
        ;;
      merge)
        [[ "$2" == --ff-only ]] || exit 97
        printf '%s\n' "$3" > "$DEPLOY_TEST_STATE"
        ;;
      *) printf 'Unexpected git invocation\n' >&2; exit 97 ;;
    esac
    ;;
  docker)
    [[ "$1" == compose ]] || exit 97
    case "$2" in
      version|config|up|ps) ;;
      build) [[ "$scenario" != build_failure ]] ;;
      exec)
        # Consume the Python smoke-check input without executing it or HTTP.
        while IFS= read -r line; do :; done
        [[ "$scenario" != smoke_failure ]]
        ;;
      *) printf 'Unexpected Docker invocation\n' >&2; exit 97 ;;
    esac
    ;;
  curl)
    if [[ "$scenario" == backend_unhealthy && "${!#}" == http://127.0.0.1:10000/health ]]; then
      exit 22
    fi
    ;;
  sleep) : ;;  # Retry tests must not actually wait.
  *) exit 97 ;;
esac
'''


@unittest.skipUnless(BASH, "Bash is required; set BASH_BIN to its executable")
class LightsailDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nididhya-deploy-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "checkout"
        self.repo.mkdir()
        (self.repo / ".env").write_text("TEST_FIXTURE_ONLY=1\n", encoding="utf-8")
        self.database = self.repo / "backend" / "Data" / "vachanamrut_db" / "chroma.sqlite3"
        self.database.parent.mkdir(parents=True)
        self.database.write_bytes(b"unchanged test database fixture")
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        for command in ("git", "docker", "curl", "sleep"):
            executable = self.bin_dir / command
            executable.write_text(STUB, encoding="utf-8", newline="\n")
            executable.chmod(0o755)
        self.log = self.root / "commands.log"
        self.state = self.root / "head.txt"
        self.state.write_text(PREVIOUS + "\n", encoding="utf-8")

    def run_deploy(self, scenario="success", target=TARGET):
        environment = os.environ.copy()
        for startup_file in ("BASH_ENV", "ENV"):
            environment.pop(startup_file, None)
        environment.update({
            "LIGHTSAIL_APP_DIR": bash_path(self.repo),
            "DEPLOY_TEST_BIN": bash_path(self.bin_dir),
            "DEPLOY_TEST_SCRIPT": bash_path(SCRIPT),
            "DEPLOY_TEST_TARGET": target,
            "DEPLOY_TEST_LOG": bash_path(self.log),
            "DEPLOY_TEST_STATE": bash_path(self.state),
            "DEPLOY_TEST_SCENARIO": scenario,
        })
        # Prefix PATH inside Bash: Git Bash converts the Windows PATH on entry.
        driver = 'export PATH="$DEPLOY_TEST_BIN:$PATH"; exec bash "$DEPLOY_TEST_SCRIPT" "$DEPLOY_TEST_TARGET"'
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", driver],
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.commands = [
            tuple(line.split("\t"))
            for line in self.log.read_text(encoding="utf-8").splitlines()
        ] if self.log.exists() else []
        return result

    def docker_updates(self):
        return [command for command in self.commands if command[:3] == ("docker", "compose", "up")]

    def assert_failed(self, result, message):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)

    def test_success_waits_for_backend_before_starting_frontend(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        backend_up, frontend_up = self.docker_updates()
        self.assertEqual(backend_up[-1], "backend")
        self.assertEqual(frontend_up[-1], "frontend")
        self.assertIn("--renew-anon-volumes", frontend_up)
        build = self.commands.index(("docker", "compose", "build", "backend", "frontend"))
        backend_health = next(i for i, command in enumerate(self.commands) if command[0] == "curl" and command[-1].endswith("10000/health"))
        smoke = self.commands.index(("docker", "compose", "exec", "-T", "backend", "python", "-"))
        self.assertLess(build, self.commands.index(backend_up))
        self.assertLess(self.commands.index(backend_up), backend_health)
        self.assertLess(backend_health, self.commands.index(frontend_up))
        self.assertLess(self.commands.index(frontend_up), smoke)
        self.assertEqual(self.state.read_text().strip(), TARGET)
        self.assertIn("successfully", result.stdout)

    def test_invalid_commit_stops_before_any_external_command(self):
        result = self.run_deploy(target="master; echo not-a-commit")
        self.assert_failed(result, "full tested commit SHA")
        self.assertEqual(self.commands, [])

    def test_server_source_edits_stop_before_fetch_or_restart(self):
        result = self.run_deploy("source_edits")
        self.assert_failed(result, "server source edits")
        self.assertFalse(any(command[:2] == ("git", "fetch") for command in self.commands))
        self.assertEqual(self.docker_updates(), [])
        self.assertEqual(self.state.read_text().strip(), PREVIOUS)

    def test_staged_changes_stop_before_update(self):
        result = self.run_deploy("staged_changes")
        self.assert_failed(result, "staged changes")
        self.assertEqual(self.docker_updates(), [])
        self.assertEqual(self.state.read_text().strip(), PREVIOUS)

    def test_dirty_runtime_database_is_preserved_without_reset_or_clean(self):
        original_database = self.database.read_bytes()
        original_environment = (self.repo / ".env").read_text()
        result = self.run_deploy("database_edits")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.database.read_bytes(), original_database)
        self.assertEqual((self.repo / ".env").read_text(), original_environment)
        self.assertFalse(any(command[:2] in (("git", "reset"), ("git", "clean")) for command in self.commands))

    def test_wrong_branch_does_not_update_or_restart(self):
        result = self.run_deploy("wrong_branch")
        self.assert_failed(result, "checkout must be on master")
        self.assertEqual(self.docker_updates(), [])
        self.assertFalse(any(command[0] == "docker" for command in self.commands))

    def test_superseded_commit_does_not_roll_back_server(self):
        result = self.run_deploy("superseded")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Skipping superseded commit", result.stdout)
        self.assertEqual(self.state.read_text().strip(), PREVIOUS)
        self.assertFalse(any(command[:2] == ("git", "merge") for command in self.commands))
        self.assertEqual(self.docker_updates(), [])

    def test_failed_image_build_does_not_restart_running_services(self):
        result = self.run_deploy("build_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.docker_updates(), [])

    def test_unhealthy_backend_prevents_frontend_restart(self):
        result = self.run_deploy("backend_unhealthy")
        self.assert_failed(result, "backend did not become ready")
        self.assertEqual([command[-1] for command in self.docker_updates()], ["backend"])
        attempts = [command for command in self.commands if command[0] == "curl"]
        self.assertEqual(len(attempts), 60)
        self.assertFalse(any(command[:3] == ("docker", "compose", "exec") for command in self.commands))

    def test_failed_smoke_check_does_not_report_deployment_success(self):
        result = self.run_deploy("smoke_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("successfully", result.stdout)


if __name__ == "__main__":
    unittest.main()
