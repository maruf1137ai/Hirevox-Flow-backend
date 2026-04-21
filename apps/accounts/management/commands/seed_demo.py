"""Seed realistic demo data so the dashboard has content immediately.

Usage: `python manage.py seed_demo [--email demo@hirevox.ai] [--password demo123456]`
"""

from datetime import timedelta
import random

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Company, Membership, User
from apps.candidates.models import Application, Candidate, Note
from apps.jobs.models import Job


SAMPLE_JOBS = [
    {
        "title": "Senior React Engineer",
        "department": "Engineering",
        "location": "Remote · US",
        "seniority": "senior",
        "salary_range": "$180k – $230k + equity",
        "skills": ["React", "TypeScript", "Next.js", "GraphQL", "Systems design"],
        "rubric": [
            {"criterion": "React depth", "weight": 0.35, "description": "Production React & ecosystem."},
            {"criterion": "Systems thinking", "weight": 0.25, "description": "Architecture & trade-offs."},
            {"criterion": "Communication", "weight": 0.2, "description": "Clear, collaborative."},
            {"criterion": "Payments domain", "weight": 0.2, "description": "Prior fintech exposure."},
        ],
        "status": "active",
    },
    {
        "title": "Product Designer",
        "department": "Design",
        "location": "San Francisco, CA",
        "seniority": "mid",
        "salary_range": "$140k – $180k + equity",
        "skills": ["Figma", "Prototyping", "Design systems", "Motion"],
        "rubric": [
            {"criterion": "Design craft", "weight": 0.4, "description": "Visual polish, attention to detail."},
            {"criterion": "Product thinking", "weight": 0.3, "description": "Understands users and tradeoffs."},
            {"criterion": "Communication", "weight": 0.2, "description": "Explains decisions."},
            {"criterion": "Motion design", "weight": 0.1, "description": "Feels-right micro-interactions."},
        ],
        "status": "active",
    },
    {
        "title": "Staff Backend Engineer",
        "department": "Engineering",
        "location": "Remote · EU",
        "seniority": "staff",
        "salary_range": "$220k – $280k + equity",
        "skills": ["Python", "PostgreSQL", "Distributed systems", "Django", "Kafka"],
        "rubric": [
            {"criterion": "Systems depth", "weight": 0.4, "description": "Distributed systems, databases."},
            {"criterion": "Code quality", "weight": 0.25, "description": "Clean, testable, maintainable code."},
            {"criterion": "Leadership", "weight": 0.2, "description": "Mentoring, technical direction."},
            {"criterion": "Communication", "weight": 0.15, "description": "Written and verbal clarity."},
        ],
        "status": "active",
    },
    {
        "title": "Head of Marketing",
        "department": "Marketing",
        "location": "New York, NY",
        "seniority": "principal",
        "salary_range": "$200k – $260k + equity",
        "skills": ["B2B SaaS", "Content strategy", "Demand gen", "Brand"],
        "rubric": [
            {"criterion": "B2B SaaS experience", "weight": 0.4, "description": "Prior scale-up marketing role."},
            {"criterion": "Strategy", "weight": 0.3, "description": "Can build a marketing org."},
            {"criterion": "Brand craft", "weight": 0.2, "description": "Taste, voice, narrative."},
            {"criterion": "Analytical chops", "weight": 0.1, "description": "Uses data to decide."},
        ],
        "status": "active",
    },
    {
        "title": "Customer Success Lead",
        "department": "CX",
        "location": "London, UK",
        "seniority": "senior",
        "salary_range": "£85k – £110k",
        "skills": ["SaaS onboarding", "Account management", "Churn reduction"],
        "rubric": [
            {"criterion": "CS experience", "weight": 0.4, "description": "B2B SaaS CS history."},
            {"criterion": "Empathy", "weight": 0.3, "description": "Reads customer signals."},
            {"criterion": "Process", "weight": 0.2, "description": "Builds playbooks."},
            {"criterion": "Communication", "weight": 0.1, "description": "Executive-level written."},
        ],
        "status": "active",
    },
    {
        "title": "Senior ML Researcher",
        "department": "Engineering",
        "location": "Remote",
        "seniority": "senior",
        "salary_range": "$210k – $280k + equity",
        "skills": ["LLMs", "PyTorch", "Evals", "Research"],
        "rubric": [],
        "status": "draft",
    },
]


SAMPLE_CANDIDATES = [
    ("Amelia Sato", "amelia@example.com", "Senior React Engineer", "Stripe", "San Francisco, CA", 96, "recommended"),
    ("Daniel Ortiz", "daniel@example.com", "Senior React Engineer", "Linear", "Remote · Mexico", 92, "recommended"),
    ("Priya Raman", "priya@example.com", "Senior React Engineer", "Vercel", "London, UK", 88, "recommended"),
    ("Julian Vance", "julian@example.com", "Staff Backend Engineer", "Retool", "New York, NY", 87, "recommended"),
    ("Noor Almasi", "noor@example.com", "Product Designer", "Loom", "Berlin, DE", 85, "shortlist"),
    ("Marcus Chen", "marcus@example.com", "Senior React Engineer", "Ramp", "San Francisco, CA", 74, "review"),
    ("Sofia Bellmer", "sofia@example.com", "Product Designer", "Arc", "Portland, OR", 69, "review"),
    ("Hiroshi Tanaka", "hiroshi@example.com", "Staff Backend Engineer", "Figma", "Tokyo, JP", 83, "review"),
    ("Elena Varga", "elena@example.com", "Senior React Engineer", "Notion", "Barcelona, ES", 81, "review"),
    ("Sade Okafor", "sade@example.com", "Product Designer", "Vercel", "Lagos, NG", 79, "review"),
    ("Naomi Ford", "naomi@example.com", "Product Designer", "Arc", "Austin, TX", 94, "recommended"),
    ("Devon Reyes", "devon@example.com", "Head of Marketing", "Retool", "New York, NY", 91, "recommended"),
]


