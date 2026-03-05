from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
import logging

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Для flash сообщений

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///baza.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Модель клиента
class Client(db.Model):
    __tablename__ = 'clients'

    client_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    passport_number = db.Column(db.String(20), unique=True, nullable=False)
    passport_issued = db.Column(db.String(100))
    passport_date = db.Column(db.Date)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), unique=True)
    birth_date = db.Column(db.Date, nullable=False)
    registration_date = db.Column(db.Date, default=datetime.now().date)
    address = db.Column(db.String(200))
    notes = db.Column(db.Text)

    # Связи
    bookings = db.relationship('Booking', backref='client', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='client', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Client {self.last_name} {self.first_name}>'


# Модель страны
class Country(db.Model):
    __tablename__ = 'countries'

    country_id = db.Column(db.Integer, primary_key=True)
    country_name = db.Column(db.String(100), unique=True, nullable=False)
    country_code = db.Column(db.String(3), unique=True)
    visa_required = db.Column(db.Boolean, default=False)
    currency = db.Column(db.String(3), default='USD')
    language = db.Column(db.String(50))
    notes = db.Column(db.Text)

    hotels = db.relationship('Hotel', backref='country', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Country {self.country_name}>'


# Модель отеля
class Hotel(db.Model):
    __tablename__ = 'hotels'

    hotel_id = db.Column(db.Integer, primary_key=True)
    hotel_name = db.Column(db.String(200), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.country_id', ondelete='CASCADE'), nullable=False)
    city_name = db.Column(db.String(100), nullable=False)
    stars = db.Column(db.Integer)
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    website = db.Column(db.String(100))
    description = db.Column(db.Text)
    facilities = db.Column(db.Text)

    # Тарифы отеля
    standard_rate = db.Column(db.Float, nullable=False, default=5000)
    deluxe_rate = db.Column(db.Float, nullable=False, default=8000)
    suite_rate = db.Column(db.Float, nullable=False, default=12000)
    family_rate = db.Column(db.Float, nullable=False, default=10000)

    __table_args__ = (
        db.CheckConstraint('stars BETWEEN 1 AND 5', name='check_stars_range'),
    )

    bookings = db.relationship('Booking', backref='hotel', lazy=True)

    def get_rate_by_room_type(self, room_type):
        rates = {
            'Standard': self.standard_rate,
            'Deluxe': self.deluxe_rate,
            'Suite': self.suite_rate,
            'Family': self.family_rate
        }
        return rates.get(room_type, self.standard_rate)


# Модель сотрудника (турагента)
class Employee(db.Model):
    __tablename__ = 'employees'

    employee_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(100), default='Турагент')
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100), unique=True)
    hire_date = db.Column(db.Date, default=datetime.now().date)
    commission_rate = db.Column(db.Float, default=5.0)  # 5% комиссии
    is_active = db.Column(db.Boolean, default=True)

    bookings = db.relationship('Booking', backref='employee', lazy=True)
    payments = db.relationship('Payment', backref='employee', lazy=True)

    def calculate_commission(self, booking):
        """Рассчитать комиссию с бронирования"""
        if booking and booking.total_price:
            return booking.total_price * (self.commission_rate / 100)
        return 0

    def total_commission_for_month(self, month, year):
        """Общая комиссия за месяц"""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        monthly_bookings = Booking.query.filter(
            Booking.employee_id == self.employee_id,
            Booking.booking_date >= start_date,
            Booking.booking_date < end_date,
            Booking.booking_status == 'confirmed'
        ).all()

        total = sum(self.calculate_commission(b) for b in monthly_bookings)
        return total


