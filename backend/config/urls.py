from django.contrib import admin
from django.urls import path

from config.views import healthz

urlpatterns = [
    path('healthz/', healthz),
    path('admin/', admin.site.urls),
]
