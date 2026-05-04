# Занятие 6. Сетевой клиент в отдельном потоке + очередь сообщений

## Цель занятия

Научиться объединять графический интерфейс tkinter с сетевыми операциями. Главная проблема: tkinter работает в главном потоке и не должен блокироваться. Сетевые вызовы (особенно `recv()`) блокируют поток. Решение – вынести сетевую часть в отдельный поток, а для безопасной передачи данных между потоками использовать очередь (`queue.Queue`). В GUI метод `after()` будет периодически проверять очередь и обновлять интерфейс.

В результате мы получим полноценный GUI-клиент, который подключается к серверу (из занятия 3 или 4), может отправлять сообщения и отображать входящие сообщения в реальном времени.

---

## Теоретическая часть

### Проблема совмещения tkinter и блокирующих операций

tkinter имеет собственный главный цикл (`mainloop()`), который обрабатывает события (нажатия кнопок, ввод текста, перерисовку). Если этот цикл заблокировать (например, вызовом `time.sleep()` или ожиданием данных по сети), интерфейс "замрёт" – перестанет реагировать на действия пользователя.

**Плохой пример (так делать нельзя):**
```python
def get_message():
    data = sock.recv(1024)  # блокировка на неопределённое время
    chat_area.insert(tk.END, data)
```

Если вызвать такую функцию по нажатию кнопки, интерфейс зависнет до получения сообщения.

**Решение:** вынести блокирующие операции в отдельный поток, а готовые данные передавать в главный поток через очередь.

### Модуль `queue.Queue`

Очередь – потокобезопасная структура данных "первым пришёл – первым ушёл" (FIFO). Поток-получатель может ждать данные, а поток-отправитель – класть их в очередь.

Основные методы:
- `put(item)` – добавить элемент в очередь (неблокирующий).
- `get()` – извлечь элемент (если очередь пуста, блокирует поток до появления элемента).
- `get_nowait()` – неблокирующее получение (если пусто, выбрасывает исключение `queue.Empty`).

В нашем случае:
- **Сетевой поток** получает сообщения от сервера и кладёт их в очередь.
- **Главный поток (GUI)** периодически проверяет очередь и забирает сообщения для отображения.

### Метод `after()`

`after(delay_ms, callback)` – метод tkinter, который планирует вызов функции `callback` через `delay_ms` миллисекунд. Он не блокирует главный цикл.

Типичный паттерн для опроса очереди:
```python
def poll_queue(self):
    try:
        while True:
            msg = self.message_queue.get_nowait()
            self.display_message(msg)
    except queue.Empty:
        pass
    finally:
        self.root.after(100, self.poll_queue)  # повторный вызов через 100 мс
```

Этот метод будет вызываться каждые 100 мс, проверять очередь и обновлять интерфейс.

### Структура сетевого клиента

Выделим логику сети в отдельный класс `NetworkClient`:
- Подключение к серверу.
- Метод `send(message)` для отправки данных (неблокирующий, так как отправка обычно быстрая).
- Поток приёма, который читает данные из сокета и складывает их в очередь.

Класс будет запускаться в GUI при старте приложения или после нажатия кнопки "Подключиться".

---

## Практика: интеграция сети в GUI клиент

Мы будем модифицировать `messanger.py` из занятия 5. Добавим:
1. Класс `NetworkClient`.
2. В основном классе `MessengerApp` – очередь сообщений, метод `poll_queue`, подключение к серверу при запуске.
3. Отправку сообщений через сеть вместо локального вывода.
4. Отображение входящих сообщений.

### Пошаговая разработка

#### Шаг 1. Импортируем необходимые модули

Добавим в начало `messanger.py`:
```python
import socket
import threading
import queue
import tkinter as tk
from tkinter import messagebox
```

#### Шаг 2. Создаём класс NetworkClient

Этот класс будет управлять сокетом и потоком приёма.

```python
class NetworkClient:
    def __init__(self, host, port, message_queue):
        self.host = host
        self.port = port
        self.message_queue = message_queue   # очередь для сообщений от сервера
        self.socket = None
        self.receive_thread = None
        self.running = False

    def connect(self):
        """Подключиться к серверу и запустить поток приёма."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            return True, "Подключено к серверу"
        except Exception as e:
            return False, f"Ошибка подключения: {e}"

    def _receive_loop(self):
        """Поток: постоянно принимает данные от сервера и кладёт в очередь."""
        try:
            while self.running:
                data = self.socket.recv(1024)
                if not data:
                    break
                message = data.decode('utf-8')
                self.message_queue.put(message)  # передаём в GUI
        except Exception as e:
            self.message_queue.put(f"[Система] Ошибка приёма: {e}")
        finally:
            self.disconnect()

    def send(self, message):
        """Отправить сообщение серверу (неблокирующий вызов)."""
        if self.socket and self.running:
            try:
                self.socket.send(message.encode('utf-8'))
            except Exception as e:
                self.message_queue.put(f"[Система] Ошибка отправки: {e}")

    def disconnect(self):
        """Закрыть соединение."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.socket = None
```

