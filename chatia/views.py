from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import PromptForm
from .models import Conversation, Message


@login_required
@require_GET
def home(request):
	conversations = request.user.conversations.all()
	return render(request, 'chatia/home.html', {'conversations': conversations})


@login_required
@require_POST
def conversation_create(request):
	conversation = Conversation.objects.create(user=request.user)
	return redirect('chatia:conversation_detail', conversation_id=conversation.id)


@login_required
@require_GET
def conversation_detail(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	context = {
		'conversation': conversation,
		'conversations': request.user.conversations.all(),
		'form': PromptForm(),
	}
	return render(request, 'chatia/conversation_detail.html', context)


@login_required
@require_POST
def send_message(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	form = PromptForm(request.POST)
	if not form.is_valid():
		context = {
			'conversation': conversation,
			'conversations': request.user.conversations.all(),
			'form': form,
			'error': 'El mensaje no es valido.',
		}
		return render(request, 'chatia/conversation_detail.html', context, status=400)

	user_text = form.cleaned_data['prompt'].strip()
	Message.objects.create(
		conversation=conversation,
		role=Message.ROLE_USER,
		content=user_text,
	)

	if conversation.title == 'Nueva conversacion' and user_text:
		conversation.title = user_text[:80]
		conversation.save(update_fields=['title', 'updated_at'])

	return redirect('chatia:conversation_detail', conversation_id=conversation.id)


@login_required
@require_GET
def info(request):
	return render(request, 'chatia/info.html')
