"""GitHub access with explicit credentials, ownership checks, and immutable context."""
import base64
import hashlib
import hmac
import os
import re
import time
from urllib.parse import quote
import httpx
import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import GitHubConnection, Repository
from apps.validation.validator import canonical_path, contains_secret, path_allowed, sensitive_path, validate_allowed_paths

API = 'https://api.github.com'


class GitHubAPIError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def github_json(client, method, path, token, **kwargs):
    try:
        response = client.request(method, API + path, headers={
            'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }, **kwargs)
    except httpx.RequestError as exc:
        raise GitHubAPIError('GitHub is temporarily unreachable.', retryable=True) from exc
    if response.status_code >= 400:
        retryable = response.status_code in (429, 500, 502, 503, 504) or (
            response.status_code == 403 and response.headers.get('x-ratelimit-remaining') == '0')
        raise GitHubAPIError(f'GitHub request failed (HTTP {response.status_code}).', retryable)
    return response.json() if response.content else {}


class GitHubAppService:
    @classmethod
    def get_app_jwt(cls):
        if not settings.GITHUB_APP_ID:
            return None
        pem = os.getenv('GITHUB_PRIVATE_KEY', '')
        path = os.getenv('GITHUB_PRIVATE_KEY_PATH', '')
        if not pem and path:
            with open(path, encoding='utf-8') as handle:
                pem = handle.read()
        if not pem:
            return None
        now = int(time.time())
        return jwt.encode({'iat': now - 60, 'exp': now + 540, 'iss': settings.GITHUB_APP_ID}, pem, algorithm='RS256')

    @classmethod
    def get_installation_token(cls, installation_id, repository_id=None):
        app_token = cls.get_app_jwt()
        if not app_token:
            raise GitHubAPIError('GitHub App credentials are not configured.')
        with httpx.Client(timeout=20) as client:
            scope = {'permissions': {'contents': 'write', 'pull_requests': 'write'}}
            if repository_id is not None:
                scope['repository_ids'] = [int(repository_id)]
            result = github_json(client, 'POST', f'/app/installations/{installation_id}/access_tokens', app_token, json=scope)
        if not result.get('token'):
            raise GitHubAPIError('GitHub did not return an installation token.')
        if result.get('permissions', {}).get('contents') != 'write' or result.get('permissions', {}).get('pull_requests') != 'write':
            raise GitHubAPIError('GitHub App needs Contents and Pull requests write permissions.')
        return result['token']

    @classmethod
    def get_effective_token(cls, connection, repository_id=None):
        if not connection.is_active:
            raise GitHubAPIError('GitHub connection is inactive. Reconnect GitHub.')
        if connection.installation_id and connection.installation_id != 'oauth_user_account':
            source = GitHubConnection.objects.filter(user=connection.user, github_user_id=connection.github_user_id,
                installation_id='oauth_user_account', is_active=True).first()
            if source is None:
                raise GitHubAPIError('Reconnect your verified GitHub user account before using this installation.')
            cls.verify_installation_access(source, connection.installation_id)
            return cls.get_installation_token(connection.installation_id, repository_id)
        if connection.token_expires_at and connection.token_expires_at <= timezone.now():
            raise GitHubAPIError('GitHub authorization expired. Reconnect GitHub.')
        token = connection.get_access_token()
        if not token or token in ('demo-token', 'gho_dev_token_placeholder'):
            raise GitHubAPIError('A valid GitHub authorization is required.')
        return token

    @classmethod
    def verify_installation_access(cls, connection, installation_id):
        if not re.fullmatch(r'[1-9][0-9]{0,19}', str(installation_id)):
            raise GitHubAPIError('Invalid installation ID.')
        if connection.installation_id != 'oauth_user_account':
            raise GitHubAPIError('Connect your GitHub user account first.')
        user_token = cls.get_effective_token(connection)
        app_token = cls.get_app_jwt()
        if not app_token:
            raise GitHubAPIError('GitHub App credentials are not configured.')
        with httpx.Client(timeout=20) as client:
            profile = github_json(client, 'GET', '/user', user_token)
            if str(profile.get('id')) != connection.github_user_id:
                raise GitHubAPIError('GitHub identity does not match this connection.')
            installation = github_json(client, 'GET', f'/app/installations/{installation_id}', app_token)
            if str(installation.get('app_id')) != str(settings.GITHUB_APP_ID) or installation.get('suspended_at'):
                raise GitHubAPIError('This installation is unavailable.')
            account = installation.get('account', {})
            if account.get('type') == 'User' and str(account.get('id')) == str(profile['id']):
                return
            if account.get('type') == 'Organization':
                membership = github_json(client, 'GET', f"/user/memberships/orgs/{account['login']}", user_token)
                if membership.get('state') == 'active' and membership.get('role') == 'admin':
                    return
        raise GitHubAPIError('You must own the installation account or be an organization administrator.')

    @classmethod
    def sync_user_repositories(cls, user):
        synced = []
        for connection in GitHubConnection.objects.filter(user=user, is_active=True):
            token = cls.get_effective_token(connection)
            app_based = connection.installation_id != 'oauth_user_account'
            found = []
            with httpx.Client(timeout=20) as client:
                for page in range(1, 101):
                    endpoint = '/installation/repositories' if app_based else '/user/repos'
                    data = github_json(client, 'GET', endpoint, token, params={'per_page': 100, 'page': page})
                    entries = data['repositories'] if app_based else data
                    found.extend(entry for entry in entries if not entry.get('archived')
                                 and not entry.get('disabled') and (app_based or entry.get('permissions', {}).get('push', False)))
                    if len(entries) < 100:
                        break
                else:
                    raise GitHubAPIError('Repository list exceeded the supported pagination limit.')
            with transaction.atomic():
                connection.repositories.update(is_active=False)
                for entry in found:
                    repo, _ = Repository.objects.get_or_create(connection=connection, github_repo_id=str(entry['id']),
                        defaults={'full_name': entry['full_name'], 'allowed_paths': ['src/', 'tests/', 'docs/']})
                    repo.full_name = entry['full_name']
                    repo.default_branch = entry['default_branch']
                    repo.is_active = True
                    repo.last_synced_at = timezone.now()
                    repo.save()
                    synced.append(repo)
                from apps.automations.models import Automation
                for automation in Automation.objects.filter(repository__connection=connection, repository__is_active=False, enabled=True):
                    automation.enabled = False
                    automation.save(update_fields=['enabled'])
        return synced

    @classmethod
    def fetch_repository_context(cls, repository):
        if not repository.is_active:
            raise GitHubAPIError('Repository is inactive. Sync repositories again.')
        allowed = validate_allowed_paths(repository.allowed_paths)
        token = cls.get_effective_token(repository.connection, repository.github_repo_id)
        root = f'/repos/{repository.full_name}'
        with httpx.Client(timeout=25) as client:
            ref = github_json(client, 'GET', f'{root}/git/ref/heads/{quote(repository.default_branch, safe="/")}', token)
            base_sha = ref['object']['sha']
            commit = github_json(client, 'GET', f'{root}/git/commits/{base_sha}', token)
            tree = github_json(client, 'GET', f"{root}/git/trees/{commit['tree']['sha']}", token, params={'recursive': 1})
            if tree.get('truncated') or len(tree.get('tree', [])) > 10000:
                raise GitHubAPIError('Repository tree is too large; narrow the repository before enabling automation.')
            entries = {entry['path']: entry for entry in tree.get('tree', [])}
            sources = {}
            total = 0
            for path, entry in entries.items():
                if len(sources) >= 15:
                    break
                if (entry.get('type') != 'blob' or entry.get('mode') not in ('100644', '100755')
                        or entry.get('size', 0) > 50000 or sensitive_path(path)
                        or not path_allowed(path, allowed)):
                    continue
                try:
                    canonical_path(path)
                    blob = github_json(client, 'GET', f"{root}/git/blobs/{entry['sha']}", token)
                    if blob.get('encoding') != 'base64' or blob.get('size', 0) > 50000:
                        continue
                    content = base64.b64decode(blob['content'], validate=False).decode('utf-8')
                    if '\x00' in content or contains_secret(content) or total + len(content.encode()) > 150000:
                        continue
                except (UnicodeError, ValueError):
                    continue
                sources[path] = content
                total += len(content.encode())
        return dict(repo_name=repository.full_name, default_branch=repository.default_branch,
                    allowed_paths=allowed, base_sha=base_sha, base_tree_sha=commit['tree']['sha'],
                    entries=entries, file_tree=[{'path': p, 'type': e['type']} for p, e in entries.items()][:200],
                    source_files=sources)

    @classmethod
    def verify_webhook_signature(cls, payload_body, signature_header):
        if not settings.GITHUB_WEBHOOK_SECRET or not re.fullmatch(r'sha256=[0-9a-f]{64}', signature_header):
            return False
        expected = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header[7:])
