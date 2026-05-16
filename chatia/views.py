import json

from django.conf import settings
from django.db.models import OuterRef, Subquery, Q
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST
from django.utils.text import slugify

from .forms import ConversationTitleForm, PromptForm
from .markdown_tools import conversation_to_markdown
from .models import Conversation, Message, MessageFeedback, UserPreference
from .services import ask_llm
from .services import ask_llm_stream
from django.utils.timezone import localtime


def conversation_messages_with_feedback(conversation, user):
	feedback_subquery = MessageFeedback.objects.filter(
		message=OuterRef('pk'),
		user=user,
	).values('value')[:1]
	return conversation.messages.annotate(user_feedback=Subquery(feedback_subquery))


def get_user_llm_preference(user):
	user_pref, _ = UserPreference.objects.get_or_create(user=user)
	return user_pref


def get_user_llm_model_label(user_pref):
	return dict(settings.LLM_MODEL_CHOICES).get(user_pref.llm_model, user_pref.llm_model)


def get_user_llm_model_options():
	return settings.LLM_MODEL_CATALOG

@require_GET
def home(request):
	recent_conversations = []
	if request.user.is_authenticated:
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
	messages = conversation_messages_with_feedback(conversation, request.user)
	user_pref = get_user_llm_preference(request.user)
	context = {
		'conversation': conversation,
		'messages': messages,
		'conversations': request.user.conversations.filter(is_archived=False),
		'conversation_title_form': ConversationTitleForm(initial={'title': conversation.title}),
		'form': PromptForm(),
		'user_preference': user_pref,
		'llm_model_label': get_user_llm_model_label(user_pref),
		'llm_model_options': get_user_llm_model_options(),
		'conversation_llm_model': conversation.llm_model,
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
def conversation_set_model(request, conversation_id):
	"""Actualizar el modelo LLM asignado a una conversación (solo modelos del catálogo)."""
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	selected = request.POST.get('llm_model', '').strip()
	# validar que el modelo esté en el catálogo
	allowed = [m['value'] for m in get_user_llm_model_options()]
	if selected and selected not in allowed:
		return JsonResponse({'ok': False, 'error': 'Modelo no permitido.'}, status=400)
	conversation.llm_model = selected or None
	conversation.save(update_fields=['llm_model', 'updated_at'])
	label = dict(settings.LLM_MODEL_CHOICES).get(selected, selected or '')
	return JsonResponse({'ok': True, 'llm_model': selected, 'label': label})


@login_required
@require_GET
def conversation_export_markdown(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	markdown_text = conversation_to_markdown(conversation)
	filename_slug = slugify(conversation.title)[:40] or 'conversacion'
	filename = f'chatia-conversacion-{conversation.id}-{filename_slug}.md'
	response = HttpResponse(markdown_text, content_type='text/markdown; charset=utf-8')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response


@login_required
@require_POST
def message_feedback(request, message_id):
	message = get_object_or_404(
		Message,
		id=message_id,
		conversation__user=request.user,
		role=Message.ROLE_ASSISTANT,
	)
	value = request.POST.get('value', '').strip().lower()
	if value not in {MessageFeedback.VALUE_UP, MessageFeedback.VALUE_DOWN}:
		if request.headers.get('x-requested-with') == 'XMLHttpRequest':
			return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)
		return redirect('chatia:conversation_detail', conversation_id=message.conversation_id)

	feedback, created = MessageFeedback.objects.get_or_create(
		message=message,
		user=request.user,
		defaults={'value': value},
	)
	if not created:
		if feedback.value == value:
			feedback.delete()
		else:
			feedback.value = value
			feedback.save(update_fields=['value', 'updated_at'])

	current_feedback = MessageFeedback.objects.filter(message=message, user=request.user).values_list('value', flat=True).first()
	response_payload = {
		'ok': True,
		'message_id': message.id,
		'value': current_feedback,
		'label': dict(MessageFeedback.VALUE_CHOICES).get(current_feedback, '') if current_feedback else '',
	}
	if request.headers.get('x-requested-with') == 'XMLHttpRequest':
		return JsonResponse(response_payload)
	return redirect('chatia:conversation_detail', conversation_id=message.conversation_id)


@login_required
@require_POST
def send_message(request, conversation_id):
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	if conversation.is_archived:
		messages = conversation_messages_with_feedback(conversation, request.user)
		user_pref = get_user_llm_preference(request.user)
		context = {
			'conversation': conversation,
			'conversations': request.user.conversations.all(),
			'messages': messages,
			'form': PromptForm(),
			'user_preference': user_pref,
			'llm_model_label': get_user_llm_model_label(user_pref),
			'error': 'La conversación está archivada. Desarchívala para seguir escribiendo.',
		}
		return render(request, 'chatia/conversation_detail.html', context, status=400)
	form = PromptForm(request.POST)
	if not form.is_valid():
		messages = conversation_messages_with_feedback(conversation, request.user)
		user_pref = get_user_llm_preference(request.user)
		context = {
			'conversation': conversation,
			'conversations': request.user.conversations.all(),
			'messages': messages,
			'form': form,
			'user_preference': user_pref,
			'llm_model_label': get_user_llm_model_label(user_pref),
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

	user_pref = get_user_llm_preference(request.user)
	# Prioritize per-conversation model, then user preference, then global default
	chosen_model = conversation.llm_model or user_pref.llm_model or settings.LLM_MODEL
	assistant_text = ask_llm(
		conversation,
		llm_model=chosen_model,
		llm_temperature=user_pref.llm_temperature,
		llm_max_tokens=user_pref.llm_max_tokens,
	)
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
	user_pref = get_user_llm_preference(request.user)

	def event_stream():
		assistant_chunks = []
		try:
			# Prioritize per-conversation model, then user preference, then global default
			chosen_model = conversation.llm_model or user_pref.llm_model or settings.LLM_MODEL
			for token in ask_llm_stream(
				conversation,
				llm_model=chosen_model,
				llm_temperature=user_pref.llm_temperature,
				llm_max_tokens=user_pref.llm_max_tokens,
			):
				assistant_chunks.append(token)
				payload = json.dumps({'token': token}, ensure_ascii=False)
				yield f'event: token\ndata: {payload}\n\n'
			assistant_text = ''.join(assistant_chunks).strip() or 'El modelo no devolvio contenido.'
		except Exception as exc:
			assistant_text = ask_llm(
				conversation,
				llm_model=chosen_model,
				llm_temperature=user_pref.llm_temperature,
				llm_max_tokens=user_pref.llm_max_tokens,
			)
			if assistant_text.startswith('Error ') or assistant_text.startswith('No se pudo'):
				payload = json.dumps({'message': assistant_text}, ensure_ascii=False)
				yield f'event: error\ndata: {payload}\n\n'

		Message.objects.create(
			conversation=conversation,
			role=Message.ROLE_ASSISTANT,
			content=assistant_text,
		)

		messages = conversation_messages_with_feedback(conversation, request.user)
		html = render_to_string('chatia/_messages.html', {'messages': messages}, request=request)
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
	q = (request.GET.get('q') or '').strip()
	base_q = Q()
	if q:
		# search in title or in any message content
		base_q = Q(title__icontains=q) | Q(messages__content__icontains=q)
	active_conversations = (
		request.user.conversations.filter(is_archived=False).filter(base_q).distinct()
	)
	archived_conversations = (
		request.user.conversations.filter(is_archived=True).filter(base_q).distinct()
	)
	return render(
		request,
		'chatia/_conversations_list.html',
		{
			'active_conversations': active_conversations,
			'archived_conversations': archived_conversations,
		},
	)


@login_required
def configuration(request):
	"""Mostrar y actualizar las preferencias personales del usuario (GET/POST).

	Las preferencias globales del servidor se muestran en lectura.
	"""
	user_pref, created = UserPreference.objects.get_or_create(user=request.user)
	from .forms import UserPreferenceForm

	if request.method == 'POST':
		form = UserPreferenceForm(request.POST)
		if form.is_valid():
			user_pref.llm_model = form.cleaned_data.get('llm_model') or user_pref.llm_model
			# alias: optional, allow empty string to clear
			alias = form.cleaned_data.get('alias')
			if alias is not None:
				user_pref.alias = alias.strip() or None
			llm_max_tokens = form.cleaned_data.get('llm_max_tokens')
			if llm_max_tokens:
				user_pref.llm_max_tokens = llm_max_tokens
			llm_temperature = form.cleaned_data.get('llm_temperature')
			if llm_temperature is not None:
				user_pref.llm_temperature = llm_temperature
			user_pref.save()
			return redirect('chatia:configuration')
	else:
		initial = {
			'llm_model': user_pref.llm_model,
			'alias': user_pref.alias,
			'llm_max_tokens': user_pref.llm_max_tokens,
			'llm_temperature': user_pref.llm_temperature,
		}
		form = UserPreferenceForm(initial=initial)

	selected_llm_model = form.data.get('llm_model') if form.is_bound else user_pref.llm_model
	if not selected_llm_model:
		selected_llm_model = user_pref.llm_model

	context = {
		'llm_base_url': settings.LLM_BASE_URL,
		'llm_model': settings.LLM_MODEL,
		'llm_max_tokens': settings.LLM_MAX_TOKENS,
		'llm_model_options': get_user_llm_model_options(),
		'user_preference': user_pref,
		'selected_llm_model': selected_llm_model,
		'form': form,
	}
	return render(request, 'chatia/configuration.html', context)
