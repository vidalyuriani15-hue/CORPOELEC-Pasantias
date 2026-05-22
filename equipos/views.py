# -*- coding: utf-8 -*- 
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, FileResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from .models import *
from .decorators import no_cache, puede_crear, puede_actualizar, puede_eliminar
import sys
import os
import shutil
import zipfile
from datetime import datetime
from django.conf import settings

@login_required(login_url='/login/')
def get_user_permisos(request, user_id):
    """API para obtener permisos de un usuario"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    try:
        usuario_perfil = Usuario.objects.get(Id_user_id=user_id)
        permisos = usuario_perfil.permisos
    except Usuario.DoesNotExist:
        permisos = {'crear': False, 'actualizar': False, 'eliminar': False}
    return JsonResponse(permisos)

@login_required(login_url='/login/')
def index_view(request):
    """Vista principal del dashboard"""
    total_reconectadores = Reconectador.objects.count() or 0
    total_reles = Rele.objects.count() or 0
    total_subestaciones = Subestacion.objects.count() or 0
    total_remotas = Remota.objects.count() or 0
    total_interfaces = InterfazDeComunicacion.objects.filter(Tipo_Interfaz='PUERTOS', Activo=True).count() or 0
    total_protocolos = InterfazDeComunicacion.objects.filter(Tipo_Interfaz='PROTOCOLOS', Activo=True).count() or 0
    total_tensiones = NivelTension.objects.count() or 0

    ultimos_reconectadores = list(Reconectador.objects.all().order_by('-Fecha_Reg')[:5]) if total_reconectadores > 0 else []
    ultimos_reles = list(Rele.objects.all().order_by('-Fecha_Reg')[:5]) if total_reles > 0 else []
    ultimas_subestaciones = list(Subestacion.objects.all().order_by('-Fecha_Reg')[:5]) if total_subestaciones > 0 else []
    context = {
        'title': 'GridGuard - Dashboard',
        'total_reconectadores': total_reconectadores,
        'total_reles': total_reles,
        'total_subestaciones': total_subestaciones,
        'total_remotas': total_remotas,
        'total_interfaces': total_interfaces,
        'total_protocolos': total_protocolos,
        'total_tensiones': total_tensiones,
        'ultimos_reconectadores': ultimos_reconectadores,
        'ultimos_reles': ultimos_reles,
        'ultimas_subestaciones': ultimas_subestaciones,
    }
    return render(request, 'index.html', context)

@no_cache
@login_required(login_url='/login/')
def perfil_view(request):
    """Vista de perfil de usuario"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, 'Perfil actualizado correctamente.', extra_tags='updated')
        return redirect('perfil')
    
    context = {
        'title': 'Mi Perfil',
        'user': request.user
    }
    return render(request, 'perfil.html', context)

@no_cache
@login_required(login_url='/login/')
def cambiar_clave_view(request):
    """Vista para cambiar contrasenia"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(old_password):
            messages.error(request, 'La contrasenia actual es incorrecta.')
        elif new_password != confirm_password:
            messages.error(request, 'Las nuevas contrasenias no coinciden.')
        elif len(new_password) < 8:
            messages.error(request, 'La contrasenia debe tener al menos 8 caracteres.')
        else:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, 'Contrasenia cambiada correctamente.')
            return redirect('cambiar_clave')
    
    context = {
        'title': 'Cambiar Contrasenia'
    }
    return render(request, 'cambiar_clave.html', context)

@no_cache
@login_required(login_url='/login/')
def usuarios_view(request):
    """Vista de gestion de usuarios"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')
    
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            user_id = request.POST.get('user_id')
            try:
                user = User.objects.get(id=user_id)
                username = user.username
                user.delete()
                registrar_evento(request, 'ELIMINACION', f'Usuario eliminado: {username}')
                messages.success(request, 'Usuario eliminado correctamente.', extra_tags='deleted')
            except User.DoesNotExist:
                messages.error(request, 'Usuario no encontrado.')
            return redirect('admin_usuarios')
        elif request.POST.get('crear'):
            username = request.POST.get('username')
            password = request.POST.get('password')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            email = request.POST.get('email', '')
            is_superuser = request.POST.get('is_superuser') is not None
            permisos = {
                'crear': request.POST.get('permiso_crear') is not None,
                'actualizar': request.POST.get('permiso_actualizar') is not None,
                'eliminar': request.POST.get('permiso_eliminar') is not None,
            }
            try:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_superuser=is_superuser,
                    is_staff=is_superuser,
                )
                usuario_perfil, created = Usuario.objects.get_or_create(
                    Id_user=user,
                    defaults={'Nombre': f'{first_name} {last_name}', 'Correo': email, 'Nivel_User': 'admin' if is_superuser else 'usuario', 'permisos': permisos}
                )
                if not created:
                    usuario_perfil.permisos = permisos
                    usuario_perfil.save()
                rol = 'Administrador' if is_superuser else 'Usuario'
                registrar_evento(request, 'CREACION', f'Usuario creado: {username} ({rol})')
                messages.success(request, 'Usuario creado correctamente.')
            except Exception as e:
                messages.error(request, f'Error al crear usuario: {str(e)}')
            return redirect('admin_usuarios')
        elif request.POST.get('editar'):
            user_id = request.POST.get('user_id')
            permisos = {
                'crear': request.POST.get('permiso_crear') is not None,
                'actualizar': request.POST.get('permiso_actualizar') is not None,
                'eliminar': request.POST.get('permiso_eliminar') is not None,
            }
            try:
                user = User.objects.get(id=user_id)
                usuario_perfil, created = Usuario.objects.get_or_create(Id_user=user)
                usuario_perfil.permisos = permisos
                usuario_perfil.save()
                registrar_evento(request, 'ACTUALIZACION', f'Permisos actualizados para: {user.username}')
                messages.success(request, 'Permisos actualizados correctamente.', extra_tags='updated')
            except User.DoesNotExist:
                messages.error(request, 'Usuario no encontrado.')
            return redirect('admin_usuarios')
    
    usuarios = User.objects.select_related('usuario').all().order_by('-date_joined')
    
    context = {
        'title': 'Gestion de Usuarios',
        'usuarios': usuarios
    }
    return render(request, 'admin/usuarios.html', context)

