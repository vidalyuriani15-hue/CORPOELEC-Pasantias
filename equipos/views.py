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
    return render(request, 'admin/usuarios.html', context)

@login_required(login_url='/login/')
def subestaciones_view(request):
    """Vista de subestaciones"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            sub_id = request.POST.get('sub_id')
            try:
                sub = Subestacion.objects.get(Id_Sub_est=sub_id)
                sub.delete()
                messages.success(request, 'Subestacion eliminada correctamente.')
            except Subestacion.DoesNotExist:
                messages.error(request, 'Subestacion no encontrada.')
            return redirect('subestaciones')
        elif request.POST.get('editar'):
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
                messages.success(request, 'Subestacion actualizada correctamente.')
            except Subestacion.DoesNotExist:
                messages.error(request, 'Subestacion no encontrada.')
            except NivelTension.DoesNotExist:
                messages.error(request, 'Nivel de tension no valido.')
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
                        Ubicación=ubicacion,
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
    """Vista de niveles de tensión"""
    if request.method == 'POST':
        if request.POST.get('crear'):
            tipo_ten = request.POST.get('tipo_ten')
            nivel = request.POST.get('nivel')
            if tipo_ten and nivel:
                NivelTension.objects.create(
                    Tipo_ten=tipo_ten,
                    Nivel=nivel,
                    creado_por=request.user
                )
                messages.success(request, 'Nivel de tensión creado correctamente.')
            else:
                messages.error(request, 'Datos incompletos.')
            return redirect('tensiones')
        elif request.POST.get('editar'):
            ten_id = request.POST.get('ten_id')
            tipo_ten = request.POST.get('tipo_ten')
            nivel = request.POST.get('nivel')
            try:
                ten = NivelTension.objects.get(Id_Ten=ten_id)
                ten.Tipo_ten = tipo_ten
                ten.Nivel = nivel
                ten.save()
                messages.success(request, 'Nivel de tensión actualizado correctamente.')
            except NivelTension.DoesNotExist:
                messages.error(request, 'Nivel de tensión no encontrado.')
            return redirect('tensiones')
        elif request.POST.get('eliminar'):
            ten_id = request.POST.get('ten_id')
            try:
                NivelTension.objects.get(Id_Ten=ten_id).delete()
                messages.success(request, 'Nivel de tensión eliminado correctamente.')
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
    
    interfaces_list = InterfazDeComunicacion.objects.all().order_by('Id_Interfaz')
    paginator = Paginator(interfaces_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    puertos_tipos = PuertoComunicacion.TIPO_CHOICES
    
    context = {
        'title': 'Interfaces',
        'page_obj': page_obj,
        'puertos_tipos': puertos_tipos,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'interfaces.html', context)

@login_required(login_url='/login/')
def protocolo_view(request):
    """Vista de protocolos e interfaces"""
    if request.method == 'POST':
        # Crear interfaz con protocolos
        if request.POST.get('crear'):
            interfaz = InterfazDeComunicacion.objects.create(
                creado_por=request.user
            )
            tipos_protocolo = request.POST.getlist('tipos_protocolo')
            for tipo in tipos_protocolo:
                Protocolo.objects.create(
                    Id_Interfaz=interfaz,
                    Tipo=tipo,
                    creado_por=request.user
                )
            messages.success(request, 'Interfaz creada correctamente')
            
        # Editar interfaz/protocolos
        elif request.POST.get('editar'):
            interfaz_id = request.POST.get('interfaz_id')
            try:
                interfaz = InterfazDeComunicacion.objects.get(Id_Interfaz=interfaz_id)
                Protocolo.objects.filter(Id_Interfaz=interfaz).delete()
                tipos_protocolo = request.POST.getlist('tipos_protocolo')
                for tipo in tipos_protocolo:
                    Protocolo.objects.create(
                        Id_Interfaz=interfaz,
                        Tipo=tipo,
                        creado_por=request.user
                    )
                messages.success(request, 'Interfaz actualizada correctamente')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada')
                
        # Eliminar interfaz
        elif request.POST.get('eliminar'):
            interfaz_id = request.POST.get('interfaz_id')
            try:
                InterfazDeComunicacion.objects.get(Id_Interfaz=interfaz_id).delete()
                messages.success(request, 'Interfaz eliminada correctamente')
            except InterfazDeComunicacion.DoesNotExist:
                messages.error(request, 'Interfaz no encontrada')
    
    interfaces = InterfazDeComunicacion.objects.all().order_by('Id_Interfaz')
    paginator = Paginator(interfaces, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': 'Protocolos',
        'page_obj': page_obj,
        'is_admin': request.user.is_superuser,
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
    
    remotas_list = Remota.objects.all().order_by('Id_Remota')
    paginator = Paginator(remotas_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    tensiones = NivelTension.objects.all().order_by('Nivel')
    
    context = {
        'title': 'Remotas',
        'page_obj': page_obj,
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
        elif request.POST.get('editar'):
            recon_id = request.POST.get('reconectador_id')
            try:
                recon = Reconectador.objects.get(Id_reconectador=recon_id)
                recon.Id_Sub_est = Subestacion.objects.get(Id_Sub_est=request.POST.get('id_sub_est'))
                recon.Id_Ten = NivelTension.objects.get(Id_Ten=request.POST.get('id_ten'))
                recon.Marca = request.POST.get('marca')
                recon.Modelo = request.POST.get('modelo')
                recon.Estado = request.POST.get('estado')
                recon.Observaciones = request.POST.get('observaciones', '')
                
                if request.FILES.get('imagen'):
                    recon.Imagen = request.FILES.get('imagen')
                
                recon.save()
                messages.success(request, 'Reconectador actualizado correctamente.')
            except (Reconectador.DoesNotExist, Subestacion.DoesNotExist, NivelTension.DoesNotExist) as e:
                messages.error(request, f'Error al actualizar: {str(e)}')
            return redirect('reconectadores')
        else:
            # Crear nuevo reconectador
            sub = Subestacion.objects.get(Id_Sub_est=request.POST.get('id_sub_est'))
            ten = NivelTension.objects.get(Id_Ten=request.POST.get('id_ten'))
            
            recon = Reconectador.objects.create(
                Id_Sub_est=sub,
                Id_Ten=ten,
                Marca=request.POST.get('marca'),
                Modelo=request.POST.get('modelo'),
                Estado=request.POST.get('estado'),
                Observaciones=request.POST.get('observaciones', ''),
                creado_por=request.user
            )
            
            if request.FILES.get('imagen'):
                recon.Imagen = request.FILES.get('imagen')
                recon.save()
            
            messages.success(request, 'Reconectador creado correctamente.')
            return redirect('reconectadores')
    
    reconectadores_list = Reconectador.objects.all().order_by('Id_reconectador')
    paginator = Paginator(reconectadores_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    subestaciones = Subestacion.objects.all().order_by('Nombre')
    tensiones = NivelTension.objects.all().order_by('Nivel')
    
    context = {
        'title': 'Reconectadores',
        'page_obj': page_obj,
        'subestaciones': subestaciones,
        'tensiones': tensiones,
        'is_admin': request.user.is_superuser
    }
    return render(request, 'reconectadores.html', context)

@login_required(login_url='/login/')
def reles_view(request):
    """Vista de relés"""
    if request.method == 'POST':
        if request.POST.get('eliminar'):
            rele_id = request.POST.get('rele_id')
            try:
                rele = Rele.objects.get(Id_relé=rele_id)
                rele.delete()
                messages.success(request, 'Relé eliminado correctamente.')
            except Rele.DoesNotExist:
                messages.error(request, 'Relé no encontrado.')
            return redirect('reles')
        elif request.POST.get('editar'):
            rele_id = request.POST.get('rele_id')
            try:
                rele = Rele.objects.get(Id_relé=rele_id)
                rele.Id_Sub_est = Subestacion.objects.get(Id_Sub_est=request.POST.get('id_sub_est'))
                rele.Id_Ten = NivelTension.objects.get(Id_Ten=request.POST.get('id_ten'))
                rele.Marca = request.POST.get('marca')
                rele.Modelo = request.POST.get('modelo')
                rele.Estado = request.POST.get('estado')
                rele.Observaciones = request.POST.get('observaciones', '')
                
                if request.FILES.get('imagen'):
                    rele.Imagen = request.FILES.get('imagen')
                
                rele.Protocolos.set(request.POST.getlist('protocolos'))
                rele.Puertos.set(request.POST.getlist('puertos'))
                
                es_remoto = request.POST.get('es_remoto') == 'si'
                rele.EsRemoto = es_remoto
                if es_remoto and request.POST.get('remota_id'):
                    rele.Remota = Remota.objects.get(Id_Remota=request.POST.get('remota_id'))
                
                rele.save()
                messages.success(request, 'Relé actualizado correctamente.')
            except (Rele.DoesNotExist, Subestacion.DoesNotExist, NivelTension.DoesNotExist, Remota.DoesNotExist) as e:
                messages.error(request, f'Error al actualizar: {str(e)}')
            return redirect('reles')
        else:
            sub = Subestacion.objects.get(Id_Sub_est=request.POST.get('id_sub_est'))
            ten = NivelTension.objects.get(Id_Ten=request.POST.get('id_ten'))
            
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
            
            rele.Protocolos.set(request.POST.getlist('protocolos'))
            rele.Puertos.set(request.POST.getlist('puertos'))
            
            es_remoto = request.POST.get('es_remoto') == 'si'
            rele.EsRemoto = es_remoto
            if es_remoto and request.POST.get('remota_id'):
                rele.Remota = Remota.objects.get(Id_Remota=request.POST.get('remota_id'))
                rele.save()
            
            messages.success(request, 'Relé creado correctamente.')
            return redirect('reles')
    elif request.method == 'GET' and request.GET.get('detalle'):
        rele_id = request.GET.get('id')
        try:
            rele = Rele.objects.get(Id_relé=rele_id)
            data = {
                'id_sub_est': rele.Id_Sub_est.Id_Sub_est if rele.Id_Sub_est else '',
                'id_ten': rele.Id_Ten.Id_Ten if rele.Id_Ten else '',
                'marca': rele.Marca or '',
                'modelo': rele.Modelo or '',
                'estado': rele.Estado or '',
                'observaciones': rele.Observaciones or '',
                'imagen_url': rele.Imagen.url if rele.Imagen else '',
                'protocolos': list(rele.Protocolos.values_list('Id_Protocolo', flat=True)),
                'puertos': list(rele.Puertos.values_list('Id_Puerto', flat=True)),
                'es_remoto': rele.EsRemoto,
                'remota_id': rele.Remota.Id_Remota if rele.Remota else '',
                'remota_marca': rele.Remota.Marca if rele.Remota else '',
            }
            return JsonResponse(data)
        except Rele.DoesNotExist:
            return JsonResponse({'error': 'Relé no encontrado'}, status=404)
    
    reles_list = Rele.objects.all().order_by('-Id_relé')
    paginator = Paginator(reles_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    subestaciones = Subestacion.objects.all().order_by('Nombre')
    tensiones = NivelTension.objects.all().order_by('Nivel')
    protocolos = Protocolo.objects.all().order_by('Tipo')
    puertos = PuertoComunicacion.objects.all().order_by('Id_Puerto')
    remotas = Remota.objects.all().order_by('Id_Remota')
    interfaces_disponibles = InterfazDeComunicacion.objects.all().order_by('Id_Interfaz')
    
    context = {
        'title': 'Relés',
        'page_obj': page_obj,
        'subestaciones': subestaciones,
        'tensiones': tensiones,
        'protocolos': protocolos,
        'puertos': puertos,
        'remotas': remotas,
        'interfaces_disponibles': interfaces_disponibles,
        'is_admin': request.user.is_superuser
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
        
        marcas = list(remotas.values_list('Marca', flat=True).distinct())
        modelos_por_marca = {}
        interfaces_por_remota = {}
        interfaces_disponibles = list(InterfazDeComunicacion.objects.values_list('Id_Interfaz', flat=True))
        
        for remota in remotas:
            if remota.Marca not in modelos_por_marca:
                modelos_por_marca[remota.Marca] = {}
            modelos_por_marca[remota.Marca][remota.Modelo] = {
                'id': remota.Id_Remota,
                'nivel': remota.Id_Ten.get_Nivel_display() if remota.Id_Ten else ''
            }
            interfaces_por_remota[remota.Id_Remota] = list(remota.Interfaces.values_list('Id_Interfaz', flat=True))
        
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
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = find('img/logo_corpoelec.png')
    if not logo_path: logo_path = find('img/logo.jpg')

    if logo_path:
        elements.append(Paragraph("<font size=12><b>CORPOELEC</b></font>", styles['Normal']))
        elements.append(Paragraph("<font size=11><b>Niveles de Tensión Registrados</b></font>", styles['Normal']))
        elements.append(Paragraph(f"<font size=8>Reporte Generado: {datetime.now().strftime('%d/%m/%Y')}</font>", styles['Normal']))
    else:
        elements.append(Paragraph("<font size=14><b>Niveles de Tensión Registrados</b></font>", styles['Heading1']))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E63946')))
    elements.append(Spacer(1, 18))

    tensiones = NivelTension.objects.all().order_by('Nivel')
    data = [['Nivel', 'Tipo']]
    for tension in tensiones:
        data.append([tension.get_Nivel_display(), tension.get_Tipo_ten_display()])

    table = Table(data, colWidths=[2.0*inch, 4.0*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2e4a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<font size=8 color=grey>Corporación Eléctrica Nacional S.A. - Documento de carácter oficial</font>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="tensiones.pdf"'
    return response

@login_required(login_url='/login/')
def exportar_interfaces_pdf(request):
    """Exporta todas las interfaces a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = find('img/logo_corpoelec.png')
    if not logo_path: logo_path = find('img/logo.jpg')

    if logo_path:
        elements.append(Paragraph("<font size=12><b>CORPOELEC</b></font>", styles['Normal']))
        elements.append(Paragraph("<font size=11><b>Interfaces Registradas</b></font>", styles['Normal']))
        elements.append(Paragraph(f"<font size=8>Reporte Generado: {datetime.now().strftime('%d/%m/%Y')}</font>", styles['Normal']))
    else:
        elements.append(Paragraph("<font size=14><b>Interfaces Registradas</b></font>", styles['Heading1']))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E63946')))
    elements.append(Spacer(1, 18))

    interfaces = InterfazDeComunicacion.objects.all().order_by('Id_Interfaz')
    data = [['ID Interfaz', 'Puertos', 'Fecha Registro']]
    for interfaz in interfaces:
        data.append([interfaz.Id_Interfaz, interfaz.Puertos_C, interfaz.Fecha_Reg.strftime('%d/%m/%Y') if interfaz.Fecha_Reg else ''])

    table = Table(data, colWidths=[1.5*inch, 2.0*inch, 2.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2e4a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<font size=8 color=grey>Corporación Eléctrica Nacional S.A. - Documento de carácter oficial</font>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="interfaces.pdf"'
    return response

@login_required(login_url='/login/')
def exportar_protocolo_pdf(request):
    """Exporta todos los protocolos a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = find('img/logo_corpoelec.png')
    if not logo_path: logo_path = find('img/logo.jpg')

    if logo_path:
        elements.append(Paragraph("<font size=12><b>CORPOELEC</b></font>", styles['Normal']))
        elements.append(Paragraph("<font size=11><b>Protocolos Registrados</b></font>", styles['Normal']))
        elements.append(Paragraph(f"<font size=8>Reporte Generado: {datetime.now().strftime('%d/%m/%Y')}</font>", styles['Normal']))
    else:
        elements.append(Paragraph("<font size=14><b>Protocolos Registrados</b></font>", styles['Heading1']))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E63946')))
    elements.append(Spacer(1, 18))

    protocolos = Protocolo.objects.select_related('Id_Interfaz').all().order_by('Tipo')
    data = [['ID Protocolo', 'Tipo', 'Interfaz', 'Estado', 'Fecha Registro']]
    for protocolo in protocolos:
        interfaz_str = f"Interfaz {protocolo.Id_Interfaz.Id_Interfaz}" if protocolo.Id_Interfaz else 'N/A'
        fecha_reg = protocolo.Fecha_Reg.strftime('%d/%m/%Y') if protocolo.Fecha_Reg else 'N/A'
        data.append([protocolo.Id_Protocolo, protocolo.get_Tipo_display(), interfaz_str, protocolo.Estado, fecha_reg])

    table = Table(data, colWidths=[1.2*inch, 1.2*inch, 1.5*inch, 1.2*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2e4a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<font size=8 color=grey>Corporación Eléctrica Nacional S.A. - Documento de carácter oficial</font>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="protocolos.pdf"'
    return response

@login_required(login_url='/login/')
def exportar_subestaciones_pdf(request):
    """Exporta todas las subestaciones a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = find('img/logo_corpoelec.png')
    if not logo_path: logo_path = find('img/logo.jpg')

    if logo_path:
        elements.append(Paragraph("<font size=12><b>CORPOELEC</b></font>", styles['Normal']))
        elements.append(Paragraph("<font size=11><b>Subestaciones Registradas</b></font>", styles['Normal']))
        elements.append(Paragraph(f"<font size=8>Reporte Generado: {datetime.now().strftime('%d/%m/%Y')}</font>", styles['Normal']))
    else:
        elements.append(Paragraph("<font size=14><b>Subestaciones Registradas</b></font>", styles['Heading1']))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E63946')))
    elements.append(Spacer(1, 18))

    subestaciones = Subestacion.objects.all().order_by('Nombre')
    data = [['Nombre', 'Nivel de Tensión', 'Ubicación']]
    for sub in subestaciones:
        data.append([sub.Nombre, sub.Id_Ten.get_Nivel_display() if sub.Id_Ten else '', sub.Ubicación if hasattr(sub, 'Ubicación') and sub.Ubicación else ''])

    table = Table(data, colWidths=[2.0*inch, 2.0*inch, 2.0*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2e4a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<font size=8 color=grey>Corporación Eléctrica Nacional S.A. - Documento de carácter oficial</font>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="subestaciones.pdf"'
    return response

@login_required(login_url='/login/')
def exportar_remotas_pdf(request):
    """Exporta todas las remotas a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = find('img/logo_corpoelec.png')
    if not logo_path: logo_path = find('img/logo.jpg')

    if logo_path:
        elements.append(Paragraph("<font size=12><b>CORPOELEC</b></font>", styles['Normal']))
        elements.append(Paragraph("<font size=11><b>Remotas Registradas</b></font>", styles['Normal']))
        elements.append(Paragraph(f"<font size=8>Reporte Generado: {datetime.now().strftime('%d/%m/%Y')}</font>", styles['Normal']))
    else:
        elements.append(Paragraph("<font size=14><b>Remotas Registradas</b></font>", styles['Heading1']))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E63946')))
    elements.append(Spacer(1, 18))

    remotas = Remota.objects.all().order_by('Id_Remota')
    data = [['ID Remota', 'Marca', 'Modelo', 'Fecha Registro']]
    for remota in remotas:
        data.append([remota.Id_Remota, remota.Marca if remota.Marca else '', remota.Modelo if remota.Modelo else '', remota.Fecha_Reg.strftime('%d/%m/%Y') if remota.Fecha_Reg else ''])

    table = Table(data, colWidths=[0.8*inch, 1.5*inch, 1.5*inch, 2.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2e4a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<font size=8 color=grey>Corporación Eléctrica Nacional S.A. - Documento de carácter oficial</font>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="remotas.pdf"'
    return response

@login_required(login_url='/login/')
def exportar_reles_pdf(request):
    """Exporta todos los relés a PDF"""
    from django.contrib.staticfiles.finders import find
    from datetime import datetime
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from io import BytesIO

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = find('img/logo_corpoelec.png')
    if not logo_path: logo_path = find('img/logo.jpg')

    if logo_path:
        elements.append(Paragraph("<font size=12><b>CORPOELEC</b></font>", styles['Normal']))
        elements.append(Paragraph("<font size=11><b>Relés Registrados</b></font>", styles['Normal']))
        elements.append(Paragraph(f"<font size=8>Reporte Generado: {datetime.now().strftime('%d/%m/%Y')}</font>", styles['Normal']))
    else:
        elements.append(Paragraph("<font size=14><b>Relés Registrados</b></font>", styles['Heading1']))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E63946')))
    elements.append(Spacer(1, 18))

    reles = Rele.objects.all().order_by('-Id_relé')
    data = [['ID Relé', 'Subestación', 'Nivel Tensión', 'Marca', 'Modelo', 'Estado']]
    for rele in reles:
        nivel_ten = f"{rele.Id_Ten.get_Tipo_ten_display()} - {rele.Id_Ten.get_Nivel_display()}" if rele.Id_Ten else ''
        data.append([rele.Id_relé, rele.Id_Sub_est.Nombre if rele.Id_Sub_est else '', nivel_ten, rele.Marca if rele.Marca else '', rele.Modelo if rele.Modelo else '', rele.Estado if rele.Estado else ''])

    table = Table(data, colWidths=[0.8*inch, 1.8*inch, 1.8*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2e4a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<font size=8 color=grey>Corporación Eléctrica Nacional S.A. - Documento de carácter oficial</font>", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reles.pdf"'
    return response


@login_required(login_url='/login/')
def admin_eventos_view(request):
    """Vista de registro de eventos"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')
    
    context = {
        'title': 'Registro de Eventos'
    }
    return render(request, 'admin/eventos.html', context)


@login_required(login_url='/login/')
def admin_restaurar_view(request):
    """Vista de restaurar sistema"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')
    
    context = {
        'title': 'Restaurar Sistema'
    }
    return render(request, 'admin/restaurar.html', context)


@login_required(login_url='/login/')
def admin_backup_view(request):
    """Vista de copia de seguridad"""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para acceder a esta seccion.')
        return redirect('index')
    
    context = {
        'title': 'Copia de Seguridad'
    }
    return render(request, 'admin/backup.html', context)
