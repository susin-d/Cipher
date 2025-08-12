import os
import logging
import uvicorn
import tempfile
import ffmpeg
import whisper # <-- Import the whisper library
from datetime import timedelta
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- Basic Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = FastAPI()

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LOCAL WHISPER MODEL CONFIGURATION ---
try:
    MODEL_SIZE = os.environ.get("MODEL_SIZE", "base")
    logging.info(f"--- Loading local Whisper model: {MODEL_SIZE} ---")
    # This line downloads the model to a cache directory on first run
    model = whisper.load_model(MODEL_SIZE)
    logging.info("--- Whisper model loaded successfully. ---")
except Exception as e:
    logging.error(f"Failed to load Whisper model: {e}")
    model = None


# --- Word Grouping Function for Perfect Subtitles ---
# This function is compatible with the output from the local model
def group_words_into_sentences(word_chunks, max_chars=42, pause_threshold=0.7):
    if not word_chunks:
        return []
    sentence_chunks, current_sentence = [], []
    for i, word_chunk in enumerate(word_chunks):
        current_sentence.append(word_chunk)
        current_text = ' '.join(w['text'] for w in current_sentence) # Changed from w['text'].strip()
        is_punctuation_end = word_chunk['text'].strip().endswith(('.', '?', '!'))
        is_max_len_reached = len(current_text) >= max_chars
        is_pause_after = False
        if i < len(word_chunks) - 1:
            next_word_start = word_chunks[i+1]['timestamp'][0]
            current_word_end = word_chunk['timestamp'][1]
            if current_word_end is not None and next_word_start is not None and (next_word_start - current_word_end > pause_threshold):
                is_pause_after = True
        is_last_word = (i == len(word_chunks) - 1)
        if is_last_word or is_punctuation_end or is_pause_after or is_max_len_reached:
            if not current_sentence: continue
            start_ts = current_sentence[0]['timestamp'][0]
            end_ts = current_sentence[-1]['timestamp'][1]
            sentence_chunks.append({'text': current_text, 'timestamp': [start_ts, end_ts]})
            current_sentence = []
    logging.info(f"Grouped {len(word_chunks)} words into {len(sentence_chunks)} sentences.")
    return sentence_chunks

# --- SRT Formatting Helper Function (Unchanged) ---
def format_to_srt(chunks):
    def format_srt_time(seconds_float):
        if seconds_float is None or seconds_float < 0: seconds_float = 0.0
        delta = timedelta(seconds=seconds_float)
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = delta.microseconds // 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    srt_content = []
    if not chunks: return ""
    for i, chunk in enumerate(chunks):
        start_time_val = chunk.get('timestamp', [0, 0])[0]
        end_time_val = chunk.get('timestamp', [0, 0.5])[1] or (start_time_val + 0.5)
        text = chunk.get('text', '').strip()
        start_time = format_srt_time(start_time_val)
        end_time = format_srt_time(end_time_val)
        srt_content.append(f"{i + 1}\n{start_time} --> {end_time}\n{text}\n")
    return "\n".join(srt_content)


# --- API Endpoint (Now uses local Whisper model) ---
@app.post("/api/process_local")
async def process_audio_locally(file: UploadFile = File(...)):
    if not model:
        raise HTTPException(status_code=500, detail="Whisper model is not loaded. Check server logs.")

    logging.info(f"--- API call received for file: {file.filename} ---")
    input_temp_path, output_temp_path = None, None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            input_temp_path = temp_file.name

        base_name, _ = os.path.splitext(input_temp_path)
        output_temp_path = f"{base_name}_processed.mp3"
        logging.info(f"Extracting audio from '{input_temp_path}' to '{output_temp_path}'")
        try:
            ffmpeg.input(input_temp_path).output(output_temp_path, acodec='libmp3lame', audio_bitrate='192k', **{'map_metadata': -1}).run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            error_details = e.stderr.decode() if e.stderr else "Unknown FFmpeg error"
            raise HTTPException(status_code=500, detail=f"Failed to process media file. FFmpeg error: {error_details}")

        # --- THIS IS THE CORE CHANGE: USE LOCAL MODEL ---
        logging.info(f"Transcribing '{output_temp_path}' with local Whisper model...")
        result = model.transcribe(output_temp_path, word_timestamps=True, fp16=False) # fp16=False for CPU
        
        # --- Adapt local whisper output to the format our grouping function expects ---
        all_words = []
        for segment in result.get('segments', []):
            all_words.extend(segment.get('words', []))
        
        if not all_words:
             logging.warning("Whisper did not return any words. Returning full text as one chunk.")
             full_text = result.get('text', '').strip()
             if not full_text: return PlainTextResponse(content="", media_type="text/plain")
             duration = float(ffmpeg.probe(output_temp_path)['format']['duration'])
             word_chunks_for_grouping = [{'text': full_text, 'timestamp': [0, duration]}]
        else:
            word_chunks_for_grouping = [
                {'text': word['word'].strip(), 'timestamp': [word['start'], word['end']]}
                for word in all_words
            ]

        sentence_chunks = group_words_into_sentences(word_chunks_for_grouping)
        srt_output = format_to_srt(sentence_chunks)
        return PlainTextResponse(content=srt_output, media_type="text/plain")

    except Exception as e:
        logging.error(f"An internal error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if input_temp_path and os.path.exists(input_temp_path): os.remove(input_temp_path)
        if output_temp_path and os.path.exists(output_temp_path): os.remove(output_temp_path)

# --- Static File Serving (Unchanged) ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    return FileResponse('templates/index.html')

# --- Main entry point for local execution (Unchanged) ---
if __name__ == "__main__":
    print("--- Starting local development server ---")
    print("Access the application at http://127.0.0.1:8000")
    print("NOTE: The first time you run this, it will download the Whisper model, which may take some time.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
