from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('analyzing-eccentric-binary-black-holes/', views.analyzing_eccentric_bbh, name='analyzing-eccentric-bbh'),
    path('analyzing-eccentric-binary-black-holes/simulate/', views.simulate_bbh, name='simulate-bbh'),
    path('analyzing-eccentric-binary-black-holes/analyze/', views.analyze_bbh, name='analyze-bbh'),
    path('analyzing-eccentric-binary-black-holes/eccentricity-distribution/', views.eccentricity_distribution, name='ecc-dist'),
]
