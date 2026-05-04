import sqlite3

connection = sqlite3.connect('school.db')
cursor = connection.cursor()


class User:
    def __init__(self, name, age, email, password):
        self.name = name
        self.age = age
        self.email = email
        self.password = password



cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS users
    (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name     TEXT NOT NULL,
        email    TEXT,
        age      INTEGER,
        password TEXT NOT NULL
    )
    '''
)

cursor.execute('''INSERT INTO users (name, password) VALUES ("Саша", "1234")''')
cursor.execute('''INSERT INTO users (name, password) VALUES ("Илья", "4321")''')
cursor.execute('''INSERT INTO users (name, email, age, password) VALUES ("Администратор", "admin@example.com", 48, "admin")''')
connection.commit()

cursor.execute('''SELECT * FROM users''')
rows = cursor.fetchall()
for row in rows:
    print(row)

cursor.execute('''UPDATE users SET age = ? WHERE name = ?''', (22, "Илья"))
cursor.execute('''UPDATE users SET age = ? WHERE name = ?''', (13, "Саша"))
connection.commit()

cursor.execute('''DELETE FROM users''')
connection.commit()