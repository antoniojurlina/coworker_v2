import psycopg2
import pandas as pd
from ..decorators.error_handling import handle_database_errors

class DatabaseConnection:
    _instance = None

    def __new__(cls, host=None, port=None, user=None, dbname=None, password=None):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.host = host
            cls._instance.port = port
            cls._instance.user = user
            cls._instance.dbname = dbname
            cls._instance.password = password
        return cls._instance

    @handle_database_errors
    def fetch_data(self, query):
        connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            dbname=self.dbname,
            password=self.password
        )
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        # Convert rows to pandas DataFrame
        df = pd.DataFrame(rows, columns=[desc[0] for desc in cursor.description])
        return df