"""
database.py — manages all interactions with the SQLite database.

A database is an organized way to store and retrieve data. We use SQLite,
which stores everything in a single file (resume.db) — no server needed.

This file is organized as a class called `database`.
"""

import sqlite3
import csv
import os
from io import StringIO

# Path to the SQLite database file
DB_PATH = 'flask_app/database/resume.db'

# Tables must be created in this order because of foreign key relationships.
TABLE_ORDER = [
    'institutions',
    'positions',
    'experiences',
    'skills',
    'llm_roles'
]


class database:
    """
    Manages all interactions with the SQLite resume database.
    """

    def __init__(self):
        """
        Store the path to the database file.
        """
        self.db_path = DB_PATH

    # ------------------------------------------------------------------
    # CORE QUERY FUNCTION
    # ------------------------------------------------------------------

    def query(self, sql, params=()):
        """
        Execute any SQL statement and return results as a list of dicts.

        Args:
            sql    (str): The SQL statement to run.
            params (tuple): Values to safely substitute into the SQL.

        Returns:
            list: A list of dicts for SELECT queries; empty list otherwise.
        """

        connection = sqlite3.connect(self.db_path)

        # Enable SQLite foreign key enforcement
        connection.execute("PRAGMA foreign_keys = ON")

        # Allow access to columns by name
        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()
        cursor.execute(sql, params)

        results = []

        if sql.strip().upper().startswith(('SELECT', 'PRAGMA')):
            results = [dict(row) for row in cursor.fetchall()]

        connection.commit()
        connection.close()

        return results

    # ------------------------------------------------------------------
    # TABLE SETUP
    # ------------------------------------------------------------------

    def createTables(self, purge=False):
        """
        Create all database tables and load initial data from CSV files.

        Args:
            purge (bool): If True, drop existing tables first.
        """

        # Create the database directory if it does not exist
        os.makedirs(
            os.path.dirname(self.db_path),
            exist_ok=True
        )

        # Purge existing tables if requested
        if purge:
            for table in reversed(TABLE_ORDER):
                self.query(f"DROP TABLE IF EXISTS {table}")

        # Create each table from its SQL schema
        for table in TABLE_ORDER:
            sql_path = f'flask_app/database/create_tables/{table}.sql'

            if not os.path.exists(sql_path):
                print(f"Warning: SQL file not found: {sql_path}")
                continue

            with open(sql_path, 'r', encoding='utf-8') as file:
                sql = file.read()

            self.query(sql)

        # Load initial CSV data
        for table in TABLE_ORDER:
            csv_path = f'flask_app/database/initial_data/{table}.csv'

            if not os.path.exists(csv_path):
                print(f"Warning: CSV file not found: {csv_path}")
                continue

            with open(
                csv_path,
                'r',
                encoding='utf-8',
                newline=''
            ) as file:
                reader = csv.DictReader(file)
                rows = list(reader)

            if not rows:
                continue

            columns = list(rows[0].keys())

            for row in rows:
                values = []

                for column in columns:
                    value = row[column]

                    # Convert empty CSV fields to None
                    if value == '':
                        value = None

                    # Convert numeric IDs / skill levels to integers
                    elif column.endswith('_id') or column == 'skill_level':
                        try:
                            value = int(value)
                        except (ValueError, TypeError):
                            pass

                    values.append(value)

                placeholders = ', '.join(['?'] * len(values))

                sql = (
                    f"INSERT INTO {table} "
                    f"({', '.join(columns)}) "
                    f"VALUES ({placeholders})"
                )

                try:
                    self.query(sql, tuple(values))
                except Exception as error:
                    print(
                        f"Error loading data into {table}: {error}"
                    )

            print(f"Loaded data for table: {table}")

    # ------------------------------------------------------------------
    # RESUME DATA
    # ------------------------------------------------------------------

    def getResumeData(self):
        """
        Return the complete resume data in the nested format expected
        by resume.html.

        Structure:

        {
            inst_id: {
                institution fields...,
                "positions": {
                    position_id: {
                        position fields...,
                        "experiences": {
                            experience_id: {
                                experience fields...,
                                "skills": {
                                    skill_id: {
                                        skill fields...
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        # --------------------------------------------------------------
        # Load all records
        # --------------------------------------------------------------

        institutions = self.query(
            """
            SELECT *
            FROM institutions
            ORDER BY inst_id
            """
        )

        positions = self.query(
            """
            SELECT *
            FROM positions
            ORDER BY position_id
            """
        )

        experiences = self.query(
            """
            SELECT *
            FROM experiences
            ORDER BY experience_id
            """
        )

        skills = self.query(
            """
            SELECT *
            FROM skills
            ORDER BY skill_id
            """
        )

        # --------------------------------------------------------------
        # Build the nested structure
        # --------------------------------------------------------------

        resume = {}

        # --------------------------------------------------------------
        # Institutions
        # --------------------------------------------------------------

        for institution in institutions:
            inst_id = institution['inst_id']

            resume[inst_id] = dict(institution)

            # Each institution contains its positions
            resume[inst_id]['positions'] = {}

        # --------------------------------------------------------------
        # Positions
        # --------------------------------------------------------------

        for position in positions:
            position_id = position['position_id']
            inst_id = position['inst_id']

            # Make sure the parent institution exists
            if inst_id not in resume:
                continue

            resume[inst_id]['positions'][position_id] = dict(position)

            # Remove the foreign key from the nested display object
            # It is no longer needed inside the template.
            resume[inst_id]['positions'][position_id]['experiences'] = {}

        # --------------------------------------------------------------
        # Experiences
        # --------------------------------------------------------------

        for experience in experiences:
            experience_id = experience['experience_id']
            position_id = experience['position_id']

            # Find the position that owns this experience
            position_found = None

            for institution in resume.values():
                if position_id in institution['positions']:
                    position_found = institution['positions'][position_id]
                    break

            if position_found is None:
                continue

            position_found['experiences'][experience_id] = dict(experience)

            # Each experience contains its skills
            position_found['experiences'][experience_id]['skills'] = {}

        # --------------------------------------------------------------
        # Skills
        # --------------------------------------------------------------

        for skill in skills:
            skill_id = skill['skill_id']
            experience_id = skill['experience_id']

            # Find the experience that owns this skill
            experience_found = None

            for institution in resume.values():
                for position in institution['positions'].values():
                    if experience_id in position['experiences']:
                        experience_found = position['experiences'][experience_id]
                        break

                if experience_found is not None:
                    break

            if experience_found is None:
                continue

            experience_found['skills'][skill_id] = dict(skill)

        return resume

    # ------------------------------------------------------------------
    # RESUME TEXT
    # ------------------------------------------------------------------

    def getResumeText(self):
        """
        Return the resume content as plain text.

        This text is used as background context for the Content Expert.
        """

        resume_data = self.getResumeData()

        lines = []

        # Institutions
        lines.append("INSTITUTIONS:")

        for inst_id, institution in resume_data.items():
            lines.append(
                f"- {institution.get('name', '')}"
            )

        # Positions
        lines.append("")
        lines.append("POSITIONS:")

        for inst_id, institution in resume_data.items():

            for position_id, position in institution.get(
                'positions',
                {}
            ).items():

                lines.append(
                    f"- {position.get('title', '')} "
                    f"at {institution.get('name', '')}: "
                    f"{position.get('responsibilities', '')}"
                )

        # Experiences
        lines.append("")
        lines.append("EXPERIENCES:")

        for institution in resume_data.values():

            for position in institution.get(
                'positions',
                {}
            ).values():

                for experience in position.get(
                    'experiences',
                    {}
                ).values():

                    lines.append(
                        f"- {experience.get('name', '')}: "
                        f"{experience.get('description', '')}"
                    )

        # Skills
        lines.append("")
        lines.append("SKILLS:")

        for institution in resume_data.values():

            for position in institution.get(
                'positions',
                {}
            ).values():

                for experience in position.get(
                    'experiences',
                    {}
                ).values():

                    for skill in experience.get(
                        'skills',
                        {}
                    ).values():

                        lines.append(
                            f"- {skill.get('name', '')} "
                            f"(level {skill.get('skill_level', '')})"
                        )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM ROLES
    # ------------------------------------------------------------------

    def getLLMRoles(self):
        """
        Return every row of llm_roles as a dictionary keyed by role name.

        Example:
            {
                "Database Read Expert": {
                    "role": "Database Read Expert",
                    "domain": "...",
                    ...
                }
            }
        """

        rows = self.query("SELECT * FROM llm_roles")

        return {
            row['role']: row
            for row in rows
        }

    # ------------------------------------------------------------------
    # INSERT ROWS
    # ------------------------------------------------------------------

    def insertRows(self, table, columns, values):
        """
        Insert one row into a database table.

        Any value that starts with "(SELECT" is inserted directly into
        the SQL. This allows the Database Write Expert to resolve
        foreign keys using a SELECT query.

        Example:

            "(SELECT experience_id FROM experiences
              WHERE name = 'MSU Research')"
        """

        value_sql = []
        bound_params = []

        for value in values:

            # Foreign-key lookup expressions are inserted directly
            if (
                isinstance(value, str)
                and value.strip().startswith("(SELECT")
            ):
                value_sql.append(value)

            else:
                value_sql.append("?")
                bound_params.append(value)

        sql = (
            f"INSERT INTO {table} "
            f"({', '.join(columns)}) "
            f"VALUES ({', '.join(value_sql)})"
        )

        self.query(sql, tuple(bound_params))

