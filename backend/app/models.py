from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = 'users' # sticking to common convention
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(100), nullable = True)
    email = db.Column(db.String(255), unique = True, nullable = False)
    password_hash = db.Column(db.String(256), nullable = False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        nullable=False
    )
    failed_login_attempts = db.Column(db.Integer, default = 0, nullable = False)

    def __repr__(self):
        return f'<User {self.email}>'


class Job(db.Model):
    # Schema mirrors feature/recs-schema's jobs table so both migrations
    # converge on the same shape (whichever lands first wins; the other
    # is a no-op via "if 'jobs' not in existing" guards).
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(255), nullable=False, index=True)
    company = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(2048))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    country = db.Column(db.String(120))
    salary_usd = db.Column(db.Numeric(12, 2))
    posted_at = db.Column(db.Date)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    def __repr__(self):
        return f'<Job {self.role} @ {self.company}>'
