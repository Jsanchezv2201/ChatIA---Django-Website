from django import template
from django.utils.safestring import mark_safe

from chatia.markdown_tools import render_markdown_html

register = template.Library()


@register.filter(name='render_markdown')
def render_markdown(value):
	return mark_safe(render_markdown_html(value))