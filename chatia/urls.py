from django.urls import path

from . import views

app_name = 'chatia'

urlpatterns = [
    path('', views.home, name='home'),
    path('chats/', views.chats, name='chats'),
    path('profile/', views.profile, name='profile'),
    path('configuration/', views.configuration, name='configuration'),
    path('info/', views.info, name='info'),
    path('conversations/new/', views.conversation_create, name='conversation_create'),
    path('conversations/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path(
        'conversations/<int:conversation_id>/send-stream/',
        views.send_message_stream,
        name='send_message_stream',
    ),
    path('conversations/<int:conversation_id>/send/', views.send_message, name='send_message'),
]
