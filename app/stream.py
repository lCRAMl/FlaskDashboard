# app/stream.py
import os
import subprocess
import threading
import time
from .config import OUTPUT_DIR, RTSP_URL

ffmpeg_process = None
stop_thread = False

def start_hls_stream():
    """Starte FFmpeg in einem eigenen Thread mit Auto-Restart."""
    global stop_thread
    stop_thread = False
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    def ffmpeg_thread():
        global ffmpeg_process
        while not stop_thread:
            cmd = [
                "ffmpeg",
                "-nostdin",
                "-rtsp_transport", "tcp",
                "-i", RTSP_URL,
                "-c:v", "copy",
                "-an",
                "-f", "hls",
                "-hls_time", "1",
                "-hls_list_size", "5",
                "-hls_flags", "delete_segments+append_list+omit_endlist",
                os.path.join(OUTPUT_DIR, "stream.m3u8")
            ]
            try:
                #with open("ffmpeg.log", "a") as log_file:
                    ffmpeg_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        bufsize=1,
                        universal_newlines=True
                    )
                    print("[INFO] HLS-Stream gestartet")
                    ffmpeg_process.wait()
            except Exception as e:
                print(f"[ERROR] FFmpeg Thread: {e}")

            if not stop_thread:
                print("[WARN] FFmpeg abgestürzt oder beendet, restart in 3s...")
                time.sleep(3)

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