# Модель бронирования
class Booking(db.Model):
    __tablename__ = 'bookings'

    booking_id = db.Column(db.Integer, primary_key=True)
    booking_number = db.Column(db.String(20), unique=True)

    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id', ondelete='CASCADE'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.hotel_id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'))

    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)
    booking_date = db.Column(db.Date, default=datetime.now().date)

    adults_count = db.Column(db.Integer, nullable=False, default=1)
    children_count = db.Column(db.Integer, default=0)
    room_type = db.Column(db.String(50))

    nights_count = db.Column(db.Integer)
    daily_rate = db.Column(db.Float)

    total_price = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0)

    booking_status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled
    payment_status = db.Column(db.String(20), default='unpaid')  # unpaid, partial, paid

    special_requests = db.Column(db.Text)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.CheckConstraint('check_in_date < check_out_date', name='check_dates'),
    )

    payments = db.relationship('Payment', backref='booking', lazy=True, cascade='all, delete-orphan')

    def calculate_nights(self):
        if self.check_in_date and self.check_out_date:
            delta = self.check_out_date - self.check_in_date
            return delta.days
        return 0

    def calculate_total_price(self):
        self.nights_count = self.calculate_nights()
        if self.hotel and self.nights_count > 0:
            self.daily_rate = self.hotel.get_rate_by_room_type(self.room_type)
            return self.daily_rate * self.nights_count
        return 0

    def remaining_payment(self):
        return self.total_price - self.paid_amount

    def generate_booking_number(self):
        return f"BK-{datetime.now().strftime('%Y%m%d')}-{self.booking_id:04d}"

    def commission_amount(self):
        """Сумма комиссии агента"""
        if self.employee and self.total_price:
            return self.total_price * (self.employee.commission_rate / 100)
        return 0


# Модель платежа
class Payment(db.Model):
    __tablename__ = 'payments'

    payment_id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(20), unique=True)

    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id', ondelete='CASCADE'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.client_id', ondelete='CASCADE'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.employee_id'))

    payment_date = db.Column(db.Date, default=datetime.now().date)
    payment_amount = db.Column(db.Float, nullable=False)

    payment_method = db.Column(db.String(20))
    transaction_id = db.Column(db.String(100))
    payment_purpose = db.Column(db.String(200))

    payment_status = db.Column(db.String(20), default='completed')

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    __table_args__ = (
        db.CheckConstraint('payment_amount > 0', name='check_payment_amount'),
    )

    def generate_payment_number(self):
        return f"PAY-{datetime.now().strftime('%Y%m%d')}-{self.payment_id:04d}"


