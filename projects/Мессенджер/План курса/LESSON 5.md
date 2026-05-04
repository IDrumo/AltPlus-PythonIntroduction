# Занятие 5. Графический интерфейс клиента на tkinter (основы)

## Цель занятия

Освоить базовые виджеты библиотеки tkinter, научиться создавать оконный интерфейс для мессенджера. Мы возьмём заготовку `messanger.py` и реализуем в ней:
- область чата только для чтения,
- функцию отправки сообщения (локальное отображение),
- очистку чата,
- реакцию на выбор контакта (пока просто меняем заголовок окна).

В результате получится работающий GUI, который визуально похож на мессенджер, но без сетевой части – отображение сообщений будет локальным, для отладки интерфейса.

---

## Теоретическая часть

### Библиотека tkinter

Tkinter – стандартная библиотека Python для создания графических интерфейсов. Она проста в освоении и входит в поставку Python.

Основные виджеты, которые мы используем:

| Виджет | Назначение |
|--------|-------------|
| `Tk` | Главное окно приложения |
| `Frame` | Контейнер для группировки виджетов |
| `Text` | Многострочное текстовое поле (для области чата) |
| `Entry` | Однострочное поле ввода (для сообщения) |
| `Button` | Кнопка |
| `Listbox` | Список (для контактов) |
| `Scrollbar` | Полоса прокрутки |

### Менеджеры геометрии

Управляют расположением виджетов в окне:

- **`pack()`** – простой "упаковщик": размещает виджеты последовательно (сверху вниз или слева направо).
- **`grid()`** – табличная верстка (ряды и колонки).
- **`place()`** – абсолютное позиционирование (не рекомендуется для адаптивных интерфейсов).

В нашем мессенджере удобно использовать `pack()` для основных блоков и `grid()` для внутренней структуры.

### Привязка событий

- **`command`** – параметр кнопки: функция, вызываемая при нажатии.
- **`bind()`** – привязка событий клавиатуры/мыши к любому виджету (например, нажатие Enter в поле ввода).

Пример:
```python
def on_enter_pressed(event):
    send_message()

entry.bind('<Return>', on_enter_pressed)
```

### Состояния виджетов

- `state=tk.NORMAL` – виджет активен, можно редактировать.
- `state=tk.DISABLED` – виджет заблокирован (только для чтения). Для области чата нам нужно `DISABLED`, чтобы пользователь не мог редактировать историю.

---

## Практика: доработка заготовки `messanger.py`

Предполагается, что у нас есть начальный файл `messanger.py` с базовой структурой:

```python
import tkinter as tk

class MessengerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Мессенджер")
        self.root.geometry("600x400")
        
        # TODO: добавить виджеты
        
    def send_message(self):
        # TODO: отправка сообщения
        pass
    
    def clear_chat(self):
        # TODO: очистка чата
        pass
    
    def on_contact_select(self, event):
        # TODO: выбор контакта
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = MessengerApp(root)
    root.mainloop()
```

### Пошаговая разработка

#### Шаг 1. Создаём фреймы (панели)

Разделим окно на левую панель (список контактов) и правую (область чата и ввод).

```python
# Левая панель
self.left_frame = tk.Frame(self.root, width=150, bg='lightgray')
self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

# Правая панель
self.right_frame = tk.Frame(self.root, bg='white')
self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
```

#### Шаг 2. Добавляем список контактов (Listbox) с прокруткой

```python
# Список контактов
self.contacts_listbox = tk.Listbox(self.left_frame, height=20, width=20)
self.contacts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Полоса прокрутки для списка контактов
scroll_contacts = tk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.contacts_listbox.yview)
scroll_contacts.pack(side=tk.RIGHT, fill=tk.Y)
self.contacts_listbox.config(yscrollcommand=scroll_contacts.set)

# Пример контактов (временно)
for contact in ["Алиса", "Боб", "Чарли"]:
    self.contacts_listbox.insert(tk.END, contact)
```

#### Шаг 3. Область чата (Text) – только для чтения

```python
# Текстовая область для отображения сообщений
self.chat_area = tk.Text(self.right_frame, state=tk.DISABLED, wrap=tk.WORD)
self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

# Полоса прокрутки для чата
scroll_chat = tk.Scrollbar(self.right_frame, orient=tk.VERTICAL, command=self.chat_area.yview)
scroll_chat.pack(side=tk.RIGHT, fill=tk.Y)
self.chat_area.config(yscrollcommand=scroll_chat.set)
```

#### Шаг 4. Панель ввода сообщения (Entry + Button)

```python
# Фрейм для ввода и кнопок
input_frame = tk.Frame(self.right_frame)
input_frame.pack(fill=tk.X, pady=(0, 5))

self.message_entry = tk.Entry(input_frame)
self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

send_button = tk.Button(input_frame, text="Отправить", command=self.send_message)
send_button.pack(side=tk.RIGHT)

clear_button = tk.Button(input_frame, text="Очистить чат", command=self.clear_chat)
clear_button.pack(side=tk.RIGHT, padx=(0, 5))
```

#### Шаг 5. Привязываем событие выбора контакта

```python
self.contacts_listbox.bind('<<ListboxSelect>>', self.on_contact_select)
```

#### Шаг 6. Реализуем методы

