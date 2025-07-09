#!/usr/bin/env python3
"""Simplified GUI to test if the main template loads."""

import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Mount static files
script_dir = os.path.dirname(__file__)
static_files_path = os.path.join(script_dir, "gui", "static")
if os.path.exists(static_files_path):
    app.mount("/static", StaticFiles(directory=static_files_path), name="static")
    print(f"Static files mounted from: {static_files_path}")
else:
    print(f"Static files directory not found: {static_files_path}")

@app.get("/", response_class=HTMLResponse)
async def get_root():
    try:
        template_path = os.path.join(script_dir, "gui", "templates", "index.html")
        print(f"Looking for template at: {template_path}")
        
        if not os.path.exists(template_path):
            print(f"Template file not found at: {template_path}")
            return HTMLResponse(content="""
                <html><body style='background:#000;color:#fff;font-family:Arial;padding:20px;'>
                <h1>Template Not Found</h1>
                <p>Template path: {}</p>
                </body></html>
            """.format(template_path))
        
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        print("Template loaded successfully")
        return HTMLResponse(content=html_content)
    except Exception as e:
        print(f"Error loading template: {e}")
        return HTMLResponse(content=f"""
            <html><body style='background:#000;color:#fff;font-family:Arial;padding:20px;'>
            <h1>Error Loading Template</h1>
            <p>Error: {e}</p>
            </body></html>
        """)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("Starting simplified GUI server on http://127.0.0.1:8001")
    print(f"Script directory: {script_dir}")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
