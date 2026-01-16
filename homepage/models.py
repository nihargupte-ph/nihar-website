from django.db import models
from django.utils.text import slugify


class Poster(models.Model):
    """Model for research posters displayed on the website"""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, help_text="URL-friendly version of the title")
    description = models.TextField()
    image = models.ImageField(upload_to='posters/images/', help_text="Poster image (JPG/PNG)")
    pdf = models.FileField(upload_to='posters/pdfs/', help_text="Poster PDF file")
    background_color = models.CharField(max_length=7, default='#453e5d', help_text="Hex color code (e.g., #453e5d)")
    text_color = models.CharField(max_length=7, default='#ffffff', help_text="Hex color code (e.g., #ffffff)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Display this poster on the website")
    display_order = models.IntegerField(default=0, help_text="Order in which to display (lower numbers first)")

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'Poster'
        verbose_name_plural = 'Posters'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
