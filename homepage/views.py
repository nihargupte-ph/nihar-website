from django.shortcuts import render
from django.http import Http404


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
    posters = {
        'eccentric-binary-black-holes': {
            'title': 'Eccentric Binary Black Holes',
            'description': '',
            'image': 'images/posters/eccentric_poster.jpg',
            'pdf': 'images/posters/eccentric_poster.pdf',
            'background_color': '#453e5d',
            'text_color': '#ffffff',
        },
        'binary-neutron-star-inference': {
            'title': 'Binary Neutron Star Inference',
            'description': '',
            'image': 'images/posters/dingo_bns_poster.jpg',
            'pdf': 'images/posters/dingo_bns_poster.pdf',
            'background_color': '#2b2220',
            'text_color': '#ffffff',
        },
    }

    if poster_slug not in posters:
        raise Http404(f"Poster '{poster_slug}' not found")

    context = {
        'poster': posters[poster_slug],
        'poster_slug': poster_slug,
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
            'title': '',
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
