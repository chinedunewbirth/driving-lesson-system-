from flask import Blueprint, render_template
from app.models import User, Lesson, InstructorProfile
from sqlalchemy import func
from app import db

bp = Blueprint('main', __name__)


@bp.route('/')
@bp.route('/index')
def index():
    # Query instructor performance stats
    instructors = db.session.query(
        User.id,
        User.username,
        InstructorProfile.bio,
        InstructorProfile.hourly_rate,
        func.count(Lesson.id).label('total_lessons'),
        func.sum(
            db.case(
                (Lesson.status == 'completed', 1),
                else_=0
            )
        ).label('completed_lessons'),
        func.sum(
            db.case(
                (Lesson.status == 'completed', Lesson.duration),
                else_=0
            )
        ).label('total_minutes')
    ).join(
        InstructorProfile, User.id == InstructorProfile.user_id
    ).outerjoin(
        Lesson, User.id == Lesson.instructor_id
    ).filter(
        User.role == 'instructor'
    ).group_by(
        User.id, User.username, InstructorProfile.bio, InstructorProfile.hourly_rate
    ).all()

    instructor_data = []
    for inst in instructors:
        completed = inst.completed_lessons or 0
        total = inst.total_lessons or 0
        minutes = inst.total_minutes or 0
        instructor_data.append({
            'username': inst.username,
            'bio': inst.bio or 'Certified driving instructor',
            'hourly_rate': inst.hourly_rate or 0,
            'total_lessons': total,
            'completed_lessons': completed,
            'hours_taught': round(minutes / 60, 1),
            'completion_rate': round((completed / total * 100) if total > 0 else 0)
        })

    return render_template('index.html', title='Home', instructors=instructor_data)
