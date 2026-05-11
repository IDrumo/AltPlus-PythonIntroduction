import socket
import threading
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

active_clients = []  # список сокетов активных клиентов
clients_lock = threading.Lock()
users = {}
users_lock = threading.Lock()


def send_private_message(sender_name, target_name, message):
    with clients_lock:
        target_socket = users[target_name]
        if not target_socket:
            return False, f"Пользователь {target_name} не найден"
        try:
            target_socket.send(f"Личное от {sender_name}: {message}".encode('utf-8'))
            return True, "Отправлено"
        except:
            return False, 'Не удалось доставить сообщение'



def broadcast(message, sender_socket=None):
    """Отправить сообщение всем подключённым клиентам, кроме отправителя."""
    with clients_lock:
        for client in active_clients:
            if client != sender_socket:
                try:
                    client.send(message.encode('utf-8'))
                except Exception as e:
                    logging.error(f"Не удалось отправить сообщение клиенту: {e}")
                    # Не удаляем здесь, чтобы не менять список во время итерации


def remove_dead_clients():
    """Удалить клиентов, у которых соединение закрыто."""
    with clients_lock:
        dead = []
        for client in active_clients:
            try:
                # Отправляем пустое сообщение как проверку соединения
                client.send(b'')
            except:
                dead.append(client)
        for d in dead:
            active_clients.remove(d)
            logging.info(f"Клиент удалён из списка (недоступен)")


def handle_client(client_socket, client_address):
    username = None
    logging.info(f"Новый клиент: {client_address}")
    # Добавляем клиента в список
    with clients_lock:
        active_clients.append(client_socket)

    try:
        client_socket.send('Сначала авторизуйтесь (/login)')

        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            text = data.decode('utf-8').strip()
            if not text:
                continue
            #===================Блок обработки команд===========================
            if text.startswith('/login'):
                parts = text.split()
                if len(parts) == 2:
                    new_name = parts[1]
                    with clients_lock:
                        if new_name in users:
                            client_socket.send(f"ERR: Пользователь {new_name} уже авторизован".encode('utf-8'))
                        else:
                            username = new_name
                            users[username] = client_socket
                            client_socket.send(f"OK: Авторизация успешна".encode('utf-8'))
                            broadcast(f"{username} вошел в сеть.")
                            online = ', '.join(active_clients)
                            client_socket.send(f"Пользователи онлайн: {online}".encode('utf-8'))
                continue

            if not username:
                client_socket.send(f"Сначала авторизуйтесь.".encode('utf-8'))
                continue

            if text.startswith('/msg'):
                # /msg target_name message
                parts = text.split()
                target = parts[1]
                message = parts[2]
                success, response = send_private_message(username, target, message)
                status = 'OK' if success else 'ERR'
                client_socket.send(status.encode('utf-8'))
                continue

            if text.startswith('/logout'):
                break

            broadcast(text, sender_socket=client_socket)
    except ConnectionResetError:
        logging.warning(f"Клиент {client_address} оборвал соединение")
    except Exception as e:
        logging.error(f"Ошибка при обработке {client_address}: {e}")
    finally:
        # Удаляем клиента из списка
        with clients_lock:
            if client_socket in active_clients:
                active_clients.remove(client_socket)
        if username:
            with users_lock:
                if username in users and users[username] == client_socket:
                    del users[username]
            broadcast(f"Пользователь {username} покинул чат.")
        client_socket.close()
        logging.info(f"Клиент {client_address} отключился")


def main():
    HOST = '127.0.0.1'
    PORT = 12345

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    logging.info(f"Чат-сервер запущен на {HOST}:{PORT}")

    try:
        while True:
            client_sock, client_addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(client_sock, client_addr))
            thread.start()
    except KeyboardInterrupt:
        logging.info("Сервер остановлен вручную")
    finally:
        server.close()


if __name__ == "__main__":
    main()