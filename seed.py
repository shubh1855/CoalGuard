# seed.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db, Site, ComplianceItem, Inspection, CorrectiveAction, Contractor, Violation, AlertLog
from datetime import datetime, timedelta
import random

init_db()
db = SessionLocal()

# Clear existing data
db.query(AlertLog).delete()
db.query(Violation).delete()
db.query(CorrectiveAction).delete()
db.query(Inspection).delete()
db.query(ComplianceItem).delete()
db.query(Contractor).delete()
db.query(Site).delete()
db.commit()

sites_data = [
    {"name": "Jharia Colliery", "location": "Jharkhand", "latitude": 23.75, "longitude": 86.42, "subsidiary": "BCCL"},
    {"name": "Singareni Mine Block A", "location": "Telangana", "latitude": 18.02, "longitude": 79.97, "subsidiary": "SCCL"},
    {"name": "Korba Central", "location": "Chhattisgarh", "latitude": 22.36, "longitude": 82.68, "subsidiary": "SECL"},
]

sites = []
for s in sites_data:
    site = Site(**s)
    db.add(site)
    db.flush()
    sites.append(site)

regulations = [
    ("Safety", "Mines Act 1952 - Sec 22", "Monthly safety inspection by manager"),
    ("Safety", "Mines Act 1952 - Sec 45", "First aid equipment check"),
    ("Labour", "Minimum Wages Act", "Wage register update"),
    ("Environment", "Environment Protection Act - Rule 14", "Dust control measures check"),
    ("Production", "Coal Mines Regulations 2017 - Rule 88", "Quarterly production report"),
    ("Safety", "DGMS Circular 2019", "PPE compliance audit"),
]

statuses = ["Compliant", "Pending", "Overdue", "In Progress"]

for site in sites:
    for category, regulation, description in regulations:
        due = datetime.utcnow() + timedelta(days=random.randint(-10, 30))
        status = random.choice(statuses)
        db.add(ComplianceItem(
            site_id=site.id,
            category=category,
            regulation=regulation,
            description=description,
            due_date=due,
            status=status,
            responsible_officer=f"Officer {random.randint(1, 5)}",
        ))

inspection_types = ["Safety", "Environmental", "Labour"]
severities = ["Low", "Medium", "High", "Critical"]
observations_list = [
    "Missing hardhats observed near drill site.",
    "Drainage blocked near slope B.",
    "Overtime records not maintained.",
    "Dust suppression system inactive.",
    "Emergency exit blocked by equipment.",
]

for site in sites:
    for i in range(4):
        insp = Inspection(
            site_id=site.id,
            inspector_name=f"Inspector {random.randint(1,3)}",
            inspection_type=random.choice(inspection_types),
            date=datetime.utcnow() - timedelta(days=random.randint(0, 20)),
            latitude=site.latitude + random.uniform(-0.01, 0.01),
            longitude=site.longitude + random.uniform(-0.01, 0.01),
            observations=random.choice(observations_list),
            status=random.choice(["Open", "Closed", "Action Pending"]),
            severity=random.choice(severities),
        )
        db.add(insp)
        db.flush()
        db.add(CorrectiveAction(
            inspection_id=insp.id,
            description="Issue corrective action and monitor compliance.",
            assigned_to=f"Supervisor {random.randint(1,3)}",
            deadline=datetime.utcnow() + timedelta(days=7),
            status=random.choice(["Pending", "In Progress", "Completed"]),
        ))

    for j in range(2):
        db.add(Contractor(
            site_id=site.id,
            name=f"Contractor Co. {j+1}",
            contact=f"98{random.randint(10000000,99999999)}",
            license_number=f"LIC{random.randint(1000,9999)}",
            license_expiry=datetime.utcnow() + timedelta(days=random.randint(-5, 120)),
            compliance_status=random.choice(["Valid", "Expiring", "Expired"]),
        ))

    # Seed some violations
    violation_types = ["NO-Hardhat", "NO-Vest", "Zone Intrusion", "NO-Gloves"]
    for _ in range(5):
        db.add(Violation(
            site_id=site.id,
            worker_id=f"W{random.randint(100,999)}",
            violation_type=random.choice(violation_types),
            source="CV",
            timestamp=datetime.utcnow() - timedelta(hours=random.randint(0, 48)),
        ))

# Seed alert log
for site in sites:
    db.add(AlertLog(
        site_id=site.id,
        alert_type="Compliance",
        message=f"Overdue compliance item at {site.name}: PPE audit pending.",
        severity="High",
        channel="Dashboard",
    ))
    db.add(AlertLog(
        site_id=site.id,
        alert_type="CV Violation",
        message=f"Worker detected without hardhat at {site.name}.",
        severity="High",
        channel="Dashboard",
    ))

db.commit()
db.close()
print("Seeded.")
