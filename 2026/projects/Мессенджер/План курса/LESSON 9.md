# Занятие 9. История сообщений и команда `/history`

## Цель занятия

Научиться загружать и отображать историю переписки между двумя пользователями. Мы добавим на сервер команду `/history`, которая возвращает последние N сообщений из базы данных. На клиенте при выборе контакта будем автоматически запрашивать историю и выводить её в область чата. В результате пользователь сможет видеть предыдущие диалоги при открытии чата с любым контактом.

---

## Теоретическая часть

### Зачем нужна история сообщений?

В реальных мессенджерах сообщения сохраняются на сервере. Когда пользователь открывает диалог с контактом, он видит не только новые, но и старые сообщения. Это улучшает UX и позволяет не потерять важную информацию.

### Команда `/history`

Мы расширим протокол сервера новой командой:

**Формат:** `/history target_username [limit]`

- `target_username` – имя собеседника (обязательно).
- `limit` – количество последних сообщений (необязательно, по умолчанию 50).

**Ответ сервера:**  
Сервер возвращает список сообщений в формате, удобном для отображения, например:

```
HISTORY_START
2025-03-15 14:23:10 - alice -> bob: Привет!
2025-03-15 14:24:05 - bob -> alice: Здравствуй!
...
HISTORY_END
```

Или просто отправляет каждое сообщение как отдельную строку. Для простоты сервер может отправить обычные текстовые строки, которые клиент выведет в чат.

### SQL-запрос для истории

Чтобы получить последние сообщения между пользователями `user1` и `user2`, нужно выбрать строки, где:
- `(from_user = user1 AND to_user = user2)` – сообщения, отправленные user1 пользователю user2,
- `OR (from_user = user2 AND to_user = user1)` – сообщения, отправленные user2 пользователю user1.

Сортируем по времени убывания, ограничиваем `LIMIT`, а затем разворачиваем в правильном хронологическом порядке.

```sql
SELECT from_user, text, timestamp 
FROM messages 
WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
ORDER BY timestamp DESC 
LIMIT ?
```

После получения строк мы переворачиваем список, чтобы отображать от старых к новым.

### Отображение истории в GUI

При выборе контакта в `Listbox`:
1. Очищаем текущую область чата.
2. Отправляем на сервер команду `/history contact_name`.
3. Сервер присылает историю – клиент выводит её в `chat_area`.
4. Затем клиент продолжает нормально принимать новые сообщения (они будут добавляться ниже).

Важно не заблокировать интерфейс – отправка команды и ожидание ответа должны быть асинхронными. Ответ придёт через очередь, как и обычные сообщения. Поэтому в `poll_queue` мы будем распознавать сообщения истории и выводить их особым образом (можно просто выводить как есть).

---

## Практика: добавление `/history` на сервер

Модифицируем серверный код (из занятия 8). Добавим обработку команды `/history` в функцию `handle_client`.

### Шаг 1. Добавляем метод в класс Database

В файле `database.py` добавим:

```python
def get_history(self, user1, user2, limit=50):
    """Возвращает список сообщений между user1 и user2 (последние limit)."""
    with self.lock:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT from_user, text, timestamp 
            FROM messages 
            WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (user1, user2, user2, user1, limit))
        rows = cursor.fetchall()
        conn.close()
    # Возвращаем в хронологическом порядке (от старых к новым)
    return list(reversed(rows))
```

### Шаг 2. Добавляем обработку команды в сервер

В основном серверном цикле (после обработки `/msg` и перед broadcast) добавим:

```python
if text.startswith('/history'):
    parts = text.split()
    if len(parts) < 2:
        client_socket.send(b'ERR: Usage /history username [limit]\n')
        continue
    target = parts[1]
    limit = 50
    if len(parts) >= 3:
        try:
            limit = int(parts[2])
        except:
            client_socket.send(b'ERR: Invalid limit\n')
            continue
    if username is None:
        client_socket.send(b'ERR: You must login first\n')
        continue
    # Получаем историю
    history = db.get_history(username, target, limit)
    if not history:
        client_socket.send(b'HISTORY: No messages found\n')
    else:
        client_socket.send(b'HISTORY_START\n')
        for from_user, text, timestamp in history:
            # Форматируем: [2025-03-15 14:23:10] alice -> bob: Привет!
            line = f"[{timestamp}] {from_user}: {text}\n"
            client_socket.send(line.encode('utf-8'))
        client_socket.send(b'HISTORY_END\n')
    continue
```

Обратите внимание: мы отправляем маркеры `HISTORY_START` и `HISTORY_END`, чтобы клиент знал, где начинается и заканчивается история. Это полезно, если клиент захочет очистить чат перед выводом истории.

---

## Практика: модификация клиента для загрузки истории

В клиенте (из занятия 7) нам нужно:
1. При выборе контакта отправлять команду `/history`.
2. В методе `poll_queue` распознавать блок истории и вставлять его в чат, предварительно очистив область чата.
3. Обычные сообщения (не входящие в блок истории) выводить как обычно.

### Шаг 1. Добавляем переменные состояния

В классе `MessengerApp` добавим:
```python
self.loading_history = False   # флаг, что мы ждём историю
self.current_contact = None    # имя текущего выбранного контакта
```

### Шаг 2. Модифицируем `on_contact_select`

Теперь при выборе контакта:
- Очищаем чат.
- Устанавливаем `self.current_contact = contact`.
- Отправляем команду `/history contact`.
- Устанавливаем флаг `self.loading_history = True`.