# Функция инициализации базы данных с начальными данными
def init_db():
    with app.app_context():
        # Удаляем старую базу данных если она есть
        db.drop_all()
        # Создаем все таблицы заново
        db.create_all()

        # Добавляем страны
        countries = [
            {'name': 'Турция', 'code': 'TR', 'visa': False, 'currency': 'TRY', 'lang': 'Турецкий'},
            {'name': 'Египет', 'code': 'EG', 'visa': False, 'currency': 'EGP', 'lang': 'Арабский'},
            {'name': 'Таиланд', 'code': 'TH', 'visa': True, 'currency': 'THB', 'lang': 'Тайский'},
            {'name': 'ОАЭ', 'code': 'AE', 'visa': False, 'currency': 'AED', 'lang': 'Арабский'},
            {'name': 'Греция', 'code': 'GR', 'visa': True, 'currency': 'EUR', 'lang': 'Греческий'},
            {'name': 'Испания', 'code': 'ES', 'visa': True, 'currency': 'EUR', 'lang': 'Испанский'},
            {'name': 'Италия', 'code': 'IT', 'visa': True, 'currency': 'EUR', 'lang': 'Итальянский'},
            {'name': 'Россия', 'code': 'RU', 'visa': False, 'currency': 'RUB', 'lang': 'Русский'}
        ]
        for c in countries:
            country = Country(
                country_name=c['name'],
                country_code=c['code'],
                visa_required=c['visa'],
                currency=c['currency'],
                language=c['lang']
            )
            db.session.add(country)
        db.session.commit()

        # Добавляем 10 отелей
        hotels_data = [
            # Турция (3 отеля)
            {'name': 'Rixos Premium Belek', 'country': 'Турция', 'city': 'Белек', 'stars': 5,
             'standard': 8500, 'deluxe': 12000, 'suite': 18000, 'family': 15000,
             'facilities': 'WiFi, Аквапарк, Спа, 5 ресторанов, Частный пляж'},
            {'name': 'Hilton Istanbul Bosphorus', 'country': 'Турция', 'city': 'Стамбул', 'stars': 5,
             'standard': 7500, 'deluxe': 11000, 'suite': 16500, 'family': 13500,
             'facilities': 'WiFi, Бассейн, Спа, Бизнес-центр, Вид на Босфор'},
            {'name': 'Voyage Belek Golf & Spa', 'country': 'Турция', 'city': 'Белек', 'stars': 5,
             'standard': 9000, 'deluxe': 13000, 'suite': 19500, 'family': 16000,
             'facilities': 'WiFi, Гольф-поле, Аквапарк, Спа, Рестораны'},

            # Египет (2 отеля)
            {'name': 'Steigenberger Al Dau Beach', 'country': 'Египет', 'city': 'Хургада', 'stars': 5,
             'standard': 6500, 'deluxe': 9500, 'suite': 14000, 'family': 11500,
             'facilities': 'WiFi, Бассейн, Спа, Дайвинг-центр, Частный пляж'},
            {'name': 'Four Seasons Sharm El Sheikh', 'country': 'Египет', 'city': 'Шарм-эль-Шейх', 'stars': 5,
             'standard': 8000, 'deluxe': 11500, 'suite': 17000, 'family': 14000,
             'facilities': 'WiFi, Спа, Рестораны, Дайвинг, Теннисные корты'},

            # Таиланд (2 отеля)
            {'name': 'Mandarin Oriental Bangkok', 'country': 'Таиланд', 'city': 'Бангкок', 'stars': 5,
             'standard': 7000, 'deluxe': 10500, 'suite': 15500, 'family': 12500,
             'facilities': 'WiFi, Спа, Рестораны, Бассейн, Река Чао-Прайя'},
            {'name': 'The Shore at Katathani', 'country': 'Таиланд', 'city': 'Пхукет', 'stars': 5,
             'standard': 6800, 'deluxe': 9800, 'suite': 14500, 'family': 11800,
             'facilities': 'WiFi, Бассейн, Спа, Ресторан, Частный пляж'},

            # ОАЭ (1 отель)
            {'name': 'Burj Al Arab Jumeirah', 'country': 'ОАЭ', 'city': 'Дубай', 'stars': 5,
             'standard': 25000, 'deluxe': 35000, 'suite': 55000, 'family': 40000,
             'facilities': 'WiFi, Спа, Рестораны, Бассейн, Вертолетная площадка, Подводный ресторан'},

            # Греция (1 отель)
            {'name': 'Amanzoe', 'country': 'Греция', 'city': 'Порт-Хели', 'stars': 5,
             'standard': 12000, 'deluxe': 17000, 'suite': 25000, 'family': 20000,
             'facilities': 'WiFi, Спа, Рестораны, Бассейн, Вид на Эгейское море'},

            # Италия (1 отель)
            {'name': 'Hotel de Russie', 'country': 'Италия', 'city': 'Рим', 'stars': 5,
             'standard': 10000, 'deluxe': 15000, 'suite': 22000, 'family': 18000,
             'facilities': 'WiFi, Спа, Ресторан, Сад, Терраса'}
        ]

        for hotel_data in hotels_data:
            country = Country.query.filter_by(country_name=hotel_data['country']).first()
            if country:
                hotel = Hotel(
                    hotel_name=hotel_data['name'],
                    country_id=country.country_id,
                    city_name=hotel_data['city'],
                    stars=hotel_data['stars'],
                    facilities=hotel_data['facilities'],
                    description=f'Отель {hotel_data["stars"]} звезд в {hotel_data["city"]}, {hotel_data["country"]}',
                    standard_rate=hotel_data['standard'],
                    deluxe_rate=hotel_data['deluxe'],
                    suite_rate=hotel_data['suite'],
                    family_rate=hotel_data['family']
                )
                db.session.add(hotel)

        db.session.commit()

        # Добавляем 5 сотрудников
        employees = [
            {'first': 'Анна', 'last': 'Иванова', 'phone': '+7 (999) 111-22-33', 'email': 'anna@agency.ru'},
            {'first': 'Петр', 'last': 'Сидоров', 'phone': '+7 (999) 222-33-44', 'email': 'petr@agency.ru'},
            {'first': 'Елена', 'last': 'Петрова', 'phone': '+7 (999) 333-44-55', 'email': 'elena@agency.ru'},
            {'first': 'Михаил', 'last': 'Смирнов', 'phone': '+7 (999) 444-55-66', 'email': 'mikhail@agency.ru'},
            {'first': 'Ольга', 'last': 'Козлова', 'phone': '+7 (999) 555-66-77', 'email': 'olga@agency.ru'},
        ]

        for emp in employees:
            employee = Employee(
                first_name=emp['first'],
                last_name=emp['last'],
                position='Турагент',
                phone=emp['phone'],
                email=emp['email'],
                hire_date=date(2023, 1, 1),
                commission_rate=5.0,
                is_active=True
            )
            db.session.add(employee)
        db.session.commit()

        # Добавляем 10 клиентов
        clients = [
            {'first': 'Иван', 'last': 'Петров', 'middle': 'Иванович', 'passport': '1234 567890',
             'phone': '+7 (999) 123-45-67', 'email': 'ivan.petrov@email.com', 'birth': '1990-01-15',
             'address': 'Москва, ул. Тверская, 15, кв. 45'},
            {'first': 'Мария', 'last': 'Сидорова', 'middle': 'Петровна', 'passport': '9876 543210',
             'phone': '+7 (999) 765-43-21', 'email': 'maria.sidorova@email.com', 'birth': '1992-05-20',
             'address': 'Санкт-Петербург, Невский пр., 45, кв. 12'},
            {'first': 'Алексей', 'last': 'Иванов', 'middle': 'Сергеевич', 'passport': '4567 890123',
             'phone': '+7 (999) 555-66-77', 'email': 'alexey.ivanov@email.com', 'birth': '1988-10-10',
             'address': 'Казань, ул. Баумана, 25, кв. 8'},
            {'first': 'Екатерина', 'last': 'Смирнова', 'middle': 'Андреевна', 'passport': '2345 678901',
             'phone': '+7 (999) 234-56-78', 'email': 'ekaterina.smirnova@email.com', 'birth': '1991-03-25',
             'address': 'Екатеринбург, ул. Ленина, 50, кв. 15'},
            {'first': 'Дмитрий', 'last': 'Кузнецов', 'middle': 'Владимирович', 'passport': '3456 789012',
             'phone': '+7 (999) 345-67-89', 'email': 'dmitry.kuznetsov@email.com', 'birth': '1985-07-12',
             'address': 'Новосибирск, Красный пр., 120, кв. 30'},
            {'first': 'Анна', 'last': 'Морозова', 'middle': 'Дмитриевна', 'passport': '5678 901234',
             'phone': '+7 (999) 456-78-90', 'email': 'anna.morozova@email.com', 'birth': '1993-12-05',
             'address': 'Ростов-на-Дону, ул. Большая Садовая, 85, кв. 7'},
            {'first': 'Сергей', 'last': 'Волков', 'middle': 'Павлович', 'passport': '6789 012345',
             'phone': '+7 (999) 567-89-01', 'email': 'sergey.volkov@email.com', 'birth': '1987-09-18',
             'address': 'Самара, ул. Ленинградская, 32, кв. 5'},
            {'first': 'Ольга', 'last': 'Соколова', 'middle': 'Игоревна', 'passport': '7890 123456',
             'phone': '+7 (999) 678-90-12', 'email': 'olga.sokolova@email.com', 'birth': '1994-02-28',
             'address': 'Нижний Новгород, ул. Большая Покровская, 15, кв. 23'},
            {'first': 'Павел', 'last': 'Михайлов', 'middle': 'Алексеевич', 'passport': '8901 234567',
             'phone': '+7 (999) 789-01-23', 'email': 'pavel.mikhailov@email.com', 'birth': '1986-11-08',
             'address': 'Челябинск, ул. Кирова, 100, кв. 42'},
            {'first': 'Наталья', 'last': 'Федорова', 'middle': 'Викторовна', 'passport': '9012 345678',
             'phone': '+7 (999) 890-12-34', 'email': 'natalia.fedorova@email.com', 'birth': '1995-06-17',
             'address': 'Красноярск, пр. Мира, 75, кв. 10'}
        ]

        for cl in clients:
            # Проверяем уникальность email и паспорта
            if not Client.query.filter_by(email=cl['email']).first() and not Client.query.filter_by(
                    passport_number=cl['passport']).first():
                client = Client(
                    first_name=cl['first'],
                    last_name=cl['last'],
                    middle_name=cl['middle'],
                    passport_number=cl['passport'],
                    passport_issued='УФМС России',
                    passport_date=date(2020, 1, 1),
                    phone=cl['phone'],
                    email=cl['email'],
                    birth_date=datetime.strptime(cl['birth'], '%Y-%m-%d').date(),
                    address=cl['address'],
                    registration_date=date.today()
                )
                db.session.add(client)

        db.session.commit()

        print("=" * 60)
        print("БАЗА ДАННЫХ УСПЕШНО ИНИЦИАЛИЗИРОВАНА!")
        print("=" * 60)
        print(f"Стран: {Country.query.count()}")
        print(f"Отелей: {Hotel.query.count()}")
        print(f"Сотрудников: {Employee.query.count()}")
        print(f"Клиентов: {Client.query.count()}")
        print("=" * 60)
        print("Бронирования и платежи добавляются через интерфейс")
        print("=" * 60)


