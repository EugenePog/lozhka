from django.db import migrations


class Migration(migrations.Migration):
    """Human-readable, sequential order numbers (LZ-10101, ...). Seeded demo orders use lower numbers."""

    dependencies = [("sales", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql="create sequence if not exists order_number_seq start 10101",
            reverse_sql="drop sequence if exists order_number_seq",
        )
    ]
