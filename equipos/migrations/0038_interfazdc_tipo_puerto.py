from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('equipos', '0037_remove_unused_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='interfazdecomunicacion',
            name='Tipo_Puerto',
            field=models.CharField(
                blank=True,
                choices=[
                    ('ETH',   'Ethernet'),
                    ('RS232', 'RS-232'),
                    ('RS485', 'RS-485'),
                    ('USB',   'USB'),
                    ('FIBRA', 'Fibra Óptica'),
                ],
                default='',
                max_length=30,
                verbose_name='Tipo de Puerto',
            ),
        ),
    ]
