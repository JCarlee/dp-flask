from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import login
from hashlib import md5
from time import time
import jwt
from app import app


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    items = db.relationship('Items', backref='added_by', lazy='dynamic')
    freight = db.relationship('Freight', backref='added_by', lazy='dynamic')
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)


class Items(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice = db.Column(db.String(20))
    date = db.Column(db.String(50))
    year = db.Column(db.Integer)
    month = db.Column(db.Integer)
    day = db.Column(db.Integer)
    source = db.Column(db.String(100))
    qty = db.Column(db.Integer)
    itm = db.Column(db.String(10))
    item = db.Column(db.String(100))
    type = db.Column(db.String(10))
    price = db.Column(db.Float)
    price_total = db.Column(db.Float)
    taxable = db.Column(db.Boolean, default=False)
    credit = db.Column(db.Boolean, default=False)
    fresh = db.Column(db.Boolean, default=False)
    desc = db.Column(db.String(100))
    file = db.Column(db.String(100))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class PerBunch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100))
    stm = db.Column(db.Integer)


class Freight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice = db.Column(db.String(20))
    date = db.Column(db.String(50))
    year = db.Column(db.Integer)
    month = db.Column(db.Integer)
    day = db.Column(db.Integer)
    price = db.Column(db.Float)
    source = db.Column(db.String(100))
    file = db.Column(db.String(100))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login.user_loader
def load_user(id):
    return User.query.get(int(id))
