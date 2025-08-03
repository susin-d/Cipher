# Cipher Converter: AI Subtitle Generator

Cipher Converter is a sleek, single-file web application that automatically generates subtitle files (`.srt`) from audio or video sources. It leverages the power of the Hugging Face Inference API, specifically using OpenAI's Whisper model, to provide fast and accurate transcriptions with timestamps.

The entire application—backend, frontend, and styling—is contained within a single `app.py` file, making it incredibly easy to deploy on platforms like Render.



## Features

-   **AI-Powered Transcription**: Utilizes the `openai/whisper-large-v3` model via the Hugging Face API for state-of-the-art speech-to-text conversion.
-   **Timestamped Subtitles**: Generates subtitles in the standard SRT format, including accurate start and end times for each text chunk.
-   **Broad File Support**: Accepts common audio and video formats like `.mp3`, `.mp4`, `.m4a`, and `.wav`.
-   **Modern & Interactive UI**:
    -   A clean, "glassmorphism" design built with Tailwind CSS.
    -   An interactive particle network animation in the background, created with HTML Canvas.
    -   Responsive for a seamless experience on different devices.
-   **Single-File Deployment**: The Python backend (FastAPI), HTML, CSS, and JavaScript are all self-contained in `app.py`, simplifying the deployment process.
-   **User-Friendly**: Provides clear loading indicators, error messages, and a direct download link for the generated file.

## Tech Stack

-   **Backend**: Python, FastAPI
-   **AI Model**: Hugging Face Inference API (`openai/whisper-large-v3`)
-   **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript
-   **Server**: Uvicorn
-   **Deployment**: Designed for Render

## How It Works

1.  **File Upload**: The user selects an audio or video file through the web interface.
2.  **API Request**: The FastAPI backend receives the file and securely streams it to the Hugging Face Inference API, along with the user's API token.
3.  **AI Processing**: The Whisper model transcribes the audio, generating text chunks complete with timestamps.
4.  **SRT Formatting**: The backend receives the JSON response from the API and formats it into a valid `.srt` file content.
5.  **Download**: The formatted SRT content is sent back to the frontend, where JavaScript creates a blob and presents a download link to the user.

## Setup and Running Locally

### Prerequisites

-   Python 3.8+
-   A Hugging Face account with a User Access Token (read role is sufficient).

### Instructions

1.  **Clone the Repository (or save `app.py`)**
    If this were in a repository, you would clone it. Otherwise, just save the `app.py` file to a new directory.

2.  **Install Dependencies**
    Open your terminal in the project directory and run:
    ```bash
    pip install "fastapi[all]" requests python-dotenv
    ```

3.  **Create an Environment File**
    Create a file named `.env` in the same directory as `app.py`. Add your Hugging Face token to this file:
    ```
    HUGGING_FACE_TOKEN="hf_YourSecretTokenHere"
    ```

4.  **Run the Application**
    Start the local server with the following command:
    ```bash
    python app.py
    ```

5.  **Access the App**
    Open your web browser and navigate to `http://127.0.0.1:8000`.

## Deployment to Render

This application is optimized for a straightforward deployment on Render.

1.  **Push to GitHub**: Make sure your `app.py` file is in a GitHub repository.
2.  **Create a New Web Service on Render**:
    -   Connect your GitHub account and select the repository.
    -   Render will detect it's a Python app.
3.  **Configure the Settings**:
    -   **Build Command**: `pip install "fastapi[all]" requests`
    -   **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4.  **Add Environment Variable**:
    -   Go to the **Environment** tab for your new service.
    -   Click **Add Environment Variable** or **Add Secret File**.
    -   **Key**: `HUGGING_FACE_TOKEN`
    -   **Value**: Paste your Hugging Face token (e.g., `hf_YourSecretTokenHere`).
5.  **Deploy**:
    -   Click **Create Web Service**. Render will automatically build and deploy your application. Your subtitle generator will be live at the URL provided by Render.
