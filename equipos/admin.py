from django.contrib import admin
from django.contrib.auth.models import Group, User
from .models import NivelTension, Subestacion, Rele, Usuario

admin.site.unregister(Group)
admin.site.unregister(User)

@admin.register(NivelTension)
class NivelTensionAdmin(admin.ModelAdmin):
    list_display = ['Id_Ten', 'Tipo_ten', 'Nivel', 'Fecha_Reg']
    search_fields = ['Tipo_ten', 'Nivel']

@admin.register(Subestacion)
class SubestacionAdmin(admin.ModelAdmin):
    list_display = ['Id_Sub_est', 'Nombre', 'Ubicación', 'Id_Ten', 'Fecha_Reg']
    search_fields = ['Nombre', 'Ubicación']
    list_filter = ['Id_Ten']

@admin.register(Rele)
class ReleAdmin(admin.ModelAdmin):
    list_display = ['Id_relé', 'Marca', 'Modelo', 'Estado', 'Id_Ten', 'Id_Sub_est', 'Fecha_Reg']
    search_fields = ['Marca', 'Modelo']
    list_filter = ['Estado', 'Id_Ten', 'Id_Sub_est']

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['Id_user', 'Nombre', 'Correo', 'Nivel_User']
    search_fields = ['Nombre', 'Correo']
    list_filter = ['Nivel_User']
