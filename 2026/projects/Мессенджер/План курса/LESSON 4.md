# Занятие 4. Идентификация пользователей и личные сообщения

## Цель занятия

Научить сервер различать пользователей и направлять личные сообщения конкретным получателям. Мы введём простой текстовый протокол с командами, добавим аутентификацию (вход по имени) и реализуем маршрутизацию личных сообщений (`/msg`). В результате получится консольный мессенджер, где пользователи могут обмениваться как общими сообщениями (broadcast), так и приватными.

---

## Теоретическая часть

### Необходимость идентификации

В групповом чате все сообщения видны всем. Для личной переписки нужно:
- Знать, кто есть кто (имя пользователя).
- Отправлять сообщение только одному получателю.
- Поддерживать список подключённых пользователей с их сокетами.

### Протокол команд

Протокол – это набор правил, как клиент и сервер обмениваются данными. Мы используем простые текстовые команды, начинающиеся с косой черты (`/`). Формат:

| Команда              | Назначение                                             | Пример             |
|----------------------|--------------------------------------------------------|--------------------|
| `/login имя`         | Зарегистрировать пользователя на сервере (войти в чат) | `/login Alice`     |
| `/msg имя текст`     | Отправить личное сообщение пользователю `имя`          | `/msg Bob Привет!` |
| `/logout`            | Выйти из чата (отключиться)                            | `/logout`          |
| (любой другой текст) | Отправить общее сообщение всем (broadcast)             | `Всем привет!`     |

Сервер отвечает на команды текстовыми сообщениями, например:
- `OK` – команда выполнена.
- `ERR: причина` – ошибка.
- `MSG от имя: текст` – уведомление о личном сообщении.
- `BROADCAST от имя: текст` – общее сообщение.

### Структура данных на сервере

Нужно сопоставить имя пользователя и его сокет:
```python
users = {}            # {username: socket}
users_lock = threading.Lock()
```

При `/login`:
- Проверяем, не занято ли имя.
- Добавляем в словарь.
- Отправляем клиенту `OK`.
- (опционально) Оповещаем всех, что пользователь вошёл.

При `/msg`:
- Ищем получателя по имени.
- Если найден, отправляем ему сообщение от имени отправителя.
- Если не найден, возвращаем ошибку.

При отключении клиента (обрыв соединения или `/logout`):
- Удаляем его из словаря.
- Закрываем сокет.

### Блокировки для словаря

Словарь `users` – разделяемый ресурс. Все операции чтения/записи должны быть защищены блокировкой `users_lock`.

---

## Практика: сервер с идентификацией и личными сообщениями

### Пошаговая реализация

1. **Добавим глобальные структуры**:
   ```python
   users = {}           # username -> socket
   users_lock = threading.Lock()
   ```

2. **Функция отправки личного сообщения**:
   ```python
   def send_private_message(sender_name, target_name, message):
       with users_lock:
           target_socket = users.get(target_name)
           if not target_socket:
               return False, f"Пользователь {target_name} не найден"
           try:
               formatted = f"[Личное от {sender_name}] {message}"
               target_socket.send(formatted.encode('utf-8'))
               return True, "Отправлено"
           except:
               return False, "Не удалось доставить сообщение"
   ```

3. **Модифицируем `handle_client`**:
   - Теперь каждый клиент должен сначала отправить `/login`, иначе сообщения не принимаются.
   - Сохраняем имя клиента в переменной (привязанной к потоку).
   - При получении данных разбираем команды.

4. **Парсинг команд**:
   ```python
   if data.startswith('/login'):
       parts = data.split(maxsplit=1)
       if len(parts) < 2:
           client_socket.send(b'ERR: укажите имя')
       else:
           username = parts[1]
           with users_lock:
               if username in users:
                   client_socket.send(b'ERR: имя уже занято')
               else:
                   users[username] = client_socket
                   client_socket.send(b'OK')
                   # Рассылаем всем, что пользователь вошёл
                   broadcast(f"*** {username} вошёл в чат ***", exclude=client_socket)
   ```

### Полный код сервера (`chat_server_private.py`)

