# app/database.py

import sqlite3
import io
import csv
from flask import send_file
from datetime import datetime
from . import config

# --- Setup ---
def init_db():
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER,
            timestamp TEXT,
            temperature REAL,
            humidity REAL
        )
    """)
    conn.commit()
    conn.close()

# --- Schreiben ---
def store_reading(sensor_id, timestamp, temperature, humidity):
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO readings (sensor_id, timestamp, temperature, humidity) VALUES (?, ?, ?, ?)",
        (sensor_id, timestamp, temperature, humidity)
    )
    conn.commit()
    conn.close()

# --- Lesen ---
def get_readings(limit=100):
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT sensor_id, timestamp, temperature, humidity FROM readings ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_latest_by_sensor(sensor_id):
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, temperature, humidity FROM readings WHERE sensor_id = ? ORDER BY id DESC LIMIT 1",
        (sensor_id,)
    )
    row = c.fetchone()
    conn.close()
    return row

def get_latest_readings():
    """Letzte Messwerte pro Sensor als Dict {sensor_id: {...}}."""
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    rows = c.execute("""
        SELECT sensor_id, timestamp, temperature, humidity
        FROM readings
        WHERE id IN (
            SELECT MAX(id) FROM readings GROUP BY sensor_id
        )
    """).fetchall()
    conn.close()
    # Keys als Strings
    return {str(sensor_id): {"timestamp": ts, "temp": temp, "hum": hum} for sensor_id, ts, temp, hum in rows}


# --- Wartung ---
def clear_data():
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM readings")
    conn.commit()
    conn.close()

def csvdump():
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    rows = c.execute("SELECT timestamp, sensor_id, temperature, humidity FROM readings ORDER BY timestamp ASC").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "sensor_id", "temperature", "humidity"])
    writer.writerows(rows)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        download_name="sensor_data.csv",
        as_attachment=True
    )

def today_readings():
    today_start = datetime.combine(datetime.today(), datetime.min.time())
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    rows = c.execute(
        "SELECT timestamp, sensor_id, temperature, humidity FROM readings WHERE timestamp >= ? ORDER BY timestamp ASC",
        (today_start.strftime("%Y-%m-%d %H:%M:%S"),)
    ).fetchall()
    conn.close()
    return rows
