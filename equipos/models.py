from django.db import models
from django.contrib.auth.models import User

class NivelTension(models.Model):
    """Modelo para almacenar los diferentes niveles de tensión eléctrica"""
    TIPO_CHOICES = [
        ('AT', 'Alta Tensión'),
        ('MT', 'Media Tensión'),
        ('BT', 'Baja Tensión'),
    ]
    NIVEL_CHOICES = [
        ('230kV', '230 kV'),
        ('115kV', '115 kV'),
        ('34.5kV', '34.5 kV'),
        ('13.8kV', '13.8 kV'),
    ]
    Id_Ten = models.AutoField(primary_key=True)  # Identificador único
    Tipo_ten = models.CharField(max_length=5, choices=TIPO_CHOICES, default='AT')  # Tipo de tensión (AT/MT/BT)
    Nivel = models.CharField(max_length=10, choices=NIVEL_CHOICES)  # Valor del nivel (115kV, 34.5kV, etc.)
    Fecha_Reg = models.DateField(auto_now_add=True)  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='niveles_tension_creados')  # Usuario que creó el registro
    
    class Meta:
        verbose_name = 'Nivel de Tensión'
        verbose_name_plural = 'Niveles de Tensión'
        ordering = ['Id_Ten']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: 'Tipo - Nivel' (ej: 'Alta Tensión - 115 kV')"""
        return f"{self.get_Tipo_ten_display()} - {self.get_Nivel_display()}"

class Subestacion(models.Model):
    """Modelo para gestionar subestaciones eléctricas"""
    Id_Sub_est = models.AutoField(primary_key=True)  # Identificador único
    Id_Ten = models.ForeignKey(NivelTension, on_delete=models.CASCADE, related_name='subestaciones')  # Nivel de tensión asociado
    Nombre = models.CharField(max_length=100)  # Nombre de la subestación
    Ubicación = models.CharField(max_length=200)  # Dirección o ubicación física
    Coordenadas = models.CharField(max_length=100, blank=True, verbose_name='Coordenadas')  # Coordenadas GPS (opcional)
    Fecha_Reg = models.DateField(auto_now_add=True)  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='subestaciones_creadas')  # Usuario que creó el registro
    
    class Meta:
        verbose_name = 'Subestación'
        verbose_name_plural = 'Subestaciones'
        ordering = ['Id_Sub_est']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: nombre de la subestación"""
        return self.Nombre

class Rele(models.Model):
    """Modelo principal para gestionar relés de protección eléctrica"""
    Id_relé = models.AutoField(primary_key=True)  # Identificador único
    Id_Ten = models.ForeignKey(NivelTension, on_delete=models.CASCADE, related_name='reles')  # Nivel de tensión asociado
    Id_Sub_est = models.ForeignKey(Subestacion, on_delete=models.CASCADE, related_name='reles')  # Subestación donde está instalado
    Marca = models.CharField(max_length=100)  # Marca del fabricante
    Modelo = models.CharField(max_length=100)  # Modelo específico del relé
    Estado = models.CharField(max_length=50)  # Estado operativo (Activo/Inactivo/Mantenimiento)
    Observaciones = models.TextField(blank=True)  # Notas adicionales (opcional)
    Imagen = models.ImageField(upload_to='reles/', blank=True, null=True, verbose_name='Imagen del relé')  # Imagen del relé
    Fecha_Reg = models.DateField(auto_now_add=True)  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reles_creados')  # Usuario que creó el registro
    # Relaciones muchos-a-muchos para protocolos y puertos soportados
    Protocolos = models.ManyToManyField("Protocolo", blank=True, related_name='reles_asociados')  # Protocolos de comunicación configurados
    Puertos = models.ManyToManyField("PuertoComunicacion", blank=True, related_name='reles_asociados')  # Puertos de comunicación configurados
    # Relación con remota vía ForeignKey
    EsRemoto = models.BooleanField(default=False, verbose_name='¿Posee Remota?')  # Indica si tiene remota asociada
    Remota = models.ForeignKey("Remota", on_delete=models.SET_NULL, null=True, blank=True, related_name='reles_asociados', verbose_name='Remota asociada')
    Puertos_IPs = models.JSONField(default=dict, blank=True, verbose_name='IPs por puerto ETH del relé')
    Remota_IPs = models.JSONField(default=dict, blank=True, verbose_name='IPs por puerto ETH de la remota')
    Entradas_Digitales = models.PositiveIntegerField(default=0, verbose_name='Entradas Digitales')
    Salidas_Digitales = models.PositiveIntegerField(default=0, verbose_name='Salidas Digitales')
    Entradas_Analogicas = models.PositiveIntegerField(default=0, verbose_name='Entradas Analógicas')
    Contadores = models.PositiveIntegerField(default=0, verbose_name='Contadores')
    
    class Meta:
        verbose_name = 'Relé'
        verbose_name_plural = 'Relés'
        ordering = ['Id_relé']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: 'Marca Modelo' (ej: 'SEL-587')"""
        return f"{self.Marca} {self.Modelo}"


class Usuario(models.Model):
    """Modelo extendido de perfil de usuario"""
    Id_user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)  # Enlace con usuario de Django
    Nombre = models.CharField(max_length=100)  # Nombre completo
    Correo = models.EmailField()  # Correo electrónico
    Nivel_User = models.CharField(max_length=50)  # Nivel de acceso/permisos
    permisos = models.JSONField(default=dict, blank=True)  # Permisos: crear, actualizar, eliminar
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['Id_user']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: nombre del usuario"""
        return self.Nombre

