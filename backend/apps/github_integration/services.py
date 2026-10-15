import os
import time
import hmac
import hashlib
import jwt
import httpx
from typing import List, Dict, Any, Optional
from .models import GitHubConnection, Repository
from apps.authentication.models import User

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH", "")
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

class GitHubAppService:
    @classmethod
    def get_app_jwt(cls) -> Optional[str]:
        """
        Signs an RS256 JWT using the GitHub App's private key.
        Valid for 10 minutes (GitHub maximum).
        """
        if not GITHUB_APP_ID:
            return None

        pem_content = GITHUB_PRIVATE_KEY
        if not pem_content and GITHUB_PRIVATE_KEY_PATH and os.path.exists(GITHUB_PRIVATE_KEY_PATH):
            with open(GITHUB_PRIVATE_KEY_PATH, "r") as f:
                pem_content = f.read()

        if not pem_content:
            return None

        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (9 * 60),
            "iss": GITHUB_APP_ID
        }
        return jwt.encode(payload, pem_content, algorithm="RS256")

    @classmethod
    def get_installation_token(cls, installation_id: str) -> Optional[str]:
        app_jwt = cls.get_app_jwt()
        if not app_jwt:
            return None

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            if resp.status_code == 201:
                return resp.json().get("token")
        return None

    @classmethod
    def get_effective_token(cls, connection: GitHubConnection) -> Optional[str]:
        """
        Retrieves a valid token: installation token if App-based, or stored OAuth token.
        """
        if connection.installation_id and connection.installation_id != "oauth_user_account":
            inst_token = cls.get_installation_token(connection.installation_id)
            if inst_token:
                return inst_token
        return connection.get_access_token()

    @classmethod
    def sync_user_repositories(cls, user: User) -> List[Repository]:
        """
        Fetches live repositories from GitHub and persists them into the database.
        """
        connections = GitHubConnection.objects.filter(user=user)
        if not connections.exists():
            return []

        synced_repos = []
        for connection in connections:
            token = cls.get_effective_token(connection)
            if not token or token == "demo-token":
                continue

            with httpx.Client(timeout=20.0) as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                # If installed as a GitHub App
                endpoint = (
                    "https://api.github.com/installation/repositories"
                    if connection.installation_id and connection.installation_id != "oauth_user_account"
                    else "https://api.github.com/user/repos?per_page=100&sort=updated"
                )

                resp = client.get(endpoint, headers=headers)
                if resp.status_code != 200:
                    continue

                raw_data = resp.json()
                repo_list = raw_data.get("repositories", raw_data) if isinstance(raw_data, dict) else raw_data

                for repo_data in repo_list:
                    # Skip archived repositories
                    if repo_data.get("archived", False):
                        continue

                    repo_obj, _ = Repository.objects.update_or_create(
                        connection=connection,
                        github_repo_id=str(repo_data["id"]),
                        defaults={
                            "full_name": repo_data["full_name"],
                            "default_branch": repo_data.get("default_branch", "main"),
                            "is_active": True,
                        }
                    )
                    synced_repos.append(repo_obj)

        return synced_repos

    @classmethod
    def fetch_repository_context(cls, repository: Repository) -> Dict[str, Any]:
        """
        Ingests real repository file tree, README, and languages using GitHub API.
        """
        token = cls.get_effective_token(repository.connection)
        context = {
            "repo_name": repository.full_name,
            "default_branch": repository.default_branch,
            "allowed_paths": repository.allowed_paths or ["src/", "tests/"],
            "file_tree": [],
            "readme_preview": "",
        }

        if not token or token == "demo-token":
            return context

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        base_url = f"https://api.github.com/repos/{repository.full_name}"

        with httpx.Client(timeout=25.0) as client:
            try:
                # 1. Fetch recursive tree
                tree_resp = client.get(
                    f"{base_url}/git/trees/{repository.default_branch}?recursive=1",
                    headers=headers
                )
                if tree_resp.status_code == 200:
                    tree_data = tree_resp.json()
                    paths = [
                        {"path": item["path"], "type": item["type"]}
                        for item in tree_data.get("tree", [])[:200] # Limit to 200 relevant files
                    ]
                    context["file_tree"] = paths

                # 2. Fetch README
                readme_resp = client.get(f"{base_url}/readme", headers=headers)
                if readme_resp.status_code == 200:
                    import base64
                    content_b64 = readme_resp.json().get("content", "")
                    try:
                        readme_text = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
                        context["readme_preview"] = readme_text[:1500]
                    except Exception:
                        pass

            except Exception as e:
                context["error"] = str(e)

        return context

    @classmethod
    def verify_webhook_signature(cls, payload_body: bytes, signature_header: str) -> bool:
        if not GITHUB_WEBHOOK_SECRET or not signature_header:
            return False

        hash_type, signature = signature_header.split("=")
        if hash_type != "sha256":
            return False

        mac = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
        expected_signature = mac.hexdigest()
        return hmac.compare_digest(expected_signature, signature)
