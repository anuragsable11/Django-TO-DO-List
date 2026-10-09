📝 Doneward

Doneward is a calm, focused to-do list built with Django: write tasks down, check them off, and let Stripes, its tiger assistant, remind you what is still waiting.

🚀 Features
➕ Quick add that understands plain words: "Pay rent friday #home !high" sets the date, the list and the priority
📅 Due dates, with Today, Upcoming and Overdue views
🔁 Repeating tasks (every day, weekday, week or month) that come back after you check them off
🚩 Priority levels (high, normal, low) and drag-to-reorder, by mouse, touch or arrow keys
🗂️ Lists such as Work, Home and Study, each with its own colour
🔍 Search across titles and notes, in your list, Completed and Trash
↩️ Undo after completing or deleting, from the message or with Ctrl+Z
✉️ A morning email with what's overdue and due today (optional)
🐯 Stripes, a 3D tiger who reminds you of the most urgent tasks first
🌗 Light and dark themes, and a layout that works on phones

🛠️ Tech Stack
Frontend: HTML, CSS, JavaScript, three.js (for Stripes)
Backend: Django (Python)
Database: PostgreSQL on Neon (SQLite locally when no DATABASE_URL is set)

⚙️ Run locally
1. python -m venv myenv, then myenv\Scripts\activate (Windows) or source myenv/bin/activate
2. pip install -r requirements.txt
3. Copy .env.example to .env and fill in DATABASE_URL and DJANGO_SECRET_KEY (skip this to use SQLite)
4. python manage.py migrate
5. python manage.py runserver
6. Optional: python manage.py send_digests sends today's morning emails (printed in the terminal without email settings)
7. Tests: python manage.py test

☁️ Deploy on Vercel
1. In the Vercel project, open Settings → Environment Variables and add DATABASE_URL and DJANGO_SECRET_KEY for Production and Preview (Vercel never reads .env).
   Connecting Neon from Vercel's Storage tab with a prefix also works: the app reads e.g. downward_DATABASE_URL.
2. For the morning email, also add EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DEFAULT_FROM_EMAIL, CRON_SECRET and SITE_URL (see .env.example).
   vercel.json schedules the email once a day at 01:00 to 01:59 UTC (about 7 AM in India).
3. Redeploy. Vercel detects Django from manage.py and serves the static files itself.
4. After changing models, run python manage.py migrate with DATABASE_URL pointing at Neon (the local .env does this), right after the deploy.
