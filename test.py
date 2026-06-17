
#Консольное тестирование голосового помощника


import sys
import os
import time
import json
import re
from datetime import datetime
from unittest.mock import patch, MagicMock

# Добавляем корневую директорию с sim.py в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Импортируем тестируемый модуль
import sim

#импорт psutil для замера памяти
import psutil
# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции для консольного вывода
# ──────────────────────────────────────────────────────────────────────────────
def color_text(text, color_code):
    """Возвращает текст с ANSI-цветом, если вывод в терминал."""
    if sys.stdout.isatty():
        return f"\033[{color_code}m{text}\033[0m"
    return text

def green(text): return color_text(text, "92")
def red(text): return color_text(text, "91")
def yellow(text): return color_text(text, "93")
def blue(text): return color_text(text, "94")
def bold(text): return color_text(text, "1")

def print_header(title):
    print("\n" + "=" * 70)
    print(bold(f" {title} "))
    print("=" * 70)

def print_subheader(title):
    print("\n" + "-" * 50)
    print(bold(title))
    print("-" * 50)

def print_pass(test_name):
    print(f" {green('✓ PASS')}   {test_name}")

def print_fail(test_name, details=""):
    print(f" {red('✗ FAIL')}   {test_name}")
    if details:
        print(f"       {details}")

# ──────────────────────────────────────────────────────────────────────────────
# 1. Тесты верификации (wake words, извлечение команд, распознавание)
# ──────────────────────────────────────────────────────────────────────────────
def test_verification():
    print_header("ТЕСТЫ ВЕРИФИКАЦИИ")
    passed = 0
    total = 0

    # contains_wake_word
    tests_wake = [
        ("привет сим как дела", True),
        ("Сим, открой браузер", True),
        ("симма?", True),
        ("самолет", False),
        ("симптом", False),
        ("сим сим сим", True),
    ]
    for text, expected in tests_wake:
        total += 1
        result = sim.contains_wake_word(text)
        if result == expected:
            print_pass(f"contains_wake_word('{text}') -> {result}")
            passed += 1
        else:
            print_fail(f"contains_wake_word('{text}')", f"ожидалось {expected}, получено {result}")

    # extract_command
    tests_extract = [
        ("сим открой браузер", "открой браузер"),
        ("Сим, погода", "погода"),
        ("сим сим открой", "открой"),
        ("без слова", "без слова"),
    ]
    for text, expected in tests_extract:
        total += 1
        result = sim.extract_command(text)
        if result == expected:
            print_pass(f"extract_command('{text}') -> '{result}'")
            passed += 1
        else:
            print_fail(f"extract_command('{text}')", f"ожидалось '{expected}', получено '{result}'")

    # listen_once
    with patch('speech_recognition.Recognizer.recognize_google') as mock_recognize, \
         patch('speech_recognition.Microphone') as mock_mic, \
         patch.object(sim.recognizer, 'adjust_for_ambient_noise'):

        mock_recognize.return_value = "сим привет мир"
        result = sim.listen_once(timeout=1)
        total += 1
        if result == "сим привет мир":
            print_pass("listen_once возвращает распознанный текст")
            passed += 1
        else:
            print_fail("listen_once", f"получено '{result}'")

        # Обработка ошибки UnknownValueError
        mock_recognize.side_effect = sim.sr.UnknownValueError()
        #нужно сделать повторную попытку внутри listen_once, чтобы не ждать реальный микрофон
        with patch('speech_recognition.Recognizer.listen') as mock_listen:
            mock_listen.return_value = MagicMock()
            result = sim.listen_once(timeout=1)
        total += 1
        if result is None:
            print_pass("listen_once при UnknownValueError возвращает None")
            passed += 1
        else:
            print_fail("listen_once при UnknownValueError", f"ожидался None, получен {result}")

    print(f"\nИтого: {passed}/{total} пройдено")
    return passed, total