class InterfazDeComunicacion(models.Model):
    """Modelo para gestionar interfaces de comunicación (puertos físicos o protocolos)"""
    TIPO_INTERFAZ_CHOICES = [
        ('PUERTOS', 'Puertos de Comunicación'),
        ('PROTOCOLOS', 'Protocolos de Comunicación'),
    ]
    
    Id_Interfaz = models.AutoField(primary_key=True, serialize=False)  # Identificador único (PK)
    Puertos_C = models.IntegerField(default=0, verbose_name='Cantidad de Puertos')  # Contador de puertos
    Fecha_Reg = models.DateField(auto_now_add=True)  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='interfaces_creadas')  # Usuario que creó el registro
    Tipo_Interfaz = models.CharField(max_length=20, choices=TIPO_INTERFAZ_CHOICES, default='PUERTOS', verbose_name='Tipo de Interfaz')  # Tipo de interfaz
    Activo = models.BooleanField(default=True, verbose_name='Activo')  # Para eliminación lógica
    
    objects = models.Manager()
    activos = models.Manager()  # Manager por defecto para filtrar activos
    
    class Meta:
        verbose_name = 'Interfaz de Comunicación'
        verbose_name_plural = 'Interfaces de Comunicación'
        ordering = ['Id_Interfaz']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: 'Interfaz X - Tipo'"""
        return f"Interfaz {self.Id_Interfaz} - {self.get_Tipo_Interfaz_display()}"
    
    def clean(self):
        """Validación: una interfaz no puede tener ambos tipos simultáneamente"""
        from django.core.exceptions import ValidationError
        if self.pk:
            # Check counts without causing recursion
            puertos_count = self.puertos.count()
            protocolos_count = self.protocolos.count()
            if puertos_count > 0 and protocolos_count > 0:
                raise ValidationError('Una interfaz no puede tener puertos y protocolos simultáneamente.')

class PuertoComunicacion(models.Model):
    """Modelo para gestionar puertos de comunicación individuales"""
    TIPO_CHOICES = [
        ('ETH', 'Ethernet'),
        ('RS232', 'RS232'),
        ('RS485', 'RS485'),
        ('USB', 'USB'),
        ('FIBRA', 'Fibra Óptica'),
    ]
    Id_Puerto = models.AutoField(primary_key=True)  # Identificador único
    Id_Interfaz = models.ForeignKey(InterfazDeComunicacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='puertos')  # Interface a la que pertenece - SET_NULL permite eliminar interfaz sin borrar puertos
    Tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='ETH', verbose_name='Tipo de Puerto')  # Tipo de puerto (enumerado)
    Estado = models.CharField(max_length=50, default='Activo', verbose_name='Estado')  # Estado operativo
    Fecha_Reg = models.DateField(auto_now_add=True)  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='puertos_creados')  # Usuario que creó el registro
    
    class Meta:
        verbose_name = 'Puerto de Comunicación'
        verbose_name_plural = 'Puertos de Comunicación'
        ordering = ['Id_Puerto']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: 'Puerto TIPO - Interfaz X'"""
        return f"Puerto {self.Tipo} - Interfaz {self.Id_Interfaz.Id_Interfaz}"

