from django.urls import path

from . import views

app_name = 'chatia'

urlpatterns = [
    path('', views.home, name='home'),
]
