# Growbox Dashboard
# v0.1 - Erste Version mit DHT22 und Chart.js
# v0.2 - Mehrere Sensoren, MUX-Support
# v0.3 - Chart.js, CSV-Export, DB-Cleanup
# v0.4 - BME280-Support, SQLite, Chart-Redesign
# v0.4.3 - Komplettes Redesign mit ApexCharts, HLS-Stream, SQLite, MUX-Support
 

#!/usr/bin/env python3
from flask import Flask, render_template_string, jsonify, send_from_directory, send_file
import smbus2, bme280, time, sqlite3, csv, io
import threading, os, subprocess
from datetime import datetime, timedelta

MAX_POINTS = 100
MAX_CHART_POINTS = 500
DB_FILE = 'sensors.db'

app = Flask(__name__)

# --- I2C / MUX ---
I2C_BUS = 1
MUX_ADDR = 0x70
bus = smbus2.SMBus(I2C_BUS)

SENSORS = [(0, 0x76), (0, 0x77)]

# --- Live-Daten ---
live_data = {"timestamps": [], "temperature": {}, "humidity": {}, "pressure": {}}
for i, (ch, addr) in enumerate(SENSORS, start=1):
    name = f"Sensor {i} (CH{ch}, 0x{addr:02X})"
    live_data["temperature"][name] = []
    live_data["humidity"][name] = []
    live_data["pressure"][name] = []

