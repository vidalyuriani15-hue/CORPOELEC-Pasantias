from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Crea los usuarios por defecto del sistema (admin y administracion)'
    
    def handle(self, *args, **options):
        # Crear superusuario admin
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'Admin123!')
            self.stdout.write(self.style.SUCCESS('Superusuario "admin" creado'))
        else:
            self.stdout.write(self.style.WARNING('El usuario "admin" ya existe'))
        
        # Crear usuario staff administracion
        if not User.objects.filter(username='administracion').exists():
            user = User.objects.create_user('administracion', 'administracion@example.com', 'Admin123!')
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS('Usuario "administracion" (staff) creado'))
        else:
            self.stdout.write(self.style.WARNING('El usuario "administracion" ya existe'))