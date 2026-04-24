from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
	title = models.CharField(max_length=120, default='Nueva conversacion')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-updated_at']

	def __str__(self):
		return f"{self.user.username} - {self.title}"


class Message(models.Model):
	ROLE_USER = 'user'
	ROLE_ASSISTANT = 'assistant'
	ROLE_SYSTEM = 'system'
	ROLE_CHOICES = [
		(ROLE_USER, 'Usuario'),
		(ROLE_ASSISTANT, 'Asistente'),
		(ROLE_SYSTEM, 'Sistema'),
	]

	conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
	role = models.CharField(max_length=12, choices=ROLE_CHOICES)
	content = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']

	def __str__(self):
		return f"{self.conversation_id} - {self.role}"
