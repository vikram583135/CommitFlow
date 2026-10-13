from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
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

    def post(self, request, pk=None):
        try:
            config = AIProviderConfig.objects.get(pk=pk, user=request.user)
            adapter = get_ai_adapter(config)
            is_valid = adapter.test_connection()
            return Response({"success": is_valid})
        except AIProviderConfig.DoesNotExist:
            return Response({"error": "Config not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
