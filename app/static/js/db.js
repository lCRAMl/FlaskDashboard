// --- Video / Stream ---
const video = document.getElementById('videoPlayer');
const placeholder = document.getElementById('stream-placeholder');
const videoSrc = '/hls/stream.m3u8';

// --- Farbpalette für Sensoren ---
const sensorColors = [
  '#00e61fc5', '#007BFF', '#ff7300ff', '#FFC300',
  '#C70039', '#8E44AD', '#FF8C00', '#1ABC9C'
];
function getSensorColor(idx) {
  return sensorColors[idx % sensorColors.length];
}

// --- Zeitparser ---
function parseTimestamp(ts) {
  if (!ts) return Date.now();
  if (ts instanceof Date) return ts.getTime();
  if (typeof ts === "number") return ts;

  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(ts))
    return new Date(ts.replace(" ", "T")).getTime();

  if (/^\d{2}:\d{2}:\d{2}$/.test(ts)) {
    const today = new Date().toISOString().split("T")[0];
    return new Date(`${today}T${ts}`).getTime();
  }

  console.warn("⚠️ Unbekanntes Zeitformat:", ts);
  return Date.now();
}

// --- UI Hilfen ---
function hidePlaceholder() {
  placeholder.style.display = 'none';
}

function setPulse(el) {
  el.classList.remove('pulse');
  void el.offsetWidth; // force reflow
  el.classList.add('pulse');
}

function updateValue(id, value, unit, icon) {
  const el = document.getElementById(id);
  if (el) {
    el.innerText = value != null ? `${icon} ${value} ${unit}` : `-- ${unit}`;
  }
}

// --- Video Init ---
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
    hls.on(Hls.Events.ERROR, (event, data) => {
      if (!data.fatal) return;
      console.warn("[HLS] Fatal error, recovering...", data);
      switch (data.type) {
        case Hls.ErrorTypes.NETWORK_ERROR: hls.startLoad(); break;
        case Hls.ErrorTypes.MEDIA_ERROR: hls.recoverMediaError(); break;
        default:
          hls.destroy();
          setTimeout(initVideo, 3000);
      }
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = videoSrc;
    video.addEventListener('error', () => setTimeout(() => video.load(), 3000));
    video.addEventListener('loadedmetadata', () => video.play());
  }
  ['canplay', 'playing', 'loadeddata'].forEach(ev =>
    video.addEventListener(ev, hidePlaceholder));
}

// --- Sensor UI ---
let sensors = window.SENSOR_NAMES || [];
let sensorElements = {};

function createSensorTile(name, data) {
  const el = document.createElement('div');
  el.className = 'sensor';
  el.innerHTML = `
    <h2>${name}</h2>
    <div class="value" id="${name}-temp"></div>
    <div class="value" id="${name}-hum"></div>
  `;
  if (data) {
    updateValue(`${name}-temp`, data.temp?.[0], '°C', '🌡');
    updateValue(`${name}-hum`, data.hum?.[0], '%', '💧');
  }
  return el;
}

function initSensors(data) {
  const container = document.getElementById('sensors');
  container.innerHTML = '';
  sensors.forEach(name => {
    const el = createSensorTile(name, data[name]);
    container.appendChild(el);
    sensorElements[name] = el;
  });
}

function initShellyTile(data) {
  const container = document.getElementById('shelly');
  container.innerHTML = "";
  const el = document.createElement('div');
  el.className = 'sensor shelly-tile';
  el.innerHTML = `
    <h2>Shelly</h2>
    <div class="value" id="shelly-temp">🌡 -- °C</div>
    <div class="value" id="shelly-power">⚡ -- W</div>
  `;
  container.appendChild(el);
  sensorElements["Shelly"] = el;

  if (data?.Shelly) {
    updateValue("shelly-temp", data.Shelly.temp?.toFixed(1), '°C', '🌡');
    updateValue("shelly-power", data.Shelly.apower?.toFixed(1), 'W', '⚡');
  }
}

function initPiTile(data) {
  const container = document.getElementById('pi');
  container.innerHTML = "";
  const el = document.createElement('div');
  el.className = 'sensor pi-tile';
  el.innerHTML = `
    <h2>Raspberry</h2>
    <div class="value" id="pi-temp">🌡 -- °C</div>
    <div class="value" id="pi-cpu">🖥️ -- %</div>
  `;
  container.appendChild(el);
  sensorElements["Pi"] = el;

  if (data?.Pi) {
    updateValue("pi-temp", data.Pi.temp?.toFixed(1), '°C', '🌡');
    updateValue("pi-cpu", data.Pi.cpu?.toFixed(1), '%', '🖥️');
  }
}

// --- Charts ---
function buildTraces(data, type) {
  return sensors.map((name, idx) => {
    const s = data[name];
    if (!s || !Array.isArray(s[type])) return null;  // ❗ Schutz

    const timestamps = (s.timestamps?.length)
      ? s.timestamps.map(parseTimestamp)
      : s.temp.map((_, i) => Date.now() - (s.temp.length - i) * 5000);

    const color = getSensorColor(idx);
    return {
      x: timestamps,
      y: s[type],
      type: 'scatter',
      mode: 'lines',
      name: name,
      line: { color, width: 2, shape: 'spline' },
      marker: { size: 6, color },
      hovertemplate: `%{x}<br>%{y} ${type === 'temp' ? '°C' : '%'}<extra>${name}</extra>`
    };
  }).filter(Boolean);
}

