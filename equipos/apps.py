from django.apps import AppConfig


class EquiposConfig(AppConfig):
    name = 'equipos'
    verbose_name = 'Información'

    def ready(self):
        import equipos.signals
