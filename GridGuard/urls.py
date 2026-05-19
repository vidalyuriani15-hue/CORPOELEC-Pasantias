"""
URL configuration for CORPOELEC project.
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from equipos.views import reles_view, rele_detalle_view, tensiones_view, perfil_view, cambiar_clave_view, usuarios_view, subestaciones_view, index_view, interfaces_view, protocolo_view, remotas_view, api_remotas, exportar_tensiones_pdf, exportar_interfaces_pdf, exportar_protocolo_pdf, exportar_subestaciones_pdf, exportar_remotas_pdf, exportar_reles_pdf, admin_eventos_view, admin_restaurar_view, admin_backup_view, bitacora_view, custom_login, custom_logout
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('cerrar-sesion/', custom_logout, name='user_logout'),
    path('admin/cerrar-sesion/', custom_logout, name='logout'),
    path('login/', custom_login, name='user_login'),
    path('perfil/', perfil_view, name='perfil'),
    path('admin/perfil/', perfil_view, name='admin_perfil'),
    path('cambiar-clave/', cambiar_clave_view, name='cambiar_clave'),
    path('admin/cambiar-clave/', cambiar_clave_view, name='admin_cambiar_clave'),
    path('admin/usuarios/', usuarios_view, name='admin_usuarios'),
    path('admin/eventos/', admin_eventos_view, name='admin_eventos'),
    path('admin/restaurar/', admin_restaurar_view, name='admin_restaurar'),
    path('admin/backup/', admin_backup_view, name='admin_backup'),
    path('bitacora/', bitacora_view, name='registro'),
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
    path('reles/<int:pk>/detalle/', rele_detalle_view, name='rele_detalle'),
    path('reles/', reles_view, name='reles'),
    path('reles/exportar-pdf/', exportar_reles_pdf, name='exportar_reles_pdf'),
    path('api/remotas/', api_remotas, name='api_remotas'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)