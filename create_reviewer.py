from app import create_app
from models import db, User

def create_reviewer(username='reviewer1', password='Review@123', email='reviewer@example.com'):
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(name=username).first()
        if user:
            print(f'User {username} already exists')
            return False
        user = User(name=username, role='Reviewer', email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f'Created reviewer: {username} / {password}')
        return True

if __name__ == '__main__':
    create_reviewer()
