from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    email = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(50), nullable=False)  # 'PIC' or 'Reviewer'
    password_hash = db.Column(db.String(200), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.name}>"

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    incharge = db.Column(db.String(120), nullable=True)

    def __repr__(self):
        return f"<Trade {self.name}>"

class Explanation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=True)
    data_json = db.Column(db.Text, nullable=True)  # parsed excel as JSON
    status = db.Column(db.String(50), default='Submitted')  # Submitted, Reviewed, Needs Changes
    reviewer_comments = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    trade = db.relationship('Trade', backref=db.backref('explanations', lazy=True))
    user = db.relationship('User', backref=db.backref('explanations', lazy=True))

    def set_data_from_dfs(self, dfs):
        # `dfs` is a dict of sheet_name -> pandas.DataFrame
        out = {}
        for name, df in dfs.items():
            try:
                out[name] = df.to_dict(orient='records')
            except Exception:
                out[name] = []
        self.data_json = json.dumps(out, default=str)

    def get_data(self):
        try:
            return json.loads(self.data_json or '{}')
        except Exception:
            return {}

    def __repr__(self):
        return f"<Explanation trade={self.trade_id} user={self.user_id}>"
