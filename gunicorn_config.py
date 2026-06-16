import os

# Server socket
bind = "127.0.0.1:5100"
workers = 2
worker_class = "sync"
timeout = 120

# Logging
accesslog = os.path.join(os.path.dirname(__file__), "logs", "access.log")
errorlog = os.path.join(os.path.dirname(__file__), "logs", "error.log")
loglevel = "info"

# Process naming
proc_name = "agnes-auth-backend"