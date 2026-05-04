import tkinter as tk

def send_message():
    pass

def on_contact_select(event):
    pass

def clear_chat(event):
    pass


root = tk.Tk()
root.title("Мой мессенджер")
root.geometry("700x900")


chat_area = tk.Text(root, height=20, width=50)
contacts_listbox = tk.Listbox(root, width=20, height=15)
contacts_listbox.insert(tk.END, "Пользователь 1", "Железный человек", "Моргенштерн")
contacts_listbox.bind("<<ListboxSelect>>", on_contact_select)
send_at_label = tk.Label(root, text='Выберете пользователя')
bottom_frame = tk.Frame(root)
entry = tk.Entry(bottom_frame, width=40)
send_btn = tk.Button(bottom_frame, text="Отправить", command=send_message)

# Разметка
contacts_listbox.grid(row=0, column=0, sticky='ns')
chat_area.grid(row=0, column=1, sticky='nsew')

bottom_frame.grid(row=1, column=1, sticky='ew')
entry.pack(expand=True)
send_btn.pack()

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

entry.focus()

root.mainloop()
