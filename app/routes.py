from datetime import datetime
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.urls import url_parse
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm
from app.models import User
from app.forms import ResetPasswordRequestForm
from app.email import send_password_reset_email
from app.forms import ResetPasswordForm
import os
from werkzeug.utils import secure_filename
from app.pdf import dir_loop
from sqlalchemy.sql import func
from app.models import Items, Freight
from sqlalchemy import cast, Numeric, desc


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['pdf']


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()


@app.route('/')
@app.route('/index')
@login_required
def index():
    return render_template('index.html', title='Home')


@app.route('/', methods=['POST'])
@app.route('/index', methods=['POST'])
def upload_files():
    files = []
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        for file in request.files.getlist('file'):
            if file.filename == '':
                flash('No file selected for uploading')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                files.append(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        dir_loop(files, app.config['UPLOAD_FOLDER'])
        flash('File(s) successfully uploaded')
        return redirect('/')


@app.route('/fresh', methods=['GET'])
def fresh():
    f = db.session.query(
        Items.itm, Items.item, func.sum(Items.qty), Items.stems,
        cast(func.sum(Items.qty * Items.price) / func.sum(Items.qty), Numeric(2, 2)),
        cast(func.sum(Items.qty * Items.price) / func.sum(Items.qty) / Items.stems, Numeric(2, 2)))\
        .filter(Items.credit == 0).filter(Items.stems > 0).group_by(Items.itm)
    return render_template('fresh.html', title='Fresh', f=f)


@app.route('/freight', methods=['GET'])
@login_required
def freight():
    a = db.session.query(Freight.year, Freight.month, func.sum(Freight.price))\
        .group_by(Freight.year, Freight.month).\
        order_by(desc(Freight.year), desc(Freight.month))
    return render_template('freight.html', title='Freight', a=a)


@app.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    if request.method == 'POST':
        item = Items(request.form['invoice'], request.form['invoice-date'], request.form['year'],
                     request.form['month'], request.form['day'], request.form['source'], request.form['qty'],
                     request.form['itm'], request.form['itm'], request.form['item'], request.form['type'],
                     request.form['price'], request.form['total-price'], request.form['qty'], request.form['desc'],
                     request.form['file'])
        db.session.add(item)
        return redirect(url_for('add_item'))
    return render_template('add_item.html', title='Add Item')


@app.route('/add_freight', methods=['POST'])
@login_required
def add_freight():
    return render_template('add_freight.html', title='Add Freight')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('User added to dp-invoice.')
        return redirect(url_for('index'))
    return render_template('register.html', title='Register', form=form)


@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('user.html', user=user)


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html',
                           title='Reset Password', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)



