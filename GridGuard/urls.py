"""
URL configuration for CORPOELEC project.
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from equipos.views import reconectadores_view, reles_view, rele_detalle_view, tensiones_view, perfil_view, cambiar_clave_view, usuarios_view, subestaciones_view, index_view, interfaces_view, protocolo_view, remotas_view, api_remotas, exportar_tensiones_pdf, exportar_interfaces_pdf, exportar_protocolo_pdf, exportar_subestaciones_pdf, exportar_remotas_pdf, exportar_reles_pdf
from django.conf import settings
from django.conf.urls.static import static

@never_cache
def custom_login(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('/admin/inicio/')
        else:
            return redirect('/')
    
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('/admin/inicio/')
            else:
                return redirect('/')
        else:
            error = 'Usuario o contraseña incorrectos.'
    
    response = render(request, 'login.html', {'error': error})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@never_cache
def custom_logout(request):
    from django.contrib.auth import logout
    logout(request)
    response = redirect('/login/')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

urlpatterns = [
    path('cerrar-sesion/', custom_logout, name='user_logout'),
    path('admin/cerrar-sesion/', custom_logout, name='logout'),
    path('login/', custom_login, name='user_login'),
    path('perfil/', perfil_view, name='perfil'),
    path('admin/perfil/', perfil_view, name='admin_perfil'),
    path('cambiar-clave/', cambiar_clave_view, name='cambiar_clave'),
    path('admin/cambiar-clave/', cambiar_clave_view, name='admin_cambiar_clave'),
    path('admin/usuarios/', usuarios_view, name='admin_usuarios'),
    path('admin/inicio/', index_view, name='admin_index'),
    path('admin/', admin.site.urls),
    path('', index_view, name='index'),
    path('tensiones/', tensiones_view, name='tensiones'),
    path('tensiones/exportar-pdf/', exportar_tensiones_pdf, name='exportar_tensiones_pdf'),
    path('interfaces/', interfaces_view, name='interfaces'),
    path('interfaces/exportar-pdf/', exportar_interfaces_pdf, name='exportar_interfaces_pdf'),
    path('protocolo/', protocolo_view, name='protocolo'),
    path('protocolo/exportar-pdf/', exportar_protocolo_pdf, name='exportar_protocolo_pdf'),
    path('subestaciones/', subestaciones_view, name='subestaciones'),
    path('subestaciones/exportar-pdf/', exportar_subestaciones_pdf, name='exportar_subestaciones_pdf'),
    path('remotas/', remotas_view, name='remotas'),
    path('remotas/exportar-pdf/', exportar_remotas_pdf, name='exportar_remotas_pdf'),
    path('reconectadores/', reconectadores_view, name='reconectadores'),
    path('subestaciones/', subestaciones_view, name='subestaciones'),
    path('reles/<int:pk>/detalle/', rele_detalle_view, name='rele_detalle'),
    path('reles/', reles_view, name='reles'),
    path('reles/exportar-pdf/', exportar_reles_pdf, name='exportar_reles_pdf'),
    path('interfaces/', interfaces_view, name='interfaces'),
    path('protocolo/', protocolo_view, name='protocolo'),
    path('remotas/', remotas_view, name='remotas'),
    path('api/remotas/', api_remotas, name='api_remotas'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)