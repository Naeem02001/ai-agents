from flask_app import create_app

app, socketio = create_app()

with app.app_context():
    import flask_app.routes as routes

    skills = routes.db.query("""
        SELECT
            s.skill_id,
            s.name,
            s.skill_level,
            e.name AS experience
        FROM skills s
        JOIN experiences e
            ON s.experience_id = e.experience_id
        WHERE e.name = 'Smart Home IoT System'
        ORDER BY s.skill_id
    """)

    print("\n=== Skills for Smart Home IoT System ===")

    for skill in skills:
        print(
            f"ID: {skill['skill_id']} | "
            f"Skill: {skill['name']} | "
            f"Level: {skill['skill_level']} | "
            f"Experience: {skill['experience']}"
        )