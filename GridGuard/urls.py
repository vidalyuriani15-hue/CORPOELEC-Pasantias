"""
URL configuration for CORPOELEC project.
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from equipos.views import reles_view, rele_detalle_view, tensiones_view, perfil_view, cambiar_clave_view, usuarios_view, get_user_permisos, subestaciones_view, index_view, interfaces_view, protocolo_view, remotas_view, api_remotas, exportar_tensiones_pdf, exportar_interfaces_pdf, exportar_protocolo_pdf, exportar_subestaciones_pdf, exportar_remotas_pdf, exportar_reles_pdf, admin_eventos_view, admin_restaurar_view, admin_backup_view, admin_backup_download, admin_backup_delete, bitacora_view, custom_login, custom_logout, admin_root_view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Rutas de autenticación
    path('login/', custom_login, name='user_login'),
    path('cerrar-sesion/', custom_logout, name='user_logout'),

    # Rutas del dashboard principal
    path('', index_view, name='index'),

    # Rutas del perfil de usuario
    path('perfil/', perfil_view, name='perfil'),
    path('cambiar-clave/', cambiar_clave_view, name='cambiar_clave'),
    path('bitacora/', bitacora_view, name='registro'),

    # Rutas de datos principales
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

    # Rutas del administrador (más específicas primero)
    path('admin/backup/descargar/<str:filename>/', admin_backup_download, name='admin_backup_download'),
    path('admin/backup/eliminar/<str:filename>/', admin_backup_delete, name='admin_backup_delete'),
    path('admin/get-permisos/<int:user_id>/', get_user_permisos, name='get_user_permisos'),
    path('admin/usuarios/', usuarios_view, name='admin_usuarios'),
    path('admin/eventos/', admin_eventos_view, name='admin_eventos'),
    path('admin/restaurar/', admin_restaurar_view, name='admin_restaurar'),
    path('admin/backup/', admin_backup_view, name='admin_backup'),
    path('admin/perfil/', perfil_view, name='admin_perfil'),
    path('admin/cambiar-clave/', cambiar_clave_view, name='admin_cambiar_clave'),
    path('admin/cerrar-sesion/', custom_logout, name='logout'),
    path('admin/inicio/', index_view, name='admin_index'),
    path('admin/', admin_root_view, name='admin_root'),

    # Django admin (acceso restringido para desarrolladores)
    path('admin-panel/', admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)