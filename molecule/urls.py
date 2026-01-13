from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('browse/<str:dataset_id>/', views.index, name='index'),
    path('download/', views.download, name='molecule_download'),
    # More specific patterns must come before generic patterns
    path('dummymolview/<str:molid>/', views.dummymolview, name='dummymolview'),
    path('<str:molid>/download/', views.download_single_molecule, name='molecule_single_download'),
    path('<str:molid>/', views.molecule, name='molecule'),
]