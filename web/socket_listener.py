import socket
import threading
import tkinter as tk
from datetime import datetime
import traceback
import time

import mod_buchen # <‑‑ вот так Важно: импортировать модуль, а не функцию, чтобы избежать циклических импортов.

PORT = 54321


def start_tracking():
    print(">>> start_tracking() called")
    #status_var.set("Tracking started!")

def socket_listener(root, status_var, callback):
    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_var.set(f"{timestamp} — {msg}")
        print("STATUS:", msg)

    log("Starting socket listener…")

    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", PORT))
        server.listen(1)
        log(f"Listening on port {PORT}")
    except Exception as e:
        err = traceback.format_exc()
        print("ERROR starting listener:\n", err)
        root.after(0, lambda: status_var.set(f"Listener error: {e}"))
        return

    while True:
        try:
            conn, addr = server.accept()
            print("Connection from:", addr)
            data = conn.recv(1024).decode("utf-8").strip()
            conn.close()

            if data:
                root.after(0, log, f"Received: {data}")
                print("Received:", data)

            if data == "START":
                root.after(0, callback)

        except Exception as e:
            err = traceback.format_exc()
            print("ERROR in listener loop:\n", err)
            root.after(0, log, f"Listener error: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Socket Test")

    status_var = tk.StringVar()
    status_var.set("Initializing…")

    status_bar = tk.Label(root, textvariable=status_var, bd=1, relief=tk.SUNKEN, anchor="w")
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    thread = threading.Thread(target=socket_listener, args=(root,start_tracking), daemon=True)
    thread = threading.Thread(
        target=socket_listener,
        args=(root, status_var,
        start_tracking
    ), daemon=True )
    thread.start()

    root.mainloop()

