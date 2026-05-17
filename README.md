# ENTREGA CONVOCATORIA MAYO

# ENTREGA DE PRÁCTICA

## Datos

- Nombre: Juan Sánchez Vinuesa
- Titulación: Grado en Ingeniería Telemática
- Cuenta en laboratorios: juansv
- Cuenta URJC: j.sanchezv.2021@alumnos.urjc.es
- Video básico (url): https://youtu.be/NwHQRQ5agu4
- Video parte opcional (url): https://youtu.be/QM8VW4ZUVvg
- Despliegue (url): https://juansv22.pythonanywhere.com/
- Contraseñas (cuentas de prueba):
	- Usuario 1: user1 / usuario1
	- Usuario 2: user2 / usuario2
- Cuenta Admin Site: juan / admin

## Recursos implementados y métodos disponibles para cada recurso

- `/` (GET): Página pública de inicio (resumen y acceso al chat)
- `/chats/` (GET): Listado de conversaciones del usuario (login requerido)
- `/conversations/<id>/` (GET): Vista detallada de la conversación (chat UI)
- `/conversations/<id>/message/stream/` (POST): Envío de mensaje con streaming SSE (fetch streaming)
- `/conversations/<id>/set-model/` (POST): Selector para fijar el modelo LLM de la conversación
- `/messages/<id>/feedback/` (POST): Envío de valoración (like/dislike) 
- `/conversations/<id>/export/markdown/` (GET): Exportar la conversación a Markdown descargable
- `/preferences/` (GET/POST): Página para editar `UserPreference` (modelo, tokens, temperatura)

> Nota: todas las rutas excepto `/` requieren autenticación.

## Resumen parte obligatoria

Esta entrega incluye la aplicación Django `ChatIA` que implementa un chat con historial por conversación,
integración con un LLM mediante llamadas HTTP (con soporte para streaming de tokens), persistencia de mensajes
y conversaciones, y una interfaz usable (con HTMX y JavaScript). Se han añadido pruebas automatizadas que
verifican endpoints críticos y comportamientos. 

## Lista partes opcionales implementadas

- Inclusión de un favicon del sitio.
- Modo oscuro (toggle).
- Preferencias por usuario (`UserPreference`) con `llm_model`, `llm_max_tokens`, `llm_temperature`.
- Selector de modelo LLM por conversación y guardado en BD.
- Evaluación de respuestas (útil/no útil) y panel básico de métricas en Admin Site.
- Soporte multi-chat avanzado: Renombrado de conversaciones, archivado, borrado, y búsqueda por título/contenido.
- Streaming real de tokens en la interfaz con HTMX/SSE y render progresivo de la respuesta.
- Exportación de conversaciones a Markdown. 
- Mejora de cobertura de tests (errores, llamadas consecutivas, unit tests).







