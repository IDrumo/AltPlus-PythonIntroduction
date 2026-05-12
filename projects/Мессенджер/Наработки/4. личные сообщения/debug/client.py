import socket
import sys
import threading


def receive_messenge(client_socket):
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                print(f"\nСоединение с сервером разорвано")
                break
            messenge = data.decode('utf-8').rstrip()
            print(f"\n[Новое сообщение] {messenge}")
            print("> ",end="",flush=True)
    except:
        print("Ошибка при получении сообщения")
    finally:
        client_socket.close()
        sys.exit(0)


def main():
    HOST = "127.0.0.1"
    PORT = 1234
    client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
 
    
    try:
        client_socket.connect((HOST,PORT))
        print(f"Подлючение к серверу {HOST}:{PORT}")
        print(f"Введите /login для регистрации")
    except :
        print("ERR: Не удалось подключиться к серверу")

    recv_thread = threading.Thread(target=receive_messenge,args=(client_socket,))
    recv_thread.daemon = True
    recv_thread.start()

    try:
        while True :
            messege = input("Введите сообщение:")
            if not messege:
                continue
            if messege.lower() == "/quit":
                client_socket.send(b"/logout")
                break
    
            client_socket.send(messege.encode("utf-8"))
    except KeyboardInterrupt:
        print("Завершение клиента")
        client_socket.send(b"/logout")
    finally:
        client_socket.close()
        print("Клиент завершил работу")



if __name__ == "__main__":
    main()