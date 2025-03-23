import os
from rq import Worker, Queue
from redis import Redis
from app import create_app

# Conexão com Redis
redis_conn = Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
q = Queue(connection=redis_conn)

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        worker = Worker([q], connection=redis_conn)
        worker.work()