# Nova AI Voice Assistant

A Python desktop voice assistant with a Tkinter GUI, speech recognition, text-to-speech, Google search, website shortcuts, live weather, and optional AI question answering.

## Requirements
- Python 3.10 or newer
- Working microphone and speakers/headphones
- Internet connection for Google speech recognition, weather, and optional AI chat

## Setup (Windows)
1. Install Python 3.10+ and select **Add Python to PATH** during installation.
2. Open this folder in VS Code.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. Copy `.env.example` to `.env`. Add your API key to `OPENAI_API_KEY` if you want AI question answering. The built-in commands and weather feature work without an AI key.
6. Run:

   ```powershell
   python main.py
   ```

## macOS / Linux notes
Create a virtual environment with `python3 -m venv .venv`, activate it with `source .venv/bin/activate`, then install `requirements.txt`. PyAudio may require PortAudio development libraries from your operating system's package manager.

## Example commands
- "What time is it?"
- "What's today's date?"
- "Open YouTube"
- "Open Gmail"
- "Search Python classes"
- "Weather in Delhi"
- "Explain what an API is"
- "Stop listening"

You can also type commands in the input box.

## Features and privacy
- Speech-to-text uses the Google Web Speech recognition service through the SpeechRecognition library. Audio is sent to that service for recognition.
- Weather uses the free Open-Meteo geocoding and forecast endpoints.
- AI chat is optional and sends your prompt to the configured AI API provider.
- The API key is read from a local `.env` file. Do not share or commit that file.
- Email sending and smart-home control are not included. Add them only with explicit authorization and secure credentials.

## Troubleshooting
- **No microphone found:** Check Windows Settings > Privacy & security > Microphone and allow desktop apps to access it.
- **PyAudio installation fails:** Use a Python version supported by the available PyAudio wheel, then retry `python -m pip install PyAudio`. On Windows, installing the matching 64-bit Python version usually helps.
- **No sound:** Check the system output device and try another `pyttsx3` voice.
- **AI answers unavailable:** Check the `.env` API key, model access, internet connection, and account billing/limits.
- **Weather lookup fails:** Check internet access and try a more specific city name.
