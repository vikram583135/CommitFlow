from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from .models import User
from .serializers import UserSerializer, RegisterSerializer, LoginSerializer
from .oauth import OAuthService
from apps.github_integration.models import GitHubConnection

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"message": "Successfully logged out."})

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

class OAuthUrlView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        provider = request.query_params.get('provider', 'github').lower()
        redirect_uri = request.query_params.get('redirect_uri', 'http://localhost:3000/auth/callback')
        try:
            data = OAuthService.get_auth_url(provider, redirect_uri)
            return Response(data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class OAuthCallbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        provider = request.data.get('provider', 'github').lower()
        code = request.data.get('code', '')
        redirect_uri = request.data.get('redirect_uri', 'http://localhost:3000/auth/callback')

        try:
            if provider == 'github':
                profile = OAuthService.handle_github_callback(code, redirect_uri)
            elif provider == 'google':
                profile = OAuthService.handle_google_callback(code, redirect_uri)
            else:
                return Response({"error": f"Unknown provider {provider}"}, status=status.HTTP_400_BAD_REQUEST)

            email = profile['email']
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'name': profile.get('name', ''),
                    'avatar_url': profile.get('avatar_url'),
                    'auth_provider': provider,
                    'provider_id': profile.get('provider_id', ''),
                }
            )

            if not created:
                user.avatar_url = profile.get('avatar_url') or user.avatar_url
                user.auth_provider = provider
                user.provider_id = profile.get('provider_id', '') or user.provider_id
                user.save(update_fields=['avatar_url', 'auth_provider', 'provider_id'])

            # If user authenticated with GitHub, persist GitHubConnection
            if provider == 'github' and profile.get('access_token'):
                connection, _ = GitHubConnection.objects.get_or_create(
                    user=user,
                    defaults={
                        'github_user_id': profile.get('provider_id', ''),
                        'github_username': profile.get('name', ''),
                        'installation_id': 'oauth_user_account',
                    }
                )
                connection.set_access_token(profile['access_token'])
                connection.save()

            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            })

        except Exception as e:
            return Response({"error": f"OAuth exchange failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
