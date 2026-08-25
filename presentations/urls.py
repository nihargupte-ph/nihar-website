from django.urls import path

from .views import archive

app_name = 'presentations'
urlpatterns = [
    path('presentations/', archive.index, name='index'),
    path('presentations/<slug:slug>/', archive.archive, name='archive'),
]
