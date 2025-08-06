import os
import logging
import requests
import time
import uvicorn
import tempfile
import ffmpeg
from datetime import timedelta
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, Response, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- Basic Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI()

# --- CORS Middleware (Good practice for web apps) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Hugging Face API Configuration ---
HF_TOKEN = os.environ.get('HUGGING_FACE_TOKEN')
if not HF_TOKEN:
    logging.warning("HUGGING_FACE_TOKEN not found in environment. The API will not work.")
API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"


# --- SRT Formatting Helper Function ---
# FINAL VERSION: This version is robust and handles missing API timestamps.
def format_to_srt(chunks, total_duration_seconds=None):
    """
    Formats the output from the Whisper API into a standard SRT subtitle file.
    Uses the total audio duration as a fallback for missing end timestamps.
    """
    def format_srt_time(seconds_float):
        """Converts a float number of seconds to an SRT time string HH:MM:SS,ms."""
        if seconds_float is None or seconds_float < 0:
            seconds_float = 0.0
        
        delta = timedelta(seconds=seconds_float)
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = delta.microseconds // 1000
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    srt_content = []
    # If there are no chunks from the API, create one master chunk with the full text.
    if not chunks and total_duration_seconds is not None:
         # This case is less common now but good for safety
         return f"1\n{format_srt_time(0)} --> {format_srt_time(total_duration_seconds)}\n[Transcription text not available in chunks]\n"

    for i, chunk in enumerate(chunks):
        start_time_val = chunk.get('timestamp', [0, None])[0]
        end_time_val = chunk.get('timestamp', [None, 0])[1]
        text = chunk.get('text', '').strip()

        start_time = format_srt_time(start_time_val)

        # --- THE CRITICAL FIX IS HERE ---
        # If the end time is invalid (null, 0, or same as start), and we have a total duration,
        # use the total duration for the very last chunk. This correctly times single-chunk results.
        if (end_time_val is None or end_time_val <= start_time_val) and (i == len(chunks) - 1) and total_duration_seconds:
             end_time = format_srt_time(total_duration_seconds)
             logging.info(f"API returned invalid end timestamp. Using probed file duration: {total_duration_seconds}s")
        else:
             # Otherwise, use the API's provided end time.
             end_time = format_srt_time(end_time_val)

        srt_content.append(f"{i + 1}\n{start_time} --> {end_time}\n{text}\n")
        
    return "\n".join(srt_content)


