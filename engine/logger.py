import os
import logging
import sqlite3
import queue
import threading
from .config_loader import cfg_get

class WorldLogger:
    _logger = None
    _log_queue = queue.Queue()
    _log_thread = None
    _db_path = "database/openworld.db"

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
        WorldLogger._log_queue.put((npc_id, level, msg))

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
    def debug(msg: str, npc = None):
        """Log detalhado - Apenas no arquivo de log (DEBUG)."""
        WorldLogger.get_logger().debug(msg)
        if npc:
            WorldLogger.queue_db_log(npc, "DEBUG", msg)

    @staticmethod
    def info(msg: str, npc = None):
        """Log geral - Vai para console e arquivo (INFO)."""
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
