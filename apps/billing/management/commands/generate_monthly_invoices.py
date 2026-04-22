from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.billing.services import MonthlyInvoiceService

class Command(BaseCommand):
    help = 'Generate monthly invoices and send reminders'
    
    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
        parser.add_argument('--reminders', action='store_true', help='Send payment reminders')
        parser.add_argument('--suspensions', action='store_true', help='Check for suspensions')
    
    def handle(self, *args, **options):
        target_date = None
        if options.get('date'):
            from datetime import datetime
            target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
        
        if options.get('reminders'):
            self.stdout.write("Sending payment reminders...")
            results = MonthlyInvoiceService.send_payment_reminders()
            self.stdout.write(self.style.SUCCESS(f"Sent {results['reminders_sent']} reminders"))
        
        elif options.get('suspensions'):
            self.stdout.write("Checking for suspensions...")
            results = MonthlyInvoiceService.check_suspensions()
            self.stdout.write(self.style.SUCCESS(f"Suspended {results['suspended']} accounts"))
        
        else:
            self.stdout.write("Generating monthly invoices...")
            results = MonthlyInvoiceService.generate_monthly_invoices(target_date)
            
            if results.get("status") == "skipped":
                self.stdout.write(self.style.WARNING(results["message"]))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Generated: {results['generated']}, "
                    f"Skipped: {results['skipped']}, "
                    f"Credit Applied: {results['credit_applied']}"
                ))