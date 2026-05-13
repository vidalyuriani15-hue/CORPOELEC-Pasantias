#!/usr/bin/env python
"""Análisis de TIPO_CHOICES del modelo Protocolo"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GridGuard.settings')
django.setup()

from equipos.models import Protocolo

print("=" * 80)
print("ANALISIS DE TIPO_CHOICES - MODELO PROTOCOLO")
print("=" * 80)

choices = Protocolo.TIPO_CHOICES
print(f"\nTotal de opciones definidas: {len(choices)}")
print()

# Verificacion 1: Claves unicas
claves = [c[0] for c in choices]
print("[1] VERIFICACION DE CLAVES UNICAS")
print("-" * 40)
if len(claves) == len(set(claves)):
    print("[OK] Todas las claves son unicas (sin duplicados)")
else:
    print("[ERROR] Claves duplicadas encontradas:")
    from collections import Counter
    for k, v in Counter(claves).items():
        if v > 1:
            print(f"   '{k}' aparece {v} veces")

# Verificacion 2: Claves no vacias
print("\n[2] VERIFICACION DE CLAVES NO VACIAS")
print("-" * 40)
vacios = [(k, v) for k, v in choices if not k or k.strip() == '']
if vacios:
    print(f"[ERROR] {len(vacios)} clave(s) vacia(s):")
    for k, v in vacios:
        print(f"   ('{k}', '{v}')")
else:
    print("[OK] Todas las claves tienen valor")

# Verificacion 3: Etiquetas unicas (opcional, pero recomendado)
print("\n[3] VERIFICACION DE ETIQUETAS DUPLICADAS")
print("-" * 40)
etiquetas = [c[1] for c in choices]
etiquetas_dup = {}
for e in etiquetas:
    etiquetas_dup[e] = etiquetas_dup.get(e, 0) + 1
dup_encontrados = {k: v for k, v in etiquetas_dup.items() if v > 1}
if dup_encontrados:
    print("[ADVERTENCIA] Etiquetas duplicadas (misma etiqueta, diferente clave):")
    for etiq, count in dup_encontrados.items():
        print(f"   '{etiq}' aparece en {count} opciones")
else:
    print("[OK] Todas las etiquetas son unicas")

# Verificacion 4: Coherencia clave-etiqueta
print("\n[4] VERIFICACION DE COHERENCIA CLAVE-ETIQUETA")
print("-" * 40)
problemas = []
for k, v in choices:
    # Para protocolos, la etiqueta debe contener información relevante
    # No debe ser un código duplicado o genérico
    if v.strip() == '':
        problemas.append(f"Clave '{k}' tiene etiqueta vacía")
    elif k in v and k != v:
        # Esto no es necesariamente malo, solo informativo
        pass

if problemas:
    for p in problemas:
        print(f"  [ERROR] {p}")
else:
    print("[OK] Todas las etiquetas estan correctamente definidas")

# Verificacion 5: Longitud maxima de clave
print("\n[5] VERIFICACION DE COMPATIBILIDAD CON MODELO")
print("-" * 40)
max_len = Protocolo._meta.get_field('Tipo').max_length
print(f"  Campo 'Tipo' en modelo: CharField(max_length={max_len})")
claves_largas = [(k, v) for k, v in choices if len(k) > max_len]
if claves_largas:
    print(f"[ADVERTENCIA] {len(claves_largas)} clave(s) exceden max_length:")
    for k, v in claves_largas:
        print(f"     '{k}' (longitud {len(k)})")
else:
    print("[OK] Todas las claves caben en max_length")

# Resumen tabular
print("\n" + "=" * 80)
print("RESUMEN DE PROTOCOLOS DEFINIDOS")
print("=" * 80)
print(f"{'Clave':<12} {'Etiqueta (Display)':<25}")
print("-" * 80)
for k, v in choices:
    print(f"  {k:<12} {v:<25}")
print("\n[CONCLUSION]")
print("-" * 40)
claves_unicas = len(claves) == len(set(claves))
etiquetas_unicas = len(etiquetas) == len(set(etiquetas))
tamano_ok = len(claves_largas) == 0
sin_vacios = len(vacios) == 0

if all([claves_unicas, etiquetas_unicas, tamano_ok, sin_vacios]):
    print("[OK] La definicion TIPO_CHOICES es correcta: sin duplicados, sin vacios, etiquetas unicas, dentro de max_length.")
else:
    print("[REVISION REQUERIDA] Se encontraron problemas que pueden causar inconsistencias.")
