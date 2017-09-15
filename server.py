from flask import Flask, render_template, redirect, request, session, flash
from mysqlconnection import MySQLConnector
import re
import os, binascii
import md5
from datetime import datetime, timedelta
LETTER_REGEX = re.compile(r"^[a-zA-Z]+$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$")
app = Flask(__name__)
app.secret_key = "KeepItSecretKeepItSafe"
mysql = MySQLConnector(app,'the_wall_db')
@app.route("/")
def form():
    # redirect away from login/registration if already logged in
    if "id" in session:
        return redirect("/wall")
    else:
        return render_template("index.html")
@app.route("/log", methods=["POST"])
def log():
    # validation for login
    valid = True
    if len(request.form["email"]) < 1:
        flash("Email must not be blank!", "log")
        valid = False
    elif not EMAIL_REGEX.match(request.form["email"]):
        flash("Invalid email!", "log")
        valid = False
    if len(request.form["password"]) < 1:
        flash("Password must not be blank!", "log")
        valid = False
    if valid:
        # pw check
        query = "SELECT id, hashed_pw, salt FROM users WHERE email = :email"
        data = {"email": request.form["email"]}
        pw_info = mysql.query_db(query, data)
        if pw_info == []:
            flash("Email not registered!", "log")
            return redirect("/")
        elif md5.new(request.form["password"]+pw_info[0]["salt"]).hexdigest() == pw_info[0]["hashed_pw"]:
            session["id"]=pw_info[0]["id"]
            flash("Successfully logged in!")
            return redirect("/wall")
        else:
            flash("Email and password do not match!", "log")
    return redirect("/")
@app.route("/reg", methods=["POST"])
def reg():
    # validation for registration
    valid = True
    if len(request.form["first_name"]) < 1:
        flash("First name must not be blank!", "reg")
        valid = False
    elif len(request.form["first_name"]) < 2:
        flash("First name must be at least 2 letters!", "reg")
        valid = False
    elif not LETTER_REGEX.match(request.form["first_name"]):
        flash("First name must be letters only!", "reg")
        valid = False
    if len(request.form["last_name"]) < 1:
        flash("Last name cannot be blank!", "reg")
        valid = False
    elif len(request.form["last_name"]) < 2:
        flash("Last name must be at least 2 letters!", "reg")
        valid = False
    elif not LETTER_REGEX.match(request.form["last_name"]):
        flash("Last name must be letters only!", "reg")
        valid = False
    if len(request.form["email"]) < 1:
        flash("Email must not be blank!", "reg")
        valid = False
    elif not EMAIL_REGEX.match(request.form["email"]):
        flash("Invalid email!", "reg")
        valid = False
    else:
        query = "SELECT email FROM users WHERE email = :email"
        data = {"email":request.form["email"]}
        if mysql.query_db(query, data) != []:
            flash("An account with that email is already registered!", "reg")
            valid = False
    if len(request.form["password"]) < 1:
        flash("Password must not be blank!", "reg")
        valid = False
    elif len(request.form["password"])<8:
        flash("Password must be at least 8 characters!", "reg")
        valid = False
    if len(request.form["confirm_password"]) < 1:
        flash("Password confirmation cannot be blank!", "reg")
        valid = False
    elif request.form["password"] != request.form["confirm_password"]:
        flash("Password confirmation must match password!", "reg")
        valid = False
    if valid:
        # salted and hashed pw
        salt = binascii.b2a_hex(os.urandom(15))
        hashed_password = md5.new(request.form["password"] + salt).hexdigest()
        query = "INSERT INTO users (first_name, last_name, email, hashed_pw, salt, created_at, updated_at) VALUES (:first_name, :last_name, :email, :hashed_pw, :salt, NOW(), NOW())"
        data = {
            "first_name": request.form["first_name"],
            "last_name": request.form["last_name"],
            "email": request.form["email"],
            "hashed_pw": hashed_password,
            "salt": salt
        }
        session["id"] = mysql.query_db(query, data)
        flash("Successfully registered and logged in!")
        return redirect("/wall")
    else:
        return redirect("/")
@app.route("/wall")
def success():
    # get name of logged in user for welcome
    query = "SELECT first_name, last_name FROM users WHERE id = :id"
    data = {"id": session["id"]}
    namedic = mysql.query_db(query, data)
    name = namedic[0]["first_name"]+" "+namedic[0]["last_name"]
    # query for messages
    query = "SELECT users.id AS userid, CONCAT(users.first_name,' ',users.last_name) AS messager, messages.id as messageid, message, DATE_FORMAT(messages.created_at, '%M %D %Y %r') AS date FROM users JOIN messages ON users.id = messages.user_id ORDER BY messages.created_at DESC"
    posts = mysql.query_db(query)
    # query for comments
    query = "SELECT CONCAT(users.first_name,' ',users.last_name) AS commenter, comment, comments.message_id, DATE_FORMAT(comments.created_at, '%M %D %Y %r') AS date FROM users JOIN comments ON users.id = comments.user_id ORDER BY comments.created_at ASC"
    posts2 = mysql.query_db(query)
    return render_template("wall.html", user=name, all_messages=posts, all_comments=posts2)
@app.route("/logout", methods=["POST"])
def logout():
    session.pop("id")
    return redirect("/")
@app.route("/newmessage", methods=["POST"])
def newmessage():
    query = "INSERT INTO messages (user_id, message, created_at, updated_at) VALUES (:user_id, :message, NOW(), NOW())"
    data = {
        "user_id" : session["id"],
        "message" : request.form["message"]
    }
    mysql.query_db(query, data)
    return redirect("/wall")
@app.route("/newcomment/<mesid>", methods=["POST"])
def newcomment(mesid):
    query = "INSERT INTO comments (message_id, user_id, comment, created_at, updated_at) VALUES (:message_id, :user_id, :comment, NOW(), NOW())"
    data = {
        "message_id" : mesid,
        "user_id": session["id"],
        "comment" : request.form["comment"]
    }
    mysql.query_db(query, data)
    return redirect("/wall")
@app.route("/deletemessage/<mesid>", methods=["POST"])
def delete(mesid):
    # check id match is for some security, already made delete to not show for non-authors
    query = "SELECT user_id, created_at FROM messages WHERE id = :id"
    data = {"id":mesid}
    verify = mysql.query_db(query, data)
    if verify == []:
        flash("Invalid message")
    # 30 min limit
    elif datetime.today() > verify[0]["created_at"] + timedelta(minutes=30):
        flash("You cannot delete a message after 30 minutes have elapsed")
    elif verify[0]["user_id"] == session["id"]:
        query = "DELETE FROM messages WHERE id = :id"
        data = {"id":mesid}
        mysql.query_db(query, data)
    else:
        flash("That message is not yours")
    return redirect("/wall")
app.run(debug=True)