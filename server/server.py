#!/usr/bin/env python3
# MIT License
# 
# Copyright (c) 2023 takpika
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from websocket_server import WebsocketServer
import json, threading, hashlib, os, hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from time import sleep

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, parent):
        self.parent = parent
        super().__init__(server_address, RequestHandlerClass)

class Server:
    def __init__(self, websocket_port, http_port, password:str = ""):
        self.password = password
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
        sendData = {
            "status": "error",
            "command": command,
            "data": {}
        }
        if command == "register":
            repo = recvData["data"]["repo"]
            hash = recvData["data"]["hash"]
            if self.genHash(repo, self.password) == hash:
                self.clients[client["id"]] = {
                    "client": client,
                    "repo": repo
                }
                sendData["status"] = "ok"
            else:
                sendData["data"]["message"] = "Invalid password"
        else:
            print("Unknown command: %s" % command)
            sendData["data"]["message"] = "Unknown command"
        server.send_message(client, json.dumps(sendData))

    def genHash(self, repo: str, password: str) -> str:
        return hashlib.sha256(("%s:%s" % (repo, password)).encode()).hexdigest()

    class HTTPRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            headers = self.headers
            if "X-Hub-Signature-256" not in headers:
                self.responseError("\"X-Hub-Signature-256\" not found in headers", 400)
                return
            if "Content-Length" not in headers:
                self.responseError("\"Content-Length\" not found in headers", 411)
                return
            signature = headers["X-Hub-Signature-256"].replace("sha256=", "")
            contentSize = int(self.headers.get('Content-Length'))
            content = self.rfile.read(contentSize)
            webhookData = json.loads(content)
            if not "repository" in webhookData:
                self.responseError("No Repository data", 404)
                return
            repo = webhookData["repository"]["full_name"]
            password = self.server.parent.genHash(repo, self.server.parent.password)
            signatureHash = hmac.new(password.encode(), content, hashlib.sha256).hexdigest()
            if signatureHash != signature:
                self.responseError("Signature Error", 401)
                return
            if "zen" in webhookData:
                self.responseOK()
            if self.handleRequest(webhookData):
                self.responseOK()
            else:
                self.responseError("Something went wrong while handling data", 406)

        def handleRequest(self, webhookData: dict) -> bool:
            if "action" not in webhookData:
                return False
            if webhookData["action"] != "closed" or "pull_request" not in webhookData:
                return False
            if webhookData["pull_request"]["merged"] == True:
                repo = webhookData["repository"]["full_name"]
                clients = self.server.parent.getRepoClient(repo)
                for client in clients:
                    self.server.parent.websocket_server.send_message(client["client"], json.dumps({
                        "status": "ok",
                        "command": "pull_request_closed",
                        "data": {
                            "repo": repo,
                            "pull_request": webhookData["pull_request"]
                        }
                    }))
                return True
            return False

        def responseOK(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({}).encode())

        def responseError(self, message: str, statusCode: int = 400):
            self.send_response(statusCode)
            self.end_headers()
            self.wfile.write(json.dumps({"message": message}).encode())

if __name__ == "__main__":
    password = ""
    if "GIT_NOTIFY_PASSWORD" in os.environ:
        password = os.environ["GIT_NOTIFY_PASSWORD"]
    server = Server(9001, 9002, password)
    while True:
        sleep(60)
        pass

