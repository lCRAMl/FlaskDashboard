const video = document.getElementById('videoPlayer');
const placeholder = document.getElementById('stream-placeholder');
const videoSrc = '/hls/stream.m3u8';

// --- Farbpalette für Sensoren ---
const sensorColors = [
    '#FF5733', '#007BFF', '#28A745', '#FFC300', '#C70039', '#8E44AD', '#FF8C00', '#1ABC9C'
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
function initSensors(){
    const container = document.getElementById('sensors');
    sensors.forEach(name=>{
        const el = document.createElement('div');
        el.className = 'sensor';
        el.innerHTML = `<h2>${name}</h2>
                        <div class="value" id="${name}-temp"></div>
                        <div class="value" id="${name}-hum"></div>`;
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

// --- Dashboard initialisieren ---
async function initDashboard() {
    initSensors();

    const res = await fetch('/history'); 
    const data = await res.json();

    let tempTraces = [], humTraces = [];

    sensors.forEach((name, idx) => {
        let timestamps = [];
        if (data[name].timestamps && data[name].timestamps.length) {
            timestamps = data[name].timestamps.map(ts => ts.replace(' ', 'T'));
        } else {
            const len = data[name].temp.length;
            const now = new Date();
            timestamps = data[name].temp.map((_, i) => new Date(now - (len - i) * 5000).toISOString());
        }

        const color = getSensorColor(idx);

        tempTraces.push({
            x: timestamps,
            y: data[name].temp,
            type: 'scatter',
            mode: 'lines+markers',
            name: name,
            line: { color: color, width: 2, shape: 'spline' },
            marker: { size: 6, color: color },
            hovertemplate: '%{x}<br>%{y} °C<extra>' + name + '</extra>'
        });

        humTraces.push({
            x: timestamps,
            y: data[name].hum,
            type: 'scatter',
            mode: 'lines+markers',
            name: name,
            line: { color: color, width: 2, shape: 'spline' },
            marker: { size: 6, color: color },
            hovertemplate: '%{x}<br>%{y} %<extra>' + name + '</extra>'
        });
    });

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
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 40, y1: 40, line: { color: 'blue', dash: 'dash' } },
            { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: 70, y1: 70, line: { color: 'blue', dash: 'dash' } }
        ],
        hovermode: 'closest'
    };
    // Initial Plot
    Plotly.newPlot('tempChart', tempTraces, tempLayout);
    Plotly.newPlot('humChart', humTraces, humLayout);

    await updateData();
    setInterval(updateData, 10000);
    initVideo();
}

// --- Live-Daten nachführen ---
async function updateData() {
    try {
        const res = await fetch('/data'); 
        const data = await res.json();
        updateAverages(data);

        const now = new Date().toISOString();
        const maxPoints = 50; // nur die letzten 50 Messwerte anzeigen

        sensors.forEach((name, idx) => {
            const v = data[name];
            const el = sensorElements[name]; 
            if (!el) return;

            // Hintergrundfarbe setzen
            el.style.background = `linear-gradient(135deg, ${tempColor(v.temp)}, ${humColor(v.hum)})`;

            // Werte in der Kachel aktualisieren
            document.getElementById(`${name}-temp`).innerText = `🌡 ${v.temp} °C`;
            document.getElementById(`${name}-hum`).innerText  = `💧 ${v.hum} %`;

            // Puls-Animation triggern
            el.classList.remove('pulse');    // vorherige Animation zurücksetzen
            void el.offsetWidth;             // Trigger für Neuanlauf
            el.classList.add('pulse');       // Animation starten

            // Timestamp prüfen
            const ts = v.timestamp ? parseTimestamp(v.timestamp) : Date.now();

            // Plotly: neue Daten anhängen
            Plotly.extendTraces('tempChart', { x:[[ts]], y:[[v.temp]] }, [idx]);
            Plotly.extendTraces('humChart', { x:[[ts]], y:[[v.hum]] }, [idx]);

            // Scrollen auf die letzten maxPoints
            const tempData = document.getElementById('tempChart').data[idx].x;
            const humData  = document.getElementById('humChart').data[idx].x;

            if (tempData.length > maxPoints) {
                Plotly.relayout('tempChart', {
                    'xaxis.range': [tempData[tempData.length - maxPoints], tempData[tempData.length - 1]]
                });
            }
            if (humData.length > maxPoints) {
                Plotly.relayout('humChart', {
                    'xaxis.range': [humData[humData.length - maxPoints], humData[humData.length - 1]]
                });
            }
        });

    } catch(e) {
        console.error(e);
    }
}


// DB
async function clearDB(){ 
    await fetch('/clear',{method:'POST'}); 
    tempChart.updateSeries([]); humChart.updateSeries([]); 
}
function exportCSV(){ window.location.href='/export'; }

// --- Startpunkt ---
document.addEventListener("DOMContentLoaded", initDashboard);
