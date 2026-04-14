# Python Process Orchestration & Live Simulation

Hello Aary! As requested, here is a breakdown of the concepts we just used to orchestrate the backend, frontend, database, and pipeline simulator into a single, clean executable script.

## 1. What Was the Problem?
In a full-stack project, there are multiple moving pieces that need to be run simultaneously to test the system:
- **Databases**: Need to be booted via Docker (`docker compose up -d`).
- **Backend API**: The FastAPI layer needs to be started (`uvicorn app.main:app`).
- **Frontend Dashboard**: The React layer needs its dev server (`npm run dev`).
- **Live Simulator**: A script to continuously feed data (HTTP POSTs) into the API so you can watch real-time graph updates.

**The pain point**: Managing 4 different terminal windows, starting them manually in the right order, and waiting for things to boot before generating mock data is cumbersome and ruins the seamless "demo" experience.

## 2. The Solution
We needed an **Orchestrator**. 
Instead of relying on heavy-duty tools, we leaned into **pure Python natively** using process management and threading. We built a single `run_live_demo.py` script that takes charge of spinning up every required service, properly delaying execution until services are booted, pulling open your browser automatically, and kicking off a background task that streams events at intervals.

## 3. How We Tackled It & What We Used

We used three primary standard library packages in Python to tackle this:

### A. Subprocesses (Technology: `subprocess` module)
We used `subprocess.run()` and `subprocess.Popen()` to tell python to act like a human typing in a terminal.
- `subprocess.run("docker compose up -d")` ran synchronously, making the script *wait* until docker finished loading.
- `subprocess.Popen()` was used for `uvicorn` and `npm`. `Popen` stands for "process open" and it allows external commands to run in the **background** without blocking the rest of our python code from progressing.

### B. Threading & Time (Technology: `threading` and `time` modules)
If we just ran a loop to `POST` events right away, the Python script would lock up.
- **`time.sleep(X)`**: We used this to orchestrate exact delays (e.g., waiting 10 seconds for the backend/frontend to finish booting up before we started slamming the API with database payload requests).
- **`threading.Thread(target=simulate_live_pipeline, daemon=True)`**: A thread is a way to tell Python, "Go do this incredibly long function block off to the side, I'm going to keep running main code." Setting `daemon=True` ensures that when you finally shut down the main script via `Ctrl+C`, this thread safely gets killed instantly.

### C. Browser Automation (Technology: `webbrowser` module)
It is tedious to highlight and click `http://localhost:5173`. We used Python's built-in `webbrowser.open("http://localhost:5173")` module. Once the Python sleep timer ended, this command reached into your OS (Windows) and simply told Chrome/Edge to pop open the new tab. 

### D. The Simulator Logic (Our Own Logic + `httpx`)
We scavenged the logic from `ingest_sql_files.py`. But instead of blasting all 40 Jaffle Shop configurations to your database in 0.5 seconds, we added `time.sleep(2.5)` inside the `for` loop. This transforms a bulk-upload script into a **streaming simulator**. When you watch the UI, the pipeline will grow slowly file-by-file, matching how a real Data Factory or Airflow pipeline would update node-by-node depending on calculation times!
