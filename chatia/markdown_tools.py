import html

from django.utils.timezone import localtime, now

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover - fallback defensivo si falta la dependencia
    markdown_lib = None


def render_markdown_html(text):
	"""Renderiza texto Markdown a HTML seguro para mostrarse en pantalla."""
	raw_text = text or ''
	escaped_text = html.escape(raw_text)
	if markdown_lib is None:
		paragraphs = [part.replace('\n', '<br>') for part in escaped_text.split('\n\n') if part.strip()]
		if not paragraphs:
			return '<p></p>'
		return ''.join(f'<p>{paragraph}</p>' for paragraph in paragraphs)
	return markdown_lib.markdown(
		escaped_text,
		extensions=['fenced_code', 'tables', 'sane_lists'],
		output_format='html5',
	)


def conversation_to_markdown(conversation):
	"""Convierte una conversación completa en un documento Markdown descargable."""
	created_at = localtime(conversation.created_at).strftime('%d/%m/%Y %H:%M')
	updated_at = localtime(conversation.updated_at).strftime('%d/%m/%Y %H:%M')
	lines = [
		f'# Conversación: {conversation.title}',
		'',
		f'- Usuario: {conversation.user.username}',
		f'- Estado: {"Archivada" if conversation.is_archived else "Activa"}',
		f'- Creada: {created_at}',
		f'- Actualizada: {updated_at}',
		f'- Exportada: {localtime(now()).strftime("%d/%m/%Y %H:%M")}',
		'',
		'## Mensajes',
		'',
	]

	for message in conversation.messages.order_by('created_at'):
		if message.role == 'user':
			role_label = 'Tu'
		elif message.role == 'assistant':
			role_label = 'ChatIA'
		else:
			role_label = 'Sistema'
		timestamp = localtime(message.created_at).strftime('%d/%m/%Y %H:%M')
		message_body = message.content.strip() or '_Sin contenido_'
		lines.extend([
			f'### {role_label} · {timestamp}',
			'',
			message_body,
			'',
		])

	return '\n'.join(lines).rstrip() + '\n'