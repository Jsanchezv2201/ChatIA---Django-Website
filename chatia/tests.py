from django.conf import settings
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json
from unittest.mock import patch

from .models import Conversation, Message, UserPreference
from .forms import PromptForm
from .services import build_messages_payload


class AuthenticationTests(TestCase):
	"""Tests de autenticación y acceso a recursos protegidos."""

	def setUp(self):
		"""Configurar cliente y usuario de prueba."""
		self.client = Client()
		self.user = User.objects.create_user(
			username='testuser',
			email='test@example.com',
			password='testpass123'
		)

	def test_home_is_public(self):
		"""Test: la página principal es accesible sin autenticación."""
		response = self.client.get(reverse('chatia:home'))
		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'chatia/home.html')

	def test_authenticated_user_can_access_home(self):
		"""Test: usuario autenticado puede acceder a home."""
		self.client.login(username='testuser', password='testpass123')
		response = self.client.get(reverse('chatia:home'))
		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'chatia/home.html')


class ConversationTests(TestCase):
	"""Tests de creación y gestión de conversaciones."""

	def setUp(self):
		"""Configurar cliente y usuario de prueba."""
		self.client = Client()
		self.user = User.objects.create_user(
			username='testuser',
			email='test@example.com',
			password='testpass123'
		)
		self.other_user = User.objects.create_user(
			username='otheruser',
			email='other@example.com',
			password='otherpass123'
		)
		self.client.login(username='testuser', password='testpass123')

	def test_create_conversation(self):
		"""Test: crear una conversación nueva."""
		response = self.client.post(reverse('chatia:conversation_create'))
		self.assertEqual(response.status_code, 302)
		conversation = Conversation.objects.filter(user=self.user).first()
		self.assertIsNotNone(conversation)
		self.assertFalse(conversation.is_archived)

	def test_rename_conversation(self):
		"""Test: renombrar una conversación del usuario."""
		conversation = Conversation.objects.create(user=self.user, title='Titulo viejo')
		response = self.client.post(
			reverse('chatia:conversation_rename', args=[conversation.id]),
			{'title': 'Nuevo titulo'}
		)
		self.assertEqual(response.status_code, 302)
		conversation.refresh_from_db()
		self.assertEqual(conversation.title, 'Nuevo titulo')

	def test_archive_conversation(self):
		"""Test: archivar y restaurar una conversación."""
		conversation = Conversation.objects.create(user=self.user, title='Para archivar')
		response = self.client.post(reverse('chatia:conversation_toggle_archive', args=[conversation.id]))
		self.assertEqual(response.status_code, 302)
		conversation.refresh_from_db()
		self.assertTrue(conversation.is_archived)

		response = self.client.post(reverse('chatia:conversation_toggle_archive', args=[conversation.id]))
		self.assertEqual(response.status_code, 302)
		conversation.refresh_from_db()
		self.assertFalse(conversation.is_archived)

	def test_delete_conversation(self):
		"""Test: borrar una conversación del usuario."""
		conversation = Conversation.objects.create(user=self.user, title='Para borrar')
		conversation_id = conversation.id
		response = self.client.post(reverse('chatia:conversation_delete', args=[conversation_id]))
		self.assertEqual(response.status_code, 302)
		self.assertFalse(Conversation.objects.filter(id=conversation_id).exists())

	def test_user_cannot_see_other_conversations(self):
		"""Test: usuario no puede ver conversaciones de otros usuarios."""
		conversation = Conversation.objects.create(
			user=self.other_user,
			title='Other User Conversation'
		)
		response = self.client.get(
			reverse('chatia:conversation_detail', args=[conversation.id])
		)
		self.assertEqual(response.status_code, 404)


