import logging
import os

from app import create_app

# Surface the app's INFO logs (schema sync, daily backups) in the console and
# the host's log viewer. Keep startup log messages ASCII (Windows cp1252).
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = create_app()

if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
