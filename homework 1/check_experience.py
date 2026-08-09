from flask_app import create_app

app, socketio = create_app()

with app.app_context():
    import flask_app.routes as routes

    rows = routes.db.query("""
        SELECT
            experience_id,
            position_id,
            name,
            description
        FROM experiences
        ORDER BY experience_id
    """)

    print("\n=== Experiences ===")

    for row in rows:
        print(
            f"ID: {row['experience_id']} | "
            f"Position: {row['position_id']} | "
            f"Name: {row['name']}"
        )