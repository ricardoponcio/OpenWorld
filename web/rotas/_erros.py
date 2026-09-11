from flask import jsonify, request
from engine.logger import WorldLogger


def registrar_erro_handler(bp):
    """Único tratador de erro por blueprint (R-D07) — substitui os 10 blocos idênticos
    `except Exception as e: return jsonify({"error": str(e)}), 500` que existiam
    espalhados por cada rota em `composed_routes.py`."""
    @bp.errorhandler(Exception)
    def erro_inesperado(e):
        WorldLogger.error(f"[API] {request.path}: {e}")
        return jsonify({"error": str(e)}), 500
