# -*- coding: utf-8 -*-
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.paginator import Paginator
from .models import *
import json
from datetime import datetime

@login_required(login_url='/login/')
def index_view(request):
    """Vista principal del dashboard"""
    total_reconectadores = Reconectador.objects.count() or 0
    total_reles = Rele.objects.count() or 0
    total_subestaciones = Subestacion.objects.count() or 0
    total_remotas = Remota.objects.count() or 0
    total_interfaces = InterfazDeComunicacion.objects.count() or 0
    total_protocolos = Protocolo.objects.count() or 0
    total_tensiones = NivelTension.objects.count() or 0

    ultimos_reconectadores = list(Reconectador.objects.all().order_by('-Fecha_Reg')[:5]) if total_reconectadores > 0 else []
    ultimos_reles = list(Rele.objects.all().order_by('-Fecha_Reg')[:5]) if total_reles > 0 else []
    
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
    }
    return render(request, 'index.html', context)

@login_required(login_url='/login/')
def perfil_view(request):
    """Vista de perfil de usuario"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('perfil')
    
    context = {
        'title': 'Mi Perfil',
        'user': request.user
    }
    return render(request, 'perfil.html', context)

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

@login_required(login_url='/login/')
def usuarios_view(request):
    """Vista de gestion de usuarios"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')
    
    usuarios = User.objects.all().order_by('-date_joined')
    
    context = {
        'title': 'Gestion de Usuarios',
        'usuarios': usuarios
    }
    return render(request, 'usuarios.html', context)

@login_required(login_url='/login/')
def subestaciones_view(request):
    """Vista de subestaciones"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            sub_id = request.POST.get('subestacion_id')
            try:
                sub = Subestacion.objects.get(Id_Sub_est=sub_id)
                sub.delete()
                messages.success(request, 'Subestacion eliminada correctamente.')
            except Subestacion.DoesNotExist:
                messages.error(request, 'Subestacion no encontrada.')
            return redirect('subestaciones')
        else:
            nombre = request.POST.get('nombre')
            id_ten_id = request.POST.get('id_ten')
            ubicacion = request.POST.get('ubicacion')
            coordenadas = request.POST.get('coordenadas')
            
            if nombre and id_ten_id:
                try:
                    id_ten = NivelTension.objects.get(Id_Ten=id_ten_id)
                    Subestacion.objects.create(
                        Nombre=nombre,
                        Id_Ten=id_ten,
                        Ubicacion=ubicacion,
                        Coordenadas=coordenadas,
                        creado_por=request.user
                    )
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

@login_required(login_url='/login/')
def tensiones_view(request):
    """Vista de niveles de tension"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            ten_id = request.POST.get('tension_id')
            try:
                ten = NivelTension.objects.get(Id_Ten=ten_id)
                ten.delete()
                messages.success(request, 'Nivel de tension eliminado correctamente.')
            except NivelTension.DoesNotExist:
                messages.error(request, 'Nivel de tension no encontrado.')
            return redirect('tensiones')
        else:
            tipo = request.POST.get('tipo')
            nivel = request.POST.get('nivel')
            
            if tipo and nivel:
                NivelTension.objects.create(
                    Tipo_ten=tipo,
                    Nivel=nivel,
                    creado_por=request.user
                )
                messages.success(request, 'Nivel de tension creado correctamente.')
                return redirect('tensiones')
    
    tensiones = NivelTension.objects.all().order_by('Nivel')
    
    context = {
        'title': 'Niveles de Tension',
        'tensiones': tensiones,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'tensiones.html', context)

