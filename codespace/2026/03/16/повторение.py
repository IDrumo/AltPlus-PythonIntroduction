import sqlite3

connection = sqlite3.connect('books.db')
cursor = connection.cursor()
cursor.execute('''DROP TABLE IF EXISTS books''')
cursor.execute('''DROP TABLE IF EXISTS authors''')

cursor.execute('''
               CREATE TABLE IF NOT EXISTS authors
               (
                   id       INTEGER PRIMARY KEY AUTOINCREMENT,
                   name     TEXT NOT NULL,
                   birthday TIMESTAMP
               )
               ''')

authors = [
    ("Грин",),
    ("Роулинг",),
    ("Устное народное",),
]

cursor.executemany("INSERT INTO authors (name) VALUES (?)", authors)
connection.commit()

cursor.execute('''
               CREATE TABLE IF NOT EXISTS books
               (
                   id        INTEGER PRIMARY KEY AUTOINCREMENT,
                   name      TEXT NOT NULL,
                   year      INTEGER,
                   author_id INTEGER,
                   FOREIGN KEY (author_id) REFERENCES authors (id)
               )
               ''')

authors_from_db = cursor.execute("SELECT id, name FROM authors").fetchall()
authors = { name: id for id, name in authors_from_db }

books = [
    ("Алые паруса", 1922, authors["Грин"]),
    ("Апельсины", 1907, authors["Грин"]),
    ("Гарри Поттер", 1997, authors["Роулинг"]),
    ("Колобок", 1120, authors["Устное народное"]),
]

cursor.executemany("INSERT INTO books (name, year, author_id) VALUES (?, ?, ?)", books)
connection.commit()




# Фамилии авторов, книги которых выпущены после 1922 года
books_from_db = cursor.execute('''
        SELECT max(books.year) FROM books
            JOIN authors ON books.author_id = authors.id
            GROUP BY authors.name
                               ''').fetchall()
print(books_from_db)








cursor.execute("DELETE FROM books")
connection.commit()

cursor.execute("DELETE FROM authors")
connection.commit()
