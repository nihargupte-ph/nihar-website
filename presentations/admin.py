from django.contrib import admin
from .models import Session, Participant, Response, Comment


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('deck_slug', 'join_code', 'started_at', 'ended_at', 'is_locked', 'version')
    list_filter = ('deck_slug', 'is_locked')


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'session', 'expertise_tag', 'joined_at')
    list_filter = ('session__deck_slug', 'expertise_tag')


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('interaction_id', 'participant', 'session', 'updated_at')
    list_filter = ('session__deck_slug', 'interaction_id')


@admin.action(description='Hide selected comments')
def hide_comments(modeladmin, request, queryset):
    queryset.update(is_hidden=True)


@admin.action(description='Unhide selected comments')
def unhide_comments(modeladmin, request, queryset):
    queryset.update(is_hidden=False)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('deck_slug', 'slide_id', 'author_name', 'body', 'created_at', 'is_hidden')
    list_filter = ('deck_slug', 'is_hidden')
    actions = [hide_comments, unhide_comments]
