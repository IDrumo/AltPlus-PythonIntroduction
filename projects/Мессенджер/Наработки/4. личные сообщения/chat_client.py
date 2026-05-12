import socket
import threading
import sys

def receive_messages(client_socket):
    """Поток для получения сообщений от сервера."""
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                print("\nСоединение с сервером разорвано.")
                break
            message = data.decode('utf-8').rstrip()
            # Выводим сообщение, не мешая вводу
            print(f"\n{message}")
            print("> ", end="", flush=True)
    except:
        print("\nОшибка приёма.")
    finally:
        client_socket.close()
        sys.exit(0)

def main():
    HOST = '127.0.0.1'
    PORT = 12345

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((HOST, PORT))
        print("Подключено к серверу. Введите /login ваше_имя")
    except:
        print("Не удалось подключиться к серверу")
        return

    # Запускаем поток приёма
    recv_thread = threading.Thread(target=receive_messages, args=(client,))
    recv_thread.daemon = True
    recv_thread.start()

    # Главный поток для отправки
    try:
        while True:
            msg = input("> ")
            if not msg:
                continue
            if msg.lower() == '/quit':
                client.send(b'/logout')
                break
            client.send(msg.encode('utf-8'))
    except KeyboardInterrupt:
        print("\nЗавершение клиента...")
        client.send(b'/logout')
    finally:
        client.close()

if __name__ == "__main__":
    main()