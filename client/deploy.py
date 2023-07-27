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

import argparse, subprocess, json
import websocket, hashlib, os

DEVNULL = open("/dev/null", "w")

class Client:
    def __init__(self, password:str = ""):
        self.password = password

    def run(self):
        self.parse_args()
        self.run_command()
        self.connectWebsocket()

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Client for git-notify")
        parser.add_argument("-s", "--server", type=str, help="Server URL", required=True)
        parser.add_argument("-p", "--password", type=str, help="Password", required=False, default="")
        parser.add_argument("-r", "--repo", type=str, help="GitHub Repository", required=True)
        parser.add_argument("-b", "--branch", type=str, help="Branch name", required=False, default="main")
        parser.add_argument("-c", "--command", type=str, help="Command to run", required=True)

        args = parser.parse_args()
        self.server = args.server
        self.branch = args.branch
        self.password = args.password
        self.repo = args.repo
        self.command = args.command

    def run_command(self):
        self.process = subprocess.Popen(self.command, shell=True)

    def stop_command(self):
        self.process.terminate()

    def restart_command(self):
        self.stop_command()
        self.run_command()

    def connectWebsocket(self):
        self.ws = websocket.WebSocketApp(self.server,
            on_message = self.on_message)
        self.ws.run_forever(reconnect=1)

    def on_message(self, ws, message):
        recvData = json.loads(message)
        command = recvData["command"]
        if command == "new_client":
            ws.send(json.dumps({
                "command": "register",
                "data": {
                    "repo": self.repo,
                    "hash": self.genHash(self.repo, self.password)
                }
            }))
        elif command == "register":
            if recvData["status"] == "error":
                print("Failed to register: %s" % recvData["data"]["message"])
                exit(1)
        elif command == "pull_request_closed":
            if recvData["data"]["repo"] != self.repo or recvData["data"]["pull_request"]["base"]["ref"] != self.branch:
                return
            self.restart_command()

    def genHash(self, repo: str, password: str) -> str:
        return hashlib.sha256(("%s:%s" % (repo, password)).encode()).hexdigest()

if __name__ == "__main__":
    password = ""
    if "GIT_NOTIFY_PASSWORD" in os.environ:
        password = os.environ["GIT_NOTIFY_PASSWORD"]
    client = Client(password)
    client.run()