class MessageTests(TestCase):
	"""Tests de envío y gestión de mensajes."""

	def setUp(self):
		"""Configurar cliente, usuario y conversación de prueba."""
		self.client = Client()
		self.user = User.objects.create_user(
			username='testuser',
			email='test@example.com',
			password='testpass123'
		)
		self.client.login(username='testuser', password='testpass123')
		self.conversation = Conversation.objects.create(user=self.user)

	@patch('chatia.views.ask_llm')
	def test_send_message(self, mock_ask_llm):
		"""Test: enviar un mensaje y recibir respuesta del LLM."""
		mock_ask_llm.return_value = 'Respuesta mockeada del modelo'
		
		response = self.client.post(
			reverse('chatia:send_message', args=[self.conversation.id]),
			{'prompt': 'Hola, ¿cómo estás?'}
		)
		
		self.assertEqual(response.status_code, 302)
		
		# Verificar que se crearon ambos mensajes
		user_messages = Message.objects.filter(
			conversation=self.conversation,
			role=Message.ROLE_USER
		)
		assistant_messages = Message.objects.filter(
			conversation=self.conversation,
			role=Message.ROLE_ASSISTANT
		)
		self.assertEqual(user_messages.count(), 1)
		self.assertEqual(assistant_messages.count(), 1)

	def test_send_message_invalid_prompt(self):
		"""Test: enviar un mensaje vacío no debería funcionar."""
		response = self.client.post(
			reverse('chatia:send_message', args=[self.conversation.id]),
			{'prompt': ''}
		)
		
		self.assertEqual(response.status_code, 400)
		self.assertEqual(Message.objects.filter(
			conversation=self.conversation
		).count(), 0)

	@patch('chatia.views.ask_llm_stream')
	def test_send_message_stream_returns_sse_events(self, mock_ask_llm_stream):
		"""Test: el endpoint de streaming devuelve eventos SSE con token y done."""
		mock_ask_llm_stream.return_value = iter(['Hola ', 'mundo'])
		response = self.client.post(
			reverse('chatia:send_message_stream', args=[self.conversation.id]),
			{'prompt': 'Hazme un saludo'}
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'text/event-stream')
		body = b''.join(response.streaming_content).decode('utf-8')
		self.assertIn('event: token', body)
		self.assertIn('Hola ', body)
		self.assertIn('event: done', body)
		self.assertEqual(Message.objects.filter(conversation=self.conversation, role=Message.ROLE_USER).count(), 1)
		self.assertEqual(Message.objects.filter(conversation=self.conversation, role=Message.ROLE_ASSISTANT).count(), 1)

	def test_send_message_stream_invalid_prompt_returns_error(self):
		"""Test: enviar prompt vacío al endpoint de streaming devuelve evento de error y 400."""
		response = self.client.post(
			reverse('chatia:send_message_stream', args=[self.conversation.id]),
			{'prompt': ''}
		)
		self.assertEqual(response.status_code, 400)
		# contenido SSE con evento error
		body = b''.join(response.streaming_content).decode('utf-8')
		self.assertIn('event: error', body)
		self.assertIn('mensaje', body.lower() or '')

	def test_send_message_stream_on_archived_conversation_returns_error(self):
		"""Test: no se puede enviar streaming si la conversación está archivada."""
		self.conversation.is_archived = True
		self.conversation.save()
		response = self.client.post(
			reverse('chatia:send_message_stream', args=[self.conversation.id]),
			{'prompt': 'Hola'}
		)
		self.assertEqual(response.status_code, 400)
		body = b''.join(response.streaming_content).decode('utf-8')
		self.assertIn('event: error', body)
		self.assertIn('archiv', body.lower())

	def test_send_message_stream_forbidden_for_other_user(self):
		"""Test: otro usuario no puede acceder al endpoint de streaming (404)."""
		other = User.objects.create_user(username='other', password='otherpass')
		conv = Conversation.objects.create(user=other)
		response = self.client.post(
			reverse('chatia:send_message_stream', args=[conv.id]),
			{'prompt': 'Hola'}
		)
		self.assertEqual(response.status_code, 404)

	def test_message_feedback_ajax_saves_vote(self):
		"""Test: el feedback por AJAX guarda la valoración del usuario."""
		assistant_message = Message.objects.create(
			conversation=self.conversation,
			role=Message.ROLE_ASSISTANT,
			content='Respuesta del asistente'
		)
		response = self.client.post(
			reverse('chatia:message_feedback', args=[assistant_message.id]),
			{'value': 'up'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

		self.assertEqual(response.status_code, 200)
		payload = json.loads(response.content)
		self.assertTrue(payload['ok'])
		self.assertEqual(payload['value'], 'up')
		self.assertEqual(payload['label'], 'Útil')
		self.assertEqual(assistant_message.feedbacks.filter(user=self.user, value='up').count(), 1)

	def test_conversation_set_model_ajax_updates_database(self):
		"""Test: el selector de modelo por conversación se guarda en BD."""
		selected_model = settings.LLM_MODEL_CATALOG[0]['value']
		response = self.client.post(
			reverse('chatia:conversation_set_model', args=[self.conversation.id]),
			{'llm_model': selected_model},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

		self.assertEqual(response.status_code, 200)
		payload = json.loads(response.content)
		self.assertTrue(payload['ok'])
		self.assertEqual(payload['llm_model'], selected_model)
		self.conversation.refresh_from_db()
		self.assertEqual(self.conversation.llm_model, selected_model)


class APITests(TestCase):
	"""Tests de los endpoints JSON de la API."""

	def setUp(self):
		"""Configurar cliente, usuario y conversaciones de prueba."""
		self.client = Client()
		self.user = User.objects.create_user(
			username='testuser',
			email='test@example.com',
			password='testpass123'
		)
		self.client.login(username='testuser', password='testpass123')
		
		# Crear conversaciones
		self.conv1 = Conversation.objects.create(user=self.user, title='Conv 1')
		Message.objects.create(
			conversation=self.conv1,
			role=Message.ROLE_USER,
			content='Mensaje 1'
		)
		Message.objects.create(
			conversation=self.conv1,
			role=Message.ROLE_ASSISTANT,
			content='Respuesta 1'
		)

	def test_api_conversations_returns_json(self):
		"""Test: GET /api/conversations/ devuelve JSON con conversaciones del usuario."""
		response = self.client.get(reverse('chatia:api_conversations'))
		
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'application/json')
		
		data = json.loads(response.content)
		self.assertIsInstance(data, list)
		self.assertEqual(len(data), 1)
		self.assertIn('id', data[0])
		self.assertIn('title', data[0])

	def test_api_statistics_returns_json(self):
		"""Test: GET /api/statistics/ devuelve JSON con estadísticas."""
		response = self.client.get(reverse('chatia:api_statistics'))
		
		self.assertEqual(response.status_code, 200)
		data = json.loads(response.content)
		
		self.assertIn('total_conversations', data)
		self.assertIn('total_messages', data)
		self.assertIn('user_conversations', data)
		self.assertIn('user_messages', data)

	def test_api_conversations_requires_login(self):
		"""Test: API requiere autenticación."""
		self.client.logout()
		response = self.client.get(reverse('chatia:api_conversations'))
		self.assertEqual(response.status_code, 302)
		self.assertIn('/accounts/login/', response.url)


class ConfigurationTests(TestCase):
	"""Tests de configuración y preferencias del usuario."""

	def setUp(self):
		"""Configurar cliente y usuario de prueba."""
		self.client = Client()
		self.user = User.objects.create_user(
			username='testuser',
			email='test@example.com',
			password='testpass123'
		)
		self.client.login(username='testuser', password='testpass123')

	def test_configuration_page_loads(self):
		"""Test: página de configuración se carga y crea UserPreference."""
		response = self.client.get(reverse('chatia:configuration'))
		
		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'chatia/configuration.html')
		# UserPreference se crea automáticamente
		self.assertTrue(UserPreference.objects.filter(user=self.user).exists())


class AuthTests(TestCase):
	def setUp(self):
		"""Crear un usuario base para probar login y registro."""
		self.client = Client()
		self.user = User.objects.create_user(
			username='testuser',
			email='test@example.com',
			password='testpass123'
		)

	def test_failed_login_returns_401(self):
		"""Si las credenciales son inválidas, el login debe devolver 401."""
		login_url = reverse('login')
		resp = self.client.post(login_url, {'username': 'nope', 'password': 'wrong'})
		self.assertEqual(resp.status_code, 401)

	def test_register_page_loads(self):
		"""La página pública de registro debe ser accesible sin autenticación."""
		response = self.client.get(reverse('register'))
		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'registration/register.html')
		self.assertNotContains(response, 'too similar to your other personal information')
		self.assertNotContains(response, 'must contain at least 8 characters')

	def test_register_creates_user_and_logs_in(self):
		"""Registrar una cuenta crea el usuario y deja la sesión iniciada."""
		response = self.client.post(
			reverse('register'),
			{
				'username': 'newuser',
				'password1': 'StrongPass123!',
				'password2': 'StrongPass123!',
			},
		)
		self.assertEqual(response.status_code, 302)
		self.assertTrue(User.objects.filter(username='newuser').exists())
		self.assertEqual(response.url, reverse('chatia:home'))

	def test_register_redirects_authenticated_user(self):
		"""Si el usuario ya ha iniciado sesión, el registro no tiene sentido y vuelve a home."""
		self.client.login(username='testuser', password='testpass123')
		response = self.client.get(reverse('register'))
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('chatia:home'))


class ApiConversationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='alice', password='pass')
		self.client.login(username='alice', password='pass')
		self.conv = Conversation.objects.create(user=self.user, title='Test conv')
		Message.objects.create(conversation=self.conv, role=Message.ROLE_USER, content='Hola')
		Message.objects.create(conversation=self.conv, role=Message.ROLE_ASSISTANT, content='Hola, soy ChatIA')

	def test_api_conversation_detail_requires_auth_and_returns_structure(self):
		url = reverse('chatia:api_conversation_detail', args=[self.conv.id])
		resp = self.client.get(url)
		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertEqual(data['id'], self.conv.id)
		self.assertIn('messages', data)
		self.assertEqual(len(data['messages']), 2)


class TemplateRenderingTests(TestCase):
	"""Tests de renderización de templates."""

	def setUp(self):
		"""Configurar cliente y usuario de prueba."""
		self.client = Client()
		self.user = User.objects.create_user(
			username='testuser',
			email='test@example.com',
			password='testpass123'
		)
		self.client.login(username='testuser', password='testpass123')

	def test_home_template_renders_correctly(self):
		"""Test: template home se renderiza correctamente."""
		response = self.client.get(reverse('chatia:home'))
		
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'ChatIA')

	def test_unknown_url_uses_custom_404_page(self):
		"""Una ruta inventada debe mostrar la 404 personalizada en lugar de la página técnica de Django."""
		response = self.client.get('/ruta-que-no-existe/')
		self.assertEqual(response.status_code, 404)
		self.assertTemplateUsed(response, '404.html')
		self.assertContains(response, 'No hemos encontrado esa página', status_code=404)

	def test_info_page_loads(self):
		"""Test: página de información/ayuda se carga correctamente."""
		response = self.client.get(reverse('chatia:info'))
		
		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'chatia/info.html')

	def test_markdown_is_rendered_in_message_bubble(self):
		"""Test: el contenido de los mensajes se renderiza como Markdown."""
		conversation = Conversation.objects.create(user=self.user, title='Markdown Test')
		message = Message.objects.create(
			conversation=conversation,
			role=Message.ROLE_ASSISTANT,
			content='Hola **mundo**',
		)
		response = self.client.get(reverse('chatia:conversation_detail', args=[conversation.id]))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '<strong>mundo</strong>', html=False)
		self.assertNotContains(response, f'{message.id} - {message.role}', html=False)

	def test_conversation_export_markdown_downloads_file(self):
		"""Test: la exportación devuelve un fichero Markdown descargable."""
		conversation = Conversation.objects.create(user=self.user, title='Exportable')
		Message.objects.create(
			conversation=conversation,
			role=Message.ROLE_USER,
			content='Primera linea\n\n**negrita**',
		)
		response = self.client.get(reverse('chatia:conversation_export_markdown', args=[conversation.id]))
		self.assertEqual(response.status_code, 200)
		self.assertIn('text/markdown', response['Content-Type'])
		self.assertIn('.md', response['Content-Disposition'])
		self.assertContains(response, '# Conversación: Exportable', html=False)
		self.assertContains(response, '**negrita**', html=False)

	def test_footer_appears_in_all_pages(self):
		"""Test: el footer aparece en todas las páginas."""
		pages = [
			reverse('chatia:home'),
			reverse('chatia:chats'),
			reverse('chatia:profile'),
			reverse('chatia:configuration'),
			reverse('chatia:info'),
		]
		
		for page in pages:
			response = self.client.get(page)
			self.assertEqual(response.status_code, 200)
			# El footer debe contener el ID site-footer
			self.assertContains(response, 'site-footer')


