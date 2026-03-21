# Database Migrations

This folder contains Alembic migration files for the driving lesson system database.

## Important: Retain Migration Files

Migration files must be retained in the repository. They provide:
- Database schema history
- Ability to rollback changes
- Consistency across deployments
- Tracking of database evolution

Do not delete or modify existing migration files. Only add new ones through the proper migration commands.

## Commands

- Create migration: `flask db migrate -m "description"`
- Apply migrations: `flask db upgrade`
- Rollback: `flask db downgrade`