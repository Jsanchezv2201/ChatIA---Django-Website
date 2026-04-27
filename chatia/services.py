import time

from django.conf import settings
from openai import APIConnectionError
from openai import APIStatusError
from openai import APITimeoutError
from openai import AuthenticationError
from openai import OpenAI
from openai import RateLimitError


def build_messages_payload(conversation):
	payload = [
		{
			'role': 'system',
			'content': 'Eres ChatIA, un asistente util para estudiantes universitarios.',
		}
	]
	recent_messages = list(conversation.messages.order_by('-created_at')[:12])[::-1]
	for message in recent_messages:
		payload.append({'role': message.role, 'content': message.content})
	return payload


def ask_llm(conversation):
	api_key = settings.LLM_API_KEY
	if not api_key:
		return 'Configura LLM_API_KEY en el entorno para activar respuestas reales del modelo.'

	max_attempts = 2
	timeout = 20

	client = OpenAI(
		base_url=settings.LLM_BASE_URL,
		api_key=api_key,
		timeout=timeout,
	)

	for attempt in range(max_attempts):
		try:
			completion = client.chat.completions.create(
				model=settings.LLM_MODEL,
				messages=build_messages_payload(conversation),
				temperature=0.5,
				top_p=0.7,
				max_tokens=192,
			)
			content = completion.choices[0].message.content
			return (content or '').strip() or 'El modelo no devolvio contenido.'

		except APITimeoutError:
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			return 'El modelo de IA tardó demasiado en responder. Intenta de nuevo en un momento.'

		except APIConnectionError:
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			return 'No se pudo conectar con el servidor de IA (error de red). Intenta de nuevo.'

		except AuthenticationError:
			return 'Error de autenticación: verifica tu LLM_API_KEY.'

		except RateLimitError:
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			return 'El servidor está sobrecargado. Intenta de nuevo en unos segundos.'

		except APIStatusError as exc:
			if exc.status_code == 429:
				return 'El servidor está sobrecargado. Intenta de nuevo en unos segundos.'
			if exc.status_code >= 500 and attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			return f'Error del servidor de IA (HTTP {exc.status_code}). Intenta de nuevo.'

		except Exception as exc:
			return f'Error inesperado contactando IA: {str(exc)[:100]}'

	return 'No se pudo contactar con el servidor después de varios intentos.'


def ask_llm_stream(conversation):
	api_key = settings.LLM_API_KEY
	if not api_key:
		raise RuntimeError('Configura LLM_API_KEY en el entorno para activar respuestas reales del modelo.')

	max_attempts = 2
	timeout = 20

	client = OpenAI(
		base_url=settings.LLM_BASE_URL,
		api_key=api_key,
		timeout=timeout,
	)

	for attempt in range(max_attempts):
		emitted_any_token = False
		try:
			stream = client.chat.completions.create(
				model=settings.LLM_MODEL,
				messages=build_messages_payload(conversation),
				temperature=0.5,
				top_p=0.7,
				max_tokens=192,
				stream=True,
			)

			for chunk in stream:
				if not chunk.choices:
					continue
				delta = chunk.choices[0].delta
				token = getattr(delta, 'content', None)
				if token:
					emitted_any_token = True
					yield token
			return

		except (APITimeoutError, APIConnectionError, RateLimitError, APIStatusError) as exc:
			if emitted_any_token:
				raise RuntimeError('La respuesta en streaming se interrumpio.') from exc
			if attempt < max_attempts - 1:
				wait_time = 2 ** attempt
				time.sleep(wait_time)
				continue
			raise RuntimeError('Request timed out.') from exc

		except AuthenticationError as exc:
			raise RuntimeError('Error de autenticacion: verifica tu LLM_API_KEY.') from exc