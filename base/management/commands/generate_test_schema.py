from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Generates a default test schema including the User table."

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
            self.stdout.write("Database connection successfully established.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to database: {e}"))
            return

        sql = """
        CREATE TABLE IF NOT EXISTS base_usermodel (
            id VARCHAR(100) PRIMARY KEY,
            name VARCHAR(255) NOT NULL
        );
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            self.stdout.write(self.style.SUCCESS("Default test schema with User table generated successfully."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating schema: {e}"))
