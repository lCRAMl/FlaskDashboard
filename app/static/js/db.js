const video = document.getElementById('videoPlayer');
const placeholder = document.getElementById('stream-placeholder');
const videoSrc = '/hls/stream.m3u8';

// --- Farbpalette für Sensoren ---
const sensorColors = [
    '#00e61fc5', '#007BFF', '#ff7300ff', '#FFC300', '#C70039', '#8E44AD', '#FF8C00', '#1ABC9C'
];

function getSensorColor(idx){
    return sensorColors[idx % sensorColors.length];
}

// --- Zentrale Zeitparser-Funktion ---
function parseTimestamp(ts) {
    if (!ts) return Date.now();  // fallback auf "jetzt"

    // Wenn schon ein Date-Objekt oder Zahl kommt
    if (ts instanceof Date) return ts.getTime();
    if (typeof ts === "number") return ts;

    // Falls Format "YYYY-MM-DD HH:MM:SS"
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(ts)) {
        return new Date(ts.replace(" ", "T")).getTime();
    }

    // Falls nur Uhrzeit "HH:MM:SS" → heutiges Datum davor setzen
    if (/^\d{2}:\d{2}:\d{2}$/.test(ts)) {
        const today = new Date().toISOString().split("T")[0];
        return new Date(`${today}T${ts}`).getTime();
    }

    console.warn("⚠️ Unbekanntes Zeitformat:", ts);
    return Date.now(); // Fallback, damit kein NaN entsteht
}

function hidePlaceholder() {
    placeholder.style.display = 'none';
}

// HLS Stream starten
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

// --- HLS-Player starten und reconnecten ---
async function initVideo() {
    if (Hls.isSupported()) {
        const hls = new Hls({
            maxBufferLength: 5,
            liveSyncDurationCount: 3,
            enableWorker: true,
            debug: false
        });
        hls.loadSource(videoSrc);
        hls.attachMedia(video);

        hls.on(Hls.Events.MANIFEST_PARSED, () => video.play());
        hls.on(Hls.Events.ERROR, function (event, data) {
            if (data.fatal) {
                console.warn("[HLS] Fatal error, trying to recover...", data);
                switch (data.type) {
                    case Hls.ErrorTypes.NETWORK_ERROR:
                        console.log("[HLS] Network error, reload source");
                        hls.startLoad();  // reconnect
                        break;
                    case Hls.ErrorTypes.MEDIA_ERROR:
                        console.log("[HLS] Media error, recover");
                        hls.recoverMediaError();
                        break;
                    default:
                        hls.destroy();
                        setTimeout(initVideo, 3000); // Thread neu starten
                        break;
                }
            }
        });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        // Safari / iOS fallback
        video.src = videoSrc;
        video.addEventListener('error', () => {
            console.warn("[HLS] Safari reload source");
            setTimeout(() => video.load(), 3000);
        });
        video.addEventListener('loadedmetadata', () => video.play());
    }

    ['canplay','playing','loadeddata'].forEach(ev => video.addEventListener(ev, hidePlaceholder));
}

// Sensor-Elemente
let sensors = window.SENSOR_NAMES || [];
let sensorElements = {};
let tempChart, humChart;

// --- Sensor-Kacheln initialisieren ---
function initSensors(data){
    const container = document.getElementById('sensors');
    container.innerHTML = '';  // alte Kacheln löschen
    sensors.forEach(name=>{
        const el = document.createElement('div');
        el.className = 'sensor';
        el.innerHTML = `<h2>${name}</h2>
                        <div class="value" id="${name}-temp"></div>
                        <div class="value" id="${name}-hum"></div>`;
        container.appendChild(el);
        sensorElements[name] = el;

        // --- letzte Werte aus data setzen ---
        if (data && data[name]) {
            const lastTemp = data[name].temp?.[0] ?? '--';
            const lastHum  = data[name].hum?.[0] ?? '--';
            document.getElementById(`${name}-temp`).innerText = lastTemp !== '--' ? `🌡 ${lastTemp} °C` : '-- °C';
            document.getElementById(`${name}-hum`).innerText  = lastHum  !== '--' ? `💧 ${lastHum} %` : '-- %';

            // Hintergrundfarbe direkt setzen
            //el.style.background = `linear-gradient(135deg, ${tempColor(lastTemp)}, ${humColor(lastHum)})`;
        }
    });
}

