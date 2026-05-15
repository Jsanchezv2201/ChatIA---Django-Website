import html

try:
	import bleach
except Exception:
	bleach = None

from django.utils.timezone import localtime, now

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover - fallback defensivo si falta la dependencia
    markdown_lib = None


def render_markdown_html(text):
	"""Renderiza texto Markdown a HTML seguro para mostrarse en pantalla."""
	raw_text = text or ''
	# Decodificar entidades HTML si las hubiera (p. ej. &quot;, &lt;, &gt;)
	unescaped = html.unescape(raw_text)

	if markdown_lib is None:
		# Fallback: escapar y convertir saltos de linea simples en <br>
		escaped = html.escape(unescaped)
		paragraphs = [part.replace('\n', '<br>') for part in escaped.split('\n\n') if part.strip()]
		if not paragraphs:
			return '<p></p>'
		return ''.join(f'<p>{paragraph}</p>' for paragraph in paragraphs)

	# Convertir Markdown -> HTML usando la libreria
	html_out = markdown_lib.markdown(
		unescaped,
		extensions=['fenced_code', 'tables', 'sane_lists'],
		output_format='html5',
	)

	# Si bleach está disponible, sanitizar el HTML resultante
	if bleach is not None:
		allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS) | {
			'p', 'pre', 'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
			'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'blockquote'
		}
		allowed_attrs = {
			'a': ['href', 'title', 'rel', 'target']
		}
		html_out = bleach.clean(html_out, tags=allowed_tags, attributes=allowed_attrs, strip=True)

	return html_out


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