from psycopg2 import pool as pg_pool
import threading
from src.config import settings


class PostgresContext:

    _connection_pool: pg_pool.ThreadedConnectionPool | None = None
    _pool_lock = threading.Lock()

    def _get_connection_pool(self) -> pg_pool.ThreadedConnectionPool:
        if PostgresContext._connection_pool is None:
            with PostgresContext._pool_lock:
                if PostgresContext._connection_pool is None:
                    PostgresContext._connection_pool = pg_pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=20,
                        dsn=settings.DATABASE_URL
                    )
        return PostgresContext._connection_pool

    def connect(self):
        try:
            connection_pool = self._get_connection_pool()
            connection = connection_pool.getconn()

            if connection is None:
                raise ConnectionError("Não foi possível obter conexão do pool")

            cursor = connection.cursor()
            return cursor, connection

        except pg_pool.PoolError as e:
            raise ConnectionError(f"Erro no pool de conexões: {e}") from e
        except Exception as e:
            raise ConnectionError(f"Erro ao conectar ao banco: {e}") from e

    def disconnect(self, connection):
        try:
            if connection and not connection.closed:
                PostgresContext._connection_pool.putconn(connection)
        except Exception:
            if connection and not connection.closed:
                connection.close()

    @classmethod
    def close_all_connections(cls):
        if cls._connection_pool:
            cls._connection_pool.closeall()
