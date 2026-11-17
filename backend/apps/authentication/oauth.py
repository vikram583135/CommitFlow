"""OAuth exchanges; missing configuration and unverified identities fail closed."""
from urllib.parse import urlencode
import httpx
from django.conf import settings


class OAuthService:
    @staticmethod
    def credentials(provider):
        if provider not in ('github', 'google'):
            raise ValueError('Unsupported OAuth provider.')
        client_id = getattr(settings, provider.upper() + '_CLIENT_ID', '')
        secret = getattr(settings, provider.upper() + '_CLIENT_SECRET', '')
        if not client_id or not secret:
            raise ValueError(f'{provider.title()} OAuth is not configured.')
        return client_id, secret

    @classmethod
    def get_auth_url(cls, provider, redirect_uri, state, code_challenge):
        client_id, _ = cls.credentials(provider)
        params = dict(client_id=client_id, redirect_uri=redirect_uri, state=state,
                      code_challenge=code_challenge, code_challenge_method='S256')
        if provider == 'github':
            endpoint = 'https://github.com/login/oauth/authorize'
            params['scope'] = 'read:user user:email read:org repo'
        else:
            endpoint = 'https://accounts.google.com/o/oauth2/v2/auth'
            params.update(response_type='code', scope='openid email profile')
        return {'provider': provider, 'state': state, 'url': endpoint + '?' + urlencode(params)}

    @classmethod
    def exchange(cls, provider, code, redirect_uri, code_verifier):
        client_id, secret = cls.credentials(provider)
        if not code:
            raise ValueError('An authorization code is required.')
        endpoint = ('https://github.com/login/oauth/access_token' if provider == 'github'
                    else 'https://oauth2.googleapis.com/token')
        with httpx.Client(timeout=15.0) as client:
            response = client.post(endpoint, headers={'Accept': 'application/json'}, data={
                'client_id': client_id, 'client_secret': secret, 'code': code,
                'redirect_uri': redirect_uri, 'code_verifier': code_verifier,
                'grant_type': 'authorization_code',
            })
            response.raise_for_status()
            token = response.json().get('access_token')
            if not token:
                raise ValueError('Provider did not return an access token.')
            headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
            if provider == 'github':
                response = client.get('https://api.github.com/user', headers=headers)
                response.raise_for_status()
                profile = response.json()
                response = client.get('https://api.github.com/user/emails', headers=headers)
                response.raise_for_status()
                emails = [entry for entry in response.json() if entry.get('verified')]
                primary = next((entry for entry in emails if entry.get('primary')), None)
                if not primary or not profile.get('id'):
                    raise ValueError('A verified primary GitHub email is required.')
                return dict(provider_id=str(profile['id']), email=primary['email'].lower(),
                            name=profile.get('name') or profile['login'], login=profile['login'],
                            avatar_url=profile.get('avatar_url'), access_token=token)
            response = client.get('https://www.googleapis.com/oauth2/v3/userinfo', headers=headers)
            response.raise_for_status()
            profile = response.json()
            if not profile.get('email_verified') or not profile.get('sub') or not profile.get('email'):
                raise ValueError('A verified Google email is required.')
            return dict(provider_id=str(profile['sub']), email=profile['email'].lower(),
                        name=profile.get('name', ''), avatar_url=profile.get('picture'))
