from django.contrib import admin
from .models import Poster


@admin.register(Poster)
class PosterAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_active', 'display_order', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ('is_active', 'display_order')
    ordering = ('display_order', '-created_at')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description')
        }),
        ('Files', {
            'fields': ('image', 'pdf')
        }),
        ('Appearance', {
            'fields': ('background_color', 'text_color')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'display_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
