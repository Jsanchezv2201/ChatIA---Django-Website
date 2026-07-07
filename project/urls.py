"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.urls import include, path
from chatia.views import CustomLoginView, not_found, register

urlpatterns = [
    path('admin/', admin.site.urls),
    # Override the login view so failed attempts return HTTP 401
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    # Registration page to create new users without using the admin site
    path('accounts/register/', register, name='register'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('chatia.urls')),
    # Catch-all al final para mostrar una 404 propia en rutas inexistentes.
    path('<path:unknown_path>', not_found, name='not_found'),
]