class ModelUnitTests(TestCase):
	"""Tests unitarios de modelos (opcionales)."""

	def setUp(self):
		self.user = User.objects.create_user(
			username='unituser',
			email='unit@example.com',
			password='unitpass123'
		)

	def test_conversation_default_title(self):
		"""Conversation usa el título por defecto esperado."""
		conversation = Conversation.objects.create(user=self.user)
		self.assertEqual(conversation.title, 'Nueva conversacion')

	def test_message_role_choices_contains_required_roles(self):
		"""Message expone roles user y assistant para el flujo del chat."""
		roles = [choice[0] for choice in Message.ROLE_CHOICES]
		self.assertIn(Message.ROLE_USER, roles)
		self.assertIn(Message.ROLE_ASSISTANT, roles)

	def test_user_preference_defaults(self):
		"""UserPreference crea valores por defecto válidos."""
		pref = UserPreference.objects.create(user=self.user)
		self.assertEqual(pref.llm_model, 'meta/llama-3.1-8b-instruct')
		self.assertEqual(pref.llm_max_tokens, 1024)
		self.assertEqual(pref.llm_temperature, 0.7)


class FormUnitTests(TestCase):
	"""Tests unitarios de formularios (opcionales)."""

	def test_prompt_form_valid(self):
		"""PromptForm acepta un prompt válido."""
		form = PromptForm(data={'prompt': 'Hola mundo'})
		self.assertTrue(form.is_valid())

	def test_prompt_form_rejects_too_long_prompt(self):
		"""PromptForm rechaza prompts que exceden max_length."""
		form = PromptForm(data={'prompt': 'a' * 1501})
		self.assertFalse(form.is_valid())
		self.assertIn('prompt', form.errors)


