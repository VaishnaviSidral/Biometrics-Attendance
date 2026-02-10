# Biometrics Attendance System - Setup Guide

This guide will help you set up the Biometrics Attendance System on a new machine. The project consists of a Python FastAPI backend and a React frontend.

## Prerequisites

- **Python 3.8+**
- **Node.js 16+** and **npm**

---

## 1. Backend Setup

The backend handles the API, database, and logic.

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    ```

3.  **Activate the virtual environment:**
    - On Linux/macOS:
        ```bash
        source venv/bin/activate
        ```
    - On Windows:
        ```bash
        .\venv\Scripts\activate
        ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    
    *Dependencies installed:*
    - `fastapi` (Web framework)
    - `uvicorn` (ASGI server)
    - `sqlalchemy` (Database ORM)
    - `pandas` & `openpyxl` (Excel processing)
    - `python-multipart` (File uploads)
    - ...and others.

5.  **Configure Environment Variables:**
    - Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    - The default configuration uses **MySQL**. If you wish to use MySQL, proceed to the **Database Setup** section below.
    - If you prefer **SQLite** (no installation required), edit `.env` and follow the instructions inside.

6.  **Run the Backend Server:**
    ```bash
    python3 main.py
    ```
    The server will start at `http://localhost:8000`.

---

## 2. Database Setup (MySQL)

This project uses MySQL by default. Follow these steps to set it up locally:

1.  **Install MySQL Server** (if not already installed):
    - On Ubuntu/Debian:
        ```bash
        sudo apt update
        sudo apt install mysql-server
        ```
    - On Windows: Download and install the [MySQL Installer](https://dev.mysql.com/downloads/installer/).

2.  **Access MySQL Shell:**
    ```bash
    sudo mysql -u root -p
    ```

3.  **Create Database and User:**
    Run the following SQL commands in the MySQL shell:
    ```sql
    -- Create the database
    CREATE DATABASE attendance_db;

    -- Create a dedicated user
    CREATE USER 'attendance_user'@'localhost' IDENTIFIED BY 'attendance_pass';

    -- Grant privileges
    GRANT ALL PRIVILEGES ON attendance_db.* TO 'attendance_user'@'localhost';

    -- Apply changes
    FLUSH PRIVILEGES;

    -- Exit
    EXIT;
    ```

4.  **Verify Configuration:**
    Ensure your `backend/.env` file has the correct `DATABASE_URL`:
    ```
    DATABASE_URL="mysql+pymysql://attendance_user:attendance_pass@localhost:3306/attendance_db"
    ```

---

## 3. Frontend Setup

The frontend provides the user interface.

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```
    
    *Dependencies installed:*
    - `react`, `react-dom` (Core framework)
    - `react-router-dom` (Navigation)
    - `lucide-react` (Icons)
    - `recharts` (Charts)
    - `vite` (Build tool)

3.  **Run the Frontend Development Server:**
    ```bash
    npm run dev
    ```
    The application will be accessible at `http://localhost:5173`.

---

## 4. Using the Application

1.  Open your browser and navigate to `http://localhost:5173`.
2.  **Admin Settings:** Go to the **Settings** page to configure:
    - WFO/WFH days per week
    - Expected hours per day
    - Minimum hours to be marked PRESENT
    - Compliance thresholds
3.  **Upload Data:** Go to the **Upload Data** page to upload your biometrics attendance Excel file. This will process the data based on your current settings.

## Troubleshooting

- **Database Issues:** If you encounter database errors, delete the `backend/attendance.db` file and restart the backend server. It will recreate the database automatically.
- **Port Conflicts:** Ensure ports `8000` (backend) and `5173` (frontend) are free.
