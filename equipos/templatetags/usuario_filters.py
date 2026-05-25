from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Lookup en dict admitiendo clave int o str (las JSONField guardan str)."""
    if not isinstance(d, dict):
        return ''
    if key in d:
        return d[key]
    return d.get(str(key), '')


@register.filter
def get_permisos(user):
    try:
        return user.usuario.permisos
    except:
        return {'crear': False, 'actualizar': False, 'eliminar': False}