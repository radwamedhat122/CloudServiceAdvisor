import sqlite3
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "Processed_AmazonData.csv"
DB_PATH = BASE_DIR / "ui" / "web_app" / "cloud_web.db"

st.set_page_config(
    page_title="Cloud Service Advisor",
    page_icon="☁️",
    layout="wide"
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'User',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL,
        app_type TEXT NOT NULL,
        budget REAL NOT NULL,
        storage_type TEXT NOT NULL,
        need_ai INTEGER NOT NULL DEFAULT 0,
        need_database INTEGER NOT NULL DEFAULT 0,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(created_by) REFERENCES users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        provider TEXT,
        service_model TEXT,
        compute_service TEXT,
        storage_service TEXT,
        estimated_cost TEXT,
        dataset_summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """)

    conn.commit()
    conn.close()


def register_user(full_name, username, email, password):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO users (full_name, username, email, password, role)
        VALUES (?, ?, ?, ?, ?)
        """, (
            full_name.strip(),
            username.strip(),
            email.strip().lower(),
            hash_password(password),
            "User"
        ))

        conn.commit()
        return True, "Account created successfully."

    except sqlite3.IntegrityError:
        return False, "Username or email already exists."

    except Exception as error:
        return False, str(error)

    finally:
        conn.close()