@no_cache
@login_required(login_url='/login/')
def subestaciones_view(request):
    """Vista de subestaciones"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            if not puede_eliminar(request):
                messages.error(request, 'No tiene permisos para eliminar subestaciones.')
                return redirect('subestaciones')
            sub_id = request.POST.get('sub_id')
            try:
                sub = Subestacion.objects.get(Id_Sub_est=sub_id)
                sub_nombre = sub.Nombre
                sub.delete()
                registrar_evento(request, 'ELIMINACION', f'Subestacion eliminada: {sub_nombre}')
                messages.success(request, 'Subestacion eliminada correctamente.', extra_tags='deleted')
            except Subestacion.DoesNotExist:
                messages.error(request, 'Subestacion no encontrada.')
            return redirect('subestaciones')
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para actualizar subestaciones.')
                return redirect('subestaciones')
            sub_id = request.POST.get('sub_id')
            nombre = request.POST.get('nombre')
            id_ten_id = request.POST.get('id_ten')
            ubicacion = request.POST.get('ubicacion')
            coordenadas = request.POST.get('coordenadas')
            try:
                sub = Subestacion.objects.get(Id_Sub_est=sub_id)
                sub.Nombre = nombre
                sub.Id_Ten = NivelTension.objects.get(Id_Ten=id_ten_id)
                sub.Ubicación = ubicacion
                sub.Coordenadas = coordenadas
                sub.save()
                registrar_evento(request, 'ACTUALIZACION', f'Subestacion actualizada: {sub.Nombre}')
                messages.success(request, 'Subestacion actualizada correctamente.', extra_tags='updated')
            except Subestacion.DoesNotExist:
                messages.error(request, 'Subestacion no encontrada.')
            except NivelTension.DoesNotExist:
                messages.error(request, 'Nivel de tension no valido.')
            return redirect('subestaciones')
        else:
            if not puede_crear(request):
                messages.error(request, 'No tiene permisos para crear subestaciones.')
                return redirect('subestaciones')
            nombre = request.POST.get('nombre')
            id_ten_id = request.POST.get('id_ten')
            ubicacion = request.POST.get('ubicacion')
            coordenadas = request.POST.get('coordenadas')
            
            if nombre and id_ten_id:
                try:
                    id_ten = NivelTension.objects.get(Id_Ten=id_ten_id)
                    sub = Subestacion.objects.create(
                        Nombre=nombre,
                        Id_Ten=id_ten,
                        Ubicación=ubicacion,
                        Coordenadas=coordenadas,
                        creado_por=request.user
                    )
                    registrar_evento(request, 'CREACION', f'Subestacion creada: {sub.Nombre}')
                    messages.success(request, 'Subestacion creada correctamente.')
                except NivelTension.DoesNotExist:
                    messages.error(request, 'Nivel de tension no valido.')
                return redirect('subestaciones')
    
    subestaciones_list = Subestacion.objects.all().order_by('Nombre')
    paginator = Paginator(subestaciones_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    tensiones = NivelTension.objects.all().order_by('Nivel')
    
    context = {
        'title': 'Subestaciones',
        'page_obj': page_obj,
        'tensiones': tensiones,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'subestaciones.html', context)

@no_cache
@login_required(login_url='/login/')
def tensiones_view(request):
    """Vista de niveles de tensión"""
    if request.method == 'POST':
        if request.POST.get('crear'):
            if not puede_crear(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('tensiones')
            tipo_ten = request.POST.get('tipo_ten')
            nivel = request.POST.get('nivel')
            if tipo_ten and nivel:
                ten = NivelTension.objects.create(
                    Tipo_ten=tipo_ten,
                    Nivel=nivel,
                    creado_por=request.user
                )
                registrar_evento(request, 'CREACION', f'Nivel de tension creado: {ten.get_Tipo_ten_display()} {ten.get_Nivel_display()}')
                messages.success(request, 'Nivel de tensión creado correctamente.')
            else:
                messages.error(request, 'Datos incompletos.')
            return redirect('tensiones')
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('tensiones')
            ten_id = request.POST.get('ten_id')
            tipo_ten = request.POST.get('tipo_ten')
            nivel = request.POST.get('nivel')
            try:
                ten = NivelTension.objects.get(Id_Ten=ten_id)
                ten.Tipo_ten = tipo_ten
                ten.Nivel = nivel
                ten.save()
                registrar_evento(request, 'ACTUALIZACION', f'Nivel de tension actualizado: {ten.get_Tipo_ten_display()} {ten.get_Nivel_display()}')
                messages.success(request, 'Nivel de tensión actualizado correctamente.', extra_tags='updated')
            except NivelTension.DoesNotExist:
                messages.error(request, 'Nivel de tensión no encontrado.')
            return redirect('tensiones')
        elif request.POST.get('eliminar'):
            if not puede_eliminar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('tensiones')
            ten_id = request.POST.get('ten_id')
            try:
                ten = NivelTension.objects.get(Id_Ten=ten_id)
                ten_label = f'{ten.get_Tipo_ten_display()} {ten.get_Nivel_display()}'
                ten.delete()
                registrar_evento(request, 'ELIMINACION', f'Nivel de tension eliminado: {ten_label}')
                messages.success(request, 'Nivel de tensión eliminado correctamente.', extra_tags='deleted')
            except NivelTension.DoesNotExist:
                messages.error(request, 'Nivel de tensión no encontrado.')
            return redirect('tensiones')
    
    tensiones = NivelTension.objects.all().order_by('Nivel')
    paginator = Paginator(tensiones, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Niveles de Tensión',
        'page_obj': page_obj,
        'tensiones': tensiones,
        'tipo_choices': NivelTension.TIPO_CHOICES,
        'nivel_choices': NivelTension.NIVEL_CHOICES,
        'nivel_choices_simple': [(v, v) for v, _ in NivelTension.NIVEL_CHOICES],
        'is_admin': request.user.is_superuser,
    }
    return render(request, 'tensiones.html', context)

@login_required(login_url='/login/')
@no_cache
def interfaces_view(request):
    """Vista de interfaces de comunicacion"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            if not puede_eliminar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('interfaces')
            iface_id = request.POST.get('interfaz_id')
            try:
                iface = InterfazDeComunicacion.objects.get(Id_Interfaz=iface_id)
                
                with transaction.atomic():
                    # Limpiar relaciones M2M de Relés antes de desactivar
                    reles_afectados = Rele.objects.filter(
                        Q(Puertos__Id_Interfaz=iface_id) | Q(Protocolos__Id_Interfaz=iface_id)
                    ).distinct()
                    for rele in reles_afectados:
                        rele.Puertos.remove(*rele.Puertos.filter(Id_Interfaz=iface_id).values_list('Id_Puerto', flat=True))
                        rele.Protocolos.remove(*rele.Protocolos.filter(Id_Interfaz=iface_id).values_list('Id_Protocolo', flat=True))
                    
                    # Limpiar relaciones M2M de Remotas
                    remotas_afectadas = Remota.objects.filter(Interfaces=iface).distinct()
                    for remota in remotas_afectadas:
                        remota.Interfaces.remove(iface_id)
                        remota.Protocolos.remove(*remota.Protocolos.filter(Id_Interfaz=iface_id).values_list('Id_Protocolo', flat=True))
                    
                    # Eliminación lógica: marcar como inactivo
                    iface.Activo = False
                    iface.save()
                    registrar_evento(request, 'ELIMINACION', f'Interfaz de Comunicacion eliminada: {iface.get_Tipo_Interfaz_display()}')
                    messages.success(request, 'Interfaz de Comunicación eliminada correctamente.', extra_tags='deleted')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada.')
            return redirect('interfaces')
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('interfaces')
            iface_id = request.POST.get('interfaz_id')
            tipos_puerto = request.POST.getlist('tipos_puerto')
            try:
                with transaction.atomic():
                    iface = InterfazDeComunicacion.objects.select_for_update().get(Id_Interfaz=iface_id)
                    iface.puertos.all().delete()
                    for tipo in tipos_puerto:
                        PuertoComunicacion.objects.create(
                            Id_Interfaz=iface,
                            Tipo=tipo,
                            creado_por=request.user
                        )
                    iface.Puertos_C = len(tipos_puerto)
                    iface.Tipo_Interfaz = 'PUERTOS'
                    iface.save()
                    # Validar
                    try:
                        iface.full_clean()
                    except Exception as e:
                        messages.error(request, f'Error de validación: {str(e)}')
                        raise  # Rollback via transaction.atomic()
                    messages.success(request, 'Interfaz actualizada correctamente.', extra_tags='updated')
                registrar_evento(request, 'ACTUALIZACION', 'Interfaz de Puertos editada')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada.')
            return redirect('interfaces')
        else:
            if not puede_crear(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('interfaces')
            tipos_puerto = request.POST.getlist('tipos_puerto')
            if tipos_puerto:
                iface = InterfazDeComunicacion.objects.create(
                    Puertos_C=len(tipos_puerto),
                    Tipo_Interfaz='PUERTOS',
                    creado_por=request.user
                )
                for tipo in tipos_puerto:
                    PuertoComunicacion.objects.create(
                        Id_Interfaz=iface,
                        Tipo=tipo,
                        creado_por=request.user
                    )
                # Validar consistencia
                try:
                    iface.full_clean()
                except Exception as e:
                    messages.error(request, f'Error de validación: {str(e)}')
                    iface.delete()
                    return redirect('interfaces')
                registrar_evento(request, 'CREACION', 'Interfaz de Puertos creada')
                messages.success(request, 'Interfaz creada correctamente')
                return redirect('interfaces')
    
    interfaces_list = InterfazDeComunicacion.objects.filter(Tipo_Interfaz='PUERTOS', Activo=True).prefetch_related('puertos').order_by('Id_Interfaz')
    paginator = Paginator(interfaces_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    puertos_tipos = PuertoComunicacion.TIPO_CHOICES
    
    context = {
        'title': 'Interfaz de Comunicacion',
        'page_obj': page_obj,
        'puertos_tipos': puertos_tipos,
        'is_admin': request.user.is_superuser,
        'puede_crear': puede_crear(request),
        'puede_actualizar': puede_actualizar(request),
        'puede_eliminar': puede_eliminar(request)
    }
    return render(request, 'interfaces.html', context)

@login_required(login_url='/login/')
@no_cache
def protocolo_view(request):
    """Vista de protocolos e interfaces"""
    if request.method == 'POST':
        # Crear interfaz con protocolos
        if request.POST.get('crear'):
            if not puede_crear(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('protocolo')
            tipos_protocolo = request.POST.getlist('tipos_protocolo')
            with transaction.atomic():
                interfaz = InterfazDeComunicacion.objects.create(
                    Puertos_C=0,
                    Tipo_Interfaz='PROTOCOLOS',
                    creado_por=request.user
                )
                for tipo in tipos_protocolo:
                    Protocolo.objects.create(
                        Id_Interfaz=interfaz,
                        Tipo=tipo,
                        creado_por=request.user
                    )
                # Validar consistencia
                try:
                    interfaz.full_clean()
                except Exception as e:
                    messages.error(request, f'Error de validación: {str(e)}')
                    raise  # Rollback
            registrar_evento(request, 'CREACION', f'Interfaz de Protocolos creada: {tipos_protocolo}')
            messages.success(request, 'Interfaz creada correctamente')
        
        # Editar interfaz/protocolos
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('protocolo')
            interfaz_id = request.POST.get('interfaz_id')
            try:
                with transaction.atomic():
                    interfaz = InterfazDeComunicacion.objects.select_for_update().get(Id_Interfaz=interfaz_id)
                    Protocolo.objects.filter(Id_Interfaz=interfaz).delete()
                    tipos_protocolo = request.POST.getlist('tipos_protocolo')
                    for tipo in tipos_protocolo:
                        Protocolo.objects.create(
                            Id_Interfaz=interfaz,
                            Tipo=tipo,
                            creado_por=request.user
                        )
                    interfaz.Puertos_C = 0
                    interfaz.Tipo_Interfaz = 'PROTOCOLOS'
                    interfaz.save()
                    # Validar
                    try:
                        interfaz.full_clean()
                    except Exception as e:
                        messages.error(request, f'Error de validación: {str(e)}')
                        raise
                messages.success(request, 'Interfaz actualizada correctamente', extra_tags='updated')
                registrar_evento(request, 'ACTUALIZACION', 'Interfaz de Protocolos editada')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada')
        
        # Eliminar interfaz con limpieza de dependencias (eliminación lógica)
        elif request.POST.get('eliminar'):
            if not puede_eliminar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('protocolo')
            interfaz_id = request.POST.get('interfaz_id')
            try:
                interfaz = InterfazDeComunicacion.objects.get(Id_Interfaz=interfaz_id)
                
                with transaction.atomic():
                    # Limpiar relaciones M2M de Relés
                    reles_afectados = Rele.objects.filter(
                        Q(Protocolos__Id_Interfaz=interfaz_id) | Q(Puertos__Id_Interfaz=interfaz_id)
                    ).distinct()
                    for rele in reles_afectados:
                        rele.Puertos.remove(*rele.Puertos.filter(Id_Interfaz=interfaz_id).values_list('Id_Puerto', flat=True))
                        rele.Protocolos.remove(*rele.Protocolos.filter(Id_Interfaz=interfaz_id).values_list('Id_Protocolo', flat=True))
                    
                    # Limpiar relaciones M2M de Remotas
                    remotas_afectadas = Remota.objects.filter(Interfaces=interfaz).distinct()
                    for remota in remotas_afectadas:
                        remota.Interfaces.remove(interfaz_id)
                        remota.Protocolos.remove(*remota.Protocolos.filter(Id_Interfaz=interfaz_id).values_list('Id_Protocolo', flat=True))
                    
                    # Eliminación lógica
                    interfaz.Activo = False
                    interfaz.save()
                registrar_evento(request, 'ELIMINACION', f'Interfaz de Protocolos eliminada: {interfaz.get_Tipo_Interfaz_display()}')
                messages.success(request, 'Protocolos de Telecontrol y Energía eliminados correctamente.', extra_tags='deleted')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada')
    
    interfaces = InterfazDeComunicacion.objects.filter(Tipo_Interfaz='PROTOCOLOS', Activo=True).prefetch_related('protocolos').all().order_by('Id_Interfaz')
    paginator = Paginator(interfaces, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Protocolos',
        'page_obj': page_obj,
        'is_admin': request.user.is_superuser,
        'puede_crear': puede_crear(request),
        'puede_actualizar': puede_actualizar(request),
        'puede_eliminar': puede_eliminar(request)
    }
    return render(request, 'protocolo.html', context)


@no_cache
@login_required(login_url='/login/')
def remotas_view(request):
    """Vista de remotas"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            if not puede_eliminar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('remotas')
            remota_id = request.POST.get('remota_id')
            try:
                remota = Remota.objects.get(Id_Remota=remota_id)
                marca_modelo = f'{remota.Marca} {remota.Modelo}'
                remota.delete()
                registrar_evento(request, 'ELIMINACION', f'Remota eliminada: {marca_modelo}')
                messages.success(request, 'Remota eliminada correctamente.', extra_tags='deleted')
            except Remota.DoesNotExist:
                messages.error(request, 'Remota no encontrada.')
            return redirect('remotas')
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('remotas')
            remota_id = request.POST.get('remota_id')
            marca = request.POST.get('marca')
            modelo = request.POST.get('modelo')
            id_ten_id = request.POST.get('id_ten')
            try:
                with transaction.atomic():
                    remota = Remota.objects.select_for_update().get(Id_Remota=remota_id)
                    remota.Marca = marca
                    remota.Modelo = modelo
                    remota.Id_Ten = NivelTension.objects.get(Id_Ten=id_ten_id) if id_ten_id else None
                    remota.save()
                registrar_evento(request, 'ACTUALIZACION', f'Remota actualizada: {remota.Marca} {remota.Modelo}')
                messages.success(request, 'Remota actualizada correctamente.', extra_tags='updated')
            except Remota.DoesNotExist:
                messages.error(request, 'Remota no encontrada.')
            return redirect('remotas')
        else:
            marca = request.POST.get('marca')
            modelo = request.POST.get('modelo')
            id_ten_id = request.POST.get('id_ten')
            
            if marca and modelo:
                if not puede_crear(request):
                    messages.error(request, 'No tiene permisos para realizar esta acción.')
                    return redirect('remotas')
                id_ten = NivelTension.objects.get(Id_Ten=id_ten_id) if id_ten_id else None
                remota = Remota.objects.create(
                    Marca=marca,
                    Modelo=modelo,
                    Id_Ten=id_ten,
                    creado_por=request.user
                )
                registrar_evento(request, 'CREACION', f'Remota creada: {remota.Marca} {remota.Modelo}')
                messages.success(request, 'Remota creada correctamente.')
                return redirect('remotas')
    
    remotas_list = Remota.objects.all().order_by('Id_Remota')
    paginator = Paginator(remotas_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    tensiones = NivelTension.objects.all().order_by('Nivel')
    
    context = {
        'title': 'Remotas',
        'page_obj': page_obj,
        'tensiones': tensiones,
        'is_admin': request.user.is_superuser,
        'puede_crear': puede_crear(request),
        'puede_actualizar': puede_actualizar(request),
        'puede_eliminar': puede_eliminar(request)
    }
    return render(request, 'remotas.html', context)

@login_required(login_url='/login/')
def reles_view(request):
    """Vista de relés"""
    # API: obtener detalle de un relé para edición
    if request.GET.get('detalle') == '1' and request.GET.get('id'):
        rele = get_object_or_404(Rele, Id_relé=request.GET.get('id'))
        
        # Datos de remota asociada (si existe)
        remota_data = {}
        if rele.Remota:
            remota = rele.Remota
            remota_data = {
                'remota_id': remota.Id_Remota,
                'remota_marca': remota.Marca,
                'remota_modelo': remota.Modelo,
                'remota_niveles': list(remota.Niveles_Ten.values_list('Id_Ten', flat=True)),
                'remota_protocolos': list(remota.Protocolos.values_list('Id_Protocolo', flat=True)),
                'remota_interfaces': list(remota.Interfaces.values_list('Id_Interfaz', flat=True))
            }
        
        # Validar IDs contra la BD para evitar referencias huérfanas (D6)
        valid_protocolo_ids = set(Protocolo.objects.values_list('Id_Protocolo', flat=True))
        valid_puerto_ids = set(PuertoComunicacion.objects.values_list('Id_Puerto', flat=True))
        
        data = {
            'id_sub_est': rele.Id_Sub_est.Id_Sub_est,
            'id_ten': rele.Id_Ten.Id_Ten,
            'marca': rele.Marca,
            'modelo': rele.Modelo,
            'estado': rele.Estado,
            'observaciones': rele.Observaciones or '',
            'es_remoto': rele.EsRemoto,
            'imagen_url': rele.Imagen.url if rele.Imagen else None,
            'protocolos': [pid for pid in rele.Protocolos.values_list('Id_Protocolo', flat=True) if pid in valid_protocolo_ids],
            'puertos': [pid for pid in rele.Puertos.values_list('Id_Puerto', flat=True) if pid in valid_puerto_ids],
        }
        data.update(remota_data)
        return JsonResponse(data)
    
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            if not puede_eliminar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('reles')
            rele_id = request.POST.get('rele_id')
            try:
                with transaction.atomic():
                    rele = Rele.objects.select_for_update().get(Id_relé=rele_id)
                    rele_ident = f'{rele.Marca} {rele.Modelo} (ID {rele_id})'
                    rele.delete()
                    registrar_evento(request, 'ELIMINACION', f'Relé eliminado: {rele_ident}')
                    messages.success(request, 'Relé eliminado correctamente.', extra_tags='deleted')
            except Rele.DoesNotExist:
                messages.error(request, 'Relé no encontrado.')
            return redirect('reles')
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('reles')
            rele_id = request.POST.get('rele_id')
            
            # DEBUG: Log POST data
            print("=" * 80, file=sys.stderr)
            print(f"DEBUG EDIT Rele {rele_id} - POST DATA:", file=sys.stderr)
            for key, value in request.POST.items():
                print(f"  {key}: {value}", file=sys.stderr)
            print(f"  protocolos getlist: {request.POST.getlist('protocolos')}", file=sys.stderr)
            print(f"  puertos getlist: {request.POST.getlist('puertos')}", file=sys.stderr)
            print(f"  remota_nivel_tension: {request.POST.getlist('remota_nivel_tension')}", file=sys.stderr)
            print(f"  remota_protocolos: {request.POST.getlist('remota_protocolos')}", file=sys.stderr)
            print(f"  remota_interfaces: {request.POST.getlist('remota_interfaces')}", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            
            try:
                with transaction.atomic():
                    rele = Rele.objects.select_for_update().get(Id_relé=rele_id)
                    rele.Id_Sub_est = Subestacion.objects.get(Id_Sub_est=request.POST.get('id_sub_est'))
                    rele.Id_Ten = NivelTension.objects.get(Id_Ten=request.POST.get('id_ten'))
                    rele.Marca = request.POST.get('marca')
                    rele.Modelo = request.POST.get('modelo')
                    rele.Estado = request.POST.get('estado')
                    rele.Observaciones = request.POST.get('observaciones', '')
                    
                    if request.FILES.get('imagen'):
                        rele.Imagen = request.FILES.get('imagen')
                    
                    # M2M assignments on Rele
                    protocolos_list = request.POST.getlist('protocolos')
                    puertos_list = request.POST.getlist('puertos')
                    print(f"DEBUG: Assigning Protocolos to Rele: {protocolos_list}", file=sys.stderr)
                    print(f"DEBUG: Assigning Puertos to Rele: {puertos_list}", file=sys.stderr)
                    rele.Protocolos.set(protocolos_list)
                    rele.Puertos.set(puertos_list)
                    
                    # Handle remote association and remote M2M
                    es_remoto = request.POST.get('es_remoto') == 'si'
                    rele.EsRemoto = es_remoto
                    
                    if es_remoto and request.POST.get('remota_id'):
                        remota = Remota.objects.get(Id_Remota=request.POST.get('remota_id'))
                        rele.Remota = remota
                        
                        # Update Remota's M2M fields
                        remota_niveles = request.POST.getlist('remota_nivel_tension')
                        remota_protocolos = request.POST.getlist('remota_protocolos')
                        remota_interfaces = request.POST.getlist('remota_interfaces')
                        
                        print(f"DEBUG: Updating Remota {remota.Id_Remota} - Niveles: {remota_niveles}, Protocolos: {remota_protocolos}, Interfaces: {remota_interfaces}", file=sys.stderr)
                        
                        remota.Niveles_Ten.set(remota_niveles)
                        remota.Protocolos.set(remota_protocolos)
                        remota.Interfaces.set(remota_interfaces)
                        remota.save()
                    else:
                        # Clear remote association if unchecked
                        rele.Remota = None
                    
                    rele.save()
                    print(f"DEBUG: Rele {rele_id} saved successfully. EsRemoto={es_remoto}", file=sys.stderr)
                    registrar_evento(request, 'ACTUALIZACION', f'Relé actualizado: {rele.Marca} {rele.Modelo}')
                    messages.success(request, 'Relé actualizado correctamente.', extra_tags='updated')
            except (Rele.DoesNotExist, Subestacion.DoesNotExist, NivelTension.DoesNotExist, Remota.DoesNotExist) as e:
                print(f"DEBUG ERROR: {str(e)}", file=sys.stderr)
                messages.error(request, f'Error al actualizar: {str(e)}')
            return redirect('reles')
        else:
            if not puede_crear(request):
                messages.error(request, 'No tiene permisos para crear relés.')
                return redirect('reles')
            try:
                sub = Subestacion.objects.get(Id_Sub_est=request.POST.get('id_sub_est'))
                ten = NivelTension.objects.get(Id_Ten=request.POST.get('id_ten'))
                
                with transaction.atomic():
                    rele = Rele.objects.create(
                        Id_Sub_est=sub,
                        Id_Ten=ten,
                        Marca=request.POST.get('marca'),
                        Modelo=request.POST.get('modelo'),
                        Estado=request.POST.get('estado'),
                        Observaciones=request.POST.get('observaciones', ''),
                        creado_por=request.user
                    )
                    
                    if request.FILES.get('imagen'):
                        rele.Imagen = request.FILES.get('imagen')
                        rele.save()
                    
                    # M2M assignments on Rele
                    protocolos_list = request.POST.getlist('protocolos')
                    puertos_list = request.POST.getlist('puertos')
                    print(f"DEBUG: Assigning Protocolos to Rele: {protocolos_list}", file=sys.stderr)
                    print(f"DEBUG: Assigning Puertos to Rele: {puertos_list}", file=sys.stderr)
                    rele.Protocolos.set(protocolos_list)
                    rele.Puertos.set(puertos_list)
                    
                    # Handle remote association and remote M2M
                    es_remoto = request.POST.get('es_remoto') == 'si'
                    rele.EsRemoto = es_remoto
                    
                    if es_remoto and request.POST.get('remota_id'):
                        remota = Remota.objects.get(Id_Remota=request.POST.get('remota_id'))
                        rele.Remota = remota
                        
                        # Update Remota's M2M fields
                        remota_niveles = request.POST.getlist('remota_nivel_tension')
                        remota_protocolos = request.POST.getlist('remota_protocolos')
                        remota_interfaces = request.POST.getlist('remota_interfaces')
                        
                        print(f"DEBUG: Updating Remota {remota.Id_Remota} - Niveles: {remota_niveles}, Protocolos: {remota_protocolos}, Interfaces: {remota_interfaces}", file=sys.stderr)
                        
                        remota.Niveles_Ten.set(remota_niveles)
                        remota.Protocolos.set(remota_protocolos)
                        remota.Interfaces.set(remota_interfaces)
                        remota.save()
                    
                    rele.save()
                    print(f"DEBUG: Rele created. EsRemoto={es_remoto}, Remota_id={request.POST.get('remota_id')}", file=sys.stderr)
                    
                    registrar_evento(request, 'CREACION', f'Relé creado: {rele.Marca} {rele.Modelo}')
                    messages.success(request, 'Relé creado correctamente.')
                    return redirect('reles')
            except (Subestacion.DoesNotExist, NivelTension.DoesNotExist, Remota.DoesNotExist) as e:
                print(f"DEBUG CREATE ERROR: {str(e)}", file=sys.stderr)
                messages.error(request, f'Error al crear: {str(e)}')
                return redirect('reles')
    elif request.method == 'GET':
        # GET: mostrar lista
        rele_list = Rele.objects.all().order_by('Id_relé')
        paginator = Paginator(rele_list, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Obtener valores únicos para evitar duplicados en los formularios
        subestaciones = Subestacion.objects.select_related('Id_Ten').all().order_by('Nombre')
        tensiones = list(NivelTension.objects.all().order_by('Nivel'))
        
        # Protocolos únicos por tipo (solo activos)
        protocolos_dict = {}
        for p in Protocolo.objects.filter(Activo=True).order_by('Tipo'):
            if p.Tipo not in protocolos_dict:
                protocolos_dict[p.Tipo] = p
        protocolos = list(protocolos_dict.values())
        
        # Puertos únicos por tipo (solo de interfaces activas)
        puertos_dict = {}
        for pt in PuertoComunicacion.objects.filter(Id_Interfaz__Activo=True).order_by('Tipo'):
            if pt.Tipo not in puertos_dict:
                puertos_dict[pt.Tipo] = pt
        puertos = list(puertos_dict.values())
        
        # Remotas únicas por marca+modelo (evita duplicados)
        remotas_dict = {}
        for r in Remota.objects.all().order_by('Marca', 'Modelo'):
            key = f"{r.Marca}|{r.Modelo}"
            if key not in remotas_dict:
                remotas_dict[key] = r
        remotas = list(remotas_dict.values())
        
        # Solo interfaces de tipo PUERTOS activas pueden asignarse a remotas
        interfaces_disponibles = InterfazDeComunicacion.objects.filter(
            Tipo_Interfaz='PUERTOS', Activo=True
        ).prefetch_related('puertos').order_by('Id_Interfaz')
        
        context = {
            'title': 'Relés',
            'page_obj': page_obj,
            'subestaciones': subestaciones,
            'tensiones': tensiones,
            'protocolos': protocolos,
            'puertos': puertos,
            'remotas': remotas,
            'interfaces_disponibles': interfaces_disponibles,
            'is_admin': request.user.is_superuser,
            'puede_crear': puede_crear(request),
            'puede_actualizar': puede_actualizar(request),
            'puede_eliminar': puede_eliminar(request)
        }
        return render(request, 'reles.html', context)

@login_required(login_url='/login/')
def rele_detalle_view(request, pk):
    """Vista de detalle de un relé"""
    rele = get_object_or_404(Rele, Id_relé=pk)
    
    if request.GET.get('modal') == '1':
        return render(request, 'rele_detalle_partial.html', {'rele': rele})
    
    context = {
        'title': f'Detalle de Relé {rele.Id_relé}',
        'rele': rele
    }
    return render(request, 'rele_detalle.html', context)

@login_required(login_url='/login/')
def api_remotas(request):
    """API para obtener datos de remotas en formato JSON"""
    if request.method == 'GET':
        remotas = Remota.objects.all().prefetch_related('Niveles_Ten')
        
        # Obtener marcas únicas
        marcas = list(remotas.values_list('Marca', flat=True).distinct())
        
        # Modelos únicos por marca (evita duplicados modelo+marca)
        modelos_por_marca = {}
        modelos_vistos = set()
        interfaces_por_remota = {}
        
        for remota in remotas:
            marca = remota.Marca
            modelo = remota.Modelo
            key = f"{marca}|{modelo}"
            
            if marca not in modelos_por_marca:
                modelos_por_marca[marca] = {}
            
            # Solo agregar modelo si no se ha visto antes para esta marca
            if key not in modelos_vistos:
                modelos_por_marca[marca][modelo] = {
                    'id': remota.Id_Remota,
                    'nivel': remota.Id_Ten.get_Nivel_display() if remota.Id_Ten else ''
                }
                modelos_vistos.add(key)
            
            interfaces_por_remota[remota.Id_Remota] = list(remota.Interfaces.values_list('Id_Interfaz', flat=True))
        
        # Solo interfaces de tipo PUERTOS activas están disponibles para asignar a remotas
        interfaces_disponibles = list(InterfazDeComunicacion.objects.filter(
            Tipo_Interfaz='PUERTOS', Activo=True
        ).values_list('Id_Interfaz', flat=True).distinct())
        
        return JsonResponse({
            'marcas': marcas,
            'modelos_por_marca': modelos_por_marca,
            'interfaces_por_remota': interfaces_por_remota,
            'interfaces_disponibles': interfaces_disponibles
        })
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required(login_url='/login/')
def exportar_tensiones_pdf(request):
    """Exporta todas las tensiones a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO
    from django.http import FileResponse


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.7*inch, height=0.7*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
               ParagraphStyle('corp', parent=styles['Normal'], fontSize=13, leading=15))]],
            colWidths=[0.8*inch, 1.4*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=13))
    title_p = Paragraph('<b>Niveles de Tensión Registrados</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=14, leading=17, alignment=1))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=styles['Normal'],
                                       fontSize=8, leading=10, alignment=2,
                                       textColor=colors.HexColor('#555555')))
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[2.2*inch, 3.8*inch, 2.0*inch])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(hdr)
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=RED, spaceBefore=0, spaceAfter=8))

    tensiones = NivelTension.objects.all().order_by('Nivel')
    _pw = landscape(letter)[0] - 50
    _ratios = [1.8, 1.5, 3.0, 1.8]
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    data = [[Paragraph(f'<b>{h}</b>', hdr_st) for h in ['Tipo', 'Nivel (kV)', 'Creado Por', 'Fecha Registro']]]
    for tension in tensiones:
        creado_por = tension.creado_por.get_full_name() if tension.creado_por else 'Sistema'
        fecha_reg  = tension.Fecha_Reg.strftime('%d/%m/%Y') if tension.Fecha_Reg else ''
        data.append([Paragraph(tension.get_Tipo_ten_display(), cell_st),
                     Paragraph(tension.get_Nivel_display(), cell_st),
                     Paragraph(creado_por, cell_st),
                     Paragraph(fecha_reg, cell_st)])
    table = Table(data, colWidths=col_w, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('TOPPADDING',    (0, 0), (-1, 0),  6),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  6),
        ('INNERGRID',     (0, 0), (-1, 0),  0,   NAVY),
        ('BOX',           (0, 0), (-1, 0),  0,   NAVY),
        ('LINEBELOW',     (0, 0), (-1, 0),  1.0, colors.white),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, GREY_L]),
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, GREY_B),
        ('LINEBEFORE',    (0, 1), (0,  -1), 0.4, GREY_B),
        ('LINEAFTER',     (-1,1), (-1, -1), 0.4, GREY_B),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_B))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. — Documento de carácter oficial',
        ParagraphStyle('foot', parent=styles['Normal'], fontSize=7.5, leading=9,
                       alignment=1, textColor=colors.HexColor('#666666'))))
    doc.build(elements)
    buffer.seek(0)
    response = FileResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="tensiones.pdf"'
    return response

