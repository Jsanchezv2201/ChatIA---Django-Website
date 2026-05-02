# Módulos necesarios para comunicarse con NVIDIA Build API y manejar errores
import time  # Para pausas entre reintentos

from django.conf import settings
from openai import APIConnectionError  # Error de conexión a la API
from openai import APIStatusError  # Errores HTTP generales (4xx, 5xx)
from openai import APITimeoutError  # Timeout en la respuesta
from openai import AuthenticationError  # API key inválida o expirada
from openai import OpenAI  # Cliente de OpenAI (compatible con NVIDIA Build)
from openai import RateLimitError  # Límite de rate limit excedido


def build_messages_payload(conversation):
	"""
	Construye el historial de mensajes para enviar a la API del LLM.
	
	Estructura del payload:                                 
	- Primer mensaje: instrucción del sistema (rol 'system')
	- Resto: últimos 12 mensajes de la conversación en orden cronológico
	
	Args:
		conversation: Objeto Conversation con el historial de mensajes
		
	Returns:
		Lista de dicts con formato OpenAI: [{'role': 'system'/'user'/'assistant', 'content': '...'}, ...]
	"""
	payload = [
		{
			'role': 'system',
			'content': 'Eres ChatIA, un asistente util para estudiantes universitarios.',
		}
	]
	# Obtener últimos 12 mensajes, ordenados del más antiguo al más reciente
	recent_messages = list(conversation.messages.order_by('-created_at')[:12])[::-1]
	for message in recent_messages:
		payload.append({'role': message.role, 'content': message.content})
	return payload


def ask_llm(conversation):
	"""
	Envía la conversación a NVIDIA Build API y obtiene una respuesta completa.
	
	Este es el flujo sincrónico (sin streaming):
	1. Verifica que exista LLM_API_KEY
	2. Crea cliente OpenAI apuntando a https://integrate.api.nvidia.com/v1
	3. Reintenta hasta 2 veces en caso de errores transitorios
	4. Devuelve la respuesta completa como string
	
	Args:
		conversation: Objeto Conversation con el historial
		
	Returns:
		String con la respuesta del modelo, o mensaje de error si no se puede conectar
	"""
	# Obtener API key desde variables de entorno (.env)
	api_key = settings.LLM_API_KEY
	if not api_key:
		return 'Configura LLM_API_KEY en el entorno para activar respuestas reales del modelo.'

	max_attempts = 2  # Reintentar una vez en caso de error
	timeout = 20  # Esperar máximo 20 segundos por respuesta

	# Crear cliente OpenAI apuntando a NVIDIA Build
	# (OpenAI es compatible con cualquier endpoint compatible con la API OpenAI)
	client = OpenAI(
		base_url=settings.LLM_BASE_URL,  # https://integrate.api.nvidia.com/v1
		api_key=api_key,
		timeout=timeout,
	)

	for attempt in range(max_attempts):
		try:
			# Llamada a la API (como en el ejemplo del profesor)
			completion = client.chat.completions.create(
				model=settings.LLM_MODEL,  # ej: meta/llama-3.1-8b-instruct
				messages=build_messages_payload(conversation),  # Historial de la conversación
				temperature=0.5,  # Equilibrio entre creatividad (alto) y consistencia (bajo)
				top_p=0.7,  # Nucleus sampling: considerar tokens con prob acumulada hasta 70%
				max_tokens=settings.LLM_MAX_TOKENS,  # Máximo de tokens en la respuesta
			)
			# Extraer el texto de la respuesta
			content = completion.choices[0].message.content
			return (content or '').strip() or 'El modelo no devolvio contenido.'

		except APITimeoutError:
			# Si el timeout, reintentar (excepto en el último intento)
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt  # Espera exponencial: 1s, 2s, ...
				time.sleep(wait_time)
				continue
			return 'El modelo de IA tardó demasiado en responder. Intenta de nuevo en un momento.'

		except APIConnectionError:
			# Errores de red: reintentar
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			return 'No se pudo conectar con el servidor de IA (error de red). Intenta de nuevo.'

		except AuthenticationError:
			# API key inválida: no reintentar (nunca funcionará)
			return 'Error de autenticación: verifica tu LLM_API_KEY.'

		except RateLimitError:
			# Límite de requests excedido: reintentar después
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			return 'El servidor está sobrecargado. Intenta de nuevo en unos segundos.'

		except APIStatusError as exc:
			# Errores HTTP generales
			if exc.status_code == 429:  # Too Many Requests (rate limit)
				return 'El servidor está sobrecargado. Intenta de nuevo en unos segundos.'
			if exc.status_code >= 500 and attempt < max_attempts - 1:  # Errores del servidor (5xx)
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			return f'Error del servidor de IA (HTTP {exc.status_code}). Intenta de nuevo.'

		except Exception as exc:
			# Error inesperado
			return f'Error inesperado contactando IA: {str(exc)[:100]}'

	return 'No se pudo contactar con el servidor después de varios intentos.'


