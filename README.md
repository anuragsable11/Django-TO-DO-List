📝 Doneward

Doneward is a calm, focused to-do list built with Django: write tasks down, check them off, and let Stripes, its tiger assistant, remind you what is still waiting.

🚀 Features
➕ Add new tasks
📝 Update existing tasks
❌ Delete tasks
✅ Mark tasks as completed
📋 View all tasks in a clean UI
🛠️ Tech Stack
Frontend: HTML, CSS
Backend: Django (Python)
Database: PostgreSQL on Neon (SQLite locally when no DATABASE_URL is set)

⚙️ Run locally
1. python -m venv myenv, then myenv\Scripts\activate (Windows) or source myenv/bin/activate
2. pip install -r requirements.txt
3. Copy .env.example to .env and fill in DATABASE_URL and DJANGO_SECRET_KEY (skip this to use SQLite)
4. python manage.py migrate
5. python manage.py runserver

☁️ Deploy on Vercel
1. In the Vercel project, open Settings → Environment Variables and add DATABASE_URL and DJANGO_SECRET_KEY for Production and Preview (Vercel never reads .env).
2. Redeploy. Vercel detects Django from manage.py and serves the static files itself.
3. After changing models, run python manage.py migrate locally with DATABASE_URL pointing at Neon, then deploy.
