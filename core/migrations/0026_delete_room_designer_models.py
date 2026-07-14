# Generated migration to remove Room Designer feature

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_designhistory_alter_roomdesignproduct_options_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DesignHistory',
        ),
        migrations.DeleteModel(
            name='RoomDesignProduct',
        ),
        migrations.DeleteModel(
            name='RoomDesign',
        ),
    ]