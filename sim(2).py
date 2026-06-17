"""
Голосовой помощник "Сим"
"""


import speech_recognition as sr
import pyttsx3
import subprocess
import os
import json
import threading
import re
import urllib.request
import urllib.parse
import queue as _queue
import time as _time
from datetime import datetime
import ctypes

GITHUB_TOKEN = "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"
ALL_WAKE_WORDS = ["сим", "sim", "симм", "сима", "симо", "syim", "seem"]

APPS = {
    "блокнот": "notepad.exe", "notepad": "notepad.exe",
    "калькулятор": "calc.exe", "calculator": "calc.exe",
    "проводник": "explorer.exe",
    "paint": "mspaint.exe", "пейнт": "mspaint.exe",
    "хром": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "фаерфокс": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "эдж": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "телеграм": os.path.join(os.getenv("APPDATA",""),"Telegram Desktop","Telegram.exe"),
    "telegram": os.path.join(os.getenv("APPDATA",""),"Telegram Desktop","Telegram.exe"),
    "тг": os.path.join(os.getenv("APPDATA",""),"Telegram Desktop","Telegram.exe"),
    "дискорд": os.path.join(os.getenv("LOCALAPPDATA",""),"Discord","Update.exe"),
    "discord": os.path.join(os.getenv("LOCALAPPDATA",""),"Discord","Update.exe"),
    "spotify": os.path.join(os.getenv("APPDATA",""),"Spotify","Spotify.exe"),
    "спотифай": os.path.join(os.getenv("APPDATA",""),"Spotify","Spotify.exe"),
    "стим": r"C:\Program Files (x86)\Steam\steam.exe",
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "vscode": os.path.join(os.getenv("LOCALAPPDATA",""),"Programs","Microsoft VS Code","Code.exe"),
    "диспетчер задач": "taskmgr.exe", "диспетчер": "taskmgr.exe",
    "cmd": "cmd.exe", "командная строка": "cmd.exe", "консоль": "cmd.exe",
    "powershell": "powershell.exe",
    "ворд": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "эксель": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
}

# ─── TTS ──────────────────────────────────────────────────────────────────────

engine = pyttsx3.init()
engine.setProperty("rate", 165)
engine.setProperty("volume", 1.0)
for v in engine.getProperty("voices"):
    if any(x in v.id.lower()+v.name.lower() for x in ["irina","elena","anna","rhvoice","ru","russian"]):
        engine.setProperty("voice", v.id)
        break

tts_lock = threading.Lock()

def speak(text: str):
    print(f"\n[СИМ] {text}")
    with tts_lock:
        engine.say(text)
        engine.runAndWait()

# ─── МИКРОФОН ─────────────────────────────────────────────────────────────────

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5
recognizer.energy_threshold = 150
recognizer.pause_threshold = 1.0
recognizer.phrase_threshold = 0.1
recognizer.non_speaking_duration = 0.8

mic = sr.Microphone()

print("[МИК] Калибровка...")
with mic as source:
    recognizer.adjust_for_ambient_noise(source, duration=2)
print(f"[МИК] Готово. Чувствительность: {int(recognizer.energy_threshold)}")

def listen_once(timeout=10, phrase_limit=20):
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.2)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return None
    try:
        return recognizer.recognize_google(audio, language="ru-RU").lower().strip()
    except sr.UnknownValueError:
        old = recognizer.energy_threshold
        recognizer.energy_threshold = max(50, old * 0.7)
        try:
            with mic as src:
                audio2 = recognizer.listen(src, timeout=2, phrase_time_limit=phrase_limit)
            return recognizer.recognize_google(audio2, language="ru-RU").lower().strip()
        except Exception:
            recognizer.energy_threshold = old
            return None
    except sr.RequestError:
        return None

def contains_wake_word(text: str) -> bool:
    words = re.split(r'[\s,\.!?]+', text.lower())
    return any(ww in words for ww in ALL_WAKE_WORDS)

def extract_command(text: str) -> str:
    result = text.lower()
    for ww in ALL_WAKE_WORDS:
        result = re.sub(rf'\b{ww}\b', '', result)
    return result.strip(" ,.")

# ─── ОТКРЫТИЕ URL ─────────────────────────────────────────────────────────────

def open_url(url: str):
    subprocess.Popen(["rundll32.exe", "url.dll,FileProtocolHandler", url],
                     creationflags=subprocess.CREATE_NO_WINDOW)

# ─── ЗАПУСК ПРИЛОЖЕНИЙ ────────────────────────────────────────────────────────

_app_cache = {}
_last_launched = {}

