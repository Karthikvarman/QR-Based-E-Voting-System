import mysql.connector
from mysql.connector import errorcode
import logging
from typing import Optional, Union, Dict, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Handles all database operations for the voting system"""
    
    def __init__(self):
        self.config = {
            'host': '127.0.0.1',
            'user': 'root',
            'password': 'Karthik@333438',
            'database': 'voting_system',
            'auth_plugin': 'Karthik@333438',
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'raise_on_warnings': True
        }
        self.connection = None

    def connect(self) -> bool:
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(**self.config)
            logger.info("Successfully connected to database")
            return True
        except mysql.connector.Error as err:
            logger.error(f"Database connection failed: {err}")
            return False

    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Database connection closed")

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        query = """
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
        """
        result = self.execute_query(query, (self.config['database'], table_name), fetch=True)
        return result and result[0]['COUNT(*)'] > 0

    def execute_query(self, query: str, params: tuple = None, 
                     fetch: bool = False) -> Optional[Union[List[Dict], int]]:
        """
        Execute a SQL query
        :param query: SQL query string
        :param params: Parameters for the query
        :param fetch: Whether to fetch results
        :return: Results if fetch=True, None otherwise
        """
        cursor = None
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if fetch:
                result = cursor.fetchall()
                logger.debug(f"Query executed successfully: {query}")
                return result
            else:
                self.connection.commit()
                logger.debug(f"Query executed successfully: {query}")
                return cursor.rowcount
                
        except mysql.connector.Error as err:
            logger.error(f"Query failed: {query} - Error: {err}")
            if self.connection:
                self.connection.rollback()
            return None
        finally:
            if cursor:
                cursor.close()

# Singleton instance
db_manager = DatabaseManager()