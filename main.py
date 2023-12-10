from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit, join_room, leave_room, send
import random
import requests
import os
from openai import OpenAI
client = OpenAI(api_key='sk-') #輸入你的API_KEY

from string import ascii_uppercase

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"
socketio = SocketIO(app)

# OpenAI GPT API 設置

rooms = {}

def generate_unique_code(length):
    code = "".join(random.choices(ascii_uppercase, k=length))
    if code in rooms:
        generate_unique_code(length)
    else:
        return code


@app.route("/", methods=["GET", "POST"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if code == "GPT4":
            session["name"] = name
            return redirect(url_for("gpt_room"))

        if join != False and not code:
            flash("Please enter a room code.")
            return render_template("home.html", code=code, name=name)
    
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            flash("Room does not exist.")
            return render_template("home.html", code=code, name=name)
        
        session["room"] = room  
        session["name"] = name

        return redirect(url_for("room"))


    return render_template("home.html")

@app.route('/gpt_room')
def gpt_room():
    name = session.get("name")
    if session.get("name") is None:
        return redirect(url_for("home"))
    
    return render_template('gpt_room.html', name=name)

@socketio.on('send_message', namespace='/gpt_room')
def handle_message(message):
    response = call_gpt_api(message)
    emit('receive_message', {'text': response}, room=request.sid)

def call_gpt_api(message):
    complete_response = ""
    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": f"{message}"}],
        stream=True,
        max_tokens=150,
        temperature=0.9,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.6,
    )
    try:
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                complete_response += chunk.choices[0].delta.content
        return complete_response
    except Exception as e:
        return f"錯誤: {str(e)}"

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code = room, messages=rooms[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    
    content = {
        "name": session["name"],
        "message": data["data"]
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{session['name']}: {data['data']}")


@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if room is None or name is None:
        return 
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name":name, "message": "has joined the room."}, to=room)
    print(f"{name} has joined the room.")
    rooms[room]["members"] += 1
    emit("joined", {"name": session["name"], "room": room}, room=room)

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({"name":name, "message": "has left the room."}, to=room)
    print(f"{name} has left the room.")



if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)