function initShellyTile(data) {
    const container = document.getElementById('shelly'); // 👉 eigener Container
    container.innerHTML = ""; // alte Shelly-Kachel löschen, falls vorhanden

    const el = document.createElement('div');
    el.className = 'sensor shelly-tile';
    el.innerHTML = `<h2>Shelly</h2>
                    <div class="value" id="shelly-power">⚡ -- W</div>
                    <div class="value" id="shelly-temp">🌡 -- °C</div>`;
    container.appendChild(el);
    sensorElements["Shelly"] = el;

    if (data && data["Shelly"]) {
        document.getElementById("shelly-power").innerText = `⚡ ${data["Shelly"].apower.toFixed(1)} W`;
        document.getElementById("shelly-temp").innerText  = `🌡 ${data["Shelly"].temp.toFixed(1)} °C`;
    }
}

// --- Dashboard initialisieren ---
async function initDashboard() {

    const res = await fetch('/history'); 
    const data = await res.json();

    initShellyTile(data)
    // Normale Sensoren
    sensors = Object.keys(data).filter(k => k !== "Shelly");
    initSensors(data);

    // --- Charts ---
    let tempTraces = [], humTraces = [];
    sensors.forEach((name, idx) => {
        if (!data[name]) {
            console.warn(`⚠️ Keine Daten für Sensor ${name}`);
            return;
        }
        let timestamps = [];
        if (data[name].timestamps && data[name].timestamps.length) {
            timestamps = data[name].timestamps.map(ts => parseTimestamp(ts));
        } else {
            const len = data[name].temp.length;
            const now = new Date();
            timestamps = data[name].temp.map((_, i) => now - (len - i) * 5000);
        }

        const color = getSensorColor(idx);

        tempTraces.push({
            x: timestamps,
            y: data[name].temp,
            type: 'scatter',
            mode: 'lines',
            name: name,
            line: { color: color, width: 2, shape: 'spline' },
            marker: { size: 6, color: color },
            hovertemplate: '%{x}<br>%{y} °C<extra>' + name + '</extra>'
        });

        humTraces.push({
            x: timestamps,
            y: data[name].hum,
            type: 'scatter',
            mode: 'lines',
            name: name,
            line: { color: color, width: 2, shape: 'spline' },
            marker: { size: 6, color: color },
            hovertemplate: '%{x}<br>%{y} %<extra>' + name + '</extra>'
        });
    });

    const tempLayout = {
        title: { text: 'Temperaturen', font: { size: 20 }, x: 0.5 },
        margin: { t: 35, b: 30, l: 35, r: 5 },
        height: 250,
        plot_bgcolor: '#f0f2f5',
        paper_bgcolor: '#f0f2f5',
        xaxis: { type: 'date', title: 'Zeit', showgrid: true, gridcolor: '#e0e0e0' },
        yaxis: { type: 'linear', range: [15, 30], title: '°C', showgrid: false, gridcolor: '#e0e0e0' },
        shapes: [
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 18, y1: 18, line: { color: 'red', dash: 'dash' } },
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 28, y1: 28, line: { color: 'red', dash: 'dash' } }
        ],
        hovermode: 'closest'
    };

    const humLayout = {
        title: { text: 'Luftfeuchtigkeit', font: { size: 20 }, x: 0.5 },
        margin: { t: 35, b: 30, l: 35, r: 5 },
        height: 300,
        plot_bgcolor: '#f0f2f5',
        paper_bgcolor: '#f0f2f5',
        xaxis: { type: 'date', title: 'Zeit', showgrid: true, gridcolor: '#e0e0e0' },
        yaxis: { type: 'linear', range: [30, 80], title: '%', showgrid: false, gridcolor: '#e0e0e0' },
        shapes: [
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 40, y1: 40, line: { color: 'red', dash: 'dash' } },
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 70, y1: 70, line: { color: 'red', dash: 'dash' } }
        ],
        hovermode: 'closest'
    };
    // Initial Plot
    Plotly.newPlot('tempChart', tempTraces, tempLayout);
    Plotly.newPlot('humChart', humTraces, humLayout);

    await updateData();
    setInterval(updateData, 5000);
    initVideo();
}

// --- Live-Daten nachführen ---
// --- Mapping Sensorname → Plotly Trace Index ---
const traceMap = {
  "CH0-0x76": 0, // erster BME280
  "CH0-0x77": 1, // zweiter BME280
  // weitere Sensoren hier ergänzen
  // Shelly hat keine Traces, wird separat behandelt
};

const maxPoints = 50; // Anzahl an Punkten im Chart

