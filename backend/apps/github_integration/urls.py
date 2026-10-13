from django.urls import path
from .views import (
    GitHubConnectionListView,
    GitHubConnectionDetailView,
    RepositoryListView,
    RepositoryDetailView,
    GitHubOAuthCallbackView
)

urlpatterns = [
    path('connections/', GitHubConnectionListView.as_view(), name='github-connections'),
    path('connections/<uuid:pk>/', GitHubConnectionDetailView.as_view(), name='github-connection-detail'),
    path('repositories/', RepositoryListView.as_view(), name='github-repositories'),
    path('repositories/<uuid:pk>/', RepositoryDetailView.as_view(), name='github-repository-detail'),
    path('callback/', GitHubOAuthCallbackView.as_view(), name='github-callback'),
]
