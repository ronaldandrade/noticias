import os

timeout = 120
workers = 1
worker_class = "sync"
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"