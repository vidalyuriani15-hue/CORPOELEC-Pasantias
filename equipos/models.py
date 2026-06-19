from django.db import models
from django.contrib.auth.models import User

class NivelTension(models.Model):
    """Nivel de tensión eléctrica (Alta, Media o Baja Tensión).
    Es el punto de partida de la jerarquía: las subestaciones, relés y remotas
    se agrupan bajo un nivel de tensión. Los niveles predefinidos cubren los
    estándares venezolanos; el admin puede agregar valores personalizados vía
    la opción 'Otro' en el formulario.
    """
    TIPO_CHOICES = [
        ('AT', 'Alta Tensión'),
        ('MT', 'Media Tensión'),
        ('BT', 'Baja Tensión'),
    ]
    # Valores de tensión más comunes en la red CORPOELEC; el admin puede definir niveles extras
    NIVEL_CHOICES = [
        ('230kV', '230 kV'),
        ('115kV', '115 kV'),
        ('34.5kV', '34.5 kV'),
        ('13.8kV', '13.8 kV'),
    ]
    Id_Ten = models.AutoField(primary_key=True)
    Tipo_ten = models.CharField(max_length=5, choices=TIPO_CHOICES, default='AT')  # AT / MT / BT
    Nivel = models.CharField(max_length=10, choices=NIVEL_CHOICES)  # Valor kV (puede ser personalizado)
    Fecha_Reg = models.DateField(auto_now_add=True)
    # SET_NULL para no borrar el nivel si el usuario que lo creó es eliminado del sistema
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='niveles_tension_creados')

    class Meta:
        verbose_name = 'Nivel de Tensión'
        verbose_name_plural = 'Niveles de Tensión'
        ordering = ['Id_Ten']

    def __str__(self):
        """Representación legible: 'Alta Tensión - 115 kV'"""
        return f"{self.get_Tipo_ten_display()} - {self.get_Nivel_display()}"

    def get_dependencias(self):
        """Recorre todas las relaciones inversas para detectar si el nivel
        está siendo referenciado antes de permitir su eliminación.
        """
        dependencias = []

        if self.subestaciones.exists():
            dependencias.extend([f"Subestación: {s.Nombre}" for s in self.subestaciones.all()])

        if self.reles.exists():
            dependencias.extend([f"Relé: {r.Marca} {r.Modelo}" for r in self.reles.all()])

        if self.remotas.exists():
            dependencias.extend([f"Remota: {r.Marca} {r.Modelo}" for r in self.remotas.all()])

        return dependencias

    def puede_ser_eliminado(self):
        """Retorna (True, '') si no tiene dependencias, o (False, mensaje) si las tiene.
        Llamado desde la vista antes de ejecutar el DELETE para proteger la integridad.
        """
        dependencias = self.get_dependencias()
        if dependencias:
            return False, f"Este nivel de tensión tiene {len(dependencias)} elemento(s) asociado(s)"
        return True, ""

class Subestacion(models.Model):
    """Subestación eléctrica. Contiene uno o varios relés instalados.
    Puede operar con múltiples niveles de tensión simultáneamente (campo M2M
    Niveles_Ten). El campo Id_Ten conserva el primer nivel seleccionado por
    compatibilidad con registros anteriores a la migración multi-nivel.
    """
    Id_Sub_est = models.AutoField(primary_key=True)
    # Primer nivel de tensión seleccionado — se mantiene por compatibilidad con datos legacy
    Id_Ten = models.ForeignKey(NivelTension, on_delete=models.SET_NULL, null=True, blank=True, related_name='subestaciones')
    # Una subestación puede manejar varios niveles a la vez (ej: AT y MT en el mismo patio)
    Niveles_Ten = models.ManyToManyField("NivelTension", blank=True, related_name='subestaciones_multiples')
    Nombre = models.CharField(max_length=100)
    Ubicación = models.CharField(max_length=200)
    Coordenadas = models.CharField(max_length=100, blank=True, verbose_name='Coordenadas')  # Formato: "lat,lon" (opcional)
    Fecha_Reg = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subestaciones_creadas')

    class Meta:
        verbose_name = 'Subestación'
        verbose_name_plural = 'Subestaciones'
        ordering = ['Id_Sub_est']

    def __str__(self):
        return self.Nombre

    def get_dependencias(self):
        """Lista los relés instalados en esta subestación para validar eliminación."""
        dependencias = []

        if self.reles.exists():
            dependencias.extend([f"Relé: {r.Marca} {r.Modelo}" for r in self.reles.all()])

        return dependencias

    def puede_ser_eliminada(self):
        """Retorna (True, '') si no tiene relés asociados, o (False, mensaje) si los tiene."""
        dependencias = self.get_dependencias()
        if dependencias:
            return False, f"Esta subestación tiene {len(dependencias)} elemento(s) asociado(s)"
        return True, ""

