# Biometric Attendance & Compliance System – Simple Implementation README

This file is for **implementation only**.
Cursor must follow this directly.
No extra logic, no over-engineering.

---

# 🎯 Goal

Build a biometric attendance system where:

* Login with email and password can be anything below this i want google oauth
* Login is done using **Google OAuth**
* User validation is done from **Redmine DB (READ ONLY)**
* Attendance + compliance system uses **Biometric DB (READ/WRITE)**
* Admin and Employees have different access
* Admin uploads biometric Excel files
* System calculates attendance + compliance automatically

---

# 🔐 Login Flow (Simple)

```
Google Sign-In
   ↓
Get user email
   ↓
Check in Redmine DB (READ ONLY)
   ↓
If email exists → allow login
Else → block login
   ↓
Check in Biometric DB
   ↓
If email in admins table → role = ADMIN
Else → role = EMPLOYEE
   ↓
Create session/JWT
```

---

# 🗄 Databases

## 1) Redmine DB (READ ONLY)

Used only for login validation.
Never write to this DB.
Never change schema.

**Connection config:**

```python
db_readonly_host = "localhost"
db_readonly_port = 3306
db_readonly_name = "redmine_readonly"
db_readonly_user = "root"
db_readonly_password = "root"
```

Used fields:

* id
* email
* firstname
* lastname

---

## 2) Biometric DB (READ/WRITE)

Used for whole system logic.

### admins table

```
id
email
is_admin
created_at
```

### employees table

```
id
name
email
work_mode   (WFO / HYBRID / WFH)
```
---

# 🧑‍💼 Admin

Admin can:

* Upload biometric Excel
* See all employees
* See dashboards
* See compliance
* Manage work_mode

---

# 🧑‍💻 Employee

Employee can:

* Login
* See own attendance
* See own compliance

---

# 📤 Excel Upload Flow

```
Admin uploads Excel
→ Read punch-in / punch-out
→ Store in punches table
→ Calculate daily hours
→ Store in attendance_daily
→ Calculate weekly compliance
→ Store in compliance_weekly
```

---

# 📊 Compliance Rules

## WFO

* 5 days office
* 45 hours/week
* 9 hours/day

## Hybrid

* 3 days office
* 27 hours/week
* 9 hours/day

## WFH

* Only tracking (rules configurable later)

---

# 📈 Status Rules

```
Compliance     >= 90%
Mid-Compliance = 60% – 89%
Non-Compliance < 60%
```

---

# 🖥 Dashboard
* For showing and calculating tab wise and mode wise calculation make the use of biometric employees where i have employee details of working mode so that we can segragate and calculate compliance based on work mode

In all employees Tab below the display grids add 3 tabs as :

* WFO - table should have Employee ,Total hours, WFO days variable/5, Expected hours,Compliance,Status
* Hybrid - table should have Employee ,Total hours, WFO days variable/3, Expected hours,Compliance,Status
* WFH - table should have Employee,Total hours,Compliance,Status should be 100% only for WFH 

---

# 🔒 Rules for Cursor

* Redmine DB is READ ONLY
* Biometric DB is READ/WRITE
* Login only via Google OAuth
* Validate user only via Redmine DB
* Role only from biometric.admins
* Employee data only from biometric.employees
* No passwords
* No local auth
* No DB merging

---

# ❌ Do NOT do

* Do not write in Redmine DB
* Do not create login tables
* Do not store passwords
* Do not hardcode roles
* Do not bypass Google OAuth

---

# ✅ Result

System will:

* Allow only Redmine users
* Give admin access to selected users
* Upload biometric data
* Auto-calculate attendance
* Auto-calculate compliance
* Show dashboards
* Replace manual Excel work

---

This file is enough for implementation.
Follow only this.
