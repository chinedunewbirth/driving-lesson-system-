"""add lesson_reschedule refund and booking_package models

Revision ID: 17ed7910b477
Revises: caec02cff6b7
Create Date: 2026-03-23 13:01:27.600783

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '17ed7910b477'
down_revision = 'caec02cff6b7'
branch_labels = None
depends_on = None


def upgrade():
    # Only create the 3 new tables; other tables/columns already exist in production
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'booking_package' not in existing_tables:
        op.create_table('booking_package',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('instructor_id', sa.Integer(), nullable=False),
        sa.Column('total_lessons', sa.Integer(), nullable=False),
        sa.Column('lessons_used', sa.Integer(), nullable=True),
        sa.Column('price_per_lesson', sa.Float(), nullable=False),
        sa.Column('discount_percent', sa.Float(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
        sa.Column('payment_status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['instructor_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    if 'lesson_reschedule' not in existing_tables:
        op.create_table('lesson_reschedule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('requested_by_id', sa.Integer(), nullable=False),
        sa.Column('old_date', sa.Date(), nullable=False),
        sa.Column('old_time', sa.Time(), nullable=False),
        sa.Column('new_date', sa.Date(), nullable=False),
        sa.Column('new_time', sa.Time(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lesson_id'], ['lesson.id'], ),
        sa.ForeignKeyConstraint(['requested_by_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    if 'refund' not in existing_tables:
        op.create_table('refund',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('stripe_refund_id', sa.String(length=255), nullable=True),
        sa.Column('processed_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['lesson_id'], ['lesson.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payment.id'], ),
        sa.ForeignKeyConstraint(['processed_by_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )

    # Conditionally add columns that may already exist
    for table, columns in [
        ('instructor_profile', [
            ('address', sa.String(length=255)),
            ('latitude', sa.Float()),
            ('longitude', sa.Float()),
            ('service_radius_km', sa.Float()),
            ('phone', sa.String(length=20)),
        ]),
        ('lesson', [
            ('pickup_address', sa.String(length=255)),
            ('pickup_lat', sa.Float()),
            ('pickup_lng', sa.Float()),
        ]),
        ('student_profile', [
            ('address', sa.String(length=255)),
            ('test_passed', sa.Boolean()),
            ('test_passed_date', sa.Date()),
        ]),
    ]:
        if table in existing_tables:
            existing_cols = [c['name'] for c in inspector.get_columns(table)]
            with op.batch_alter_table(table, schema=None) as batch_op:
                for col_name, col_type in columns:
                    if col_name not in existing_cols:
                        batch_op.add_column(sa.Column(col_name, col_type, nullable=True))

    # Create other tables that may not exist yet
    for tbl_name, tbl_def in [
        ('instructor_availability', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('instructor_id', sa.Integer(), nullable=True),
            sa.Column('day_of_week', sa.Integer(), nullable=True),
            sa.Column('start_time', sa.Time(), nullable=True),
            sa.Column('end_time', sa.Time(), nullable=True),
        ]),
        ('notification_preference', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('email_enabled', sa.Boolean(), nullable=True),
            sa.Column('whatsapp_enabled', sa.Boolean(), nullable=True),
            sa.Column('notify_lesson_booked', sa.Boolean(), nullable=True),
            sa.Column('notify_lesson_cancelled', sa.Boolean(), nullable=True),
            sa.Column('notify_feedback', sa.Boolean(), nullable=True),
            sa.Column('notify_payment', sa.Boolean(), nullable=True),
            sa.Column('notify_skill_update', sa.Boolean(), nullable=True),
        ]),
        ('skill_progress', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('skill_key', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('instructor_id', sa.Integer(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('notes', sa.String(length=255), nullable=True),
        ]),
        ('lesson_feedback', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('lesson_id', sa.Integer(), nullable=False),
            sa.Column('instructor_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('rating', sa.Integer(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('strengths', sa.Text(), nullable=True),
            sa.Column('areas_to_improve', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        ]),
        ('payment', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('lesson_id', sa.Integer(), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(length=3), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('payment_method', sa.String(length=50), nullable=True),
            sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        ]),
    ]:
        if tbl_name not in existing_tables:
            op.create_table(tbl_name, *tbl_def, sa.PrimaryKeyConstraint('id'))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('student_profile', schema=None) as batch_op:
        batch_op.drop_column('test_passed_date')
        batch_op.drop_column('test_passed')
        batch_op.drop_column('address')

    with op.batch_alter_table('lesson', schema=None) as batch_op:
        batch_op.drop_column('pickup_lng')
        batch_op.drop_column('pickup_lat')
        batch_op.drop_column('pickup_address')

    with op.batch_alter_table('instructor_profile', schema=None) as batch_op:
        batch_op.drop_column('phone')
        batch_op.drop_column('service_radius_km')
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
        batch_op.drop_column('address')

    op.drop_table('refund')
    op.drop_table('payment')
    op.drop_table('lesson_reschedule')
    op.drop_table('lesson_feedback')
    op.drop_table('skill_progress')
    op.drop_table('notification_preference')
    op.drop_table('instructor_availability')
    op.drop_table('booking_package')
    # ### end Alembic commands ###
