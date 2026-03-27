from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import User, InstructorProfile, StudentProfile
from app.forms import LoginForm, RegistrationForm
from app.notifications import notify_user, send_email
from app.oauth import oauth
import secrets
from datetime import datetime

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
        if not user.email_confirmed:
            flash('Please confirm your email address before logging in. '
                  'Check your inbox or request a new confirmation link.',
                  'warning')
            return redirect(url_for('auth.resend_confirmation'))
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

            # Build full address from form fields
            address_parts = filter(None, [
                form.address_line1.data,
                form.address_line2.data,
                form.city.data,
                form.county.data,
                form.postcode.data,
            ])
            full_address = ', '.join(address_parts) or None

            if form.role.data == 'instructor':
                profile = InstructorProfile(user_id=user.id, address=full_address)
                db.session.add(profile)
                db.session.commit()
            elif form.role.data == 'student':
                profile = StudentProfile(user_id=user.id, address=full_address)
                db.session.add(profile)
                db.session.commit()

            # Send confirmation email
            try:
                token = user.generate_confirmation_token()
                confirm_url = url_for('auth.confirm_email', token=token, _external=True)
                send_email(user.email, 'email_confirm', **{
                    'username': user.username,
                    'confirm_url': confirm_url,
                })
            except Exception:
                pass  # Email failure should not block registration

            flash('Registration successful! A confirmation link has been sent to your email. '
                  'Please check your inbox to activate your account.', 'info')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}')
            return redirect(url_for('auth.register'))
    return render_template('auth/register.html', title='Register', form=form)


@bp.route('/confirm/<token>')
def confirm_email(token):
    user = User.verify_confirmation_token(token)
    if user is None:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.login'))
    if user.email_confirmed:
        flash('Your email is already confirmed. Please log in.', 'info')
        return redirect(url_for('auth.login'))
    user.email_confirmed = True
    user.confirmed_at = datetime.utcnow()
    db.session.commit()

    # Send welcome notification now that the account is confirmed
    try:
        notify_user(user, 'welcome', **{
            'username': user.username,
            'role': user.role.title(),
            'email': user.email,
            'login_url': url_for('auth.login', _external=True),
        })
    except Exception:
        pass

    flash('Your email has been confirmed! You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/resend-confirmation', methods=['GET', 'POST'])
def resend_confirmation():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email:
            user = User.query.filter_by(email=email).first()
            if user and not user.email_confirmed:
                try:
                    token = user.generate_confirmation_token()
                    confirm_url = url_for('auth.confirm_email', token=token, _external=True)
                    send_email(user.email, 'email_confirm', **{
                        'username': user.username,
                        'confirm_url': confirm_url,
                    })
                except Exception:
                    pass
        # Always show the same message to prevent email enumeration
        flash('If an account with that email exists and is unconfirmed, '
              'a new confirmation link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/resend_confirmation.html', title='Resend Confirmation')


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if email:
            user = User.query.filter_by(email=email).first()
            if user:
                try:
                    token = user.generate_reset_token()
                    reset_url = url_for('auth.reset_password', token=token, _external=True)
                    send_email(user.email, 'password_reset', **{
                        'username': user.username,
                        'reset_url': reset_url,
                    })
                except Exception:
                    pass
        # Always show the same message to prevent email enumeration
        flash('If an account with that email exists, a password reset link has been sent. '
              'Please check your inbox.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html', title='Forgot Password')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('auth/reset_password.html', title='Reset Password', token=token)
        if password != password2:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', title='Reset Password', token=token)
        user.set_password(password)
        db.session.commit()
        flash('Your password has been reset. You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', title='Reset Password', token=token)


