import os
import queue
import re
import threading
import webbrowser
from datetime import datetime
from urllib.parse import quote_plus

import tkinter as tk
from tkinter import ttk, messagebox

import speech_recognition as sr
import pyttsx3
import requests
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "NOVA"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
WEATHER_DEFAULT_CITY = os.getenv("WEATHER_DEFAULT_CITY", "").strip()


class NovaAssistant:
    """Voice assistant logic. UI updates are sent through a thread-safe queue."""

    def __init__(self, events):
        self.events = events
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.stop_event = threading.Event()
        self.listening = False
        self.speaker_lock = threading.Lock()
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 175)
        self.engine.setProperty("volume", 1.0)
        self.engine_lock = threading.Lock()

    def emit(self, kind, text):
        self.events.put((kind, text))

    def speak(self, text):
        self.emit("assistant", text)
        def run_speech():
            try:
                with self.engine_lock:
                    self.engine.say(text)
                    self.engine.runAndWait()
            except Exception as exc:
                self.emit("error", f"Speech output error: {exc}")
        threading.Thread(target=run_speech, daemon=True).start()

    def start_listening(self):
        if self.listening:
            return
        self.stop_event.clear()
        self.listening = True
        threading.Thread(target=self._listen_loop, daemon=True).start()
        self.emit("status", "Listening. Speak a command.")

    def stop_listening(self):
        self.stop_event.set()
        self.listening = False
        self.emit("status", "Listening stopped.")

    def _listen_loop(self):
        try:
            with sr.Microphone() as source:
                self.emit("status", "Calibrating microphone...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                self.emit("status", "Listening. Speak a command.")
                while not self.stop_event.is_set():
                    try:
                        audio = self.recognizer.listen(
                            source, timeout=1, phrase_time_limit=8
                        )
                    except sr.WaitTimeoutError:
                        continue
                    try:
                        text = self.recognizer.recognize_google(audio)
                        self.emit("user", text)
                        self.handle_command(text)
                    except sr.UnknownValueError:
                        self.emit("status", "I couldn't understand that. Try again.")
                    except sr.RequestError:
                        self.emit("error", "Speech recognition service unavailable. Check your internet connection.")
                        break
        except (OSError, AttributeError) as exc:
            self.emit("error", f"Microphone problem: {exc}\nCheck microphone permissions and PyAudio installation.")
        finally:
            self.listening = False
            self.emit("status", "Not listening.")

    def handle_command(self, raw_text):
        text = raw_text.lower().strip()
        if not text:
            return

        if any(x in text for x in ("stop listening", "pause listening")):
            self.stop_listening()
            self.speak("I have stopped listening.")
        elif any(x in text for x in ("goodbye", "exit assistant", "quit assistant")):
            self.stop_listening()
            self.speak("Goodbye. See you soon.")
        elif "time" in text:
            self.speak("The time is " + datetime.now().strftime("%I:%M %p"))
        elif "date" in text or "today" in text:
            self.speak("Today is " + datetime.now().strftime("%A, %d %B %Y"))
        elif "open youtube" in text:
            webbrowser.open("https://www.youtube.com")
            self.speak("Opening YouTube.")
        elif "open google" in text:
            webbrowser.open("https://www.google.com")
            self.speak("Opening Google.")
        elif "open gmail" in text:
            webbrowser.open("https://mail.google.com")
            self.speak("Opening Gmail.")
        elif text.startswith("search for ") or text.startswith("search "):
            query = re.sub(r"^search(?: for)? ", "", text).strip()
            if query:
                webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
                self.speak("Here are the search results for " + query)
            else:
                self.speak("Tell me what you want to search for.")
        elif "weather" in text:
            city = re.sub(r".*weather(?:\s+in)?", "", text).strip(" ?")
            city = city or WEATHER_DEFAULT_CITY
            if not city:
                self.speak("Please say weather in, followed by a city name.")
            else:
                self.get_weather(city)
        elif text.startswith("ask ") or text.startswith("explain ") or text.startswith("what is "):
            prompt = re.sub(r"^(ask|explain|what is)\s*", "", raw_text, flags=re.I).strip()
            self.ask_ai(prompt or raw_text)
        elif "help" in text or "what can you do" in text:
            self.speak("I can tell the time and date, search Google, open websites, check weather, and answer questions when an AI key is configured.")
        else:
            self.ask_ai(raw_text)

    def get_weather(self, city):
        self.emit("status", f"Getting weather for {city}...")
        try:
            geo = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "en", "format": "json"},
                timeout=10
            )
            geo.raise_for_status()
            results = geo.json().get("results", [])
            if not results:
                self.speak(f"I couldn't find a location called {city}.")
                return
            place = results[0]
            forecast = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "timezone": "auto"
                },
                timeout=10
            )
            forecast.raise_for_status()
            current = forecast.json()["current"]
            summary = (
                f"In {place['name']}, it is {current['temperature_2m']} degrees Celsius, "
                f"feels like {current['apparent_temperature']} degrees, "
                f"with humidity at {current['relative_humidity_2m']} percent "
                f"and wind speed {current['wind_speed_10m']} kilometres per hour."
            )
            self.speak(summary)
        except requests.RequestException as exc:
            self.emit("error", f"Weather request failed: {exc}")

    def ask_ai(self, prompt):
        if not OPENAI_API_KEY:
            self.speak("AI chat is not configured yet. Add your API key to the .env file. I can still handle my built-in commands.")
            return
        self.emit("status", "Thinking...")
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are Nova, a helpful, concise desktop voice assistant. Keep spoken answers brief and clear."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5
                },
                timeout=30
            )
            response.raise_for_status()
            answer = response.json()["choices"][0]["message"]["content"].strip()
            self.speak(answer)
        except requests.RequestException as exc:
            self.emit("error", f"AI request failed: {exc}")
        except (KeyError, IndexError, ValueError):
            self.emit("error", "The AI service returned an unexpected response.")


class NovaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova AI Voice Assistant")
        self.root.geometry("850x650")
        self.root.minsize(720, 540)
        self.root.configure(bg="#101522")
        self.events = queue.Queue()
        self.assistant = NovaAssistant(self.events)
        self._build_ui()
        self._poll_events()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.add_message("Nova", "Hello! I'm Nova. Press Start Listening or type a command below.")
        self.add_message("Nova", "Try: 'What time is it?', 'Weather in Delhi', or 'Search Python tutorials'.")

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 10), padding=9)
        style.configure("TEntry", padding=9)

        header = tk.Frame(self.root, bg="#101522")
        header.pack(fill="x", padx=24, pady=(20, 10))
        tk.Label(header, text="NOVA", font=("Segoe UI", 26, "bold"),
                 fg="#8bd5ff", bg="#101522").pack(anchor="w")
        tk.Label(header, text="YOUR PYTHON AI VOICE ASSISTANT",
                 font=("Segoe UI", 9, "bold"), fg="#8a94a8",
                 bg="#101522").pack(anchor="w")

        self.status = tk.Label(self.root, text="● Ready", anchor="w",
                               font=("Segoe UI", 10), fg="#77e0b5",
                               bg="#182235", padx=14, pady=10)
        self.status.pack(fill="x", padx=24, pady=8)

        chat_frame = tk.Frame(self.root, bg="#182235", bd=0)
        chat_frame.pack(fill="both", expand=True, padx=24, pady=10)
        self.chat = tk.Text(
            chat_frame, wrap="word", state="disabled",
            bg="#182235", fg="#e7edf7", insertbackground="white",
            font=("Segoe UI", 11), relief="flat", padx=16, pady=14,
            spacing1=5, spacing3=9
        )
        scrollbar = ttk.Scrollbar(chat_frame, command=self.chat.yview)
        self.chat.configure(yscrollcommand=scrollbar.set)
        self.chat.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.chat.tag_configure("user", foreground="#8bd5ff", font=("Segoe UI", 10, "bold"))
        self.chat.tag_configure("nova", foreground="#77e0b5", font=("Segoe UI", 10, "bold"))
        self.chat.tag_configure("body", foreground="#e7edf7")

        controls = tk.Frame(self.root, bg="#101522")
        controls.pack(fill="x", padx=24, pady=(5, 20))
        self.start_btn = ttk.Button(controls, text="🎙 Start Listening", command=self.start)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(controls, text="■ Stop", command=self.stop)
        self.stop_btn.pack(side="left", padx=(0, 12))

        self.command_entry = ttk.Entry(controls)
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.command_entry.bind("<Return>", lambda event: self.send_typed())
        ttk.Button(controls, text="Send", command=self.send_typed).pack(side="left")

        footer = tk.Label(self.root, text="Voice recognition requires an internet connection. Your API key stays in your local .env file.",
                          bg="#101522", fg="#77839a", font=("Segoe UI", 8))
        footer.pack(pady=(0, 10))

    def add_message(self, speaker, message):
        self.chat.configure(state="normal")
        tag = "user" if speaker.lower() == "you" else "nova"
        self.chat.insert("end", f"{speaker}\n", tag)
        self.chat.insert("end", f"{message}\n\n", "body")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def start(self):
        self.assistant.start_listening()

    def stop(self):
        self.assistant.stop_listening()

    def send_typed(self):
        command = self.command_entry.get().strip()
        if not command:
            return
        self.command_entry.delete(0, "end")
        self.add_message("You", command)
        threading.Thread(target=self.assistant.handle_command, args=(command,), daemon=True).start()

    def _poll_events(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "user":
                    self.add_message("You", text)
                elif kind == "assistant":
                    self.add_message("Nova", text)
                elif kind == "status":
                    self.status.config(text="● " + text)
                elif kind == "error":
                    self.add_message("System", text)
                    self.status.config(text="● Attention needed")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def close(self):
        self.assistant.stop_listening()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = NovaGUI(root)
    root.mainloop()
