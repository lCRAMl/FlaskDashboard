# app/routes.py

from flask import Blueprint, render_template, jsonify, send_from_directory
from . import database, config

routes = Blueprint("routes", __name__)

# --- Startseite ---
@routes.route("/")
def index():
    readings = database.get_readings(limit=20)

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
    latest = database.get_latest_readings()  # dict {sensor: {timestamp, temp, hum}}
    # Schlüssel anpassen für JS: temp/hum statt temperature/humidity
    result = {
    str(sid): {
        "timestamp": vals["timestamp"],
        "temp": vals["temp"],
        "hum": vals["hum"]
    }
    for sid, vals in latest.items()
    }
    return jsonify(result)


# --- Verlauf für Charts ---
@routes.route("/history")
def history():
    rows = database.today_readings()  # [(timestamp, sensor_id, temp, hum), ...]

    grouped = {}
    for ts, sensor, temp, hum in rows:
        grouped.setdefault(sensor, {"timestamps": [], "temp": [], "hum": []})
        grouped[sensor]["timestamps"].append(ts)
        grouped[sensor]["temp"].append(temp)
        grouped[sensor]["hum"].append(hum)

    def downsample(timestamps, values):
        n = len(values)
        if n <= config.MAX_CHART_POINTS:
            return timestamps, values
        step = n / config.MAX_CHART_POINTS
        ts_ds, val_ds = [], []
        for i in range(config.MAX_CHART_POINTS):
            start, end = int(i * step), int((i + 1) * step)
            window_vals, window_ts = values[start:end], timestamps[start:end]
            if not window_vals:
                continue
            min_idx = window_vals.index(min(window_vals))
            max_idx = window_vals.index(max(window_vals))
            ts_ds.extend([window_ts[min_idx], window_ts[max_idx]])
            val_ds.extend([window_vals[min_idx], window_vals[max_idx]])
        return ts_ds, val_ds

    data = {}
    for sensor, vals in grouped.items():
        ts_ds, temp_ds = downsample(vals["timestamps"], vals["temp"])
        _, hum_ds = downsample(vals["timestamps"], vals["hum"])
        data[sensor] = {
            "timestamps": ts_ds,
            "temp": temp_ds,
            "hum": hum_ds,
        }

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
    latest = database.get_latest_by_sensor(sensor_id)
    return render_template("sensor.html", sensor_id=sensor_id, latest=latest)

# --- API für externe Tools ---
@routes.route("/api/readings")
def api_readings():
    rows = database.get_readings(limit=100)
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
