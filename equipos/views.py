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
    """API para obtener datos completos de un usuario para edición"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    try:
        user = User.objects.get(id=user_id)
        usuario_perfil, _ = Usuario.objects.get_or_create(Id_user=user)
        permisos = usuario_perfil.permisos
        data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'is_superuser': user.is_superuser,
            'permisos': {
                'crear': permisos.get('crear', False) if permisos else False,
                'actualizar': permisos.get('actualizar', False) if permisos else False,
                'eliminar': permisos.get('eliminar', False) if permisos else False,
            }
        }
    except User.DoesNotExist:
        data = {'error': 'Usuario no encontrado'}
    return JsonResponse(data)

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

    # Datos para gráfica de picos: subestaciones creadas por mes (últimos 12 meses)
    from datetime import date, timedelta

    hoy = date.today()
    year, month = hoy.year, hoy.month
    month -= 11
    while month <= 0:
        month += 12
        year -= 1
    inicio = date(year, month, 1)
    inicio_dia = date(hoy.year, hoy.month, 1)
    # Días del mes actual
    if hoy.month == 12:
        siguiente_mes = date(hoy.year + 1, 1, 1)
    else:
        siguiente_mes = date(hoy.year, hoy.month + 1, 1)
    dias_mes = (siguiente_mes - inicio_dia).days

    meses_es = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

    # Construir las etiquetas (eje X) una sola vez
    subs_chart_labels = []
    meses_keys = []
    y, mo = inicio.year, inicio.month
    for _ in range(12):
        subs_chart_labels.append(f"{meses_es[mo - 1]} {str(y)[-2:]}")
        meses_keys.append((y, mo))
        mo += 1
        if mo > 12:
            mo = 1
            y += 1

    subs_chart_dia_labels = []
    dias_keys = []
    for i in range(dias_mes):
        d = inicio_dia + timedelta(days=i)
        subs_chart_dia_labels.append(f"{d.day:02d}")
        dias_keys.append(d)

    def build_series(model):
        fechas = model.objects.filter(Fecha_Reg__gte=inicio).values_list('Fecha_Reg', flat=True)
        mes = {}
        dia = {}
        for f in fechas:
            if not f:
                continue
            mes[(f.year, f.month)] = mes.get((f.year, f.month), 0) + 1
            if f >= inicio_dia:
                dia[f] = dia.get(f, 0) + 1
        return ([mes.get(k, 0) for k in meses_keys],
                [dia.get(k, 0) for k in dias_keys])

    series_config = [
        ('subestaciones', 'Subestaciones', '#4DA6FF', Subestacion),
        ('reles',         'Relés',          '#00CC66', Rele),
        ('niveles',       'Niveles Tensión','#FFCC00', NivelTension),
        ('interfaces',    'Interfaces',     '#8844CC', InterfazDeComunicacion),
        ('protocolos',    'Protocolos',     '#FF3333', Protocolo),
        ('remotas',       'Remotas',        '#00CCCC', Remota),
    ]
    chart_series = []
    for key, label, color, model in series_config:
        mes_data, dia_data = build_series(model)
        chart_series.append({
            'key': key,
            'label': label,
            'color': color,
            'mes': mes_data,
            'dia': dia_data,
        })

    import json
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
        'subs_chart_labels': json.dumps(subs_chart_labels),
        'subs_chart_dia_labels': json.dumps(subs_chart_dia_labels),
        'chart_series': json.dumps(chart_series),
    }
    return render(request, 'index.html', context)

def admin_root_view(request):
    """Redirige /admin/ a /admin/inicio/"""
    if not request.user.is_authenticated:
        return redirect('user_login')
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta sección.')
        return redirect('index')
    return redirect('admin_index')

@no_cache
@login_required(login_url='/login/')
def perfil_view(request):
    """Vista de perfil de usuario"""
    if request.method == 'POST':
        user = request.user
        nuevo_email = (request.POST.get('email', user.email) or '').strip()
        # Validación: el correo no puede coincidir con el de otro usuario
        if nuevo_email and User.objects.filter(email__iexact=nuevo_email).exclude(id=user.id).exists():
            messages.error(request, 'Ya existe otro usuario con ese correo electrónico.')
            return redirect('perfil')
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = nuevo_email or user.email
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
            is_superuser = request.POST.get('is_superuser') == 'on'
            permisos = {
                'crear': request.POST.get('permiso_crear') == 'on',
                'actualizar': request.POST.get('permiso_actualizar') == 'on',
                'eliminar': request.POST.get('permiso_eliminar') == 'on',
            }
            # Validación: el correo no puede repetirse (si se proporcionó)
            email_n = (email or '').strip()
            if email_n and User.objects.filter(email__iexact=email_n).exists():
                messages.error(request, 'Ya existe un usuario con ese correo electrónico.')
                return redirect('admin_usuarios')
            # Validación: el nombre de usuario no puede repetirse
            if username and User.objects.filter(username__iexact=username).exists():
                messages.error(request, 'Ya existe un usuario con ese nombre de usuario.')
                return redirect('admin_usuarios')
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
            username = request.POST.get('username')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            email = request.POST.get('email', '')
            is_superuser = request.POST.get('is_superuser') == 'on'
            permisos = {
                'crear': request.POST.get('permiso_crear') == 'on',
                'actualizar': request.POST.get('permiso_actualizar') == 'on',
                'eliminar': request.POST.get('permiso_eliminar') == 'on',
            }
            # Validación: el correo no puede repetirse en otro usuario
            email_n = (email or '').strip()
            if email_n and User.objects.filter(email__iexact=email_n).exclude(id=user_id).exists():
                messages.error(request, 'Ya existe otro usuario con ese correo electrónico.')
                return redirect('admin_usuarios')
            # Validación: el nombre de usuario no puede repetirse en otro usuario
            if username and User.objects.filter(username__iexact=username).exclude(id=user_id).exists():
                messages.error(request, 'Ya existe otro usuario con ese nombre de usuario.')
                return redirect('admin_usuarios')
            try:
                user = User.objects.get(id=user_id)
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.is_superuser = is_superuser
                user.is_staff = is_superuser
                user.save()
                usuario_perfil, created = Usuario.objects.get_or_create(Id_user=user)
                usuario_perfil.permisos = permisos
                usuario_perfil.save()
                registrar_evento(request, 'ACTUALIZACION', f'Usuario actualizado: {user.username}')
                messages.success(request, 'Usuario actualizado correctamente.', extra_tags='updated')
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
            niveles_ids = request.POST.getlist('niveles_ten')
            ubicacion = request.POST.get('ubicacion')
            coordenadas = request.POST.get('coordenadas')
            try:
                sub = Subestacion.objects.get(Id_Sub_est=sub_id)
                # Validación de duplicado por nombre (case-insensitive, excluye el propio)
                if Subestacion.objects.filter(Nombre__iexact=(nombre or '').strip()).exclude(Id_Sub_est=sub_id).exists():
                    messages.error(request, 'Ya existe otra subestación con ese nombre.')
                    return redirect('subestaciones')
                if not niveles_ids:
                    messages.error(request, 'Debe seleccionar al menos un nivel de tensión.')
                    return redirect('subestaciones')
                niveles = list(NivelTension.objects.filter(Id_Ten__in=niveles_ids))
                if not niveles:
                    messages.error(request, 'Nivel de tension no valido.')
                    return redirect('subestaciones')
                sub.Nombre = nombre
                sub.Id_Ten = niveles[0]  # Primer nivel como principal (legacy)
                sub.Ubicación = ubicacion
                sub.Coordenadas = coordenadas
                sub.save()
                sub.Niveles_Ten.set(niveles)
                registrar_evento(request, 'ACTUALIZACION', f'Subestacion actualizada: {sub.Nombre}')
                messages.success(request, 'Subestacion actualizada correctamente.', extra_tags='updated')
            except Subestacion.DoesNotExist:
                messages.error(request, 'Subestacion no encontrada.')
            return redirect('subestaciones')
        else:
            if not puede_crear(request):
                messages.error(request, 'No tiene permisos para crear subestaciones.')
                return redirect('subestaciones')
            nombre = request.POST.get('nombre')
            niveles_ids = request.POST.getlist('niveles_ten')
            ubicacion = request.POST.get('ubicacion')
            coordenadas = request.POST.get('coordenadas')

            if nombre and niveles_ids:
                # Validación de duplicado por nombre (case-insensitive)
                if Subestacion.objects.filter(Nombre__iexact=nombre.strip()).exists():
                    messages.error(request, 'Ya existe una subestación con ese nombre.')
                    return redirect('subestaciones')
                niveles = list(NivelTension.objects.filter(Id_Ten__in=niveles_ids))
                if not niveles:
                    messages.error(request, 'Nivel de tension no valido.')
                    return redirect('subestaciones')
                sub = Subestacion.objects.create(
                    Nombre=nombre,
                    Id_Ten=niveles[0],  # Primer nivel como principal (legacy)
                    Ubicación=ubicacion,
                    Coordenadas=coordenadas,
                    creado_por=request.user
                )
                sub.Niveles_Ten.set(niveles)
                registrar_evento(request, 'CREACION', f'Subestacion creada: {sub.Nombre}')
                messages.success(request, 'Subestacion creada correctamente.')
                return redirect('subestaciones')
            else:
                messages.error(request, 'Debe indicar el nombre y al menos un nivel de tensión.')
                return redirect('subestaciones')
    
    subestaciones_list = Subestacion.objects.prefetch_related('Niveles_Ten').all().order_by('-Fecha_Reg', '-Id_Sub_est')
    paginator = Paginator(subestaciones_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    tensiones = NivelTension.objects.all().order_by('Nivel')
    
    context = {
        'title': 'Subestaciones',
        'page_obj': page_obj,
        'tensiones': tensiones,
        'is_admin': request.user.is_superuser,
        'puede_crear': puede_crear(request),
        'puede_actualizar': puede_actualizar(request),
        'puede_eliminar': puede_eliminar(request),
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
            # "Otro" (nivel personalizado): solo disponible para administradores.
            if nivel == '__otro__':
                if not request.user.is_superuser:
                    messages.error(request, 'Solo el administrador puede agregar un nivel personalizado.')
                    return redirect('tensiones')
                nivel = (request.POST.get('nivel_otro') or '').strip()
            if not (tipo_ten and nivel):
                messages.error(request, 'Datos incompletos.')
                return redirect('tensiones')
            # Validación de duplicado: misma combinación Tipo + Nivel
            if NivelTension.objects.filter(Tipo_ten=tipo_ten, Nivel=nivel).exists():
                messages.error(request, 'Ya existe un nivel de tensión con esa combinación de tipo y nivel.')
                return redirect('tensiones')
            ten = NivelTension.objects.create(
                Tipo_ten=tipo_ten,
                Nivel=nivel,
                creado_por=request.user
            )
            registrar_evento(request, 'CREACION', f'Nivel de tension creado: {ten.get_Tipo_ten_display()} {ten.get_Nivel_display()}')
            messages.success(request, 'Nivel de tensión creado correctamente.')
            return redirect('tensiones')
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('tensiones')
            ten_id = request.POST.get('ten_id')
            tipo_ten = request.POST.get('tipo_ten')
            nivel = request.POST.get('nivel')
            # "Otro" (nivel personalizado): solo disponible para administradores.
            if nivel == '__otro__':
                if not request.user.is_superuser:
                    messages.error(request, 'Solo el administrador puede agregar un nivel personalizado.')
                    return redirect('tensiones')
                nivel = (request.POST.get('nivel_otro') or '').strip()
            if not (tipo_ten and nivel):
                messages.error(request, 'Datos incompletos.')
                return redirect('tensiones')
            try:
                ten = NivelTension.objects.get(Id_Ten=ten_id)
                # Validación de duplicado (excluye el propio registro)
                if NivelTension.objects.filter(Tipo_ten=tipo_ten, Nivel=nivel).exclude(Id_Ten=ten_id).exists():
                    messages.error(request, 'Ya existe otro nivel de tensión con esa combinación de tipo y nivel.')
                    return redirect('tensiones')
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
    
    tensiones = NivelTension.objects.all().order_by('-Fecha_Reg', '-Id_Ten')
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
        'puede_crear': puede_crear(request),
        'puede_actualizar': puede_actualizar(request),
        'puede_eliminar': puede_eliminar(request),
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

                # Capturar tipos de puertos/protocolos hijos antes de eliminar
                tipos_puerto = [p.get_Tipo_display() for p in iface.puertos.all()]
                tipos_proto = [p.get_Tipo_display() for p in iface.protocolos.all()]
                tipos_display = tipos_puerto + tipos_proto

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

                    # Eliminación lógica: marcar como inactivo (y sus puertos/protocolos hijos)
                    iface.Activo = False
                    iface.save()
                    Protocolo.objects.filter(Id_Interfaz=iface).update(Activo=False)
                    etiqueta = ', '.join(tipos_display) if tipos_display else 'sin tipos'
                    noun = 'Interfaz de Comunicación eliminada' if len(tipos_display) <= 1 \
                        else 'Interfaces de Comunicación eliminadas'
                    registrar_evento(request, 'ELIMINACION', f'{noun}: {etiqueta}')
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
            # "Otro" (tipo personalizado): solo administradores.
            descripciones = {}
            iconos = {}
            if request.user.is_superuser:
                otro = (request.POST.get('tipo_otro') or '').strip().upper()
                if otro and otro not in tipos_puerto:
                    tipos_puerto.append(otro)
                    descripciones[otro] = (request.POST.get('tipo_otro_desc') or '').strip()
                    iconos[otro] = (request.POST.get('tipo_otro_icono') or '').strip()
            # Heredar descripción/ícono del catálogo personalizado para los tipos
            # OTRA seleccionados desde checkboxes (sin re-introducir el nombre).
            _stock = {c[0] for c in PuertoComunicacion.TIPO_CHOICES}
            for tipo in tipos_puerto:
                if tipo not in _stock and tipo not in descripciones:
                    tp = TipoPuertoPersonalizado.objects.filter(Tipo=tipo).first()
                    if tp:
                        descripciones[tipo] = tp.Descripcion
                        iconos[tipo] = tp.Icono
            # Validación: ningún tipo puede estar registrado en OTRA interfaz activa
            ya_registrados = set(PuertoComunicacion.objects.filter(
                Id_Interfaz__Tipo_Interfaz='PUERTOS', Id_Interfaz__Activo=True
            ).exclude(Id_Interfaz=iface_id).values_list('Tipo', flat=True))
            conflictos = [t for t in tipos_puerto if t in ya_registrados]
            if conflictos:
                messages.error(request, f'Estos puertos ya están registrados en otra interfaz: {", ".join(conflictos)}')
                return redirect('interfaces')
            try:
                with transaction.atomic():
                    iface = InterfazDeComunicacion.objects.select_for_update().get(Id_Interfaz=iface_id)
                    iface.puertos.all().delete()
                    for tipo in tipos_puerto:
                        PuertoComunicacion.objects.create(
                            Id_Interfaz=iface,
                            Tipo=tipo,
                            Descripcion=descripciones.get(tipo, ''),
                            Icono=iconos.get(tipo, ''),
                            creado_por=request.user
                        )
                        # Registrar en catálogo de tipos OTRA si no es estándar
                        if tipo not in _stock:
                            TipoPuertoPersonalizado.objects.update_or_create(
                                Tipo=tipo,
                                defaults={
                                    'Descripcion': descripciones.get(tipo, ''),
                                    'Icono': iconos.get(tipo, ''),
                                    'Activo': True,
                                    'creado_por': request.user,
                                },
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
            # "Otro" (tipo personalizado): solo administradores.
            descripciones = {}
            iconos = {}
            if request.user.is_superuser:
                otro = (request.POST.get('tipo_otro') or '').strip().upper()
                if otro and otro not in tipos_puerto:
                    tipos_puerto.append(otro)
                    descripciones[otro] = (request.POST.get('tipo_otro_desc') or '').strip()
                    iconos[otro] = (request.POST.get('tipo_otro_icono') or '').strip()
            # Heredar metadatos del catálogo para tipos OTRA seleccionados
            _stock = {c[0] for c in PuertoComunicacion.TIPO_CHOICES}
            for tipo in tipos_puerto:
                if tipo not in _stock and tipo not in descripciones:
                    tp = TipoPuertoPersonalizado.objects.filter(Tipo=tipo).first()
                    if tp:
                        descripciones[tipo] = tp.Descripcion
                        iconos[tipo] = tp.Icono
            if tipos_puerto:
                # Validación: ningún tipo puede estar ya registrado en otra interfaz activa
                ya_registrados = set(PuertoComunicacion.objects.filter(
                    Id_Interfaz__Tipo_Interfaz='PUERTOS', Id_Interfaz__Activo=True
                ).values_list('Tipo', flat=True))
                conflictos = [t for t in tipos_puerto if t in ya_registrados]
                if conflictos:
                    messages.error(request, f'Estos puertos ya están registrados: {", ".join(conflictos)}')
                    return redirect('interfaces')
                iface = InterfazDeComunicacion.objects.create(
                    Puertos_C=len(tipos_puerto),
                    Tipo_Interfaz='PUERTOS',
                    creado_por=request.user
                )
                for tipo in tipos_puerto:
                    PuertoComunicacion.objects.create(
                        Id_Interfaz=iface,
                        Tipo=tipo,
                        Descripcion=descripciones.get(tipo, ''),
                        Icono=iconos.get(tipo, ''),
                        creado_por=request.user
                    )
                    # Registrar en catálogo de tipos OTRA si no es estándar
                    if tipo not in _stock:
                        TipoPuertoPersonalizado.objects.update_or_create(
                            Tipo=tipo,
                            defaults={
                                'Descripcion': descripciones.get(tipo, ''),
                                'Icono': iconos.get(tipo, ''),
                                'Activo': True,
                                'creado_por': request.user,
                            },
                        )
                # Validar consistencia
                try:
                    iface.full_clean()
                except Exception as e:
                    messages.error(request, f'Error de validación: {str(e)}')
                    iface.delete()
                    return redirect('interfaces')
                tipos_display = [p.get_Tipo_display() for p in iface.puertos.all()]
                etiqueta = ', '.join(tipos_display) if tipos_display else 'sin tipos'
                noun = 'Interfaz de Comunicación creada' if len(tipos_display) <= 1 \
                    else 'Interfaces de Comunicación creadas'
                registrar_evento(request, 'CREACION', f'{noun}: {etiqueta}')
                messages.success(request, 'Interfaz creada correctamente')
                return redirect('interfaces')
    
    interfaces_list = InterfazDeComunicacion.objects.filter(Tipo_Interfaz='PUERTOS', Activo=True).prefetch_related('puertos').order_by('-Fecha_Reg', '-Id_Interfaz')
    paginator = Paginator(interfaces_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    puertos_tipos = PuertoComunicacion.TIPO_CHOICES

    # Tipos de puerto ya registrados en cualquier interfaz activa (para ocultar opciones)
    tipos_registrados = list(PuertoComunicacion.objects.filter(
        Id_Interfaz__Tipo_Interfaz='PUERTOS', Id_Interfaz__Activo=True
    ).values_list('Tipo', flat=True).distinct())

    # Catálogo de tipos OTRA personalizados (persistente, disponible para todos)
    tipos_personalizados = TipoPuertoPersonalizado.objects.filter(Activo=True).order_by('Tipo')

    context = {
        'title': 'Interfaz de Comunicacion',
        'page_obj': page_obj,
        'puertos_tipos': puertos_tipos,
        'tipos_registrados': tipos_registrados,
        'tipos_personalizados': tipos_personalizados,
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
            # "Otro" (protocolo personalizado): solo administradores.
            descripciones = {}
            iconos = {}
            if request.user.is_superuser:
                otro = (request.POST.get('tipo_otro') or '').strip().upper()
                if otro and otro not in tipos_protocolo:
                    tipos_protocolo.append(otro)
                    descripciones[otro] = (request.POST.get('tipo_otro_desc') or '').strip()
                    iconos[otro] = (request.POST.get('tipo_otro_icono') or '').strip()
            # Validación: ningún tipo puede estar ya registrado en otra interfaz activa
            ya_registrados = set(Protocolo.objects.filter(
                Activo=True, Id_Interfaz__Activo=True
            ).values_list('Tipo', flat=True))
            conflictos = [t for t in tipos_protocolo if t in ya_registrados]
            if conflictos:
                messages.error(request, f'Estos protocolos ya están registrados: {", ".join(conflictos)}')
                return redirect('protocolo')
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
                        Descripcion=descripciones.get(tipo, ''),
                        Icono=iconos.get(tipo, ''),
                        creado_por=request.user
                    )
                # Validar consistencia
                try:
                    interfaz.full_clean()
                except Exception as e:
                    messages.error(request, f'Error de validación: {str(e)}')
                    raise  # Rollback
            tipos_display = [p.get_Tipo_display() for p in interfaz.protocolos.all()]
            etiqueta = ', '.join(tipos_display) if tipos_display else 'sin tipos'
            noun = 'Protocolo de Telecontrol y Energía creado' if len(tipos_display) <= 1 \
                else 'Protocolos de Telecontrol y Energía creados'
            registrar_evento(request, 'CREACION', f'{noun}: {etiqueta}')
            messages.success(request, 'Interfaz creada correctamente')
        
        # Editar interfaz/protocolos
        elif request.POST.get('editar'):
            if not puede_actualizar(request):
                messages.error(request, 'No tiene permisos para realizar esta acción.')
                return redirect('protocolo')
            interfaz_id = request.POST.get('interfaz_id')
            tipos_protocolo = request.POST.getlist('tipos_protocolo')
            # "Otro" (protocolo personalizado): solo administradores.
            descripciones = {}
            iconos = {}
            if request.user.is_superuser:
                otro = (request.POST.get('tipo_otro') or '').strip().upper()
                if otro and otro not in tipos_protocolo:
                    tipos_protocolo.append(otro)
                    descripciones[otro] = (request.POST.get('tipo_otro_desc') or '').strip()
                    iconos[otro] = (request.POST.get('tipo_otro_icono') or '').strip()
            # Validación: ningún tipo puede estar registrado en OTRA interfaz activa
            ya_registrados = set(Protocolo.objects.filter(
                Activo=True, Id_Interfaz__Activo=True
            ).exclude(Id_Interfaz=interfaz_id).values_list('Tipo', flat=True))
            conflictos = [t for t in tipos_protocolo if t in ya_registrados]
            if conflictos:
                messages.error(request, f'Estos protocolos ya están registrados en otra interfaz: {", ".join(conflictos)}')
                return redirect('protocolo')
            try:
                with transaction.atomic():
                    interfaz = InterfazDeComunicacion.objects.select_for_update().get(Id_Interfaz=interfaz_id)
                    Protocolo.objects.filter(Id_Interfaz=interfaz).delete()
                    for tipo in tipos_protocolo:
                        Protocolo.objects.create(
                            Id_Interfaz=interfaz,
                            Tipo=tipo,
                            Descripcion=descripciones.get(tipo, ''),
                            Icono=iconos.get(tipo, ''),
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
                
                # Capturar los tipos de protocolos antes de eliminar para registrar evento
                tipos_display = [p.get_Tipo_display() for p in interfaz.protocolos.all()]

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

                    # Eliminación lógica de la interfaz y de sus protocolos hijos
                    interfaz.Activo = False
                    interfaz.save()
                    Protocolo.objects.filter(Id_Interfaz=interfaz).update(Activo=False)
                etiqueta = ', '.join(tipos_display) if tipos_display else 'sin tipos'
                noun = 'Protocolo de Telecontrol y Energía eliminado' if len(tipos_display) <= 1 \
                    else 'Protocolos de Telecontrol y Energía eliminados'
                registrar_evento(request, 'ELIMINACION', f'{noun}: {etiqueta}')
                messages.success(request, 'Protocolos de Telecontrol y Energía eliminados correctamente.', extra_tags='deleted')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada')
    
    interfaces = InterfazDeComunicacion.objects.filter(Tipo_Interfaz='PROTOCOLOS', Activo=True).prefetch_related('protocolos').all().order_by('-Fecha_Reg', '-Id_Interfaz')
    paginator = Paginator(interfaces, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Tipos de protocolo ya registrados en cualquier interfaz activa
    tipos_registrados = list(Protocolo.objects.filter(
        Activo=True, Id_Interfaz__Activo=True
    ).values_list('Tipo', flat=True).distinct())

    context = {
        'title': 'Protocolos',
        'page_obj': page_obj,
        'tipos_registrados': tipos_registrados,
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
            # Validación: marca+modelo+nivel no puede coincidir con otra remota
            # (marca+modelo pueden repetirse si el nivel es distinto)
            marca_n = (marca or '').strip()
            modelo_n = (modelo or '').strip()
            duplicada = Remota.objects.filter(
                Marca__iexact=marca_n, Modelo__iexact=modelo_n, Id_Ten_id=id_ten_id or None
            ).exclude(Id_Remota=remota_id).exists()
            if duplicada:
                messages.error(request, 'Ya existe otra remota con la misma marca, modelo y nivel de tensión.')
                return redirect('remotas')
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
                # Validación: marca+modelo pueden repetirse, pero no junto con el mismo nivel
                marca_n = marca.strip()
                modelo_n = modelo.strip()
                duplicada = Remota.objects.filter(
                    Marca__iexact=marca_n, Modelo__iexact=modelo_n, Id_Ten_id=id_ten_id or None
                ).exists()
                if duplicada:
                    messages.error(request, 'Ya existe una remota con la misma marca, modelo y nivel de tensión.')
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
    
    remotas_list = Remota.objects.all().order_by('-Fecha_Reg', '-Id_Remota')
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

def _extract_puerto_ips(post, puertos_list):
    """Extrae {puerto_id: ip} para puertos ETH seleccionados.
    Si un puerto ETH está seleccionado pero no hay IP en el POST (o está vacía),
    se guarda '0.0.0.0' por defecto.
    """
    ips = {}
    selected = [str(p) for p in puertos_list]

    # IPs explícitas del formulario
    for key, value in post.items():
        if not key.startswith('puerto_ip_'):
            continue
        pid = key[len('puerto_ip_'):]
        if pid not in selected:
            continue
        ips[pid] = (value or '').strip() or '0.0.0.0'

    # Asegurar default 0.0.0.0 para todos los puertos ETH seleccionados
    eth_ids = PuertoComunicacion.objects.filter(
        Id_Puerto__in=selected, Tipo='ETH'
    ).values_list('Id_Puerto', flat=True)
    for pid in eth_ids:
        ips.setdefault(str(pid), '0.0.0.0')

    return ips


def _extract_remota_ips(post, puerto_keys):
    """Extrae {iface_id_puerto_id: ip} para los puertos ETH de la remota
    seleccionados (claves 'iface_puerto'). Si un puerto ETH está seleccionado
    y no hay IP en el POST, se guarda '0.0.0.0' por defecto.
    """
    ips = {}
    selected = set(str(k) for k in puerto_keys)

    # IDs de puerto seleccionados (segunda parte de cada clave)
    puerto_ids = [k.split('_', 1)[1] for k in selected if '_' in k]
    eth_puerto_ids = set(
        str(p) for p in PuertoComunicacion.objects.filter(
            Id_Puerto__in=puerto_ids, Tipo='ETH'
        ).values_list('Id_Puerto', flat=True)
    )

    # IPs explícitas del formulario (solo para claves seleccionadas)
    for key, value in post.items():
        if not key.startswith('remota_ip_'):
            continue
        rest = key[len('remota_ip_'):]
        if rest not in selected:
            continue
        ips[rest] = (value or '').strip() or '0.0.0.0'

    # Default 0.0.0.0 para cada puerto ETH seleccionado sin IP
    for key in selected:
        if '_' not in key:
            continue
        puerto_id = key.split('_', 1)[1]
        if puerto_id in eth_puerto_ids:
            ips.setdefault(key, '0.0.0.0')

    return ips


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
            # Claves de puerto seleccionadas ('iface_puerto'). Para relés antiguos
            # sin selección a nivel de puerto, derivar de las interfaces asociadas.
            remota_puertos_sel = list(rele.Remota_Puertos or [])
            if not remota_puertos_sel:
                for iface in remota.Interfaces.all():
                    for puerto in iface.puertos.all():
                        remota_puertos_sel.append(f'{iface.Id_Interfaz}_{puerto.Id_Puerto}')
            remota_data = {
                'remota_id': remota.Id_Remota,
                'remota_marca': remota.Marca,
                'remota_modelo': remota.Modelo,
                'remota_id_ten': remota.Id_Ten.Id_Ten if remota.Id_Ten else None,
                'remota_niveles': list(remota.Niveles_Ten.values_list('Id_Ten', flat=True)),
                'remota_protocolos': list(remota.Protocolos.values_list('Id_Protocolo', flat=True)),
                'remota_puertos_sel': remota_puertos_sel,
            }
        
        # Validar IDs contra la BD para evitar referencias huérfanas (D6)
        valid_protocolo_ids = set(Protocolo.objects.values_list('Id_Protocolo', flat=True))
        valid_puerto_ids = set(PuertoComunicacion.objects.values_list('Id_Puerto', flat=True))
        
        data = {
            'id_sub_est': rele.Id_Sub_est.Id_Sub_est,
            'id_ten': rele.Id_Ten.Id_Ten if rele.Id_Ten else None,
            'marca': rele.Marca,
            'modelo': rele.Modelo,
            'estado': rele.Estado,
            'observaciones': rele.Observaciones or '',
            'es_remoto': rele.EsRemoto,
            'imagen_url': rele.Imagen.url if rele.Imagen else None,
            'protocolos': [pid for pid in rele.Protocolos.values_list('Id_Protocolo', flat=True) if pid in valid_protocolo_ids],
            'puertos': [pid for pid in rele.Puertos.values_list('Id_Puerto', flat=True) if pid in valid_puerto_ids],
            'puertos_ips': rele.Puertos_IPs or {},
            'remota_ips': rele.Remota_IPs or {},
            'entradas_digitales': rele.Entradas_Digitales,
            'salidas_digitales': rele.Salidas_Digitales,
            'entradas_analogicas': rele.Entradas_Analogicas,
            'contadores': rele.Contadores,
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
                    sub_nombre = rele.Id_Sub_est.Nombre if rele.Id_Sub_est else 'sin subestación'
                    rele.delete()
                    registrar_evento(request, 'ELIMINACION', f'Relé eliminado: {sub_nombre}')
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
            print(f"  remota_puerto_sel: {request.POST.getlist('remota_puerto_sel')}", file=sys.stderr)
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
                    rele.Entradas_Digitales = int(request.POST.get('entradas_digitales') or 0)
                    rele.Salidas_Digitales = int(request.POST.get('salidas_digitales') or 0)
                    rele.Entradas_Analogicas = int(request.POST.get('entradas_analogicas') or 0)
                    rele.Contadores = int(request.POST.get('contadores') or 0)
                    
                    if request.FILES.get('imagen'):
                        rele.Imagen = request.FILES.get('imagen')
                    
                    # M2M assignments on Rele
                    protocolos_list = request.POST.getlist('protocolos')
                    puertos_list = request.POST.getlist('puertos')
                    print(f"DEBUG: Assigning Protocolos to Rele: {protocolos_list}", file=sys.stderr)
                    print(f"DEBUG: Assigning Puertos to Rele: {puertos_list}", file=sys.stderr)
                    rele.Protocolos.set(protocolos_list)
                    rele.Puertos.set(puertos_list)

                    # Persist per-puerto IPs (only for selected ETH puertos)
                    rele.Puertos_IPs = _extract_puerto_ips(request.POST, puertos_list)

                    # Handle remote association and remote M2M
                    es_remoto = request.POST.get('es_remoto') == 'si'
                    rele.EsRemoto = es_remoto

                    if es_remoto and request.POST.get('remota_id'):
                        remota = Remota.objects.get(Id_Remota=request.POST.get('remota_id'))
                        rele.Remota = remota

                        # Update Remota's M2M fields
                        remota_niveles = request.POST.getlist('remota_nivel_tension')
                        remota_protocolos = request.POST.getlist('remota_protocolos')
                        # Selección a nivel de puerto: claves 'iface_puerto'
                        remota_puerto_keys = request.POST.getlist('remota_puerto_sel')
                        remota_interfaces = list({k.split('_', 1)[0] for k in remota_puerto_keys if '_' in k})

                        remota.Niveles_Ten.set(remota_niveles)
                        remota.Protocolos.set(remota_protocolos)
                        remota.Interfaces.set(remota_interfaces)
                        remota.save()

                        rele.Remota_Puertos = remota_puerto_keys
                        rele.Remota_IPs = _extract_remota_ips(request.POST, remota_puerto_keys)
                    elif es_remoto:
                        # EsRemoto=True pero falta remota_id en el POST: conservar
                        # la asociación previa para no perder datos silenciosamente.
                        print(f"DEBUG: es_remoto=True sin remota_id; conservando Remota previa", file=sys.stderr)
                    else:
                        # Clear remote association if unchecked
                        rele.Remota = None
                        rele.Remota_IPs = {}
                        rele.Remota_Puertos = []

                    rele.save()
                    print(f"DEBUG: Rele {rele_id} saved successfully. EsRemoto={es_remoto}", file=sys.stderr)
                    registrar_evento(request, 'ACTUALIZACION', f'Relé actualizado: {rele.Id_Sub_est.Nombre}')
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
                        Entradas_Digitales=int(request.POST.get('entradas_digitales') or 0),
                        Salidas_Digitales=int(request.POST.get('salidas_digitales') or 0),
                        Entradas_Analogicas=int(request.POST.get('entradas_analogicas') or 0),
                        Contadores=int(request.POST.get('contadores') or 0),
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

                    rele.Puertos_IPs = _extract_puerto_ips(request.POST, puertos_list)

                    # Handle remote association and remote M2M
                    es_remoto = request.POST.get('es_remoto') == 'si'
                    rele.EsRemoto = es_remoto

                    if es_remoto and request.POST.get('remota_id'):
                        remota = Remota.objects.get(Id_Remota=request.POST.get('remota_id'))
                        rele.Remota = remota

                        # Update Remota's M2M fields
                        remota_niveles = request.POST.getlist('remota_nivel_tension')
                        remota_protocolos = request.POST.getlist('remota_protocolos')
                        # Selección a nivel de puerto: claves 'iface_puerto'
                        remota_puerto_keys = request.POST.getlist('remota_puerto_sel')
                        remota_interfaces = list({k.split('_', 1)[0] for k in remota_puerto_keys if '_' in k})

                        remota.Niveles_Ten.set(remota_niveles)
                        remota.Protocolos.set(remota_protocolos)
                        remota.Interfaces.set(remota_interfaces)
                        remota.save()

                        rele.Remota_Puertos = remota_puerto_keys
                        rele.Remota_IPs = _extract_remota_ips(request.POST, remota_puerto_keys)

                    rele.save()
                    print(f"DEBUG: Rele created. EsRemoto={es_remoto}, Remota_id={request.POST.get('remota_id')}", file=sys.stderr)
                    
                    registrar_evento(request, 'CREACION', f'Relé creado: {sub.Nombre}')
                    messages.success(request, 'Relé creado correctamente.')
                    return redirect('reles')
            except (Subestacion.DoesNotExist, NivelTension.DoesNotExist, Remota.DoesNotExist) as e:
                print(f"DEBUG CREATE ERROR: {str(e)}", file=sys.stderr)
                messages.error(request, f'Error al crear: {str(e)}')
                return redirect('reles')
    elif request.method == 'GET':
        # GET: mostrar lista
        rele_list = Rele.objects.all().order_by('-Fecha_Reg', '-Id_relé')
        paginator = Paginator(rele_list, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Obtener valores únicos para evitar duplicados en los formularios
        subestaciones = Subestacion.objects.select_related('Id_Ten').all().order_by('Nombre')
        tensiones = list(NivelTension.objects.all().order_by('Nivel'))
        
        # Protocolos únicos por tipo: solo activos y con interfaz padre activa.
        # Los protocolos sin interfaz (Id_Interfaz=None) se consideran huérfanos.
        protocolos_dict = {}
        protocolos_qs = Protocolo.objects.filter(
            Activo=True, Id_Interfaz__isnull=False, Id_Interfaz__Activo=True
        ).order_by('Tipo')
        for p in protocolos_qs:
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

    # Para Remota: aplanar y deduplicar puertos por Tipo.
    # Para ETH se conservan todos los puertos distintos (mantienen su IP propia),
    # pero deduplicados por la clave (iface_id, puerto_id).
    remota_puertos_unicos = []
    if rele.Remota_id and rele.EsRemoto:
        # Construir la lista de pares (iface_id, puerto_id) a mostrar.
        # Se usa la selección a nivel de puerto guardada en Remota_Puertos;
        # para relés antiguos sin ese dato, se deriva de las interfaces (compat).
        pares = []
        if rele.Remota_Puertos:
            for clave in rele.Remota_Puertos:
                if '_' in clave:
                    iface_id, puerto_id = clave.split('_', 1)
                    pares.append((iface_id, puerto_id))
        else:
            for iface in rele.Remota.Interfaces.all():
                for puerto in iface.puertos.all():
                    pares.append((str(iface.Id_Interfaz), str(puerto.Id_Puerto)))

        # Resolver los puertos en lote
        puerto_ids = [pid for _, pid in pares]
        puertos_map = {
            str(p.Id_Puerto): p
            for p in PuertoComunicacion.objects.filter(Id_Puerto__in=puerto_ids)
        }

        seen_non_eth = set()
        seen_eth_keys = set()
        for iface_id, puerto_id in pares:
            puerto = puertos_map.get(str(puerto_id))
            if not puerto:
                continue
            if puerto.Tipo == 'ETH':
                key = (iface_id, puerto_id)
                if key in seen_eth_keys:
                    continue
                seen_eth_keys.add(key)
                ipkey = f'{iface_id}_{puerto_id}'
                ip = (rele.Remota_IPs or {}).get(ipkey) or '0.0.0.0'
                remota_puertos_unicos.append({
                    'tipo': puerto.Tipo,
                    'tipo_display': puerto.get_Tipo_display(),
                    'is_eth': True,
                    'ip': ip,
                })
            else:
                if puerto.Tipo in seen_non_eth:
                    continue
                seen_non_eth.add(puerto.Tipo)
                remota_puertos_unicos.append({
                    'tipo': puerto.Tipo,
                    'tipo_display': puerto.get_Tipo_display(),
                    'is_eth': False,
                    'ip': None,
                })

    if request.GET.get('modal') == '1':
        return render(request, 'rele_detalle_partial.html', {
            'rele': rele,
            'remota_puertos_unicos': remota_puertos_unicos,
        })

    context = {
        'title': f'Detalle de Relé {rele.Id_relé}',
        'rele': rele,
        'remota_puertos_unicos': remota_puertos_unicos,
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
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO
    from django.http import FileResponse


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    elements = []
    styles = getSampleStyleSheet()
    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.6*inch, height=0.6*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
               ParagraphStyle('corp', parent=styles['Normal'], fontSize=12, leading=14))]],
            colWidths=[0.7*inch, 1.5*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=12))
    title_p = Paragraph('<b>Niveles de Tensión Registrados</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=14, leading=17, alignment=1))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=styles['Normal'],
                                       fontSize=8, leading=10, alignment=2,
                                       textColor=colors.HexColor('#555555')))
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[2.3*inch, 2.8*inch, 2.0*inch])
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

    tensiones = NivelTension.objects.all().order_by('-Fecha_Reg', '-Id_Ten')
    _pw = letter[0] - 50
    _ratios = [1.5, 1.5, 1.8, 1.2]
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    data = [[Paragraph(f'<b>{h}</b>', hdr_st) for h in ['Tipo', 'Nivel (kV)', 'Creado Por', 'Fecha Registro']]]
    for tension in tensiones:
        if tension.creado_por:
            creado_por = tension.creado_por.get_full_name() or tension.creado_por.username
        else:
            creado_por = 'Sistema'
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

@login_required(login_url='/login/')
def exportar_interfaces_pdf(request):
    """Exporta todas las interfaces a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
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
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[1.8*inch, 3.2*inch, 2.1*inch])
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

    interfaces = InterfazDeComunicacion.objects.filter(Activo=True).prefetch_related('puertos').all().order_by('-Fecha_Reg', '-Id_Interfaz')
    interfaces = [i for i in interfaces if i.puertos.exists()]
    _pw = letter[0] - 50
    _ratios = [2.2, 1.5, 1.3]
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

