from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404

# Poster configuration
POSTERS = {
    'eccentric-binary-black-holes': {
        'title': 'Eccentric Binary Black Holes',
        'description': 'Research poster on eccentric binary black hole systems',
        'image_path': 'homepage/images/eccentric_poster.jpg',
        'pdf_path': 'homepage/images/eccentric_poster.pdf',
        'background_color': '#453e5d',  
        'text_color': '#ffffff'
    },
    'binary-neutron-star-inference': {
        'title': 'Binary Neutron Star Inference',
        'description': 'Research poster on binary neutron star parameter inference',
        'image_path': 'homepage/images/dingo_bns_poster.jpg',
        'pdf_path': 'homepage/images/dingo_bns_poster.pdf',
        'background_color': '#2f2621',  # Saddle brown
        'text_color': '#ffffff'
    }
}

def publications(request):
    context = {}
    return render(request, 'homepage/publications.html', context)

def projects(request):
    context = {}
    return render(request, 'homepage/projects.html', context)

def poster_detail(request, poster_slug):
    """Dynamic view for displaying posters based on slug"""
    if poster_slug not in POSTERS:
        raise Http404("Poster not found")
    
    poster_data = POSTERS[poster_slug]
    context = {
        'poster': poster_data,
        'poster_slug': poster_slug
    }
    return render(request, 'homepage/poster_detail.html', context)

# Create your views here.


# Create your views here.
