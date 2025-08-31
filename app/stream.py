# app/stream.py
import os
import subprocess
import threading
import time
from . import config

ffmpeg_process = None


def start_hls_stream():
    """Starte FFmpeg in einem eigenen Thread ohne Auto-Restart."""
    global ffmpeg_process

    # Falls schon ein Prozess läuft → nicht nochmal starten
    if ffmpeg_process and ffmpeg_process.poll() is None:
        print("[INFO] FFmpeg läuft bereits.")
        return
    
    # HLS-Ausgabeordner erstellen
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)


    def ffmpeg_thread():
        global ffmpeg_process
        
        def consume_stdout(pipe):
            """Liess die stdout-Pipe, sonst blockiert FFmpeg."""
            for line in pipe:
                pass  # Hier könntest du die Zeilen auch loggen
        
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-rtsp_transport", "tcp",
            "-i", config.RTSP_URL,
            "-c:v", "copy",
            "-an",
            "-f", "hls",
            "-hls_time", "1",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+append_list+omit_endlist",
            os.path.join(config.OUTPUT_DIR, "stream.m3u8")
        ]
        try:
            #with open(config.FFMPEGLOG_PATH, "a") as log_file:
            ffmpeg_process = subprocess.Popen(
                cmd,
                #stdout=log_file,            # stdout ins Log
                stdout=subprocess.PIPE,
                #stderr=subprocess.STDOUT,   # stderr ebenfalls ins Log
                stderr=subprocess.DEVNULL,
                bufsize=1,
                universal_newlines=True
            )
            
            # Thread starten, um stdout zu konsumieren
            threading.Thread(target=consume_stdout, args=(ffmpeg_process.stdout,), daemon=True).start()
            
            print("[INFO] HLS-Stream gestartet")
            ffmpeg_process.wait()  # nur einmal warten
            print("[INFO] FFmpeg beendet")
        except Exception as e:
            print(f"[ERROR] FFmpeg Thread: {e}")

    t = threading.Thread(target=ffmpeg_thread, daemon=True)
    t.start()


def stop_hls_stream():
    """Stoppe FFmpeg und den Thread sauber."""
    global stop_thread, ffmpeg_process
    stop_thread = True
    if ffmpeg_process and ffmpeg_process.poll() is None:
        ffmpeg_process.terminate()
        ffmpeg_process.wait()
        print("[INFO] HLS-Stream gestoppt")
