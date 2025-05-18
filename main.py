from flask import Flask, render_template, redirect, url_for, flash, request, session, Blueprint
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'b2c8d4f19f8e2b7d9a6e5f4c1b3f2e8d4c6a7b8c'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/pyproject'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.Float, nullable=False)
    billing_date = db.Column(db.Date, nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#53a7f3")
    label_id = db.Column(db.Integer, db.ForeignKey('label.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    label = db.relationship('Label', backref='subscriptions')
    user = db.relationship('User', backref='subscriptions')

class Label(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#e2f1ff")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User', backref='labels')

@app.route('/')
def index():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('index.html', user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
            return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('A választott név már foglalt.')
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Sikeres regisztráció!')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('Sikeres bejelentkezés!')
            return redirect(url_for('index'))
        else:
            flash('A felhasználónév vagy jelszó helytelen.')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' not in session:
            return redirect(url_for('index'))

    session.pop('user_id', None)
    flash('Sikeresen kijelentkeztél!')
    return redirect(url_for('index'))

@app.route('/subscriptions', methods=['GET', 'POST'])
def subscriptions():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        cost = float(request.form['cost'])
        billing_date = datetime.strptime(request.form['billing_date'], '%Y-%m-%d').date()
        color = request.form['color']
        label_id = request.form.get('label_id') or None
        if label_id == "new":
            label_name = request.form.get('new_label_name')
            label_color = request.form.get('new_label_color', '#e2f1ff')
            if label_name:
                new_label = Label(name=label_name, color=label_color, user_id=session['user_id'])
                db.session.add(new_label)
                db.session.commit()
                label_id = new_label.id
            else:
                label_id = None
        subscription = Subscription(
            name=name,
            cost=cost,
            billing_date=billing_date,
            color=color,
            label_id=label_id,
            user_id=session['user_id']
        )
        db.session.add(subscription)
        db.session.commit()
        flash("Előfizetés sikeresen hozzáadva!", "success")
        return redirect(url_for('subscriptions'))
    
    user_id = session['user_id']
    all_subs = Subscription.query.filter_by(user_id=user_id).all()

    for sub in all_subs:
        sub.next_billing_date = calculate_next_billing_date(sub.billing_date)

    all_subs.sort(key=lambda sub: sub.next_billing_date)

    total_cost = int(sum(sub.cost for sub in all_subs))
    today = datetime.today().date()
    remaining_cost = int(sum(sub.cost for sub in all_subs if sub.billing_date >= today))

    labels = Label.query.filter_by(user_id=user_id).all()
    return render_template(
        'subscriptions.html',
        subscriptions=all_subs,
        labels=labels,
        total_cost=total_cost,
        remaining_cost=remaining_cost
    )

@app.route('/subscriptions/delete/<int:sub_id>', methods=['POST'])
def delete_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.user_id != session['user_id']:
        abort()
    db.session.delete(sub)
    db.session.commit()
    flash("Előfizetés törölve!", "success")
    return redirect(url_for('subscriptions'))

def calculate_next_billing_date(billing_date):
    today = datetime.today().date()
    if billing_date >= today:
        return billing_date
    while billing_date < today:
        billing_date = billing_date.replace(month=billing_date.month + 1) if billing_date.month < 12 else billing_date.replace(year=billing_date.year + 1, month=1)
    return billing_date

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