class Rele(models.Model):
    """Relé de protección eléctrica instalado en una subestación.

    Puede ser local (EsRemoto=False) o remoto (EsRemoto=True). Cuando es remoto,
    tiene una Remota asociada con sus propios puertos, protocolos e IPs.

    Los campos JSON almacenan la configuración de red sin necesidad de tablas extra:
      - Puertos_IPs: {puerto_id: ip}  — IPs de los puertos ETH del propio relé
      - Remota_IPs:  {'iface_puerto': ip} — IPs de los puertos ETH de la remota
      - Remota_Puertos: ['iface_puerto', ...] — selección de puertos de la remota
    """
    Id_relé = models.AutoField(primary_key=True)
    Id_Ten = models.ForeignKey(NivelTension, on_delete=models.CASCADE, related_name='reles')
    Id_Sub_est = models.ForeignKey(Subestacion, on_delete=models.CASCADE, related_name='reles')
    Marca = models.CharField(max_length=100)
    Modelo = models.CharField(max_length=100)
    Estado = models.CharField(max_length=50)  # Ej: 'Activo', 'Inactivo', 'En mantenimiento'
    Observaciones = models.TextField(blank=True)
    Imagen = models.ImageField(upload_to='reles/', blank=True, null=True, verbose_name='Imagen del relé')
    Fecha_Reg = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reles_creados')

    # Protocolos de comunicación configurados en el relé (IEC 104, DNP3, etc.)
    Protocolos = models.ManyToManyField("Protocolo", blank=True, related_name='reles_asociados')

    # Indica si el relé tiene una unidad remota (RTU/IED) asociada
    EsRemoto = models.BooleanField(default=False, verbose_name='¿Posee Remota?')
    # SET_NULL permite eliminar la remota sin perder el registro del relé
    Remota = models.ForeignKey("Remota", on_delete=models.SET_NULL, null=True, blank=True, related_name='reles_asociados', verbose_name='Remota asociada')

    # Diccionario {puerto_id: ip} con las IPs asignadas a cada puerto ETH del relé
    Puertos_IPs = models.JSONField(default=dict, blank=True, verbose_name='IPs por puerto ETH del relé')
    # Diccionario {'iface_puerto': ip} con las IPs de los puertos ETH de la remota
    Remota_IPs = models.JSONField(default=dict, blank=True, verbose_name='IPs por puerto ETH de la remota')
    # Lista de claves 'iface_puerto' que identifican los puertos de la remota seleccionados
    Remota_Puertos = models.JSONField(default=list, blank=True, verbose_name='Puertos de la remota seleccionados')

    # Capacidad de entradas/salidas del relé (informativo, no afecta lógica)
    Entradas_Digitales = models.PositiveIntegerField(default=0, verbose_name='Entradas Digitales')
    Salidas_Digitales = models.PositiveIntegerField(default=0, verbose_name='Salidas Digitales')
    Entradas_Analogicas = models.PositiveIntegerField(default=0, verbose_name='Entradas Analógicas')
    Contadores = models.PositiveIntegerField(default=0, verbose_name='Contadores')

    class Meta:
        verbose_name = 'Relé'
        verbose_name_plural = 'Relés'
        ordering = ['Id_relé']

    def __str__(self):
        return f"{self.Marca} {self.Modelo}"


class Usuario(models.Model):
    """Perfil extendido de usuario vinculado al User de Django (relación 1-a-1).
    Agrega permisos granulares independientes del sistema de permisos de Django.
    El campo `permisos` tiene la estructura:
        {'crear': bool, 'actualizar': bool, 'eliminar': bool}
    Los superusuarios tienen todos los permisos implícitos sin necesidad de
    este campo; solo aplica a usuarios regulares.
    """
    # CASCADE: al eliminar el User de Django también se elimina este perfil
    Id_user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    Nombre = models.CharField(max_length=100)
    Correo = models.EmailField()
    Nivel_User = models.CharField(max_length=50)  # 'admin' o 'usuario'
    # JSON con tres llaves booleanas: crear, actualizar, eliminar
    permisos = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['Id_user']

    def __str__(self):
        return self.Nombre

