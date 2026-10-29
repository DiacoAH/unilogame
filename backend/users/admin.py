from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Referral, User


class UserAdmin(BaseUserAdmin):
    list_display = (
        'telegram_id',
        'username',
        'first_name',
        'last_name',
        'language_code',
        'is_premium',
        'referral_code',
        'is_staff',
        'is_active',
        'date_joined',
        'last_seen_at',
    )
    list_filter = (
        'is_staff',
        'is_superuser',
        'is_active',
        'is_premium',
        'notifications_enabled',
        'bot_blocked',
        'language_code',
        'referral_code',
    )
    search_fields = ('telegram_id', 'username', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login', 'telegram_id')
    ordering = ('-date_joined',)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            'Telegram',
            {
                'fields': (
                    'telegram_id',
                    'language_code',
                    'is_premium',
                    'started_bot_at',
                    'first_app_open_at',
                    'last_seen_at',
                    'notifications_enabled',
                    'bot_blocked',
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('telegram_id', 'password1', 'password2'),
            },
        ),
    )


admin.site.register(User, UserAdmin)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referee', 'created_at', 'rewarded', 'rewarded_at')
    list_filter = ('rewarded', 'created_at')
    search_fields = ('referrer__telegram_id', 'referee__telegram_id')
    raw_id_fields = ('referrer', 'referee')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
