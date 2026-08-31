import secrets
import string

from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

INTERACTION_STATES = ('hidden', 'open', 'closed', 'revealed')
_CODE_ALPHABET = ''.join(c for c in string.ascii_uppercase + string.digits if c not in 'O0I1')


def make_join_code():
    return ''.join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def make_token():
    return secrets.token_hex(16)


class Session(models.Model):
    deck_slug = models.SlugField(max_length=80, db_index=True)
    join_code = models.CharField(max_length=6, unique=True, default=make_join_code)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    current_slide_id = models.CharField(max_length=80, blank=True, default='')
    interaction_states = models.JSONField(default=dict, blank=True)
    video_state = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['deck_slug'], condition=models.Q(is_locked=False),
                name='uniq_open_session_per_deck',
            )
        ]

    def __str__(self):
        return f'{self.deck_slug} [{self.join_code}]'

    # --- writers (presenter only) ---
    def bump(self):
        self.version = models.F('version') + 1
        self.save()
        self.refresh_from_db(fields=['version'])

    def _apply(self, fields, mutate):
        """Re-read the row under lock, apply `mutate(fresh)`, save the changed
        `fields` plus a version bump, then sync the result back onto self.
        Guards against a concurrent presenter request clobbering a
        read-modify-write on JSON fields like interaction_states."""
        with transaction.atomic():
            fresh = Session.objects.select_for_update().get(pk=self.pk)
            mutate(fresh)
            fresh.version = F('version') + 1
            fresh.save(update_fields=[*fields, 'version'])
        self.refresh_from_db()

    def set_slide(self, slide_id):
        def mutate(fresh):
            fresh.current_slide_id = slide_id
        self._apply(['current_slide_id'], mutate)

    def set_interaction_state(self, interaction_id, state):
        if state not in INTERACTION_STATES:
            raise ValueError(f'invalid state {state!r}')

        def mutate(fresh):
            states = dict(fresh.interaction_states)
            states[interaction_id] = state
            fresh.interaction_states = states
        self._apply(['interaction_states'], mutate)

    def set_video_state(self, playing, t):
        video_state = {'playing': bool(playing), 't': float(t), 'at': timezone.now().timestamp()}

        def mutate(fresh):
            fresh.video_state = video_state
        self._apply(['video_state'], mutate)

    def lock(self):
        def mutate(fresh):
            fresh.interaction_states = {
                k: ('revealed' if v in ('open', 'closed', 'revealed') else v)
                for k, v in fresh.interaction_states.items()
            }
            fresh.is_locked = True
            fresh.ended_at = timezone.now()
        self._apply(['interaction_states', 'is_locked', 'ended_at'], mutate)

    def unlock(self):
        def mutate(fresh):
            fresh.is_locked = False
            fresh.ended_at = None
        self._apply(['is_locked', 'ended_at'], mutate)

    def state_for(self, interaction_id):
        return self.interaction_states.get(interaction_id, 'hidden')

    # --- lookups ---
    @classmethod
    def open_for(cls, deck_slug):
        return cls.objects.filter(deck_slug=deck_slug, is_locked=False).order_by('-started_at').first()

    @classmethod
    def archived_for(cls, deck_slug):
        return cls.objects.filter(deck_slug=deck_slug, is_locked=True).order_by('-ended_at').first()


class Participant(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='participants')
    token = models.CharField(max_length=32, unique=True, default=make_token)
    display_name = models.CharField(max_length=60, blank=True, default='')
    expertise_tag = models.CharField(max_length=60)
    joined_at = models.DateTimeField(auto_now_add=True)
    ip_hash = models.CharField(max_length=64, blank=True, default='')

    def __str__(self):
        return self.display_name or f'anon-{self.token[:6]}'


class Response(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='responses')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='responses')
    interaction_id = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['participant', 'interaction_id'], name='uniq_response_per_participant')
        ]


class VisibleCommentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_hidden=False)


class Comment(models.Model):
    deck_slug = models.SlugField(max_length=80, db_index=True)
    slide_id = models.CharField(max_length=80, db_index=True)
    anchor = models.JSONField(null=True, blank=True)   # {"rect":[x,y,w,h]} | {"anchor":"fig-2"} | null
    author_name = models.CharField(max_length=60, blank=True, default='')
    participant = models.ForeignKey(Participant, null=True, blank=True, on_delete=models.SET_NULL)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_hidden = models.BooleanField(default=False)
    ip_hash = models.CharField(max_length=64, blank=True, default='')

    objects = models.Manager()
    visible = VisibleCommentManager()

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.deck_slug}/{self.slide_id}: {self.body[:40]}'
