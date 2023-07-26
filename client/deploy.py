import argparse, subprocess, json
import websocket

DEVNULL = open("/dev/null", "w")

class Client:
    def __init__(self):
        pass

    def run(self):
        self.parse_args()
        self.run_command()
        self.connectWebsocket()

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Client for git-notify")
        parser.add_argument("-s", "--server", type=str, help="Server URL", required=True)
        parser.add_argument("-r", "--repo", type=str, help="GitHub Repository", required=True)
        parser.add_argument("-b", "--branch", type=str, help="Branch name", required=True)
        parser.add_argument("-c", "--command", type=str, help="Command to run", required=True)

        args = parser.parse_args()
        self.server = args.server
        self.repo = args.repo
        self.command = args.command

    def run_command(self):
        subprocess.run(["git", "pull"], stdout=DEVNULL, stderr=DEVNULL)
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
                    "repo": self.repo
                }
            }))
        elif command == "pull_request_closed":
            if recvData["data"]["repo"] != self.repo or recvData["data"]["pull_request"]["base"]["ref"] != self.branch:
                return
            self.restart_command()

if __name__ == "__main__":
    client = Client()
    client.run()