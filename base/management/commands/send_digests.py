from django.conf import settings
from django.core.management.base import BaseCommand

from base.digest import send_all


class Command(BaseCommand):
    help = "Send today's morning email to everyone who turned it on (what the daily Vercel cron does)."

    def add_arguments(self, parser):
        parser.add_argument('--site-url', default=settings.SITE_URL or 'http://127.0.0.1:8000',
                            help='Address used for links in the email.')

    def handle(self, *args, **options):
        stats = send_all(options['site_url'].rstrip('/'))
        self.stdout.write(', '.join(f'{key.replace("_", " ")}: {value}' for key, value in stats.items()))
