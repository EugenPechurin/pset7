from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    rows = db.execute("SELECT * FROM portfolio WHERE user_id = :id", id=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    positions = []
    all_cash = 0
    for row in rows:
        stock = lookup(row['symbol'])
        positions.append({"symbol": row['symbol'], "name": stock['name'], "shares": row['shares'], "price": stock['price'], "id": row['id'] })
        all_cash = all_cash + stock['price'] * row['shares']
    if request.method == "POST":
        return redirect("/sell")
    return render_template("index.html", positions = positions, cash = cash[0]['cash'], all_cash = all_cash)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        
        if not request.form.get("symbol"):
            flash('missing symbol')
            return render_template("buy.html")
        stock = lookup(request.form.get("symbol"))
        
        if not stock:
            flash('invalid symbol')
            return render_template("buy.html")
        if not request.form.get("shares"):
            flash('missing shares')
            return render_template("buy.html")
        
        try:
            if int(request.form.get("shares")) < 0:
                flash('invalid shares')
                return render_template("buy.html")
        except ValueError:
            flash('invalid shares')
            return render_template("buy.html")
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        if stock['price'] * float(request.form.get("shares")) > rows[0]['cash']:
            return apology("missing cash")
        q = db.execute("UPDATE portfolio SET shares = shares + :shares WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=request.form.get("symbol").upper(), shares=request.form.get("shares"))
        if q:
            db.execute("INSERT INTO history (symbol, shares, price, user_id, 'transaction') VALUES(:symbol, :shares, :price, :user_id, 'BUY')",symbol=request.form.get("symbol").upper(), shares=request.form.get("shares"), price=stock['price'], user_id=session["user_id"])
            db.execute("UPDATE users SET cash = cash - :coast WHERE id = :user_id", coast=int(request.form.get("shares")) * stock['price'], user_id=session["user_id"])
            
        if q == 0:
            db.execute("INSERT INTO history (symbol, shares, price, user_id, 'transaction') VALUES(:symbol, :shares, :price, :user_id, 'BUY')",symbol=request.form.get("symbol").upper(), shares=request.form.get("shares"), price=stock['price'], user_id=session["user_id"])
            db.execute("INSERT INTO portfolio (user_id, symbol, shares) VALUES(:user_id, :symbol, :shares)", user_id=session["user_id"], symbol=request.form.get("symbol").upper(), shares=request.form.get("shares"))
            db.execute("UPDATE users SET cash = cash - :coast WHERE id = :user_id", coast=int(request.form.get("shares")) * stock['price'], user_id=session["user_id"])
        flash('Done!')
        return redirect("/")

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    rows = db.execute("SELECT * FROM history WHERE user_id = :id", id=session["user_id"])
    positions = []
    for row in rows:
        positions.append({"symbol": row['symbol'], "shares": row['shares'], "price": float(row['price']), "total": int(row['shares']) * float(row['price']), "date": row['date'], "transaction": row['transaction'] })
        
    return render_template("history.html", positions = positions)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash('must provide username')
            return render_template("login.html", username=request.form.get("username"))

        # ensure password was submitted
        elif not request.form.get("password"):
            flash('must provide password')
            return render_template("login.html", username=request.form.get("username"))

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            flash('invalid username and/or password')
            return render_template("login.html", username=request.form.get("username"))

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["user"] = request.form.get("username")

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        
        if not request.form.get("symbol"):
            return apology("you must provide a symbol")
            
        quote = lookup(request.form.get("symbol"))
        
        if not quote:
            return apology("symbol not found")
            
        return render_template("quoted.html", name=quote["name"], symbol=quote["symbol"], quote = quote["price"])

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":

        if not request.form.get("username"):
            flash('must provide username')
            return render_template("register.html")
        # ensure password was submitted
        elif not request.form.get("password"):
            flash('must provide password')
            return render_template("register.html", username=request.form.get("username"))
        # ensure confirm password was submitted
        elif not request.form.get("confirmation"):
            flash('must provide confirm password')
            return render_template("register.html", username=request.form.get("username"))
        elif request.form.get("password") != request.form.get("confirmation"):
            flash('passwords do not match')
            return render_template("register.html", username=request.form.get("username"))
        # query database for username
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=pwd_context.hash(request.form.get("password")))
        
        # ensure username exists and password is correct
        if not result:
            flash('this user already exists')
            return render_template("register.html", username=request.form.get("username"))
        # remember which user has logged in
        session["user_id"] = result
        session["user"] = request.form.get("username")
        
        flash('registration completed')
        return render_template("ш.html", username=request.form.get("username"))
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        symbols = db.execute("SELECT symbol FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])
        #return apology_texts(request.form)
        if request.form.get("id"):
            symbol = db.execute("SELECT * FROM portfolio WHERE id = :id", id=int(request.form.get("id")))
            return render_template("sell.html", symbols = symbols, symbol=symbol[0]["symbol"], shares=symbol[0]["shares"])
        if not request.form.get("symbol"):
            return apology("missing symbol")
            
        stock = lookup(request.form.get("symbol"))
        
        if not stock:
            return apology("invalid symbol")
            
        if not request.form.get("shares"):
            return apology("missing shares")
            
        symbol = db.execute("SELECT * FROM portfolio WHERE symbol = :symbol", symbol=request.form.get("symbol"))
        
        if not request.form.get("shares").isdigit:
            flash('invalid shares')
            return render_template("sell.html", symbol=request.form.get("symbol"), symbols = symbols)
        try:
            if int(request.form.get("shares")) > symbol[0]["shares"]:
                flash('invalid shares')
                return render_template("sell.html", symbol=request.form.get("symbol"), symbols = symbols)
        except ValueError:
            flash('invalid shares')
            return render_template("sell.html", symbol=request.form.get("symbol"), symbols = symbols)
        try:
            if int(request.form.get("shares")) < 0:
                flash('invalid shares')
                return render_template("sell.html", symbol=request.form.get("symbol"), symbols = symbols)
        except ValueError:
            flash('invalid shares')
            return render_template("sell.html", symbol=request.form.get("symbol"), symbols = symbols)
        if int(request.form.get("shares")) == symbol[0]["shares"]:
            db.execute("INSERT INTO history (symbol, shares, price, user_id, 'transaction') VALUES(:symbol, :shares, :price, :user_id, 'SELL')",symbol=request.form.get("symbol").upper(), shares=request.form.get("shares"), price=stock['price'], user_id=session["user_id"])
            db.execute("UPDATE users SET cash = cash + :coast WHERE id = :user_id", coast=int(request.form.get("shares")) * stock['price'], user_id=session["user_id"])
            db.execute("DELETE FROM portfolio WHERE user_id = :user_id AND symbol = :symbol",user_id=session["user_id"], symbol=request.form.get("symbol"))
        else:
            db.execute("INSERT INTO history (symbol, shares, price, user_id, 'transaction') VALUES(:symbol, :shares, :price, :user_id, 'SELL')",symbol=request.form.get("symbol").upper(), shares=request.form.get("shares"), price=stock['price'], user_id=session["user_id"])
            db.execute("UPDATE users SET cash = cash + :coast WHERE id = :user_id", coast=int(request.form.get("shares")) * stock['price'], user_id=session["user_id"])
            db.execute("UPDATE portfolio SET shares = shares - :shares WHERE user_id = :user_id AND symbol = :symbol", shares=int(request.form.get("shares")), user_id=session["user_id"], symbol=request.form.get("symbol"))
        flash('Done!')
        return redirect("/")
    else:
        symbols = db.execute("SELECT symbol FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])
        return render_template("sell.html", symbols=symbols)
        
@app.route("/user", methods=["GET", "POST"])
@login_required
def usermenu():
    return render_template("user.html")
    
@app.route("/new_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        
        
        if not request.form.get("password"):
            flash('must provide password')
            return render_template("change_password.html", username=request.form.get("username"))
        elif not request.form.get("new_password"):
            flash('must provide new password')
            return render_template("change_password.html", username=request.form.get("username"))
        # ensure confirm password was submitted
        elif not request.form.get("confirmation"):
            flash('must provide confirm password')
            return render_template("change_password.html", username=request.form.get("username"))
        elif request.form.get("new_password") != request.form.get("confirmation"):
            flash('passwords do not match')
            return render_template("change_password.html", username=request.form.get("username"))
            
        rows = db.execute("SELECT hash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            flash('invalid username and/or password')
            return render_template("login.html", username=request.form.get("username"))
            
        db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", user_id=session["user_id"], hash=pwd_context.hash(request.form.get("new_password")))
        
        flash('Done!')
        return redirect("/")
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("change_password.html")
    
@app.route("/new_username", methods=["GET", "POST"])
@login_required
def change_username():
    if request.method == "POST":
        
        if not request.form.get("username"):
            flash('must provide new username')
            return render_template("register.html")
    
        result = db.execute("UPDATE users SET username = :username WHERE id = :user_id", user_id=session["user_id"], username=request.form.get("username"))
        
        if not result:
            flash('this user already exists')
            return render_template("change_username.html")
        
        session["user"] = request.form.get("username")
        flash('Done!')
        return redirect("/")
    else:
        return render_template("change_username.html")