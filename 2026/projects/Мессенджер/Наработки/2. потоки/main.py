import threading
import logging

def worker():
    print('Я работаю в потоке')

t = threading.Thread(target=worker)
t.start()


lock = threading.Lock()

lock.acquire()
pass
lock.release()

with lock:
    pass
