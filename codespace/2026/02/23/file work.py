import pickle

user = {
    'hp': 90,
    'damage': 50,
    'ability': ['fly', 'jump']
}

try:
    with open("input.txt", 'wb+') as file:
        pickle.dump(user, file)
        user = pickle.load(file)
        print(user)
        print(type(user))
        print(user['hp'])

except FileNotFoundError:
    print("Не удалось открыть файл")