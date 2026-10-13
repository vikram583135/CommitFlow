from django.urls import path
from .views import (
    ExecutionListView,
    ExecutionDetailView,
    ExecutionApproveView,
    ExecutionRetryView
)

urlpatterns = [
    path('', ExecutionListView.as_view(), name='execution-list'),
    path('<uuid:pk>/', ExecutionDetailView.as_view(), name='execution-detail'),
    path('<uuid:pk>/approve/', ExecutionApproveView.as_view(), name='execution-approve'),
    path('<uuid:pk>/retry/', ExecutionRetryView.as_view(), name='execution-retry'),
]
