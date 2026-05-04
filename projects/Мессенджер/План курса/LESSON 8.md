# Занятие 8. База данных SQLite на сервере

## Цель занятия

Научиться хранить данные пользователей и сообщений в базе данных SQLite. Мы добавим на сервер:
- таблицу `users` (id, username, password_hash),
- таблицу `messages` (id, from_user, to_user, text, timestamp),
- хеширование паролей с помощью `hashlib.sha256`,
- функции регистрации, входа и сохранения сообщений.

В результате сервер будет сохранять все данные между перезапусками, а пароли – храниться в безопасном хешированном виде.

---

## Теоретическая часть

### Зачем нужна база данных?

До этого сервер хранил пользователей и сообщения только в оперативной памяти (словари, списки). При перезапуске сервера все данные терялись. База данных решает эту проблему.

### SQLite

SQLite – встроенная реляционная БД, не требующая отдельного сервера. Данные хранятся в одном файле (например, `messenger.db`). Python имеет встроенную поддержку через модуль `sqlite3`.

Основные операции:
- `sqlite3.connect('file.db')` – подключение к БД.
- `cursor.execute('SQL запрос')` – выполнение запроса.
- `connection.commit()` – фиксация изменений.
- `cursor.fetchall()` / `fetchone()` – получение результатов.

### Хеширование паролей

Хранить пароли в открытом виде опасно. Вместо этого храним **хеш** – результат работы односторонней функции. При входе хешируем введённый пароль и сравниваем с сохранённым хешем.

Используем `hashlib.sha256`:
```python
import hashlib
hash = hashlib.sha256(password.encode()).hexdigest()
```

**Важно:** в реальном проекте нужно использовать соль (`salt`) и более стойкие алгоритмы (bcrypt, PBKDF2). Для учебного курса sha256 достаточен.

### Структура таблиц

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user TEXT NOT NULL,
    to_user TEXT NOT NULL,
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_user) REFERENCES users(username),
    FOREIGN KEY (to_user) REFERENCES users(username)
);
```

### Потокобезопасность

SQLite поддерживает одновременное чтение из нескольких потоков, но запись должна быть последовательной. В нашем многопоточном сервере все потоки будут использовать одно соединение с БД, поэтому нужно синхронизировать запросы на изменение с помощью блокировки (`threading.Lock`).

---

## Практика: интеграция SQLite в сервер

Модифицируем сервер из занятия 7 (или 4). Создадим класс `Database`, который инкапсулирует все операции.

### Шаг 1. Создаём файл `database.py` (или добавляем в сервер)

```python
import sqlite3
import hashlib
import threading

