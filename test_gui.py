#!/usr/bin/env python3
"""Simple test GUI server to debug the issue."""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def get_root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test GUI</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background: #000; 
                color: #fff; 
                padding: 20px; 
            }
            .container { 
                max-width: 800px; 
                margin: 0 auto; 
                text-align: center; 
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Automoy Test GUI</h1>
            <p>If you can see this, the FastAPI server is working!</p>
            <p>Date: June 27, 2025</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("Starting test GUI server on http://127.0.0.1:8001")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