# API для аналитики
@app.route('/api/popular_country')
def popular_country():
    """Самая популярная страна за текущий месяц"""
    today = date.today()
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)

    # Получаем все подтвержденные бронирования за текущий месяц
    bookings = Booking.query.filter(
        Booking.booking_date >= month_start,
        Booking.booking_date < month_end,
        Booking.booking_status == 'confirmed'
    ).all()

    # Считаем бронирования по странам
    country_counts = {}
    for booking in bookings:
        if booking.hotel and booking.hotel.country:
            country_name = booking.hotel.country.country_name
            country_counts[country_name] = country_counts.get(country_name, 0) + 1

    if not country_counts:
        return jsonify({'error': 'Нет бронирований за текущий месяц'})

    # Находим самую популярную страну
    popular = max(country_counts.items(), key=lambda x: x[1])

    return jsonify({
        'country': popular[0],
        'bookings_count': popular[1],
        'month': today.strftime('%B %Y')
    })


@app.route('/api/top_client_year')
def top_client_year():
    """Клиент, потративший больше всего денег в текущем году"""
    current_year = date.today().year
    year_start = date(current_year, 1, 1)
    year_end = date(current_year, 12, 31)

    # Получаем все ПОДТВЕРЖДЕННЫЕ бронирования за текущий год
    bookings = Booking.query.filter(
        Booking.booking_date >= year_start,
        Booking.booking_date <= year_end,
        Booking.booking_status == 'confirmed'
    ).all()

    # Считаем траты по клиентам
    client_spending = {}
    for booking in bookings:
        client_id = booking.client_id
        client_name = f"{booking.client.last_name} {booking.client.first_name}"
        if booking.client.middle_name:
            client_name += f" {booking.client.middle_name}"

        if client_id not in client_spending:
            client_spending[client_id] = {
                'name': client_name,
                'total': 0,
                'bookings_count': 0,
                'phone': booking.client.phone,
                'email': booking.client.email
            }
        client_spending[client_id]['total'] += booking.total_price
        client_spending[client_id]['bookings_count'] += 1

    if not client_spending:
        return jsonify({'error': 'Нет бронирований в текущем году'})

    # Находим клиента с максимальными тратами
    top_client = max(client_spending.values(), key=lambda x: x['total'])

    return jsonify({
        'year': current_year,
        'client': top_client['name'],
        'total_spent': top_client['total'],
        'bookings_count': top_client['bookings_count'],
        'phone': top_client['phone'],
        'email': top_client['email']
    })