```python
def send_message(self):
    """Взять текст из поля ввода и вывести в область чата (локально)."""
    message = self.message_entry.get().strip()
    if message:
        # Включаем редактирование чата
        self.chat_area.config(state=tk.NORMAL)
        # Вставляем сообщение от "Я"
        self.chat_area.insert(tk.END, f"Я: {message}\n")
        # Прокручиваем вниз
        self.chat_area.see(tk.END)
        # Отключаем редактирование
        self.chat_area.config(state=tk.DISABLED)
        # Очищаем поле ввода
        self.message_entry.delete(0, tk.END)

def clear_chat(self):
    """Очистить область чата."""
    self.chat_area.config(state=tk.NORMAL)
    self.chat_area.delete(1.0, tk.END)
    self.chat_area.config(state=tk.DISABLED)

def on_contact_select(self, event):
    """Обработка выбора контакта из списка."""
    selection = self.contacts_listbox.curselection()
    if selection:
        contact = self.contacts_listbox.get(selection[0])
        self.root.title(f"Мессенджер - Чат с {contact}")
        # Здесь позже будем загружать историю сообщений
```

#### Шаг 7. Добавим удобство: отправка по Enter

```python
self.message_entry.bind('<Return>', lambda event: self.send_message())
```

---

## Полный код `messanger.py` после доработки

```python
import tkinter as tk

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

        # Список контактов
        self.contacts_listbox = tk.Listbox(self.left_frame, height=20, width=20)
        self.contacts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Полоса прокрутки для контактов
        scroll_contacts = tk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.contacts_listbox.yview)
        scroll_contacts.pack(side=tk.RIGHT, fill=tk.Y)
        self.contacts_listbox.config(yscrollcommand=scroll_contacts.set)

        # Временные контакты для демонстрации
        for contact in ["Алиса", "Боб", "Чарли", "Диана"]:
            self.contacts_listbox.insert(tk.END, contact)

        # --- Правая панель (чат) ---
        self.right_frame = tk.Frame(self.root, bg='white')
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Область отображения сообщений
        self.chat_area = tk.Text(self.right_frame, state=tk.DISABLED, wrap=tk.WORD, font=('Arial', 10))
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Полоса прокрутки для чата
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

        # Привязка событий
        self.contacts_listbox.bind('<<ListboxSelect>>', self.on_contact_select)
        self.message_entry.bind('<Return>', lambda event: self.send_message())

    def send_message(self):
        """Отправить сообщение (локальное отображение)."""
        message = self.message_entry.get().strip()
        if message:
            self.chat_area.config(state=tk.NORMAL)
            self.chat_area.insert(tk.END, f"Я: {message}\n")
            self.chat_area.see(tk.END)
            self.chat_area.config(state=tk.DISABLED)
            self.message_entry.delete(0, tk.END)

    def clear_chat(self):
        """Очистить область чата."""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def on_contact_select(self, event):
        """Обработка выбора контакта."""
        selection = self.contacts_listbox.curselection()
        if selection:
            contact = self.contacts_listbox.get(selection[0])
            self.root.title(f"Мессенджер - Чат с {contact}")
            # Здесь позже будет загрузка истории сообщений

if __name__ == "__main__":
    root = tk.Tk()
    app = MessengerApp(root)
    root.mainloop()
```

---

## Запуск и проверка

1. Сохраните код в файл `messanger.py`.
2. Запустите: `python messanger.py`.
3. Проверьте:
   - Список контактов слева (при выборе меняется заголовок окна).
   - Ввод текста в поле и нажатие "Отправить" – сообщение появляется в чате.
   - Кнопка "Очистить чат" удаляет все сообщения.
   - Отправка по нажатию Enter работает.
   - Область чата нельзя редактировать вручную (только через программу).

---

## Практическое задание

1. **Создайте/доработайте `messanger.py`** в соответствии с кодом выше. Убедитесь, что интерфейс работает.

2. **Добавьте статусную строку** (внизу окна) с текстом "Готов к работе". Используйте виджет `Label`.

3. **Модифицируйте `send_message()`**, чтобы она не отправляла пустые сообщения и показывала предупреждение через `messagebox.showwarning`, если поле ввода пустое.

4. **Добавьте возможность удалить выбранный контакт** (временно, без сохранения). Сделайте кнопку "Удалить контакт", которая удаляет выделенный элемент из `Listbox`.

5. **Эксперимент:** Измените цветовую схему: тёмный фон чата, светлый текст. Настройте шрифты.

---

## Вопросы для самопроверки

1. Для чего мы устанавливаем `state=tk.DISABLED` для `chat_area`? Что произойдёт, если не сделать этого?
2. В чём разница между `pack()` и `grid()`? Когда что удобнее?
3. Как привязать нажатие клавиши Enter к функции отправки сообщения?
4. Почему перед вставкой текста в `chat_area` мы меняем состояние на `NORMAL`, а после – обратно на `DISABLED`?
5. Как получить выбранный элемент из `Listbox`?

---

## Что дальше?

На следующем занятии (№6) мы подключим сетевую часть: создадим класс `NetworkClient`, который будет работать в отдельном потоке, принимать сообщения от сервера и помещать их в очередь. В GUI с помощью метода `after()` будем периодически проверять очередь и выводить сообщения в `chat_area`. Так мы соединим графический интерфейс с настоящим сервером из занятий 3-4.

Сейчас же вы освоили основы tkinter и создали полностью функциональный локальный интерфейс – важный шаг к итоговому проекту.