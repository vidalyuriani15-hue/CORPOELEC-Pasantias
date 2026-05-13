import os
import sys
import django

sys.path.append('C:\\Users\\zulay\\Documents\\pyhton\\django\\pasantias\\GridGuard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GridGuard.settings')
django.setup()

from equipos.models import InterfazDeComunicacion
from django.db.models import Count
stats = InterfazDeComunicacion.objects.values('Tipo_Interfaz').annotate(count=Count('Id_Interfaz'))
print('Distribución de interfaces por tipo:')
for s in stats:
    print(f"  {s['Tipo_Interfaz']}: {s['count']}")
