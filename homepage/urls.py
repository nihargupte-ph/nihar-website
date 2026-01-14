from django.urls import path 
from . import views

urlpatterns = [
    path('', views.publications, name="homepage"),
    path('projects/', views.projects, name="projects"),
    path('posters/<str:poster_slug>/', views.poster_detail, name="poster-detail"),
]