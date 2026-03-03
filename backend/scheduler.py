import schedule
import time
from job_searcher import run_search

# run every 30 minutes
schedule.every(30).minutes.do(run_search)

# run immediately on startup
run_search()

print("Scheduler running...")
while True:
    schedule.run_pending()
    time.sleep(60)
