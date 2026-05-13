#!/usr/bin/env python
"""Verificación directa de protocolos en base de datos"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GridGuard.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT Id_Protocolo, Tipo, Id_Interfaz_id, Estado, Fecha_Reg, creado_por_id
        FROM equipos_protocolo
        ORDER BY Id_Protocolo
    """)
    rows = cursor.fetchall()
    
    print("=" * 80)
    print("PROTOCOLOS EN BASE DE DATOS")
    print("=" * 80)
    print(f"{'ID':<5} {'Tipo':<10} {'Display':<15} {'Interfaz':<10} {'Estado':<10} {'Creado por':<10}")
    print("-" * 80)
    
    from equipos.models import Protocolo
    for row in rows:
        id_proto, tipo, interfaz, estado, fecha, creado_por = row
        # Obtener display
        try:
            display = dict(Protocolo.TIPO_CHOICES).get(tipo, 'DESCONOCIDO')
        except:
            display = 'N/A'
        print(f"{str(id_proto):<5} {str(tipo):<10} {display:<15} {str(interfaz):<10} {str(estado):<10} {str(creado_por):<10}")
    
    print()
    print(f"Total: {len(rows)} registros")
    
    # Buscar duplicados por Tipo
    print("\n" + "=" * 80)
    print("ANÁLISIS DE DUPLICADOS (por campo 'Tipo'):")
    print("=" * 80)
    cursor.execute("""
        SELECT Tipo, COUNT(*) as veces
        FROM equipos_protocolo
        GROUP BY Tipo
        HAVING COUNT(*) > 1
        ORDER BY veces DESC
    """)
    dup_rows = cursor.fetchall()
    if dup_rows:
        for tipo, veces in dup_rows:
            print(f"  ⚠️  Tipo='{tipo}': {veces} registros (DUPLICADO)")
    else:
        print("  ✅ No se encontraron duplicados. Cada tipo es único.")
