import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'jilani.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'CHANGE-THIS-TO-A-LONG-RANDOM-SECRET-BEFORE-DEPLOYING')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ChangeMe123!')
WHATSAPP_NUMBER = ''.join(ch for ch in os.environ.get('WHATSAPP_NUMBER', '8801816615037') if ch.isdigit())
AGENCY_PHONE = os.environ.get('AGENCY_PHONE', '+880 1816-615037')
AGENCY_ADDRESS = os.environ.get('AGENCY_ADDRESS', 'নন্দনকানন, পুলিশ প্লাজা, চট্টগ্রাম')


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Umrah',
            price TEXT NOT NULL, duration TEXT DEFAULT '', departure TEXT DEFAULT '', airline TEXT DEFAULT '',
            hotel TEXT DEFAULT '', details TEXT DEFAULT '', image_url TEXT DEFAULT '', featured INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        con.execute('''CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, package_id INTEGER, customer_name TEXT NOT NULL,
            phone TEXT NOT NULL, travelers INTEGER DEFAULT 1, travel_date TEXT DEFAULT '', message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(package_id) REFERENCES packages(id))''')
        count = con.execute('SELECT COUNT(*) FROM packages').fetchone()[0]
        if count == 0:
            starter = [
                ('Economy Umrah Package', 'Umrah', 'Contact for price', '14 Days', 'Contact us for upcoming dates', 'Subject to availability', 'Makkah & Madinah hotel details on request', 'Package details and inclusions will be confirmed by our team.', 'https://images.unsplash.com/photo-1564769625905-50e93615e769?auto=format&fit=crop&w=1200&q=85', 1),
                ('Premium Umrah Package', 'Umrah', 'Contact for price', '14–21 Days', 'Contact us for upcoming dates', 'Subject to availability', 'Premium hotel options available', 'Ask us about hotel category, transport and package inclusions.', 'https://images.unsplash.com/photo-1591604129939-f1efa4d9f7fa?auto=format&fit=crop&w=1200&q=85', 1),
                ('Hajj Registration Assistance', 'Hajj', 'Contact for details', 'As per official schedule', 'Subject to official announcement', 'As announced officially', 'As per approved arrangement', 'Registration information and guidance. All dates, eligibility and fees are subject to official announcements.', 'https://images.unsplash.com/photo-1542810634-71277d95dcbb?auto=format&fit=crop&w=1200&q=85', 1),
            ]
            con.executemany('''INSERT INTO packages (title,category,price,duration,departure,airline,hotel,details,image_url,featured)
                VALUES (?,?,?,?,?,?,?,?,?,?)''', starter)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {'whatsapp_number': WHATSAPP_NUMBER, 'agency_phone': AGENCY_PHONE, 'agency_address': AGENCY_ADDRESS}


@app.route('/')
def index():
    with db() as con:
        packages = con.execute('SELECT * FROM packages ORDER BY featured DESC, id DESC').fetchall()
    return render_template('index.html', packages=packages)


@app.route('/book/<int:package_id>', methods=['GET', 'POST'])
def book(package_id):
    with db() as con:
        package = con.execute('SELECT * FROM packages WHERE id=?', (package_id,)).fetchone()
    if not package:
        abort(404)
    if request.method == 'POST':
        name = request.form.get('customer_name', '').strip()
        phone = request.form.get('phone', '').strip()
        travelers = max(1, min(50, int(request.form.get('travelers', '1') or '1')))
        travel_date = request.form.get('travel_date', '').strip()
        message = request.form.get('message', '').strip()
        if not name or not phone:
            flash('নাম ও ফোন নম্বর দিন।', 'error')
            return render_template('book.html', package=package)
        with db() as con:
            con.execute('INSERT INTO bookings (package_id,customer_name,phone,travelers,travel_date,message) VALUES (?,?,?,?,?,?)',
                        (package_id, name, phone, travelers, travel_date, message))
        text = f"Assalamu Alaikum, I want to enquire about {package['title']}. Name: {name}; Phone: {phone}; Travellers: {travelers}; Travel date: {travel_date or 'Not decided'}; Message: {message or '—'}"
        from urllib.parse import quote
        flash('আপনার অনুরোধ গ্রহণ করা হয়েছে। WhatsApp-এ মেসেজ পাঠিয়ে বুকিং নিশ্চিত করুন।', 'success')
        return redirect('https://wa.me/' + WHATSAPP_NUMBER + '?text=' + quote(text))
    return render_template('book.html', package=package)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        # Password can be supplied as plain env var for initial setup; use a strong unique value in production.
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        flash('Username অথবা password সঠিক নয়।', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    with db() as con:
        packages = con.execute('SELECT * FROM packages ORDER BY id DESC').fetchall()
        bookings = con.execute('''SELECT bookings.*, packages.title AS package_title FROM bookings
                                  LEFT JOIN packages ON packages.id=bookings.package_id ORDER BY bookings.id DESC LIMIT 100''').fetchall()
    return render_template('admin.html', packages=packages, bookings=bookings)


@app.route('/admin/packages/new', methods=['GET', 'POST'])
@app.route('/admin/packages/<int:package_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_package(package_id=None):
    with db() as con:
        package = con.execute('SELECT * FROM packages WHERE id=?', (package_id,)).fetchone() if package_id else None
    if package_id and not package:
        abort(404)
    if request.method == 'POST':
        data = [request.form.get(k, '').strip() for k in ['title','category','price','duration','departure','airline','hotel','details','image_url']]
        if not data[0] or not data[2]:
            flash('প্যাকেজের নাম ও মূল্য দিতে হবে।', 'error')
            return render_template('package_form.html', package=package)
        featured = 1 if request.form.get('featured') == 'on' else 0
        with db() as con:
            if package:
                con.execute('''UPDATE packages SET title=?,category=?,price=?,duration=?,departure=?,airline=?,hotel=?,details=?,image_url=?,featured=? WHERE id=?''', (*data, featured, package_id))
            else:
                con.execute('''INSERT INTO packages (title,category,price,duration,departure,airline,hotel,details,image_url,featured) VALUES (?,?,?,?,?,?,?,?,?,?)''', (*data, featured))
        flash('প্যাকেজ সংরক্ষণ করা হয়েছে।', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('package_form.html', package=package)


@app.route('/admin/packages/<int:package_id>/delete', methods=['POST'])
@admin_required
def delete_package(package_id):
    with db() as con:
        con.execute('DELETE FROM packages WHERE id=?', (package_id,))
    flash('প্যাকেজ মুছে ফেলা হয়েছে।', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/bookings/<int:booking_id>/delete', methods=['POST'])
@admin_required
def delete_booking(booking_id):
    with db() as con:
        con.execute('DELETE FROM bookings WHERE id=?', (booking_id,))
    flash('বুকিং রেকর্ড মুছে ফেলা হয়েছে।', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/health')
def health():
    return {'status': 'ok', 'app': 'JILANI AIR TRAVELS'}


init_db()
if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
