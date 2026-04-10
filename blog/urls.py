from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('simulate-your-own-eccentric-binary-black-holes/', views.analyzing_eccentric_bbh, name='analyzing-eccentric-bbh'),
    path('simulate-your-own-eccentric-binary-black-holes/simulate/', views.simulate_bbh, name='simulate-bbh'),
    path('simulate-your-own-eccentric-binary-black-holes/analyze/', views.analyze_bbh, name='analyze-bbh'),
    path('simulate-your-own-eccentric-binary-black-holes/eccentricity-distribution/', views.eccentricity_distribution, name='ecc-dist'),
    path('catalog-of-eccentric-binary-black-holes/', views.catalog_eccentric_bbh, name='catalog-eccentric-bbh'),
    path('catalog-of-eccentric-binary-black-holes/posteriors/', views.catalog_posteriors, name='catalog-posteriors'),
]