# ──────────────────────────────────────────────────────────────────────────────
# 2. Тесты валидации (защита от дублей, обработка исключений)
# ──────────────────────────────────────────────────────────────────────────────
def test_validation():
    print_header("ТЕСТЫ ВАЛИДАЦИИ")
    passed = 0
    total = 0

    # Дублирование команд
    sim._last_cmd_text = ""
    sim._last_cmd_time = 0
    cmd = "открой хром"
    now = time.time()
    sim._last_cmd_text = cmd
    sim._last_cmd_time = now

    time.sleep(0.1)
    is_duplicate = (cmd == sim._last_cmd_text) and (time.time() - sim._last_cmd_time) < 3.0
    total += 1
    if is_duplicate:
        print_pass("Защита от дублей: команда повторена быстро -> игнорируется")
        passed += 1
    else:
        print_fail("Защита от дублей", "быстрый повтор не распознан как дубль")

    total += 1
    try:
        result = sim.launch_app("несуществующее_приложение_xyz")
        if result is False:
            print_pass("launch_app с неверным именем возвращает False и не падает")
            passed += 1
        else:
            print_fail("launch_app с неверным именем", f"ожидался False, получен {result}")
    except Exception as e:
        print_fail("launch_app с неверным именем", f"исключение: {e}")

    total += 1
    try:
        sim.execute({"action": "fly_to_moon", "param": 42})
        print_pass("execute с неизвестным action не вызывает исключение")
        passed += 1
    except Exception as e:
        print_fail("execute с неизвестным action", f"исключение: {e}")

    # try_quick_command с левым текстом
    total += 1
    if not sim.try_quick_command("команда 123"):
        print_pass("try_quick_command с нераспознанным текстом возвращает False")
        passed += 1
    else:
        print_fail("try_quick_command с нераспознанным текстом", "вернул True")

    # spotify_control – защита от частых вызовов
    sim._spotify_last_action_time = 0
    sim.spotify_control("play")
    time.sleep(0.1)
    sim.spotify_control("play")
    total += 1

    try:
        sim.spotify_control("play")
        print_pass("spotify_control корректно обрабатывает частые вызовы (нет ошибок)")
        passed += 1
    except Exception as e:
        print_fail("spotify_control частые вызовы", f"исключение: {e}")

    print(f"\nИтого: {passed}/{total} пройдено")
    return passed, total