```python
import socket
import threading
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

active_clients = []      # список сокетов (для broadcast)
clients_lock = threading.Lock()
users = {}               # username -> socket
users_lock = threading.Lock()

def broadcast(message, exclude_socket=None):
    """Отправить сообщение всем, кроме exclude_socket."""
    with clients_lock:
        for client in active_clients:
            if client != exclude_socket:
                try:
                    client.send(message.encode('utf-8'))
                except:
                    pass

def send_private_message(sender_name, target_name, message, sender_socket=None):
    """Отправить личное сообщение. Возвращает (success, response_message)."""
    with users_lock:
        target_socket = users.get(target_name)
        if not target_socket:
            return False, f"Пользователь {target_name} не найден или не в сети"
        try:
            formatted = f"[Личное от {sender_name}] {message}"
            target_socket.send(formatted.encode('utf-8'))
            return True, f"Сообщение для {target_name} отправлено"
        except:
            return False, f"Не удалось доставить сообщение {target_name}"

def handle_client(client_socket, client_address):
    username = None
    logging.info(f"Новое подключение: {client_address}")

    # Добавляем в список для broadcast
    with clients_lock:
        active_clients.append(client_socket)

    try:
        # Сначала просим представиться
        client_socket.send(b"Welcome! Please login: /login your_username\n")
        
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            text = data.decode('utf-8').strip()
            if not text:
                continue

            # --- Обработка команд ---
            if text.startswith('/login'):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    client_socket.send(b'ERR: Usage: /login username\n')
                    continue
                new_name = parts[1]
                with users_lock:
                    if new_name in users:
                        client_socket.send(b'ERR: Username already taken\n')
                    else:
                        username = new_name
                        users[username] = client_socket
                        client_socket.send(f'OK: logged in as {username}\n'.encode())
                        broadcast(f"*** {username} присоединился к чату ***", exclude_socket=client_socket)
                        # Отправить новому пользователю список онлайн
                        online = ', '.join(users.keys())
                        client_socket.send(f"Online users: {online}\n".encode())
                continue

            if username is None:
                client_socket.send(b'ERR: You must login first using /login name\n')
                continue

            if text.startswith('/msg'):
                # Формат: /msg target message_text
                parts = text.split(maxsplit=2)
                if len(parts) < 3:
                    client_socket.send(b'ERR: Usage: /msg username message\n')
                    continue
                target = parts[1]
                message = parts[2]
                success, resp = send_private_message(username, target, message)
                client_socket.send(f"{'OK' if success else 'ERR'}: {resp}\n".encode())
                if success:
                    logging.info(f"Личное от {username} -> {target}: {message}")
                continue

            if text.startswith('/logout'):
                client_socket.send(b'OK: Goodbye!\n')
                break

            # Если не команда – отправляем всем (broadcast)
            broadcast_msg = f"[{username}] {text}"
            broadcast(broadcast_msg, exclude_socket=client_socket)
            logging.info(f"Broadcast от {username}: {text}")

    except ConnectionResetError:
        logging.warning(f"Клиент {client_address} оборвал соединение")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        # Удаление пользователя из структур
        with clients_lock:
            if client_socket in active_clients:
                active_clients.remove(client_socket)
        if username:
            with users_lock:
                if username in users and users[username] == client_socket:
                    del users[username]
            broadcast(f"*** {username} покинул чат ***")
        client_socket.close()
        logging.info(f"Клиент {client_address} отключился")

def main():
    HOST = '127.0.0.1'
    PORT = 12345

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    logging.info(f"Сервер личных сообщений запущен на {HOST}:{PORT}")

    try:
        while True:
            client_sock, client_addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(client_sock, client_addr))
            thread.start()
    except KeyboardInterrupt:
        logging.info("Сервер остановлен")
    finally:
        server.close()

if __name__ == "__main__":
    main()
```

---

## Практика: клиент с поддержкой команд

Клиент должен:
- При запуске предложить ввести команду `/login`.
- Отправлять все введённые строки на сервер.
- В потоке приёма выводить входящие сообщения (включая личные и системные).
- Поддерживать `/logout` для выхода.

### Полный код клиента (`chat_client_private.py`)

