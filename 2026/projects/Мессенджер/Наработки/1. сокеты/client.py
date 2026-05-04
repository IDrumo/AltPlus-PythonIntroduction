import socket

def main():
    HOST = '127.0.0.1'
    PORT = 12345

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    client_socket.connect((HOST, PORT))
    print(f'Подключение к серверу {HOST}:{PORT}')

    while True:
        message = input('Введите сообщение: ')

        if message.lower() == 'stop':
            break

        client_socket.send(message.encode('utf-8'))
        response = client_socket.recv(1024)
        print(f'Ответ сервера: {response.decode("utf-8")}')

    client_socket.close()
    print(f'Клиент завершил работу')


if __name__ == '__main__':
    main()