# --- API Endpoint (Handles Video and Audio) ---
@app.post("/api/process_hf")
async def process_audio_with_huggingface(file: UploadFile = File(...)):
    if not HF_TOKEN:
        raise HTTPException(status_code=500, detail="Server is not configured with an API token.")
    
    logging.info(f"--- API call received for file: {file.filename} ---")
    
    input_temp_path = None
    output_temp_path = None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            input_temp_path = temp_file.name

        output_temp_path = os.path.splitext(input_temp_path)[0] + ".mp3"

        logging.info(f"Extracting audio from '{input_temp_path}' to '{output_temp_path}'")
        try:
            (
                ffmpeg
                .input(input_temp_path)
                .output(output_temp_path, acodec='libmp3lame', audio_bitrate='192k')
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            logging.info("Audio extraction successful.")
        except ffmpeg.Error as e:
            error_details = e.stderr.decode() if e.stderr else "Unknown FFmpeg error"
            logging.error(f"FFmpeg Error: {error_details}")
            raise HTTPException(status_code=500, detail=f"Failed to process media file. FFmpeg error: {error_details}")

        # --- NEW STEP: PROBE THE AUDIO FILE FOR ITS DURATION ---
        logging.info(f"Probing '{output_temp_path}' for duration...")
        probe_result = ffmpeg.probe(output_temp_path)
        audio_duration = float(probe_result['format']['duration'])
        logging.info(f"Detected audio duration: {audio_duration:.2f} seconds.")

        with open(output_temp_path, 'rb') as f:
            audio_data = f.read()

        request_headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "audio/mpeg"
        }
        params = {"return_timestamps": "chunk"}
        
        start_time = time.time()
        logging.info("Sending extracted audio to Hugging Face API...")
        response = requests.post(API_URL, headers=request_headers, data=audio_data, params=params, timeout=300)
        duration = time.time() - start_time
        logging.info(f"AI model processing took {duration:.2f} seconds.")
        
        response.raise_for_status()
        
        result = response.json()
        
        # --- PASS THE DURATION TO THE FORMATTER ---
        # The API can return the full text in 'text' and chunked text in 'chunks'.
        # We prioritize chunks if they exist.
        api_chunks = result.get('chunks')
        if not api_chunks:
            # If the API returns no chunks, create a single one from the main text
            full_text = result.get('text', '[No text returned from API]')
            api_chunks = [{'text': full_text, 'timestamp': [0, None]}]

        srt_output = format_to_srt(api_chunks, total_duration_seconds=audio_duration)
        return PlainTextResponse(content=srt_output, media_type="text/plain")
        
    except requests.exceptions.HTTPError as http_err:
        error_detail = "Unknown error"
        try:
            error_detail = http_err.response.json().get('error', http_err.response.text)
        except requests.exceptions.JSONDecodeError:
            error_detail = http_err.response.text
        logging.error(f"Hugging Face API Error: {error_detail}")
        raise HTTPException(status_code=502, detail=f"AI model processing failed: {error_detail}")
    except Exception as e:
        logging.error(f"An internal error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if input_temp_path and os.path.exists(input_temp_path):
            os.remove(input_temp_path)
        if output_temp_path and os.path.exists(output_temp_path):
            os.remove(output_temp_path)

# --- Embedded Frontend Content (unchanged) ---

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Subtitle Generator</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body class="bg-[#0b0b12] min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
    <canvas id="waveCanvas"></canvas>

    <div class="glass-effect p-8 rounded-lg shadow-2xl w-full max-w-md text-center border border-gray-700/50 z-10">
        <h1 class="text-3xl font-bold text-gray-100 mb-6">Cipher Converter</h1>
        <p class="text-gray-300 mb-8">Upload any video or audio file (MP4, MOV, MP3, etc.) to generate SRT subtitles automatically.</p>

        <div class="mb-6 flex justify-center">
            <label for="fileInputFiles" class="custom-file-upload glass-button text-gray-200 font-semibold py-3 px-6 rounded-lg">
                Choose File
            </label>
            <input type="file" id="fileInputFiles" accept="audio/*,video/*" style="display: none;">
        </div>
        <p id="fileNameDisplay" class="mt-4 text-gray-400 text-sm italic h-5"></p>

        <button id="processButton"
            class="w-full glass-button text-white font-semibold py-3 px-4 rounded-lg"
            disabled>
            Process File
        </button>

        <div id="loadingIndicator" class="mt-4 hidden">
            <div class="flex justify-center items-center space-x-2">
                <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p class="text-sm text-gray-400">Processing... this may take a moment.</p>
            </div>
        </div>

        <div id="downloadLinksContainer" class="hidden mt-6">
            <h3 class="text-lg font-semibold text-gray-200 mb-2">Download Your File:</h3>
            <div id="downloadLinksList" class="text-center"></div>
        </div>

        <div id="messageArea" class="mt-6 text-sm text-red-400 min-h-[20px]"></div>
    </div>

    <script src="/static/js/script.js" defer></script>
</body>
</html>
"""

CSS_CONTENT = """
/* --- Global Styles & Font --- */
body {
    font-family: 'Inter', sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* --- Main Glass Effect Card --- */
.glass-effect {
    background: rgba(18, 18, 28, 0.7);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}

/* --- Canvas Background --- */
#waveCanvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 0;
}


/* --- Glossy Glass Button Style --- */
.glass-button {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
}

.glass-button:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.4);
    transform: scale(1.05);
}

.glass-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* --- Custom File Upload Styling --- */
input[type="file"] {
    display: none;
}

.custom-file-upload {
    display: inline-block;
    cursor: pointer;
}

