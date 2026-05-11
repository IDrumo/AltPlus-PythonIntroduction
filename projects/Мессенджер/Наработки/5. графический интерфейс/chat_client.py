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
            message = data.decode('utf-8')
            # Выводим сообщение, аккуратно вставляя его в консоль
            print(f"\n[Новое сообщение] {message}")
            print("> ", end="", flush=True)   # повторяем приглашение ввода
    except:
        print("Ошибка при получении сообщения.")
    finally:
        client_socket.close()
        sys.exit(0)

def main():
    HOST = '127.0.0.1'
    PORT = 12345

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((HOST, PORT))
        print(f"Подключено к чат-серверу {HOST}:{PORT}")
    except:
        print("Не удалось подключиться к серверу")
        return

    # Запускаем поток для приёма сообщений
    recv_thread = threading.Thread(target=receive_messages, args=(client,))
    recv_thread.daemon = True   # поток завершится при выходе из main
    recv_thread.start()

    # Главный поток занимается отправкой
    try:
        while True:
            message = input("> ")
            if not message:
                continue
            if message.lower() == '/quit':
                break
            client.send(message.encode('utf-8'))
    except KeyboardInterrupt:
        print("\nЗавершение клиента...")
    finally:
        client.close()

if __name__ == "__main__":
    main()