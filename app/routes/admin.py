from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, Lesson

bp = Blueprint('admin', __name__)

@bp.route('/admin/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin():
        flash('Access denied: Admins only.', 'danger')
        return redirect(url_for('main.index'))
    users = User.query.all()
    lessons = Lesson.query.all()
    return render_template('admin/dashboard.html', users=users, lessons=lessons)

@bp.route('/admin/users')
@login_required
def users():
    if not current_user.is_admin():
        flash('Access denied: Admins only.', 'danger')
        return redirect(url_for('main.index'))
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@bp.route('/admin/lessons')
@login_required
def lessons():
    if not current_user.is_admin():
        flash('Access denied: Admins only.', 'danger')
        return redirect(url_for('main.index'))
    lessons = Lesson.query.all()
    return render_template('admin/lessons.html', lessons=lessons)