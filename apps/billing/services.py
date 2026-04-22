from datetime import timedelta, date
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import Invoice, Company, Payment

class MonthlyInvoiceService:
    """
    Service to handle monthly invoice generation for subscribers
    """
    
    MONTHLY_RATE = Decimal("150.00")
    
    @classmethod
    def generate_monthly_invoices(cls, target_date=None):
        """
        Generate invoices for all active companies on the 1st of each month
        """
        if target_date is None:
            target_date = timezone.localdate()
        
        # Only run on the 1st of the month
        if target_date.day != 1:
            return {"status": "skipped", "message": "Not the 1st of the month"}
        
        results = {
            "generated": 0,
            "skipped": 0,
            "errors": 0,
            "credit_applied": 0,
        }
        
        # Get all active companies
        active_companies = Company.objects.filter(is_active=True)
        
        for company in active_companies:
            try:
                with transaction.atomic():
                    # Check for existing invoice this month
                    existing = Invoice.objects.filter(
                        company=company,
                        invoice_date__year=target_date.year,
                        invoice_date__month=target_date.month
                    ).exists()
                    
                    if existing:
                        results["skipped"] += 1
                        continue
                    
                    # Get company's last invoice to check for credit
                    last_invoice = Invoice.objects.filter(
                        company=company
                    ).order_by('-invoice_date').first()
                    
                    credit_forward = Decimal("0.00")
                    if last_invoice and last_invoice.credit_amount > 0:
                        credit_forward = last_invoice.credit_amount
                    
                    # Calculate amount due after credit
                    amount_due = cls.MONTHLY_RATE - credit_forward
                    
                    # Create new invoice
                    invoice = Invoice.objects.create(
                        company=company,
                        invoice_date=target_date,
                        due_date=target_date + timedelta(days=30),
                        bill_to_name=company.name,
                        bill_to_company=company.business_name,
                        bill_to_email=company.email,
                        bill_to_phone=company.phone,
                        bill_to_address=company.address,
                        notes=f"Monthly subscription - {target_date.strftime('%B %Y')}",
                    )
                    
                    # Add invoice item
                    invoice.items.create(
                        description=f"Monthly Website Subscription - {target_date.strftime('%B %Y')}",
                        qty=1,
                        unit_price=cls.MONTHLY_RATE,
                    )
                    
                    # Apply credit if available
                    if credit_forward > 0:
                        # Create a credit payment record
                        Payment.objects.create(
                            invoice=invoice,
                            amount=credit_forward,
                            payment_date=target_date,
                            method=Payment.METHOD_OTHER,
                            note=f"Credit applied from previous invoice {last_invoice.invoice_number}",
                        )
                        
                        invoice.credit_used = credit_forward
                        invoice.applied_credit = last_invoice
                        invoice.save()
                        
                        # Update the old invoice to show credit was used
                        last_invoice.coverage_until = target_date
                        last_invoice.save()
                        
                        results["credit_applied"] += 1
                        
                        # Calculate coverage
                        months_covered = (credit_forward / cls.MONTHLY_RATE).quantize(Decimal("0.01"))
                        results[f"credit_coverage"] = f"{months_covered} months"
                    
                    invoice.refresh_status()
                    results["generated"] += 1
                    
            except Exception as e:
                results["errors"] += 1
                print(f"Error generating invoice for {company}: {e}")
        
        return results
    
    @classmethod
    def send_payment_reminders(cls):
        """
        Send reminders 7 days before due date (24th of month)
        """
        today = timezone.localdate()
        reminder_date = today + timedelta(days=7)
        
        # Find invoices due in 7 days
        due_invoices = Invoice.objects.filter(
            due_date=reminder_date,
            status__in=['sent', 'partial'],
            amount_due__gt=0
        ).select_related('company')
        
        results = {
            "reminders_sent": 0,
            "errors": 0
        }
        
        for invoice in due_invoices:
            try:
                # Calculate days overdue warning
                days_until_due = 7
                
                # Send email reminder
                subject = f"Payment Reminder: Invoice {invoice.invoice_number} due in 7 days"
                
                html_message = render_to_string('billing/email/payment_reminder.html', {
                    'invoice': invoice,
                    'company': invoice.company,
                    'days_until_due': days_until_due,
                    'amount_due': invoice.amount_due,
                    'has_credit': invoice.credit_amount > 0,
                    'credit_amount': invoice.credit_amount if invoice.credit_amount > 0 else None,
                })
                
                # Uncomment when email is configured
                # send_mail(
                #     subject=subject,
                #     message="",
                #     html_message=html_message,
                #     from_email=settings.DEFAULT_FROM_EMAIL,
                #     recipient_list=[invoice.bill_to_email],
                #     fail_silently=False,
                # )
                
                results["reminders_sent"] += 1
                
            except Exception as e:
                results["errors"] += 1
                print(f"Error sending reminder for invoice {invoice.invoice_number}: {e}")
        
        return results
    
    @classmethod
    def check_suspensions(cls):
        """
        Check for invoices that are 7 days overdue and should be suspended
        """
        today = timezone.localdate()
        suspension_date = today - timedelta(days=7)
        
        # Find invoices overdue by 7+ days
        suspend_invoices = Invoice.objects.filter(
            due_date__lte=suspension_date,
            status__in=['sent', 'partial', 'overdue'],
            amount_due__gt=0
        )
        
        results = {
            "suspended": 0,
            "warning_sent": 0
        }
        
        for invoice in suspend_invoices:
            # Mark as overdue if not already
            if invoice.status != 'overdue':
                invoice.status = Invoice.STATUS_OVERDUE
                invoice.save()
                
                # Send suspension warning
                # ... email logic here
                
                results["suspended"] += 1
        
        return results
    
    @classmethod
    def get_client_coverage_info(cls, company):
        """
        Get coverage information for a client
        """
        invoices = Invoice.objects.filter(company=company).order_by('-invoice_date')
        
        if not invoices.exists():
            return {
                "has_coverage": False,
                "message": "No invoices found"
            }
        
        latest = invoices.first()
        total_credit = sum(inv.credit_amount for inv in invoices)
        
        if total_credit > 0:
            months_covered = total_credit / cls.MONTHLY_RATE
            coverage_until = None
            
            if latest.coverage_until:
                coverage_until = latest.coverage_until
            else:
                # Calculate estimated coverage
                from dateutil.relativedelta import relativedelta
                months_int = int(months_covered)
                days_extra = int((months_covered - months_int) * 30)
                coverage_until = latest.invoice_date + relativedelta(months=months_int, days=days_extra)
            
            return {
                "has_coverage": True,
                "total_credit": total_credit,
                "months_covered": months_covered.quantize(Decimal("0.01")),
                "coverage_until": coverage_until,
                "latest_invoice": latest,
                "message": f"Client has credit for {months_covered.quantize(Decimal('0.01'))} months until {coverage_until}"
            }
        else:
            return {
                "has_coverage": False,
                "total_credit": 0,
                "months_covered": 0,
                "message": "No credit available"
            }