from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = '2rist-travel-agency-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel_agency.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# ========== МОДЕЛИ ==========
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    birth_date = db.Column(db.Date)
    gender = db.Column(db.String(10))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship('Booking', backref='user', lazy=True)
    reviews = db.relationship('Review', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def age(self):
        if self.birth_date:
            today = datetime.utcnow().date()
            return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return None

class Hotel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(300))
    stars = db.Column(db.Integer)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    image_url_2 = db.Column(db.String(500))
    image_url_3 = db.Column(db.String(500))
    image_url_4 = db.Column(db.String(500))
    rating = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tariffs = db.relationship('Tariff', backref='hotel', lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship('Review', backref='hotel', lazy=True, cascade="all, delete-orphan")

    @property
    def min_price(self):
        if self.tariffs:
            return min(tariff.price_per_night for tariff in self.tariffs)
        return 0

    @property
    def all_images(self):
        result = []
        for url in [self.image_url, self.image_url_2, self.image_url_3, self.image_url_4]:
            if url and url.strip():
                result.append(url.strip())
        return result

    def suitable_for_guests(self, guests_count):
        return any(tariff.max_guests >= guests_count for tariff in self.tariffs)


class Tariff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    price_per_night = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    max_guests = db.Column(db.Integer, default=2)
    meal_type = db.Column(db.String(50), default='Без питания')
    wifi_included = db.Column(db.Boolean, default=True)
    cancellation_policy = db.Column(db.String(200))
    image_url = db.Column(db.String(500))
    image_url_2 = db.Column(db.String(500))
    image_url_3 = db.Column(db.String(500))

    @property
    def all_images(self):
        result = []
        for url in [self.image_url, self.image_url_2, self.image_url_3]:
            if url and url.strip():
                result.append(url.strip())
        return result

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    tariff_id = db.Column(db.Integer, db.ForeignKey('tariff.id'), nullable=False)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=False)
    guests = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    hotel = db.relationship('Hotel', backref='bookings')
    tariff = db.relationship('Tariff', backref='bookings')


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(20), default='completed')

    booking = db.relationship('Booking', backref='payments')


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200))
    text = db.Column(db.Text)
    pros = db.Column(db.Text)
    cons = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ========== ДЕКОРАТОРЫ ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


# ========== МАРШРУТЫ ==========
@app.route('/')
def index():
    # Популярные отели — 3 самых бронируемых
    from sqlalchemy import func

    popular_query = db.session.query(
        Hotel,
        func.count(Booking.id).label('booking_count')
    ).outerjoin(Booking).group_by(Hotel.id).order_by(func.count(Booking.id).desc()).limit(3).all()

    popular_hotels = []
    for hotel, count in popular_query:
        hotel.booking_count = count
        hotel.is_hit = count > 0
        popular_hotels.append(hotel)

    return render_template('index.html', popular_hotels=popular_hotels)


