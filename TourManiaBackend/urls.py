"""TourManiaBackend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from mongo_auth import views as mongo_auth_views
from TourMania import views

urlpatterns = [
    path('admin/', admin.site.urls),
    #path('mongo_auth/', include('mongo_auth.urls')),
    path('mongo_auth/signup/', mongo_auth_views.signup),
    path('mongo_auth/login/', views.login),
    path('tour/upsert/', views.upsert_tour),
    path('tour/images/upsert/', views.upsert_tour_images),
    path('tour/<username>/', views.get_tours_by_user),
    path('tour/images/by_id/', views.get_tour_images_by_tour_ids),
    path('tour/delete/<_id>/', views.delete_tour_by_id),

    path('get_test/', views.get_test),
    path('hello/', views.get_hello),
    path('hello_db/', views.get_hello_db),
]
