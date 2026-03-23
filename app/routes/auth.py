from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import User, InstructorProfile, StudentProfile
from app.forms import LoginForm, RegistrationForm
from app.notifications import notify_user

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))
        login_user(user)
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('auth/login.html', title='Sign In', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if request.method == 'GET' and request.args.get('role') in ('instructor', 'student'):
        form.role.data = request.args.get('role')
    if form.validate_on_submit():
        try:
            user = User(username=form.username.data, email=form.email.data, role=form.role.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            if form.role.data == 'instructor':
                profile = InstructorProfile(user_id=user.id, address=form.location.data)
                db.session.add(profile)
                db.session.commit()
            elif form.role.data == 'student':
                profile = StudentProfile(user_id=user.id, address=form.location.data)
                db.session.add(profile)
                db.session.commit()

            flash('Congratulations, you are now registered!')

            # Send welcome notification (non-blocking — don't roll back user on failure)
            try:
                notify_user(user, 'welcome', **{
                    'username': user.username,
                    'role': form.role.data.title(),
                    'email': user.email,
                    'login_url': url_for('auth.login', _external=True),
                })
            except Exception:
                pass  # Notification failure should not affect registration

            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}')
            return redirect(url_for('auth.register'))
    return render_template('auth/register.html', title='Register', form=form)
