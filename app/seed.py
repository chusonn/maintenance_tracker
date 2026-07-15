"""Deterministic demo data: `flask seed` (add --wipe to replace everything).

Generates a realistic-looking UK portfolio for screenshots, dev, and demos.
Seeded RNG means repeated runs produce identical data.
"""

import random
from datetime import date, timedelta

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import Contractor, Flat, MaintenanceJob

STREETS = [
    "Victoria Road", "Albert Street", "Church Lane", "High Street", "Station Road",
    "Park Avenue", "Queensway", "Mill Lane", "The Green", "Kings Road",
]
CITIES_POSTCODES = [
    ("London", "E2 7"), ("London", "N1 5"), ("London", "SE15 3"), ("Manchester", "M4 1"),
    ("Leeds", "LS6 2"), ("Bristol", "BS8 4"),
]
TENANTS = [
    "Amelia Clarke", "Oliver Bennett", "Sophie Turner", "Harry Wilson", "Isla Ahmed",
    "Jack Murphy", "Freya Campbell", "Noah Patel", "Grace Robinson", "Leo Novak",
    "Maya Okafor", "Ethan Price", "Chloe Barnes", "Daniel Kim", "Ruby Fletcher",
]
LANDLORDS = ["Hartley Estates", "Pinnacle Lettings", "J & M Properties", "Cornerstone Homes"]

CONTRACTORS = [
    ("Dave Thompson", "Thompson Plumbing & Heating", "Plumbing"),
    ("Sarah Mitchell", "Mitchell Electrical Ltd", "Electrical"),
    ("Tom O'Brien", "OB Heating Services", "HVAC"),
    ("Priya Sharma", "Sharma Property Maintenance", "General Maintenance"),
    ("Marek Kowalski", "MK Carpentry", "Carpentry"),
    ("Lisa Chen", "Chen Decorating", "Painting"),
]

JOB_TEMPLATES = [
    ("Boiler not heating water", "Tenant reports no hot water since yesterday morning.", "HVAC"),
    ("Leaking kitchen tap", "Steady drip from the cold tap, worsening this week.", "Plumbing"),
    ("Blocked bathroom drain", "Shower draining very slowly, standing water.", "Plumbing"),
    ("Faulty hallway light switch", "Switch sparks intermittently - safety concern.", "Electrical"),
    ("Broken extractor fan", "Bathroom extractor stopped, condensation building.", "Electrical"),
    ("Radiator cold in bedroom", "Radiator stays cold with heating on - needs bleeding.", "HVAC"),
    ("Mould on bathroom ceiling", "Black mould spreading around the light fitting.", "Painting"),
    ("Front door lock stiff", "Key difficult to turn, tenant worried about lockout.", "Carpentry"),
    ("Cracked windowpane", "Small crack in bedroom window after storm.", "General Maintenance"),
    ("Washing machine leaking", "Water pooling under machine during spin.", "General Maintenance"),
    ("Loose stair banister", "Banister wobbles - hazard for elderly tenant.", "Carpentry"),
    ("Repaint living room wall", "Water stain from old leak needs repainting.", "Painting"),
]

STATUS_WEIGHTS = [
    ("Completed", 55),
    ("Pending", 15),
    ("Scheduled", 12),
    ("In Progress", 10),
    ("Cancelled", 8),
]
PRIORITY_WEIGHTS = [("Low", 25), ("Medium", 45), ("High", 22), ("Urgent", 8)]


def _weighted(rng: random.Random, pairs):
    values, weights = zip(*pairs, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


def seed_data(flat_count: int = 15, job_count: int = 60) -> dict:
    rng = random.Random(42)
    today = date.today()

    contractors = []
    for name, company, specialty in CONTRACTORS:
        email = name.lower().replace(" ", ".").replace("'", "") + "@example.co.uk"
        contractor = Contractor(
            name=name, company=company, specialty=specialty, email=email,
            phone=f"07{rng.randint(100000000, 999999999)}",
        )
        db.session.add(contractor)
        contractors.append(contractor)

    flats = []
    for i in range(flat_count):
        city, pc_prefix = rng.choice(CITIES_POSTCODES)
        street = rng.choice(STREETS)
        number = rng.randint(1, 140)
        flat_no = f"{rng.randint(1, 30)}{rng.choice(['', 'A', 'B'])}"
        start = today - timedelta(days=rng.randint(60, 900))
        flat = Flat(
            flat_number=flat_no,
            payment_reference=f"PROP-{2000 + i}",
            address=f"Flat {flat_no}, {number} {street}, {city}",
            postcode=pc_prefix + "".join(rng.choices("ABDEFGHJLNPQRSTUWXYZ", k=2)),
            tenant_name=TENANTS[i % len(TENANTS)],
            tenant_contact_details=f"07{rng.randint(100000000, 999999999)}",
            rent_amount=rng.choice([950, 1100, 1250, 1400, 1600, 1850]),
            rent_due_date=rng.choice([1, 1, 5, 15, 28]),
            tenancy_start_date=start,
            tenancy_end_date=start + timedelta(days=365),
            landlord=rng.choice(LANDLORDS),
        )
        db.session.add(flat)
        flats.append(flat)

    db.session.flush()  # assign ids

    for _ in range(job_count):
        title, description, specialty = rng.choice(JOB_TEMPLATES)
        status = _weighted(rng, STATUS_WEIGHTS)
        priority = _weighted(rng, PRIORITY_WEIGHTS)
        reported = today - timedelta(days=rng.randint(0, 365))
        estimated = rng.choice([60, 80, 100, 150, 220, 300, 450])

        job = MaintenanceJob(
            flat_id=rng.choice(flats).id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            reported_date=reported,
            estimated_cost=float(estimated),
        )

        if status != "Pending":
            match = [c for c in contractors if c.specialty == specialty]
            job.contractor_id = (match[0] if match else rng.choice(contractors)).id
            job.scheduled_date = reported + timedelta(days=rng.randint(1, 10))
        if status == "Completed":
            job.completed_date = job.scheduled_date + timedelta(days=rng.randint(0, 5))
            job.actual_cost = round(estimated * rng.uniform(0.75, 1.45), 2)
            job.notes = "Work completed and checked."
        if status in ("Scheduled", "In Progress") and rng.random() < 0.6:
            job.follow_up_count = rng.randint(1, 3)
            job.follow_up_notes = "Chased contractor for an update."

        db.session.add(job)

    db.session.commit()
    return {"flats": flat_count, "contractors": len(contractors), "jobs": job_count}


@click.command("seed")
@click.option("--wipe", is_flag=True, help="Delete ALL existing data first.")
@with_appcontext
def seed_command(wipe: bool) -> None:
    """Populate the database with deterministic UK demo data."""
    if wipe:
        if not click.confirm("This deletes ALL flats, contractors and jobs. Continue?"):
            raise click.Abort()
        db.session.execute(db.delete(MaintenanceJob))
        db.session.execute(db.delete(Flat))
        db.session.execute(db.delete(Contractor))
        db.session.commit()

    counts = seed_data()
    click.echo(
        f"Seeded {counts['flats']} flats, {counts['contractors']} contractors, "
        f"{counts['jobs']} jobs."
    )


def register(app) -> None:
    app.cli.add_command(seed_command)
