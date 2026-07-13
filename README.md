# 📦 Returns Management System

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-CC2927?style=for-the-badge&logo=databricks&logoColor=white)](https://www.sqlalchemy.org/)
[![Status](https://img.shields.io/badge/Status-Live%20in%20Production-brightgreen?style=for-the-badge)](https://andredevolucoes.pythonanywhere.com/)

> A full-featured web application for managing product return flows — from the initial request by a sales rep to final settlement by the finance team. Built with role-based access control, PDF invoice uploads, and automated status tracking.

🌐 **[Live Demo](https://andredevolucoes.pythonanywhere.com/)**

---

## 🚀 Features

- 🔐 **Authentication** with session management
- 👥 **Role-based access control**: Salesperson, Inspector, Manager, and Finance
- 📋 **Full return workflow** with trackable stages:
  `Awaiting Validation` → `Awaiting Approval` → `Awaiting Arrival` → `Awaiting Payment Settlement` → `Completed`
- 📎 **PDF invoice upload** linked to each return record
- 🔍 **Search and filters** by customer, customer invoice number, and internal invoice number
- 📊 **PDF report generation** by date range (Manager only)
- ✏️ **Edit returns** while still in the initial stage
- 🕐 **Timestamps and responsible user logged** at each workflow stage

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python + Flask | Backend framework |
| SQLAlchemy | ORM / database management |
| SQLite | Database |
| ReportLab | PDF report generation |
| Werkzeug | Password hashing & file uploads |
| Jinja2 | HTML templating |
| PythonAnywhere | Cloud hosting |

---

## 🔄 Workflow

```
New Return (Salesperson)
        ↓
Awaiting Validation (Inspector)
        ↓
Awaiting Approval (Manager)
        ↓
Awaiting Arrival (Manager)
        ↓
Awaiting Payment Settlement (Salesperson / Inspector)
        ↓
Completed (Finance)
```

---

## 👤 User Roles

| Role | Permissions |
|---|---|
| **Salesperson** | Submit returns, track status, confirm receipt |
| **Inspector** | Validate submitted returns |
| **Manager** | Approve shipments, manage users, generate PDF reports |
| **Finance** | Settle payments and finalize the process |

---

## ⚙️ Running Locally

```bash
# Clone the repository
git clone https://github.com/andregabriel-dev/devolucoes_app.git
cd devolucoes_app

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start the application
python app.py
```

Access at: `http://localhost:5000`

> On first run, the system automatically creates the database and default users.

---

## 📁 Project Structure

```
devolucoes_app/
├── app.py              # Main routes and application logic
├── models.py           # Database models (User, Return, ReturnPDF)
├── config.py           # Application configuration
├── Procfile            # Deployment configuration
├── requirements.txt    # Project dependencies
├── static/             # Static files (CSS, uploads)
├── screenshots/        # Application screenshots
└── templates/          # Jinja2 HTML templates
```

---

## 👨‍💻 Author

Developed by **André Gabriel**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/andré-gabriel-6a2333208/)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/andregabriel-dev)