#### Шаг 3. Модифицируем MessengerApp

Добавляем в `__init__`:
- Создание очереди: `self.message_queue = queue.Queue()`
- Создание сетевого клиента (пока без подключения, можно позже в отдельном диалоге, но для простоты подключимся сразу).
- Запуск "опроса" очереди: `self.poll_queue()`

```python
class MessengerApp:
    def __init__(self, root):
        # ... (весь код интерфейса из занятия 5) ...
        
        # Сетевая часть
        self.message_queue = queue.Queue()
        self.network = NetworkClient('127.0.0.1', 12345, self.message_queue)
        
        # Подключаемся к серверу
        success, msg = self.network.connect()
        if not success:
            messagebox.showerror("Ошибка", msg)
        else:
            self.chat_area.config(state=tk.NORMAL)
            self.chat_area.insert(tk.END, f"[Система] {msg}\n")
            self.chat_area.config(state=tk.DISABLED)
        
        # Запускаем периодическую проверку очереди
        self.poll_queue()
```

#### Шаг 4. Метод poll_queue

Добавляем в класс `MessengerApp`:

```python
def poll_queue(self):
    """Периодически проверяет очередь и выводит новые сообщения."""
    try:
        while True:
            msg = self.message_queue.get_nowait()
            self.display_message(msg)
    except queue.Empty:
        pass
    finally:
        # Повторяем вызов через 100 мс
        self.root.after(100, self.poll_queue)
```

#### Шаг 5. Метод display_message

Выводит сообщение в `chat_area`:

```python
def display_message(self, message):
    """Отобразить сообщение в области чата."""
    self.chat_area.config(state=tk.NORMAL)
    self.chat_area.insert(tk.END, f"{message}\n")
    self.chat_area.see(tk.END)
    self.chat_area.config(state=tk.DISABLED)
```

#### Шаг 6. Модифицируем send_message

Вместо локальной вставки отправляем сообщение через сеть и (опционально) показываем его сразу как "Я: текст" (можно и так, и так). Но чтобы избежать дублирования при получении эха от сервера (если сервер повторяет сообщения), лучше показывать своё сообщение сразу, а ответы сервера будут приходить отдельно. Однако наш будущий протокол может не эхотировать. Для группового чата из занятия 3 сервер рассылает всем, включая отправителя? Нет, в broadcast мы исключали отправителя. Значит, своё сообщение нужно показывать локально.

Исправленный `send_message`:

```python
def send_message(self):
    """Отправить сообщение через сеть и отобразить локально."""
    message = self.message_entry.get().strip()
    if not message:
        messagebox.showwarning("Предупреждение", "Введите сообщение")
        return
    
    # Отображаем своё сообщение сразу
    self.display_message(f"Я: {message}")
    # Отправляем на сервер
    self.network.send(message)
    # Очищаем поле ввода
    self.message_entry.delete(0, tk.END)
```

#### Шаг 7. Закрытие соединения при выходе

Переопределим метод закрытия окна:

```python
def on_closing(self):
    """При закрытии окна отключаемся от сервера."""
    self.network.disconnect()
    self.root.destroy()
```

В `__init__` добавим:
```python
self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
```

---

## Полный код `messanger.py` после занятия 6