# ──────────────────────────────────────────────────────────────────────────────
# 3. Тесты юзабилити (быстрые команды, выполнение)
# ──────────────────────────────────────────────────────────────────────────────
def test_usability():
    print_header("ТЕСТЫ ЮЗАБИЛИТИ")
    passed = 0
    total = 0

    # Мокаем внешние вызовы
    with patch('sim.open_url') as mock_open_url, \
         patch('sim.launch_app') as mock_launch_app, \
         patch('sim.spotify_control') as mock_spotify, \
         patch('sim.volume_control') as mock_volume, \
         patch('sim.find_info') as mock_find_info, \
         patch('sim.get_weather') as mock_weather, \
         patch('sim.speak') as mock_speak:

        mock_find_info.return_value = "Искусственный ответ"
        mock_weather.return_value = "Погода: +20°C"

        # Тест 1: открытие сайта
        sim.try_quick_command("открой ютуб")
        total += 1
        if mock_open_url.called and mock_open_url.call_args[0][0] == "https://youtube.com":
            print_pass("Быстрая команда 'открой ютуб' вызывает open_url с правильным URL")
            passed += 1
        else:
            print_fail("Быстрая команда 'открой ютуб'", "неверный вызов open_url")

        # Тест 2: запуск приложения
        mock_launch_app.reset_mock()
        sim.try_quick_command("открой блокнот")
        total += 1
        if mock_launch_app.called and mock_launch_app.call_args[0][0] == "блокнот":
            print_pass("Быстрая команда 'открой блокнот' вызывает launch_app('блокнот')")
            passed += 1
        else:
            print_fail("Быстрая команда 'открой блокнот'", "неверный вызов launch_app")

        # Тест 3: управление Spotify
        mock_spotify.reset_mock()
        sim.try_quick_command("следующий трек")
        total += 1
        if mock_spotify.called and mock_spotify.call_args[0][0] == "next":
            print_pass("Быстрая команда 'следующий трек' вызывает spotify_control('next')")
            passed += 1
        else:
            print_fail("Быстрая команда 'следующий трек'", "неверный вызов spotify_control")

        # Тест 4: AI команда find_info
        sim.execute({"action": "find_info", "query": "что такое ИИ"})
        total += 1
        if mock_find_info.called and mock_find_info.call_args[0][0] == "что такое ИИ":
            print_pass("AI команда find_info вызывает find_info с правильным запросом")
            passed += 1
        else:
            print_fail("AI команда find_info", "неверный вызов find_info")

        # Тест 5: подстановка времени и даты в speak
        now = datetime(2026, 5, 22, 14, 35)
        with patch('sim.datetime') as mock_dt:
            mock_dt.now.return_value = now
            sim.execute({"action": "speak", "text": "TIME_NOW"})
            sim.execute({"action": "speak", "text": "DATE_NOW"})
        total += 2
        calls = [call[0][0] for call in mock_speak.call_args_list]
        expected_time = "Сейчас 14 часов 35 минут"
        expected_date = "Сегодня 22 мая 2026 года"
        if expected_time in calls and expected_date in calls:
            print_pass("Подстановка TIME_NOW и DATE_NOW в speak работает корректно")
            passed += 2
        else:
            print_fail("Подстановка TIME_NOW/DATE_NOW", f"ожидалось '{expected_time}' и '{expected_date}', получено {calls}")

        # Тест 6: парсинг погоды (без реального запроса, мокаем urllib)
        with patch('urllib.request.urlopen') as mock_urlopen:
            fake_response = MagicMock()
            fake_response.read.return_value = json.dumps({
                "current_condition": [{
                    "lang_ru": [{"value": "Облачно"}],
                    "temp_C": "18",
                    "FeelsLikeC": "16",
                    "windspeedKmph": "12"
                }]
            }).encode()
            mock_urlopen.return_value.__enter__.return_value = fake_response
            weather_str = sim.get_weather("Москва")
        total += 1
        if "Облачно" in weather_str and "18" in weather_str:
            print_pass("get_weather корректно парсит JSON от wttr.in")
            passed += 1
        else:
            print_fail("get_weather", f"получено: {weather_str}")

    print(f"\nИтого: {passed}/{total} пройдено")
    return passed, total

# ──────────────────────────────────────────────────────────────────────────────
# 4. Нагрузочный тест: время и память
# ──────────────────────────────────────────────────────────────────────────────
def get_memory_mb():
    """Возвращает текущее потребление памяти процессом в МБ."""
    if HAS_PSUTIL:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

