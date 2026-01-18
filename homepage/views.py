from django.shortcuts import render, get_object_or_404
from django.http import Http404
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


def mindmap_viewer(request, mindmap_slug):
    """Display interactive mindmap viewer with SVG pan-zoom."""
    mindmaps = {
        'physics': {
            'title': '',
            'description': 'A comprehensive visualization of physics concepts and their interconnections.',
            'svg_path': 'mindmaps/physics.svg',
        },
        'cs': {
            'title': 'Computer Science Mindmap',
            'description': 'A comprehensive visualization of computer science concepts.',
            'svg_path': 'mindmaps/cs-stat.svg',
        },
    }

    if mindmap_slug not in mindmaps:
        raise Http404(f"Mindmap '{mindmap_slug}' not found")

    mindmap = mindmaps[mindmap_slug]

    context = {
        'mindmap_slug': mindmap_slug,
        'mindmap_title': mindmap['title'],
        'mindmap_description': mindmap['description'],
        'svg_path': mindmap['svg_path'],
    }

    return render(request, 'homepage/mindmap_viewer.html', context)
