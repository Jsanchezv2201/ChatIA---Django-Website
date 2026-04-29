import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from .forms import PromptForm
from .models import Conversation, Message, UserPreference
from .services import ask_llm
from .services import ask_llm_stream


@login_required
@require_GET
def home(request):
	recent_conversations = request.user.conversations.all()[:4]
	return render(
		request,
		'chatia/home.html',
		{'recent_conversations': recent_conversations},
	)


@login_required
@require_GET
def chats(request):
	conversations = request.user.conversations.all()
	return render(request, 'chatia/chats.html', {'conversations': conversations})


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

	assistant_text = ask_llm(conversation)
	Message.objects.create(
		conversation=conversation,
		role=Message.ROLE_ASSISTANT,
		content=assistant_text,
	)

	return redirect('chatia:conversation_detail', conversation_id=conversation.id)


@login_required
@require_POST
def send_message_stream(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	form = PromptForm(request.POST)
	if not form.is_valid():
		return StreamingHttpResponse(
			'event: error\ndata: {"message":"El mensaje no es valido."}\n\n',
			content_type='text/event-stream',
			status=400,
		)

	user_text = form.cleaned_data['prompt'].strip()
	Message.objects.create(
		conversation=conversation,
		role=Message.ROLE_USER,
		content=user_text,
	)

	if conversation.title == 'Nueva conversacion' and user_text:
		conversation.title = user_text[:80]
		conversation.save(update_fields=['title', 'updated_at'])

	def event_stream():
		assistant_chunks = []
		try:
			for token in ask_llm_stream(conversation):
				assistant_chunks.append(token)
				payload = json.dumps({'token': token}, ensure_ascii=False)
				yield f'event: token\ndata: {payload}\n\n'
			assistant_text = ''.join(assistant_chunks).strip() or 'El modelo no devolvio contenido.'
		except Exception as exc:
			assistant_text = ask_llm(conversation)
			if assistant_text.startswith('Error ') or assistant_text.startswith('No se pudo'):
				payload = json.dumps({'message': assistant_text}, ensure_ascii=False)
				yield f'event: error\ndata: {payload}\n\n'

		Message.objects.create(
			conversation=conversation,
			role=Message.ROLE_ASSISTANT,
			content=assistant_text,
		)

		html = render_to_string('chatia/_messages.html', {'conversation': conversation}, request=request)
		payload = json.dumps({'html': html}, ensure_ascii=False)
		yield f'event: done\ndata: {payload}\n\n'

	response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
	response['Cache-Control'] = 'no-cache'
	response['X-Accel-Buffering'] = 'no'
	return response


@login_required
@require_GET
def info(request):
	return render(request, 'chatia/info.html')


@login_required
@require_GET
def profile(request):
	recent_conversations = request.user.conversations.all()[:5]
	total_messages = sum(c.messages.count() for c in request.user.conversations.all())
	last_conversation = request.user.conversations.first()
	context = {
		'recent_conversations': recent_conversations,
		'total_messages': total_messages,
		'last_conversation': last_conversation,
	}
	return render(request, 'chatia/profile.html', context)


@login_required
@require_GET
def configuration(request):
	user_pref, created = UserPreference.objects.get_or_create(user=request.user)
	context = {
		'llm_base_url': settings.LLM_BASE_URL,
		'llm_model': settings.LLM_MODEL,
		'llm_max_tokens': settings.LLM_MAX_TOKENS,
		'user_preference': user_pref,
	}
	return render(request, 'chatia/configuration.html', context)
