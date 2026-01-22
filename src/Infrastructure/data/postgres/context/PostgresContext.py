"""
Gerenciamento de sessão de banco de dados PostgreSQL com pool de conexões.
Implementa pool de conexões para melhor performance.
"""
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import threading
from src.config import settings


class PostgresContext:
    """
    Gerencia conexões com PostgreSQL usando pool de conexões.
    Usa ThreadedConnectionPool para melhor performance e reutilização de conexões.
    """
    
    # Pool de conexões compartilhado (Singleton)
    _connection_pool = None
    _pool_lock = threading.Lock()
    _connection_params = None
    
    def __init__(self):
        """Inicializa o DbSession e cria o pool se ainda não existir."""
        self._initialize_pool()
    
    def _parse_connection_string(self, connection_string=None):
        """
        Parse da string de conexão.
        
        Args:
            connection_string: String no formato 'server=...;data=...;user=...;port=...;password=...'
                              ou 'postgresql://user:password@host:port/database'
        
        Returns:
            Tupla com (host, database, user, port, password) ou None se for formato PostgreSQL padrão
        """
        if connection_string is None:
            # Usa DATABASE_URL
            database_url = settings.DATABASE_URL
            if database_url:
                # Se DATABASE_URL estiver no formato PostgreSQL (postgresql://...), retorna None para usar DSN diretamente
                if database_url.startswith(('postgresql://', 'postgres://')):
                    return None
                # Caso contrário, usa como string de conexão customizada
                connection_string = database_url
            else:
                raise ValueError(
                    "Variável de ambiente 'DATABASE_URL' não encontrada. "
                    "Defina-a no arquivo .env ou como variável de ambiente."
                )
        
        # Verifica se é formato PostgreSQL padrão
        if connection_string.startswith(('postgresql://', 'postgres://')):
            return None
        
        # Parse do formato customizado: 'server=...;data=...;user=...;port=...;password=...'
        params = connection_string.split(';')
        connection_params = {}
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                connection_params[key.strip()] = value.strip()
        
        return (
            connection_params.get('server'),
            connection_params.get('data'),
            connection_params.get('user'),
            connection_params.get('port'),
            connection_params.get('password')
        )
    
    def _initialize_pool(self):
        """Inicializa o pool de conexões se ainda não existir."""
        if PostgresContext._connection_pool is None:
            with PostgresContext._pool_lock:
                # Double-check locking pattern
                if PostgresContext._connection_pool is None:
                    try:
                        # Parse da string de conexão
                        parsed_params = self._parse_connection_string()
                        
                        # Se retornou None, significa que deve usar DATABASE_URL diretamente
                        if parsed_params is None:
                            database_url = settings.DATABASE_URL
                            PostgresContext._connection_pool = pool.ThreadedConnectionPool(
                                minconn=2,
                                maxconn=20,
                                dsn=database_url
                            )
                        else:
                            host, database, user, port, password = parsed_params
                            
                            # Valida se todos os parâmetros foram fornecidos
                            if not all([host, database, user, port, password]):
                                missing = [k for k, v in zip(['host', 'database', 'user', 'port', 'password'], 
                                                             [host, database, user, port, password]) if not v]
                                raise ValueError(f"Parâmetros de conexão faltando: {', '.join(missing)}")
                            
                            # Salva parâmetros para reuso
                            PostgresContext._connection_params = {
                                'host': host,
                                'database': database,
                                'user': user,
                                'port': port,
                                'password': password
                            }
                            
                            # Cria pool de conexões
                            # minconn: mínimo de conexões no pool (2)
                            # maxconn: máximo de conexões no pool (20)
                            # Isso evita criar/fechar conexões a cada request
                            PostgresContext._connection_pool = pool.ThreadedConnectionPool(
                                minconn=2,
                                maxconn=20,
                                host=host,
                                dbname=database,
                                user=user,
                                port=port,
                                password=password
                            )
                            
                    except Exception as e:
                        raise ConnectionError(f"Erro ao criar pool de conexões: {e}") from e
    
    def _get_connection_pool(self):
        """Retorna o pool de conexões (deve ser inicializado via _initialize_pool)"""
        if PostgresContext._connection_pool is None:
            # Se o pool não foi inicializado, tenta inicializar agora
            self._initialize_pool()
        return PostgresContext._connection_pool
    
    def connect(self, asdict: bool | None = None):
        '''Obtém uma conexão do pool'''
        try:
            pool = self._get_connection_pool()
            connection = pool.getconn()
            
            if connection is None:
                raise ConnectionError("Não foi possível obter conexão do pool")
            
            cursor = connection.cursor()
            database_name = PostgresContext._connection_params.get('database') if PostgresContext._connection_params else 'N/A'
            return cursor, connection
            
        except pool.PoolError as e:
            raise ConnectionError(f"Erro ao obter conexão do pool: {e}") from e
        except Exception as e:
            raise ConnectionError(f"Erro ao conectar ao banco de dados: {e}") from e

    def disconnect(self, connection) -> None:
        """
        Retorna a conexão para o pool (não fecha, apenas retorna para reuso).
        
        Args:
            connection: Objeto de conexão PostgreSQL
        """
        try:
            if connection and not connection.closed:
                # Retorna conexão para o pool (não fecha)
                PostgresContext._connection_pool.putconn(connection)
        except Exception as e:
            # Se houver erro ao retornar, tenta fechar a conexão
            try:
                if connection and not connection.closed:
                    connection.close()
            except:
                pass
    
    @classmethod
    def close_all_connections(cls):
        """
        Fecha todas as conexões do pool.
        Útil para shutdown graceful da aplicação.
        """
        if cls._connection_pool:
            try:
                cls._connection_pool.closeall()
            except Exception as e:
                return "Erro ao fechar pool de conexões: {e}"