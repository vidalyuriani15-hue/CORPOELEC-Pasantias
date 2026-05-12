from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_migrate)
def create_default_users(sender, **kwargs):
    if sender.name == 'equipos':
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'Admin123!')
            print('[OK] Superusuario admin creado')
        
        if not User.objects.filter(username='administracion').exists():
            user = User.objects.create_user('administracion', 'administracion@example.com', 'Admin123!')
            user.is_staff = True
            user.save()
            print('[OK] Usuario administracion creado')