@app.route('/api/employee_stats')
def employee_stats():
    """Статистика по сотрудникам"""
    employees = Employee.query.all()
    stats = []

    for emp in employees:
        # Считаем ТОЛЬКО подтвержденные бронирования
        confirmed_bookings = Booking.query.filter_by(
            employee_id=emp.employee_id,
            booking_status='confirmed'
        ).all()

        # Сумма всех подтвержденных бронирований
        total_sales = sum(b.total_price for b in confirmed_bookings)
        bookings_count = len(confirmed_bookings)

        # Общая комиссия
        total_commission = total_sales * (emp.commission_rate / 100)

        stats.append({
            'id': emp.employee_id,
            'name': f"{emp.last_name} {emp.first_name}",
            'position': emp.position,
            'commission_rate': emp.commission_rate,
            'total_bookings': Booking.query.filter_by(employee_id=emp.employee_id).count(),  # все бронирования
            'confirmed_bookings': bookings_count,  # только подтвержденные
            'total_sales': total_sales,
            'total_commission': total_commission
        })

    return jsonify(stats)


# Маршруты для добавления данных через формы
@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        try:
            print("Получены данные формы:", request.form)  # Отладка

            # Проверяем обязательные поля
            required_fields = ['first_name', 'last_name', 'passport_number', 'phone', 'birth_date']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'Поле {field} обязательно для заполнения', 'error')
                    return redirect(url_for('add_client'))

            # Проверяем уникальность паспорта
            existing_client = Client.query.filter_by(passport_number=request.form['passport_number']).first()
            if existing_client:
                flash('Клиент с таким номером паспорта уже существует', 'error')
                return redirect(url_for('add_client'))

            # Проверяем уникальность email если он указан
            email = request.form.get('email', '').strip()
            if email:
                existing_client = Client.query.filter_by(email=email).first()
                if existing_client:
                    flash('Клиент с таким email уже существует', 'error')
                    return redirect(url_for('add_client'))
                email = email if email else None

            # Обработка даты рождения
            try:
                birth_date = datetime.strptime(request.form['birth_date'], '%Y-%m-%d').date()
            except ValueError:
                flash('Некорректный формат даты рождения', 'error')
                return redirect(url_for('add_client'))

            # Обработка даты выдачи паспорта (необязательно)
            passport_date = None
            if request.form.get('passport_date'):
                try:
                    passport_date = datetime.strptime(request.form['passport_date'], '%Y-%m-%d').date()
                except ValueError:
                    passport_date = None

            # Создаем клиента
            client = Client(
                first_name=request.form['first_name'].strip(),
                last_name=request.form['last_name'].strip(),
                middle_name=request.form.get('middle_name', '').strip() or None,
                passport_number=request.form['passport_number'].strip(),
                passport_issued=request.form.get('passport_issued', 'УФМС России').strip(),
                passport_date=passport_date,
                phone=request.form['phone'].strip(),
                email=email,
                birth_date=birth_date,
                address=request.form.get('address', '').strip() or None
            )

            db.session.add(client)
            db.session.commit()
            flash(f'Клиент {client.last_name} {client.first_name} успешно добавлен!', 'success')

        except Exception as e:
            db.session.rollback()
            print(f"Ошибка при добавлении клиента: {str(e)}")  # Отладка
            flash(f'Ошибка при добавлении клиента: {str(e)}', 'error')

        return redirect(url_for('index'))

    return render_template('add_client.html')


