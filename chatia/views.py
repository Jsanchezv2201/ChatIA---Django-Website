import json

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
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
from django.contrib.auth import views as auth_views
from django.shortcuts import render


def conversation_messages_with_feedback(conversation, user):
	"""Devuelve los mensajes de una conversación anotando el voto del usuario en cada mensaje."""
	# Subquery: para cada mensaje buscamos si ese usuario ya votó ese mensaje.
	feedback_subquery = MessageFeedback.objects.filter(
		message=OuterRef('pk'),
		user=user,
	).values('value')[:1]
	# annotate() añade una columna virtual user_feedback a cada mensaje.
	return conversation.messages.annotate(user_feedback=Subquery(feedback_subquery))


def get_user_llm_preference(user):
	"""Obtiene o crea las preferencias LLM del usuario para usar sus ajustes personales."""
	# Si el usuario todavía no tiene preferencias, Django crea una fila nueva.
	user_pref, _ = UserPreference.objects.get_or_create(user=user)
	return user_pref


def get_user_llm_model_label(user_pref):
	"""Convierte el valor técnico del modelo en una etiqueta legible para la interfaz."""
	# El valor guardado puede ser el identificador técnico; aquí lo convertimos a nombre bonito.
	return dict(settings.LLM_MODEL_CHOICES).get(user_pref.llm_model, user_pref.llm_model)


def get_user_llm_model_options():
	"""Devuelve el catálogo de modelos disponibles para mostrarlo en formularios y selects."""
	# Se usa en la vista y en los templates para poblar el selector de modelos.
	return settings.LLM_MODEL_CATALOG

@require_GET
def home(request):
	"""Renderiza la página de inicio con accesos rápidos y conversaciones recientes."""
	recent_conversations = []
	if request.user.is_authenticated:
		# Solo mostramos conversaciones si hay sesión iniciada.
		recent_conversations = request.user.conversations.filter(is_archived=False)[:4]
	return render(
		request,
		'chatia/home.html',
		{'recent_conversations': recent_conversations},
	)


@login_required
@require_GET
def chats(request):
	"""Muestra el listado principal de conversaciones activas y archivadas."""
	# Separar activas y archivadas permite pintarlas de forma distinta en la interfaz.
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
	"""Crea una conversación nueva para el usuario autenticado y la abre enseguida."""
	conversation = Conversation.objects.create(user=request.user)
	return redirect('chatia:conversation_detail', conversation_id=conversation.id)