@app.route('/hotels')
def hotels():
    search_query = request.args.get('query', '')
    country = request.args.get('country', '')
    city = request.args.get('city', '')
    stars = request.args.getlist('stars')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    sort = request.args.get('sort', 'popular')
    meal_type = request.args.get('meal_type', '')
    rating_min = request.args.get('rating_min', '')
    guests_str = request.args.get('guests', '2')

    if not search_query and country:
        search_query = country

    try:
        guests_count = int(guests_str)
        guests_count = max(1, min(6, guests_count))
    except:
        guests_count = 2

    query = Hotel.query

    if stars:
        query = query.filter(Hotel.stars.in_([int(s) for s in stars]))
    if rating_min:
        query = query.filter(Hotel.rating >= float(rating_min))

    hotels_all = query.all()

    # Регистронезависимый поиск через Python
    if search_query:
        search_lower = search_query.lower().strip()
        hotels_all = [h for h in hotels_all if
                      search_lower in h.country.lower() or
                      search_lower in h.city.lower() or
                      search_lower in h.name.lower()]

    # Фильтр по количеству гостей
    hotels_list = [h for h in hotels_all if h.suitable_for_guests(guests_count)]

    # Сортировка
    if sort == 'price_asc':
        hotels_list.sort(key=lambda h: h.min_price)
    elif sort == 'price_desc':
        hotels_list.sort(key=lambda h: h.min_price, reverse=True)
    elif sort == 'rating':
        hotels_list.sort(key=lambda h: h.rating, reverse=True)
    else:
        hotels_list.sort(key=lambda h: h.rating, reverse=True)

    # Фильтр по цене
    if min_price or max_price:
        filtered = []
        for hotel in hotels_list:
            if min_price and hotel.min_price < float(min_price):
                continue
            if max_price and hotel.min_price > float(max_price):
                continue
            filtered.append(hotel)
        hotels_list = filtered

    # Фильтр по питанию
    if meal_type:
        filtered = []
        for hotel in hotels_list:
            for tariff in hotel.tariffs:
                if tariff.max_guests < guests_count:
                    continue
                meal = tariff.meal_type.lower()
                matched = False
                if meal_type == 'breakfast':
                    matched = 'завтрак' in meal and 'обед' not in meal and 'ужин' not in meal
                elif meal_type == 'half_board':
                    matched = 'завтрак' in meal and 'ужин' in meal and 'обед' not in meal
                elif meal_type == 'full_board':
                    matched = 'завтрак' in meal and 'обед' in meal and 'ужин' in meal
                elif meal_type == 'all_inclusive':
                    matched = 'всё включено' in meal and 'ультра' not in meal
                elif meal_type == 'ultra_all_inclusive':
                    matched = 'ультра всё включено' in meal
                if matched:
                    filtered.append(hotel)
                    break
        hotels_list = filtered

    return render_template('hotels.html', hotels=hotels_list, hero_small=True, guests_count=guests_count,
                           search_query=search_query)

