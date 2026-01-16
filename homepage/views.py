from django.shortcuts import render, get_object_or_404
from .models import Poster


def publications(request):
    """Display publications and projects page"""
    context = {}
    return render(request, 'homepage/publications.html', context)


def projects(request):
    """Display projects page"""
    context = {}
    return render(request, 'homepage/projects.html', context)


def poster_detail(request, poster_slug):
    """Display individual poster detail page"""
    poster = get_object_or_404(Poster, slug=poster_slug, is_active=True)
    context = {
        'poster': poster,
        'poster_slug': poster_slug
    }
    return render(request, 'homepage/poster_detail.html', context)