class Remota(models.Model):
    """Modelo para gestionar remotas de protección eléctrica"""
    Id_Remota = models.AutoField(primary_key=True)  # Identificador único
    Id_Ten = models.ForeignKey(NivelTension, on_delete=models.SET_NULL, null=True, blank=True, related_name='remotas')  # Nivel de tensión asociado (opcional)
    Marca = models.CharField(max_length=100)  # Marca del fabricante
    Modelo = models.CharField(max_length=100)  # Modelo específico de la remota
    Fecha_Reg = models.DateField(auto_now_add=True)  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='remotas_creadas')  # Usuario que creó el registro
    # Relaciones muchos-a-muchos para interfaces y protocolos
    Interfaces = models.ManyToManyField("InterfazDeComunicacion", blank=True, related_name='remotas_asociadas')
    Protocolos = models.ManyToManyField("Protocolo", blank=True, related_name='remotas_asociadas')
    Niveles_Ten = models.ManyToManyField("NivelTension", blank=True, related_name='remotas_multiples')
    
    class Meta:
        verbose_name = 'Remota'
        verbose_name_plural = 'Remotas'
        ordering = ['Id_Remota']
    
    def __str__(self):
        return f"{self.Marca} {self.Modelo}"


class Protocolo(models.Model):
    """Modelo para gestionar protocolos de comunicación soportados"""
    TIPO_CHOICES = [
        ('104', 'IEC 104'),
        ('DNP', 'DNP3'),
        ('GOOSE', 'GOOSE'),
        ('101', 'IEC 101'),
        ('MODBUS', 'Modbus'),
    ]
    Id_Protocolo = models.AutoField(primary_key=True)  # Identificador único
    Id_Interfaz = models.ForeignKey(InterfazDeComunicacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='protocolos', verbose_name='Interfaz')  # Interface asociada - SET_NULL permite eliminar interfaz sin borrar protocolos
    Tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name='Tipo de Protocolo')  # Tipo de protocolo (enumerado)
    Estado = models.CharField(max_length=50, default='Activo', verbose_name='Estado')  # Estado operativo
    Fecha_Reg = models.DateField(auto_now_add=True, verbose_name='Fecha de Registro')  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='protocolos_creados')  # Usuario que creó el registro
    Activo = models.BooleanField(default=True, verbose_name='Activo')  # Para eliminación lógica
    

    class Meta:
        verbose_name = 'Protocolo de Comunicación'
        verbose_name_plural = 'Protocolos de Comunicación'
        ordering = ['Id_Protocolo']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: 'TIPO - Interfaz X' (ej: 'IEC 104 - Interfaz 1')"""
        return f"{self.get_Tipo_display()} - Interfaz {self.Id_Interfaz.Id_Interfaz}"


class Reconectador(models.Model):
    """Modelo para gestionar reconectadores eléctricos"""
    Id_reconectador = models.AutoField(primary_key=True)  # Identificador único
    Id_Ten = models.ForeignKey(NivelTension, on_delete=models.CASCADE, related_name='reconectadores')  # Nivel de tensión asociado
    Id_Sub_est = models.ForeignKey(Subestacion, on_delete=models.CASCADE, related_name='reconectadores')  # Subestación donde está instalado
    Marca = models.CharField(max_length=100)  # Marca del fabricante
    Modelo = models.CharField(max_length=100)  # Modelo específico del reconectador
    Estado = models.CharField(max_length=50)  # Estado operativo (Activo/Inactivo/Mantenimiento)
    Observaciones = models.TextField(blank=True)  # Notas adicionales (opcional)
    Imagen = models.ImageField(upload_to='reconectadores/', blank=True, null=True, verbose_name='Imagen del reconectador')  # Imagen del reconectador
    Fecha_Reg = models.DateField(auto_now_add=True)  # Fecha de registro automática
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reconectadores_creados')  # Usuario que creó el registro
    
    class Meta:
        verbose_name = 'Reconectador'
        verbose_name_plural = 'Reconectadores'
        ordering = ['Id_reconectador']  # Orden por ID ascendente
    
    def __str__(self):
        """Representación legible: 'Marca Modelo' (ej: 'Siemens 7SJ85')"""
        return f"{self.Marca} {self.Modelo}"


class Evento(models.Model):
    """Modelo para registrar eventos en la bitácora del sistema"""
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
    Usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos')
    Fecha_Hora = models.DateTimeField(auto_now_add=True)
    IP_Address = models.GenericIPAddressField(null=True, blank=True)
    Vista = models.CharField(max_length=100, blank=True, default='')
    
    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Registro de Eventos'
        ordering = ['-Fecha_Hora']
    
    def __str__(self):
        return f"{self.get_Tipo_display()}: {self.Descripcion[:50]}"

