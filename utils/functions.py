import json
import requests

server_url = 'https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json'
rate_url = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"

def find_server(find):
    resp = requests.get(server_url)
    found = False
    if resp.status_code == 200:
        data = resp.json()
        for server in data:
            if 'SessionName' in server:
                if find.lower() in server['SessionName'].lower():
                    found = True
                    return (
                        f"**Server is online!**\n{server['SessionName']}\n"
                        f"**IP Address:**  {server['IP']}\n"
                        f"**Day:**  {server['DayTime']}\n"
                        f"**Players Online:**  {server['NumPlayers']}\n"
                        f"**Ping:** {server['ServerPing']}\n"
                    )
    if not found:
        return "I couldn't find the Server, probably it's offline."
    else:
        return "I couldn't find the Server, probably it's offline."

def add_server_channel(server_id: str, channel_id: str, role: str):
    try:
        with open("rate-notification-channels.json", "r") as file:
            data = json.load(file)
            for entry in data:
                if entry["server_id"] == server_id:
                    entry["server_id"] = server_id
                    entry["channel_id"] = channel_id
                    entry["role"] = role
                    break
            else:
                entry = {"server_id": server_id, "channel_id": channel_id, "role": role}
                data.append(entry)
    except FileNotFoundError:
        data = [{"server_id": server_id, "channel_id": channel_id, "role": role}]
    
    with open("rate-notification-channels.json", "w") as file:
        json.dump(data, file)

last = None

def sfile():
    last = requests.get(rate_url)
    lines = last.text.strip().splitlines()
    with open("previous-rates.text", "w") as file:
        for line in lines:
            file.writelines(line + "\n")

data = None

def loop():
    global last, data
    current_data = requests.get(rate_url)
    new = current_data.text + '\n'
    lines = current_data.text.strip().splitlines()
    with open("previous-rates.text", "r") as file1:
        last = str(file1.read())
    with open("current-rates.text", "w") as file2:
        for line1 in lines:
            file2.write(line1 + "\n")
    with open("current-rates.text", "r") as file3:
        newfile = str(file3.read())
    
    if last != newfile:
        with open("rate-notification-channels.json", "r") as file:
            data = json.load(file)
        lines = current_data.text.strip().splitlines()
        with open("previous-rates.text", "w") as file:
            for line in lines:
                file.write(line + "\n")
        return data, new, 0
    return None, None, 1