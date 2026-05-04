# Занятие 7. Интеграция протокола и аутентификация в GUI

## Цель занятия

Добавить в графический клиент полноценную аутентификацию: окно входа (логин/пароль) или регистрации, отправку соответствующих команд на сервер, обработку ответов и переход к основному окну только после успешного входа. Мы также модифицируем сервер (из занятия 4 или 6), чтобы он поддерживал простую проверку паролей (пока без базы данных – просто хранить пары логин:пароль в словаре). В результате клиент сможет подключаться к серверу, проходить аутентификацию и затем обмениваться сообщениями, зная имя пользователя.

---

## Теоретическая часть

### Диалоговые окна в tkinter

Для запроса имени и пароля удобно использовать:
- `simpledialog.askstring()` – модальное диалоговое окно с полем ввода.
- `messagebox.showerror()` – для вывода ошибок.
- Но лучше создать отдельное окно (`Toplevel`) с полями ввода, чтобы контролировать процесс.

Мы создадим класс `AuthDialog`, который будет показываться перед главным окном мессенджера. После успешной аутентификации диалог закрывается, и запускается основное приложение с переданными учётными данными.

### Протокол аутентификации

Определим простые команды для сервера:

| Команда | Формат | Ответ сервера |
|---------|--------|----------------|
| `/register` | `/register имя пароль` | `OK` или `ERR: причина` |
| `/login` | `/login имя пароль` | `OK` или `ERR: причина` |

Сервер должен хранить пары (имя, хеш пароля) в словаре (временно, без БД). При регистрации добавлять нового пользователя, если имя не занято. При входе проверять соответствие.

**Важно:** пароли пока передаются в открытом виде – это допустимо для учебного проекта. На занятии 8 добавим хеширование и SQLite.

### Последовательность работы клиента

1. Запуск клиента – сразу показываем окно аутентификации.
2. Пользователь вводит имя, пароль и выбирает действие (Вход / Регистрация).
3. Клиент подключается к серверу (если ещё не подключён) и отправляет команду.
4. Ожидает ответа. Если `OK` – сохраняет имя пользователя, закрывает диалог, создаёт главное окно с этим именем.
5. Если ошибка – показывает сообщение и даёт повторить попытку.

### Сохранение имени пользователя в главном окне

