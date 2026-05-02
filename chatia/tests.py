from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json
from unittest.mock import patch

from .models import Conversation, Message, UserPreference


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

	def test_footer_appears_in_pages(self):
		"""Test: el footer aparece en las páginas autenticadas."""
		pages = [
			reverse('chatia:home'),
			reverse('chatia:chats'),
			reverse('chatia:profile'),
		]
		
		for page in pages:
			response = self.client.get(page)
			self.assertEqual(response.status_code, 200)
			# El footer debe contener el ID site-footer
			self.assertContains(response, 'site-footer')
