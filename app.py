from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_migrate import Migrate
import stripe
from flask_cors import CORS
from models import db  # Import the db from model.py
from chatbot import get_chatbot_response
from twilio.rest import Client
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY')
app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')

# Initialize the app with the db
db.init_app(app)
migrate = Migrate(app, db)

babel = Babel(app)
CORS(app)

stripe.api_key = app.config['STRIPE_SECRET_KEY']

# Twilio Credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def get_locale():
    return session.get('locale', 'en')

babel.init_app(app, locale_selector=get_locale)

@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale)


@app.route('/set_locale/<locale>')
def set_locale(locale):
    session['locale'] = locale
    return redirect(request.referrer)

@app.route('/test_locale')
def test_locale():
    return f"Current locale: {get_locale()}"

@app.route('/logout')
def logout():
    # Logic to log out the user, e.g., clearing the session
    session.clear()
    return redirect(url_for('login'))  # Redirect to the login page or homepage

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/view')
def view():
    return render_template('view.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Process form data
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        # Here you can handle the form data, e.g., send an email, save to a database, etc.
        
        return "Thank you for your message!"  # Or redirect to a 'thank you' page
    return render_template('contact.html')



@app.route('/')
def home():
    return render_template('home.html')

# Generate OTP
def generate_otp():
    return str(random.randint(100000, 999999))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        mobile = request.form['mobile']

        if not mobile.startswith("+"):
            mobile = f"+91{mobile}"
            
        # Generate and store OTP
        otp = generate_otp()
        session['otp'] = otp
        session['username'] = username
        session['password'] = password
        session['mobile'] = mobile

        # Send OTP via Twilio
        try:
            client.messages.create(
                body=f"Your OTP is {otp}",
                from_="+15075744362",
                to="+91 84012 13311"
            )
            flash("OTP sent to your mobile number.", "info")
            return redirect(url_for('verify_otp'))
        except Exception as e:
            flash(f"Error sending OTP: {e}", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    from models import User
    if request.method == 'POST':
        user_otp = request.form['otp']
        if user_otp == session.get('otp'):
            # OTP verified, create user
            new_user = User(username=session['username'], password=session['password'], mobile=session['mobile'])
            new_user.set_password(session['password'])  # Hash the password before storing
            db.session.add(new_user)
            db.session.commit()

            # Clear session data
            session.pop('otp', None)
            session.pop('username', None)
            session.pop('password', None)
            session.pop('mobile', None)

            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP. Please try again.", "danger")

    return render_template('verify_otp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        from models import User  # Import User model
        
        # Get username and password from form input
        username = request.form['username']
        password = request.form['password']
        
        # Query database for user with the given username
        user = User.query.filter_by(username=username).first()

        # Check if user exists and if the provided password is correct
        # if user and user.check_password(password):  # Verify hashed password
        #     session['user_id'] = user.id  # Store user ID in session
        #     return redirect(url_for('book_ticket'))  # Redirect to booking page
        # else:
        #     flash("Invalid username or password.", "danger")  # Show error message

    return render_template('login.html')  # Render login page if request is GET
   

@app.route('/book_ticket', methods=['GET', 'POST'])
def book_ticket():
    if request.method == 'POST':
        group_size = request.form.get('group_size')
        if not group_size or int(group_size) < 1:
            flash("⚠️ Please enter a valid number of visitors.", "danger")
            return redirect(url_for('book_ticket'))

        # Generate a dummy ticket_id (replace with database logic)
        ticket_id = random.randint(1000, 9999)  # Example: Generate a random ticket ID

        flash("✅ Ticket booked successfully!", "success")
        return redirect(url_for('payment', ticket_id=ticket_id))  # Pass ticket_id

    return render_template('book_ticket.html')

@app.route('/my_tickets')
def my_tickets():
    from models import Ticket
    user_id = session['user_id']
    tickets = Ticket.query.filter_by(user_id=user_id).all()
    return render_template('my_tickets.html', tickets=tickets)

@app.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    from models import Ticket
    Ticket.query.filter_by(id=ticket_id).delete()
    db.session.commit()
    return redirect(url_for('my_tickets'))

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        try:
            stripe.PaymentIntent.create(
                amount=1000,
                currency='usd',
                payment_method=request.form['payment_method_id'],
                confirmation_method='manual',
                confirm=True
            )
            return "Payment successful!"
        except Exception as e:
            return f"An error occurred: {str(e)}", 400
    return render_template('payment.html', stripe_public_key=app.config['STRIPE_PUBLIC_KEY'])


@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if request.method == 'POST':
        data = request.get_json()
        user_message = data.get('message')
        bot_response = get_chatbot_response(user_message)
        return jsonify({"response": bot_response})
    else:
        return render_template('chatbot.html')
    
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()




if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True)