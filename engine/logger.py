import os
import logging
import sqlite3
import queue
import threading
from .config_loader import cfg_get

class WorldLogger:
    _logger = None
    # A07 (docs/PLANO_POPULACAO_E_ESCALA.md): teto na fila — um avanço rápido produz
    # logs muito mais rápido do que a thread consumidora consegue committar (um
    # commit por linha). Sem teto, isso é vazamento de memória com outro nome, e a
    # thread engolia toda exceção em silêncio (`except Exception: pass`), então até
    # aqui isso falhava sem deixar rastro.
    _MAXSIZE_FILA_LOG = 10000
    _log_queue = queue.Queue(maxsize=_MAXSIZE_FILA_LOG)
    _fila_cheia_avisada = False
    _log_thread = None
    _db_path = "database/openworld.db"
    # A07: suprime info/debug (mantém warning/error e `evento_mundo`) — sem isto,
    # `_avancar_relogio` sozinho loga um cabeçalho de tick por minuto simulado, e um
    # avanço de 7 dias são 10.080 linhas só do cabeçalho.
    _modo_avanco_rapido = False

    @staticmethod
    def _log_worker():
        conn = None
        while True:
            try:
                item = WorldLogger._log_queue.get()
                if item is None:
                    break
                npc_id, level, message = item
                
                if conn is None:
                    db_dir = os.path.dirname(WorldLogger._db_path)
                    if db_dir:
                        os.makedirs(db_dir, exist_ok=True)
                    conn = sqlite3.connect(WorldLogger._db_path)
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                    cursor = conn.cursor()
                
                cursor.execute(
                    'INSERT INTO npc_logs (npc_id, level, message) VALUES (?, ?, ?)',
                    (npc_id, level, message)
                )
                conn.commit()
            except Exception as e:
                # Silently catch exceptions to not disrupt simulation
                pass
            finally:
                WorldLogger._log_queue.task_done()
        if conn:
            conn.close()

    @staticmethod
    def start_db_logger():
        if WorldLogger._log_thread is None:
            # Set the DB path dynamically and absolute to be robust
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            WorldLogger._db_path = os.path.join(base_dir, "database", "openworld.db")
            
            WorldLogger._log_thread = threading.Thread(target=WorldLogger._log_worker, daemon=True)
            WorldLogger._log_thread.start()

    _npc_logging_enabled = None
    _last_config_check = 0

    @staticmethod
    def is_npc_logging_enabled():
        import time
        now = time.time()
        if WorldLogger._npc_logging_enabled is None or now - WorldLogger._last_config_check > 5.0:
            WorldLogger._last_config_check = now
            try:
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                config_path = os.path.join(base_dir, "config.json")
                if os.path.exists(config_path):
                    import json
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    # default=True: fallback de sistema — logger não deve parar a simulação
                    WorldLogger._npc_logging_enabled = cfg_get(cfg, "salvar_logs_npc_no_banco", default=True)
                else:
                    WorldLogger._npc_logging_enabled = True
            except Exception:
                WorldLogger._npc_logging_enabled = True
        return WorldLogger._npc_logging_enabled

    @staticmethod
    def queue_db_log(npc, level, msg):
        if not WorldLogger.is_npc_logging_enabled():
            return
        if npc is None:
            return
        npc_id = getattr(npc, 'id', str(npc))
        if not npc_id:
            return
        
        WorldLogger.start_db_logger()
        try:
            WorldLogger._log_queue.put_nowait((npc_id, level, msg))
        except queue.Full:
            if not WorldLogger._fila_cheia_avisada:
                WorldLogger._fila_cheia_avisada = True
                WorldLogger.get_logger().warning(
                    f"[LOGGER] Fila de log do banco cheia ({WorldLogger._MAXSIZE_FILA_LOG}) — "
                    "descartando logs excedentes daqui pra frente. O avanço/tick está "
                    "produzindo log mais rápido do que a thread consegue gravar.")

    @staticmethod
    def get_logger():
        if WorldLogger._logger is None:
            # Garantir pasta de logs
            log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "world.log")

            logger = logging.getLogger("OpenWorld")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False

            # Limpar handlers anteriores
            if logger.handlers:
                logger.handlers.clear()

            # 1. File Handler (Salva TUDO - Nível DEBUG)
            file_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # 2. Console Handler (Apenas eventos importantes - Nível INFO)
            console_formatter = logging.Formatter('%(message)s')
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

            WorldLogger._logger = logger

        return WorldLogger._logger

    @staticmethod
    def ativar_modo_avanco_rapido() -> None:
        """A07: suprime `debug`/`info` — usado por `bench_avanco.py` e pelo avanço
        rápido do Modo Mestre. `evento_mundo`, `warning` e `error` continuam saindo:
        é o que dá pra acompanhar a história do mundo (nascimento, morte, casamento,
        obra, expansão) e os problemas de verdade, mesmo com o resto suprimido."""
        WorldLogger._modo_avanco_rapido = True

    @staticmethod
    def desativar_modo_avanco_rapido() -> None:
        WorldLogger._modo_avanco_rapido = False

    @staticmethod
    def debug(msg: str, npc = None):
        """Log detalhado - Apenas no arquivo de log (DEBUG)."""
        if WorldLogger._modo_avanco_rapido:
            return
        WorldLogger.get_logger().debug(msg)
        if npc:
            WorldLogger.queue_db_log(npc, "DEBUG", msg)

    @staticmethod
    def info(msg: str, npc = None):
        """Log geral - Vai para console e arquivo (INFO)."""
        if WorldLogger._modo_avanco_rapido:
            return
        WorldLogger.get_logger().info(msg)
        if npc:
            WorldLogger.queue_db_log(npc, "INFO", msg)

    @staticmethod
    def evento_mundo(msg: str, npc = None):
        """A07: eventos de mundo que sobrevivem ao modo de avanço rápido —
        nascimento, morte, casamento, obra concluída, expansão urbana. Use no lugar
        de `info` exatamente nesses pontos; qualquer outra notificação de rotina
        continua em `info`/`debug` (suprimíveis)."""
        WorldLogger.get_logger().info(msg)
        if npc:
            WorldLogger.queue_db_log(npc, "INFO", msg)

    @staticmethod
    def warning(msg: str, npc = None):
        """Alertas leves - Console e arquivo (WARNING)."""
        WorldLogger.get_logger().warning(msg)
        if npc:
            WorldLogger.queue_db_log(npc, "WARNING", msg)

    @staticmethod
    def error(msg: str, npc = None):
        """Erros - Console e arquivo (ERROR)."""
        WorldLogger.get_logger().error(msg)
        if npc:
            WorldLogger.queue_db_log(npc, "ERROR", msg)

    @staticmethod
    def deve_logar_amostra(tick_count: int, config: dict) -> bool:
        """Amostragem de log de ação (R-B10): um tick é 1 minuto de jogo — logar toda
        ação de todo NPC a cada tick inunda o arquivo. Substitui o `% 4` solto que
        estava copiado em 5 lugares (`actions.py` x4, `kingdom.py` x1)."""
        n = cfg_get(config, "observabilidade", "log_acao_a_cada_n_ticks")
        return tick_count % n == 0