# --- Datenbank ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS readings (
                        timestamp DATETIME,
                        sensor TEXT,
                        temperature REAL,
                        humidity REAL,
                        pressure REAL
                        )''')

def cleanup_old_data():
    cutoff = datetime.now() - timedelta(days=40)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff,))

def store_reading(sensor_name, data):
    cleanup_old_data()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO readings VALUES (?,?,?,?,?)",
                     (ts, sensor_name, data['temp'], data['humidity'], data['pressure']))

# --- BME280 ---
_cal_cache = {}
def select_channel(channel: int):
    bus.write_byte(MUX_ADDR, 1 << channel)
    time.sleep(0.01)

def read_bme280(channel, addr):
    select_channel(channel)
    if (channel, addr) not in _cal_cache:
        _cal_cache[(channel, addr)] = bme280.load_calibration_params(bus, addr)
    data = bme280.sample(bus, addr, _cal_cache[(channel, addr)])
    return {"temp": round(data.temperature,1), "humidity": round(data.humidity,1), "pressure": round(data.pressure,1)}

# --- Sensor-Hintergrundthread ---
def sensor_loop():
    while True:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        live_data["timestamps"].append(ts)
        if len(live_data["timestamps"]) > MAX_POINTS:
            live_data["timestamps"].pop(0)
        for i, (ch, addr) in enumerate(SENSORS, start=1):
            name = f"Sensor {i} (CH{ch}, 0x{addr:02X})"
            try:
                val = read_bme280(ch, addr)
                live_data["temperature"][name].append(val["temp"])
                live_data["humidity"][name].append(val["humidity"])
                live_data["pressure"][name].append(val["pressure"])
                if len(live_data["temperature"][name]) > MAX_POINTS:
                    live_data["temperature"][name].pop(0)
                    live_data["humidity"][name].pop(0)
                    live_data["pressure"][name].pop(0)
                store_reading(name, val)
            except Exception as e:
                print(f"Fehler Sensor {name}: {e}")
        time.sleep(3)

# --- Flask Routes ---
@app.route("/data")
def data():
    latest_ts = live_data["timestamps"][-1] if live_data["timestamps"] else ""
    result = {sensor:{
        "temp": live_data["temperature"][sensor][-1] if live_data["temperature"][sensor] else None,
        "hum": live_data["humidity"][sensor][-1] if live_data["humidity"][sensor] else None,
        "pressure": live_data["pressure"][sensor][-1] if live_data["pressure"][sensor] else None,
        "timestamp": latest_ts
    } for sensor in live_data["temperature"]}
    return jsonify(result)

@app.route("/history")
def history():
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT timestamp, sensor, temperature, humidity FROM readings WHERE timestamp >= ? ORDER BY timestamp ASC",
            (today_start.strftime("%Y-%m-%d %H:%M:%S"),)
        ).fetchall()
    grouped = {}
    for ts, sensor, temp, hum in rows:
        grouped.setdefault(sensor, {"timestamps": [], "temp": [], "hum": []})
        grouped[sensor]["timestamps"].append(ts)
        grouped[sensor]["temp"].append(temp)
        grouped[sensor]["hum"].append(hum)

    def downsample(timestamps, values):
        n = len(values)
        if n <= MAX_CHART_POINTS: return timestamps, values
        step = n / MAX_CHART_POINTS
        ts_ds, val_ds = [], []
        for i in range(MAX_CHART_POINTS):
            start, end = int(i*step), int((i+1)*step)
            window_vals, window_ts = values[start:end], timestamps[start:end]
            if not window_vals: continue
            min_idx, max_idx = window_vals.index(min(window_vals)), window_vals.index(max(window_vals))
            ts_ds.extend([window_ts[min_idx], window_ts[max_idx]])
            val_ds.extend([window_vals[min_idx], window_vals[max_idx]])
        return ts_ds, val_ds

    data = {}
    for sensor, vals in grouped.items():
        ts_ds, temp_ds = downsample(vals["timestamps"], vals["temp"])
        _, hum_ds = downsample(vals["timestamps"], vals["hum"])
        data[sensor] = {"timestamps": ts_ds, "temp": temp_ds, "hum": hum_ds}
    return jsonify(data)

@app.route("/clear", methods=["POST"])
def clear_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM readings")
    live_data["timestamps"].clear()
    for sensor in live_data["temperature"]:
        live_data["temperature"][sensor].clear()
        live_data["humidity"][sensor].clear()
        live_data["pressure"][sensor].clear()
    return jsonify({"status":"ok"})

@app.route("/export")
def export_csv():
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute("SELECT * FROM readings ORDER BY timestamp ASC").fetchall()
    output = io.StringIO()
    csv.writer(output).writerows([["timestamp","sensor","temperature","humidity","pressure"]]+rows)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", download_name="sensor_data.csv", as_attachment=True)

# --- HLS Stream ---
RTSP_URL = "rtsp://growbox:growbox1@192.168.178.55:554/stream1"
OUTPUT_DIR = "hls"

def start_hls_stream():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ffmpeg_cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-i", RTSP_URL,
        "-c:v", "copy",
        "-an",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "6",
        "-hls_flags", "delete_segments",
        f"{OUTPUT_DIR}/stream.m3u8"
    ]
    return subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@app.route("/hls/<path:filename>")
def hls_files(filename):
    return send_from_directory(OUTPUT_DIR, filename)

# --- HTML Template ---
template = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Growbox Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
body { font-family:'Segoe UI',sans-serif; text-align:center; background:#f0f2f5; margin:0; padding:20px;}
#averages { font-size:2em; margin-bottom:20px; color:#333; }
#stream { width:90%; max-width:800px; margin:auto; position:relative; margin-bottom:20px;}
#videoPlayer { width:100%; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,.3);}
#stream-placeholder { position:absolute; top:0; left:0; width:100%; height:100%; display:flex; align-items:center; justify-content:center; background:#000; color:#fff; font-size:1.2em; border-radius:12px; z-index:2; }
#dashboard {
    display: flex;
    flex-direction: row;   /* nebeneinander */
    align-items: flex-start;
    justify-content: flex-start;
    gap: 20px;             /* Abstand zwischen Spalten */
    max-width: 800px;
    margin: auto;
}
.sensor-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 200px;      /* Breite der linken Spalte */
}
.sensor { width:180px; min-width: 180px; max-width: 220px; padding:10px; border-radius:16px; color:#fff; box-shadow:0 4px 12px rgba(0,0,0,.2); transition: transform 0.3s; margin-bottom:10px; }
.sensor h2 {
    font-size: 1em;          /* Schriftgröße anpassen */
    margin: 0;
    word-break: break-word;   /* Zeilenumbruch bei langen Namen */
    text-align: center;       /* Name zentrieren */
}
.value { font-size:1.1em; margin:6px 0; font-weight:500; }
.chart-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    flex-grow: 1;          /* Charts nehmen Restbreite ein */
}
.chart { width:100%; max-width:100%; margin-bottom:20px;}
button { margin:5px; padding:8px 12px; border:none; border-radius:6px; cursor:pointer; background:#2196F3; color:#fff; font-weight:bold; margin-bottom:20px;}
</style>
</head>
<body>
<div id="averages">🌡 -- °C &nbsp;&nbsp; 💧 -- %</div>
<div id="stream">
  <div id="stream-placeholder">🔄 Lade Stream...</div>
  <video id="videoPlayer" controls autoplay muted playsinline></video>
</div>
<div>
<button onclick="clearDB()">Alle Werte löschen</button>
<button onclick="exportCSV()">CSV herunterladen</button>
</div>
<div id="dashboard">
    <div class="sensor-container" id="sensors"></div>
    <div class="chart-container">
        <div id="tempChart" class="chart"></div>
        <div id="humChart" class="chart"></div>
    </div>
</div>

<script>
const video = document.getElementById('videoPlayer');
const placeholder = document.getElementById('stream-placeholder');
const videoSrc = '/hls/stream.m3u8';

function hidePlaceholder() {
    placeholder.style.display = 'none';
}

// Sensor-Elemente
let sensors = {{ SENSOR_NAMES|tojson }};
let sensorElements = {};
let tempChart, humChart;

function initSensors(){
    const container = document.getElementById('sensors');
    sensors.forEach(name=>{
        const el = document.createElement('div');
        el.className = 'sensor';
        el.innerHTML = `<h2>${name}</h2>
                        <div class="value" id="${name}-temp"></div>
                        <div class="value" id="${name}-hum"></div>
                        <div class="value" id="${name}-press"></div>`;
        container.appendChild(el);
        sensorElements[name] = el;
    });
}

function tempColor(t){ if(t===null) return '#9e9e9e'; let hue=240-(Math.min(Math.max(t,0),40)/40*240); return `hsl(${hue},70%,50%)`; }
function humColor(h){ if(h===null) return '#9e9e9e'; let l=90-(Math.min(Math.max(h,0),100)/100*60); return `hsl(200,70%,${l}%)`; }

function updateAverages(data){
    let tempSum = 0, humSum = 0, count = 0;
    Object.values(data).forEach(v => { if(v.temp !== null && v.hum !== null){ tempSum += v.temp; humSum += v.hum; count++; } });
    const avgTemp = count ? (tempSum/count).toFixed(1) : '--';
    const avgHum  = count ? (humSum/count).toFixed(1) : '--';
    document.getElementById('averages').innerHTML = `🌡 ${avgTemp} °C &nbsp;&nbsp; 💧 ${avgHum} %`;
}

async function updateData(){
    try{
        const res = await fetch('/data'); const data = await res.json();
        updateAverages(data);
        for(let name in data){
            const el = sensorElements[name]; if(!el) continue;
            const v = data[name];
            el.style.background = `linear-gradient(135deg, ${tempColor(v.temp)}, ${humColor(v.hum)})`;
            document.getElementById(`${name}-temp`).innerText = `🌡 ${v.temp} °C`;
            document.getElementById(`${name}-hum`).innerText  = `💧 ${v.hum} %`;
            document.getElementById(`${name}-press`).innerText = `⏲ ${v.pressure} hPa`;
            const ts = new Date(v.timestamp).getTime();
            if(tempChart) tempChart.appendData([{data:[[ts,v.temp]]}]);
            if(humChart) humChart.appendData([{data:[[ts,v.hum]]}]);
        }
    }catch(e){ console.error(e); }
}

async function initDashboard() {
    // --- Charts wie vorher ---
    const res = await fetch('/history'); 
    const data = await res.json();
    let tempSeries = [], humSeries = [];
    for (let name in data) {
        let ts = data[name].timestamps.map(t => new Date(t).getTime());
        tempSeries.push({ name: name, data: data[name].temp.map((v,i)=>[ts[i],v]) });
        humSeries.push({ name: name, data: data[name].hum.map((v,i)=>[ts[i],v]) });
    }
    tempChart = new ApexCharts(document.querySelector("#tempChart"),{
        chart:{type:"line", height:300},
        series: tempSeries,
        xaxis:{type:'datetime'},
        yaxis:{min:15,max:35},
        title:{text:'Temperaturen'}
    });
    tempChart.render();
    humChart = new ApexCharts(document.querySelector("#humChart"),{
        chart:{type:"line", height:300},
        series: humSeries,
        xaxis:{type:'datetime'},
        yaxis:{min:20,max:80},
        title:{text:'Luftfeuchtigkeit'}
    });
    humChart.render();

    // --- Sensor-Kacheln mit letztem Messwert füllen ---
    try {
        const resData = await fetch('/data'); 
        const latestData = await resData.json();
        for (let name in latestData) {
            const el = sensorElements[name];
            if (!el) continue;
            const v = latestData[name];
            el.style.background = `linear-gradient(135deg, ${tempColor(v.temp)}, ${humColor(v.hum)})`;
            document.getElementById(`${name}-temp`).innerText = `🌡 ${v.temp} °C`;
            document.getElementById(`${name}-hum`).innerText = `💧 ${v.hum} %`;
            document.getElementById(`${name}-press`).innerText = `⏲ ${v.pressure} hPa`;
        }
    } catch(e) {
        console.error("Fehler beim Laden der Sensorwerte:", e);
    }
}

// HLS Stream starten, sobald Segmente existieren
async function waitForSegments(){
    while(true){
        try{
            const res = await fetch(videoSrc);
            const text = await res.text();
            if(text.includes('.ts')) break;
        } catch(e){}
        await new Promise(r => setTimeout(r,500));
    }
}

async function initVideo(){
    await waitForSegments();
    if(Hls.isSupported()){
        const hls = new Hls();
        hls.loadSource(videoSrc);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
    } else if(video.canPlayType('application/vnd.apple.mpegurl')){
        video.src = videoSrc;
        video.addEventListener('loadedmetadata', ()=>video.play());
    }
    ['canplay','playing','loadeddata'].forEach(ev => video.addEventListener(ev, hidePlaceholder));
}

async function clearDB(){ await fetch('/clear',{method:'POST'}); tempChart.updateSeries([]); humChart.updateSeries([]); }
function exportCSV(){ window.location.href='/export'; }

window.onload = async function(){
    initSensors();
    await await initDashboard();
    setInterval(updateData,3000);
    initVideo();
};
</script>
</body>
</html>
"""

@app.route("/")
def index():
    sensor_names = [f"Sensor {i} (CH{ch}, 0x{addr:02X})" for i, (ch, addr) in enumerate(SENSORS, start=1)]
    return render_template_string(template, SENSOR_NAMES=sensor_names)

# --- Start ---
init_db()
threading.Thread(target=sensor_loop, daemon=True).start()
ffmpeg_process = start_hls_stream()

try:
    app.run(host="0.0.0.0", port=5000, threaded=True)
finally:
    ffmpeg_process.terminate()

