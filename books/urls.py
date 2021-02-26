from django.conf.urls import url, include 
from . import views

urlpatterns = [
    url(r'^genres/$', views.genres, name='genres'),
    url(r'^index/$', views.index, name='index'),
    url(r'^result/$', views.result, name='result'),
    url(r'^signup/$', views.signup, name='signup'),
    url(r'^user_index/$', views.user_index, name='user_index'),
    url(r'^success/$', views.success, name='success'),
    url(r'^book_info/$', views.book_info, name='book_info'),
]
