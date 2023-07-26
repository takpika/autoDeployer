from websocket_server import WebsocketServer
import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from time import sleep

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, parent):
        self.parent = parent
        super().__init__(server_address, RequestHandlerClass)

class Server:
    def __init__(self, websocket_port, http_port):
        self.websocket_port = websocket_port
        self.http_port = http_port
        self.websocket_server = WebsocketServer(host='127.0.0.1', port=websocket_port)
        self.websocket_server.set_fn_new_client(self.new_client)
        self.websocket_server.set_fn_client_left(self.client_left)
        self.websocket_server.set_fn_message_received(self.message_received)
        self.websocket_server_thread = threading.Thread(target=self.websocket_server.run_forever)
        self.websocket_server_thread.daemon = True
        self.websocket_server_thread.start()
        self.http_server = ThreadedHTTPServer(('127.0.0.1', http_port), self.HTTPRequestHandler, self)
        self.http_server_thread = threading.Thread(target=self.http_server.serve_forever)
        self.http_server_thread.daemon = True
        self.http_server_thread.start()
        self.clients: dict[str, dict] = {}

    def isClientRegistered(self, clientID: str):
        return clientID in self.clients
    
    def getRepoClient(self, repoURL: str) -> list:
        return [client for client in self.clients.values() if client["repo"] == repoURL]

    def new_client(self, client, server):
        server.send_message(client, json.dumps({
            "status": "ok",
            "command": "new_client",
            "data": {}
        }))

    def client_left(self, client, server):
        if self.isClientRegistered(client["id"]):
            self.clients.pop(client["id"])

    def message_received(self, client, server, message):
        recvData = json.loads(message)
        command = recvData["command"]
        if command == "register":
            repoURL = recvData["data"]["repo"]
            self.clients[client["id"]] = {
                "client": client,
                "repo": repoURL
            }
            server.send_message(client, json.dumps({
                "status": "ok",
                "command": "register",
                "data": {}
            }))
        else:
            print("Unknown command: %s" % command)
            server.send_message(client, json.dumps({
                "status": "error",
                "command": command,
                "data": {
                    "message": "Unknown command"
                }
            }))

    class HTTPRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            contentSize = self.headers.get('Content-Length')
            if contentSize is None:
                contentSize = 0
            else:
                contentSize = int(contentSize)
            content = self.rfile.read(contentSize)
            webhookData = json.loads(content)
            if "zen" in webhookData:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"pong")
                return
            if "action" not in webhookData:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if webhookData["action"] != "closed":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            repoURL = webhookData["repository"]["html_url"]
            clients = self.server.parent.getRepoClient(repoURL)
            for client in clients:
                self.server.parent.websocket_server.send_message(client["client"], json.dumps({
                    "status": "ok",
                    "command": "pull_request_closed",
                    "data": {
                        "repo": repoURL,
                        "pull_request": webhookData["pull_request"]
                    }
                }))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

if __name__ == "__main__":
    server = Server(9001, 9002)
    while True:
        sleep(60)
        pass

