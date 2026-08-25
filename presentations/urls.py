from django.urls import path

from .views import archive, common, phone, present

app_name = 'presentations'
urlpatterns = [
    path('presentations/', archive.index, name='index'),
    path('presentations/<slug:slug>/', archive.archive, name='archive'),
    path('presentations/<slug:slug>/aggregate/<str:iid>/', archive.archive_aggregate, name='archive-aggregate'),
    path('presentations/<slug:slug>/comment/', common.placeholder, name='comment'),
    path('presentations/<slug:slug>/present/', present.present, name='present'),
    path('presentations/<slug:slug>/present/state/', present.state, name='present-state'),
    path('presentations/<slug:slug>/present/goto/', present.goto, name='present-goto'),
    path('presentations/<slug:slug>/present/interaction/<str:iid>/<str:state>/', present.interaction, name='present-interaction'),
    path('presentations/<slug:slug>/present/video/', present.video, name='present-video'),
    path('presentations/<slug:slug>/present/lock/', present.lock, name='present-lock'),
    path('presentations/<slug:slug>/present/unlock/', present.unlock, name='present-unlock'),
    path('p/<str:code>/', phone.phone, name='phone'),
    path('p/<str:code>/join/', phone.join, name='phone-join'),
    path('p/<str:code>/state/', phone.state, name='phone-state'),
    path('p/<str:code>/respond/<str:iid>/', phone.respond, name='phone-respond'),
    path('p/<str:code>/aggregate/<str:iid>/', phone.aggregate, name='phone-aggregate'),
]
