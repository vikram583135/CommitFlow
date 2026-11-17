from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        cache.set('commitflow:readiness', True, 10)
        if cache.get('commitflow:readiness') is not True:
            raise RuntimeError('Cache unavailable')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok', 'service': 'commitflow-api'})

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('api/health/', health_check, name='api-health-check'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.authentication.urls')),
    path('api/github/', include('apps.github_integration.urls')),
    path('api/ai-configs/', include('apps.ai_engine.urls')),
    path('api/automations/', include('apps.automations.urls')),
    path('api/executions/', include('apps.executions.urls')),
]
