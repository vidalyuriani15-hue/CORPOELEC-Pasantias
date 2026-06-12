from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User


@receiver(post_migrate)
def create_default_users(sender, **kwargs):
    if sender.name == 'equipos':
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin1234')
            print('[OK] Superusuario "admin" creado con clave "admin1234"')
