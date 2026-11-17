"""Repository-relative static validation. Generated code is never executed here."""
import ast
import json
import re
from pathlib import PurePosixPath

SECRET_PATTERNS = [
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    r"sk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{20,}",
    r"AIza[0-9A-Za-z_-]{35}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----",
    r"(?i)(?:password|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_+/=-]{20,}",
]


def canonical_path(value):
    if not isinstance(value, str) or not value or len(value) > 500:
        raise ValueError('A nonempty repository-relative path is required (maximum 500 characters).')
    if '\\' in value or ':' in value or any(ord(c) < 32 for c in value):
        raise ValueError('Backslashes, drive paths, and control characters are prohibited.')
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Path traversal or noncanonical path detected.')
    return path.as_posix()


def validate_allowed_paths(values):
    if not isinstance(values, list) or not values or len(values) > 20:
        raise ValueError('Configure between 1 and 20 allowed directory paths.')
    result = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError('Allowed paths must be strings.')
        result.append(canonical_path(value.rstrip('/')) + '/')
    return sorted(set(result))


def path_allowed(path, allowed_paths):
    return any(path.startswith(prefix) for prefix in allowed_paths)


def sensitive_path(path):
    for part in PurePosixPath(path).parts:
        name = part.lower()
        if (name in {'.git', '.github', '.ssh', '.aws', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519'}
                or name.startswith(('.env', 'dockerfile', 'docker-compose', 'compose.'))
                or name.endswith(('.pem', '.key', '.p12', '.pfx', '.keystore'))):
            return True
    return False


def contains_secret(content):
    return any(re.search(pattern, content) for pattern in SECRET_PATTERNS)


class ValidationResult:
    def __init__(self, is_valid, errors=None, warnings=None, checks=None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.checks = checks or {}

    def to_dict(self):
        return dict(is_valid=self.is_valid, errors=self.errors, warnings=self.warnings, checks=self.checks)


class ValidationEngine:
    @staticmethod
    def validate(proposal, allowed_paths, max_files=3, originals=None):
        errors = []
        checks = dict(paths=True, secrets=True, changes=True, syntax=True)
        try:
            allowed = validate_allowed_paths(allowed_paths)
        except ValueError as exc:
            return ValidationResult(False, [str(exc)], checks={'paths': False})
        if not proposal.files or len(proposal.files) > max_files:
            errors.append(f'Proposal must contain between 1 and {max_files} files.')
            checks['changes'] = False
        if sum(len(f.content.encode('utf-8')) for f in proposal.files) > 250_000:
            errors.append('Proposal exceeds the 250 KB content limit.')
            checks['changes'] = False
        seen = set()
        for file in proposal.files:
            try:
                path = canonical_path(file.path)
            except ValueError as exc:
                errors.append(f'Path traversal or invalid path: {exc}')
                checks['paths'] = False
                continue
            if path in seen:
                errors.append(f'Duplicate path: {path}.')
                checks['changes'] = False
            if any(path.startswith(other + '/') or other.startswith(path + '/') for other in seen):
                errors.append(f'Conflicting parent/child file paths: {path}.')
                checks['changes'] = False
            seen.add(path)
            if sensitive_path(path):
                errors.append(f'Modification of restricted file {path} is prohibited.')
                checks['paths'] = False
            if not path_allowed(path, allowed):
                errors.append(f'{path} is outside allowed paths.')
                checks['paths'] = False
            content = file.content.strip()
            meaningful = [line for line in content.splitlines()
                          if line.strip() and not line.lstrip().startswith(('#', '//', '/*', '*', '<!--'))]
            if len(content) < 20 or not meaningful:
                errors.append(f'{path} has insufficient meaningful content.')
                checks['changes'] = False
            if originals is not None:
                original = originals.get(path)
                if file.change_type == 'CREATE' and original is not None:
                    errors.append(f'{path} already exists; CREATE cannot overwrite it.')
                    checks['changes'] = False
                if file.change_type == 'MODIFY' and original is None:
                    errors.append(f'{path} must be read before it can be modified.')
                    checks['changes'] = False
                if original is not None and ''.join(original.split()) == ''.join(file.content.split()):
                    errors.append(f'{path} contains no substantive change.')
                    checks['changes'] = False
            if contains_secret(file.content):
                errors.append(f'Potential secret or API credential detected in {path}.')
                checks['secrets'] = False
            try:
                if path.endswith('.py'):
                    ast.parse(file.content)
                elif path.endswith('.json'):
                    json.loads(file.content)
            except (SyntaxError, ValueError, RecursionError):
                errors.append(f'{path} failed syntax validation.')
                checks['syntax'] = False
        if any(contains_secret(value) for value in
               [proposal.summary, proposal.commit_message, proposal.pr_title, proposal.pr_body]):
            errors.append('Potential secret detected in proposal metadata.')
            checks['secrets'] = False
        return ValidationResult(not errors, errors, [
            'Static checks only. Generated code and test assertions have not been executed.'
        ], checks)
