# ENTREGA CONVOCATORIA MAYO

# ENTREGA DE PRÁCTICA

## Datos

- Nombre: Juan Sánchez Vinuesa
- Titulación: Grado en Ingeniería Telemática
- Cuenta en laboratorios: juansv
- Cuenta URJC: j.sanchezv.2021
- Video básico (url): https://youtu.be/REPLACE_BASIC_VIDEO
- Video parte opcional (url): https://youtu.be/REPLACE_OPTIONAL_VIDEO
- Despliegue (url): https://REPLACE_WITH_YOUR_DEPLOY_URL
- Contraseñas (cuentas de prueba):
	- Usuario estudiante: estudiante / estudiante123
	- Usuario profesor: profesor / profesor123
- Cuenta Admin Site: admin / admin

## Recursos implementados y métodos disponibles para cada recurso

- `/` (GET): Página pública de inicio (resumen y acceso al chat)
- `/chats/` (GET): Listado de conversaciones del usuario (login requerido)
- `/conversations/<id>/` (GET): Vista detallada de la conversación (chat UI)
- `/conversations/<id>/message/stream/` (POST): Envío de mensaje con streaming SSE (fetch streaming)
- `/conversations/<id>/set-model/` (POST): Selector AJAX para fijar el modelo LLM de la conversación
- `/messages/<id>/feedback/` (POST): Envío de valoración (like/dislike) via AJAX
- `/conversations/<id>/export/markdown/` (GET): Exportar la conversación a Markdown descargable
- `/preferences/` (GET/POST): Página para editar `UserPreference` (modelo, tokens, temperatura)

> Nota: todas las rutas excepto `/` requieren autenticación.

## Resumen parte obligatoria

Esta entrega incluye la aplicación Django `ChatIA` que implementa un chat con historial por conversación,
integración con un LLM mediante llamadas HTTP (con soporte para streaming de tokens), persistencia de mensajes
y conversaciones, y una interfaz usable (con HTMX y JavaScript). Se han añadido pruebas automatizadas que
verifican endpoints críticos y comportamientos (streaming, AJAX, autenticación). La portada (`/`) es pública
como exige el enunciado; el resto de páginas requiere login.

## Lista partes opcionales implementadas

- Modo oscuro (toggle).
- Selector de modelo por conversación (persistente) y catálogo limitado a 4 modelos.
- Preferencias por usuario (`UserPreference`) con `llm_model`, `llm_max_tokens`, `llm_temperature`.
- Valoración de mensajes (`MessageFeedback`) con envío AJAX y métricas accesibles en admin.
- Streaming con render progresivo de tokens y reemplazo final del mensaje completo.
- Exportar conversaciones a Markdown.
- HTMX partials para refresco de componentes y peticiones parciales.
- Tests adicionales para streaming y endpoints AJAX.
- Inclusión de un favicon del sitio.
- Soporte multi-chat avanzado: Renombrado de conversaciones, archivado, borrado, y búsqueda por título/contenido.
- Streaming real de tokens en la interfaz con HTMX/SSE y render progresivo de la respuesta.
- Selector de modelo LLM por conversación (solo modelos gratuitos) y guardado en BD.
- Contexto enriquecido (adjuntar fragmentos/documentos): NO IMPLEMENTADO (MEDIO)
- Evaluación de respuestas (like/dislike) y panel básico de métricas en Admin Site.
- Modo "comparar modelos" (enviar prompt a dos modelos y mostrar diferencias): NO IMPLEMENTADO (DIFÍCIL)
- Caché inteligente de respuestas con invalidación y trazabilidad: NO IMPLEMENTADO (DIFÍCIL)
- Exportación de conversaciones y compartir mediante enlace temporal: PARCIAL (Exportar a Markdown: IMPLEMENTADO; JSON/PDF/links temporales: NO IMPLEMENTADO) (DIFÍCIL)
- Internacionalización de la interfaz (i18n usando Django): NO IMPLEMENTADO (MEDIO)
- Mejora de cobertura de tests (errores, llamadas consecutivas, unit tests): PARCIAL (se añadieron  tests críticos y casos para streaming/AJAX; se recomienda ampliar cobertura) (MEDIO)
- Integración con fuente externa (embeddings/ranking/moderación): NO IMPLEMENTADO (DIFÍCIL)



Otros detalles implementados (completan la entrega):

- Endpoint AJAX `/conversations/<id>/set-model/` y control en la UI (`select`) para fijar el modelo por conversación.
- Pruebas: la suite local contiene 28 tests que pasan (incluye tests para streaming y AJAX).



