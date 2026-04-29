from django.contrib import admin

from .models import Conversation, Message, UserPreference


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'title', 'updated_at')
	search_fields = ('title', 'user__username')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ('id', 'conversation', 'role', 'created_at')
	list_filter = ('role',)
	search_fields = ('content',)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
	list_display = ('user', 'llm_model', 'llm_max_tokens', 'llm_temperature', 'updated_at')
	search_fields = ('user__username',)
	readonly_fields = ('created_at', 'updated_at')

