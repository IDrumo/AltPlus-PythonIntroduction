# Занятие 12. Отладка, рефакторинг, дополнительные возможности

## Цель занятия

Завершить разработку мессенджера: исправить ошибки, улучшить структуру кода, добавить «graceful shutdown» и одну дополнительную функцию (например, уведомление о наборе текста). Также подготовить проект к демонстрации: научиться обрабатывать исключения, корректно закрывать соединения, разбивать код на модули (если ещё не сделано). В результате получится стабильное, хорошо структурированное приложение, готовое к презентации.

---

## Теоретическая часть

### Проблемы многопоточного сервера

- **Зависание потоков**: если поток клиента застрял в `recv`, сервер не может его «убить» извне. Решение – использовать таймауты или механизм «heartbeat».
- **Корректное завершение (graceful shutdown)**: при нажатии Ctrl+C сервер должен закрыть все сокеты и дождаться завершения потоков, а не просто завершиться.
- **Исключения в потоках**: необработанные исключения могут привести к «висячим» ресурсам.

### Рефакторинг кода

Код, написанный на занятиях, можно улучшить:
- Вынести константы (HOST, PORT, BUFFER_SIZE) в config-файл или класс.
- Разбить на модули: `common/protocol.py`, `server/server_main.py`, `client/gui.py`, `client/network.py`.
- Убрать дублирование, добавить документирование.

### Graceful shutdown сервера

Используем `signal` для перехвата SIGINT (Ctrl+C) и устанавливаем флаг `running = False`. В главном цикле принимаем новых клиентов только пока `running`. Для уже работающих потоков – устанавливаем таймаут на `recv` или отправляем им сигнал к закрытию.

Пример:
```python
import signal
import time

running = True

def stop_server(signum, frame):
    global running
    running = False

signal.signal(signal.SIGINT, stop_server)

while running:
    try:
        client_sock, addr = server.accept()
        # ...
    except KeyboardInterrupt:
        break
```

Также нужно закрыть серверный сокет и вызвать `join()` для потоков (хотя daemon-потоки завершатся сами).

### Дополнительная функция: «Печатает...»

Реализуем уведомление, когда пользователь набирает текст. Протокол:
- Клиент при каждом нажатии клавиши в поле ввода отправляет на сервер команду `/typing target`.
- Сервер пересылает эту команду получателю в виде `TYPING:sender`.
- Получатель отображает «пользователь печатает...» на несколько секунд.

Для этого в клиенте нужно привязать событие `<Key>` к полю `Entry` и отправлять `/typing` не чаще раза в 2 секунды (debounce).

---

## Практика: рефакторинг и улучшения

### 1. Вынесение констант (common/protocol.py)

Создадим файл `common/protocol.py`:

```python
# Константы протокола
CMD_LOGIN = "/login"
CMD_REGISTER = "/register"
CMD_MSG = "/msg"
CMD_HISTORY = "/history"
CMD_LOGOUT = "/logout"
CMD_TYPING = "/typing"

# Ответы сервера
RESP_OK = "OK"
RESP_ERR = "ERR"
PREFIX_PRIVATE = "[Личное от "
PREFIX_BROADCAST = "["
USERLIST_PREFIX = "USERLIST:"
HISTORY_START = "HISTORY_START"
HISTORY_END = "HISTORY_END"
```

Затем в клиенте и сервере импортировать эти константы.

### 2. Разделение сервера на модули

Рекомендуемая структура (как в начале курса):
```
messenger/
├── common/
│   └── protocol.py
├── server/
│   ├── server_main.py      # класс ChatServer, main
│   ├── client_handler.py   # handle_client
│   └── database.py
├── client/
│   ├── client_main.py      # точка входа, аутентификация
│   ├── gui.py              # класс MessengerApp
│   └── network.py          # NetworkClient
```

В рамках занятия 12 можно показать пример такого разделения, но подробно не переписывать весь код – достаточно обсудить принципы.

### 3. Graceful shutdown сервера

Модифицируем сервер (например, `server_main.py`):

```python
import signal
import threading
import time

class ChatServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.running = True
        self.server_socket = None
        self.client_threads = []

    def run(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logging.info(f"Server started on {self.host}:{self.port}")
        signal.signal(signal.SIGINT, self.stop)
        
        while self.running:
            try:
                self.server_socket.settimeout(1.0)  # чтобы не блокироваться навсегда
                client_sock, addr = self.server_socket.accept()
                thread = threading.Thread(target=handle_client, args=(client_sock, addr))
                thread.start()
                self.client_threads.append(thread)
            except socket.timeout:
                continue
            except OSError:
                break
        self.cleanup()

    def stop(self, signum, frame):
        logging.info("Shutting down server...")
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        # Даём потокам время завершиться
        for t in self.client_threads:
            t.join(timeout=1)
        logging.info("Server stopped")
```

### 4. Обработка исключений в клиенте

