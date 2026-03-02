# Произвольное число аргументов и именованных аргументов
# def sum(*args, **kwargs):
#     if 'flag' in kwargs:
#         print("Нашли флаг")
#     a = 0
#     for i in args:
#         a += i
#     return a
#
# print(sum(1, 2, 3, 4, flag=True))
#
# def main(*args, **kwargs):
#     pass
# Операторы упаковки и распаковки
# декораторы и пользовательские декораторы
# from curses import wrapper
#
#
# def func_decorator(func):
#     def wrapper(*args, **kwargs):
#         print("что-то до функции")
#         res = func(*args, **kwargs)
#         print("что-то после функции")
#         return res
#     return wrapper
#
# @func_decorator
# def some_func(title):
#     print(title)
#
# some_func('Привет')
# Декораторы с параметром (сохранение __name__ и __doc__)

# импорты math, time pprint (визуализация через locals()). Операторы from, as
# для чего пишут if __name__ == "__main__"
# import pprint
# from math import *
# pprint.pprint(locals())
#
# def main():
#     pass
#
# if __name__ == '__main__':
#     main()


# Установка внешних модулей:
# python -m venv .venv, pip list, pip install, pypi.org, pip freeze > requirements.txt, pip install -r requirements.txt

# пакеты: экспорт через __init__ и __all__ = []

# работа с файлами: open(file, mode, encoding), file.read(), каретка, file.seek(pos) - переместить, file.tell() - получить
# file.readline(), file.readlines(), file.close()
# повторить про исключения FileNotFoundException, try except finally, менеджер контекста with open()
# запись фалов ("w", "a") file.write(), file.writelines()
# бинарный режим доступа "wb", import pickle и pickle.dump(data, file) и pickle.load(file)