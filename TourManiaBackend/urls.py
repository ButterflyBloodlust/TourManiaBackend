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
from TourMania import views

urlpatterns = [
    #path('mongo_auth/', include('mongo_auth.urls')),
    path('mongo_auth/signup/', views.signup),
    path('mongo_auth/login/', views.login),
    path('tour/upsert/', views.upsert_tour),
    path('tour/images/upsert/', views.upsert_tour_images),
    path('tour/id/<_id>', views.get_tour_by_tour_id),
    path('tour/i/id/<tour_id>/', views.get_tour_images_by_tour_id),
    path('tour/id/<tour_id>/rate', views.rate_tour),
    path('tour/u/<username>/', views.get_full_tours_by_user),
    path('tour/u/<username>/overviews', views.get_nearby_tours_overviews_by_user),
    path('tour/images/by_id/', views.get_tour_images_by_tour_ids),
    path('tour/delete/<_id>/', views.delete_tour_by_id),
    path('tour/search/<phrase>', views.search_tours_by_phrase),
    path('tour/near', views.get_nearby_tours),
    path('user/favs/add/', views.add_tour_to_favourites),
    path('user/favs/delete/<tour_id>/', views.delete_tour_from_favourites),
    path('user/<username>/favs/', views.get_fav_tours_by_user),
    path('user/prefs/', views.update_user_settings),
    path('tour_guide/near', views.get_nearby_tour_guides),
    path('tour_guide', views.get_tour_guide_info),
    path('tour_guide/<tour_guide_username>/rate', views.rate_tour_guide),
    path('tour_guide/search/<phrase>', views.search_tour_guides_by_phrase),
    path('tour_guide/image/upsert', views.update_user_image),
    path('tour_guide/image/get', views.get_tour_guide_image),

    ### Location sharing components ###
    path('tour_guide/loc/update', views.update_tour_guide_location),
    path('tour_guide/loc/get', views.get_tour_guide_location),
    path('tour_guide/loc/sub', views.subscribe_to_tour_guide_location),
    path('tour_guide/loc/token', views.get_location_sharing_token),
    path('tour_guide/loc/token/revoke', views.revoke_sharing_location_token),
    path('tour_guide/image/by_nickname/', views.get_tour_guides_images_by_nicknames),

    path('get_test/', views.get_test),
    path('hello/', views.get_hello),
    path('hello_db/', views.get_hello_db),
]