class ServiceUnitTests(TestCase):
	"""Tests unitarios de servicios (opcionales)."""

	def setUp(self):
		self.user = User.objects.create_user(
			username='serviceuser',
			email='service@example.com',
			password='servicepass123'
		)
		self.conversation = Conversation.objects.create(user=self.user)

	def test_build_messages_payload_adds_system_message(self):
		"""El payload siempre incluye el mensaje system en primera posición."""
		payload = build_messages_payload(self.conversation)
		self.assertGreaterEqual(len(payload), 1)
		self.assertEqual(payload[0]['role'], 'system')

	def test_build_messages_payload_uses_last_12_messages(self):
		"""El payload limita el historial a los últimos 12 mensajes en orden correcto."""
		for i in range(1, 15):
			Message.objects.create(
				conversation=self.conversation,
				role=Message.ROLE_USER,
				content=f'msg {i}'
			)

		payload = build_messages_payload(self.conversation)

		# 1 system + 12 mensajes recientes
		self.assertEqual(len(payload), 13)
		self.assertEqual(payload[1]['content'], 'msg 3')
		self.assertEqual(payload[-1]['content'], 'msg 14')


class LLMServiceTests(TestCase):
	"""Unit tests for `ask_llm` and `ask_llm_stream` behaviours using mocks."""

	def setUp(self):
		self.user = User.objects.create_user(username='svcuser', password='pass')
		self.conv = Conversation.objects.create(user=self.user)

	def test_ask_llm_returns_config_message_if_no_api_key(self):
		from django.conf import settings
		orig = settings.LLM_API_KEY
		settings.LLM_API_KEY = ''
		try:
			from chatia.services import ask_llm
			resp = ask_llm(self.conv)
			self.assertIn('Configura LLM_API_KEY', resp)
		finally:
			settings.LLM_API_KEY = orig

	def test_ask_llm_stream_raises_if_no_api_key(self):
		from django.conf import settings
		orig = settings.LLM_API_KEY
		settings.LLM_API_KEY = ''
		try:
			from chatia.services import ask_llm_stream
			with self.assertRaises(RuntimeError):
				list(ask_llm_stream(self.conv))
		finally:
			settings.LLM_API_KEY = orig

	def test_ask_llm_stream_yields_tokens_from_client(self):
		# Mock OpenAI client to yield chunk objects with choices[0].delta.content
		class Delta: 
			def __init__(self, content):
				self.content = content

		class Choice:
			def __init__(self, delta):
				self.delta = delta

		class Chunk:
			def __init__(self, token):
				self.choices = [Choice(Delta(token))]

		def fake_stream(*args, **kwargs):
			for t in ['Hola ', 'mundo', '!']:
				yield Chunk(t)

		from unittest.mock import patch
		from django.conf import settings
		settings.LLM_API_KEY = settings.LLM_API_KEY or 'FAKE'

		with patch('chatia.services.OpenAI') as MockOpenAI:
			mock_client = MockOpenAI.return_value
			mock_client.chat.completions.create.return_value = fake_stream()
			from chatia.services import ask_llm_stream
			tokens = list(ask_llm_stream(self.conv))
			self.assertEqual(''.join(tokens), 'Hola mundo!')


