from django.contrib import admin
from django.urls import path

from config.views import healthz
from users.views import internal_register_user, internal_user_detail

urlpatterns = [
    path('healthz/', healthz),
    path('admin/', admin.site.urls),
    path('api/internal/users/', internal_register_user, name='internal_register_user'),
    path('api/internal/users/<int:telegram_id>/', internal_user_detail, name='internal_user_detail'),
]
