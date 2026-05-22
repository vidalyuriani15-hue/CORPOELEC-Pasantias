from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def no_cache(view_func):
    """Decorator que desactiva el caché HTTP para la respuesta de una vista."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, proxy-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    return _wrapped


def requiere_permiso(permiso_requerido):
    """Decorator que verifica si el usuario tiene un permiso específico."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            try:
                permisos = request.user.usuario.permisos or {}
            except Exception:
                permisos = {}
            if permisos.get(permiso_requerido, False):
                return view_func(request, *args, **kwargs)
            messages.error(request, f'No tiene permiso para realizar esta acción.')
            return redirect('index')
        return _wrapped
    return decorator


def puede_crear(request):
    """Verifica si el usuario puede crear"""
    if request.user.is_superuser:
        return True
    try:
        return request.user.usuario.permisos.get('crear', False)
    except Exception:
        return False


def puede_actualizar(request):
    """Verifica si el usuario puede actualizar"""
    if request.user.is_superuser:
        return True
    try:
        return request.user.usuario.permisos.get('actualizar', False)
    except Exception:
        return False


def puede_eliminar(request):
    """Verifica si el usuario puede eliminar"""
    if request.user.is_superuser:
        return True
    try:
        return request.user.usuario.permisos.get('eliminar', False)
    except Exception:
        return False