@login_required(login_url='/login/')
def exportar_protocolo_pdf(request):
    """Exporta todos los protocolos a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
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
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[1.8*inch, 3.2*inch, 2.1*inch])
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
    # Iterar interfaces de PROTOCOLOS ordenadas por más recientes primero,
    # para que el PDF coincida con la tabla de la vista.
    interfaces_proto = InterfazDeComunicacion.objects.filter(
        Tipo_Interfaz='PROTOCOLOS', Activo=True
    ).prefetch_related('protocolos').order_by('-Fecha_Reg', '-Id_Interfaz')
    for iface in interfaces_proto:
        protos = list(iface.protocolos.all().order_by('Tipo'))
        if not protos:
            continue
        protocolos_por_interfaz[iface.Id_Interfaz] = [p.get_Tipo_display() for p in protos]
        creado_por_por_interfaz[iface.Id_Interfaz] = iface.creado_por.username if iface.creado_por else 'Sistema'
        fecha_por_interfaz[iface.Id_Interfaz] = iface.Fecha_Reg.strftime('%d/%m/%Y') if iface.Fecha_Reg else ''
    _pw = letter[0] - 50
    _ratios = [2.0, 1.5, 1.5]
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

@login_required(login_url='/login/')
def exportar_subestaciones_pdf(request):
    """Exporta todas las subestaciones a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
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
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[1.8*inch, 3.2*inch, 2.1*inch])
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

    subestaciones = Subestacion.objects.select_related('Id_Ten').prefetch_related('Niveles_Ten').all().order_by('-Fecha_Reg', '-Id_Sub_est')
    _pw = letter[0] - 50
    _ratios = [1.3, 1.3, 1.7, 1.2, 1.3, 1.3]
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=8, leading=10, alignment=1)
    data = [[Paragraph(f'<b>{h}</b>', hdr_st)
             for h in ['Nombre', 'Ubicación', 'Niveles de Tensión', 'Coordenadas', 'Creado Por', 'Fecha de Registro']]]
    for sub in subestaciones:
        niveles_list = list(sub.Niveles_Ten.all()) or ([sub.Id_Ten] if sub.Id_Ten else [])
        nivel     = '<br/>'.join(f"{n.get_Tipo_ten_display()} - {n.get_Nivel_display()}" for n in niveles_list) or '—'
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

