from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import subprocess
import threading
import time

# Define base directory (where this script lives)
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.txt")

app = FastAPI()

# Mount static files (CSS/JS) and HTML templates
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/command")
async def main_command(command: str = Form(...)):
    print(f"Main command received: {command}")
    return {"status": "success", "message": f"Command '{command}' received."}

@app.post("/correction")
async def correction_command(message: str = Form(...)):
    print(f"Correction message received: {message}")
    return {"status": "success", "message": f"Correction '{message}' received."}

@app.post("/temperature")
async def set_temperature(value: float = Form(...)):
    # Update config.txt
    lines = []
    with open(CONFIG_PATH, "r") as f:
        lines = f.readlines()
    with open(CONFIG_PATH, "w") as f:
        for line in lines:
            if line.strip().startswith("TEMPERATURE:"):
                f.write(f"TEMPERATURE: {value}\n")
            else:
                f.write(line)
    print(f"Temperature updated to {value}")
    return {"status": "success", "value": value}

# Track GUI visibility state (simple in-memory flag for demo)
GUI_VISIBLE = True
CONSOLE_LOG = []

@app.get("/show_gui")
async def show_gui():
    global GUI_VISIBLE
    GUI_VISIBLE = True
    return {"status": "shown"}

@app.get("/hide_gui")
async def hide_gui():
    global GUI_VISIBLE
    GUI_VISIBLE = False
    return {"status": "hidden"}

@app.get("/gui_state")
async def gui_state():
    return {"visible": GUI_VISIBLE}

@app.get("/console_output")
async def get_console_output():
    # Return the last 100 lines of console output
    return {"output": CONSOLE_LOG[-100:]}

# Utility to append to console log (thread-safe)
def append_console_log(line):
    if len(CONSOLE_LOG) > 1000:
        del CONSOLE_LOG[:500]
    CONSOLE_LOG.append(line)

# Example: wrap print to also log to GUI
import builtins
_builtin_print = builtins.print
def gui_print(*args, **kwargs):
    msg = ' '.join(str(a) for a in args)
    append_console_log(msg)
    _builtin_print(*args, **kwargs)
builtins.print = gui_print

# Endpoint to trigger screenshot (simulate hiding GUI, taking screenshot, then showing GUI)
@app.post("/take_screenshot")
async def take_screenshot(background_tasks: BackgroundTasks):
    # Hide GUI
    global GUI_VISIBLE
    GUI_VISIBLE = False
    # Simulate screenshot (replace with actual call if needed)
    def do_screenshot():
        time.sleep(1.5)  # Simulate screenshot delay
        # Show GUI again
        global GUI_VISIBLE
        GUI_VISIBLE = True
        append_console_log("[GUI] Screenshot taken, GUI restored.")
    background_tasks.add_task(do_screenshot)
    append_console_log("[GUI] Screenshot triggered, GUI hidden.")
    return {"status": "screenshot_in_progress"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