def ask_llm_stream(conversation):
	"""
	Envía la conversación a NVIDIA Build API y obtiene la respuesta en streaming.
	
	Este es el flujo con streaming (como en el ejemplo del profesor):
	1. Verifica que exista LLM_API_KEY
	2. Crea cliente OpenAI con stream=True
	3. Itera sobre los chunks recibidos (tokens individuales)
	4. Usa 'yield' para devolver cada token conforme llega (sin esperar la respuesta completa)
	5. El navegador recibe los tokens vía SSE (Server-Sent Events) y los muestra en tiempo real
	
	Args:
		conversation: Objeto Conversation con el historial
		
	Yields:
		String con cada token (palabra/parte) de la respuesta conforme llega
		
	Raises:
		RuntimeError: Si ocurre un error irrecuperable
	"""
	# Obtener API key desde variables de entorno
	api_key = settings.LLM_API_KEY
	if not api_key:
		raise RuntimeError('Configura LLM_API_KEY en el entorno para activar respuestas reales del modelo.')

	max_attempts = 2
	timeout = 20

	# Crear cliente OpenAI
	client = OpenAI(
		base_url=settings.LLM_BASE_URL,  # NVIDIA Build
		api_key=api_key,
		timeout=timeout,
	)

	for attempt in range(max_attempts):
		emitted_any_token = False  # Rastreamos si hemos enviado al menos un token
		try:
			# Llamada con stream=True (como en el ejemplo del profesor)
			stream = client.chat.completions.create(
				model=settings.LLM_MODEL,
				messages=build_messages_payload(conversation),
				temperature=0.5,
				top_p=0.7,
				max_tokens=settings.LLM_MAX_TOKENS,
				stream=True,  # ← Importante: activa el streaming
			)

			# Iterar sobre cada chunk que llega del servidor (como el profesor hace)
			for chunk in stream:
				if not chunk.choices:
					continue
				delta = chunk.choices[0].delta  # Parte del mensaje en este chunk
				# Extraer el token (puede ser None si es el último chunk)
				token = getattr(delta, 'content', None)
				if token:
					emitted_any_token = True
					yield token  # Enviar el token al cliente (navegador) vía SSE
			return  # Streaming completado exitosamente

		except (APITimeoutError, APIConnectionError, RateLimitError, APIStatusError) as exc:
			# Si ya enviamos tokens y luego falla, no reintentar (respuesta parcial)
			if emitted_any_token:
				raise RuntimeError('La respuesta en streaming se interrumpio.') from exc
			# Si no hemos enviado nada aún, reintentar
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			raise RuntimeError('Request timed out.') from exc

		except AuthenticationError as exc:
			# API key inválida: no reintentar
			raise RuntimeError('Error de autenticacion: verifica tu LLM_API_KEY.') from exc