.hidden {
    display: none !important;
}
"""

JS_CONTENT = """
document.addEventListener('DOMContentLoaded', () => {
    // --- 1. DOM Element Selection ---
    const fileInputFiles = document.getElementById('fileInputFiles');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    const processButton = document.getElementById('processButton');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const messageArea = document.getElementById('messageArea');
    const downloadLinksContainer = document.getElementById('downloadLinksContainer');
    const downloadLinksList = document.getElementById('downloadLinksList');
    const canvas = document.getElementById('waveCanvas');
    const ctx = canvas.getContext('2d');

    // --- 2. State Management ---
    let selectedFile = null;

    // --- 3. Main Application Logic ---
    fileInputFiles.addEventListener('change', (event) => {
        if (event.target.files.length > 0) {
            selectedFile = event.target.files[0];
            fileNameDisplay.textContent = `Selected: ${selectedFile.name}`;
            messageArea.textContent = '';
            downloadLinksContainer.classList.add('hidden');
            processButton.disabled = false;
        } else {
            selectedFile = null;
            fileNameDisplay.textContent = '';
            processButton.disabled = true;
        }
    });

    processButton.addEventListener('click', async () => {
        if (!selectedFile) {
            messageArea.textContent = 'Please select a file first.';
            return;
        }
        processButton.disabled = true;
        loadingIndicator.classList.remove('hidden');
        messageArea.textContent = '';
        downloadLinksContainer.classList.add('hidden');
        downloadLinksList.innerHTML = '';
        
        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('/api/process_hf', { method: 'POST', body: formData });
            
            if (!response.ok) {
                const contentType = response.headers.get("content-type");
                let errorMessage;
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || 'An unknown server error occurred.';
                } else { 
                    errorMessage = await response.text(); 
                }
                throw new Error(errorMessage);
            }
            
            const srtContent = await response.text();
            const blob = new Blob([srtContent], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const originalFileName = selectedFile.name.split('.').slice(0, -1).join('.');
            
            const link = document.createElement('a');
            link.href = url;
            link.download = `${originalFileName}.srt`;
            link.textContent = `Download Subtitles (.srt)`;
            link.className = "text-violet-400 hover:text-violet-300 underline block text-lg";
            
            downloadLinksList.appendChild(link);
            downloadLinksContainer.classList.remove('hidden');

        } catch (error) {
            console.error('An error occurred during processing:', error);
            messageArea.textContent = `Error: ${error.message}`;
        } finally {
            loadingIndicator.classList.add('hidden');
            processButton.disabled = false;
        }
    });

    // --- 4. CONSTELLATION PARTICLE NETWORK ANIMATION ---
    let particles = [];
    const numParticles = 100;
    const maxDistance = 120;
    const particleSpeed = 0.5;
    const mouse = { x: undefined, y: undefined };

    window.addEventListener('mousemove', (event) => {
        mouse.x = event.x;
        mouse.y = event.y;
    });
    
    window.addEventListener('mouseout', () => {
        mouse.x = undefined;
        mouse.y = undefined;
    });

    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * particleSpeed;
            this.vy = (Math.random() - 0.5) * particleSpeed;
            this.radius = Math.random() * 1.5 + 1;
            this.hue = 220 + Math.random() * 80;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;
            if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = `hsl(${this.hue}, 100%, 70%)`;
            ctx.fill();
        }
    }

    function setupAnimation() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        particles = [];
        for (let i = 0; i < numParticles; i++) {
            particles.push(new Particle());
        }
    }

    function drawLines() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < maxDistance) {
                    const opacity = 1 - distance / maxDistance;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(191, 128, 255, ${opacity})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
    }
    
    function drawMouseLines() {
        if (mouse.x === undefined) return;

        for (let i = 0; i < particles.length; i++) {
            const dx = particles[i].x - mouse.x;
            const dy = particles[i].y - mouse.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < maxDistance * 1.5) {
                const opacity = 1 - distance / (maxDistance * 1.5);
                ctx.beginPath();
                ctx.moveTo(particles[i].x, particles[i].y);
                ctx.lineTo(mouse.x, mouse.y);
                ctx.strokeStyle = `rgba(160, 180, 255, ${opacity})`;
                ctx.lineWidth = 0.7;
                ctx.stroke();
            }
        }
    }

    function animate() {
        ctx.fillStyle = '#0b0b12';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => { p.update(); p.draw(); });
        drawLines();
        drawMouseLines();
        requestAnimationFrame(animate);
    }
    
    window.addEventListener('resize', setupAnimation);
    setupAnimation();
    animate();
});
"""


# --- Static File Serving (from embedded content) ---
@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serves the main HTML page."""
    return HTMLResponse(content=HTML_CONTENT)

@app.get("/static/css/style.css")
async def read_css():
    """Serves the CSS file."""
    return Response(content=CSS_CONTENT, media_type="text/css")

@app.get("/static/js/script.js")
async def read_js():
    """Serves the JavaScript file."""
    return Response(content=JS_CONTENT, media_type="application/javascript")


# --- Main entry point for local execution ---
if __name__ == "__main__":
    print("--- Starting local development server ---")
    print("Access the application at http://127.0.0.1:8000")
    print("Ensure you have a .env file with HUGGING_FACE_TOKEN set.")
    print("Ensure FFmpeg is installed on your system.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
