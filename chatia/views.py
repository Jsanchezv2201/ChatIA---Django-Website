import json

from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from .forms import ConversationTitleForm, PromptForm
from .models import Conversation, Message, UserPreference
from .services import ask_llm
from .services import ask_llm_stream
from django.utils.timezone import localtime


@login_required
@require_GET
def home(request):
	recent_conversations = request.user.conversations.filter(is_archived=False)[:4]
	return render(
		request,
		'chatia/home.html',
		{'recent_conversations': recent_conversations},
	)


@login_required
@require_GET
def chats(request):
	active_conversations = request.user.conversations.filter(is_archived=False)
	archived_conversations = request.user.conversations.filter(is_archived=True)
	return render(
		request,
		'chatia/chats.html',
		{
			'active_conversations': active_conversations,
			'archived_conversations': archived_conversations,
		},
	)


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
		'conversation_title_form': ConversationTitleForm(initial={'title': conversation.title}),
		'form': PromptForm(),
	}
	return render(request, 'chatia/conversation_detail.html', context)


@login_required
@require_POST
def conversation_rename(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	form = ConversationTitleForm(request.POST)
	if form.is_valid():
		title = form.cleaned_data['title'].strip()
		if title:
			conversation.title = title[:120]
			conversation.save(update_fields=['title', 'updated_at'])
	return redirect('chatia:conversation_detail', conversation_id=conversation.id)


@login_required
@require_POST
def conversation_toggle_archive(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	conversation.is_archived = not conversation.is_archived
	conversation.save(update_fields=['is_archived', 'updated_at'])
	return redirect('chatia:chats')


@login_required
@require_POST
def conversation_delete(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	conversation.delete()
	return redirect('chatia:chats')


@login_required
@require_POST
def send_message(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	if conversation.is_archived:
		context = {
			'conversation': conversation,
			'conversations': request.user.conversations.all(),
			'form': PromptForm(),
			'error': 'La conversación está archivada. Desarchívala para seguir escribiendo.',
		}
		return render(request, 'chatia/conversation_detail.html', context, status=400)
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
	if conversation.is_archived:
		return StreamingHttpResponse(
			'event: error\ndata: {"message":"La conversación está archivada. Desarchívala para seguir escribiendo."}\n\n',
			content_type='text/event-stream',
			status=400,
		)
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
def api_conversations(request):
	"""Devuelve JSON con la lista de conversaciones del usuario autenticado.

	Usos: consumidores API (devuelve JSON). Requiere autenticación por sesión (usuario logueado).
	Ejemplo de respuesta: [{"id":1, "title":"...", "updated_at":"...", "messages":3}, ...]
	"""
	conversations = request.user.conversations.all().order_by('-updated_at')
	data = [
		{
			'id': c.id,
			'title': c.title,
			'is_archived': c.is_archived,
			'updated_at': localtime(c.updated_at).isoformat(),
			'messages': c.messages.count(),
		}
		for c in conversations
	]
	return JsonResponse(data, safe=False)


@login_required
@require_GET
def api_statistics(request):
	"""Devuelve estadísticas en JSON (globales y del usuario).

	Usos: herramientas de monitorización o frontend que muestren métricas. Requiere autenticación por sesión.
	Ejemplo de respuesta: {"total_conversations":42, "total_messages":317, ...}
	"""
	total_conversations = Conversation.objects.count()
	total_messages = Message.objects.count()
	user_conversations = request.user.conversations.count()
	user_messages = sum(c.messages.count() for c in request.user.conversations.all())
	return JsonResponse(
		{
			'total_conversations': total_conversations,
			'total_messages': total_messages,
			'user_conversations': user_conversations,
			'user_messages': user_messages,
		}
	)


@login_required
@require_GET
def conversations_partial(request):
	"""Devuelve un fragmento HTML con las conversaciones del usuario (usado por HTMX).

	HTMX realizará un GET a esta vista y reemplazará un contenedor en la página padre
	con el HTML devuelto (ver `chats.html` para el contenedor objetivo).
	"""
	active_conversations = request.user.conversations.filter(is_archived=False)
	archived_conversations = request.user.conversations.filter(is_archived=True)
	return render(
		request,
		'chatia/_conversations_list.html',
		{
			'active_conversations': active_conversations,
			'archived_conversations': archived_conversations,
		},
	)


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