@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        try:
            employee = Employee(
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                position=request.form.get('position', 'Турагент'),
                phone=request.form.get('phone', ''),
                email=request.form.get('email', ''),
                hire_date=datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date() if request.form.get(
                    'hire_date') else datetime.now().date(),
                commission_rate=float(request.form.get('commission_rate', 5.0)),
                is_active=True
            )
            db.session.add(employee)
            db.session.commit()
            flash('Сотрудник успешно добавлен', 'success')
        except Exception as e:
            flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('index'))

    return render_template('add_employee.html')


@app.route('/add_booking', methods=['GET', 'POST'])
def add_booking():
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            client_id = int(request.form['client_id'])
            hotel_id = int(request.form['hotel_id'])
            employee_id = int(request.form['employee_id']) if request.form.get('employee_id') else None

            check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
            check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
            room_type = request.form['room_type']

            # Получаем отель для расчета стоимости
            hotel = Hotel.query.get(hotel_id)
            nights = (check_out - check_in).days
            daily_rate = hotel.get_rate_by_room_type(room_type)
            total_price = daily_rate * nights

            # Создаем бронирование
            booking = Booking(
                client_id=client_id,
                hotel_id=hotel_id,
                employee_id=employee_id,
                check_in_date=check_in,
                check_out_date=check_out,
                adults_count=int(request.form['adults_count']),
                children_count=int(request.form.get('children_count', 0)),
                room_type=room_type,
                nights_count=nights,
                daily_rate=daily_rate,
                total_price=total_price,
                paid_amount=0,
                booking_status='pending',  # Статус ожидания
                payment_status='unpaid',
                special_requests=request.form.get('special_requests', '')
            )

            db.session.add(booking)
            db.session.flush()
            booking.booking_number = booking.generate_booking_number()
            db.session.commit()

            flash(f'Бронирование создано! Номер: {booking.booking_number}', 'success')
        except Exception as e:
            flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('index'))

    # GET запрос - показываем форму
    clients = Client.query.all()
    hotels = Hotel.query.all()
    employees = Employee.query.filter_by(is_active=True).all()

    return render_template('add_booking.html',
                           clients=clients,
                           hotels=hotels,
                           employees=employees)


