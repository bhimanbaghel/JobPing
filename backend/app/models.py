from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users' # sticking to common convention
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(100), nullable = True)
    email = db.Column(db.String(255), unique = True, nullable = False)
    password_hash = db.Column(db.String(256), nullable = False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    failed_login_attempts = db.Column(db.Integer, default = 0, nullable = False)

    def __repr__(self):
        return f'<User {self.email}>'
