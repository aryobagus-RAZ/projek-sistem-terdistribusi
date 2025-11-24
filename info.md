# MQTT Home Automation Simulation (Python)

This workspace contains a small MQTT-based home automation simulation using Python.

Files added:

- `publisher.py` — simulates 5 virtual sensors (Temperature, Humidity, Motion, Light Level, Door). Each sensor publishes JSON messages to topics such as `home/livingroom/temperature` and listens for acknowledgements on `ack/<sensor_id>`.
- `dashboard.py` — MQTT subscriber that listens to sensor topics, sends ack messages back to sensors, and hosts a small Flask web UI (Server-Sent Events) showing live sensor values.
- `requirements.txt` — Python dependencies (`paho-mqtt`, `Flask`).

Broker:
- The easiest option is to run Mosquitto locally as the MQTT broker. If you prefer, you can change broker host/port in the scripts.

Getting started (Windows PowerShell):

1) Install Mosquitto (if you don't have a broker):

   - On Windows, download and install Mosquitto from https://mosquitto.org/download/ or via `choco install mosquitto` (if you have Chocolatey).

   - Start the broker (default port 1883). For example, with the Windows installer the service may already be running, or run:

```powershell
mosquitto -v
# or
.
``` 

2) Create a Python virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Run the dashboard (subscriber + web UI):

```powershell
python dashboard.py --broker localhost --port 1883 --host 0.0.0.0 --webport 5000
```

4) In another terminal, run the publisher (sensors):

```powershell
python publisher.py --broker localhost --port 1883
```

5) Open a browser to `http://localhost:5000` to see the live dashboard. The dashboard automatically sends ack messages back to sensors, which the publisher prints when it receives them.

Notes:
- The MQTT broker is external (Mosquitto) — implementing a full MQTT broker in Python is non-trivial and out-of-scope for this simulation; using Mosquitto keeps the system realistic and simple.
- The pub/sub scripts are intentionally simple and single-file to make testing easy.
- If you want a single-process broker (no Mosquitto), I can add a very small in-memory router, but it would not be an MQTT-compliant broker (it would be a simulated router).

# MQTT Home Automation Simulation (Python)

This project is a small, local MQTT-based home automation simulation intended for learning and testing MQTT pub/sub patterns, round-trip acknowledgements, and a simple web-based dashboard.

Overview
--------
- `publisher.py`: Simulates five virtual sensors (Temperature, Humidity, Motion, Light, Door). Each sensor periodically publishes JSON messages to topics like `home/livingroom/temperature` and listens for acknowledgements on `ack/<sensor-id>`.
- `dashboard.py`: Subscribes to sensor topics, displays live values in a Flask web UI (Server-Sent Events), and sends acknowledgement messages back to each sensor.
- `requirements.txt`: Pinned Python dependencies (`paho-mqtt`, `Flask`).

Design & architecture
---------------------
- Broker: External MQTT broker (recommended: Mosquitto) handles message routing. Both `publisher.py` and `dashboard.py` connect as MQTT clients.
- Topic structure:
   - Sensor data: `home/<room>/<sensor>` (e.g. `home/livingroom/temperature`)
   - Acknowledgements: `ack/<sensor-id>` (e.g. `ack/livingroom-temperature-abc123`)
- Sensor ID format: `<room>-<kind>-<suffix>` (readable, unique per sensor instance).
- Message flow (and the 4-direction event logging used for visibility):
   1. publisher -> broker (publish sensor data)
   2. broker -> subscriber (dashboard receives the message)
   3. subscriber -> broker (dashboard publishes an ack to `ack/<sensor-id>`)
   4. broker -> publisher (publisher receives the ack)

What the dashboard shows
------------------------
- Live cards for each configured sensor topic with latest value and timestamp.
- Event log (SSE stream) showing structured events with a `direction` field so you can trace messages across the full round trip (publisher→broker, broker→subscriber, subscriber→broker, broker→publisher).
- The UI uses a simple bright color theme (customizable in `dashboard.py` and `mqtt_simulator.html`).

Quick start (Windows PowerShell)
--------------------------------
1) Install and run an MQTT broker (Mosquitto):

    - Download Mosquitto from https://mosquitto.org/download/ or install via Chocolatey: `choco install mosquitto`.
    - Run the broker (default port 1883). Example (verbose):

```powershell
mosquitto -v
```

2) Prepare Python environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) Start the dashboard (subscriber + web UI):

```powershell
python dashboard.py --broker localhost --port 1883 --host 0.0.0.0 --webport 5000
```

4) Start the publisher (simulated sensors) in a second terminal:

```powershell
python publisher.py --broker localhost --port 1883
```

5) Open your browser at `http://localhost:5000` and hard-refresh (Ctrl+F5) if you recently changed CSS.

Files and key locations
------------------------
- `publisher.py`: Sensor simulation and publisher logic. Look for `make_id(room, kind)` to see readable ID generation and sensor-specific value generators.
- `dashboard.py`: Contains the MQTT subscriber logic and embedded HTML (`INDEX_HTML`) for the Flask web UI. The CSS variables and styles are inline in `INDEX_HTML`.
- `mqtt_simulator.html` (if present): A single-file in-browser simulator (standalone) that mirrors the Python implementation for quick demos.

Troubleshooting & common issues
-------------------------------
- Browser still showing old colors: hard-refresh the page (Ctrl+F5) or clear cache. If using Flask, restart the Python process to load the updated embedded HTML.
- `pkgutil.get_loader` AttributeError at import time: Some environments or a local file named `pkgutil.py` can shadow the standard library. Check for `pkgutil.py` in your project and remove/rename it. `dashboard.py` includes a compatibility shim to mitigate this issue.
- `AttributeError: module 'random' has no attribute 'sin'` or similar: This happened when `math.sin` was mistakenly written as `random.sin` in earlier versions. Ensure `publisher.py` imports `math` and uses `math.sin` for waveform generation.
- MQTT connection problems: verify the broker is running and reachable at the host/port you passed to the scripts. Default is `localhost:1883`.

Advanced notes & optional enhancements
------------------------------------
- Wildcard topic support: The scripts subscribe to explicit topics by default. Dashboard can be extended to subscribe to `home/#` for dynamic topics.
- Charting: The current UI uses simple numeric cards and an event log. Integrate Chart.js or similar for sparkline/historical charts.
- Security: For production use, enable TLS and authentication on the broker and configure the clients accordingly.

Developer tips
--------------
- When modifying the dashboard theme, update both `mqtt_simulator.html` (if you use it) and the `INDEX_HTML` string in `dashboard.py` so both interfaces stay consistent.
- To inspect live SSE events, open browser DevTools → Network → filter `EventSource` or the `/stream` request to see SSE frames.

If you'd like, I can also:
- Add wildcard topic subscription and auto-generated cards for new topics.
- Replace the inline dashboard HTML with a template file for easier editing.
- Add per-sensor visual ack indicators (green/red dots) on the dashboard cards.

Enjoy experimenting — tell me if you want any of the optional enhancements implemented.