@app.route('/add_payment', methods=['GET', 'POST'])
def add_payment():
    if request.method == 'POST':
        try:
            booking_id = int(request.form['booking_id'])
            booking = Booking.query.get(booking_id)

            # Сотрудник берется из бронирования
            payment = Payment(
                booking_id=booking_id,
                client_id=booking.client_id,
                employee_id=booking.employee_id,
                payment_amount=float(request.form['payment_amount']),
                payment_method=request.form['payment_method'],
                payment_purpose=request.form.get('payment_purpose', ''),
                payment_status='completed'
            )

            db.session.add(payment)
            db.session.flush()
            payment.payment_number = payment.generate_payment_number()

            # Обновляем оплаченную сумму в бронировании
            booking.paid_amount += payment.payment_amount

            # Обновляем статус оплаты
            if booking.paid_amount >= booking.total_price:
                booking.payment_status = 'paid'
                # Если оплачено полностью, меняем статус бронирования на confirmed
                booking.booking_status = 'confirmed'
            elif booking.paid_amount > 0:
                booking.payment_status = 'partial'
                # Если есть хотя бы частичная оплата, тоже считаем подтвержденным
                booking.booking_status = 'confirmed'

            db.session.commit()

            employee_name = f"{booking.employee.last_name} {booking.employee.first_name}" if booking.employee else "Не назначен"

            flash(f'Платеж успешно добавлен! Бронирование подтверждено. Сотрудник: {employee_name} получит комиссию',
                  'success')
        except Exception as e:
            flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('index'))

    # GET запрос
    bookings = Booking.query.all()
    bookings_with_debt = []
    for b in bookings:
        remaining = b.remaining_payment()
        if remaining > 0:
            employee_info = f"{b.employee.last_name} {b.employee.first_name}" if b.employee else "Не назначен"
            bookings_with_debt.append({
                'booking': b,
                'remaining': remaining,
                'employee_name': employee_info
            })

    return render_template('add_payment.html', bookings_with_debt=bookings_with_debt)


# API маршруты
@app.route('/api/clients')
def api_clients():
    clients = Client.query.all()
    return jsonify([{
        'id': c.client_id,
        'first_name': c.first_name,
        'last_name': c.last_name,
        'middle_name': c.middle_name,
        'passport': c.passport_number,
        'phone': c.phone,
        'email': c.email,
        'birth_date': str(c.birth_date) if c.birth_date else None,
        'address': c.address
    } for c in clients])