```python
import socket
import threading
import sys

def receive_messages(client_socket):
    """Поток для получения сообщений от сервера."""
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                print("\nСоединение с сервером разорвано.")
                break
            message = data.decode('utf-8').rstrip()
            # Выводим сообщение, не мешая вводу
            print(f"\n{message}")
            print("> ", end="", flush=True)
    except:
        print("\nОшибка приёма.")
    finally:
        client_socket.close()
        sys.exit(0)

def main():
    HOST = '127.0.0.1'
    PORT = 12345

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((HOST, PORT))
        print("Подключено к серверу. Введите /login ваше_имя")
    except:
        print("Не удалось подключиться к серверу")
        return

    # Запускаем поток приёма
    recv_thread = threading.Thread(target=receive_messages, args=(client,))
    recv_thread.daemon = True
    recv_thread.start()

    # Главный поток для отправки
    try:
        while True:
            msg = input("> ")
            if not msg:
                continue
            if msg.lower() == '/quit':
                client.send(b'/logout')
                break
            client.send(msg.encode('utf-8'))
    except KeyboardInterrupt:
        print("\nЗавершение клиента...")
        client.send(b'/logout')
    finally:
        client.close()

if __name__ == "__main__":
    main()
```

---

## Запуск и тестирование

1. **Запустите сервер**: `python chat_server_private.py`
2. **Запустите два клиента** (например, Алиса и Боб):
   - Клиент 1: вводит `/login Alice`
   - Клиент 2: вводит `/login Bob`
3. **Отправка личного сообщения**:
   - У Алисы: `/msg Bob Привет, Боб!`
   - У Боба: увидит `[Личное от Alice] Привет, Боб!`
4. **Отправка общего сообщения**:
   - Алиса: `Всем привет!` – это увидят все (и Боб, и другие).
5. **Выход**:
   - `/logout` или `/quit` (клиент сам отправит `/logout`).

---

## Разбор кода и важные моменты

### Различие между `active_clients` и `users`

- `active_clients` – список сокетов (используется для broadcast).
- `users` – словарь имя → сокет (используется для личных сообщений и проверки, вошёл ли пользователь).  
Они связаны: при логине добавляем сокет в оба хранилища; при выходе удаляем из обоих.

### Почему клиент должен логиниться первым?

Без логина сервер не знает, как обращаться к пользователю, и не может отправлять личные сообщения. В коде сервера после подключения отправляется приглашение, и любая команда, кроме `/login`, отклоняется с ошибкой.

### Обработка ошибок при личной отправке

Функция `send_private_message` проверяет существование получателя и пытается отправить. Если отправка не удалась (например, клиент отключился), возвращает ошибку, но пользователя из словаря не удаляет (это сделает поток, который обрабатывает разрыв соединения).

### Безопасность на данном этапе

Паролей пока нет – достаточно имени. В следующих занятиях добавим пароли и БД.

---

## Практическое задание

1. **Реализуйте сервер и клиент** с поддержкой `/login`, `/msg`, `/logout` и broadcast.

2. **Добавьте команду `/users`**, которая возвращает список всех зарегистрированных (вошедших) пользователей. Сервер должен отправлять список через личное сообщение отправителю.

3. **Модифицируйте сервер**, чтобы он не отправлял broadcast-сообщения от пользователя, который не залогинен (защита от анонимного спама).

4. **Улучшите клиент**: пусть он отдельно выводит входящие личные сообщения с пометкой `[Личное от X]`, а общие сообщения – с пометкой `[Общее] X: текст`.

5. **Дополнительно:** Реализуйте на сервере игнорирование команд, если пользователь не залогинен (кроме `/login`). При попытке отправить `/msg` без логина – ошибка.

---

## Вопросы для самопроверки

1. Для чего нужны две структуры (`active_clients` и `users`)? Нельзя ли обойтись одной?
2. Что произойдёт, если клиент отправит `/login` дважды?
3. Как сервер узнаёт, кому отправлять личное сообщение?
4. Какие проблемы могут возникнуть, если при отправке личного сообщения получатель отключился, но ещё не удалён из словаря?
5. Почему в клиенте поток приёма сделан демоническим (`daemon=True`)?

---

## Что дальше?

Следующее занятие – переход к графическому интерфейсу на tkinter. Мы начнём с заготовки `messanger.py` и реализуем локальный GUI (без сети), чтобы освоить виджеты и события. Потом подключим сетевую часть и перенесём логику команд в окно чата.

Вы уже имеете работающий консольный мессенджер с личными сообщениями – отличный фундамент для графической обёртки. Успехов!