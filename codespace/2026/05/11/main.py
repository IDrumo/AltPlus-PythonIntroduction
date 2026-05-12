# while условие:
#     тело_цикла


# print(1)
# print(2)
# ...
# print(8)
# print(9)
# print(10)

# TODO: счетчик
# i = 0
# while i < n:
#     i += 1
#     print(i)

# TODO: флаги
# flag = True
# i = 0
# while flag:
#     i += 3
#     if i == 252:
#         flag = False
#         print(i)


# n = 10
# print(f"n! = {s}")
# s = 0
# flag = True
# while flag:
#     n = int(input('Введите число: '))
#     if n == 0:
#         flag = False
#     s += n
#
# print(s)

import random

secret = random.randint(1, 100)
attempts = 0
print("Я загадал число от 1 до 100. Угадай!")

while True:
    guess = int(input("Ваша догадка: "))
    attempts += 1
    if guess < secret:
        print("Больше")
    elif guess > secret:
        print("Меньше")
    else:
        print(f"Поздравляю! Вы угадали за {attempts} попыток.")
        break