class InterfazDeComunicacion(models.Model):
    """Interfaz de comunicación física (puerto) o lógica (protocolo).
    El tipo se determina por el campo Tipo_Interfaz:
      - 'PUERTOS'    → representa un puerto físico (ETH, RS232, RS485, etc.)
                       El tipo específico se guarda en Tipo_Puerto.
      - 'PROTOCOLOS' → tiene hijos Protocolo (IEC 104, DNP3, Modbus, etc.)
    La eliminación es LÓGICA (Activo=False) para mantener trazabilidad histórica
    y no romper relaciones con relés o remotas que la referenciaron.
    """
    TIPO_INTERFAZ_CHOICES = [
        ('PUERTOS', 'Puertos de Comunicación'),
        ('PROTOCOLOS', 'Protocolos de Comunicación'),
    ]

    TIPO_PUERTO_CHOICES = [
        ('ETH',   'Ethernet'),
        ('RS232', 'RS-232'),
        ('RS485', 'RS-485'),
        ('USB',   'USB'),
        ('FIBRA', 'Fibra Óptica'),
    ]

    Id_Interfaz = models.AutoField(primary_key=True, serialize=False)
    Puertos_C = models.IntegerField(default=0, verbose_name='Cantidad de Puertos')  # Contador denormalizado para queries rápidas
    Fecha_Reg = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='interfaces_creadas')
    Tipo_Interfaz = models.CharField(max_length=20, choices=TIPO_INTERFAZ_CHOICES, default='PUERTOS', verbose_name='Tipo de Interfaz')
    # Tipo_Puerto aplica solo cuando Tipo_Interfaz='PUERTOS'
    Tipo_Puerto = models.CharField(max_length=30, choices=TIPO_PUERTO_CHOICES, blank=True, default='', verbose_name='Tipo de Puerto')
    # False = eliminada lógicamente; se filtra en todas las queries de la app
    Activo = models.BooleanField(default=True, verbose_name='Activo')

    class _ActiveManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(Activo=True)

    # Manager estándar (incluye inactivos) — usar en admin y migraciones
    objects = models.Manager()
    # Manager filtrado — devuelve solo interfaces con Activo=True
    activos = _ActiveManager()

    class Meta:
        verbose_name = 'Interfaz de Comunicación'
        verbose_name_plural = 'Interfaces de Comunicación'
        ordering = ['Id_Interfaz']

    def __str__(self):
        if self.Tipo_Interfaz == 'PUERTOS' and self.Tipo_Puerto:
            return f"Puerto {self.get_Tipo_Puerto_display()} (ID {self.Id_Interfaz})"
        return f"Interfaz {self.Id_Interfaz} - {self.get_Tipo_Interfaz_display()}"

    def clean(self):
        """PuertoComunicacion fue eliminado en migración 0037; la validación de
        puertos ya no aplica. Solo se valida la integridad de protocolos.
        """
        pass

    def get_dependencias(self):
        """Devuelve dependencias EXTERNAS que bloquean la eliminación.
        Los protocolos hijos son propios de la interfaz y se limpian al eliminar,
        no son una dependencia bloqueante. Solo bloquean:
          - Relés que tienen asignado algún protocolo de esta interfaz.
          - Remotas que tienen esta interfaz asociada.
        """
        dependencias = []

        # Relés con protocolos de esta interfaz asignados (M2M Rele.Protocolos)
        reles_con_proto = Rele.objects.filter(
            Protocolos__Id_Interfaz=self.pk, Protocolos__Activo=True
        ).distinct()
        if reles_con_proto.exists():
            for r in reles_con_proto:
                sub = r.Id_Sub_est.Nombre if r.Id_Sub_est else 'sin subestación'
                dependencias.append(f"Relé: {sub} ({r.Marca} {r.Modelo})")

        # Solo bloquea si la remota tiene al menos un relé activo; sin relés la relación es huérfana
        remotas_con_rele = self.remotas_asociadas.filter(reles_asociados__isnull=False).distinct()
        if remotas_con_rele.exists():
            dependencias.extend([f"Remota: {r.Marca} {r.Modelo}" for r in remotas_con_rele])

        return dependencias

    def puede_ser_eliminada(self):
        """Retorna (True, '') si puede eliminarse de forma segura, o (False, motivo) si no."""
        dependencias = self.get_dependencias()
        if dependencias:
            return False, f"Esta interfaz tiene {len(dependencias)} elemento(s) asociado(s)"
        return True, ""