@login_required
@require_GET
def conversation_detail(request, conversation_id):
	"""Carga la pantalla principal de una conversación con mensajes, formulario y opciones."""
	# get_object_or_404 evita mostrar datos de conversaciones de otros usuarios.
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	messages = conversation_messages_with_feedback(conversation, request.user)
	user_pref = get_user_llm_preference(request.user)
	context = {
		'conversation': conversation,
		'conversation_messages': messages,
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
	"""Cambia el título de una conversación si el formulario contiene un nombre válido."""
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	form = ConversationTitleForm(request.POST)
	if form.is_valid():
		title = form.cleaned_data['title'].strip()
		if title:
			# Limitamos el título para evitar textos demasiado largos en la interfaz.
			conversation.title = title[:120]
			conversation.save(update_fields=['title', 'updated_at'])
	return redirect('chatia:conversation_detail', conversation_id=conversation.id)


@login_required
@require_POST
def conversation_toggle_archive(request, conversation_id):
	"""Alterna el estado archivado de una conversación para ocultarla o recuperarla."""
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	# Cambia entre archivada y activa con una sola pulsación.
	conversation.is_archived = not conversation.is_archived
	conversation.save(update_fields=['is_archived', 'updated_at'])
	return redirect('chatia:chats')


@login_required
@require_POST
def conversation_delete(request, conversation_id):
	"""Elimina una conversación del usuario autenticado."""
	# Borrado definitivo de la conversación y sus mensajes relacionados.
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	conversation.delete()
	return redirect('chatia:chats')


@login_required
@require_POST
def conversation_set_model(request, conversation_id):
	"""Guarda el modelo LLM elegido para esa conversación concreta si pertenece al catálogo permitido."""
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	selected = request.POST.get('llm_model', '').strip()
	# Comprobamos que el modelo viene de la lista permitida y no de un valor inventado.
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
	"""Exporta la conversación actual como un archivo Markdown descargable."""
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	# markdown_tools convierte el historial a texto .md para descargarlo.
	markdown_text = conversation_to_markdown(conversation)
	filename_slug = slugify(conversation.title)[:40] or 'conversacion'
	filename = f'chatia-conversacion-{conversation.id}-{filename_slug}.md'
	response = HttpResponse(markdown_text, content_type='text/markdown; charset=utf-8')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response


@login_required
@require_POST
def message_feedback(request, message_id):
	"""Guarda, cambia o elimina el voto útil/no útil de un mensaje del asistente."""
	# Solo permitimos valorar mensajes del asistente que pertenezcan al usuario.
	message = get_object_or_404(
		Message,
		id=message_id,
		conversation__user=request.user,
		role=Message.ROLE_ASSISTANT,
	)
	value = request.POST.get('value', '').strip().lower()
	if value not in {MessageFeedback.VALUE_UP, MessageFeedback.VALUE_DOWN}:
		# Si la petición viene por AJAX devolvemos JSON; si no, volvemos a la conversación.
		if request.headers.get('x-requested-with') == 'XMLHttpRequest':
			return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)
		return redirect('chatia:conversation_detail', conversation_id=message.conversation_id)

	feedback, created = MessageFeedback.objects.get_or_create(
		message=message,
		user=request.user,
		defaults={'value': value},
	)
	if not created:
		# Si el usuario pulsa otra vez el mismo voto, lo quitamos.
		if feedback.value == value:
			feedback.delete()
		else:
			# Si cambia de opinión, actualizamos el voto guardado.
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
	"""Procesa un mensaje normal, llama al LLM y guarda tanto la pregunta como la respuesta."""
	# No permitimos escribir en conversaciones archivadas.
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	if conversation.is_archived:
		messages = conversation_messages_with_feedback(conversation, request.user)
		user_pref = get_user_llm_preference(request.user)
		context = {
			'conversation': conversation,
			'conversations': request.user.conversations.all(),
			'conversation_messages': messages,
			'form': PromptForm(),
			'user_preference': user_pref,
			'llm_model_label': get_user_llm_model_label(user_pref),
			'error': 'La conversación está archivada. Desarchívala para seguir escribiendo.',
		}
		return render(request, 'chatia/conversation_detail.html', context, status=400)
	form = PromptForm(request.POST)
	if not form.is_valid():
		# Si el formulario falla, devolvemos la misma pantalla pero con error.
		messages = conversation_messages_with_feedback(conversation, request.user)
		user_pref = get_user_llm_preference(request.user)
		context = {
			'conversation': conversation,
			'conversations': request.user.conversations.all(),
			'conversation_messages': messages,
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
	# Prioridad de modelo: conversación > usuario > configuración global.
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
	"""Procesa un mensaje y devuelve la respuesta del LLM en streaming mediante SSE."""
	# SSE permite enviar tokens poco a poco sin esperar al texto completo.
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
		"""Generador interno que emite eventos SSE con tokens, errores y el HTML final actualizado."""
		assistant_chunks = []
		try:
			# Misma prioridad de modelo que en send_message().
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
				# Si el streaming falla, hacemos fallback al modo normal.
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

		conversation_messages = conversation_messages_with_feedback(conversation, request.user)
		# Cuando termina el streaming, devolvemos el HTML actualizado de mensajes.
		html = render_to_string('chatia/_messages.html', {'conversation_messages': conversation_messages}, request=request)
		payload = json.dumps({'html': html}, ensure_ascii=False)
		yield f'event: done\ndata: {payload}\n\n'

	response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
	response['Cache-Control'] = 'no-cache'
	response['X-Accel-Buffering'] = 'no'
	return response


@login_required
@require_GET
def info(request):
	"""Muestra la página de ayuda y documentación del proyecto."""
	return render(request, 'chatia/info.html')


def not_found(request, unknown_path=None):
	"""Muestra una página 404 personalizada cuando la ruta no existe."""
	# unknown_path permite enseñar al usuario qué dirección intentó abrir.
	return render(
		request,
		'404.html',
		{'unknown_path': unknown_path or request.path},
		status=404,
	)


@login_required
@require_GET
def profile(request):
	"""Muestra un resumen del usuario con sus métricas y conversaciones recientes."""
	# Calculamos estadísticas simples para mostrarlas en la tarjeta de perfil.
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
	"""Devuelve en JSON la lista de conversaciones del usuario autenticado.

	Sirve para integraciones externas o para depurar datos desde el navegador.
	"""
	conversations = request.user.conversations.all().order_by('-updated_at')
	# Construimos una lista simple de diccionarios para que el frontend la consuma fácil.
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
	"""Devuelve en JSON estadísticas globales y personales del usuario.

	Se usa para paneles de métricas, depuración o consumo desde frontend.
	"""
	# Aquí resumimos los contadores para paneles o depuración.
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
def api_conversation_detail(request, conversation_id):
	"""Devuelve en JSON una conversación concreta con sus mensajes y metadatos."""
	conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
	# Ordenamos por fecha para reconstruir el hilo de la conversación en la UI.
	messages = [
		{
			'id': m.id,
			'role': m.role,
			'content': m.content,
			'created_at': localtime(m.created_at).isoformat(),
		}
		for m in conversation.messages.order_by('created_at')
	]

	try:
		# Si existe alias, se muestra en lugar del nombre de usuario.
		pref = getattr(conversation.user, 'preference', None)
		username_display = pref.alias if pref and pref.alias else conversation.user.username
	except Exception:
		username_display = conversation.user.username

	data = {
		'id': conversation.id,
		'title': conversation.title,
		'user': username_display,
		'is_archived': conversation.is_archived,
		'created_at': localtime(conversation.created_at).isoformat(),
		'updated_at': localtime(conversation.updated_at).isoformat(),
		'messages': messages,
	}
	return JsonResponse(data)


@login_required
@require_GET
def conversations_partial(request):
	"""Devuelve el fragmento HTML que HTMX inserta para refrescar la lista de conversaciones."""
	# Lee el texto de búsqueda enviado por HTMX.
	q = (request.GET.get('q') or '').strip()
	base_q = Q()
	if q:
		# Buscamos tanto en el título como en el contenido de los mensajes.
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
	"""Muestra y guarda la configuración personal del usuario, dejando la global solo en lectura."""
	# get_or_create asegura que exista una fila de preferencias para este usuario.
	user_pref, created = UserPreference.objects.get_or_create(user=request.user)
	from .forms import UserPreferenceForm

	if request.method == 'POST':
		# En POST intentamos guardar los cambios enviados desde el formulario.
		form = UserPreferenceForm(request.POST)
		if form.is_valid():
			user_pref.llm_model = form.cleaned_data.get('llm_model') or user_pref.llm_model
			# alias es opcional: si viene vacío, lo guardamos como None para limpiar el campo.
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
		# En GET rellenamos el formulario con los valores actuales.
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


class CustomLoginView(auth_views.LoginView):
	"""Login personalizado que devuelve 401 cuando el usuario o la contraseña no son válidos."""
	template_name = 'registration/login.html'

	def form_invalid(self, form):
		"""Reutiliza la plantilla de login, pero fuerza el estado HTTP 401."""
		# Django por defecto responde 200; aquí dejamos claro que las credenciales fallaron.
		context = self.get_context_data(form=form)
		return render(self.request, self.template_name, context, status=401)


def register(request):
	"""Permite crear un usuario nuevo desde la web y dejarlo iniciado sesión al terminar."""
	if request.user.is_authenticated:
		return redirect('chatia:home')

	if request.method == 'POST':
		form = UserCreationForm(request.POST)
		if form.is_valid():
			user = form.save()
			# Iniciamos sesión automáticamente para que el usuario entre directo al proyecto.
			login(request, user)
			messages.success(request, 'Cuenta creada correctamente.')
			return redirect('chatia:home')
	else:
		form = UserCreationForm()

	return render(request, 'registration/register.html', {'form': form})
