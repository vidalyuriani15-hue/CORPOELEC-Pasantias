# Generated manual migration to assign Tipo_Interfaz based on existing data

from django.db import migrations


def assign_tipo_interfaz(apps, schema_editor):
    InterfazDeComunicacion = apps.get_model('equipos', 'InterfazDeComunicacion')
    for iface in InterfazDeComunicacion.objects.all():
        puertos_count = iface.puertos.count()
        protocolos_count = iface.protocolos.count()
        if puertos_count > 0 and protocolos_count > 0:
            # Conflict: both present. Keep puertos, remove protocolos
            iface.protocolos.clear()
            iface.Tipo_Interfaz = 'PUERTOS'
            iface.save()
        elif puertos_count > 0:
            iface.Tipo_Interfaz = 'PUERTOS'
            iface.save()
        elif protocolos_count > 0:
            iface.Tipo_Interfaz = 'PROTOCOLOS'
            iface.save()
        else:
            # Empty interface, default is PUERTOS already
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0018_alter_interfazdecomunicacion_options_and_more'),
    ]

    operations = [
        migrations.RunPython(assign_tipo_interfaz, reverse_code=migrations.RunPython.noop),
    ]