```python
import socket
import threading
import queue
import tkinter as tk
from tkinter import messagebox

# --- Сетевой клиент ---
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
            return True, "Подключено к серверу"
        except Exception as e:
            return False, f"Ошибка подключения: {e}"

    def _receive_loop(self):
        try:
            while self.running:
                data = self.socket.recv(1024)
                if not data:
                    break
                message = data.decode('utf-8')
                self.message_queue.put(message)
        except Exception as e:
            self.message_queue.put(f"[Система] Ошибка приёма: {e}")
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

# --- Главное приложение ---
class MessengerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Мессенджер")
        self.root.geometry("700x500")
        self.root.minsize(500, 400)

        # --- Левая панель (контакты) ---
        self.left_frame = tk.Frame(self.root, width=150, bg='lightgray')
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        tk.Label(self.left_frame, text="Контакты", bg='lightgray', font=('Arial', 12, 'bold')).pack(pady=(0, 5))

        self.contacts_listbox = tk.Listbox(self.left_frame, height=20, width=20)
        self.contacts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_contacts = tk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.contacts_listbox.yview)
        scroll_contacts.pack(side=tk.RIGHT, fill=tk.Y)
        self.contacts_listbox.config(yscrollcommand=scroll_contacts.set)

        # Временные контакты
        for contact in ["Алиса", "Боб", "Чарли"]:
            self.contacts_listbox.insert(tk.END, contact)

        # --- Правая панель (чат) ---
        self.right_frame = tk.Frame(self.root, bg='white')
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.chat_area = tk.Text(self.right_frame, state=tk.DISABLED, wrap=tk.WORD, font=('Arial', 10))
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        scroll_chat = tk.Scrollbar(self.right_frame, orient=tk.VERTICAL, command=self.chat_area.yview)
        scroll_chat.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_area.config(yscrollcommand=scroll_chat.set)

        # --- Панель ввода ---
        input_frame = tk.Frame(self.right_frame)
        input_frame.pack(fill=tk.X, pady=(0, 5))

        self.message_entry = tk.Entry(input_frame, font=('Arial', 10))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        send_button = tk.Button(input_frame, text="Отправить", command=self.send_message, width=10)
        send_button.pack(side=tk.RIGHT, padx=(0, 5))

        clear_button = tk.Button(input_frame, text="Очистить чат", command=self.clear_chat, width=12)
        clear_button.pack(side=tk.RIGHT)

        # --- Сетевая часть ---
        self.message_queue = queue.Queue()
        self.network = NetworkClient('127.0.0.1', 12345, self.message_queue)
        success, msg = self.network.connect()
        if not success:
            messagebox.showerror("Ошибка", msg)
        else:
            self.display_message(f"[Система] {msg}")

        # Запускаем опрос очереди
        self.poll_queue()

        # Привязка событий
        self.contacts_listbox.bind('<<ListboxSelect>>', self.on_contact_select)
        self.message_entry.bind('<Return>', lambda event: self.send_message())
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def display_message(self, message):
        """Отобразить сообщение в чате."""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def send_message(self):
        """Отправить сообщение."""
        message = self.message_entry.get().strip()
        if not message:
            messagebox.showwarning("Предупреждение", "Введите сообщение")
            return
        # Отображаем своё сообщение
        self.display_message(f"Я: {message}")
        # Отправляем на сервер
        self.network.send(message)
        self.message_entry.delete(0, tk.END)

    def clear_chat(self):
        """Очистить чат."""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def on_contact_select(self, event):
        """Выбор контакта (пока просто заголовок)."""
        selection = self.contacts_listbox.curselection()
        if selection:
            contact = self.contacts_listbox.get(selection[0])
            self.root.title(f"Мессенджер - Чат с {contact}")

    def poll_queue(self):
        """Периодически забирать сообщения из очереди и выводить."""
        try:
            while True:
                msg = self.message_queue.get_nowait()
                self.display_message(msg)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.poll_queue)

    def on_closing(self):
        """Закрытие окна."""
        self.network.disconnect()
        self.root.destroy()

# --- Запуск ---
if __name__ == "__main__":
    root = tk.Tk()
    app = MessengerApp(root)
    root.mainloop()
```

---

## Запуск и тестирование

Для тестирования нам нужен сервер, который принимает текстовые сообщения. Подойдёт сервер из занятия 3 (групповой чат) или занятия 4 (с личными сообщениями).

1. **Запустите сервер** (например, `chat_server.py` из занятия 3).
2. **Запустите клиент** `messanger.py`. Должно появиться окно с подключением к серверу.
3. **Отправьте сообщение** через GUI – оно появится в чате как "Я: ..." и отправится на сервер.
4. **Запустите второй экземпляр клиента** (или два). Сообщения, отправленные одним клиентом, должны появляться у других (в зависимости от сервера). Входящие сообщения будут отображаться с пометкой (например, `[Алиса] Привет` или `[Общее] ...` в зависимости от сервера).
5. **Закройте окно** – сетевое соединение должно корректно разорваться.

---

## Практическое задание

1. **Реализуйте GUI-клиент** по приведённому коду, подключив его к серверу из занятия 3 или 4. Убедитесь, что сообщения доставляются.

2. **Добавьте диалог подключения**: перед запуском показывайте окно (Toplevel) с полями для ввода HOST и PORT, чтобы можно было подключаться к разным серверам.

3. **Добавьте индикатор соединения**: Label, который меняет цвет/текст в зависимости от статуса (подключено/отключено). Используйте очередь для получения системных сообщений.

4. **Реализуйте кнопку "Отключиться"**, которая разрывает соединение и позволяет подключиться заново (с пересозданием NetworkClient).

5. **Эксперимент:** Добавьте звуковое уведомление (через `playsound` или встроенный `beep`) при получении нового сообщения.

---

## Вопросы для самопроверки

1. Почему нельзя вызывать `recv()` в главном потоке tkinter?
2. Зачем нужна очередь (`queue.Queue`), а не глобальная переменная?
3. Что произойдёт, если очередь будет переполнена? Как этого избежать?
4. Зачем вызывать `after()` в конце `poll_queue()`? Что будет, если не вызывать?
5. Почему поток приёма объявлен как `daemon = True`?

---

## Что дальше?

На следующем занятии (№7) мы добавим протокол аутентификации: диалоговое окно логина, отправку команды `/login`, обработку ответов сервера (`OK`/`ERR`). Также начнём интегрировать команды личных сообщений (`/msg`). Сейчас же вы создали полноценного сетевого GUI-клиента – важнейший шаг к итоговому мессенджеру. Поздравляю!