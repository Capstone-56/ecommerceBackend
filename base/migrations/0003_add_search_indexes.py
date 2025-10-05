from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension

class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_usermodel_refreshtoken'),
    ]

    operations = [
        # Enable pg_trgm extension first
        TrigramExtension(),
        
        # Then create indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS product_search_idx ON product USING GIN (to_tsvector('english', name || ' ' || description));",
            reverse_sql="DROP INDEX IF EXISTS product_search_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS product_trigram_idx ON product USING GIN (name gin_trgm_ops, description gin_trgm_ops);",
            reverse_sql="DROP INDEX IF EXISTS product_trigram_idx;"
        ),
    ]