async function updateData() {
  try {
    const res = await fetch('/data');
    const data = await res.json();

    // --- Shelly-Werte ---
    if (data["Shelly"]) {
      const s = data["Shelly"];
      document.getElementById("shelly-power").innerText = s.apower != null ? `⚡ ${s.apower.toFixed(1)} W` : '-- W';
      document.getElementById("shelly-temp").innerText = s.temp != null ? `🌡 ${s.temp.toFixed(1)} °C` : '-- °C';

      const el = sensorElements["Shelly"];
      if (el) {
        el.classList.remove('pulse'); void el.offsetWidth; el.classList.add('pulse');
      }
    }

    // --- Normale Sensoren ---
    const sensors = Object.keys(data).filter(k => k !== "Shelly");
    let tempSum = 0, humSum = 0, count = 0;

    sensors.forEach(name => {
      const v = data[name];
      const el = sensorElements[name];
      if (!el || !v) return;

      const temp = v.temp != null ? v.temp : null;
      const hum = v.hum != null ? v.hum : null;

      // Kachel aktualisieren
      document.getElementById(`${name}-temp`).innerText = temp != null ? `🌡 ${temp} °C` : '-- °C';
      document.getElementById(`${name}-hum`).innerText = hum != null ? `💧 ${hum} %` : '-- %';

      // Puls-Animation
      el.classList.remove('pulse'); void el.offsetWidth; el.classList.add('pulse');

      // Durchschnittswerte
      if (temp != null && hum != null) {
        tempSum += temp;
        humSum += hum;
        count++;
      }

      // Timestamp
      const ts = v.timestamp ? parseTimestamp(v.timestamp) : Date.now();

      // Plotly Trace Index
      const traceIdx = traceMap[name];
      if (traceIdx === undefined) {
        console.warn("Kein Trace für Sensor:", name);
      return;
      }
      // Daten nur hinzufügen, wenn Werte existieren
      if (temp != null) Plotly.extendTraces('tempChart', { x:[[ts]], y:[[temp]] }, [traceIdx]);
      if (hum != null)  Plotly.extendTraces('humChart', { x:[[ts]], y:[[hum]] }, [traceIdx]);

      // Nur die letzten maxPoints anzeigen
      const tempData = document.getElementById('tempChart').data[traceIdx]?.x || [];
      const humData = document.getElementById('humChart').data[traceIdx]?.x || [];

      if (tempData.length > maxPoints) {
        Plotly.relayout('tempChart', { 'xaxis.range': [tempData[tempData.length - maxPoints], tempData[tempData.length - 1]] });
      }
      if (humData.length > maxPoints) {
        Plotly.relayout('humChart', { 'xaxis.range': [humData[humData.length - maxPoints], humData[humData.length - 1]] });
      }
    });

    // Durchschnittswerte in Kachel
    const avgTemp = count ? (tempSum / count).toFixed(1) : '--';
    const avgHum = count ? (humSum / count).toFixed(1) : '--';
    document.getElementById('averages').innerHTML = `🌡 ${avgTemp} °C &nbsp;&nbsp; 💧 ${avgHum} %`;

  } catch(e) {
    console.error("updateData Fehler:", e);
  }
}



// DB
async function clearDB(){ 
    try {
        await fetch('/clear', { method:'POST' }); 

        // Charts komplett neu erstellen, Layout behalten
        const tempLayout = {
            title: { text: 'Temperaturen', font: { size: 20 }, x: 0.5 },
            margin: { t: 30, b: 30, l: 35, r: 5 },
            height: 250,
            plot_bgcolor: '#f9f9f9',
            paper_bgcolor: '#f0f2f5',
            xaxis: { type: 'date', title: 'Zeit', showgrid: true, gridcolor: '#e0e0e0' },
            yaxis: { range: [15, 30], title: '°C', showgrid: true, gridcolor: '#e0e0e0' },
            shapes: [
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 18, y1: 18, line: { color: 'red', dash: 'dash' } },
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 28, y1: 28, line: { color: 'red', dash: 'dash' } }
            ],
            hovermode: 'closest'
        };

        const humLayout = {
            title: { text: 'Luftfeuchtigkeit', font: { size: 20 }, x: 0.5 },
            margin: { t: 30, b: 30, l: 35, r: 5 },
            height: 300,
            plot_bgcolor: '#f9f9f9',
            paper_bgcolor: '#f0f2f5',
            xaxis: { type: 'date', title: 'Zeit', showgrid: true, gridcolor: '#e0e0e0' },
            yaxis: { range: [30, 80], title: '%', showgrid: true, gridcolor: '#e0e0e0' },
            shapes: [
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 40, y1: 40, line: { color: 'red', dash: 'dash' } },
                { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 70, y1: 70, line: { color: 'red', dash: 'dash' } }
            ],
            hovermode: 'closest'
        };

        // Leere Charts neu erstellen
        Plotly.newPlot('tempChart', [], tempLayout);
        Plotly.newPlot('humChart', [], humLayout);
    } catch(e) {
        console.error("clearDB Fehler:", e);
    }
}

function exportCSV(){ window.location.href='/export'; }

// --- Startpunkt ---
document.addEventListener("DOMContentLoaded", initDashboard);