В клиенте `NetworkClient` добавим повторное подключение или обработку разрыва:

```python
def _receive_loop(self):
    try:
        while self.running:
            data = self.socket.recv(1024)
            if not data:
                break
            self.message_queue.put(data.decode('utf-8'))
    except ConnectionResetError:
        self.message_queue.put("[System] Connection lost")
    except Exception as e:
        self.message_queue.put(f"[System] Receive error: {e}")
    finally:
        self.disconnect()
```

### 5. Реализация уведомления «печатает...»

**На стороне клиента (gui.py):**

Добавим в `MessengerApp`:

```python
def __init__(self, ...):
    # ...
    self.typing_timer = None
    self.message_entry.bind('<Key>', self.on_typing)

def on_typing(self, event):
    if self.current_contact:
        # Отправляем уведомление не чаще раза в 2 секунды
        if self.typing_timer is None:
            self.network.send(f"/typing {self.current_contact}")
            self.typing_timer = self.root.after(2000, self.reset_typing_timer)

def reset_typing_timer(self):
    self.typing_timer = None

def handle_incoming_message(self, raw_msg):
    # ...
    if raw_msg.startswith("TYPING:"):
        sender = raw_msg[7:]
        if sender != self.current_contact:
            return
        # Показать в строке статуса
        self.status_label.config(text=f"{sender} печатает...")
        self.root.after(3000, lambda: self.status_label.config(text="Готов"))
        return
    # ... остальные случаи
```

**На стороне сервера (client_handler.py):**

```python
if text.startswith('/typing'):
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and username:
        target = parts[1]
        with users_lock:
            target_sock = users.get(target)
            if target_sock:
                try:
                    target_sock.send(f"TYPING:{username}\n".encode())
                except:
                    pass
    continue
```

### 6. Корректное закрытие соединения в клиенте

В `on_closing` отправляем `/logout` и ждём подтверждения, затем закрываем сокет:

```python
def on_closing(self):
    if self.network:
        self.network.send("/logout")
        # Даём время на отправку
        self.root.after(500, self._destroy)

def _destroy(self):
    self.network.disconnect()
    self.root.destroy()
```

---

## Итоговая презентация проекта

Рекомендуется подготовить презентацию (10-15 слайдов) с описанием:

1. Цель и функциональность мессенджера.
2. Архитектура (клиент-сервер, многопоточность).
3. Использованные технологии (Python, socket, threading, tkinter, SQLite).
4. Основные модули и их взаимодействие.
5. Демонстрация работы: запуск сервера, регистрация, вход, личные сообщения, история, список контактов, онлайн-статус.
6. Дополнительные фичи (например, «печатает...»).
7. Проблемы и их решения (блокировки, graceful shutdown).
8. Возможные улучшения (отправка файлов, групповые чаты, шифрование).

---

## Практическое задание

1. **Проведите рефакторинг** вашего проекта: вынесите константы в `common/protocol.py`, разбейте на модули (сервер, клиент). Обеспечьте импорты.

2. **Добавьте graceful shutdown** для сервера: перехват Ctrl+C, закрытие сокетов, ожидание потоков.

3. **Реализуйте одну дополнительную фичу** из списка:
   - Уведомление «печатает...».
   - Отправка файлов (через отдельный порт или кодирование в base64).
   - Групповые чаты (создание комнат).
   - Тёмная тема в GUI.
   - Шифрование сообщений (простое XOR или AES).

4. **Подготовьте презентацию** проекта (можно в формате Markdown или PowerPoint).

5. **Запустите итоговый проект** и убедитесь, что он работает без критических ошибок при нескольких клиентах.

---

## Вопросы для самопроверки

1. Почему при остановке сервера важно закрывать сокеты и дожидаться потоков?
2. Как можно избежать конфликта импортов при разделении на модули?
3. Какие ещё есть способы реализовать «печатает...» без лишнего трафика?
4. Как бы вы добавили логирование в файл вместо консоли?
5. Почему в многопоточном сервере важно использовать таймауты на `accept`?

---

## Заключение курса

Поздравляю! Вы прошли путь от простого эхо-сервера до полноценного десктопного мессенджера с графическим интерфейсом, историей, списком контактов и онлайн-статусом. Вы освоили:
- сетевые сокеты и многопоточность,
- протоколирование и очереди сообщений,
- работу с tkinter,
- базу данных SQLite и хеширование паролей,
- принципы отладки и рефакторинга.

Полученный проект может служить основой для дальнейшего развития: добавления аудио/видеозвонков, end-to-end шифрования, мобильной версии. Удачи в ваших будущих проектах!

---

## Дополнительные материалы

- [Руководство по graceful shutdown в Python](https://stackoverflow.com/questions/18499497/how-to-process-sigterm-signal-gracefully)
- [Рефакторинг Python-кода](https://realpython.com/python-refactoring/)
- [Идеи для расширения мессенджера](https://habr.com/ru/post/500258/)