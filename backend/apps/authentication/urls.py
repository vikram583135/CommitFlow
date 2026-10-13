from django.urls import path
from .views import RegisterView, LoginView, LogoutView, MeView, OAuthUrlView, OAuthCallbackView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('oauth/url/', OAuthUrlView.as_view(), name='oauth-url'),
    path('oauth/callback/', OAuthCallbackView.as_view(), name='oauth-callback'),
]
