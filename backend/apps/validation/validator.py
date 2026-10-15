import os
import re
from typing import List, Dict, Any
from apps.ai_engine.adapters.schemas import CodeProposal

BLOCKED_PATTERNS = [
    r"^\.env.*",
    r".*\.pem$",
    r".*\.key$",
    r".*\.id_rsa$",
    r"^Dockerfile.*",
    r"^docker-compose.*",
    r"^\.git/.*",
    r"^\.github/workflows/.*",
]

SECRET_PATTERNS = [
    r"ghp_[a-zA-Z0-9]{36}",
    r"github_pat_[a-zA-Z0-9_]{82}",
    r"sk-[a-zA-Z0-9]{32,}",
    r"AIza[0-9A-Za-z-_]{35}",
    r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----",
]

class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings
        }

class ValidationEngine:
    @staticmethod
    def validate(proposal: CodeProposal, allowed_paths: List[str]) -> ValidationResult:
        errors = []
        warnings = []

        if not proposal.files:
            return ValidationResult(is_valid=False, errors=["Proposal contains no files to create or modify."])

        # Default allowed path to current directory if empty
        effective_allowed = allowed_paths if allowed_paths else [""]

        for file in proposal.files:
            clean_path = os.path.normpath(file.path).replace("\\", "/")

            # 1. Path traversal check
            if clean_path.startswith("../") or clean_path.startswith("/"):
                errors.append(f"Security error: Path traversal detected in '{file.path}'")
                continue

            # 2. Blocked file pattern check
            for pattern in BLOCKED_PATTERNS:
                if re.match(pattern, clean_path, re.IGNORECASE):
                    errors.append(f"Security error: Modification of restricted file '{clean_path}' is prohibited.")
                    break

            # 3. Allowed path whitelist check
            if effective_allowed != [""]:
                is_within_allowed = any(clean_path.startswith(prefix.strip("/")) for prefix in effective_allowed)
                if not is_within_allowed:
                    errors.append(f"Path boundary error: '{clean_path}' is outside allowed paths {effective_allowed}.")

            # 4. Non-trivial content check
            content = file.content.strip()
            if len(content) < 20:
                errors.append(f"Quality error: '{clean_path}' has insufficient content ({len(content)} chars). Minimum 20 required.")

            # 5. Secret leak scanning
            for pattern in SECRET_PATTERNS:
                if re.search(pattern, content):
                    errors.append(f"Security error: Potential hardcoded secret or API credential detected in '{clean_path}'.")
                    break

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
