from django import template

register = template.Library()

@register.filter
def get_permisos(user):
    try:
        return user.usuario.permisos
    except:
        return {'crear': False, 'actualizar': False, 'eliminar': False}