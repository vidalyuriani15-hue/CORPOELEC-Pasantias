from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea el usuario administrador por defecto: admin / admin1234'

    def handle(self, *args, **options):
        if User.objects.filter(username='admin').exists():
            User.objects.filter(username='admin').delete()
        User.objects.create_superuser('admin', 'admin@example.com', 'admin1234')
        self.stdout.write(self.style.SUCCESS('Superusuario "admin" creado con clave "admin1234"'))