SAMPLE_RUBRIC_SCORES = [
    {"criterion": "React depth", "score": 95, "evidence": "Led Stripe Checkout redesign, React 18 migration across 2M LOC.", "reasoning": "Strong senior depth."},
    {"criterion": "Systems thinking", "score": 92, "evidence": "Explained state-machine approach with xstate for payment flows.", "reasoning": "Architectural maturity."},
    {"criterion": "Communication", "score": 90, "evidence": "Clear, structured answers with concrete examples.", "reasoning": "Good communicator."},
    {"criterion": "Payments domain", "score": 94, "evidence": "8 years at Stripe working on Checkout, Radar.", "reasoning": "Direct domain match."},
]


STAGES = ["applied", "screening", "interview", "offer", "hired"]


class Command(BaseCommand):
    help = "Seed demo users, company, jobs, candidates, applications."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@hirevox.ai")
        parser.add_argument("--password", default="demo123456")
        parser.add_argument("--reset", action="store_true", help="Wipe existing demo rows before seeding.")

    def handle(self, *args, **opts):
        email = opts["email"].lower()
        password = opts["password"]

        if opts["reset"]:
            self.stdout.write("Resetting demo data…")
            Candidate.objects.filter(company__slug="intelleqt").delete()
            Job.objects.filter(company__slug="intelleqt").delete()
            Company.objects.filter(slug="intelleqt").delete()
            User.objects.filter(email=email).delete()

        user, user_created = User.objects.get_or_create(email=email, defaults={"name": "Maruf Rahman", "title": "Founder"})
        if user_created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Created user {email} (password: {password})"))
        else:
            self.stdout.write(f"✓ User {email} already exists")

        company, _ = Company.objects.get_or_create(
            slug="intelleqt",
            defaults={"name": "Intelleqt", "website": "intelleqt.ai", "size": "11-50"},
        )
        Membership.objects.get_or_create(user=user, company=company, defaults={"role": "owner"})
        self.stdout.write(self.style.SUCCESS(f"✓ Company: {company.name}"))

        # Jobs
        jobs_by_title = {}
        for j in SAMPLE_JOBS:
            job, _ = Job.objects.get_or_create(
                company=company,
                title=j["title"],
                defaults={
                    **{k: v for k, v in j.items() if k not in ("status",)},
                    "employment_type": "full_time",
                    "summary": f"We're hiring a {j['title']} to help us scale.",
                    "ai_generated": True,
                    "status": j["status"],
                    "created_by": user,
                    "published_at": timezone.now() - timedelta(days=random.randint(2, 30)) if j["status"] == "active" else None,
                },
            )
            jobs_by_title[j["title"]] = job

        self.stdout.write(self.style.SUCCESS(f"✓ Jobs: {len(jobs_by_title)}"))

        # Candidates + Applications
        created_apps = 0
        for name, cand_email, job_title, cc, loc, score, status in SAMPLE_CANDIDATES:
            job = jobs_by_title.get(job_title)
            if not job:
                continue
            cand, _ = Candidate.objects.get_or_create(
                company=company,
                email=cand_email,
                defaults={
                    "name": name,
                    "current_role": name.split()[0] + " Engineer",
                    "current_company": cc,
                    "location": loc,
                    "tags": random.sample(["React", "TypeScript", "Systems", "Design", "Fullstack", "ML"], 3),
                },
            )

            stage = "interview" if score >= 88 else ("screening" if score >= 75 else "applied")
            app, app_created = Application.objects.get_or_create(
                candidate=cand,
                job=job,
                defaults={
                    "company": company,
                    "stage": stage,
                    "status": status,
                    "source": random.choice(["direct", "referral", "linkedin", "network"]),
                    "score": score,
                    "ai_summary": f"{name.split()[0]} brings strong relevant experience — worth a human interview.",
                    "strengths": ["Deep technical skills", "Clear communicator", "Great domain fit"][:random.randint(2, 3)],
                    "considerations": ["Location preference may need discussion"],
                    "rubric_scores": SAMPLE_RUBRIC_SCORES,
                    "created_at": timezone.now() - timedelta(days=random.randint(1, 10)),
                },
            )
            if app_created:
                created_apps += 1

        self.stdout.write(self.style.SUCCESS(f"✓ Applications: {created_apps} new / {Application.objects.filter(company=company).count()} total"))
        self.stdout.write(self.style.SUCCESS("\nDone. Sign in at http://localhost:3001/login with:"))
        self.stdout.write(f"   email: {email}")
        self.stdout.write(f"   password: {password}\n")
