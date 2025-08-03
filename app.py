# app.py

import os
import logging
import requests
import time
import uvicorn  # Import uvicorn to run the app
from datetime import timedelta
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI()

# --- CORS Middleware (Still good practice) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Hugging Face API Configuration ---
# For local development, it's good practice to use a .env file.
# On Render, you will set this as an environment variable.
HF_TOKEN = os.environ.get('HUGGING_FACE_TOKEN')
if not HF_TOKEN:
    logging.warning("HUGGING_FACE_TOKEN not found in environment. The API will not work.")

API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"


# --- SRT Formatting Helper Function (Unchanged) ---
def format_to_srt(chunks):
    # This function is the same as before
    srt_content = []
    for i, chunk in enumerate(chunks):
        start_time_sec = chunk.get('timestamp', [0, None])[0] or 0
        end_time_sec = chunk.get('timestamp', [None, 0])[1] or start_time_sec
        text = chunk.get('text', '').strip()
        start_delta = timedelta(seconds=start_time_sec)
        end_delta = timedelta(seconds=end_time_sec)
        start_srt_time = f"{int(start_delta.total_seconds()) // 3600:02d}:{int(start_delta.total_seconds()) // 60 % 60:02d}:{int(start_delta.total_seconds()) % 60:02d},{start_delta.microseconds // 1000:03d}"
        end_srt_time = f"{int(end_delta.total_seconds()) // 3600:02d}:{int(end_delta.total_seconds()) // 60 % 60:02d}:{int(end_delta.total_seconds()) % 60:02d},{end_delta.microseconds // 1000:03d}"
        srt_content.append(f"{i + 1}\n{start_srt_time} --> {end_srt_time}\n{text}\n")
    return "\n".join(srt_content)


# --- API Endpoint (The Backend Logic) ---
@app.post("/api/process_hf")
async def process_audio_with_huggingface(file: UploadFile = File(...)):
    if not HF_TOKEN:
        raise HTTPException(status_code=500, detail="Server is not configured with an API token.")
    
    logging.info(f"--- API call received for file: {file.filename} ---")
    try:
        audio_data = await file.read()
        request_headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": file.content_type}
        params = {"return_timestamps": "chunk"}
        
        start_time = time.time()
        response = requests.post(API_URL, headers=request_headers, data=audio_data, params=params, timeout=300)
        duration = time.time() - start_time
        logging.info(f"AI model processing took {duration:.2f} seconds.")
        
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        result = response.json()
        srt_output = format_to_srt(result.get('chunks', []))
        return PlainTextResponse(content=srt_output, media_type="text/plain")
        
    except requests.exceptions.HTTPError as http_err:
        error_detail = http_err.response.json().get('error', http_err.response.text)
        logging.error(f"Hugging Face API Error: {error_detail}")
        raise HTTPException(status_code=502, detail=f"AI model processing failed: {error_detail}")
    except Exception as e:
        logging.error(f"An internal error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Static File Serving (The Frontend Logic) ---

# This line "mounts" the static directory, making files like CSS and JS available.
app.mount("/static", StaticFiles(directory="static"), name="static")

# This route serves your main index.html file.
@app.get("/")
async def read_index():
    return FileResponse('index.html')


# --- This block allows you to run the app directly with `python app.py` ---
if __name__ == "__main__":
    print("Starting local server at http://127.0.0.1:8000")
    # For local development, create a file named .env and add:
    # HUGGING_FACE_TOKEN="hf_your_token_here"
    uvicorn.run(app, host="127.0.0.1", port=8000)