def login_user(username_or_email, password):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM users
    WHERE LOWER(username) = ?
    OR LOWER(email) = ?
    """, (
        username_or_email.strip().lower(),
        username_or_email.strip().lower()
    ))

    user = cursor.fetchone()
    conn.close()

    if not user:
        return False, "Invalid username/email or password."

    if user["password"] != hash_password(password):
        return False, "Invalid username/email or password."

    return True, dict(user)


@st.cache_data
def load_dataset():
    if not DATA_PATH.exists():
        return None

    df = pd.read_csv(DATA_PATH)

    required_columns = [
        "Provider",
        "Service Model",
        "Instance Type",
        "Instance Family",
        "vCPU",
        "Memory",
        "Storage",
        "Location",
        "Operating System",
        "Network Performance",
        "PricePerUnit"
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            "Missing columns in Processed_AmazonData.csv: "
            + ", ".join(missing_columns)
        )

    df["PricePerUnit"] = pd.to_numeric(df["PricePerUnit"], errors="coerce")
    df["vCPU"] = pd.to_numeric(df["vCPU"], errors="coerce")
    df["Memory"] = pd.to_numeric(df["Memory"], errors="coerce")

    df = df.dropna(subset=[
        "Provider",
        "Service Model",
        "Instance Type",
        "Instance Family",
        "vCPU",
        "Memory",
        "PricePerUnit"
    ])

    return df


def add_project(project_name, app_type, budget, storage_type, need_ai, need_database, user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO projects (
        project_name,
        app_type,
        budget,
        storage_type,
        need_ai,
        need_database,
        created_by
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        project_name,
        app_type,
        budget,
        storage_type,
        1 if need_ai else 0,
        1 if need_database else 0,
        user_id
    ))

    conn.commit()
    conn.close()


def get_my_projects(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE created_by = ?
    ORDER BY id DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_project_by_id(project_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM projects
    WHERE id = ?
    AND created_by = ?
    """, (project_id, user_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return dict(row)


def filter_dataset_by_project(df, project):
    filtered = df.copy()

    budget_filtered = filtered[filtered["PricePerUnit"] <= float(project["budget"])]

    if not budget_filtered.empty:
        filtered = budget_filtered

    storage_type = str(project["storage_type"]).lower()
    storage_column = filtered["Storage"].astype(str).str.lower()

    if storage_type == "block":
        storage_filtered = filtered[
            storage_column.str.contains("ebs", na=False)
            | storage_column.str.contains("ssd", na=False)
            | storage_column.str.contains("nvme", na=False)
        ]

        if not storage_filtered.empty:
            filtered = storage_filtered

    elif storage_type == "object":
        storage_filtered = filtered[
            storage_column.str.contains("storage", na=False)
            | storage_column.str.contains("hdd", na=False)
            | storage_column.str.contains("ssd", na=False)
            | storage_column.str.contains("ebs", na=False)
        ]

        if not storage_filtered.empty:
            filtered = storage_filtered

    elif storage_type == "file":
        storage_filtered = filtered[
            storage_column.str.contains("file", na=False)
            | storage_column.str.contains("efs", na=False)
            | storage_column.str.contains("ebs", na=False)
        ]

        if not storage_filtered.empty:
            filtered = storage_filtered

    family_column = filtered["Instance Family"].astype(str).str.lower()

    if project["need_ai"]:
        ai_filtered = filtered[
            family_column.str.contains("gpu", na=False)
            | family_column.str.contains("compute", na=False)
            | family_column.str.contains("accelerated", na=False)
        ]

        if not ai_filtered.empty:
            filtered = ai_filtered

    if project["need_database"]:
        database_filtered = filtered[
            family_column.str.contains("memory", na=False)
            | family_column.str.contains("general", na=False)
        ]

        if not database_filtered.empty:
            filtered = database_filtered

    filtered = filtered.sort_values(
        by=["PricePerUnit", "vCPU", "Memory"],
        ascending=[True, False, False]
    )

    return filtered


def generate_recommendation(project):
    df = load_dataset()

    if df is None:
        return False, "Processed dataset file not found. Please add data/Processed_AmazonData.csv.", None

    filtered = filter_dataset_by_project(df, project)

    if filtered.empty:
        return False, "No matching row found in the processed dataset.", None

    selected = filtered.iloc[0]

    result = {
        "provider": str(selected["Provider"]),
        "service_model": str(selected["Service Model"]),
        "compute_service": str(selected["Instance Type"]),
        "storage_service": str(selected["Storage"]),
        "estimated_cost": str(selected["PricePerUnit"]),
        "dataset_summary": (
            f"Provider: {selected['Provider']} | "
            f"Service Model: {selected['Service Model']} | "
            f"Instance Type: {selected['Instance Type']} | "
            f"Instance Family: {selected['Instance Family']} | "
            f"vCPU: {selected['vCPU']} | "
            f"Memory: {selected['Memory']} GiB | "
            f"Storage: {selected['Storage']} | "
            f"Location: {selected['Location']} | "
            f"Operating System: {selected['Operating System']} | "
            f"Network Performance: {selected['Network Performance']} | "
            f"Price Per Unit: {selected['PricePerUnit']}"
        )
    }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO recommendations (
        project_id,
        provider,
        service_model,
        compute_service,
        storage_service,
        estimated_cost,
        dataset_summary
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        project["id"],
        result["provider"],
        result["service_model"],
        result["compute_service"],
        result["storage_service"],
        result["estimated_cost"],
        result["dataset_summary"]
    ))

    conn.commit()
    conn.close()

    return True, "Recommendation generated successfully.", result


