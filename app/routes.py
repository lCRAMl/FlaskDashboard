# app/routes.py

from flask import Blueprint, render_template, jsonify, send_from_directory, request
from . import database, config, systeminfo

routes = Blueprint("routes", __name__)

# --- Startseite ---
@routes.route("/")
def index():
    readings = database.get_last_bme_readings(limit=20)

    # Alle Sensor-IDs aus der Datenbank ermitteln (oder fest definieren)
    sensor_ids = sorted(list({row[0] for row in readings}))  # {sensor_id, ...} → Liste

    return render_template("index.html", readings=readings, SENSOR_NAMES=sensor_ids)

# --- HLS Stream-Dateien ---
@routes.route("/hls/<path:filename>")
def hls_files(filename):
    return send_from_directory(config.OUTPUT_DIR, filename)


# --- Letzte Werte aller Sensoren ---
@routes.route("/data")
def data():
    since = request.args.get("since")  # optional von Frontend übergeben
    bme = database.get_latest_readings(since)
    bme["Shelly"] = database.get_latest_shelly(config.SHELLY_ID)
    bme["Pi"] = systeminfo.get_pi_stats()
    return jsonify(bme)



# --- Verlauf für Charts ---
@routes.route("/history")
def history():
    rows = database.get_last_bme_readings(config.MAX_CHART_POINTS * 10)

    grouped = {}
    for ts, sensor, temp, hum in rows:
        grouped.setdefault(sensor, {"timestamps": [], "temp": [], "hum": []})
        grouped[sensor]["timestamps"].append(ts)
        grouped[sensor]["temp"].append(temp)
        grouped[sensor]["hum"].append(hum)

    data = {s: {
                "timestamps": vals["timestamps"][-config.MAX_CHART_POINTS:],
                "temp": vals["temp"][-config.MAX_CHART_POINTS:],
                "hum": vals["hum"][-config.MAX_CHART_POINTS:],
             } for s, vals in grouped.items()}

    if not data:
        data = {"default": {"timestamps": [], "temp": [], "hum": []}}
        
    # Pi-Info hinzufügen (ohne Historie, nur aktueller Wert)
    data["Pi"] = systeminfo.get_pi_stats()

    return jsonify(data)


# --- DB zurücksetzen ---
@routes.route("/clear", methods=["POST"])
def clear_db():
    database.clear_data()
    return jsonify({"status": "ok"})

# --- Export als CSV ---
@routes.route("/export")
def export_csv():
    return database.csvdump()

# --- Einzelner Sensor ---
@routes.route("/sensor/<int:sensor_id>")
def sensor_detail(sensor_id):
    latest = database.get_latest_bme_by_sensorid(sensor_id)
    return render_template("sensor.html", sensor_id=sensor_id, latest=latest)

# --- API für externe Tools ---
@routes.route("/api/readings")
def api_readings():
    rows = database.get_last_bme_readings(limit=100)
    readings = [
        {
            "sensor": row[0],
            "timestamp": row[1],
            "temperature": row[2],
            "humidity": row[3],
        }
        for row in rows
    ]
    return jsonify(readings)

# --- Healthcheck ---
@routes.route("/ping")
def ping():
    return {"status": "ok"}
