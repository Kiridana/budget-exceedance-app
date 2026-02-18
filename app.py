import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
try:
    import pandas as pd
except ImportError:
    print("Missing dependency: pandas. Install with: pip install -r requirements.txt")
    raise

from models import db, User, Trade, Explanation
import config
from trades import TRADES

from flask_login import LoginManager, login_user, logout_user, login_required, current_user

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def create_app():
    app = Flask(__name__)
    app.config.from_object('config')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    db.init_app(app)

    # login manager
    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Initialize DB and ensure trades exist
    with app.app_context():
        db.create_all()
        for t in TRADES:
            if not Trade.query.filter_by(name=t).first():
                db.session.add(Trade(name=t))
        db.session.commit()

    @app.route('/')
    def index():
        trades = Trade.query.order_by(Trade.name).all()
        # For each trade, find the latest explanation, its deadline, and PIC
        trade_deadlines = {}
        trade_pics = {}
        for trade in trades:
            latest_expl = (
                Explanation.query.filter_by(trade_id=trade.id)
                .order_by(Explanation.uploaded_at.desc())
                .first()
            )
            trade_deadlines[trade.id] = latest_expl.deadline if latest_expl and latest_expl.deadline else None
            trade_pics[trade.id] = latest_expl.user.name if latest_expl and latest_expl.user else None
            trade_comments = locals().get('trade_comments', {})
            trade_comments[trade.id] = latest_expl.reviewer_comments if latest_expl and latest_expl.reviewer_comments else None
            trade_status = None
            if latest_expl and latest_expl.status:
                # Map status to display label
                if latest_expl.status.lower() in ['submitted', 'under review', 'needs changes', 'completed']:
                    trade_status = latest_expl.status
                elif latest_expl.status.lower() == 'reviewed':
                    trade_status = 'Under Review'
                else:
                    trade_status = latest_expl.status
            elif not latest_expl:
                trade_status = 'Not Submitted'
            trade_statuses = locals().get('trade_statuses', {})
            trade_statuses[trade.id] = trade_status or 'Submitted'
        return render_template('index.html', trades=trades, trade_deadlines=trade_deadlines, trade_pics=trade_pics, trade_statuses=trade_statuses, trade_comments=trade_comments)

    @app.route('/upload/<int:trade_id>', methods=['GET', 'POST'])
    @login_required
    def upload(trade_id):
        # only PIC or Admin can upload
        if current_user.role not in ('PIC', 'Admin'):
            flash('Only PIC or Admin can upload explanations', 'error')
            return redirect(url_for('index'))
        trade = Trade.query.get_or_404(trade_id)
        if request.method == 'POST':
            file = request.files.get('file')
            name = request.form.get('name') or 'PIC'
            deadline_str = request.form.get('deadline')
            if not file:
                flash('No file uploaded', 'error')
                return redirect(request.url)
            filename = secure_filename(file.filename)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(dest)
            # parse excel
            try:
                dfs = pd.read_excel(dest, sheet_name=None, engine='openpyxl')
            except Exception as e:
                flash('Failed to parse Excel: ' + str(e), 'error')
                return redirect(request.url)

            # create or find user by name (simplified)
            user = User.query.filter_by(name=name).first()
            if not user:
                user = User(name=name, role='PIC')
                db.session.add(user)
                db.session.commit()

            expl = Explanation(trade_id=trade.id, user_id=user.id, filename=filename)
            expl.set_data_from_dfs(dfs)
            if deadline_str:
                try:
                    expl.deadline = datetime.fromisoformat(deadline_str)
                except Exception:
                    pass
            db.session.add(expl)
            db.session.commit()
            flash('Explanation uploaded successfully', 'success')
            return redirect(url_for('index'))

        return render_template('upload.html', trade=trade)

    @app.route('/review', methods=['GET', 'POST'])
    @login_required
    def review_dashboard():
        # only Reviewer or Admin can review
        if current_user.role not in ('Reviewer', 'Admin'):
            flash('Only Reviewer or Admin can access reviews', 'error')
            return redirect(url_for('index'))
        explanations = Explanation.query.order_by(Explanation.uploaded_at.desc()).all()
        users = User.query.order_by(User.name).all()
        # Handle inline deadline or PIC assignment
        if request.method == 'POST':
            expl_id = request.form.get('expl_id')
            expl = Explanation.query.get(expl_id)
            if 'deadline' in request.form:
                deadline_str = request.form.get('deadline')
                try:
                    expl.deadline = datetime.fromisoformat(deadline_str)
                    db.session.commit()
                    flash('Deadline assigned', 'success')
                except Exception:
                    flash('Invalid deadline format', 'error')
            if 'pic_id' in request.form:
                pic_id = request.form.get('pic_id')
                user = User.query.get(pic_id)
                if user:
                    expl.user_id = user.id
                    db.session.commit()
                    flash('PIC assigned', 'success')
            return redirect(url_for('review_dashboard'))
        return render_template('reviewer.html', explanations=explanations, users=users)

    @app.route('/review/<int:explanation_id>', methods=['GET', 'POST'])
    @login_required
    def review_explanation(explanation_id):
        if current_user.role not in ('Reviewer', 'Admin'):
            flash('Only Reviewer or Admin can perform reviews', 'error')
            return redirect(url_for('review_dashboard'))
        expl = Explanation.query.get_or_404(explanation_id)
        if request.method == 'POST':
            expl.reviewer_comments = request.form.get('comments')
            expl.status = request.form.get('status') or expl.status
            deadline_str = request.form.get('deadline')
            if deadline_str:
                try:
                    expl.deadline = datetime.fromisoformat(deadline_str)
                except Exception:
                    flash('Invalid deadline format', 'error')
            db.session.commit()
            flash('Review saved', 'success')
            return redirect(url_for('review_dashboard'))
        data = expl.get_data()
        return render_template('reviewer.html', explanations=[expl], single=True, data=data)

    @app.route('/download/<int:explanation_id>')
    @login_required
    def download_explanation_file(explanation_id):
        expl = Explanation.query.get_or_404(explanation_id)
        if not expl.filename:
            flash('No file uploaded for this explanation.', 'error')
            return redirect(request.referrer or url_for('review_dashboard'))
        return send_from_directory(app.config['UPLOAD_FOLDER'], expl.filename, as_attachment=True)

    # Admin routes
    @app.route('/admin')
    @login_required
    def admin_index():
        if current_user.role != 'Admin':
            flash('Admin access only', 'error')
            return redirect(url_for('index'))
        return render_template('admin.html')

    @app.route('/admin/users', methods=['GET', 'POST'])
    @login_required
    def admin_users():
        if current_user.role != 'Admin':
            flash('Admin access only', 'error')
            return redirect(url_for('index'))
        if request.method == 'POST':
            # change role
            user_id = request.form.get('user_id')
            new_role = request.form.get('role')
            user = User.query.get(user_id)
            if user:
                user.role = new_role
                db.session.commit()
                flash('User role updated', 'success')
            return redirect(url_for('admin_users'))
        users = User.query.order_by(User.name).all()
        return render_template('admin_users.html', users=users)

    @app.route('/admin/trades', methods=['GET', 'POST'])
    @login_required
    def admin_trades():
        if current_user.role != 'Admin':
            flash('Admin access only', 'error')
            return redirect(url_for('index'))
        if request.method == 'POST':
            trade_id = request.form.get('trade_id')
            incharge = request.form.get('incharge')
            trade = Trade.query.get(trade_id)
            if trade:
                trade.incharge = incharge
                db.session.commit()
                flash('Trade incharge updated', 'success')
            return redirect(url_for('admin_trades'))
        trades = Trade.query.order_by(Trade.name).all()
        users = User.query.order_by(User.name).all()
        return render_template('admin_trades.html', trades=trades, users=users)

    # Authentication routes
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            name = request.form.get('name')
            password = request.form.get('password')
            user = User.query.filter_by(name=name).first()
            if user and user.check_password(password):
                login_user(user)
                flash('Logged in', 'success')
                return redirect(url_for('index'))
            flash('Invalid credentials', 'error')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        logout_user()
        flash('Logged out', 'success')
        return redirect(url_for('index'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            name = request.form.get('name')
            password = request.form.get('password')
            role = request.form.get('role') or 'PIC'
            if User.query.filter_by(name=name).first():
                flash('User already exists', 'error')
                return redirect(url_for('register'))
            user = User(name=name, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('User registered; please log in', 'success')
            return redirect(url_for('login'))
        return render_template('register.html')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
