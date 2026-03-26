from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '2rist-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                                                    'instance', 'hotel.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    bookings = db.relationship('Booking', backref='user', lazy=True)


class Hotel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(200), default='/static/images/hotel-placeholder.jpg')
    tariffs = db.relationship('Tariff', backref='hotel', lazy=True, cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='hotel', lazy=True)


class Tariff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    price_per_night = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    tariff_id = db.Column(db.Integer, db.ForeignKey('tariff.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tariff = db.relationship('Tariff', backref='bookings')
    payments = db.relationship('Payment', backref='booking', lazy=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(20), default='completed')


# Создание базы данных
with app.app_context():
    db.create_all()
    # Создание админа если не существует
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin1', email='admin@2rist.com', is_admin=True)
        db.session.add(admin)
        print("Администратор создан: admin / admin1")
    # Создание тестового пользователя если не существует
    if not User.query.filter_by(username='test').first():
        test_user = User(username='test', password='test123', email='test@example.com', is_admin=False)
        db.session.add(test_user)
        print("Тестовый пользователь создан: test / test123")
    db.session.commit()


# Маршруты
@app.route('/')
def index():
    hotels = Hotel.query.limit(6).all()
    return render_template('index.html', hotels=hotels)


@app.route('/hotels')
def hotels():
    hotels_list = Hotel.query.all()
    return render_template('hotels.html', hotels=hotels_list)


@app.route('/hotel/<int:hotel_id>')
def hotel_detail(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    return render_template('hotel_detail.html', hotel=hotel)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password, email=email, is_admin=False)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь вы можете войти в систему', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash(f'С возвращением, {username}!', 'success')

            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    bookings = Booking.query.filter_by(user_id=user.id).order_by(Booking.created_at.desc()).all()
    return render_template('dashboard.html', user=user, bookings=bookings)


@app.route('/book/<int:hotel_id>', methods=['POST'])
def book_hotel(hotel_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Пожалуйста, войдите в систему'}), 401

    data = request.json
    tariff_id = data.get('tariff_id')
    check_in = datetime.strptime(data.get('check_in'), '%Y-%m-%d').date()
    check_out = datetime.strptime(data.get('check_out'), '%Y-%m-%d').date()
    guests = data.get('guests')

    tariff = Tariff.query.get(tariff_id)
    nights = (check_out - check_in).days
    total_price = nights * tariff.price_per_night

    booking = Booking(
        user_id=session['user_id'],
        hotel_id=hotel_id,
        tariff_id=tariff_id,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        total_price=total_price
    )

    db.session.add(booking)
    db.session.commit()

    return jsonify({'success': True, 'booking_id': booking.id})


@app.route('/my-bookings')
def my_bookings():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))

    bookings = Booking.query.filter_by(user_id=session['user_id']).order_by(Booking.created_at.desc()).all()
    return render_template('bookings.html', bookings=bookings)


# Админ панель
@app.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    hotels = Hotel.query.all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    users = User.query.all()

    stats = {
        'total_hotels': len(hotels),
        'total_bookings': Booking.query.count(),
        'total_users': len(users),
        'total_revenue': sum([b.total_price for b in Booking.query.filter_by(status='confirmed').all()])
    }

    return render_template('admin/admin_dashboard.html', hotels=hotels, bookings=bookings, stats=stats)


@app.route('/admin/add-hotel', methods=['GET', 'POST'])
def add_hotel():
    if not session.get('is_admin'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        city = request.form['city']
        address = request.form['address']
        description = request.form['description']
        image_url = request.form.get('image_url', '/static/images/hotel-placeholder.jpg')

        hotel = Hotel(name=name, city=city, address=address, description=description, image_url=image_url)
        db.session.add(hotel)
        db.session.commit()

        # Добавление тарифов
        tariff_names = request.form.getlist('tariff_name[]')
        tariff_prices = request.form.getlist('tariff_price[]')
        tariff_descriptions = request.form.getlist('tariff_description[]')

        for i in range(len(tariff_names)):
            if tariff_names[i] and tariff_prices[i]:
                tariff = Tariff(
                    name=tariff_names[i],
                    price_per_night=float(tariff_prices[i]),
                    description=tariff_descriptions[i] if i < len(tariff_descriptions) else '',
                    hotel_id=hotel.id
                )
                db.session.add(tariff)

        db.session.commit()
        flash('Отель успешно добавлен!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/add_hotel.html')


@app.route('/admin/edit-hotel/<int:hotel_id>', methods=['GET', 'POST'])
def edit_hotel(hotel_id):
    if not session.get('is_admin'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    hotel = Hotel.query.get_or_404(hotel_id)

    if request.method == 'POST':
        hotel.name = request.form['name']
        hotel.city = request.form['city']
        hotel.address = request.form['address']
        hotel.description = request.form['description']
        hotel.image_url = request.form.get('image_url', hotel.image_url)

        # Обновление существующих тарифов
        existing_tariffs = {t.id: t for t in hotel.tariffs}

        tariff_ids = request.form.getlist('tariff_id[]')
        tariff_names = request.form.getlist('tariff_name[]')
        tariff_prices = request.form.getlist('tariff_price[]')
        tariff_descriptions = request.form.getlist('tariff_description[]')

        updated_ids = set()

        for i in range(len(tariff_names)):
            if tariff_names[i] and tariff_prices[i]:
                if i < len(tariff_ids) and tariff_ids[i]:
                    # Обновление существующего тарифа
                    tariff = Tariff.query.get(int(tariff_ids[i]))
                    if tariff:
                        tariff.name = tariff_names[i]
                        tariff.price_per_night = float(tariff_prices[i])
                        tariff.description = tariff_descriptions[i] if i < len(tariff_descriptions) else ''
                        updated_ids.add(tariff.id)
                else:
                    # Добавление нового тарифа
                    tariff = Tariff(
                        name=tariff_names[i],
                        price_per_night=float(tariff_prices[i]),
                        description=tariff_descriptions[i] if i < len(tariff_descriptions) else '',
                        hotel_id=hotel.id
                    )
                    db.session.add(tariff)

        # Удаление тарифов, которые не были обновлены
        for tariff in hotel.tariffs:
            if tariff.id not in updated_ids:
                db.session.delete(tariff)

        db.session.commit()
        flash('Отель успешно обновлен!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/edit_hotel.html', hotel=hotel)


@app.route('/admin/delete-hotel/<int:hotel_id>')
def delete_hotel(hotel_id):
    if not session.get('is_admin'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    hotel = Hotel.query.get_or_404(hotel_id)
    db.session.delete(hotel)
    db.session.commit()
    flash('Отель успешно удален!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/bookings')
def admin_bookings():
    if not session.get('is_admin'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)


@app.route('/admin/add-payment/<int:booking_id>', methods=['GET', 'POST'])
def add_payment(booking_id):
    if not session.get('is_admin'):
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    booking = Booking.query.get_or_404(booking_id)

    if request.method == 'POST':
        amount = float(request.form['amount'])
        payment_method = request.form['payment_method']

        payment = Payment(
            booking_id=booking.id,
            amount=amount,
            payment_method=payment_method
        )

        booking.status = 'confirmed'
        db.session.add(payment)
        db.session.commit()

        flash('Платеж успешно добавлен!', 'success')
        return redirect(url_for('admin_bookings'))

    return render_template('admin/add_payment.html', booking=booking)


if __name__ == '__main__':
    app.run(debug=True)