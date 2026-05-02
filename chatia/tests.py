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

	def test_home_requires_login(self):
		"""Test: acceso a home sin autenticación redirige a login."""
		response = self.client.get(reverse('chatia:home'))
		self.assertEqual(response.status_code, 302)
		self.assertIn('/accounts/login/', response.url)

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

	def test_info_page_loads(self):
		"""Test: página de información/ayuda se carga correctamente."""
		response = self.client.get(reverse('chatia:info'))
		
		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'chatia/info.html')

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
