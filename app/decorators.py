import hmac
import os
from functools import wraps

from flask import jsonify, request


def require_cron_secret(f):
    """Protege endpoints operacionais com o header X-Cron-Secret.

    Se CRON_SECRET não estiver definido, o endpoint fica bloqueado.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        esperado = os.environ.get("CRON_SECRET", "")
        recebido = request.headers.get("X-Cron-Secret", "")
        if not esperado or not hmac.compare_digest(recebido, esperado):
            return jsonify({"erro": "não autorizado"}), 401
        return f(*args, **kwargs)
    return decorated