```python
def on_contact_select(self, event):
    selection = self.contacts_listbox.curselection()
    if selection:
        contact = self.contacts_listbox.get(selection[0])
        self.current_contact = contact
        self.root.title(f"Мессенджер - Чат с {contact}")
        # Очищаем чат
        self.clear_chat()
        # Запрашиваем историю
        self.loading_history = True
        self.network.send(f"/history {contact}")
```

### Шаг 3. Модифицируем `poll_queue` для обработки истории

В `poll_queue` мы должны распознать сообщения, начинающиеся с `HISTORY_START` и `HISTORY_END`. Между ними все строки – это история, их нужно вывести в чат (без дополнительных системных пометок).

Удобно ввести небольшой конечный автомат:

```python
def poll_queue(self):
    try:
        while True:
            msg = self.message_queue.get_nowait()
            if msg == "HISTORY_START":
                self.in_history = True
                continue
            if msg == "HISTORY_END":
                self.in_history = False
                continue
            if self.in_history:
                # Это строка истории, выводим как есть
                self.display_message(msg.rstrip('\n'))
            else:
                # Обычное сообщение (от сервера или от других)
                self.display_message(msg)
    except queue.Empty:
        pass
    finally:
        self.root.after(100, self.poll_queue)
```

Для этого нужно добавить в `__init__`:
```python
self.in_history = False
```

Но будьте внимательны: при отправке истории сервер отправляет строки, заканчивающиеся `\n`, и они могут приходить порциями. Лучше, чтобы сервер отправлял каждое сообщение истории как отдельный пакет, но в реальности TCP может склеивать. Поэтому надёжнее собирать историю до получения `HISTORY_END`. Однако для простоты можно использовать построчный вывод, так как `recv(1024)` обычно захватывает несколько строк, и они будут обработаны за один цикл. Но возможны краевые эффекты.

**Более надёжный способ:** буферизовать входящие строки, пока не встретим `HISTORY_END`. Но в учебном проекте допустим упрощённый вариант.

### Шаг 4. Сбрасываем флаг после получения истории

После того как мы получили `HISTORY_END`, выходим из режима истории. Также можно очистить флаг `loading_history`.

---

## Полный код клиента с поддержкой истории (ключевые изменения)

Приведём только изменённые и новые части. Остальной код остаётся как в занятии 7.

```python
class MessengerApp:
    def __init__(self, root, username, password, host, port, preconnected_socket=None):
        # ... существующий код ...
        self.current_contact = None
        self.in_history = False
        # ...

    def on_contact_select(self, event):
        selection = self.contacts_listbox.curselection()
        if selection:
            contact = self.contacts_listbox.get(selection[0])
            self.current_contact = contact
            self.root.title(f"Мессенджер - Чат с {contact}")
            self.clear_chat()
            self.in_history = True
            self.network.send(f"/history {contact}")

    def poll_queue(self):
        try:
            while True:
                msg = self.message_queue.get_nowait()
                if msg == "HISTORY_START":
                    continue
                if msg == "HISTORY_END":
                    self.in_history = False
                    continue
                # Отображаем сообщение
                if self.in_history:
                    # Убираем лишние переводы строк, которые могут быть
                    self.display_message(msg.rstrip('\n'))
                else:
                    self.display_message(msg)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.poll_queue)

    def display_message(self, message):
        """Отобразить сообщение в чате (без изменений)."""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, f"{message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)
```

Важно: при выводе истории мы не должны добавлять префиксы типа "Я:" или "[Private]". Сервер уже отправляет отформатированные строки вида `[2025-03-15 14:23:10] alice: Привет!`. Поэтому `display_message` просто вставляет их.

---

## Тестирование

1. Запустите сервер с БД (занятие 8).
2. Запустите два клиента, зарегистрируйте `alice` и `bob`.
3. Отправьте несколько личных сообщений от Алисы Бобу и от Боба Алисе.
4. Закройте клиентов, снова запустите Алису, выберите в списке контактов Боба. Должна загрузиться история предыдущей переписки.
5. Отправьте новое сообщение – оно добавится в конец чата и сохранится в БД.

---

## Практическое задание

1. **Реализуйте команду `/history` на сервере** (SQL-запрос, форматирование ответа с маркерами).

2. **Модифицируйте клиент** для отправки `/history` при выборе контакта и отображения истории.

3. **Добавьте параметр `limit` в GUI**: пусть будет дополнительное поле ввода или диалог, где можно указать количество сообщений (например, 20, 50, 100). Передавайте его в команде.

4. **Улучшите отображение истории**: добавьте разделитель "=== История ===" перед историей и "=== Конец истории ===" после.

5. **Эксперимент:** Реализуйте автоматическую прокрутку чата к последнему сообщению после загрузки истории.

---

## Вопросы для самопроверки

1. Зачем нужны маркеры `HISTORY_START` и `HISTORY_END`? Что будет, если их не использовать?
2. Как изменится SQL-запрос, если мы захотим загружать историю, начиная с определённой даты?
3. Почему мы не сохраняем broadcast-сообщения в таблицу `messages`? Как бы вы их сохранили?
4. Как сделать так, чтобы при загрузке истории чат не мигал и не перерисовывался для каждого сообщения?
5. Что произойдёт, если во время загрузки истории придёт новое сообщение от собеседника?

---

## Что дальше?

На следующем занятии (№10) мы добавим список контактов и онлайн-статус. Сервер будет рассылать всем клиентам обновлённый список пользователей с пометкой, кто онлайн. В GUI список контактов будет динамически обновляться. Это приблизит нас к полноценному мессенджеру. Сейчас же вы научились загружать историю – важная функция любого чата. Отличная работа!