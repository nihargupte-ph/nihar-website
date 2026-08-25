from django.urls import path

from .views import archive, common

app_name = 'presentations'
urlpatterns = [
    path('presentations/', archive.index, name='index'),
    path('presentations/<slug:slug>/', archive.archive, name='archive'),
    path('presentations/<slug:slug>/aggregate/<str:iid>/', common.placeholder, name='archive-aggregate'),
    path('presentations/<slug:slug>/comment/', common.placeholder, name='comment'),
]
