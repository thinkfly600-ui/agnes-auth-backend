# Agnes AI Auth Backend - WSGI Entry
from server import app, init_db

# Initialize database on first import
init_db()

if __name__ == "__main__":
    app.run()