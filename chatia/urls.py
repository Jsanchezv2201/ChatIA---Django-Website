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
    path('conversations/<int:conversation_id>/rename/', views.conversation_rename, name='conversation_rename'),
    path('conversations/<int:conversation_id>/archive-toggle/', views.conversation_toggle_archive, name='conversation_toggle_archive'),
    path('conversations/<int:conversation_id>/delete/', views.conversation_delete, name='conversation_delete'),
    path(
        'conversations/<int:conversation_id>/send-stream/',
        views.send_message_stream,
        name='send_message_stream',
    ),
    path('conversations/<int:conversation_id>/send/', views.send_message, name='send_message'),
    # JSON endpoints for Fase 8
    path('api/conversations/', views.api_conversations, name='api_conversations'),
    path('api/statistics/', views.api_statistics, name='api_statistics'),
    # Partial HTML for HTMX
    path('conversations/partial/', views.conversations_partial, name='conversations_partial'),
]
