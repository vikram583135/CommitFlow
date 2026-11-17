from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from .models import AIProviderConfig
from .serializers import AIProviderConfigSerializer
from .adapters import get_ai_adapter

class AIProviderConfigListCreateView(generics.ListCreateAPIView):
    serializer_class = AIProviderConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AIProviderConfig.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class AIProviderConfigDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AIProviderConfigSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AIProviderConfig.objects.filter(user=self.request.user)

class AIProviderTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'run'

    def post(self, request, pk=None):
        try:
            config = AIProviderConfig.objects.get(pk=pk, user=request.user)
            adapter = get_ai_adapter(config)
            is_valid = adapter.test_connection()
            return Response({"success": is_valid})
        except AIProviderConfig.DoesNotExist:
            return Response({"error": "Config not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response({'error': 'Provider connection failed. Check the key and model.'}, status=400)