def exportar_interfaces_pdf(request):
    """Exporta todas las interfaces a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.7*inch, height=0.7*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
               ParagraphStyle('corp', parent=styles['Normal'], fontSize=13, leading=15))]],
            colWidths=[0.8*inch, 1.4*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=13))
    title_p = Paragraph('<b>Interfaces Registradas</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=14, leading=17, alignment=1))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=styles['Normal'],
                                       fontSize=8, leading=10, alignment=2,
                                       textColor=colors.HexColor('#555555')))
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[2.2*inch, 3.8*inch, 2.0*inch])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(hdr)
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=RED, spaceBefore=0, spaceAfter=8))

    interfaces = InterfazDeComunicacion.objects.filter(Activo=True).prefetch_related('puertos').all().order_by('Id_Interfaz')
    interfaces = [i for i in interfaces if i.puertos.exists()]
    _pw = landscape(letter)[0] - 50
    _ratios = [3.5, 2.0, 1.5]
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    data = [[Paragraph(f'<b>{h}</b>', hdr_st) for h in ['Puertos', 'Creado Por', 'Fecha Registro']]]
    for interfaz in interfaces:
        puertos_list = [p.get_Tipo_display() for p in interfaz.puertos.all()]
        puertos_str  = ', '.join(puertos_list) if puertos_list else 'Sin puertos'
        creado_por   = interfaz.creado_por.username if interfaz.creado_por else 'Sistema'
        data.append([Paragraph(puertos_str, cell_st),
                     Paragraph(creado_por, cell_st),
                     Paragraph(interfaz.Fecha_Reg.strftime('%d/%m/%Y') if interfaz.Fecha_Reg else '', cell_st)])
    table = Table(data, colWidths=col_w, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('TOPPADDING',    (0, 0), (-1, 0),  6),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  6),
        ('INNERGRID',     (0, 0), (-1, 0),  0,   NAVY),
        ('BOX',           (0, 0), (-1, 0),  0,   NAVY),
        ('LINEBELOW',     (0, 0), (-1, 0),  1.0, colors.white),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, GREY_L]),
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, GREY_B),
        ('LINEBEFORE',    (0, 1), (0,  -1), 0.4, GREY_B),
        ('LINEAFTER',     (-1,1), (-1, -1), 0.4, GREY_B),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_B))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. — Documento de carácter oficial',
        ParagraphStyle('foot', parent=styles['Normal'], fontSize=7.5, leading=9,
                       alignment=1, textColor=colors.HexColor('#666666'))))
    doc.build(elements)
    buffer.seek(0)
    response = FileResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="interfaces.pdf"'
    return response

def exportar_protocolo_pdf(request):
    """Exporta todos los protocolos a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.7*inch, height=0.7*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
               ParagraphStyle('corp', parent=styles['Normal'], fontSize=13, leading=15))]],
            colWidths=[0.8*inch, 1.4*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=13))
    title_p = Paragraph('<b>Protocolos Registrados</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=14, leading=17, alignment=1))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=styles['Normal'],
                                       fontSize=8, leading=10, alignment=2,
                                       textColor=colors.HexColor('#555555')))
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[2.2*inch, 3.8*inch, 2.0*inch])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(hdr)
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=RED, spaceBefore=0, spaceAfter=8))

    from collections import defaultdict
    protocolos_por_interfaz = defaultdict(list)
    creado_por_por_interfaz = {}
    fecha_por_interfaz = {}
    for protocolo in Protocolo.objects.filter(Id_Interfaz__isnull=False, Id_Interfaz__Activo=True).select_related('Id_Interfaz').all().order_by('Tipo'):
        interfaz_id = protocolo.Id_Interfaz.Id_Interfaz
        protocolos_por_interfaz[interfaz_id].append(protocolo.get_Tipo_display())
        if interfaz_id not in creado_por_por_interfaz:
            creado_por_por_interfaz[interfaz_id] = protocolo.creado_por.username if protocolo.creado_por else 'Sistema'
            fecha_por_interfaz[interfaz_id] = protocolo.Fecha_Reg.strftime('%d/%m/%Y') if protocolo.Fecha_Reg else ''
    _pw = landscape(letter)[0] - 50
    _ratios = [2.5, 2.0, 1.5]
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    data = [[Paragraph(f'<b>{h}</b>', hdr_st) for h in ['Protocolos', 'Creado Por', 'Fecha de Registro']]]
    for interfaz_id, protocolos_list in protocolos_por_interfaz.items():
        data.append([Paragraph(', '.join(protocolos_list), cell_st),
                     Paragraph(creado_por_por_interfaz[interfaz_id], cell_st),
                     Paragraph(fecha_por_interfaz[interfaz_id], cell_st)])
    table = Table(data, colWidths=col_w, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('TOPPADDING',    (0, 0), (-1, 0),  6),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  6),
        ('INNERGRID',     (0, 0), (-1, 0),  0,   NAVY),
        ('BOX',           (0, 0), (-1, 0),  0,   NAVY),
        ('LINEBELOW',     (0, 0), (-1, 0),  1.0, colors.white),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, GREY_L]),
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, GREY_B),
        ('LINEBEFORE',    (0, 1), (0,  -1), 0.4, GREY_B),
        ('LINEAFTER',     (-1,1), (-1, -1), 0.4, GREY_B),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_B))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. — Documento de carácter oficial',
        ParagraphStyle('foot', parent=styles['Normal'], fontSize=7.5, leading=9,
                       alignment=1, textColor=colors.HexColor('#666666'))))
    doc.build(elements)
    buffer.seek(0)
    response = FileResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="protocolos.pdf"'
    return response