@app.route('/hotel/<int:hotel_id>')
def hotel_detail(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    reviews = Review.query.filter_by(hotel_id=hotel_id).order_by(Review.created_at.desc()).limit(10).all()
    return render_template('hotel_detail.html', hotel=hotel, reviews=reviews, hero_small=True)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        full_name = request.form.get('full_name', '')
        phone = request.form.get('phone', '')

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email, full_name=full_name, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна! Теперь вы можете войти в систему', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', hero_small=True)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'danger')
    return render_template('login.html', hero_small=True)


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/booking/<int:hotel_id>', methods=['GET', 'POST'])
@login_required
def booking(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    tariff_id = request.args.get('tariff_id')

    # Если tariff_id передан — берём указанный тариф, иначе — первый
    if tariff_id:
        tariff = Tariff.query.get(tariff_id)
    else:
        tariff = hotel.tariffs[0] if hotel.tariffs else None

    if not tariff:
        flash('Нет доступных тарифов для бронирования', 'danger')
        return redirect(url_for('hotel_detail', hotel_id=hotel_id))

    if request.method == 'POST':
        tariff_id_form = request.form['tariff_id']
        tariff = Tariff.query.get_or_404(tariff_id_form)
        check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d')
        check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d')
        guests = int(request.form['guests'])

        if guests > tariff.max_guests:
            flash('Количество гостей превышает максимально допустимое для выбранного тарифа', 'danger')
            return redirect(url_for('booking', hotel_id=hotel_id, tariff_id=tariff.id))

        nights = (check_out - check_in).days
        if nights < 1:
            nights = 1

        total_price = nights * tariff.price_per_night * guests

        booking = Booking(
            user_id=session['user_id'],
            hotel_id=hotel_id,
            tariff_id=tariff.id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            total_price=total_price
        )

        db.session.add(booking)
        db.session.commit()
        flash('Бронирование успешно создано!', 'success')
        return redirect(url_for('my_bookings'))

    return render_template('booking.html', hotel=hotel, tariff=tariff, hero_small=True)


@app.route('/my-bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=session['user_id']).order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', bookings=bookings, hero_small=True)


@app.route('/hotel/<int:hotel_id>/review', methods=['POST'])
@login_required
def add_review(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    rating = int(request.form['rating'])
    title = request.form.get('title', '')
    text = request.form.get('text', '')
    pros = request.form.get('pros', '')
    cons = request.form.get('cons', '')
    existing = Review.query.filter_by(user_id=session['user_id'], hotel_id=hotel_id).first()
    if existing:
        flash('Вы уже оставляли отзыв об этом отеле', 'warning')
        return redirect(url_for('hotel_detail', hotel_id=hotel_id))
    review = Review(user_id=session['user_id'], hotel_id=hotel_id, rating=rating, title=title, text=text, pros=pros,
                    cons=cons)
    db.session.add(review)
    all_reviews = Review.query.filter_by(hotel_id=hotel_id).all()
    hotel.rating = round(sum(r.rating for r in all_reviews) / len(all_reviews), 1)
    db.session.commit()
    flash('Спасибо за отзыв!', 'success')
    return redirect(url_for('hotel_detail', hotel_id=hotel_id))


# ========== АДМИН-ПАНЕЛЬ ==========
@app.route('/admin')
@admin_required
def admin_panel():
    hotels_count = Hotel.query.count()
    bookings_count = Booking.query.count()
    users_count = User.query.filter_by(role='user').count()
    reviews_count = Review.query.count()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
    return render_template('admin/panel.html', hotels_count=hotels_count, bookings_count=bookings_count,
                           users_count=users_count, reviews_count=reviews_count, recent_bookings=recent_bookings,
                           hide_hero=True)


@app.route('/admin/hotels')
@admin_required
def admin_hotels():
    hotels = Hotel.query.all()
    return render_template('admin/hotels.html', hotels=hotels, hide_hero=True)


@app.route('/admin/hotel/add', methods=['GET', 'POST'])
@admin_required
def admin_add_hotel():
    if request.method == 'POST':
        # Сохранение изображений отеля
        image_urls = ['', '', '', '']

        for i in range(4):
            file_key = 'image_file' if i == 0 else f'image_file_{i + 1}'
            url_key = 'image_url' if i == 0 else f'image_url_{i + 1}'

            # Сначала проверяем загруженный файл
            if file_key in request.files and request.files[file_key].filename:
                file = request.files[file_key]
                filename = secure_filename(f"{datetime.utcnow().timestamp()}_{i}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_urls[i] = url_for('static', filename=f'uploads/{filename}')
            # Если файла нет, берём ссылку из текстового поля
            elif request.form.get(url_key, '').strip():
                image_urls[i] = request.form[url_key].strip()

        hotel = Hotel(
            name=request.form['name'],
            country=request.form['country'],
            city=request.form['city'],
            address=request.form.get('address', ''),
            stars=int(request.form['stars']),
            description=request.form.get('description', ''),
            image_url=image_urls[0],
            image_url_2=image_urls[1],
            image_url_3=image_urls[2],
            image_url_4=image_urls[3],
            rating=float(request.form.get('rating', 4.5))
        )

        db.session.add(hotel)
        db.session.flush()

        # Сохранение тарифов
        tariff_names = request.form.getlist('tariff_name[]')
        tariff_prices = request.form.getlist('tariff_price[]')
        tariff_descriptions = request.form.getlist('tariff_description[]')
        tariff_guests = request.form.getlist('tariff_guests[]')
        tariff_meals = request.form.getlist('tariff_meal[]')

        for i in range(len(tariff_names)):
            if tariff_names[i].strip():
                # Загрузка фото тарифа
                tariff_images = ['', '', '']

                for j in range(3):
                    file_key = f'tariff_image_{i}' if j == 0 else f'tariff_image_{i}_{j + 1}'
                    url_key = f'tariff_image_url_{i}' if j == 0 else f'tariff_image_url_{i}_{j + 1}'

                    if file_key in request.files and request.files[file_key].filename:
                        file = request.files[file_key]
                        filename = secure_filename(f"{datetime.utcnow().timestamp()}_tariff_{i}_{j}_{file.filename}")
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        tariff_images[j] = url_for('static', filename=f'uploads/{filename}')
                    elif request.form.get(url_key, '').strip():
                        tariff_images[j] = request.form[url_key].strip()

                tariff = Tariff(
                    hotel_id=hotel.id,
                    name=tariff_names[i].strip(),
                    price_per_night=float(tariff_prices[i]) if tariff_prices[i] else 0,
                    description=tariff_descriptions[i] if i < len(tariff_descriptions) else '',
                    max_guests=int(tariff_guests[i]) if i < len(tariff_guests) and tariff_guests[i] else 2,
                    meal_type=tariff_meals[i] if i < len(tariff_meals) else 'Без питания',
                    wifi_included=True,
                    cancellation_policy='Бесплатная отмена за 48 часов до заезда',
                    image_url=tariff_images[0],
                    image_url_2=tariff_images[1],
                    image_url_3=tariff_images[2]
                )
                db.session.add(tariff)

        db.session.commit()
        flash('Отель успешно добавлен!', 'success')
        return redirect(url_for('admin_hotels'))

    return render_template('admin/add_hotel.html', hide_hero=True)


@app.route('/admin/hotel/edit/<int:hotel_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_hotel(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)

    if request.method == 'POST':
        hotel.name = request.form['name']
        hotel.country = request.form['country']
        hotel.city = request.form['city']
        hotel.address = request.form.get('address', '')
        hotel.stars = int(request.form['stars'])
        hotel.description = request.form.get('description', '')
        hotel.rating = float(request.form.get('rating', hotel.rating))

        # Обновление фото отеля
        field_map = {0: 'image_url', 1: 'image_url_2', 2: 'image_url_3', 3: 'image_url_4'}
        for i in range(4):
            file_key = 'image_file' if i == 0 else f'image_file_{i + 1}'
            url_key = 'image_url' if i == 0 else f'image_url_{i + 1}'

            if file_key in request.files and request.files[file_key].filename:
                file = request.files[file_key]
                filename = secure_filename(f"{datetime.utcnow().timestamp()}_{i}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                setattr(hotel, field_map[i], url_for('static', filename=f'uploads/{filename}'))
            elif request.form.get(url_key, '').strip():
                setattr(hotel, field_map[i], request.form[url_key].strip())

        # Удаление старых тарифов и создание новых
        Tariff.query.filter_by(hotel_id=hotel.id).delete()

        tariff_names = request.form.getlist('tariff_name[]')
        tariff_prices = request.form.getlist('tariff_price[]')
        tariff_descriptions = request.form.getlist('tariff_description[]')
        tariff_guests = request.form.getlist('tariff_guests[]')
        tariff_meals = request.form.getlist('tariff_meal[]')

        for i in range(len(tariff_names)):
            if tariff_names[i].strip():
                tariff_images = ['', '', '']
                for j in range(3):
                    file_key = f'tariff_image_{i}' if j == 0 else f'tariff_image_{i}_{j + 1}'
                    url_key = f'tariff_image_url_{i}' if j == 0 else f'tariff_image_url_{i}_{j + 1}'

                    if file_key in request.files and request.files[file_key].filename:
                        file = request.files[file_key]
                        filename = secure_filename(f"{datetime.utcnow().timestamp()}_tariff_{i}_{j}_{file.filename}")
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        tariff_images[j] = url_for('static', filename=f'uploads/{filename}')
                    elif request.form.get(url_key, '').strip():
                        tariff_images[j] = request.form[url_key].strip()

                tariff = Tariff(
                    hotel_id=hotel.id,
                    name=tariff_names[i].strip(),
                    price_per_night=float(tariff_prices[i]) if tariff_prices[i] else 0,
                    description=tariff_descriptions[i] if i < len(tariff_descriptions) else '',
                    max_guests=int(tariff_guests[i]) if i < len(tariff_guests) and tariff_guests[i] else 2,
                    meal_type=tariff_meals[i] if i < len(tariff_meals) else 'Без питания',
                    wifi_included=True,
                    cancellation_policy='Бесплатная отмена за 48 часов до заезда',
                    image_url=tariff_images[0],
                    image_url_2=tariff_images[1],
                    image_url_3=tariff_images[2]
                )
                db.session.add(tariff)

        db.session.commit()
        flash('Отель успешно обновлен!', 'success')
        return redirect(url_for('admin_hotels'))

    return render_template('admin/edit_hotel.html', hotel=hotel, hide_hero=True)

@app.route('/admin/hotel/delete/<int:hotel_id>')
@admin_required
def admin_delete_hotel(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    bookings = Booking.query.filter_by(hotel_id=hotel_id).all()
    for booking in bookings:
        Payment.query.filter_by(booking_id=booking.id).delete()
        db.session.delete(booking)
    Review.query.filter_by(hotel_id=hotel_id).delete()
    db.session.delete(hotel)
    db.session.commit()
    flash('Отель успешно удален!', 'success')
    return redirect(url_for('admin_hotels'))


@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings, hide_hero=True)


@app.route('/admin/booking/<int:booking_id>/payment', methods=['POST'])
@admin_required
def admin_add_payment(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    amount = float(request.form['amount'])
    payment_method = request.form.get('payment_method', 'card')
    payment = Payment(booking_id=booking_id, amount=amount, payment_method=payment_method)
    total_paid = sum(p.amount for p in booking.payments) + amount
    if total_paid >= booking.total_price:
        booking.status = 'paid'
    else:
        booking.status = 'confirmed'
    db.session.add(payment)
    db.session.commit()
    flash('Платеж успешно добавлен!', 'success')
    return redirect(url_for('admin_bookings'))


@app.route('/admin/review/delete/<int:review_id>', methods=['POST', 'GET'])
@admin_required
def admin_delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    hotel_id = review.hotel_id
    db.session.delete(review)
    hotel = Hotel.query.get(hotel_id)
    all_reviews = Review.query.filter_by(hotel_id=hotel_id).all()
    if all_reviews:
        hotel.rating = round(sum(r.rating for r in all_reviews) / len(all_reviews), 1)
    else:
        hotel.rating = 0.0
    db.session.commit()
    flash('Отзыв успешно удалён', 'success')
    return redirect(url_for('hotel_detail', hotel_id=hotel_id))


@app.route('/api/hotels/search')
def api_search_hotels():
    query = request.args.get('q', '')
    hotels_list = Hotel.query.filter(
        (Hotel.name.ilike(f'%{query}%')) |
        (Hotel.city.ilike(f'%{query}%')) |
        (Hotel.country.ilike(f'%{query}%'))
    ).limit(10).all()
    return jsonify([{
        'id': h.id,
        'name': h.name,
        'city': h.city,
        'country': h.country,
        'stars': h.stars,
        'min_price': h.min_price
    } for h in hotels_list])


# ========== ИНФО СТРАНИЦЫ ==========
@app.route('/faq')
def faq():
    return render_template('faq.html', hero_small=True)


@app.route('/how-to-book')
def how_to_book():
    return render_template('how_to_book.html', hero_small=True)


@app.route('/payment-methods')
def payment_methods():
    return render_template('payment_methods.html', hero_small=True)


@app.route('/cancellation-policy')
def cancellation_policy():
    return render_template('cancellation_policy.html', hero_small=True)


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html', hero_small=True)


# ========== ИНИЦИАЛИЗАЦИЯ БД ==========
def init_db():
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@2rist.ru', full_name='Администратор', role='admin')
            admin.set_password('admin1')
            db.session.add(admin)

        if not User.query.filter_by(username='test').first():
            test_user = User(username='test', email='test@2rist.ru', full_name='Тестовый Пользователь', role='user')
            test_user.set_password('test123')
            db.session.add(test_user)

        db.session.commit()

        if Hotel.query.count() == 0:
            hotels_data = [
                {
                    'name': 'Rixos Premium Belek',
                    'country': 'Турция',
                    'city': 'Белек',
                    'address': 'Belek Mahallesi, Kongre Caddesi No:18/A',
                    'stars': 5,
                    'description': 'Роскошный отель на берегу Средиземного моря с собственным пляжем, аквапарком и спа-центром мирового уровня. Идеальное место для семейного отдыха.',
                    'image_url': 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=800',
                    'rating': 4.8,
                    'tariffs': [
                        {'name': 'Эконом', 'price': 15000, 'description': 'Вид на сад', 'guests': 2, 'meal': 'Завтрак'},
                        {'name': 'Стандарт', 'price': 22000, 'description': 'Вид на море', 'guests': 2,
                         'meal': 'Завтрак и ужин'},
                        {'name': 'Люкс', 'price': 35000, 'description': 'С террасой', 'guests': 4,
                         'meal': 'Всё включено'},
                        {'name': 'Делюкс', 'price': 50000, 'description': 'С джакузи', 'guests': 4,
                         'meal': 'Всё включено'}
                    ]
                },
                {
                    'name': 'Burj Al Arab Jumeirah',
                    'country': 'ОАЭ',
                    'city': 'Дубай',
                    'address': 'Jumeirah St, Dubai',
                    'stars': 5,
                    'description': 'Знаменитый отель-парус, символ роскоши и превосходного сервиса в центре Дубая.',
                    'image_url': 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800',
                    'rating': 4.9,
                    'tariffs': [
                        {'name': 'Делюкс', 'price': 80000, 'description': 'Панорамный вид', 'guests': 2,
                         'meal': 'Завтрак, обед и ужин'},
                        {'name': 'Королевский', 'price': 150000, 'description': 'С дворецким', 'guests': 4,
                         'meal': 'Всё включено'},
                        {'name': 'Президентский', 'price': 250000, 'description': 'Лучший номер', 'guests': 4,
                         'meal': 'Ультра всё включено'}
                    ]
                },
                {
                    'name': 'Four Seasons Resort Bali',
                    'country': 'Индонезия',
                    'city': 'Бали',
                    'address': 'Jimbaran, Bali',
                    'stars': 5,
                    'description': 'Райский уголок на берегу Индийского океана с традиционной балийской архитектурой.',
                    'image_url': 'https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=800',
                    'rating': 4.7,
                    'tariffs': [
                        {'name': 'Эконом', 'price': 12000, 'description': 'В саду', 'guests': 2, 'meal': 'Без питания'},
                        {'name': 'Стандарт', 'price': 18000, 'description': 'Вид на океан', 'guests': 2,
                         'meal': 'Завтрак'},
                        {'name': 'Люкс', 'price': 28000, 'description': 'С бассейном', 'guests': 4,
                         'meal': 'Завтрак и ужин'},
                        {'name': 'Делюкс', 'price': 40000, 'description': 'Премиум вилла', 'guests': 4,
                         'meal': 'Всё включено'}
                    ]
                },
                {
                    'name': 'Mövenpick Resort El Gouna',
                    'country': 'Египет',
                    'city': 'Хургада',
                    'address': 'El Gouna, Hurghada',
                    'stars': 4,
                    'description': 'Семейный отель на Красном море с развитой инфраструктурой.',
                    'image_url': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800',
                    'rating': 4.5,
                    'tariffs': [
                        {'name': 'Эконом', 'price': 8000, 'description': 'Вид на сад', 'guests': 2,
                         'meal': 'Без питания'},
                        {'name': 'Стандарт', 'price': 12000, 'description': 'Вид на лагуну', 'guests': 2,
                         'meal': 'Завтрак'},
                        {'name': 'Люкс', 'price': 20000, 'description': 'Две комнаты', 'guests': 4,
                         'meal': 'Всё включено'}
                    ]
                }
            ]

            for hotel_data in hotels_data:
                tariffs_data = hotel_data.pop('tariffs')
                hotel = Hotel(**hotel_data)
                db.session.add(hotel)
                db.session.flush()
                for tariff_data in tariffs_data:
                    tariff = Tariff(
                        hotel_id=hotel.id,
                        name=tariff_data['name'],
                        price_per_night=tariff_data['price'],
                        description=tariff_data['description'],
                        max_guests=tariff_data['guests'],
                        meal_type=tariff_data['meal'],
                        wifi_included=True,
                        cancellation_policy='Бесплатная отмена за 48 часов до заезда'
                    )
                    db.session.add(tariff)
            db.session.commit()


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '')
        user.phone = request.form.get('phone', '')
        user.email = request.form.get('email', '')
        user.country = request.form.get('country', '')
        user.city = request.form.get('city', '')
        user.gender = request.form.get('gender', '')

        birth_date_str = request.form.get('birth_date', '')
        if birth_date_str:
            user.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()

        # Проверка email на уникальность
        existing = User.query.filter(User.email == user.email, User.id != user.id).first()
        if existing:
            flash('Этот email уже используется другим пользователем', 'danger')
            return redirect(url_for('profile'))

        db.session.commit()
        flash('Профиль успешно обновлён!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user, hero_small=True)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)