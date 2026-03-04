import typing
typing.Union.__module__ = "typingimport os
import requests
import feedparser
import hashlib
from datetime import datetime
from supabase import create_client
from openai import OpenAI

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SEARCH_TERMS = [
    "Assistant Site Manager",
    "Trainee Site Manager",
    "360 Excavator Operator",
    "Dumper Driver",
    "Road Roller Operator",
    "Electricians Mate",
]

LOCATIONS = [
    "Wirral",
    "Cheshire West",
    "North Wales",
]

SALARY_MIN_ANNUAL = 35000
SALARY_MAX_ANNUAL = 40000

def search_reed():
    api_key = os.environ["REED_API_KEY"]
    jobs = []
    for term in SEARCH_TERMS:
        for location in LOCATIONS:
            url = "https://www.reed.co.uk/api/1.0/search"
            params = {
                "keywords": term,
                "locationName": location,
                "minimumSalary": SALARY_MIN_ANNUAL,
                "maximumSalary": SALARY_MAX_ANNUAL,
                "distanceFromLocation": 15,
            }
            response = requests.get(
                url, params=params, auth=(api_key, "")
            )
            if response.status_code == 200:
                data = response.json()
                for job in data.get("results", []):
                    jobs.append({
                        "external_id": f"reed_{job['jobId']}",
                        "title": job.get("jobTitle", ""),
                        "company": job.get("employerName", ""),
                        "location": job.get("locationName", ""),
                        "salary_min": job.get("minimumSalary"),
                        "salary_max": job.get("maximumSalary"),
                        "salary_text": job.get("salary", ""),
                        "description": job.get("jobDescription", ""),
                        "url": job.get("jobUrl", ""),
                        "source": "Reed",
                        "date_posted": job.get("date"),
                    })
    return jobs

def search_totaljobs():
    jobs = []
    for term in SEARCH_TERMS:
        for location in LOCATIONS:
            url = (
                f"https://www.totaljobs.com/jobs/"
                f"{term.lower().replace(' ', '-')}"
                f"/in-{location.lower().replace(' ', '-')}"
                f"?salarytype=annual&salary={SALARY_MIN_ANNUAL}"
                f"&format=rss"
            )
            feed = feedparser.parse(url)
            for entry in feed.entries:
                job_id = hashlib.md5(
                    entry.get("link", "").encode()
                ).hexdigest()
                jobs.append({
                    "external_id": f"totaljobs_{job_id}",
                    "title": entry.get("title", ""),
                    "company": entry.get("author", "Unknown"),
                    "location": location,
                    "salary_min": None,
                    "salary_max": None,
                    "salary_text": "",
                    "description": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "source": "TotalJobs",
                    "date_posted": entry.get("published"),
                })
    return jobs

def search_cvlibrary():
    jobs = []
    for term in SEARCH_TERMS:
        for location in LOCATIONS:
            url = (
                f"https://www.cv-library.co.uk/search-jobs-feeds"
                f"?q={term.replace(' ', '+')}"
                f"&l={location.replace(' ', '+')}"
                f"&salarymin={SALARY_MIN_ANNUAL}"
                f"&salarytype=annual"
                f"&distance=15"
            )
            feed = feedparser.parse(url)
            for entry in feed.entries:
                job_id = hashlib.md5(
                    entry.get("link", "").encode()
                ).hexdigest()
                jobs.append({
                    "external_id": f"cvlibrary_{job_id}",
                    "title": entry.get("title", ""),
                    "company": entry.get("author", "Unknown"),
                    "location": location,
                    "salary_min": None,
                    "salary_max": None,
                    "salary_text": "",
                    "description": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "source": "CV Library",
                    "date_posted": entry.get("published"),
                })
    return jobs

def save_new_jobs(jobs):
    new_jobs = []
    for job in jobs:
        try:
            existing = supabase.table("jobs")\
                .select("id")\
                .eq("external_id", job["external_id"])\
                .execute()
            if not existing.data:
                result = supabase.table("jobs")\
                    .insert(job)\
                    .execute()
                new_jobs.append(result.data[0])
                print(f"New job saved: {job['title']} - {job['source']}")
        except Exception as e:
            print(f"Error saving job: {e}")
    return new_jobs

def generate_cover_letter(job):
    profile = supabase.table("profile")\
        .select("*")\
        .limit(1)\
        .execute()
    cv_text = profile.data[0]["cv_text"] if profile.data else ""
    prompt = f"""
You are writing a professional cover letter for Richard Gallagher.

CV SUMMARY:
{cv_text}

JOB DETAILS:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Salary: {job['salary_text']}
Description: {job['description'][:1000]}

Write a concise, professional cover letter (3-4 paragraphs) that:
- Opens with enthusiasm for the specific role
- Highlights Richard's most relevant qualifications (SMSTS, NPORS tickets, site experience)
- Connects his civil service leadership to site management requirements
- Closes with a call to action

Use a professional but confident tone. Address it to the hiring manager.
Do not include address blocks or date - just the body paragraphs.
"""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
    )
    return response.choices[0].message.content

def send_notification(new_jobs):
    if not new_jobs:
        return
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    gmail_user = os.environ["GMAIL_ADDRESS"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]
    subject = f"🔨 {len(new_jobs)} New Job(s) Found!"
    body = "New jobs matching your criteria:\n\n"
    for job in new_jobs:
        body += f"{'='*50}\n"
        body += f"Role: {job['title']}\n"
        body += f"Company: {job['company']}\n"
        body += f"Location: {job['location']}\n"
        body += f"Salary: {job.get('salary_text', 'Not specified')}\n"
        body += f"Source: {job['source']}\n"
        body += f"Link: {job['url']}\n"
        body += f"View & Apply: {os.environ['PWA_URL']}/job/{job['id']}\n\n"
    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = gmail_user
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(gmail_user, gmail_pass)
        server.send_message(msg)
        server.quit()
        print(f"Notification sent for {len(new_jobs)} jobs")
    except Exception as e:
        print(f"Email error: {e}")

def run_search():
    print(f"Running job search at {datetime.now()}")
    all_jobs = []
    all_jobs.extend(search_reed())
    all_jobs.extend(search_totaljobs())
    all_jobs.extend(search_cvlibrary())
    print(f"Found {len(all_jobs)} total jobs across all boards")
    new_jobs = save_new_jobs(all_jobs)
    print(f"{len(new_jobs)} new jobs saved to database")
    if new_jobs:
        send_notification(new_jobs)

if __name__ == "__main__":
    run_search()
