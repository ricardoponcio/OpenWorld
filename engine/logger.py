import os
import logging

class WorldLogger:
    _logger = None

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
    def debug(msg: str):
        """Log detalhado - Apenas no arquivo de log (DEBUG)."""
        WorldLogger.get_logger().debug(msg)

    @staticmethod
    def info(msg: str):
        """Log geral - Vai para console e arquivo (INFO)."""
        WorldLogger.get_logger().info(msg)

    @staticmethod
    def warning(msg: str):
        """Alertas leves - Console e arquivo (WARNING)."""
        WorldLogger.get_logger().warning(msg)

    @staticmethod
    def error(msg: str):
        """Erros - Console e arquivo (ERROR)."""
        WorldLogger.get_logger().error(msg)