class Database:
    def __init__(self, db_file='messenger.db'):
        self.db_file = db_file
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Создаёт таблицы, если их нет."""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user TEXT NOT NULL,
                    to_user TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()

    def _hash_password(self, password):
        """Возвращает хеш пароля."""
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password):
        """Регистрирует нового пользователя. Возвращает (success, message)."""
        password_hash = self._hash_password(password)
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_file)
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                               (username, password_hash))
                conn.commit()
                conn.close()
            return True, "Регистрация успешна"
        except sqlite3.IntegrityError:
            return False, "Имя пользователя уже существует"
        except Exception as e:
            return False, f"Ошибка БД: {e}"

    def login_user(self, username, password):
        """Проверяет логин. Возвращает (success, message)."""
        password_hash = self._hash_password(password)
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            conn.close()
        if row and row[0] == password_hash:
            return True, "Вход выполнен"
        else:
            return False, "Неверное имя или пароль"

    def save_message(self, from_user, to_user, text):
        """Сохраняет сообщение в БД."""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (from_user, to_user, text)
                VALUES (?, ?, ?)
            ''', (from_user, to_user, text))
            conn.commit()
            conn.close()

    def get_history(self, user1, user2, limit=50):
        """Возвращает историю сообщений между двумя пользователями (последние limit)."""
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT from_user, text, timestamp FROM messages
                WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                ORDER BY timestamp DESC LIMIT ?
            ''', (user1, user2, user2, user1, limit))
            rows = cursor.fetchall()
            conn.close()
        # Возвращаем в хронологическом порядке
        return list(reversed(rows))
```

### Шаг 2. Интеграция в сервер

Модифицируем основной серверный файл (например, `chat_server_private.py` из занятия 4/7). Добавим использование `Database`.

**Изменения в глобальных структурах:**
- Убираем словари `users_db` (теперь БД).
- Оставляем словарь `users` для онлайн-пользователей (username -> socket).
- Добавляем экземпляр `db = Database()`.

**Изменения в обработчиках команд:**

```python
# В handle_client, секция /register
if text.startswith('/register'):
    parts = text.split()
    if len(parts) != 3:
        client_socket.send(b'ERR: Usage /register username password\n')
    else:
        _, name, pwd = parts
        success, msg = db.register_user(name, pwd)
        client_socket.send(f"{'OK' if success else 'ERR'}: {msg}\n".encode())
    continue
```

```python
# В секции /login
if text.startswith('/login'):
    parts = text.split()
    if len(parts) != 3:
        client_socket.send(b'ERR: Usage /login username password\n')
    else:
        _, name, pwd = parts
        success, msg = db.login_user(name, pwd)
        if success:
            # Проверяем, не залогинен ли уже
            with users_lock:
                if name in users:
                    client_socket.send(b'ERR: User already logged in\n')
                    continue
                users[name] = client_socket
            username = name
            client_socket.send(f'OK: Welcome {username}\n'.encode())
            # Рассылаем уведомление о входе
            broadcast(f"*** {username} вошёл в чат ***", exclude_socket=client_socket)
            # Отправляем список онлайн
            with users_lock:
                online = ', '.join(users.keys())
            client_socket.send(f"Online users: {online}\n".encode())
        else:
            client_socket.send(f'ERR: {msg}\n'.encode())
    continue
```

**Сохранение личных сообщений:**

При обработке `/msg` после успешной отправки сохраняем сообщение в БД:

```python
if text.startswith('/msg'):
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        client_socket.send(b'ERR: Usage /msg username message\n')
        continue
    target = parts[1]
    message = parts[2]
    success, resp = send_private_message(username, target, message)
    if success:
        # Сохраняем в БД
        db.save_message(username, target, message)
        logging.info(f"Личное от {username} -> {target}: {message}")
    client_socket.send(f"{'OK' if success else 'ERR'}: {resp}\n".encode())
    continue
```

**Сохранение broadcast-сообщений:**

Broadcast-сообщения можно сохранять как сообщения специальному пользователю, например, `*all*`, или просто не сохранять. Для истории лучше сохранять только личные переписки. Но для группового чата можно добавить отдельную таблицу. Мы пока сохраняем только личные.

### Шаг 3. Полный пример сервера с БД (ключевые фрагменты)

Приведём итоговую структуру сервера с использованием `Database`. (Полный код слишком велик, укажем основные изменения.)

```python
import socket
import threading
import logging
from database import Database  # наш класс выше

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

active_clients = []
clients_lock = threading.Lock()
users = {}          # username -> socket
users_lock = threading.Lock()

db = Database('messenger.db')   # глобальный объект БД

def broadcast(message, exclude_socket=None):
    with clients_lock:
        for client in active_clients:
            if client != exclude_socket:
                try:
                    client.send(message.encode('utf-8'))
                except:
                    pass

def send_private_message(sender_name, target_name, message):
    with users_lock:
        target_socket = users.get(target_name)
        if not target_socket:
            return False, f"User {target_name} not online"
        try:
            formatted = f"[Private from {sender_name}] {message}"
            target_socket.send(formatted.encode('utf-8'))
            return True, "Sent"
        except:
            return False, "Send failed"

def handle_client(client_socket, client_address):
    username = None
    with clients_lock:
        active_clients.append(client_socket)
    client_socket.send(b"Welcome! Please login or register.\n")
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            text = data.decode('utf-8').strip()
            if not text:
                continue

            # Регистрация
            if text.startswith('/register'):
                parts = text.split()
                if len(parts) != 3:
                    client_socket.send(b'ERR: Usage /register username password\n')
                else:
                    _, name, pwd = parts
                    success, msg = db.register_user(name, pwd)
                    client_socket.send(f"{'OK' if success else 'ERR'}: {msg}\n".encode())
                continue

            # Логин
            if text.startswith('/login'):
                parts = text.split()
                if len(parts) != 3:
                    client_socket.send(b'ERR: Usage /login username password\n')
                else:
                    _, name, pwd = parts
                    success, msg = db.login_user(name, pwd)
                    if success:
                        with users_lock:
                            if name in users:
                                client_socket.send(b'ERR: Already logged in\n')
                                continue
                            users[name] = client_socket
                        username = name
                        client_socket.send(f'OK: Welcome {username}\n'.encode())
                        broadcast(f"*** {username} joined the chat ***", exclude_socket=client_socket)
                        with users_lock:
                            online = ', '.join(users.keys())
                        client_socket.send(f"Online users: {online}\n".encode())
                    else:
                        client_socket.send(f'ERR: {msg}\n'.encode())
                continue

            if username is None:
                client_socket.send(b'ERR: Please login first\n')
                continue

            # Личное сообщение
            if text.startswith('/msg'):
                parts = text.split(maxsplit=2)
                if len(parts) < 3:
                    client_socket.send(b'ERR: Usage /msg username message\n')
                    continue
                target = parts[1]
                message = parts[2]
                success, resp = send_private_message(username, target, message)
                if success:
                    db.save_message(username, target, message)
                client_socket.send(f"{'OK' if success else 'ERR'}: {resp}\n".encode())
                continue

            # Выход
            if text.startswith('/logout'):
                client_socket.send(b'OK: Goodbye!\n')
                break

            # Broadcast
            broadcast_msg = f"[{username}] {text}"
            broadcast(broadcast_msg, exclude_socket=client_socket)
            logging.info(f"Broadcast from {username}: {text}")

    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        with clients_lock:
            if client_socket in active_clients:
                active_clients.remove(client_socket)
        if username:
            with users_lock:
                if username in users and users[username] == client_socket:
                    del users[username]
            broadcast(f"*** {username} left the chat ***")
        client_socket.close()

def main():
    HOST = '127.0.0.1'
    PORT = 12345
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    logging.info(f"Server with DB started on {HOST}:{PORT}")
    try:
        while True:
            client_sock, addr = server.accept()
            threading.Thread(target=handle_client, args=(client_sock, addr)).start()
    except KeyboardInterrupt:
        logging.info("Server stopped")
    finally:
        server.close()

if __name__ == "__main__":
    main()
```

### Шаг 4. Проверка работы

1. Запустите сервер. Файл `messenger.db` создастся автоматически.
2. Запустите клиент (из занятия 7) и зарегистрируйте пользователя. Проверьте, что данные сохраняются – после перезапуска сервера логин должен работать.
3. Отправьте личное сообщение – оно сохранится в БД. Проверьте через SQLite клиент: `sqlite3 messenger.db`, `SELECT * FROM messages;`.

---

## Практическое задание

1. **Добавьте БД на сервер** по приведённому образцу. Убедитесь, что регистрация и логин работают после перезапуска сервера.

2. **Реализуйте команду `/history` на сервере**:
   - Формат: `/history username [limit]` (limit по умолчанию 20).
   - Сервер должен вернуть историю сообщений между текущим пользователем и указанным.
   - Отправьте результат клиенту в виде списка сообщений.

3. **На клиенте** (занятие 7) добавьте автоматическую загрузку истории при выборе контакта: отправляйте `/history contact` и отображайте полученные сообщения в `chat_area`.

4. **Улучшите БД**: добавьте индекс на `(from_user, to_user)` для ускорения запросов истории.

5. **Эксперимент:** Реализуйте команду `/chats` – список всех собеседников, с которыми были переписки у текущего пользователя (уникальные имена).

---

## Вопросы для самопроверки

1. Почему пароли нужно хешировать? Можно ли их хранить в открытом виде?
2. Зачем нужна блокировка (`lock`) при работе с SQLite в многопоточном сервере?
3. Как получить последние 50 сообщений между двумя пользователями?
4. Что произойдёт, если два потока одновременно попробуют зарегистрировать одного пользователя?
5. Как изменить схему БД, чтобы добавить поддержку групповых чатов?

---

## Что дальше?

На следующем занятии (№9) мы реализуем команду `/history` в GUI и научимся отображать историю сообщений при выборе контакта. Также продолжим улучшать клиент и сервер. Сейчас вы добавили важнейший компонент – persistence (сохранение данных), что делает мессенджер готовым к реальному использованию.