def exportar_subestaciones_pdf(request):
    """Exporta todas las subestaciones a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.7*inch, height=0.7*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
               ParagraphStyle('corp', parent=styles['Normal'], fontSize=13, leading=15))]],
            colWidths=[0.8*inch, 1.4*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=13))
    title_p = Paragraph('<b>Subestaciones Registradas</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=14, leading=17, alignment=1))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=styles['Normal'],
                                       fontSize=8, leading=10, alignment=2,
                                       textColor=colors.HexColor('#555555')))
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[2.2*inch, 3.8*inch, 2.0*inch])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(hdr)
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=RED, spaceBefore=0, spaceAfter=8))

    subestaciones = Subestacion.objects.select_related('Id_Ten').all().order_by('Nombre')
    _pw = landscape(letter)[0] - 50
    _ratios = [1.4, 1.4, 1.8, 1.5, 1.5, 1.5]
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    data = [[Paragraph(f'<b>{h}</b>', hdr_st)
             for h in ['Nombre', 'Ubicación', 'Nivel de Tensión', 'Coordenadas', 'Creado Por', 'Fecha de Registro']]]
    for sub in subestaciones:
        nivel     = sub.Id_Ten.get_Nivel_display() if sub.Id_Ten else ''
        coords    = sub.Coordenadas if sub.Coordenadas else ''
        creado_por = sub.creado_por.username if sub.creado_por else 'Sistema'
        fecha     = sub.Fecha_Reg.strftime('%d/%m/%Y') if sub.Fecha_Reg else ''
        data.append([Paragraph(sub.Nombre, cell_st), Paragraph(sub.Ubicación, cell_st),
                     Paragraph(nivel, cell_st), Paragraph(coords, cell_st),
                     Paragraph(creado_por, cell_st), Paragraph(fecha, cell_st)])
    table = Table(data, colWidths=col_w, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('TOPPADDING',    (0, 0), (-1, 0),  6),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  6),
        ('INNERGRID',     (0, 0), (-1, 0),  0,   NAVY),
        ('BOX',           (0, 0), (-1, 0),  0,   NAVY),
        ('LINEBELOW',     (0, 0), (-1, 0),  1.0, colors.white),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, GREY_L]),
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, GREY_B),
        ('LINEBEFORE',    (0, 1), (0,  -1), 0.4, GREY_B),
        ('LINEAFTER',     (-1,1), (-1, -1), 0.4, GREY_B),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_B))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. — Documento de carácter oficial',
        ParagraphStyle('foot', parent=styles['Normal'], fontSize=7.5, leading=9,
                       alignment=1, textColor=colors.HexColor('#666666'))))
    doc.build(elements)
    buffer.seek(0)
    response = FileResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="subestaciones.pdf"'
    return response

def exportar_remotas_pdf(request):
    """Exporta todas las remotas a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.7*inch, height=0.7*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
               ParagraphStyle('corp', parent=styles['Normal'], fontSize=13, leading=15))]],
            colWidths=[0.8*inch, 1.4*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=13))
    title_p = Paragraph('<b>Remotas Registradas</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=14, leading=17, alignment=1))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=styles['Normal'],
                                       fontSize=8, leading=10, alignment=2,
                                       textColor=colors.HexColor('#555555')))
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[2.2*inch, 3.8*inch, 2.0*inch])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(hdr)
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=RED, spaceBefore=0, spaceAfter=8))

    remotas = Remota.objects.select_related('Id_Ten').all().order_by('Id_Remota')
    _pw = landscape(letter)[0] - 50
    _ratios = [1.5, 1.5, 2.2, 1.5, 1.5]
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    data = [[Paragraph(f'<b>{h}</b>', hdr_st)
             for h in ['Marca', 'Modelo', 'Nivel de Tensión', 'Creado Por', 'Fecha Registro']]]
    for remota in remotas:
        nivel_ten  = f"{remota.Id_Ten.get_Tipo_ten_display()} - {remota.Id_Ten.get_Nivel_display()}" if remota.Id_Ten else ''
        creado_por = remota.creado_por.username if remota.creado_por else 'Sistema'
        data.append([Paragraph(remota.Marca or '', cell_st), Paragraph(remota.Modelo or '', cell_st),
                     Paragraph(nivel_ten, cell_st), Paragraph(creado_por, cell_st),
                     Paragraph(remota.Fecha_Reg.strftime('%d/%m/%Y') if remota.Fecha_Reg else '', cell_st)])
    table = Table(data, colWidths=col_w, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('TOPPADDING',    (0, 0), (-1, 0),  6),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  6),
        ('INNERGRID',     (0, 0), (-1, 0),  0,   NAVY),
        ('BOX',           (0, 0), (-1, 0),  0,   NAVY),
        ('LINEBELOW',     (0, 0), (-1, 0),  1.0, colors.white),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, GREY_L]),
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, GREY_B),
        ('LINEBEFORE',    (0, 1), (0,  -1), 0.4, GREY_B),
        ('LINEAFTER',     (-1,1), (-1, -1), 0.4, GREY_B),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_B))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. — Documento de carácter oficial',
        ParagraphStyle('foot', parent=styles['Normal'], fontSize=7.5, leading=9,
                       alignment=1, textColor=colors.HexColor('#666666'))))
    doc.build(elements)
    buffer.seek(0)
    response = FileResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="remotas.pdf"'
    return response