def launch_app(app_name: str):
    now = _time.time()
    if app_name in _last_launched and now - _last_launched[app_name] < 3.0:
        print(f"[ЗАЩИТА] {app_name} уже запускался")
        return True
    _last_launched[app_name] = now

    path = APPS.get(app_name) or _app_cache.get(app_name)
    if path:
        _app_cache[app_name] = path
        try:
            subprocess.Popen([path], creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception:
            pass
    try:
        subprocess.Popen(["cmd", "/c", "start", "", app_name],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False

# ─── SPOTIFY ──────────────────────────────────────────────────────────────────

_spotify_last_action_time = 0

def spotify_control(action: str, query: str = ""):
    global _spotify_last_action_time
    # Защита от двойного нажатия — не чаще раза в 2 секунды
    now = _time.time()
    if now - _spotify_last_action_time < 2.0:
        print(f"[SPOTIFY] Игнорирую дубль: {action}")
        return
    _spotify_last_action_time = now

    spotify_path = os.path.join(os.getenv("APPDATA",""), "Spotify", "Spotify.exe")

    def send_media_key(key_code):
        ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
        _time.sleep(0.05)
        ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)

    VK_MEDIA_PLAY_PAUSE = 179
    VK_MEDIA_NEXT_TRACK = 176
    VK_MEDIA_PREV_TRACK = 177

    if action == "play":
        result = subprocess.run("tasklist", capture_output=True, text=True)
        if "Spotify.exe" not in result.stdout:
            if os.path.exists(spotify_path):
                subprocess.Popen([spotify_path])
                for _ in range(20):
                    _time.sleep(1)
                    check = subprocess.run("tasklist", capture_output=True, text=True)
                    if "Spotify.exe" in check.stdout:
                        _time.sleep(5)
                        break
        if query:
            open_url(f"https://open.spotify.com/search/{urllib.parse.quote(query)}")
            _time.sleep(2)
        _time.sleep(0.5)
        send_media_key(VK_MEDIA_PLAY_PAUSE)
        _time.sleep(0.5)  # Ждём чтобы не сработало дважды

    elif action == "pause":
        send_media_key(VK_MEDIA_PLAY_PAUSE)
    elif action == "next":
        send_media_key(VK_MEDIA_NEXT_TRACK)
    elif action == "prev":
        send_media_key(VK_MEDIA_PREV_TRACK)

# ─── ГРОМКОСТЬ ────────────────────────────────────────────────────────────────

def volume_control(action: str, level: int = 5):
    if action == "up":
        script = f"$o=New-Object -ComObject WScript.Shell; for($i=0;$i -lt {level};$i++){{$o.SendKeys([char]175)}}"
    elif action == "down":
        script = f"$o=New-Object -ComObject WScript.Shell; for($i=0;$i -lt {level};$i++){{$o.SendKeys([char]174)}}"
    elif action == "mute":
        script = "$o=New-Object -ComObject WScript.Shell; $o.SendKeys([char]173)"
    else:
        return
    subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", script],
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

# ─── БЫСТРЫЕ КОМАНДЫ (без ИИ) ─────────────────────────────────────────────────

QUICK_COMMANDS = {
    "включи музыку": ("spotify_cmd", "play"),
    "поставь музыку": ("spotify_cmd", "play"),
    "запусти музыку": ("spotify_cmd", "play"),
    "открой музыку": ("spotify_cmd", "play"),
    "следующий трек": ("spotify_cmd", "next"),
    "предыдущий трек": ("spotify_cmd", "prev"),
    "выключи звук": ("volume", "mute"),
    "хром": ("open_app", "chrome"),
    "chrome": ("open_app", "chrome"),
    "браузер": ("open_app", "edge"),
    "edge": ("open_app", "edge"),
    "телеграм": ("open_app", "телеграм"),
    "telegram": ("open_app", "телеграм"),
    "тг": ("open_app", "телеграм"),
    "дискорд": ("open_app", "дискорд"),
    "discord": ("open_app", "дискорд"),
    "spotify": ("open_app", "spotify"),
    "спотифай": ("open_app", "spotify"),
    "музыку": ("open_app", "spotify"),
    "музыка": ("open_app", "spotify"),
    "ютуб": ("open_website", "https://youtube.com"),
    "youtube": ("open_website", "https://youtube.com"),
    "вк": ("open_website", "https://vk.com"),
    "следующий": ("spotify_cmd", "next"),
    "предыдущий": ("spotify_cmd", "prev"),
    "пауза": ("spotify_cmd", "pause"),
    "громче": ("volume", "up"),
    "тише": ("volume", "down"),
}

def try_quick_command(cmd_text: str) -> bool:
    t = cmd_text.lower().strip()
    for phrase in sorted(QUICK_COMMANDS.keys(), key=len, reverse=True):
        if phrase in t:
            action, val = QUICK_COMMANDS[phrase]
            print(f"[БЫСТРО] {phrase} -> {action}:{val}")
            if action == "open_app":
                launch_app(val)
            elif action == "open_website":
                open_url(val)
            elif action == "spotify_cmd":
                spotify_control(val)
            elif action == "volume":
                volume_control(val)
            return True
    return False

# ─── ПОГОДА ───────────────────────────────────────────────────────────────────

def get_weather(city: str) -> str:
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=ru"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cur = data["current_condition"][0]
        desc = cur["lang_ru"][0]["value"] if cur.get("lang_ru") else cur["weatherDesc"][0]["value"]
        return f"В {city}: {desc}, {cur['temp_C']} градусов, ощущается как {cur['FeelsLikeC']}. Ветер {cur['windspeedKmph']} км/ч."
    except Exception:
        return f"Не удалось получить погоду для {city}."

# ─── ПОИСК ИНФОРМАЦИИ ─────────────────────────────────────────────────────────

def find_info(query: str) -> str:
    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Ты голосовой помощник. Отвечай коротко — 2-3 предложения. Только суть, по-русски, как другу."},
            {"role": "user", "content": query}
        ],
        "max_tokens": 200, "temperature": 0.5
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://models.inference.ai.azure.com/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {GITHUB_TOKEN}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[INFO ОШИБКА] {e}")
        return "Не смог найти информацию."

