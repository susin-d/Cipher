# Cipher Converter: AI Subtitle Generator

Cipher Converter is a sleek, single-file web application that automatically generates subtitle files (`.srt`) from audio or video sources.

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
