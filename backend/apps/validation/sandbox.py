"""Optional, offline Python unittest runner using a disposable Docker container.

The worker needs access to a dedicated container runtime. Never execute proposals
in the Django or Celery Python process. Only staged source files enter the runner.
"""
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from django.conf import settings
from .validator import canonical_path, sensitive_path


def run_python_tests(files):
    tests = [path for path in files if path.startswith('tests/') and Path(path).name.startswith('test') and path.endswith('.py')]
    if not tests:
        return dict(passed=False, message='Python sandbox requires unittest tests under tests/.')
    name = 'commitflow-validation-' + uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix='commitflow-validation-') as directory:
            Path(directory).chmod(0o755)
            for path, content in files.items():
                clean = canonical_path(path)
                if sensitive_path(clean):
                    raise ValueError('Sensitive file in sandbox input.')
                target = Path(directory) / clean
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf-8')
                target.chmod(0o644)
                parent = target.parent
                while parent != Path(directory):
                    parent.chmod(0o755)
                    parent = parent.parent
            command = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network=none', '--read-only',
                       '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=64', '--memory=256m',
                       '--cpus=1', '--user=65534:65534', '--tmpfs=/tmp:rw,noexec,nosuid,size=16m',
                       '--mount', f'type=bind,src={directory},dst=/work,readonly', '--workdir=/work',
                       settings.PYTHON_SANDBOX_IMAGE, 'sh', '-c',
                       'timeout --kill-after=5s 45s python -B -m unittest discover -s tests -p "test*.py" > /tmp/results 2>&1; '
                       'code=$?; head -c 50000 /tmp/results; exit "$code"']
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
            count = re.search(r'Ran (\d+) tests?', result.stdout)
            passed = result.returncode == 0 and bool(count) and int(count.group(1)) > 0
            return dict(passed=passed, tests_run=int(count.group(1)) if count else 0,
                        message='Python unittest sandbox passed.' if passed else 'Python unittest sandbox failed or was unavailable.')
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return dict(passed=False, message='Python unittest sandbox unavailable or timed out.')
    finally:
        try:
            subprocess.run(['docker', 'rm', '--force', name], capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
