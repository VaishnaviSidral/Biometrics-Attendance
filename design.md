SYSTEM REQUIREMENT (FINAL – CLEAR VERSION)
🎯 Objective

Build a biometric attendance + WFO compliance system that clearly separates:

Attendance tracking (who came to office)

Policy compliance (who followed company WFO rules)

🧩 Core Concepts
1) Attendance (Reality)

Represents physical presence in office.

Daily Attendance Status

PRESENT → employee was in office (any non-zero time)

ABSENT → employee was not in office (0 time)

This is based only on biometric logs.

2) Compliance (Policy Rule)

Represents whether company rules were followed.

Weekly Compliance Status

COMPLIANT

NON_COMPLIANT

This is based on:

Work mode (WFO / HYBRID / WFH)

Company settings

Weekly hours + days logic

🧑‍💼 Employee Work Modes
Work Mode	Policy Meaning
WFO	Must follow full WFO policy
HYBRID	Must follow partial WFO policy
WFH	Exempted from WFO policy
⚙️ Dynamic Settings (from DB)

These values control compliance logic:

expected_hours_per_day → e.g. 9 hours

wfo_days_per_week → e.g. 5 days

hybrid_days_per_week → e.g. 3 days

📐 Business Rules
✅ Attendance Rules (Daily)
If total_office_minutes > 0:
    daily_status = PRESENT
Else:
    daily_status = ABSENT


Presence ≠ Compliance

✅ Compliance Rules (Weekly)
For WFO employee:
required_days = settings.wfo_days_per_week
required_hours_per_day = settings.expected_hours_per_day

required_weekly_minutes = required_days * required_hours_per_day * 60

If total_weekly_minutes >= required_weekly_minutes:
    compliance = COMPLIANT
Else:
    compliance = NON_COMPLIANT

For HYBRID employee:
required_days = settings.hybrid_days_per_week
required_hours_per_day = settings.expected_hours_per_day

required_weekly_minutes = required_days * required_hours_per_day * 60

If total_weekly_minutes >= required_weekly_minutes:
    compliance = COMPLIANT
Else:
    compliance = NON_COMPLIANT

For WFH employee:
compliance = EXEMPTED
(always compliant, not counted in compliance stats)

📊 Manager Dashboard Requirements

For selected week:

Cards:

Total Employees
→ all employees

Total Non-Exempted Employees
→ employees where:

work_mode IN (WFO, HYBRID)


Total Employees Compliant to WFO Policy
→ employees where:

compliance_status = COMPLIANT


Total Employees Non-Compliant to WFO Policy
→ employees where:

compliance_status = NON_COMPLIANT

🖱 Click Behavior

Each card is clickable:

Total Employees →

List all employees

Non-Exempted Employees →

Only WFO + HYBRID employees

Compliant Employees →

Employees with COMPLIANT status

Non-Compliant Employees →

Employees with NON_COMPLIANT status

Each list shows:

name

work_mode

total hours

wfo_days achieved

required_days

compliance %

compliance_status

attendance summary

🧱 Data Model Requirement
daily_attendance
employee_code
date
total_office_minutes
daily_status (PRESENT/ABSENT)

weekly_summary
employee_code
week_start
week_end
total_office_minutes
required_minutes
compliance_percentage
compliance_status (COMPLIANT/NON_COMPLIANT/EXEMPTED)
work_mode

🔄 Logic Separation (IMPORTANT)
Layer	Purpose
Attendance Engine	Presence detection
Compliance Engine	Policy validation
Reports	Only use compliance data
Daily Views	Use attendance data