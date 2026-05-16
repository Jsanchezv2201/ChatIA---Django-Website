from django.contrib import admin
from django.db.models import Count, Q

from .models import Conversation, Message, MessageFeedback, UserPreference


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
	list_display = ('id', 'user', 'title', 'is_archived', 'updated_at')
	list_filter = ('is_archived',)
	search_fields = ('title', 'user__username')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ('id', 'conversation', 'role', 'created_at')
	list_filter = ('role',)
	search_fields = ('content',)
	readonly_fields = ('created_at',)


@admin.register(MessageFeedback)
class MessageFeedbackAdmin(admin.ModelAdmin):
	list_display = ('id', 'message', 'user', 'value', 'created_at')
	list_filter = ('value', 'created_at')
	search_fields = ('message__content', 'user__username')
	readonly_fields = ('created_at', 'updated_at')
	change_list_template = 'admin/chatia/messagefeedback/change_list.html'

	def changelist_view(self, request, extra_context=None):
		stats = MessageFeedback.objects.aggregate(
			total=Count('id'),
			useful=Count('id', filter=Q(value=MessageFeedback.VALUE_UP)),
			not_useful=Count('id', filter=Q(value=MessageFeedback.VALUE_DOWN)),
		)
		total = stats['total'] or 0
		useful = stats['useful'] or 0
		not_useful = stats['not_useful'] or 0
		useful_ratio = round((useful / total) * 100, 1) if total else 0
		extra_context = extra_context or {}
		extra_context['feedback_stats'] = {
			'total': total,
			'useful': useful,
			'not_useful': not_useful,
			'useful_ratio': useful_ratio,
		}
		return super().changelist_view(request, extra_context=extra_context)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
	list_display = ('user', 'alias', 'llm_model', 'llm_max_tokens', 'llm_temperature', 'updated_at')
	search_fields = ('user__username', 'alias')
	readonly_fields = ('created_at', 'updated_at')