class TipoPuertoPersonalizado(models.Model):
    """Catálogo de tipos de puerto personalizados ("Otra") reutilizables.
    Cuando un admin crea un tipo personalizado para un puerto, se registra aquí
    para que quede disponible como casilla de verificación para todos los
    usuarios, incluso si la interfaz original que lo introdujo se elimina.
    """
    Tipo = models.CharField(max_length=30, unique=True, verbose_name='Tipo')
    Descripcion = models.CharField(max_length=80, blank=True, default='', verbose_name='Descripción')
    Icono = models.CharField(max_length=40, blank=True, default='', verbose_name='Ícono')
    Activo = models.BooleanField(default=True, verbose_name='Activo')
    Fecha_Reg = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tipos_puerto_personalizados')

    class Meta:
        verbose_name = 'Tipo de Puerto Personalizado'
        verbose_name_plural = 'Tipos de Puerto Personalizados'
        ordering = ['Tipo']

    def __str__(self):
        return self.Tipo


class TipoProtocoloPersonalizado(models.Model):
    """Catálogo de tipos de protocolo personalizados ("Otro") reutilizables.
    Cuando un admin crea un protocolo personalizado, se registra aquí para que
    permanezca como casilla de verificación disponible para todos los usuarios,
    incluso si la interfaz original que lo introdujo se elimina.
    """
    Tipo = models.CharField(max_length=30, unique=True, verbose_name='Tipo')
    Descripcion = models.CharField(max_length=80, blank=True, default='', verbose_name='Descripción')
    Icono = models.CharField(max_length=40, blank=True, default='', verbose_name='Ícono')
    Activo = models.BooleanField(default=True, verbose_name='Activo')
    Fecha_Reg = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tipos_protocolo_personalizados')

    class Meta:
        verbose_name = 'Tipo de Protocolo Personalizado'
        verbose_name_plural = 'Tipos de Protocolo Personalizados'
        ordering = ['Tipo']

    def __str__(self):
        return self.Tipo


class Remota(models.Model):
    """Unidad terminal remota (RTU/IED) asociada a uno o varios relés.
    Una remota es un dispositivo físico independiente que se vincula a un relé
    cuando éste opera de forma remota (Rele.EsRemoto=True). Puede compartirse
    entre relés de la misma subestación.

    Sus M2M reflejan la configuración de red en el momento de la asignación:
      - Interfaces: interfaces de puertos (ETH, RS485, etc.) que tiene conectadas
      - Protocolos: protocolos de comunicación que soporta
      - Niveles_Ten: niveles de tensión que gestiona
    """
    Id_Remota = models.AutoField(primary_key=True)
    # Nivel de tensión principal (opcional; la remota puede gestionar varios a través de Niveles_Ten)
    Id_Ten = models.ForeignKey(NivelTension, on_delete=models.SET_NULL, null=True, blank=True, related_name='remotas')
    Marca = models.CharField(max_length=100)
    Modelo = models.CharField(max_length=100)
    Fecha_Reg = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='remotas_creadas')

    # Solo interfaces de tipo 'PUERTOS' se asignan a remotas (no protocolos directamente)
    Interfaces = models.ManyToManyField("InterfazDeComunicacion", blank=True, related_name='remotas_asociadas')
    Protocolos = models.ManyToManyField("Protocolo", blank=True, related_name='remotas_asociadas')
    Niveles_Ten = models.ManyToManyField("NivelTension", blank=True, related_name='remotas_multiples')

    class Meta:
        verbose_name = 'Remota'
        verbose_name_plural = 'Remotas'
        ordering = ['Id_Remota']

    def __str__(self):
        return f"{self.Marca} {self.Modelo}"

    def get_dependencias(self):
        """Lista los relés que referencian esta remota para validar eliminación."""
        dependencias = []

        if self.reles_asociados.exists():
            dependencias.extend([f"Relé: {r.Marca} {r.Modelo}" for r in self.reles_asociados.all()])

        return dependencias

    def puede_ser_eliminada(self):
        """Retorna (True, '') si ningún relé la usa, o (False, motivo) si la tiene asignada."""
        dependencias = self.get_dependencias()
        if dependencias:
            return False, f"Esta remota tiene {len(dependencias)} elemento(s) asociado(s)"
        return True, ""


