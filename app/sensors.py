# app/sensors.py

import smbus2, bme280, time, threading, os
from datetime import datetime
from . import database, config  # dein database.py nutzen
import requests

# --- Einstellungen ---
I2C_BUS = 1
MUX_ADDR = 0x70
SENSOR_CHANNELS = [0, 1]   # PCA9548A Kanäle, wo Sensoren hängen
DEBUG = True               # False = Fehler ignorieren, True = Fehler anzeigen

# --- Globale Variablen ---
bus = smbus2.SMBus(I2C_BUS)
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
    global sensor_map
    sensor_map.clear()

    sensor_count = 0
    for channel in SENSOR_CHANNELS:
        select_channel(channel)
        for addr in [0x76, 0x77]:
            try:
                bus.read_byte(addr)  # Test, ob Device antwortet
                sensor_count += 1
                name = f"CH{channel}-{hex(addr)}"
                sensor_map[(channel, addr)] = name
            except Exception as e:
                if DEBUG:
                    print(f"[WARN] Kein Sensor auf CH{channel}, {hex(addr)}")

    print(f"[INFO] Gefundene Sensoren: {list(sensor_map.values())}")

# --- Endlosschleife im Thread ---
def bme_sensor_loop():
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for (channel, addr), sensor_id in sensor_map.items():
            try:
                select_channel(channel)
                temp, hum = read_bme280(addr)
                if temp is None: continue

                database.store_bme_reading(sensor_id, timestamp, temp, hum)
            except Exception as e:
                if DEBUG: print(f"[ERROR] Sensorloop {sensor_id}: {e}")

        time.sleep(20)  # kleiner als die updatezeit im JS halten damit immer was neues da ist



# --- Shelly lesen ---
def read_shelly():
    try:
        url = f"http://{config.SHELLY_IP}/rpc/Switch.GetStatus?id=0"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        # relevante Werte
        apower = data.get("apower", 0.0)
        energie_total = data.get("aenergy", {}).get("total", 0.0)
        temperatur = data.get("temperature", {}).get("tC", 0.0)
        return apower, energie_total, temperatur
    except Exception as e:
        if DEBUG:
            print(f"[ERROR] Shelly read failed: {e}")
        return None, None, None


# --- Endlosschleife im Thread für Shelly ---
def shelly_loop():
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        apower, energie_total, temperatur = read_shelly()
        if apower is not None:
            # Werte in DB speichern, ähnlich wie bei BME280
            # Wir speichern hier drei Spalten: Leistung, Energie, Temperatur
            database.store_shelly_reading(config.SHELLY_ID, timestamp,
                              apower=apower,
                              aenergy=energie_total,
                              temperature=temperatur)
        time.sleep(60)




# --- Thread starten ---
def start_loop():
    t = threading.Thread(target=bme_sensor_loop, daemon=True)
    t.start()
    s = threading.Thread(target=shelly_loop, daemon=True)
    s.start()
