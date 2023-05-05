"""federated_network URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
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
from django.urls import path, re_path

from lemon import views

urlpatterns = [
    re_path(r'^@(\w+)/notes/note-create-validator', views.note_create_validator),
    re_path(r'^@(\w+)/notes/note-create', views.note_create, name="note-create"),
    re_path(r'^@(\w+)/notes/(\w+)', views.note_view, name="note"),
    re_path(r'^@(\w+)/notes', views.notes_view, name="notes"),
    # re_path(r'^@(\w+)/inbox/(\w+)', views.activity, name="inbox_item"),
    re_path(r'^@(\w+)/inbox', views.inbox_view, name="inbox"),
    # re_path(r'^@(\w+)/outbox/outbox-filter', views.outbox_filter, name="outbox-filter"),
    re_path(r'^@(\w+)/outbox/(\w+)', views.activity, name="activity"),
    re_path(r'^@(\w+)/outbox', views.outbox_view, name="outbox"),
    re_path(r'^@(\w+)/liked', views.liked_view, name="liked"),
    re_path(r'^@(\w+)/following', views.following_view, name="following"),
    re_path(r'^@(\w+)/followers', views.followers_view, name="followers"),
    re_path(r'follow/', views.following_action),
    re_path(r'^@([^/]+)$', views.person_main, name="person"),
    path("undo-likepost/", views.undo_likepost, name="undo_likepost"),
    path("likepost/", views.likepost, name="likepost"),
    path("sign-up/", views.sign_up, name="sign-up"),
    path("logout/", views.logout_view, name="logout"),
    path("about/", views.about, name="about"),
    # path("sse", views.sse, name="sse"),
    path("", views.sign_in, name="sign-in"),
]