def exportar_reles_pdf(request):
    """Exporta todos los relés a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()

    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')

    # ── Header ───────────────────────────────────────────────────────────────
    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')

    if logo_path:
        logo_img = Image(logo_path, width=0.7*inch, height=0.7*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
                                  ParagraphStyle('corp', parent=styles['Normal'],
                                                 fontSize=13, leading=15))]],
            colWidths=[0.8*inch, 1.4*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=13))

    title_p = Paragraph('<b>Relés Registrados</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=14, leading=17, alignment=1))
    date_p = Paragraph(
        f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
        ParagraphStyle('date', parent=styles['Normal'],
                       fontSize=8, leading=10, alignment=2,
                       textColor=colors.HexColor('#555555')))

    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[2.2*inch, 3.8*inch, 2.0*inch])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(hdr)
    elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=RED, spaceBefore=0, spaceAfter=8))

    # ── Data ─────────────────────────────────────────────────────────────────
    reles = (Rele.objects
             .select_related('Id_Ten', 'Id_Sub_est', 'creado_por', 'Remota', 'Remota__Id_Ten')
             .prefetch_related('Protocolos', 'Puertos')
             .order_by('Id_relé'))

    cell_st = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7, leading=9, alignment=1)

    def wrap(txt):
        return Paragraph(str(txt) if txt else '—', cell_st)

    hdr_st = ParagraphStyle('hdr', parent=styles['Normal'],
                             fontSize=7.5, leading=9, textColor=colors.white, alignment=1)
    col_names = ['Subestación', 'Marca', 'Modelo', 'Nivel (kV)',
                 'Protocolos', 'Puertos', 'Estado',
                 'Remota', 'Marca Remota', 'Modelo Remota', 'Niv. Remota',
                 'Creado Por', 'Fecha Reg.']
    data = [[Paragraph(f'<b>{h}</b>', hdr_st) for h in col_names]]

    for rele in reles:
        nivel = ''
        if rele.Id_Ten:
            tipo = rele.Id_Ten.get_Tipo_ten_display() if hasattr(rele.Id_Ten, 'get_Tipo_ten_display') else ''
            niv  = rele.Id_Ten.get_Nivel_display()    if hasattr(rele.Id_Ten, 'get_Nivel_display')    else str(rele.Id_Ten.Nivel)
            nivel = f"{tipo} - {niv}" if tipo else niv

        protos  = ', '.join(p.get_Tipo_display() for p in rele.Protocolos.all()) or '—'
        puertos = ', '.join(str(p) for p in rele.Puertos.all()) or '—'

        rem      = rele.Remota
        es_rem   = 'Sí' if rele.EsRemoto and rem else 'No'
        marc_rem = rem.Marca  if rem else '—'
        mod_rem  = rem.Modelo if rem else '—'
        niv_rem  = '—'
        if rem and rem.Id_Ten:
            niv_rem = rem.Id_Ten.get_Nivel_display() if hasattr(rem.Id_Ten, 'get_Nivel_display') else str(rem.Id_Ten.Nivel)

        fecha  = rele.Fecha_Reg.strftime('%d/%m/%Y') if rele.Fecha_Reg else '—'
        creado = rele.creado_por.username if rele.creado_por else '—'

        data.append([
            wrap(rele.Id_Sub_est.Nombre if rele.Id_Sub_est else '—'),
            wrap(rele.Marca), wrap(rele.Modelo), wrap(nivel),
            wrap(protos), wrap(puertos), wrap(rele.Estado),
            wrap(es_rem), wrap(marc_rem), wrap(mod_rem), wrap(niv_rem),
            wrap(creado), wrap(fecha),
        ])

    from reportlab.lib.pagesizes import landscape, letter as _letter
    _pw = landscape(_letter)[0] - 50  # ancho total menos márgenes (25+25)
    _ratios = [1.0, 0.7, 0.7, 0.9, 0.8, 0.7, 0.75, 0.5, 0.75, 0.75, 0.65, 0.65, 0.65]
    _total  = sum(_ratios)
    col_w   = [_pw * r / _total for r in _ratios]

    table = Table(data, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle([
        # header fondo y texto
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('TOPPADDING',    (0, 0), (-1, 0),  6),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  6),
        # sin bordes verticales en el header
        ('INNERGRID',     (0, 0), (-1, 0),  0,   NAVY),
        ('BOX',           (0, 0), (-1, 0),  0,   NAVY),
        # línea separadora header / datos
        ('LINEBELOW',     (0, 0), (-1, 0),  1.0, colors.white),
        # filas de datos
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), 7),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, GREY_L]),
        # sólo líneas horizontales entre filas de datos
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, GREY_B),
        ('LINEBEFORE',    (0, 1), (0, -1),  0.4, GREY_B),
        ('LINEAFTER',     (-1, 1),(-1, -1), 0.4, GREY_B),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    # ── Footer ───────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_B))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. — Documento de carácter oficial',
        ParagraphStyle('foot', parent=styles['Normal'],
                       fontSize=7.5, leading=9, alignment=1,
                       textColor=colors.HexColor('#666666'))))

    doc.build(elements)
    buffer.seek(0)
    response = FileResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reles.pdf"'
    return response


_VISTA_NOMBRES = {
    'index': 'Inicio',
    'admin_index': 'Inicio (Admin)',
    'tensiones': 'Niveles de Tensión',
    'interfaces': 'Interfaces',
    'protocolo': 'Protocolos',
    'subestaciones': 'Subestaciones',
    'remotas': 'Remotas',
    'reles': 'Relés',
    'rele_detalle': 'Detalle de Relé',
    'admin_usuarios': 'Usuarios',
    'admin_eventos': 'Registro de Eventos',
    'perfil': 'Perfil',
    'admin_perfil': 'Perfil (Admin)',
    'cambiar_clave': 'Cambiar Clave',
    'admin_cambiar_clave': 'Cambiar Clave (Admin)',
    'user_login': 'Login',
    'user_logout': 'Logout',
    'logout': 'Logout',
    'registro': 'Bitácora',
    'admin_restaurar': 'Restaurar',
    'admin_backup': 'Backup',
}

def registrar_evento(request, tipo, descripcion):
    """Registra un evento en la bitácora"""
    from .models import Evento
    url_name = getattr(request.resolver_match, 'url_name', '') or ''
    vista = _VISTA_NOMBRES.get(url_name, url_name.replace('_', ' ').title() if url_name else request.path)
    Evento.objects.create(
        Tipo=tipo,
        Descripcion=descripcion,
        Usuario=request.user if request.user.is_authenticated else None,
        IP_Address=request.META.get('REMOTE_ADDR', None),
        Vista=vista,
    )


@no_cache
def custom_login(request):
    """Login con registro en bitácora (LOGIN)"""
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
            registrar_evento(request, 'LOGIN', f'Inicio de sesión desde IP {request.META.get("REMOTE_ADDR", "desconocida")}')
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


@no_cache
def custom_logout(request):
    """Logout con registro en bitácora (LOGOUT)"""
    from django.contrib.auth import logout
    logout(request)
    registrar_evento(request, 'LOGOUT', f'Cierre de sesión desde IP {request.META.get("REMOTE_ADDR", "desconocida")}')
    response = redirect('/login/')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required(login_url='/login/')
def bitacora_view(request):
    """Vista de bitácora de eventos del sistema"""
    tipo_usuario = request.GET.get('tipo_usuario', '')
    busqueda = request.GET.get('q', '')

    eventos_list = Evento.objects.exclude(Tipo__in=['LOGIN', 'LOGOUT']).order_by('-Fecha_Hora')

    if tipo_usuario == 'admin':
        eventos_list = eventos_list.filter(Usuario__is_superuser=True)
    elif tipo_usuario == 'regular':
        eventos_list = eventos_list.filter(Usuario__is_superuser=False, Usuario__isnull=False)
    elif tipo_usuario == 'sistema':
        eventos_list = eventos_list.filter(Usuario__isnull=True)

    if busqueda:
        eventos_list = eventos_list.filter(
            Q(Usuario__username__icontains=busqueda) |
            Q(Vista__icontains=busqueda) |
            Q(Descripcion__icontains=busqueda)
        )

    paginator = Paginator(eventos_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Bitácora de Eventos',
        'page_obj': page_obj,
        'is_admin': request.user.is_superuser,
        'tipo_usuario': tipo_usuario,
        'busqueda': busqueda,
    }
    return render(request, 'bitacora.html', context)


@login_required(login_url='/login/')
def admin_eventos_view(request):
    """Vista de registro de eventos"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')
    
    eventos = Evento.objects.all().order_by('-Fecha_Hora')
    context = {
        'title': 'Registro de Eventos',
        'eventos': eventos,
    }
    return render(request, 'admin/eventos.html', context)


