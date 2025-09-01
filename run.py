# /run.py

from app import create_app, sensors, database, stream
import threading
import signal
import sys

app = create_app()

def start_sensors():
    sensors.init_sensors()
    sensors.start_loop()

def start_stream():
    stream.start_hls_stream()

# --- Signal-Handler zum sauberen Beenden ---
def handle_exit(sig, frame):
    print("[INFO] Beenden...")
    stream.stop_hls_stream()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

if __name__ == "__main__":
    # DB initialisieren
    database.init_db()

    # Sensorloop Thread
    sensor_thread = threading.Thread(target=start_sensors, daemon=True)
    sensor_thread.start()

    # Stream Thread
    stream_thread = threading.Thread(target=start_stream, daemon=True)
    stream_thread.start()

    print("[INFO] Flask-App starten...")
    # Flask läuft im Main-Thread, Debug=True optional
    app.run(threaded=True, debug=True, host="0.0.0.0")