def get_my_recommendations(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        r.id,
        p.project_name,
        r.provider,
        r.service_model,
        r.compute_service,
        r.storage_service,
        r.estimated_cost,
        r.created_at
    FROM recommendations r
    INNER JOIN projects p ON r.project_id = p.id
    WHERE p.created_by = ?
    ORDER BY r.id DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def logout():
    st.session_state["user"] = None
    st.session_state["page"] = "login"
    st.rerun()


def show_login_page():
    st.title("☁️ Cloud Service Advisor")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        st.subheader("Login to continue")

        username_or_email = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if not username_or_email or not password:
                st.error("Please enter username/email and password.")
                return

            success, result = login_user(username_or_email, password)

            if success:
                st.session_state["user"] = result
                st.session_state["page"] = "dashboard"
                st.rerun()
            else:
                st.error(result)

    with tab_signup:
        st.subheader("Create New Account")

        full_name = st.text_input("Full Name")
        username = st.text_input("New Username")
        email = st.text_input("Email")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        if st.button("Create Account"):
            if not full_name or not username or not email or not new_password or not confirm_password:
                st.error("Please fill all fields.")
                return

            if new_password != confirm_password:
                st.error("Passwords do not match.")
                return

            success, message = register_user(full_name, username, email, new_password)

            if success:
                st.success(message)
                st.info("Now go to the Login tab and login with your account.")
            else:
                st.error(message)


def show_dashboard():
    user = st.session_state["user"]

    st.sidebar.title("☁️ Cloud Service Advisor")
    st.sidebar.write(f"Welcome, {user['full_name']}")

    page = st.sidebar.radio(
        "Menu",
        ["Dashboard", "My Projects", "My Recommendations"]
    )

    if st.sidebar.button("Logout"):
        logout()

    if page == "Dashboard":
        st.title("My Dashboard")
        st.write("This is your personal dashboard.")

        projects = get_my_projects(user["id"])
        recommendations = get_my_recommendations(user["id"])

        col1, col2 = st.columns(2)
        col1.metric("My Projects", len(projects))
        col2.metric("My Recommendations", len(recommendations))

    elif page == "My Projects":
        st.title("My Projects")

        with st.form("add_project_form"):
            st.subheader("Add New Project")

            project_name = st.text_input("Project Name")
            app_type = st.selectbox(
                "Application Type",
                ["Web Application", "Mobile Application", "Enterprise System", "Other"]
            )
            budget = st.number_input("Budget", min_value=0.0, step=1.0)
            storage_type = st.selectbox("Storage Type", ["Block", "Object", "File"])
            need_ai = st.checkbox("Need AI / ML")
            need_database = st.checkbox("Need Database")

            submitted = st.form_submit_button("Add Project")

            if submitted:
                if not project_name:
                    st.error("Project name is required.")
                else:
                    add_project(
                        project_name,
                        app_type,
                        budget,
                        storage_type,
                        need_ai,
                        need_database,
                        user["id"]
                    )
                    st.success("Project added successfully.")
                    st.rerun()

        st.subheader("Your Projects")
        projects = get_my_projects(user["id"])

        if projects:
            st.dataframe(projects, use_container_width=True)
        else:
            st.info("No projects yet.")

    elif page == "My Recommendations":
        st.title("My Recommendations")

        projects = get_my_projects(user["id"])

        if not projects:
            st.warning("Please add a project first.")
            return

        project_options = {
            f"{project['id']} - {project['project_name']}": project["id"]
            for project in projects
        }

        selected_project_label = st.selectbox(
            "Select Project",
            list(project_options.keys())
        )

        selected_project_id = project_options[selected_project_label]

        if st.button("Generate Recommendation"):
            project = get_project_by_id(selected_project_id, user["id"])

            success, message, result = generate_recommendation(project)

            if success:
                st.success(message)

                st.subheader("Recommendation Result")
                st.write(f"**Provider:** {result['provider']}")
                st.write(f"**Service Model:** {result['service_model']}")
                st.write(f"**Compute Service:** {result['compute_service']}")
                st.write(f"**Storage Service:** {result['storage_service']}")
                st.write(f"**Estimated Cost:** {result['estimated_cost']}")
                st.write(f"**Dataset Match:** {result['dataset_summary']}")
            else:
                st.error(message)

        st.subheader("Saved Recommendations History")
        recommendations = get_my_recommendations(user["id"])

        if recommendations:
            st.dataframe(recommendations, use_container_width=True)
        else:
            st.info("No recommendations yet.")


init_database()

if "user" not in st.session_state:
    st.session_state["user"] = None

if "page" not in st.session_state:
    st.session_state["page"] = "login"

if st.session_state["user"] is None:
    show_login_page()
else:
    show_dashboard()