# ── Helper: handle OAuth user (login or auto-register) ──────
def _handle_oauth_user(email, name, provider):
    """Find existing user or create new account from OAuth profile, then log in."""
    user = User.query.filter_by(email=email).first()

    if user is None:
        # Auto-register with a unique username derived from email/name
        base_username = (name or email.split('@')[0]).replace(' ', '_').lower()
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f'{base_username}_{counter}'
            counter += 1

        # Default role is student; user can change later or pick during OAuth
        role = session.pop('oauth_role', 'student')
        user = User(username=username, email=email, role=role)
        # Set a random password (user authenticated via OAuth, not password)
        user.set_password(secrets.token_urlsafe(32))
        # OAuth providers verify email, so mark as confirmed
        user.email_confirmed = True
        user.confirmed_at = datetime.utcnow()
        db.session.add(user)
        db.session.commit()

        # Create role-specific profile
        if role == 'instructor':
            db.session.add(InstructorProfile(user_id=user.id))
        else:
            db.session.add(StudentProfile(user_id=user.id))
        db.session.commit()

        flash(f'Account created via {provider}! Welcome, {username}.')

        try:
            notify_user(user, 'welcome', **{
                'username': user.username,
                'role': role.title(),
                'email': user.email,
                'login_url': url_for('auth.login', _external=True),
            })
        except Exception:
            pass
    else:
        flash(f'Signed in with {provider}!')

    login_user(user)

    if user.role == 'instructor':
        return redirect(url_for('instructor.dashboard'))
    elif user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('student.dashboard'))


# ── Google OAuth ─────────────────────────────────────────────
@bp.route('/login/google')
def login_google():
    if not current_app.config.get('GOOGLE_CLIENT_ID'):
        flash('Google login is not configured.')
        return redirect(url_for('auth.login'))
    # Preserve role choice if coming from register page
    role = request.args.get('role')
    if role in ('instructor', 'student'):
        session['oauth_role'] = role
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route('/login/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo') or oauth.google.userinfo()
        email = user_info.get('email')
        name = user_info.get('name', '')
        if not email:
            flash('Could not retrieve email from Google.')
            return redirect(url_for('auth.login'))
        return _handle_oauth_user(email, name, 'Google')
    except Exception as e:
        current_app.logger.error(f'Google OAuth error: {e}')
        flash('Google sign-in failed. Please try again.')
        return redirect(url_for('auth.login'))


# ── GitHub OAuth ─────────────────────────────────────────────
@bp.route('/login/github')
def login_github():
    if not current_app.config.get('GITHUB_CLIENT_ID'):
        flash('GitHub login is not configured.')
        return redirect(url_for('auth.login'))
    role = request.args.get('role')
    if role in ('instructor', 'student'):
        session['oauth_role'] = role
    redirect_uri = url_for('auth.github_callback', _external=True)
    return oauth.github.authorize_redirect(redirect_uri)


@bp.route('/login/github/callback')
def github_callback():
    try:
        token = oauth.github.authorize_access_token()
        resp = oauth.github.get('user', token=token)
        profile = resp.json()
        email = profile.get('email')

        # GitHub may hide the email — fetch from /user/emails
        if not email:
            emails_resp = oauth.github.get('user/emails', token=token)
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get('primary') and e.get('verified')), None)
            email = primary['email'] if primary else None

        if not email:
            flash('Could not retrieve email from GitHub. Make sure your email is public or verified.')
            return redirect(url_for('auth.login'))

        name = profile.get('login', '')
        return _handle_oauth_user(email, name, 'GitHub')
    except Exception as e:
        current_app.logger.error(f'GitHub OAuth error: {e}')
        flash('GitHub sign-in failed. Please try again.')
        return redirect(url_for('auth.login'))


# ── Microsoft OAuth (Outlook / Hotmail / Live) ───────────────
@bp.route('/login/microsoft')
def login_microsoft():
    if not current_app.config.get('MICROSOFT_CLIENT_ID'):
        flash('Microsoft login is not configured.')
        return redirect(url_for('auth.login'))
    role = request.args.get('role')
    if role in ('instructor', 'student'):
        session['oauth_role'] = role
    redirect_uri = url_for('auth.microsoft_callback', _external=True)
    return oauth.microsoft.authorize_redirect(redirect_uri)


@bp.route('/login/microsoft/callback')
def microsoft_callback():
    try:
        token = oauth.microsoft.authorize_access_token()
        user_info = token.get('userinfo') or oauth.microsoft.userinfo()
        email = user_info.get('email') or user_info.get('preferred_username')
        name = user_info.get('name', '')
        if not email:
            flash('Could not retrieve email from Microsoft.')
            return redirect(url_for('auth.login'))
        return _handle_oauth_user(email, name, 'Microsoft')
    except Exception as e:
        current_app.logger.error(f'Microsoft OAuth error: {e}')
        flash('Microsoft sign-in failed. Please try again.')
        return redirect(url_for('auth.login'))
