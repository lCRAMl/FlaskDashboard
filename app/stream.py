# app/stream.py
import os
import subprocess
import threading
import time
from .config import OUTPUT_DIR, RTSP_URL

ffmpeg_process = None


def start_hls_stream():

    global ffmpeg_process
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
                ffmpeg_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    bufsize=1,
                    universal_newlines=True
                )
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
