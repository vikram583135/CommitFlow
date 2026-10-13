import os
import httpx
from typing import Dict, Any, Optional
from django.conf import settings

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

class OAuthService:
    @classmethod
    def get_auth_url(cls, provider: str, redirect_uri: str) -> Dict[str, str]:
        if provider == "github":
            client_id = GITHUB_CLIENT_ID or "demo_github_client_id"
            url = (
                f"https://github.com/login/oauth/authorize"
                f"?client_id={client_id}"
                f"&redirect_uri={redirect_uri}"
                f"&scope=read:user,user:email,repo"
            )
            return {"provider": "github", "url": url}
        elif provider == "google":
            client_id = GOOGLE_CLIENT_ID or "demo_google_client_id"
            url = (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?client_id={client_id}"
                f"&redirect_uri={redirect_uri}"
                f"&response_type=code"
                f"&scope=openid%20email%20profile"
                f"&access_type=offline"
            )
            return {"provider": "google", "url": url}
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

    @classmethod
    def handle_github_callback(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        # If client credentials not configured, provide developer fallback
        if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
            return {
                "provider": "github",
                "provider_id": "gh_dev_developer",
                "email": "developer@github.com",
                "name": "GitHub Developer",
                "avatar_url": "https://avatars.githubusercontent.com/u/583231?v=4",
                "access_token": "gho_dev_token_placeholder"
            }

        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri
                }
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data.get("access_token")

            # Fetch user profile
            user_resp = client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_resp.raise_for_status()
            profile = user_resp.json()

            # Fetch primary email if private
            email = profile.get("email")
            if not email:
                emails_resp = client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if emails_resp.status_code == 200:
                    for em in emails_resp.json():
                        if em.get("primary") and em.get("verified"):
                            email = em.get("email")
                            break

            return {
                "provider": "github",
                "provider_id": str(profile.get("id")),
                "email": email or f"{profile.get('login')}@users.noreply.github.com",
                "name": profile.get("name") or profile.get("login"),
                "avatar_url": profile.get("avatar_url"),
                "access_token": access_token
            }

    @classmethod
    def handle_google_callback(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            return {
                "provider": "google",
                "provider_id": "google_dev_developer",
                "email": "developer@gmail.com",
                "name": "Google Developer",
                "avatar_url": "https://lh3.googleusercontent.com/a/default-user=s96-c",
                "access_token": "ya29.dev_token_placeholder"
            }

        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri
                }
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data.get("access_token")

            user_resp = client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            user_resp.raise_for_status()
            profile = user_resp.json()

            return {
                "provider": "google",
                "provider_id": str(profile.get("sub")),
                "email": profile.get("email"),
                "name": profile.get("name") or profile.get("email"),
                "avatar_url": profile.get("picture"),
                "access_token": access_token
            }
