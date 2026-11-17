"""Idempotent publication onto a deterministic execution branch."""
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote
import httpx
from apps.github_integration.services import GitHubAppService, GitHubAPIError, github_json
from apps.validation.validator import canonical_path


@dataclass
class GitPublisherResult:
    success: bool
    branch_name: str = ''
    commit_sha: str = ''
    pull_request_url: Optional[str] = None
    pull_request_number: Optional[int] = None
    error: Optional[str] = None
    retryable: bool = False


class GitPublishingService:
    @staticmethod
    def publish(repository, proposal, branch_strategy='PULL_REQUEST', *, execution_id, base_sha,
                base_tree_sha, file_modes=None, commit_date):
        branch = f'automation/habit-{execution_id}'
        result = GitPublisherResult(False, branch_name=branch)
        try:
            if branch_strategy not in ('PULL_REQUEST', 'DIRECT_PUSH') or not base_sha or not base_tree_sha:
                raise GitHubAPIError('Missing or invalid publication snapshot.')
            token = GitHubAppService.get_effective_token(repository.connection, repository.github_repo_id)
            root = f'/repos/{repository.full_name}'
            target_ref = quote(repository.default_branch, safe='/')
            with httpx.Client(timeout=30) as client:
                base = github_json(client, 'GET', f'{root}/git/commits/{base_sha}', token)
                if base['tree']['sha'] != base_tree_sha:
                    raise GitHubAPIError('Base tree does not match the approved snapshot.')
                tree_items = []
                for file in proposal.files:
                    path = canonical_path(file.path)
                    mode = (file_modes or {}).get(path, '100644')
                    if mode not in ('100644', '100755'):
                        raise GitHubAPIError('Symlinks and submodules cannot be modified.')
                    blob = github_json(client, 'POST', f'{root}/git/blobs', token,
                                       json={'content': file.content, 'encoding': 'utf-8'})
                    tree_items.append(dict(path=path, mode=mode, type='blob', sha=blob['sha']))
                tree = github_json(client, 'POST', f'{root}/git/trees', token,
                                   json={'base_tree': base_tree_sha, 'tree': tree_items})
                if tree['sha'] == base_tree_sha:
                    raise GitHubAPIError('No repository changes were produced.')

                def existing_branch():
                    try:
                        return github_json(client, 'GET', f'{root}/git/ref/heads/{branch}', token)['object']['sha']
                    except GitHubAPIError as exc:
                        if str(exc) == 'GitHub request failed (HTTP 404).':
                            return None
                        raise

                def verify_commit(sha):
                    commit = github_json(client, 'GET', f'{root}/git/commits/{sha}', token)
                    if (commit['tree']['sha'] != tree['sha'] or commit.get('message') != proposal.commit_message
                            or [p['sha'] for p in commit.get('parents', [])] != [base_sha]):
                        raise GitHubAPIError('Execution branch changed. Refusing to overwrite it.')

                commit_sha = existing_branch()
                if commit_sha:
                    verify_commit(commit_sha)
                else:
                    head = github_json(client, 'GET', f'{root}/git/ref/heads/{target_ref}', token)
                    if head['object']['sha'] != base_sha:
                        raise GitHubAPIError('Target branch changed since generation. Generate a new proposal.')
                    identity = {'name': 'CommitFlow', 'email': 'commitflow[bot]@users.noreply.github.com', 'date': commit_date}
                    commit = github_json(client, 'POST', f'{root}/git/commits', token, json={
                        'message': proposal.commit_message, 'tree': tree['sha'], 'parents': [base_sha],
                        'author': identity, 'committer': identity,
                    })
                    commit_sha = commit['sha']
                    try:
                        github_json(client, 'POST', f'{root}/git/refs', token,
                                    json={'ref': f'refs/heads/{branch}', 'sha': commit_sha})
                    except GitHubAPIError:
                        existing = existing_branch()
                        if not existing:
                            raise
                        verify_commit(existing)
                        commit_sha = existing
                result.commit_sha = commit_sha
                if branch_strategy == 'PULL_REQUEST':
                    owner = repository.full_name.split('/')[0]
                    pull_requests = github_json(client, 'GET', f'{root}/pulls', token,
                        params={'head': f'{owner}:{branch}', 'base': repository.default_branch, 'state': 'all'})
                    if pull_requests:
                        pull = pull_requests[0]
                    else:
                        try:
                            pull = github_json(client, 'POST', f'{root}/pulls', token, json={
                                'title': proposal.pr_title, 'body': proposal.pr_body,
                                'head': branch, 'base': repository.default_branch,
                            })
                        except GitHubAPIError:
                            # A concurrent or ambiguous POST may already have created the PR.
                            pulls = github_json(client, 'GET', f'{root}/pulls', token,
                                params={'head': f'{owner}:{branch}', 'base': repository.default_branch, 'state': 'all'})
                            if not pulls:
                                raise
                            pull = pulls[0]
                    if pull.get('head', {}).get('sha') != commit_sha:
                        raise GitHubAPIError('Pull request head does not match the approved commit.')
                    result.pull_request_url = pull['html_url']
                    result.pull_request_number = pull['number']
                else:
                    head = github_json(client, 'GET', f'{root}/git/ref/heads/{target_ref}', token)
                    if head['object']['sha'] != commit_sha:
                        if head['object']['sha'] != base_sha:
                            raise GitHubAPIError('Target branch changed. Direct push was not applied.')
                        github_json(client, 'PATCH', f'{root}/git/refs/heads/{target_ref}', token,
                                    json={'sha': commit_sha, 'force': False})
                    final = github_json(client, 'GET', f'{root}/git/ref/heads/{target_ref}', token)
                    if final['object']['sha'] != commit_sha:
                        raise GitHubAPIError('GitHub did not confirm the direct push.', retryable=True)
                    result.branch_name = repository.default_branch
                result.success = True
        except GitHubAPIError as exc:
            result.error = str(exc)
            result.retryable = exc.retryable
        except (KeyError, ValueError, TypeError):
            result.error = 'GitHub returned an invalid response.'
        return result