@login_required(login_url='/login/')
def admin_restaurar_view(request):
    """Vista de restaurar sistema"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')

    if request.method == 'POST':
        confirmar = request.POST.get('confirmar')
        backup_file = request.FILES.get('backup_file')

        if not confirmar:
            messages.error(request, 'Debe marcar la casilla de confirmación para continuar.')
            return redirect('admin_restaurar')

        if not backup_file:
            messages.error(request, 'Debe seleccionar un archivo de copia de seguridad.')
            return redirect('admin_restaurar')

        if not backup_file.name.endswith('.zip'):
            messages.error(request, 'Solo se aceptan archivos .zip generados por este sistema.')
            return redirect('admin_restaurar')

        db_backup_path = None
        try:
            import tempfile, shutil
            messages.info(request, '🔄 Iniciando restauración del sistema...')

            # Cargar archivo ZIP
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                for chunk in backup_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            with zipfile.ZipFile(tmp_path, 'r') as zf:
                nombres = zf.namelist()
                messages.info(request, f'✓ Archivo ZIP validado ({len(nombres)} archivos encontrados).')

                # Restaurar base de datos SQLite
                if 'db.sqlite3' in nombres:
                    db_path = str(settings.DATABASES['default']['NAME'])
                    db_backup_path = db_path + '.backup'

                    try:
                        messages.info(request, '🔒 Cerrando conexiones a la base de datos...')
                        # Cerrar todas las conexiones antes de reemplazar el archivo
                        from django.db import connections
                        connections.close_all()
                        messages.info(request, '✓ Conexiones cerradas correctamente.')

                        # Hacer backup del archivo actual
                        if os.path.exists(db_path):
                            messages.info(request, '💾 Creando backup de la BD actual...')
                            shutil.copy2(db_path, db_backup_path)
                            messages.info(request, '✓ Backup creado exitosamente.')

                        # Restaurar la base de datos
                        messages.info(request, '📥 Restaurando base de datos...')
                        with zf.open('db.sqlite3') as src, open(db_path, 'wb') as dst:
                            shutil.copyfileobj(src, dst)
                        messages.success(request, '✓ Base de datos restaurada correctamente.')

                        # Limpiar la caché de conexiones y resetear
                        from django.core.cache import cache
                        cache.clear()
                        messages.info(request, '✓ Caché limpiada.')
                    except Exception as db_error:
                        messages.error(request, f'❌ Error al restaurar BD: {str(db_error)}')
                        # Restaurar desde backup si algo falla
                        if os.path.exists(db_backup_path):
                            messages.info(request, '⚠️ Restaurando BD desde backup de seguridad...')
                            shutil.copy2(db_backup_path, db_path)
                            messages.warning(request, '⚠️ BD restaurada desde backup anterior. Intente de nuevo.')
                        raise Exception(f'Error al restaurar base de datos: {str(db_error)}')
                else:
                    messages.warning(request, '⚠️ No se encontró base de datos en la copia de seguridad.')

                # Restaurar archivos multimedia
                media_root = str(settings.MEDIA_ROOT)
                media_files = [n for n in nombres if n.startswith('media/')]

                if media_files:
                    messages.info(request, f'🗂️ Preparando restauración de {len(media_files)} archivos multimedia...')

                    if media_root and os.path.exists(media_root):
                        # Limpiar el directorio de media antes de restaurar
                        messages.info(request, '🗑️ Limpiando directorio multimedia...')
                        deleted_count = 0
                        for item in os.listdir(media_root):
                            item_path = os.path.join(media_root, item)
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                deleted_count += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                deleted_count += 1
                        messages.info(request, f'✓ {deleted_count} elemento(s) eliminado(s).')

                    messages.info(request, '📥 Extrayendo archivos multimedia...')
                    parent = os.path.dirname(media_root)
                    zf.extractall(parent, members=media_files)
                    messages.success(request, f'✓ {len(media_files)} archivo(s) multimedia restaurado(s).')
                else:
                    messages.info(request, '📁 No hay archivos multimedia en la copia de seguridad.')

            os.unlink(tmp_path)

            # Limpiar backups temporales de BD
            if db_backup_path and os.path.exists(db_backup_path):
                os.remove(db_backup_path)

            registrar_evento(request, 'ACTUALIZACION', f'Sistema restaurado desde copia: {backup_file.name}')
            messages.success(request, f'✅ ¡Sistema restaurado correctamente desde "{backup_file.name}"! Puede ser necesario reiniciar la aplicación para que los cambios tomen efecto.')
        except zipfile.BadZipFile:
            messages.error(request, '❌ El archivo seleccionado no es un ZIP válido.')
        except Exception as e:
            messages.error(request, f'❌ Error general en restauración: {str(e)}')

        return redirect('admin_restaurar')

    context = {
        'title': 'Restaurar Sistema',
        'backups': _list_backups(),
    }
    return render(request, 'admin/restaurar.html', context)


def _get_backup_dir():
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir

def _list_backups():
    backup_dir = _get_backup_dir()
    backups = []
    for fname in sorted(os.listdir(backup_dir), reverse=True):
        fpath = os.path.join(backup_dir, fname)
        if os.path.isfile(fpath) and fname.endswith('.zip'):
            stat = os.stat(fpath)
            size_kb = stat.st_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M')
            if fname.startswith('backup_full_'):
                tipo = 'Completa'
            elif fname.startswith('backup_db_'):
                tipo = 'Base de datos'
            else:
                tipo = 'Multimedia'
            backups.append({'nombre': fname, 'fecha': mtime, 'tipo': tipo, 'tamano': size_str})
    return backups


@login_required(login_url='/login/')
def admin_backup_view(request):
    """Vista de copia de seguridad"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')

    if request.method == 'POST':
        backup_type = request.POST.get('backup_type')
        if not backup_type:
            messages.error(request, 'Seleccione un tipo de copia.')
            return redirect('admin_backup')

        backup_dir = _get_backup_dir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix_map = {'full': 'backup_full', 'db': 'backup_db', 'media': 'backup_media'}
        prefix = prefix_map.get(backup_type, 'backup')
        zip_name = f"{prefix}_{timestamp}.zip"
        zip_path = os.path.join(backup_dir, zip_name)

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                if backup_type in ('full', 'db'):
                    db_path = str(settings.DATABASES['default']['NAME'])
                    if os.path.exists(db_path):
                        zf.write(db_path, 'db.sqlite3')
                if backup_type in ('full', 'media'):
                    media_root = str(settings.MEDIA_ROOT)
                    if os.path.exists(media_root):
                        for root, dirs, files in os.walk(media_root):
                            for file in files:
                                fp = os.path.join(root, file)
                                arcname = os.path.relpath(fp, os.path.dirname(media_root))
                                zf.write(fp, arcname)
            messages.success(request, f'Copia de seguridad generada correctamente: {zip_name}')
        except Exception as e:
            messages.error(request, f'Error al generar la copia: {str(e)}')
        return redirect('admin_backup')

    context = {
        'title': 'Copia de Seguridad',
        'backups': _list_backups(),
    }
    return render(request, 'admin/backup.html', context)


@login_required(login_url='/login/')
def admin_backup_download(request, filename):
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    backup_dir = _get_backup_dir()
    safe_name = os.path.basename(filename)
    file_path = os.path.join(backup_dir, safe_name)
    if not os.path.exists(file_path):
        messages.error(request, 'Archivo no encontrado.')
        return redirect('admin_backup')
    response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=safe_name)
    return response


@login_required(login_url='/login/')
def admin_backup_delete(request, filename):
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    if request.method == 'POST':
        backup_dir = _get_backup_dir()
        safe_name = os.path.basename(filename)
        file_path = os.path.join(backup_dir, safe_name)
        if os.path.exists(file_path):
            os.remove(file_path)
            messages.success(request, f'Copia "{safe_name}" eliminada.', extra_tags='deleted')
        else:
            messages.error(request, 'Archivo no encontrado.')
    return redirect('admin_backup')
