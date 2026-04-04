from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('analyzing-eccentric-binary-black-holes/', views.analyzing_eccentric_bbh, name='analyzing-eccentric-bbh'),
]
