import socket
import threading
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

active_clients = []
clients_lock = threading.Lock()
users = {}  # username -> socket
users_lock = threading.Lock()


def broadcast(message, exclude_socket=None):
    """Отправить сообщение всем, кроме exclude_socket."""
    with clients_lock:
        for client in active_clients:
            if client != exclude_socket:
                try:
                    client.send(message.encode('utf-8'))
                except Exception as e:
                    print(f"Не удалось отправить сообщение клиенту {e}")


def send_private_message(sender_name, target_name, message, sender_socket=None):
    """Отправить личное сообщение. Возвращает (success, response_message)."""
    with users_lock:
        target_socket = users.get(target_name)
        if not target_socket:
            return False, f"Пользователь {target_name} не найден или не в сети"
        try:
            formatted = f"[Личное от {sender_name}] {message}"
            target_socket.send(formatted.encode('utf-8'))
            return True, f"Сообщение для {target_name} отправлено"
        except:
            return False, f"Не удалось доставить сообщение {target_name}"


def handle_client(client_socket, client_address):
    username = None
    logging.info(f"Новое подключение: {client_address}")

    # Добавляем в список для broadcast
    with clients_lock:
        active_clients.append(client_socket)

    try:
        # Сначала просим представиться
        client_socket.send(b"Welcome! Please login: /login your_username\n")

        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            text = data.decode('utf-8').strip()
            if not text:
                continue

            # --- Обработка команд ---
            if text.startswith('/login'):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    client_socket.send(b'ERR: Usage: /login username\n')
                    continue
                new_name = parts[1]
                with users_lock:
                    if new_name in users:
                        client_socket.send(b'ERR: Username already taken\n')
                    else:
                        username = new_name
                        users[username] = client_socket
                        client_socket.send(f'OK: logged in as {username}\n'.encode())
                        broadcast(f"*** {username} присоединился к чату ***", exclude_socket=client_socket)
                        # Отправить новому пользователю список онлайн
                        online = ', '.join(users.keys())
                        client_socket.send(f"Online users: {online}\n".encode())
                continue

            if username is None:
                client_socket.send(b'ERR: You must login first using /login name\n')
                continue

            if text.startswith('/msg'):
                # Формат: /msg target message_text
                parts = text.split(maxsplit=2)
                if len(parts) < 3:
                    client_socket.send(b'ERR: Usage: /msg username message\n')
                    continue
                target = parts[1]
                message = parts[2]
                success, resp = send_private_message(username, target, message)
                client_socket.send(f"{'OK' if success else 'ERR'}: {resp}\n".encode())
                if success:
                    logging.info(f"Личное от {username} -> {target}: {message}")
                continue

            if text.startswith('/logout'):
                client_socket.send(b'OK: Goodbye!\n')
                break

            # Если не команда – отправляем всем (broadcast)
            broadcast_msg = f"[{username}] {text}"
            broadcast(broadcast_msg, exclude_socket=client_socket)
            logging.info(f"Broadcast от {username}: {text}")

    except ConnectionResetError:
        logging.warning(f"Клиент {client_address} оборвал соединение")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        # Удаление пользователя из структур
        with clients_lock:
            if client_socket in active_clients:
                active_clients.remove(client_socket)
        if username:
            with users_lock:
                if username in users and users[username] == client_socket:
                    del users[username]
            broadcast(f"*** {username} покинул чат ***")
        client_socket.close()
        logging.info(f"Клиент {client_address} отключился")


def main():
    HOST = '127.0.0.1'
    PORT = 12345

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    logging.info(f"Сервер личных сообщений запущен на {HOST}:{PORT}")

    try:
        while True:
            client_sock, client_addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(client_sock, client_addr))
            thread.start()
    except KeyboardInterrupt:
        logging.info("Сервер остановлен")
    finally:
        server.close()


if __name__ == "__main__":
    main()