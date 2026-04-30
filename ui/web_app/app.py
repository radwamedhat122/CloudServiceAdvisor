import sqlite3
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[2]

DATA_PATH_OPTIONS = [
    BASE_DIR / "data" / "Processed_MultiCloud.csv",
    BASE_DIR / "Processed_MultiCloud.csv"
]

DB_PATH = Path(__file__).resolve().parent / "cloud_web_multicloud.db"


st.set_page_config(
    page_title="Cloud Service Advisor",
    page_icon="☁️",
    layout="wide"
)


def get_data_path():
    for path in DATA_PATH_OPTIONS:
        if path.exists():
            return path

    return DATA_PATH_OPTIONS[0]


DATA_PATH = get_data_path()


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
        main_service_type TEXT,
        optimization_goal TEXT,
        budget TEXT,
        expected_users TEXT,
        storage_type TEXT,
        security_level TEXT,
        need_ai TEXT,
        need_ml TEXT,
        need_serverless TEXT,
        need_vm TEXT,
        need_database TEXT,
        need_backup TEXT,
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
        service_type TEXT,
        service_id TEXT,
        edge_node_id TEXT,
        qos_score TEXT,
        response_time TEXT,
        service_latency TEXT,
        throughput TEXT,
        dataset_summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """)

    cursor.execute("PRAGMA table_info(projects)")
    existing_project_columns = [column[1] for column in cursor.fetchall()]

    required_project_columns = {
        "main_service_type": "TEXT",
        "optimization_goal": "TEXT",
        "budget": "TEXT",
        "expected_users": "TEXT",
        "storage_type": "TEXT",
        "security_level": "TEXT",
        "need_ai": "TEXT",
        "need_ml": "TEXT",
        "need_serverless": "TEXT",
        "need_vm": "TEXT",
        "need_database": "TEXT",
        "need_backup": "TEXT"
    }

    for column_name, column_type in required_project_columns.items():
        if column_name not in existing_project_columns:
            cursor.execute(
                f"ALTER TABLE projects ADD COLUMN {column_name} {column_type}"
            )

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
        "Service ID",
        "Provider",
        "Service Type",
        "Service Model",
        "Edge Node ID",
        "CPU Utilization",
        "Memory Usage",
        "Storage Usage",
        "Network Bandwidth",
        "Service Latency",
        "Response Time",
        "Throughput",
        "Load Balancing",
        "QoS Score",
        "Workload Variability",
        "Optimal Service Placement"
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing columns in Processed_MultiCloud.csv: "
            + ", ".join(missing_columns)
        )

    numeric_columns = [
        "CPU Utilization",
        "Memory Usage",
        "Storage Usage",
        "Network Bandwidth",
        "Service Latency",
        "Response Time",
        "Throughput",
        "Load Balancing",
        "QoS Score",
        "Workload Variability",
        "Optimal Service Placement"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=[
        "Service ID",
        "Provider",
        "Service Type",
        "Service Model",
        "QoS Score",
        "Service Latency",
        "Response Time",
        "Throughput",
        "Load Balancing"
    ])

    return df


def add_project(
    project_name,
    app_type,
    main_service_type,
    optimization_goal,
    budget,
    expected_users,
    storage_type,
    security_level,
    need_ai,
    need_ml,
    need_serverless,
    need_vm,
    need_database,
    need_backup,
    user_id
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO projects (
        project_name,
        app_type,
        main_service_type,
        optimization_goal,
        budget,
        expected_users,
        storage_type,
        security_level,
        need_ai,
        need_ml,
        need_serverless,
        need_vm,
        need_database,
        need_backup,
        created_by
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_name,
        app_type,
        main_service_type,
        optimization_goal,
        budget,
        expected_users,
        storage_type,
        security_level,
        "Yes" if need_ai else "No",
        "Yes" if need_ml else "No",
        "Yes" if need_serverless else "No",
        "Yes" if need_vm else "No",
        "Yes" if need_database else "No",
        "Yes" if need_backup else "No",
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

    main_service_type = str(project.get("main_service_type", "")).strip()

    if main_service_type:
        service_filtered = filtered[
            filtered["Service Type"].astype(str).str.lower()
            == main_service_type.lower()
        ]

        if not service_filtered.empty:
            filtered = service_filtered

    optimization_goal = str(project.get("optimization_goal", "")).strip()

    if optimization_goal == "Lowest Latency":
        filtered = filtered.sort_values(
            by=["Service Latency"],
            ascending=[True]
        )

    elif optimization_goal == "Fastest Response":
        filtered = filtered.sort_values(
            by=["Response Time"],
            ascending=[True]
        )

    elif optimization_goal == "Highest Throughput":
        filtered = filtered.sort_values(
            by=["Throughput"],
            ascending=[False]
        )

    elif optimization_goal == "Best Load Balancing":
        filtered = filtered.sort_values(
            by=["Load Balancing"],
            ascending=[False]
        )

    else:
        filtered = filtered.sort_values(
            by=["QoS Score"],
            ascending=[False]
        )

    return filtered


def generate_recommendation(project):
    df = load_dataset()

    if df is None:
        return False, "Processed_MultiCloud.csv was not found.", None

    filtered = filter_dataset_by_project(df, project)

    if filtered.empty:
        return False, "No matching service was found in the processed dataset.", None

    selected = filtered.iloc[0]

    result = {
        "provider": str(selected["Provider"]),
        "service_model": str(selected["Service Model"]),
        "service_type": str(selected["Service Type"]),
        "service_id": str(selected["Service ID"]),
        "edge_node_id": str(selected["Edge Node ID"]),
        "qos_score": str(selected["QoS Score"]),
        "response_time": str(selected["Response Time"]),
        "service_latency": str(selected["Service Latency"]),
        "throughput": str(selected["Throughput"]),
        "dataset_summary": (
            f"Service ID: {selected['Service ID']} | "
            f"Provider: {selected['Provider']} | "
            f"Service Type: {selected['Service Type']} | "
            f"Service Model: {selected['Service Model']} | "
            f"Edge Node: {selected['Edge Node ID']} | "
            f"CPU Utilization: {selected['CPU Utilization']} | "
            f"Memory Usage: {selected['Memory Usage']} | "
            f"Storage Usage: {selected['Storage Usage']} | "
            f"Network Bandwidth: {selected['Network Bandwidth']} | "
            f"Service Latency: {selected['Service Latency']} | "
            f"Response Time: {selected['Response Time']} | "
            f"Throughput: {selected['Throughput']} | "
            f"QoS Score: {selected['QoS Score']} | "
            f"Load Balancing: {selected['Load Balancing']} | "
            f"Workload Variability: {selected['Workload Variability']} | "
            f"Optimal Service Placement: {selected['Optimal Service Placement']}"
        )
    }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO recommendations (
        project_id,
        provider,
        service_model,
        service_type,
        service_id,
        edge_node_id,
        qos_score,
        response_time,
        service_latency,
        throughput,
        dataset_summary
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project["id"],
        result["provider"],
        result["service_model"],
        result["service_type"],
        result["service_id"],
        result["edge_node_id"],
        result["qos_score"],
        result["response_time"],
        result["service_latency"],
        result["throughput"],
        result["dataset_summary"]
    ))

    conn.commit()
    conn.close()

    return True, "Recommendation generated successfully from the processed Kaggle dataset.", result


def get_my_recommendations(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        r.id,
        p.project_name,
        r.provider,
        r.service_model,
        r.service_type,
        r.service_id,
        r.qos_score,
        r.response_time,
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

            success, message = register_user(
                full_name,
                username,
                email,
                new_password
            )

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
                [
                    "Web Application",
                    "Mobile Application",
                    "Enterprise System",
                    "AI Application",
                    "Data System",
                    "Other"
                ]
            )

            main_service_type = st.selectbox(
                "Main Required Service",
                [
                    "Compute",
                    "Storage",
                    "Database",
                    "AI Model",
                    "Network"
                ]
            )

            optimization_goal = st.selectbox(
                "Optimization Goal",
                [
                    "Best QoS",
                    "Lowest Latency",
                    "Fastest Response",
                    "Highest Throughput",
                    "Best Load Balancing"
                ]
            )

            budget = st.text_input("Budget")
            expected_users = st.text_input("Expected Users")

            storage_type = st.selectbox(
                "Storage Type",
                [
                    "Block",
                    "Object",
                    "File"
                ]
            )

            security_level = st.selectbox(
                "Security Level",
                [
                    "Low",
                    "Medium",
                    "High"
                ]
            )

            need_ai = st.checkbox("Need AI")
            need_ml = st.checkbox("Need Machine Learning")
            need_serverless = st.checkbox("Need Serverless")
            need_vm = st.checkbox("Need VM")
            need_database = st.checkbox("Need Database")
            need_backup = st.checkbox("Need Backup")

            submitted = st.form_submit_button("Add Project")

            if submitted:
                if not project_name:
                    st.error("Project name is required.")
                else:
                    add_project(
                        project_name,
                        app_type,
                        main_service_type,
                        optimization_goal,
                        budget,
                        expected_users,
                        storage_type,
                        security_level,
                        need_ai,
                        need_ml,
                        need_serverless,
                        need_vm,
                        need_database,
                        need_backup,
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
            (
                f"{project['id']} - {project['project_name']} "
                f"({project.get('main_service_type', 'Unknown')} - "
                f"{project.get('optimization_goal', 'Best QoS')})"
            ): project["id"]
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
                st.write(f"**Service Type:** {result['service_type']}")
                st.write(f"**Service ID:** {result['service_id']}")
                st.write(f"**Edge Node ID:** {result['edge_node_id']}")
                st.write(f"**QoS Score:** {result['qos_score']}")
                st.write(f"**Service Latency:** {result['service_latency']}")
                st.write(f"**Response Time:** {result['response_time']}")
                st.write(f"**Throughput:** {result['throughput']}")
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

if st.session_state["user"] is None:
    show_login_page()
else:
    show_dashboard()