class ExtraEndpointTests(TestCase):
	"""Additional endpoint tests for edge cases."""

	def setUp(self):
		self.client = Client()
		self.user = User.objects.create_user(username='edge', password='pass')
		self.client.login(username='edge', password='pass')
		self.conv = Conversation.objects.create(user=self.user)

	def test_conversation_set_model_rejects_invalid_model(self):
		response = self.client.post(
			reverse('chatia:conversation_set_model', args=[self.conv.id]),
			{'llm_model': 'not-a-valid-model'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 400)

	def test_message_feedback_non_ajax_redirects(self):
		assistant_message = Message.objects.create(conversation=self.conv, role=Message.ROLE_ASSISTANT, content='txt')
		response = self.client.post(reverse('chatia:message_feedback', args=[assistant_message.id]), {'value': 'up'})
		self.assertEqual(response.status_code, 302)


class ServicesErrorHandlingTests(TestCase):
	"""Tests to cover error branches in `ask_llm` and `ask_llm_stream`."""

	def setUp(self):
		self.user = User.objects.create_user(username='erruser', password='pass')
		self.conv = Conversation.objects.create(user=self.user)

	def test_ask_llm_authentication_error(self):
		from unittest.mock import patch
		from chatia import services as svc

		class FakeAuth(Exception):
			pass

		with patch('chatia.services.OpenAI') as MockOpenAI, patch('chatia.services.AuthenticationError', FakeAuth):
			mock_client = MockOpenAI.return_value
			mock_client.chat.completions.create.side_effect = FakeAuth('no auth')
			res = svc.ask_llm(self.conv)
			self.assertIn('Error de autenticación', res)

	def test_ask_llm_api_status_429(self):
		from unittest.mock import patch
		from chatia import services as svc

		class FakeStatus(Exception):
			def __init__(self, status_code):
				self.status_code = status_code

		with patch('chatia.services.OpenAI') as MockOpenAI, patch('chatia.services.APIStatusError', FakeStatus):
			mock_client = MockOpenAI.return_value
			mock_client.chat.completions.create.side_effect = FakeStatus(429)
			res = svc.ask_llm(self.conv)
			self.assertIn('El servidor está sobrecargado', res)

	def test_ask_llm_api_status_500_returns_error_message(self):
		from unittest.mock import patch
		from chatia import services as svc

		class FakeStatus(Exception):
			def __init__(self, status_code):
				self.status_code = status_code

		with patch('chatia.services.OpenAI') as MockOpenAI, patch('chatia.services.APIStatusError', FakeStatus):
			mock_client = MockOpenAI.return_value
			mock_client.chat.completions.create.side_effect = FakeStatus(500)
			res = svc.ask_llm(self.conv)
			self.assertIn('Error del servidor de IA (HTTP 500)', res)

	def test_ask_llm_stream_interrupted_after_tokens_raises_runtime(self):
		from unittest.mock import patch
		from chatia import services as svc

		class Delta:
			def __init__(self, content):
				self.content = content

		class Choice:
			def __init__(self, delta):
				self.delta = delta

		class Chunk:
			def __init__(self, token):
				self.choices = [Choice(Delta(token))]

		def broken_stream():
			yield Chunk('token1')
			raise Exception('conn lost')

		with patch('chatia.services.OpenAI') as MockOpenAI, patch('chatia.services.APIConnectionError', Exception):
			mock_client = MockOpenAI.return_value
			mock_client.chat.completions.create.return_value = broken_stream()
			with self.assertRaises(RuntimeError):
				list(svc.ask_llm_stream(self.conv))
