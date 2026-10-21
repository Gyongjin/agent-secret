import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import agent_secret as a  # noqa: E402

SCRIPT = os.path.join(ROOT, "agent_secret.py")
SECRET = "sk-test-0123456789abcdef"


def call(args, secrets_text, suffix=".json"):
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as f:
        f.write(secrets_text)
    env = dict(os.environ, AGENT_SECRET_FILE=f.name)
    try:
        return subprocess.run([sys.executable, SCRIPT] + args, env=env, capture_output=True, text=True)
    finally:
        os.unlink(f.name)


class AgentSecretTest(unittest.TestCase):
    def test_value_reaches_command_but_is_masked(self):
        code = "import os;print(os.environ['API_KEY']);print(len(os.environ['API_KEY']))"
        r = call(["run", "API_KEY", "--", sys.executable, "-c", code], json.dumps({"API_KEY": SECRET}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(SECRET, r.stdout)
        self.assertIn("***", r.stdout)
        self.assertIn(str(len(SECRET)), r.stdout)

    def test_stderr_masked_and_exit_code_kept(self):
        code = "import os,sys;sys.stderr.write(os.environ['API_KEY']);sys.exit(3)"
        r = call(["run", "API_KEY", "--", sys.executable, "-c", code], json.dumps({"API_KEY": SECRET}))
        self.assertEqual(r.returncode, 3)
        self.assertNotIn(SECRET, r.stderr)

    def test_only_listed_names_and_no_file_var(self):
        code = "import os;print(os.environ.get('OTHER'), os.environ.get('AGENT_SECRET_FILE'))"
        r = call(["run", "API_KEY", "--", sys.executable, "-c", code], json.dumps({"API_KEY": SECRET, "OTHER": "x" * 20}))
        self.assertEqual(r.stdout.strip(), "None None")

    def test_dotenv_file(self):
        code = "import os;print(os.environ['TOKEN'] == 'abc def ghi jkl')"
        r = call(["run", "TOKEN", "--", sys.executable, "-c", code], 'export TOKEN="abc def ghi jkl"\n# c\n', ".env")
        self.assertEqual(r.stdout.strip(), "True")

    def test_missing_name(self):
        r = call(["run", "NOPE", "--", sys.executable, "-c", "pass"], json.dumps({"API_KEY": SECRET}))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NOPE", r.stderr)
        self.assertNotIn(SECRET, r.stderr)

    def test_names_only_prints_names(self):
        r = call(["names"], json.dumps({"API_KEY": SECRET}))
        self.assertEqual(r.stdout.strip(), "API_KEY")

    def test_engines_refused(self):
        for cmd in (["claude"], ["npx", "@anthropic-ai/claude-code@1"], ["pnpm", "dlx", "@openai/codex"], ["gemini.exe"]):
            self.assertTrue(a.engine_of(cmd), cmd)
        for cmd in (["npm", "run", "dev"], ["npx", "vite"]):
            self.assertFalse(a.engine_of(cmd), cmd)

    def test_cmd_metacharacters(self):
        self.assertTrue(a.cmd_unsafe("C:/x/npm.cmd", ["run", "a&b"]))
        self.assertFalse(a.cmd_unsafe("C:/x/npm.cmd", ["run", "dev"]))
        self.assertFalse(a.cmd_unsafe("/usr/bin/npm", ["a&b"]))


if __name__ == "__main__":
    unittest.main()
