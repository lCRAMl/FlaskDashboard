
# app/systeminfo.py
import psutil
import subprocess

def get_pi_stats():
    try:
        # CPU-Last (Durchschnitt über 1 Sekunde)
        cpu = psutil.cpu_percent(interval=0.5)

        # Temperatur auslesen
        try:
            out = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
            temp = float(out.replace("temp=", "").replace("'C", "").strip())
        except Exception:
            temp = None

        return {
            "cpu": cpu,
            "temp": temp
        }
    except Exception as e:
        return {"cpu": None, "temp": None}
