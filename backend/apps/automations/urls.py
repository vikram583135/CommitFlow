from django.urls import path
from .views import (
    AutomationListCreateView,
    AutomationDetailView,
    AutomationRunTriggerView
)

urlpatterns = [
    path('', AutomationListCreateView.as_view(), name='automation-list-create'),
    path('<uuid:pk>/', AutomationDetailView.as_view(), name='automation-detail'),
    path('<uuid:pk>/run/', AutomationRunTriggerView.as_view(), name='automation-run'),
]