@app.route('/api/countries')
def api_countries():
    countries = Country.query.all()
    return jsonify([{
        'id': c.country_id,
        'name': c.country_name,
        'code': c.country_code,
        'visa_required': c.visa_required,
        'currency': c.currency,
        'language': c.language
    } for c in countries])


@app.route('/api/hotels')
def api_hotels():
    hotels = Hotel.query.all()
    return jsonify([{
        'id': h.hotel_id,
        'name': h.hotel_name,
        'country_id': h.country_id,
        'country_name': h.country.country_name if h.country else None,
        'city': h.city_name,
        'stars': h.stars,
        'facilities': h.facilities,
        'rates': {
            'Standard': h.standard_rate,
            'Deluxe': h.deluxe_rate,
            'Suite': h.suite_rate,
            'Family': h.family_rate
        }
    } for h in hotels])


@app.route('/api/employees')
def api_employees():
    employees = Employee.query.all()
    return jsonify([{
        'id': e.employee_id,
        'first_name': e.first_name,
        'last_name': e.last_name,
        'position': e.position,
        'phone': e.phone,
        'email': e.email,
        'hire_date': str(e.hire_date) if e.hire_date else None,
        'commission_rate': e.commission_rate,
        'is_active': e.is_active
    } for e in employees])


@app.route('/api/bookings')
def api_bookings():
    bookings = Booking.query.all()
    return jsonify([{
        'id': b.booking_id,
        'number': b.booking_number,
        'client': f"{b.client.last_name} {b.client.first_name}" if b.client else None,
        'hotel': b.hotel.hotel_name if b.hotel else None,
        'country': b.hotel.country.country_name if b.hotel and b.hotel.country else None,
        'employee': f"{b.employee.last_name} {b.employee.first_name}" if b.employee else "Не назначен",
        'employee_id': b.employee.employee_id if b.employee else None,
        'check_in': str(b.check_in_date),
        'check_out': str(b.check_out_date),
        'nights': b.nights_count,
        'adults': b.adults_count,
        'children': b.children_count,
        'room': b.room_type,
        'daily_rate': b.daily_rate,
        'total': b.total_price,
        'paid': b.paid_amount,
        'remaining': b.remaining_payment(),
        'commission': b.commission_amount(),
        'status': b.booking_status,
        'payment_status': b.payment_status
    } for b in bookings])


@app.route('/api/payments')
def api_payments():
    payments = Payment.query.all()
    return jsonify([{
        'id': p.payment_id,
        'number': p.payment_number,
        'booking': p.booking.booking_number if p.booking else None,
        'client': f"{p.client.last_name} {p.client.first_name}" if p.client else None,
        'employee': f"{p.employee.last_name} {p.employee.first_name}" if p.employee else "Не назначен",
        'employee_id': p.employee.employee_id if p.employee else None,
        'date': str(p.payment_date),
        'amount': p.payment_amount,
        'method': p.payment_method,
        'purpose': p.payment_purpose
    } for p in payments])


@app.route('/api/calculate_price', methods=['POST'])
def calculate_price():
    """API для расчета стоимости бронирования"""
    try:
        data = request.json
        hotel_id = data.get('hotel_id')
        check_in = datetime.strptime(data.get('check_in'), '%Y-%m-%d').date()
        check_out = datetime.strptime(data.get('check_out'), '%Y-%m-%d').date()
        room_type = data.get('room_type')

        hotel = Hotel.query.get(hotel_id)
        if not hotel:
            return jsonify({'error': 'Отель не найден'}), 404

        nights = (check_out - check_in).days
        if nights <= 0:
            return jsonify({'error': 'Некорректные даты'}), 400

        daily_rate = hotel.get_rate_by_room_type(room_type)
        total_price = daily_rate * nights

        return jsonify({
            'nights': nights,
            'daily_rate': daily_rate,
            'total_price': total_price
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