# ─── GITHUB MODELS API ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты — голосовой помощник Сим. Живой, дружелюбный, с характером.
Отвечай ТОЛЬКО валидным JSON — без лишнего текста.

Доступные действия:
{"action": "open_app", "app": "название"}
{"action": "open_website", "url": "https://..."}
{"action": "search_web", "query": "запрос"}
{"action": "youtube_search", "query": "запрос"}
{"action": "find_info", "query": "вопрос"}
{"action": "weather", "city": "город"}
{"action": "spotify", "cmd": "play/pause/next/prev", "query": ""}
{"action": "volume", "cmd": "up/down/mute", "level": 5}
{"action": "speak", "text": "ответ"}

Для speak: TIME_NOW = время, DATE_NOW = дата.
Вопросы → find_info. Погода → weather. Разговор → speak на русском."""

def ask_ai(user_text: str):
    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        "max_tokens": 150, "temperature": 0.7
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://models.inference.ai.azure.com/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {GITHUB_TOKEN}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
    except Exception as e:
        print(f"[API ОШИБКА] {e}")
        return None

# ─── ВЫПОЛНЕНИЕ ───────────────────────────────────────────────────────────────

def execute(cmd: dict):
    action = cmd.get("action", "")
    if action == "open_app":
        launch_app(cmd.get("app", "").lower().strip())
    elif action == "open_website":
        open_url(cmd.get("url", "https://google.com"))
    elif action == "search_web":
        open_url(f"https://www.google.com/search?q={urllib.parse.quote(cmd.get('query',''))}")
    elif action == "youtube_search":
        open_url(f"https://www.youtube.com/results?search_query={urllib.parse.quote(cmd.get('query',''))}")
    elif action == "find_info":
        speak(find_info(cmd.get("query", "")))
    elif action == "weather":
        speak(get_weather(cmd.get("city", "Москва")))
    elif action == "spotify":
        spotify_control(cmd.get("cmd", "play"), cmd.get("query", ""))
    elif action == "volume":
        volume_control(cmd.get("cmd", "up"), int(cmd.get("level", 5)))
    elif action == "speak":
        text = cmd.get("text", "")
        now = datetime.now()
        if text == "TIME_NOW":
            text = f"Сейчас {now.hour} часов {now.minute} минут"
        elif text == "DATE_NOW":
            months = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
            text = f"Сегодня {now.day} {months[now.month-1]} {now.year} года"
        speak(text)

# ─── ОСНОВНОЙ ЦИКЛ ────────────────────────────────────────────────────────────

_cmd_queue = _queue.Queue()
_last_cmd_time = 0
_last_cmd_text = ""

def _listener_thread():
    while True:
        try:
            text = listen_once()
            if text and contains_wake_word(text):
                _cmd_queue.put(text)
        except Exception as e:
            print(f"[СЛУШАТЕЛЬ ОШИБКА] {e}")

def main_loop():
    global _last_cmd_time, _last_cmd_text
    print("[СИМ] Жду слово 'Сим'...\n")

    t = threading.Thread(target=_listener_thread, daemon=True)
    t.start()

    while True:
        try:
            text = _cmd_queue.get(timeout=1)
        except _queue.Empty:
            continue

        # Очищаем очередь от дублей
        while not _cmd_queue.empty():
            try:
                _cmd_queue.get_nowait()
            except _queue.Empty:
                break

        cmd_text = extract_command(text)

        # Защита от дублей по времени
        now = _time.time()
        if cmd_text == _last_cmd_text and now - _last_cmd_time < 3.0:
            print(f"[ДУБЛЬ] Игнорирую: {cmd_text}")
            continue
        _last_cmd_text = cmd_text
        _last_cmd_time = now

        print(f"[СЛЫШУ] {text}")

        if len(cmd_text) > 2:
            print(f"[ДУМАЮ] {cmd_text}")
            if not try_quick_command(cmd_text):
                result = ask_ai(cmd_text)
                if result:
                    execute(result)
        else:
            speak("Да?")
            try:
                cmd_text = extract_command(_cmd_queue.get(timeout=8))
            except _queue.Empty:
                continue
            print(f"[ДУМАЮ] {cmd_text}")
            if not try_quick_command(cmd_text):
                result = ask_ai(cmd_text)
                if result:
                    execute(result)




def test_invalid_json():
    result = ask_ai("!!!!")
    assert result is None or isinstance(result, dict)

    

# ══════════════════════════════════════════════════════════════════════════════
# GUI ИНТЕРФЕЙС
# ══════════════════════════════════════════════════════════════════════════════

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SimUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("СИМ — Голосовой помощник")
        self.geometry("1200x720")
        self.minsize(1000, 650)

        self.configure(fg_color="#0b1020")

        self.running = False

        self.build_layout()

    def build_layout(self):
        sidebar = ctk.CTkFrame(
            self,
            width=260,
            corner_radius=0,
            fg_color="#111827"
        )
        sidebar.pack(side="left", fill="y")

        logo = ctk.CTkLabel(
            sidebar,
            text="С И М",
            font=("Segoe UI", 34, "bold"),
            text_color="#ffffff"
        )
        logo.pack(pady=(35, 5))

        subtitle = ctk.CTkLabel(
            sidebar,
            text="Voice Assistant",
            font=("Segoe UI", 14),
            text_color="#9ca3af"
        )
        subtitle.pack(pady=(0, 30))

        self.status_label = ctk.CTkLabel(
            sidebar,
            text="● Готов к запуску",
            font=("Segoe UI", 16, "bold"),
            text_color="#60a5fa"
        )
        self.status_label.pack(pady=10)

        start_btn = ctk.CTkButton(
            sidebar,
            text="▶ Запустить",
            height=52,
            corner_radius=14,
            font=("Segoe UI", 16, "bold"),
            command=self.start_assistant
        )
        start_btn.pack(fill="x", padx=18, pady=(20, 12))

        quick_title = ctk.CTkLabel(
            sidebar,
            text="Быстрые команды",
            font=("Segoe UI", 18, "bold"),
            text_color="#f3f4f6"
        )
        quick_title.pack(anchor="w", padx=20, pady=(40, 12))

        quick_commands = [
            ("🎵 Музыка", "включи музыку"),
            ("🌐 Браузер", "открой браузер"),
            ("💬 Telegram", "открой телеграм"),
            ("📺 YouTube", "открой ютуб"),
            ("🔊 Громче", "громче"),
            ("🔉 Тише", "тише")
        ]

        for text, cmd in quick_commands:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                height=42,
                corner_radius=12,
                fg_color="#1f2937",
                hover_color="#374151",
                anchor="w",
                command=lambda c=cmd: self.execute_quick(c)
            )
            btn.pack(fill="x", padx=18, pady=5)

        main = ctk.CTkFrame(
            self,
            fg_color="#0f172a",
            corner_radius=0
        )
        main.pack(side="left", fill="both", expand=True)

        topbar = ctk.CTkFrame(
            main,
            fg_color="#111827",
            height=80,
            corner_radius=0
        )
        topbar.pack(fill="x")

        title = ctk.CTkLabel(
            topbar,
            text="Панель управления СИМ",
            font=("Segoe UI", 28, "bold")
        )
        title.pack(side="left", padx=30, pady=20)

        self.console = ctk.CTkTextbox(
            main,
            font=("Consolas", 14),
            fg_color="#111827",
            corner_radius=16
        )
        self.console.pack(fill="both", expand=True, padx=25, pady=25)

        self.log("GUI успешно загружен")
        self.log("Логика ассистента не изменялась")

    def log(self, text):
        from datetime import datetime
        self.console.insert(
            "end",
            f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n"
        )
        self.console.see("end")

    def start_assistant(self):
        if self.running:
            return

        self.running = True

        self.status_label.configure(
            text="● Ассистент работает",
            text_color="#4ade80"
        )

        self.log("Запуск голосового помощника...")

        thread = threading.Thread(
            target=main_loop,
            daemon=True
        )
        thread.start()

    def execute_quick(self, command):
        self.log(f"Команда: {command}")

        if not try_quick_command(command):
            result = ask_ai(command)
            if result:
                execute(result)


if __name__ == "__main__":
    app = SimUI()
    app.mainloop()

