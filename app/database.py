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
    # Tabelle für BME280
    c.execute("""
        CREATE TABLE IF NOT EXISTS bme_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL
        )
    """)

    # Tabelle für Shelly
    c.execute("""
        CREATE TABLE IF NOT EXISTS shelly_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id TEXT,
            timestamp TEXT,
            apower REAL,
            aenergy REAL,
            temperature REAL
        )
    """)
    conn.commit()
    conn.close()

# --- BME Schreiben ---
def store_bme_reading(sensor_id, timestamp, temperature=None, humidity=None):
    if temperature is None and humidity is None:
        return
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO bme_readings (sensor_id, timestamp, temperature, humidity) VALUES (?, ?, ?, ?)",
        (sensor_id, timestamp, temperature, humidity)
    )
    conn.commit()
    conn.close()

# --- Shelly Schreiben ---
def store_shelly_reading(sensor_id, timestamp, apower=None, aenergy=None, temperature=None):
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO shelly_readings (sensor_id, timestamp, apower, aenergy, temperature) VALUES (?, ?, ?, ?, ?)",
        (sensor_id, timestamp, apower, aenergy, temperature)
    )
    conn.commit()
    conn.close()

# --- BME Lesen ---
def get_last_bme_readings(limit=1000):
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute("""
    SELECT timestamp, sensor_id, temperature, humidity
    FROM (
        SELECT * FROM bme_readings ORDER BY id DESC LIMIT ?
    ) sub
    ORDER BY id ASC
    """, (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_latest_bme_by_sensorid(sensor_id):
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, temperature, humidity FROM bme_readings WHERE sensor_id = ? ORDER BY id DESC LIMIT 1",
        (sensor_id,)
    )
    row = c.fetchone()
    conn.close()
    return row

def get_latest_readings(since=None):
    """
    Gibt für jeden Sensor den neuesten Wert zurück.
    Falls seit `since` nichts Neues kam, wird der letzte bekannte Wert geliefert.
    """
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()

    result = {}

    if since:
        # 1. Neue Werte seit 'since'
        c.execute("""
            SELECT sensor_id, MAX(timestamp), temperature, humidity
            FROM bme_readings
            WHERE timestamp > ?
            GROUP BY sensor_id
        """, (since,))
        rows_new = c.fetchall()

        # Neue Werte in Ergebnis übernehmen
        for sensor_id, ts, temp, hum in rows_new:
            result[str(sensor_id)] = {
                "timestamp": ts,
                "temp": temp,
                "hum": hum
            }

        # 2. Für Sensoren ohne neue Werte: letzten bekannten Wert davor
        c.execute("""
            SELECT sensor_id, timestamp, temperature, humidity
            FROM bme_readings
            WHERE id IN (
                SELECT MAX(id) FROM bme_readings GROUP BY sensor_id
            )
        """)
        rows_last = c.fetchall()

        for sensor_id, ts, temp, hum in rows_last:
            if str(sensor_id) not in result:  # nur ergänzen, wenn kein neuer Wert existiert
                result[str(sensor_id)] = {
                    "timestamp": ts,
                    "temp": temp,
                    "hum": hum
                }

    else:
        # Ohne since → letzter Wert pro Sensor
        c.execute("""
            SELECT sensor_id, timestamp, temperature, humidity
            FROM bme_readings
            WHERE id IN (
                SELECT MAX(id) FROM bme_readings GROUP BY sensor_id
            )
        """)
        rows = c.fetchall()
        for sensor_id, ts, temp, hum in rows:
            result[str(sensor_id)] = {
                "timestamp": ts,
                "temp": temp,
                "hum": hum
            }

    conn.close()
    return result



# --- Wartung ---
def clear_data():
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM bme_readings")
    conn.commit()
    conn.close()
    init_db()

def csvdump():
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    rows = c.execute("SELECT timestamp, sensor_id, temperature, humidity FROM bme_readings ORDER BY timestamp ASC").fetchall()
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
        "SELECT timestamp, sensor_id, temperature, humidity FROM bme_readings WHERE timestamp >= ? ORDER BY timestamp ASC",
        (today_start.strftime("%Y-%m-%d %H:%M:%S"),)
    ).fetchall()
    conn.close()
    return rows


def get_latest_shelly(sensor_id):
    conn = sqlite3.connect(config.DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, apower, aenergy, temperature FROM shelly_readings WHERE sensor_id = ? ORDER BY id DESC LIMIT 1",
        (sensor_id,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    ts, apower, aenergy, temp = row
    return {"timestamp": ts, "apower": apower, "aenergy": aenergy, "temp": temp}