const layouts = {
  temp: {
    title: { text: 'Temperaturen', font: { size: 20 }, x: 0.5 },
    margin: { t: 35, b: 30, l: 35, r: 5 },
    height: 250, plot_bgcolor: '#f0f2f5', paper_bgcolor: '#f0f2f5',
    xaxis: { type: 'date', title: 'Zeit', gridcolor: '#e0e0e0' },
    yaxis: { range: [15, 40], title: '°C' },
    shapes: [
      { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 18, y1: 18, line: { color: 'red', dash: 'dash' } },
      { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 28, y1: 28, line: { color: 'red', dash: 'dash' } }
    ]
  },
  hum: {
    title: { text: 'Luftfeuchtigkeit', font: { size: 20 }, x: 0.5 },
    margin: { t: 35, b: 30, l: 35, r: 5 },
    height: 300, plot_bgcolor: '#f0f2f5', paper_bgcolor: '#f0f2f5',
    xaxis: { type: 'date', title: 'Zeit', gridcolor: '#e0e0e0' },
    yaxis: { range: [20, 70], title: '%' },
    shapes: [
      { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 40, y1: 40, line: { color: 'red', dash: 'dash' } },
      { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 70, y1: 70, line: { color: 'red', dash: 'dash' } }
    ]
  }
};

let traceMap = {};

function buildTraceMap() {
  traceMap = {};
  sensors.forEach((name, idx) => {
    traceMap[name] = idx;
  });
}

// --- Init Dashboard ---
async function initDashboard() {
  const res = await fetch('/history');
  const data = await res.json();

  initPiTile(data);
  initShellyTile(data);
  // Nur echte Sensoren in Charts einfügen
  sensors = Object.keys(data).filter(k => !["Shelly", "Pi"].includes(k));
  initSensors(data);
  buildTraceMap();   // <--- neues Mapping passend zu sensors
  Plotly.newPlot('tempChart', buildTraces(data, 'temp'), layouts.temp);
  Plotly.newPlot('humChart', buildTraces(data, 'hum'), layouts.hum);

  await updateData();
  setInterval(updateData, 10000);
  initVideo();
}

// --- Live Updates ---
const maxPoints = 50;
let lastTimestamp = null;  // globaler Zeitstempel der letzten Aktualisierung

async function updateData() {
  try {
    const url = lastTimestamp ? `/data?since=${encodeURIComponent(lastTimestamp)}` : '/data';
    const res = await fetch(url);
    const data = await res.json();

    // Raspberry Pi
    if (data.Pi) {
      updateValue("pi-temp", data.Pi.temp?.toFixed(1), '°C', '🌡');
      updateValue("pi-cpu", data.Pi.cpu?.toFixed(1), '%', '🖥️');
      setPulse(sensorElements["Pi"]);
    }

    // Shelly
    if (data.Shelly) {
      updateValue("shelly-temp", data.Shelly.temp?.toFixed(1), '°C', '🌡');
      updateValue("shelly-power", data.Shelly.apower?.toFixed(1), 'W', '⚡');
      setPulse(sensorElements["Shelly"]);
      lastTimestamp = data.Shelly.timestamp;  // update lastTimestamp
    }

    // Sensoren
    let tempSum = 0, humSum = 0, count = 0;
    Object.keys(data).filter(k => k !== "Shelly").forEach(name => {
      const v = data[name], el = sensorElements[name];
      if (!el || !v) return;

      updateValue(`${name}-temp`, v.temp, '°C', '🌡');
      updateValue(`${name}-hum`, v.hum, '%', '💧');
      setPulse(el);

      if (v.temp != null && v.hum != null) {
        tempSum += v.temp; humSum += v.hum; count++;
      }

      const ts = parseTimestamp(v.timestamp || Date.now());
      const traceIdx = traceMap[name];
      if (traceIdx === undefined) return;

      if (v.temp != null) Plotly.extendTraces('tempChart', { x:[[ts]], y:[[v.temp]] }, [traceIdx]);
      if (v.hum != null)  Plotly.extendTraces('humChart', { x:[[ts]], y:[[v.hum]] }, [traceIdx]);

      // Chart auf maxPoints beschränken
      const tempData = document.getElementById('tempChart').data[traceIdx]?.x || [];
      const humData = document.getElementById('humChart').data[traceIdx]?.x || [];

      // letzten Timestamp merken
      if (!lastTimestamp || ts > parseTimestamp(lastTimestamp)) lastTimestamp = v.timestamp;
    });

    document.getElementById('averages').innerHTML =
      `🌡 ${count ? (tempSum / count).toFixed(1) : '--'} °C &nbsp;&nbsp; 💧 ${count ? (humSum / count).toFixed(1) : '--'} %`;

  } catch (e) {
    console.error("updateData Fehler:", e);
  }
}


// --- DB ---
async function clearDB() {
  try {
    await fetch('/clear', { method: 'POST' });
    window.location.reload();
  } catch (e) {
    console.error("clearDB Fehler:", e);
  }
}

function exportCSV() { window.location.href = '/export'; }

// --- Start ---
document.addEventListener("DOMContentLoaded", initDashboard);
