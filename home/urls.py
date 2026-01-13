from django.urls import path
from django.views.decorators.cache import cache_page

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('index', views.index, name='index'),
    #path('search', cache_page(60*60*24*30)(views.search), name='search'),
    #path('calculate', views.calculate, name='calculate'),
    path('datasets', views.datasets, name='datasets'),
    #path('get_csv/<str:x>/<str:y>', views.get_csv, name='get_csv'),
    path('about', views.about, name='about'),
    #path('documentation', views.documentation, name='documentation')
]