from django.db import migrations, models

# Esta migración añade el alias público opcional a las preferencias del usuario.
# Se usa solo para mostrar un nombre alternativo en la interfaz, no para autenticar.


class Migration(migrations.Migration):

    dependencies = [
        ('chatia', '0005_conversation_llm_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreference',
            name='alias',
            field=models.CharField(blank=True, max_length=50, null=True, help_text='Alias p\u00fablico opcional para mostrar en la interfaz del usuario.'),
        ),
    ]
