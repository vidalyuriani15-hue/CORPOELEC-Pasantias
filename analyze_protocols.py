#!/usr/bin/env python
"""Análisis de Protocolos - Detección de duplicados"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GridGuard.settings')
django.setup()

from equipos.models import Protocolo

print("=" * 70)
print("ANÁLISIS DE PROTOCOLOS - DUPLICADOS")
print("=" * 70)

total = Protocolo.objects.count()
print(f"\nTotal de protocolos registrados: {total}")

# Valores únicos
tipos_unicos = list(Protocolo.objects.values_list('Tipo', flat=True).distinct())
print(f"Tipos únicos en BD: {tipos_unicos}")

# Contar por tipo
from django.db.models import Count
conteo = Protocolo.objects.values('Tipo').annotate(count=Count('Tipo')).order_by('Tipo')
print("\nConteo por tipo:")
for c in conteo:
    print(f"  {c['Tipo']}: {c['count']} registro(s)")

# Detectar duplicados
duplicados = Protocolo.objects.values('Tipo').annotate(count=Count('Tipo')).filter(count__gt=1)
if duplicados:
    print("\n⚠️  DUPLICADOS ENCONTRADOS:")
    for dup in duplicados:
        print(f"\n  Tipo: {dup['Tipo']} ({dup['count']} registros)")
        protocolos = Protocolo.objects.filter(Tipo=dup['Tipo']).order_by('Id_Protocolo')
        for p in protocolos:
            print(f"    ID={p.Id_Protocolo}, Interfaz={p.Id_Interfaz_id}, Estado={p.Estado}, Creado por={p.creado_por}")
else:
    print("\n✅ No se encontraron duplicados")

# Verificar choices del modelo
print("\n" + "=" * 70)
print("DEFINICIÓN DE TIPO_CHOICES EN MODELO:")
print("=" * 70)
for key, label in Protocolo.TIPO_CHOICES:
    print(f"  '{key}': '{label}'")

# Verificar consistencia
print("\n" + "=" * 70)
print("VERIFICACIÓN DE CONSISTENCIA:")
print("=" * 70)
for key, label in Protocolo.TIPO_CHOICES:
    count = Protocolo.objects.filter(Tipo=key).count()
    status = "✅ OK" if count <= 1 else "⚠️  DUPLICADO"
    print(f"  {label:20s} (Tipo='{key}'): {count} registro(s) {status}")
