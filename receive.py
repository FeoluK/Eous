
from flask import Flask, request

app = Flask(__name__)


@app.route("/command", methods=["GET", "POST"])
def receive():
    if request.method == "POST":
        data = request.json
        print("Received:", data)
        return {"status": "ok"}
    else:
        # Simple response so you can test in a browser with a GET request
        return "Not Moving", 200


app.run(host="0.0.0.0", port=5000)