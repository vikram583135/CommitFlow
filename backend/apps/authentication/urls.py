from django.urls import path
from .views import RegisterView, LoginView, LogoutView, MeView, OAuthUrlView, OAuthCallbackView
from .views import VerifyEmailView, ResendVerificationView, PasswordResetRequestView, PasswordResetConfirmView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('oauth/url/', OAuthUrlView.as_view(), name='oauth-url'),
    path('oauth/callback/', OAuthCallbackView.as_view(), name='oauth-callback'),
]
