# app/sensors.py

import smbus2, bme280, time, threading, os
from datetime import datetime
from . import database   # dein database.py nutzen

# --- Einstellungen ---
I2C_BUS = 1
MUX_ADDR = 0x70
SENSOR_CHANNELS = [0, 1]   # PCA9548A Kanäle, wo Sensoren hängen
MAX_POINTS = 100           # Max. Punkte für Live-Daten
DEBUG = True               # False = Fehler ignorieren, True = Fehler anzeigen

# --- Globale Variablen ---
bus = smbus2.SMBus(I2C_BUS)
live_data = {}
sensor_map = {}  # { (channel, addr): "Sensorname" }

# --- Multiplexer auswählen ---
def select_channel(channel: int):
    bus.write_byte(MUX_ADDR, 1 << channel)

# --- BME280 auslesen ---
def read_bme280(address):
    try:
        cal_params = bme280.load_calibration_params(bus, address)
        data = bme280.sample(bus, address, cal_params)
        return round(data.temperature, 2), round(data.humidity, 2)
    except Exception as e:
        if DEBUG:
            print(f"[ERROR] Sensor {hex(address)}: {e}")
        return None, None

# --- Sensoren initialisieren ---
def init_sensors():
    global sensor_map, live_data
    sensor_map.clear()
    live_data.clear()

    sensor_count = 0
    for channel in SENSOR_CHANNELS:
        select_channel(channel)
        for addr in [0x76, 0x77]:
            try:
                bus.read_byte(addr)  # Test, ob Device antwortet
                sensor_count += 1
                name = f"CH{channel}-{hex(addr)}"
                sensor_map[(channel, addr)] = name
                live_data[name] = []
            except Exception as e:
                if DEBUG:
                    print(f"[WARN] Kein Sensor auf CH{channel}, {hex(addr)}")

    print(f"[INFO] Gefundene Sensoren: {list(sensor_map.values())}")

# --- Endlosschleife im Thread ---
def sensor_loop():
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for (channel, addr), sensor_id in sensor_map.items():
            try:
                select_channel(channel)
                temp, hum = read_bme280(addr)
                if temp is None: continue

                live_data[sensor_id].append({"time": timestamp, "temperature": temp, "humidity": hum})
                if len(live_data[sensor_id]) > MAX_POINTS:
                    live_data[sensor_id].pop(0)

                database.store_reading(sensor_id, timestamp, temp, hum)
            except Exception as e:
                if DEBUG: print(f"[ERROR] Sensorloop {sensor_id}: {e}")

        time.sleep(5)  # alle 5 Sekunden


# --- Thread starten ---
def start_loop():
    t = threading.Thread(target=sensor_loop, daemon=True)
    t.start()