class Protocolo(models.Model):
    """Protocolo de comunicación hijo de una InterfazDeComunicacion tipo 'PROTOCOLOS'.
    Los tipos estándar están predefinidos en TIPO_CHOICES; el administrador puede
    agregar tipos adicionales vía TipoProtocoloPersonalizado (campo 'Otro').
    El campo `Icono` almacena una clase CSS/FontAwesome para mostrarlo en la UI.

    La eliminación también es LÓGICA (Activo=False) para no romper referencias
    en relés y remotas que ya lo tienen asignado.
    """
    TIPO_CHOICES = [
        ('104', 'IEC 104'),
        ('DNP', 'DNP3'),
        ('GOOSE', 'GOOSE'),
        ('101', 'IEC 101'),
        ('MODBUS', 'Modbus'),
    ]
    Id_Protocolo = models.AutoField(primary_key=True)
    # SET_NULL: si se desactiva/elimina la interfaz padre, el protocolo queda huérfano
    # pero se conserva como registro histórico (se filtra por Activo=True en las vistas)
    Id_Interfaz = models.ForeignKey(InterfazDeComunicacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='protocolos', verbose_name='Interfaz')
    # Tipo puede ser un valor de TIPO_CHOICES o un tipo personalizado definido por el admin
    Tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, verbose_name='Tipo de Protocolo')
    Descripcion = models.CharField(max_length=80, blank=True, default='', verbose_name='Descripción')
    Icono = models.CharField(max_length=40, blank=True, default='', verbose_name='Ícono')  # Clase CSS (ej: 'fa-network-wired')
    Fecha_Reg = models.DateField(auto_now_add=True, verbose_name='Fecha de Registro')
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='protocolos_creados')
    # False = desactivado lógicamente; no aparece en formularios ni listados activos
    Activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Protocolo de Comunicación'
        verbose_name_plural = 'Protocolos de Comunicación'
        ordering = ['Id_Protocolo']

    def __str__(self):
        iface_id = self.Id_Interfaz.Id_Interfaz if self.Id_Interfaz else 'sin interfaz'
        return f"{self.get_Tipo_display()} - Interfaz {iface_id}"

    def get_dependencias(self):
        """Verifica si algún relé o remota referencia este protocolo."""
        dependencias = []

        if self.reles_asociados.exists():
            dependencias.extend([f"Relé: {r.Marca} {r.Modelo}" for r in self.reles_asociados.all()])

        if self.remotas_asociadas.exists():
            dependencias.extend([f"Remota: {r.Marca} {r.Modelo}" for r in self.remotas_asociadas.all()])

        return dependencias

    def puede_ser_eliminado(self):
        """Retorna (True, '') si no tiene dependencias, o (False, motivo) si las tiene."""
        dependencias = self.get_dependencias()
        if dependencias:
            return False, f"Este protocolo tiene {len(dependencias)} elemento(s) asociado(s)"
        return True, ""


class Evento(models.Model):
    """Registro de auditoría del sistema (bitácora).
    Cada operación importante (CRUD, login, logout) genera un Evento.
    El campo `Vista` guarda el nombre legible de la sección donde ocurrió
    (ej: 'Subestaciones', 'Relés') para facilitar el filtrado en la bitácora.
    El campo `IP_Address` permite rastrear desde qué equipo se realizó la acción.
    Usuario=NULL indica una operación del sistema sin usuario autenticado.
    """
    TIPO_CHOICES = [
        ('CREACION', 'Creación'),
        ('ACTUALIZACION', 'Actualización'),
        ('ELIMINACION', 'Eliminación'),
        ('LOGIN', 'Inicio de Sesión'),
        ('LOGOUT', 'Cierre de Sesión'),
        ('ERROR', 'Error'),
        ('OTRO', 'Otro'),
    ]

    Id_Evento = models.AutoField(primary_key=True)
    Tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='OTRO')
    Descripcion = models.TextField()
    # SET_NULL: si el usuario es eliminado, el evento histórico se conserva
    Usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos')
    Fecha_Hora = models.DateTimeField(auto_now_add=True)
    IP_Address = models.GenericIPAddressField(null=True, blank=True)
    # Nombre legible de la vista (sección) donde se generó el evento
    Vista = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Registro de Eventos'
        ordering = ['-Fecha_Hora']  # Más recientes primero

    def __str__(self):
        return f"{self.get_Tipo_display()}: {self.Descripcion[:50]}"

