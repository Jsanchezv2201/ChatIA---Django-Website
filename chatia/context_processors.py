from .models import Conversation, Message, UserPreference


def site_metrics(request):
    total_conversations = Conversation.objects.count()
    total_messages = Message.objects.count()
    user_conversations = 0
    user_messages = 0

    if request.user.is_authenticated:
        user_conversations = Conversation.objects.filter(user=request.user).count()
        user_messages = Message.objects.filter(conversation__user=request.user).count()
        # Ensure a UserPreference exists and include it in the template context
        try:
            user_pref, _ = UserPreference.objects.get_or_create(user=request.user)
        except Exception:
            user_pref = None

    return {
        'site_metrics': {
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'user_conversations': user_conversations,
            'user_messages': user_messages,
        },
        'user_preference': user_pref if request.user.is_authenticated else None,
    }