@login_required(login_url='/login/')
def interfaces_view(request):
    """Vista de interfaces de comunicacion"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            iface_id = request.POST.get('interfaz_id')
            try:
                iface = InterfazDeComunicacion.objects.get(Id_Interfaz=iface_id)
                iface.delete()
                messages.success(request, 'Interfaz eliminada correctamente.')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada.')
            return redirect('interfaces')
        elif request.POST.get('editar'):
            iface_id = request.POST.get('interfaz_id')
            tipos_puerto = request.POST.getlist('tipos_puerto')
            try:
                iface = InterfazDeComunicacion.objects.get(Id_Interfaz=iface_id)
                iface.puertos.all().delete()
                for tipo in tipos_puerto:
                    PuertoComunicacion.objects.create(
                        Id_Interfaz=iface,
                        Tipo=tipo,
                        creado_por=request.user
                    )
                messages.success(request, 'Interfaz actualizada correctamente.')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada.')
            return redirect('interfaces')
        else:
            tipos_puerto = request.POST.getlist('tipos_puerto')
            if tipos_puerto:
                iface = InterfazDeComunicacion.objects.create(
                    Puertos_C=len(tipos_puerto),
                    creado_por=request.user
                )
                for tipo in tipos_puerto:
                    PuertoComunicacion.objects.create(
                        Id_Interfaz=iface,
                        Tipo=tipo,
                        creado_por=request.user
                    )
                messages.success(request, 'Interfaz creada correctamente.')
                return redirect('interfaces')
    
    interfaces = InterfazDeComunicacion.objects.all().order_by('Id_Interfaz')
    puertos_tipos = PuertoComunicacion.TIPO_CHOICES
    
    context = {
        'title': 'Interfaces',
        'interfaces': interfaces,
        'puertos_tipos': puertos_tipos,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'interfaces.html', context)

@login_required(login_url='/login/')
def protocolo_view(request):
    """Vista de protocolos"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            proto_id = request.POST.get('protocolo_id')
            try:
                proto = Protocolo.objects.get(Id_Protocolo=proto_id)
                proto.delete()
                messages.success(request, 'Protocolo eliminado correctamente.')
            except Protocolo.DoesNotExist:
                messages.error(request, 'Protocolo no encontrado.')
            return redirect('protocolo')
        else:
            tipo = request.POST.get('tipo')
            id_interfaz = request.POST.get('id_interfaz')
            estado = request.POST.get('estado', 'Activo')
            
            if tipo:
                iface = InterfazDeComunicacion.objects.filter(Id_Interfaz=id_interfaz).first() if id_interfaz else None
                Protocolo.objects.create(
                    Tipo=tipo,
                    Id_Interfaz=iface,
                    Estado=estado,
                    creado_por=request.user
                )
                messages.success(request, 'Protocolo creado correctamente.')
                return redirect('protocolo')
    
    protocolos = Protocolo.objects.all().order_by('Tipo')
    interfaces = InterfazDeComunicacion.objects.all().order_by('Id_Interfaz')
    
    context = {
        'title': 'Protocolos',
        'protocolos': protocolos,
        'interfaces': interfaces,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'protocolo.html', context)

@login_required(login_url='/login/')
def remotas_view(request):
    """Vista de remotas"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            remota_id = request.POST.get('remota_id')
            try:
                remota = Remota.objects.get(Id_Remota=remota_id)
                remota.delete()
                messages.success(request, 'Remota eliminada correctamente.')
            except Remota.DoesNotExist:
                messages.error(request, 'Remota no encontrada.')
            return redirect('remotas')
        else:
            marca = request.POST.get('marca')
            modelo = request.POST.get('modelo')
            id_ten_id = request.POST.get('id_ten')
            
            if marca and modelo:
                id_ten = NivelTension.objects.get(Id_Ten=id_ten_id) if id_ten_id else None
                Remota.objects.create(
                    Marca=marca,
                    Modelo=modelo,
                    Id_Ten=id_ten,
                    creado_por=request.user
                )
                messages.success(request, 'Remota creada correctamente.')
                return redirect('remotas')
    
    remotas = Remota.objects.all().order_by('Id_Remota')
    tensiones = NivelTension.objects.all().order_by('Nivel')
    
    context = {
        'title': 'Remotas',
        'remotas': remotas,
        'tensiones': tensiones,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'remotas.html', context)

@login_required(login_url='/login/')
def reconectadores_view(request):
    """Vista de reconectadores"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            recon_id = request.POST.get('reconectador_id')
            try:
                recon = Reconectador.objects.get(Id_reconectador=recon_id)
                recon.delete()
                messages.success(request, 'Reconectador eliminado correctamente.')
            except Reconectador.DoesNotExist:
                messages.error(request, 'Reconectador no encontrado.')
            return redirect('reconectadores')
    
    reconectadores = Reconectador.objects.all().order_by('Id_reconectador')
    
    context = {
        'title': 'Reconectadores',
        'reconectadores': reconectadores,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'reconectadores.html', context)