После успешного входа мы передаём имя в `MessengerApp`, и оно используется:
- В заголовке окна.
- При отправке сообщений (можно дополнить команду `/msg` или просто отправлять текст как есть – сервер сам знает, кто отправитель, по сокету. Но в нашем протоколе из занятия 4 сервер уже ассоциирует сокет с именем после `/login`. Поэтому после аутентификации клиент не обязан добавлять имя в каждое сообщение – сервер его помнит.

Однако для корректной работы, клиент после входа не должен отправлять повторно `/login`. Поэтому разделим процесс: сначала соединение, потом аутентификация, затем основной обмен.

---

## Практика: модификация клиента

### Шаг 1. Создаём класс AuthDialog

Создадим отдельный файл или добавим в `messanger.py` перед классом `MessengerApp`.

```python
import tkinter as tk
from tkinter import messagebox, simpledialog
import socket
import threading
import queue

class AuthDialog:
    def __init__(self, parent, server_host='127.0.0.1', server_port=12345):
        self.parent = parent
        self.server_host = server_host
        self.server_port = server_port
        self.result = None  # (username, password) или None при отмене
        self.socket = None
        self.message_queue = queue.Queue()
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Авторизация")
        self.dialog.geometry("300x200")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()  # модальность
        
        # Поля ввода
        tk.Label(self.dialog, text="Имя пользователя:").pack(pady=(10,0))
        self.entry_username = tk.Entry(self.dialog)
        self.entry_username.pack(pady=5)
        
        tk.Label(self.dialog, text="Пароль:").pack()
        self.entry_password = tk.Entry(self.dialog, show="*")
        self.entry_password.pack(pady=5)
        
        # Кнопки
        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Вход", command=self.login).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Регистрация", command=self.register).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Отмена", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        self.entry_username.focus()
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
        
        # Ожидаем закрытия окна
        self.dialog.wait_window()
    
    def connect_to_server(self):
        """Устанавливает соединение с сервером (если ещё не установлено)."""
        if self.socket is None:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.server_host, self.server_port))
                # Запускаем поток приёма для получения ответа
                self.receive_thread = threading.Thread(target=self.receive_messages)
                self.receive_thread.daemon = True
                self.receive_thread.start()
                return True
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось подключиться к серверу: {e}")
                return False
        return True
    
    def receive_messages(self):
        """Поток приёма ответов сервера (только для аутентификации)."""
        try:
            while True:
                data = self.socket.recv(1024)
                if not data:
                    break
                self.message_queue.put(data.decode('utf-8'))
        except:
            pass
    
    def send_command(self, cmd):
        """Отправляет команду на сервер и ждёт ответ (упрощённо)."""
        if not self.connect_to_server():
            return False
        try:
            self.socket.send(cmd.encode('utf-8'))
            # Ждём ответ из очереди в течение 3 секунд
            import time
            timeout = time.time() + 3
            while time.time() < timeout:
                try:
                    resp = self.message_queue.get_nowait()
                    return resp
                except queue.Empty:
                    time.sleep(0.1)
            return None
        except:
            return None
    
    def login(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get()
        if not username or not password:
            messagebox.showwarning("Ошибка", "Введите имя и пароль")
            return
        resp = self.send_command(f"/login {username} {password}")
        if resp is None:
            messagebox.showerror("Ошибка", "Нет ответа от сервера")
            return
        if resp.startswith("OK"):
            self.result = (username, password)
            self.dialog.destroy()
        else:
            messagebox.showerror("Ошибка", resp)
    
    def register(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get()
        if not username or not password:
            messagebox.showwarning("Ошибка", "Введите имя и пароль")
            return
        resp = self.send_command(f"/register {username} {password}")
        if resp is None:
            messagebox.showerror("Ошибка", "Нет ответа от сервера")
            return
        if resp.startswith("OK"):
            messagebox.showinfo("Успех", "Регистрация прошла успешно. Теперь войдите.")
            # Можно автоматически выполнить вход
        else:
            messagebox.showerror("Ошибка", resp)
    
    def cancel(self):
        self.result = None
        self.dialog.destroy()
```

### Шаг 2. Модифицируем основной класс MessengerApp

Теперь при запуске приложения сначала показываем диалог, и только после успеха создаём главное окно.

```python
class MessengerApp:
    def __init__(self, root, username, server_host='127.0.0.1', server_port=12345):
        self.root = root
        self.username = username
        self.server_host = server_host
        self.server_port = server_port
        
        # ... (остальной код инициализации интерфейса, как в занятии 6)
        # Устанавливаем заголовок
        self.root.title(f"Мессенджер - {username}")
        
        # Сетевая часть (подключаемся к серверу с уже пройденной аутентификацией?
        # Но мы уже подключены в диалоге? Упростим: в диалоге мы подключаемся к серверу,
        # но после закрытия диалога сокет теряется. Лучше переподключиться и отправить /login заново.
        # Однако это неэффективно. Можно передать уже установленный сокет из диалога.
        # Для простоты в занятии 7 мы после диалога заново подключаемся и отправляем /login.
        # Но правильнее – сохранить сокет из диалога.
        # Покажем упрощённый вариант: передаём username и пароль, а в MessengerApp делаем подключение и логин.
```

Упростим: в `AuthDialog` мы не будем поддерживать соединение, а только получим учётные данные. Основной клиент после этого сам подключится и отправит `/login`. Но тогда нужно хранить пароль. Лучше передать пароль тоже.

**Альтернатива:** `AuthDialog` возвращает имя и пароль, а `MessengerApp` сам устанавливает соединение и отправляет `/login`. Это проще для понимания.

### Шаг 3. Изменим точку входа

```python
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # скрываем главное окно до аутентификации
    auth = AuthDialog(root)
    if auth.result:
        username, password = auth.result
        # Создаём главное окно и передаём учётные данные
        app = MessengerApp(tk.Toplevel(), username, password, '127.0.0.1', 12345)
        tk.mainloop()
    else:
        print("Аутентификация отменена")
```

### Шаг 4. Модифицируем MessengerApp для отправки /login

В конструкторе `MessengerApp` после создания интерфейса подключаемся к серверу, отправляем `/login` и только если успешно – запускаем сетевые потоки и опрос очереди. Если нет – показываем ошибку и выходим.

```python
class MessengerApp:
    def __init__(self, root, username, password, host, port):
        self.root = root
        self.username = username
        self.host = host
        self.port = port
        self.root.title(f"Мессенджер - {username}")
        self.root.geometry("700x500")
        # ... (весь код создания GUI как в занятии 6, но без подключения пока)
        
        # Создаём очередь и сетевой объект
        self.message_queue = queue.Queue()
        self.network = NetworkClient(host, port, self.message_queue)
        success, msg = self.network.connect()
        if not success:
            messagebox.showerror("Ошибка", msg)
            self.root.destroy()
            return
        # Отправляем логин
        self.network.send(f"/login {username} {password}")
        # Ждём ответ (можно через очередь)
        self.root.after(100, self.check_login_response)
    
    def check_login_response(self):
        """Проверяет ответ сервера на логин."""
        try:
            msg = self.message_queue.get_nowait()
            if msg.startswith("OK"):
                self.display_message("[Система] Вы вошли в чат")
                # Запускаем опрос очереди
                self.poll_queue()
            else:
                messagebox.showerror("Ошибка аутентификации", msg)
                self.on_closing()
        except queue.Empty:
            self.root.after(100, self.check_login_response)
```

Этот подход рабочий, но немного громоздкий. Можно упростить: после подключения отправляем логин и затем в `poll_queue` проверяем первое сообщение.

### Шаг 5. Полный код клиента (сокращённо, но включая изменения)

Дадим финальный код клиента с аутентификацией, опираясь на `NetworkClient` из занятия 6 и добавляя `AuthDialog`. Для компактности объединим всё в один файл.

---

## Модификация сервера для поддержки паролей

Сервер из занятия 4 не проверял пароли. Добавим простой словарь пользователей:

```python
# В сервере (дополнение к chat_server_private.py)
users_db = {}  # username -> password_hash (пока храним пароль в открытом виде)
users_db_lock = threading.Lock()

# В handle_client при обработке /register и /login:
if text.startswith('/register'):
    parts = text.split()
    if len(parts) != 3:
        client_socket.send(b'ERR: Usage /register username password\n')
    else:
        _, name, pwd = parts
        with users_db_lock:
            if name in users_db:
                client_socket.send(b'ERR: Username already exists\n')
            else:
                users_db[name] = pwd
                client_socket.send(b'OK\n')
    continue

if text.startswith('/login'):
    parts = text.split()
    if len(parts) != 3:
        client_socket.send(b'ERR: Usage /login username password\n')
    else:
        _, name, pwd = parts
        with users_db_lock:
            if name in users_db and users_db[name] == pwd:
                # Аутентификация успешна
                username = name
                with users_lock:
                    if username in users:
                        client_socket.send(b'ERR: Already logged in\n')
                    else:
                        users[username] = client_socket
                        client_socket.send(f'OK: Welcome {username}\n'.encode())
                        # Далее как в занятии 4
                # ... 
            else:
                client_socket.send(b'ERR: Invalid username or password\n')
    continue
```

Это минимальная модификация. Позже заменим на хеши и БД.

---

## Полный код клиента с аутентификацией (`messenger_auth_client.py`)

Приведём итоговый код, объединяющий всё вышесказанное (с комментариями). Для краткости опустим повторяющиеся части интерфейса, но дадим полный рабочий вариант.

```python
import socket
import threading
import queue
import tkinter as tk
from tkinter import messagebox

# ------------------------ Сетевой клиент (из занятия 6) ------------------------
class NetworkClient:
    def __init__(self, host, port, message_queue):
        self.host = host
        self.port = port
        self.message_queue = message_queue
        self.socket = None
        self.receive_thread = None
        self.running = False

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            return True, "Подключено"
        except Exception as e:
            return False, str(e)

    def _receive_loop(self):
        try:
            while self.running:
                data = self.socket.recv(1024)
                if not data:
                    break
                self.message_queue.put(data.decode('utf-8'))
        except:
            pass
        finally:
            self.disconnect()

    def send(self, message):
        if self.socket and self.running:
            try:
                self.socket.send(message.encode('utf-8'))
            except Exception as e:
                self.message_queue.put(f"[Система] Ошибка отправки: {e}")

    def disconnect(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

# ------------------------ Диалог аутентификации ------------------------
class AuthDialog:
    def __init__(self, parent, host='127.0.0.1', port=12345):
        self.parent = parent
        self.host = host
        self.port = port
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Авторизация")
        self.dialog.geometry("300x200")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()

        tk.Label(self.dialog, text="Имя пользователя:").pack(pady=(10,0))
        self.entry_username = tk.Entry(self.dialog)
        self.entry_username.pack(pady=5)

        tk.Label(self.dialog, text="Пароль:").pack()
        self.entry_password = tk.Entry(self.dialog, show="*")
        self.entry_password.pack(pady=5)

        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Вход", command=self.login).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Регистрация", command=self.register).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Отмена", command=self.cancel).pack(side=tk.LEFT, padx=5)

        self.entry_username.focus()
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)

        # Временное соединение для аутентификации
        self.temp_socket = None
        self.temp_queue = queue.Queue()

        self.dialog.wait_window()

    def connect_temp(self):
        try:
            self.temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.temp_socket.connect((self.host, self.port))
            # Запускаем поток приёма
            def recv():
                while True:
                    data = self.temp_socket.recv(1024)
                    if not data:
                        break
                    self.temp_queue.put(data.decode('utf-8'))
            threading.Thread(target=recv, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться: {e}")
            return False

    def send_cmd(self, cmd):
        if not self.temp_socket:
            if not self.connect_temp():
                return None
        try:
            self.temp_socket.send(cmd.encode('utf-8'))
            # Ждём ответ
            import time
            for _ in range(30):  # 3 секунды
                try:
                    resp = self.temp_queue.get_nowait()
                    return resp
                except queue.Empty:
                    time.sleep(0.1)
            return None
        except:
            return None

    def login(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get()
        if not username or not password:
            messagebox.showwarning("Ошибка", "Заполните оба поля")
            return
        resp = self.send_cmd(f"/login {username} {password}")
        if resp and resp.startswith("OK"):
            self.result = (username, password, self.temp_socket)  # передаём сокет
            self.dialog.destroy()
        else:
            messagebox.showerror("Ошибка", resp or "Нет ответа от сервера")

    def register(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get()
        if not username or not password:
            messagebox.showwarning("Ошибка", "Заполните оба поля")
            return
        resp = self.send_cmd(f"/register {username} {password}")
        if resp and resp.startswith("OK"):
            messagebox.showinfo("Успех", "Регистрация успешна! Теперь войдите.")
        else:
            messagebox.showerror("Ошибка", resp or "Нет ответа от сервера")

    def cancel(self):
        if self.temp_socket:
            self.temp_socket.close()
        self.dialog.destroy()

# ------------------------ Главное окно мессенджера ------------------------
class MessengerApp:
    def __init__(self, root, username, password, host, port, preconnected_socket=None):
        self.root = root
        self.username = username
        self.host = host
        self.port = port
        self.root.title(f"Мессенджер - {username}")
        self.root.geometry("700x500")
        self.root.minsize(500, 400)

        # Интерфейс (как в занятии 5, но без временных контактов)
        self.left_frame = tk.Frame(self.root, width=150, bg='lightgray')
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        tk.Label(self.left_frame, text="Контакты", bg='lightgray', font=('Arial', 12, 'bold')).pack(pady=(0,5))
        self.contacts_listbox = tk.Listbox(self.left_frame, height=20, width=20)
        self.contacts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_contacts = tk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.contacts_listbox.yview)
        scroll_contacts.pack(side=tk.RIGHT, fill=tk.Y)
        self.contacts_listbox.config(yscrollcommand=scroll_contacts.set)

        self.right_frame = tk.Frame(self.root, bg='white')
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_area = tk.Text(self.right_frame, state=tk.DISABLED, wrap=tk.WORD, font=('Arial', 10))
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(0,5))
        scroll_chat = tk.Scrollbar(self.right_frame, orient=tk.VERTICAL, command=self.chat_area.yview)
        scroll_chat.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_area.config(yscrollcommand=scroll_chat.set)

        input_frame = tk.Frame(self.right_frame)
        input_frame.pack(fill=tk.X, pady=(0,5))
        self.message_entry = tk.Entry(input_frame, font=('Arial', 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        send_button = tk.Button(input_frame, text="Отправить", command=self.send_message, width=10)
        send_button.pack(side=tk.RIGHT, padx=(0,5))
        clear_button = tk.Button(input_frame, text="Очистить чат", command=self.clear_chat, width=12)
        clear_button.pack(side=tk.RIGHT)

        # Сетевая часть
        self.message_queue = queue.Queue()
        if preconnected_socket:
            # Используем уже подключённый сокет из диалога
            self.network = self._use_existing_socket(preconnected_socket)
        else:
            self.network = NetworkClient(host, port, self.message_queue)
            success, msg = self.network.connect()
            if not success:
                messagebox.showerror("Ошибка", msg)
                self.root.destroy()
                return
            self.network.send(f"/login {username} {password}")

        # Привязки
        self.contacts_listbox.bind('<<ListboxSelect>>', self.on_contact_select)
        self.message_entry.bind('<Return>', lambda e: self.send_message())
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Запускаем опрос очереди
        self.poll_queue()

    def _use_existing_socket(self, sock):
        # Оборачиваем существующий сокет в NetworkClient (упрощённо)
        class ExistingSocketClient:
            def __init__(self, sock, queue):
                self.socket = sock
                self.message_queue = queue
                self.running = True
                threading.Thread(target=self._receive_loop, daemon=True).start()
            def _receive_loop(self):
                try:
                    while self.running:
                        data = self.socket.recv(1024)
                        if not data:
                            break
                        self.message_queue.put(data.decode('utf-8'))
                except:
                    pass
            def send(self, msg):
                try:
                    self.socket.send(msg.encode())
                except:
                    pass
            def disconnect(self):
                self.running = False
                try:
                    self.socket.close()
                except:
                    pass
        return ExistingSocketClient(sock, self.message_queue)

    def display_message(self, message):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def send_message(self):
        msg = self.message_entry.get().strip()
        if not msg:
            return
        self.display_message(f"Я: {msg}")
        self.network.send(msg)   # Сервер сам знает отправителя
        self.message_entry.delete(0, tk.END)

    def clear_chat(self):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def on_contact_select(self, event):
        selection = self.contacts_listbox.curselection()
        if selection:
            contact = self.contacts_listbox.get(selection[0])
            self.root.title(f"Мессенджер - Чат с {contact}")

    def poll_queue(self):
        try:
            while True:
                msg = self.message_queue.get_nowait()
                self.display_message(msg)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.poll_queue)

    def on_closing(self):
        self.network.disconnect()
        self.root.destroy()

# ------------------------ Запуск ------------------------
def main():
    root = tk.Tk()
    root.withdraw()
    auth = AuthDialog(root, host='127.0.0.1', port=12345)
    if auth.result:
        username, password, sock = auth.result
        main_root = tk.Toplevel()
        app = MessengerApp(main_root, username, password, '127.0.0.1', 12345, sock)
        main_root.mainloop()
    else:
        print("Выход")

if __name__ == "__main__":
    main()
```

**Примечание:** В этом коде используется передача уже подключённого сокета из диалога в главное приложение, чтобы избежать повторного логина. Это продвинутый вариант. Для простоты можно было бы заново подключаться и отправлять `/login` в `MessengerApp`, но тогда сервер должен позволять повторный логин с тем же именем (что плохо). Передача сокета – правильное решение.

---

## Запуск и тестирование

1. **Модифицируйте сервер** из занятия 4, добавив поддержку `/register` и проверку паролей в `/login`. Запустите сервер.
2. **Запустите клиент** (`messenger_auth_client.py`). Появится окно авторизации.
3. **Зарегистрируйте нового пользователя** (например, `alice / pass123`). Получите сообщение об успехе.
4. **Войдите** с теми же данными. Главное окно откроется с именем `alice` в заголовке.
5. **Отправляйте сообщения** – они должны уходить на сервер. Запустите второго клиента, зарегистрируйте `bob`, войдите и проверьте обмен сообщениями (если сервер поддерживает broadcast или личные сообщения).

---

## Практическое задание

1. **Реализуйте клиент с аутентификацией** по примерам выше. Убедитесь, что регистрация и вход работают.
2. **Добавьте в сервер команду `/logout`**, которая разрывает сессию (удаляет пользователя из словаря `users`). Клиент должен отправлять `/logout` при закрытии окна.
3. **Улучшите диалог аутентификации**: добавьте поле выбора сервера (IP и Port) и кнопку "Подключиться" для проверки соединения перед вводом пароля.
4. **Добавьте отображение статуса "В процессе входа..."** на время ожидания ответа.
5. **Эксперимент:** Реализуйте "запомнить меня" – сохраняйте последнее имя пользователя в файл `config.ini` и подставляйте его при следующем запуске.

---

## Вопросы для самопроверки

1. Почему аутентификацию нужно выполнять до открытия главного окна?
2. Как передать установленное соединение из диалога в главное приложение?
3. Какие команды протокола добавились на этом занятии?
4. Почему нельзя хранить пароли в открытом виде? Что мы сделаем на следующем занятии?
5. Как обеспечить безопасность при передаче пароля по сети в реальном приложении?

---

## Что дальше?

На следующем занятии (№8) мы добавим базу данных SQLite на сервере для хранения пользователей и истории сообщений, а также научимся хешировать пароли. Это сделает наш мессенджер более надёжным и функциональным. Сейчас же вы получили полностью работающий клиент с аутентификацией – важный шаг к завершённому продукту.