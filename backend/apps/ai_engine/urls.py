from django.urls import path
from .views import (
    AIProviderConfigListCreateView,
    AIProviderConfigDetailView,
    AIProviderTestConnectionView
)

urlpatterns = [
    path('', AIProviderConfigListCreateView.as_view(), name='ai-config-list-create'),
    path('<uuid:pk>/', AIProviderConfigDetailView.as_view(), name='ai-config-detail'),
    path('<uuid:pk>/test/', AIProviderTestConnectionView.as_view(), name='ai-config-test'),
]
