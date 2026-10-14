from flask import Flask, render_template, request, redirect, send_file, flash, session
import sqlite3
import pandas as pd
from datetime import datetime
from devices import MEDICAL_DEVICES

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_name TEXT NOT NULL,
            user_name TEXT NOT NULL,
            department TEXT NOT NULL,
            quantity_measurement TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            date_requested TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html', medical_devices=MEDICAL_DEVICES)

@app.route('/submit', methods=['POST'])
def submit():
    user_name = request.form['user_name'].title()
    department = request.form['department']
    device_names = request.form.getlist('device_name[]')
    quantity_measurements = request.form.getlist('quantity_measurement[]')
    quantities = request.form.getlist('quantity[]')

    if len(device_names) != len(quantity_measurements) or len(device_names) != len(quantities):
        flash("Invalid form data. Please ensure all fields are filled correctly.", "error")
        return redirect('/')

    conn = get_db_connection()
    try:
        for i in range(len(device_names)):
            device_name = device_names[i]
            quantity_measurement = quantity_measurements[i]
            quantity_str = quantities[i]

            if not quantity_str.strip():
                continue

            try:
                quantity = int(quantity_str)
            except ValueError:
                flash(f"Invalid quantity for device '{device_name}'. Please enter a valid number.", "error")
                conn.close()
                return redirect('/')

            date_requested = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('''
                INSERT INTO requests (device_name, user_name, department, quantity_measurement, quantity, date_requested)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (device_name, user_name, department, quantity_measurement, quantity, date_requested))

        conn.commit()
        flash("Request submitted successfully! Check the PDF file downloaded", "success")
    finally:
        conn.close()

    return redirect('/')

@app.route('/glossary')
def glossary():
    return render_template('glossary.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == 'admin' and password == 'htmadmin':
            session['admin_logged_in'] = True
            return redirect('/admin')
        else:
            flash("Invalid username or password.", "error")
            return redirect('/admin/login')

    return render_template('admin_login.html')

@app.route('/admin')
def admin():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    conn = get_db_connection()
    requests = conn.execute('SELECT * FROM requests').fetchall()
    conn.close()
    return render_template('admin.html', requests=requests)

@app.route('/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    conn = get_db_connection()
    conn.execute('DELETE FROM requests WHERE id = ?', (request_id,))
    conn.commit()
    conn.close()

    flash("Request deleted successfully!", "success")
    return redirect('/admin')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("You have been logged out.", "success")
    return redirect('/admin/login')

@app.route('/download')
def download():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    conn = get_db_connection()
    df = pd.read_sql_query('SELECT * FROM requests', conn)
    conn.close()

    mode = request.args.get('mode', '1')
    
    if mode == '1':
        df.to_excel('requests.xlsx', index=False, engine='openpyxl')
        filename = 'requests.xlsx'
    elif mode == '2':
        pivot_df = df.pivot_table(index='device_name', columns='department', values='quantity', aggfunc='sum', fill_value=0)
        pivot_df['Total'] = pivot_df.sum(axis=1)
        pivot_df.to_excel('requests_pivot.xlsx', engine='openpyxl')
        filename = 'requests_pivot.xlsx'

    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)