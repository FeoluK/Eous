import requests
ip = "10.16.146.164"
url = f"http://{ip}:5000/send"
resp = requests.post(url, json={"msg": "Hello"})
print(resp.text)