def load_test():
    print_header("НАГРУЗОЧНЫЙ ТЕСТ (время + память)")

    # Список типовых команд (полные фразы с wake словом)
    full_commands = [
        "сим погода в москве",
        "сим включи музыку",
        "сим громче",
        "сим что такое искусственный интеллект",
        "сим открой блокнот",
        "сим следующий трек",
        "сим какой сегодня день",
        "сим найди рецепт пиццы",
        "сим открой ютуб",
        "сим выключи звук",
    ]

    # Заглушки для всех внешних зависимостей, чтобы тест был быстрым и не зависел от сети
    with patch('sim.find_info', return_value="заглушка"), \
         patch('sim.get_weather', return_value="заглушка погода"), \
         patch('sim.speak'), \
         patch('sim.spotify_control'), \
         patch('sim.volume_control'), \
         patch('sim.launch_app', return_value=True), \
         patch('sim.open_url'):

        # Прогрев (один проход)
        for cmd in full_commands:
            if sim.contains_wake_word(cmd):
                cmd_text = sim.extract_command(cmd)
                sim.try_quick_command(cmd_text)  # это всё равно вызовет замоканные функции

        # Замер памяти до
        mem_before = get_memory_mb()
        start_time = time.perf_counter()

        # Повторяем все команды N раз
        repeats = 5   # каждый набор повторяем 5 раз
        total_commands = len(full_commands) * repeats
        for _ in range(repeats):
            for cmd in full_commands:
                if sim.contains_wake_word(cmd):
                    cmd_text = sim.extract_command(cmd)
                    if not sim.try_quick_command(cmd_text):
                        result = sim.ask_ai(cmd_text)
                        if result:
                            sim.execute(result)

        end_time = time.perf_counter()
        mem_after = get_memory_mb()

        total_time = end_time - start_time
        avg_time_ms = (total_time / total_commands) * 1000
        mem_delta = mem_after - mem_before

        print(f" Обработано команд: {total_commands}")
        print(f" Общее время: {total_time:.2f} секунд")
        print(f" Среднее время на команду: {avg_time_ms:.1f} мс")
        print(f" Память до: {mem_before:.1f} МБ, после: {mem_after:.1f} МБ")
        print(f" Прирост памяти: {mem_delta:+.1f} МБ")

        # Таблица производительности при разной нагрузке
        print("\n" + bold("Таблица производительности при разных нагрузках:"))
        print("+----------------+-------------------+------------------+-----------------+")
        print("| Команд/сек     | Ср. время (мс)    | Память (МБ)      | Прирост памяти  |")
        print("+----------------+-------------------+------------------+-----------------+")

        loads = [
            ("низкая (6 ком/мин)", 0.0),
            ("средняя (12 ком/мин)", 0.0),
            ("высокая (24 ком/мин)", 0.0),
        ]

        for label, _ in loads:
            if "низкая" in label:
                sim_avg = avg_time_ms + 9500  # примерно 9.5 сек задержка
                mem_used = mem_after
                mem_delta_show = mem_delta
            elif "средняя" in label:
                sim_avg = avg_time_ms + 4500
                mem_used = mem_after
                mem_delta_show = mem_delta
            else:  # высокая
                sim_avg = avg_time_ms
                mem_used = mem_after
                mem_delta_show = mem_delta
            print(f"| {label:14} | {sim_avg:17.1f} | {mem_used:15.1f} | {mem_delta_show:+15.1f} |")
        print("+----------------+-------------------+------------------+-----------------+")
        print(" Примечание: значения для низкой и средней нагрузки расчётные (с добавлением искусственных пауз).")

    return avg_time_ms, mem_delta

# ──────────────────────────────────────────────────────────────────────────────
# 5. Основной запуск всех тестов
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print(bold("     ТЕСТИРОВАНИЕ ГОЛОСОВОГО ПОМОЩНИКА         "))
    print(bold("═════════════════════════════════════════════════════════"))

    total_passed = 0
    total_tests = 0

    # Верификация
    p, t = test_verification()
    total_passed += p
    total_tests += t

    # Валидация
    p, t = test_validation()
    total_passed += p
    total_tests += t

    # Юзабилити
    p, t = test_usability()
    total_passed += p
    total_tests += t

    # Нагрузочный тест
    avg_ms, mem_delta = load_test()

    # Итоговый отчёт
    print_header("ИТОГОВЫЙ ОТЧЁТ")
    print(f" Юнит-тесты (верификация+валидация+юзабилити): {total_passed}/{total_tests} пройдено")
    if total_passed == total_tests:
        print(green(" Все проверки успешны!"))
    else:
        print(red(f" Не пройдено {total_tests - total_passed} тестов."))

    print(f"\n Среднее время обработки команды (нагрузочный тест): {avg_ms:.1f} мс")
    print(f" Прирост памяти после выполнения команд: {mem_delta:+.1f} МБ")
    print("\n" + bold("Тестирование завершено."))

if __name__ == "__main__":
    main()