@login_required(login_url='/login/')
def exportar_remotas_pdf(request):
    """Exporta todas las remotas a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
    from reportlab.lib.units import inch
    from io import BytesIO


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
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
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[1.8*inch, 3.2*inch, 2.1*inch])
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

    remotas = Remota.objects.select_related('Id_Ten').all().order_by('-Fecha_Reg', '-Id_Remota')
    _pw = letter[0] - 50
    _ratios = [1.3, 1.3, 1.8, 1.3, 1.3]
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
    """Exporta todos los relés a PDF con estilo similar al modal de detalle."""
    from ._reles_pdf_helper import build_reles_pdf
    reles = (Rele.objects
             .select_related('Id_Ten', 'Id_Sub_est', 'creado_por', 'Remota', 'Remota__Id_Ten')
             .prefetch_related('Protocolos', 'Puertos',
                               'Remota__Protocolos', 'Remota__Interfaces__puertos')
             .order_by('-Fecha_Reg', '-Id_relé'))
    return build_reles_pdf(reles)


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
    # Si no se resolvió el nombre de la URL, derivarlo del primer segmento de la
    # ruta (p. ej. "/protocolo/" -> "protocolo") para no guardar la ruta con "/".
    if not url_name:
        url_name = (request.path or '').strip('/').split('/')[0]
    vista = _VISTA_NOMBRES.get(url_name, url_name.replace('_', ' ').title() if url_name else 'Inicio')
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
    subestacion_filtro = request.GET.get('subestacion', '')
    mes_filtro = request.GET.get('mes', '')
    anio_filtro = request.GET.get('anio', '')

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

    # Filtro por subestación (busca en descripción o vista)
    if subestacion_filtro:
        eventos_list = eventos_list.filter(
            Q(Descripcion__icontains=subestacion_filtro) |
            Q(Vista__icontains=subestacion_filtro)
        )

    # Filtro por mes y año
    from django.utils import timezone
    
    if anio_filtro:
        try:
            anio = int(anio_filtro)
            eventos_list = eventos_list.filter(Fecha_Hora__year=anio)
        except ValueError:
            pass
    
    if mes_filtro:
        try:
            mes = int(mes_filtro)
            eventos_list = eventos_list.filter(Fecha_Hora__month=mes)
        except ValueError:
            pass

    paginator = Paginator(eventos_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Obtener lista de subestaciones para el filtro
    subestaciones = Subestacion.objects.values_list('Nombre', flat=True).distinct()
    
    # Generar años disponibles para filtro
    current_year = timezone.now().year
    anios = range(current_year, current_year - 5, -1)
    
    # Meses para filtro
    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]

    context = {
        'title': 'Bitácora de Eventos',
        'page_obj': page_obj,
        'is_admin': request.user.is_superuser,
        'tipo_usuario': tipo_usuario,
        'busqueda': busqueda,
        'subestacion_filtro': subestacion_filtro,
        'mes_filtro': mes_filtro,
        'anio_filtro': anio_filtro,
        'subestaciones': subestaciones,
        'meses': meses,
        'anios': anios,
    }
    return render(request, 'bitacora.html', context)


@login_required(login_url='/login/')
def exportar_bitacora_pdf(request):
    """Exporta los eventos de la bitácora a PDF (aplicando filtros si existen)"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image, PageBreak
    from reportlab.lib.units import inch
    from io import BytesIO
    from django.http import FileResponse

    # Obtener filtros de la query
    tipo_usuario = request.GET.get('tipo_usuario', '')
    busqueda = request.GET.get('q', '')
    subestacion_filtro = request.GET.get('subestacion', '')
    mes_filtro = request.GET.get('mes', '')
    anio_filtro = request.GET.get('anio', '')

    # Aplicar los mismos filtros que en bitacora_view
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

    if subestacion_filtro:
        eventos_list = eventos_list.filter(
            Q(Descripcion__icontains=subestacion_filtro) |
            Q(Vista__icontains=subestacion_filtro)
        )

    from django.utils import timezone
    if anio_filtro:
        try:
            anio = int(anio_filtro)
            eventos_list = eventos_list.filter(Fecha_Hora__year=anio)
        except ValueError:
            pass

    if mes_filtro:
        try:
            mes = int(mes_filtro)
            eventos_list = eventos_list.filter(Fecha_Hora__month=mes)
        except ValueError:
            pass

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    NAVY   = colors.HexColor('#1c2e4a')
    RED    = colors.HexColor('#ED1C24')
    GREY_L = colors.HexColor('#f5f5f5')
    GREY_B = colors.HexColor('#cccccc')
    # Colores alternados para filas
    ROW_COLORS = [colors.white, GREY_L]

    logo_path = find('img/logo_corpoelec.png') or find('img/logo.jpg')
    if logo_path:
        logo_img = Image(logo_path, width=0.6*inch, height=0.6*inch)
        logo_cell = Table(
            [[logo_img, Paragraph('<b>CORPOELEC</b>',
                   ParagraphStyle('corp', parent=styles['Normal'], fontSize=11, leading=13))]],
            colWidths=[0.7*inch, 1.2*inch])
        logo_cell.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_cell = Paragraph('<b>CORPOELEC</b>',
                              ParagraphStyle('corp', parent=styles['Normal'], fontSize=11))
    title_p = Paragraph('<b>Registro de Eventos</b>',
                        ParagraphStyle('title', parent=styles['Normal'],
                                       fontSize=13, leading=15, alignment=1))
    date_p  = Paragraph(f'Reporte Generado:<br/>{datetime.now().strftime("%d/%m/%Y %H:%M")}',
                        ParagraphStyle('date', parent=styles['Normal'],
                                       fontSize=7, leading=9, alignment=2,
                                       textColor=colors.HexColor('#555555')))
    hdr = Table([[logo_cell, title_p, date_p]], colWidths=[1.9*inch, 3.2*inch, 1.8*inch])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(hdr)
    elements.append(Spacer(1, 4))  # Reduced spacer
    elements.append(HRFlowable(width="100%", thickness=1, color=RED, spaceBefore=0, spaceAfter=6))

    # Configuración de tabla - máximo 18 filas por página para mejor distribución y legibilidad
    MAX_ROWS_PER_PAGE = 18
    _pw = letter[0] - 60  # Adjusted for increased margins
    _ratios = [1.0, 0.8, 1.3, 1.8, 2.5, 1.8]  # Reduced Fecha/Hora, increased Vista/Acción, kept Descripción
    col_w = [_pw * r / sum(_ratios) for r in _ratios]
    
    # Estilos optimizados para mejor legibilidad y distribución con espacio adecuado
    hdr_st  = ParagraphStyle('h', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.white, alignment=1)
    cell_st = ParagraphStyle('c', parent=styles['Normal'], fontSize=9, leading=12, alignment=1)

    # Dividir eventos en grupos de MAX_ROWS_PER_PAGE
    eventos = list(eventos_list)
    
    for page_idx in range(0, len(eventos), MAX_ROWS_PER_PAGE):
        page_events = eventos[page_idx:page_idx + MAX_ROWS_PER_PAGE]
        
        # Encabezados de tabla
        data = [[Paragraph(f'<b>{h}</b>', hdr_st) for h in ['Fecha', 'Hora', 'Usuario', 'Vista', 'Descripción', 'Acción']]]
        
        for evento in page_events:
            fecha = evento.Fecha_Hora.strftime('%d/%m/%Y') if evento.Fecha_Hora else ''
            hora = evento.Fecha_Hora.strftime('%H:%M:%S') if evento.Fecha_Hora else ''
            usuario = evento.Usuario.username if evento.Usuario else 'Sistema'
            vista = evento.Vista or ''
            desc = evento.Descripcion[:40] + '...' if len(evento.Descripcion) > 40 else evento.Descripcion
            tipo = evento.get_Tipo_display()
            data.append([Paragraph(fecha, cell_st), Paragraph(hora, cell_st), Paragraph(usuario, cell_st),
                         Paragraph(vista, cell_st), Paragraph(desc, cell_st), Paragraph(tipo, cell_st)])

        table = Table(data, colWidths=col_w, repeatRows=1)
        table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('TOPPADDING',    (0, 0), (-1, 0),  8),
            ('BOTTOMPADDING', (0, 0), (-1, 0),  8),
            ('INNERGRID',     (0, 0), (-1, 0),  0,   NAVY),
            ('BOX',           (0, 0), (-1, 0),  0,   NAVY),
            ('LINEBELOW',     (0, 0), (-1, 0),  1.0, colors.white),
            # Data rows styling - uniform row heights and compact padding
            ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 1), (-1, -1), 9),
            ('TOPPADDING',    (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), ROW_COLORS),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.3, GREY_B),
            ('LINEBEFORE',    (0, 1), (0,  -1), 0.3, GREY_B),
            ('LINEAFTER',     (-1, 1), (-1, -1), 0.3, GREY_B),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(table)
        
        # Agregar salto de página si hay más datos
        if page_idx + MAX_ROWS_PER_PAGE < len(eventos):
            elements.append(PageBreak())

    # Footer
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_B))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'Corporación Eléctrica Nacional S.A. — Documento de carácter oficial',
        ParagraphStyle('foot', parent=styles['Normal'], fontSize=7.5, leading=9,
                       alignment=1, textColor=colors.HexColor('#666666'))))
    doc.build(elements)

    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'bitacora_{datetime.now().strftime("%Y%m%d")}.pdf')


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
            # Cargar archivo ZIP
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                for chunk in backup_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            with zipfile.ZipFile(tmp_path, 'r') as zf:
                nombres = zf.namelist()

                # Restaurar base de datos SQLite
                if 'db.sqlite3' in nombres:
                    db_path = str(settings.DATABASES['default']['NAME'])
                    db_backup_path = db_path + '.backup'

                    try:
                        # Cerrar todas las conexiones antes de reemplazar el archivo
                        from django.db import connections
                        connections.close_all()

                        # Hacer backup del archivo actual
                        if os.path.exists(db_path):
                            shutil.copy2(db_path, db_backup_path)

                        # Restaurar la base de datos
                        with zf.open('db.sqlite3') as src, open(db_path, 'wb') as dst:
                            shutil.copyfileobj(src, dst)

                        # Limpiar la caché de conexiones y resetear
                        from django.core.cache import cache
                        cache.clear()
                    except Exception as db_error:
                        # Restaurar desde backup si algo falla
                        if os.path.exists(db_backup_path):
                            shutil.copy2(db_backup_path, db_path)
                        raise Exception(f'Error al restaurar base de datos: {str(db_error)}')
                # Restaurar archivos multimedia
                media_root = str(settings.MEDIA_ROOT)
                media_files = [n for n in nombres if n.startswith('media/')]

                if media_files:
                    if media_root and os.path.exists(media_root):
                        deleted_count = 0
                        for item in os.listdir(media_root):
                            item_path = os.path.join(media_root, item)
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                deleted_count += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                deleted_count += 1

                    parent = os.path.dirname(media_root)
                    zf.extractall(parent, members=media_files)
                else:
                    pass

            os.unlink(tmp_path)

            # Limpiar backups temporales de BD
            if db_backup_path and os.path.exists(db_backup_path):
                os.remove(db_backup_path)

            registrar_evento(request, 'ACTUALIZACION', f'Sistema restaurado desde copia: {backup_file.name}')
            messages.success(request, f'✅ Sistema restaurado correctamente desde "{backup_file.name}".', extra_tags='restore-redirect')
        except zipfile.BadZipFile:
            messages.error(request, '❌ El archivo seleccionado no es un ZIP válido.')
        except Exception as e:
            messages.error(request, f'❌ Error general en restauración: {str(e)}')

        return redirect('index')

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
