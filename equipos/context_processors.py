from django.conf import settings


def permisos_usuario(request):
    """Context processor para exponer permisos del usuario en todas las plantillas"""
    if not request.user.is_authenticated:
        return {
            'permisos_usuario': {'crear': False, 'actualizar': False, 'eliminar': False},
            'puede_crear': False,
            'puede_actualizar': False,
            'puede_eliminar': False,
        }
    
    if request.user.is_superuser:
        return {
            'permisos_usuario': {'crear': True, 'actualizar': True, 'eliminar': True},
            'puede_crear': True,
            'puede_actualizar': True,
            'puede_eliminar': True,
        }
    
    try:
        permisos = request.user.usuario.permisos or {}
    except Exception:
        permisos = {}
    
    return {
        'permisos_usuario': permisos,
        'puede_crear': permisos.get('crear', False),
        'puede_actualizar': permisos.get('actualizar', False),
        'puede_eliminar': permisos.get('eliminar', False),
    }