import socket
import threading


def handle_client(client_socket, client_addr):
    print(f'Клиент {client_addr} подключился.')
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            client_socket.send(threading.active_count() - 1)
            client_socket.send(data.encode())
    except ConnectionResetError:
        print('Произошла ошибка с соединением.')
    finally:
        client_socket.close()


def main():
    HOST = '127.0.0.1'
    PORT = 12345

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))

    server_socket.listen(5)
    print(f'Эхо-сервер запущен на {HOST}:{PORT}')

    try:
        while True:
            client_socket, client_addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(client_socket, client_addr))

            thread.start()
    except KeyboardInterrupt:
        print('Получен сигнал остановки. Завершение работы...')
    finally:
        server_socket.close()


if __name__ == '__main__':
    main()
