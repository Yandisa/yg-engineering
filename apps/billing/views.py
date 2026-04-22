from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum
from decimal import Decimal

from .forms import InvoiceForm, CompanyForm, BulkInvoiceGenerateForm
from .models import Invoice, Payment, Company
from .pdf import draw_invoice_pdf
from .services import MonthlyInvoiceService


def invoice_list(request):
    qs = Invoice.objects.all().select_related('company').order_by("-invoice_date", "-created_at")

    status = request.GET.get("status")
    q = request.GET.get("q")
    show_all = request.GET.get("all", False)

    if status and status != "all":
        qs = qs.filter(status=status)

    if q:
        qs = qs.filter(
            Q(invoice_number__icontains=q) |
            Q(bill_to_name__icontains=q) |
            Q(bill_to_company__icontains=q) |
            Q(company__business_name__icontains=q)
        )

    # Calculate summary stats
    total_outstanding = sum(inv.amount_due for inv in qs if inv.amount_due > 0)
    total_credit = sum(inv.credit_amount for inv in qs if inv.credit_amount > 0)
    total_paid = sum(inv.amount_paid for inv in qs if inv.is_paid)
    
    # Calculate credit coverage stats
    total_credit_months = Decimal("0.00")
    companies_with_credit = 0
    for inv in qs:
        if inv.credit_amount > 0 and inv.company:
            months = inv.months_covered
            total_credit_months += months
            companies_with_credit += 1

    context = {
        "invoices": qs,
        "total_outstanding": total_outstanding,
        "total_credit": total_credit,
        "total_paid": total_paid,
        "total_credit_months": total_credit_months.quantize(Decimal("0.01")),
        "companies_with_credit": companies_with_credit,
        "monthly_rate": 150,
        "status_counts": {
            "draft": qs.filter(status="draft").count(),
            "sent": qs.filter(status="sent").count(),
            "partial": qs.filter(status="partial").count(),
            "paid": qs.filter(status="paid").count(),
            "overdue": qs.filter(status="overdue").count(),
            "credit": qs.filter(status="credit").count(),
        }
    }
    return render(request, "billing/invoice_list.html", context)


def invoice_detail(request, pk: int):
    invoice = get_object_or_404(Invoice.objects.select_related('company'), pk=pk)
    
    # Get payment history for statement
    payments = invoice.payments.all().order_by("-payment_date", "-created_at")
    
    # Get next invoice preview if there's credit
    next_preview = invoice.get_next_invoice_preview() if hasattr(invoice, 'get_next_invoice_preview') else None
    
    # Get coverage info
    coverage_info = None
    if invoice.company and invoice.credit_amount > 0:
        months, until, message = invoice.company.get_coverage_info()
        coverage_info = {
            "months": months,
            "until": until,
            "message": message
        }
    
    context = {
        "invoice": invoice,
        "payments": payments,
        "balance": invoice.balance,
        "amount_due": invoice.amount_due,
        "credit_amount": invoice.credit_amount,
        "next_preview": next_preview,
        "coverage_info": coverage_info,
        "today": timezone.localdate(),
        "days_until_due": invoice.days_until_due if hasattr(invoice, 'days_until_due') else None,
        "is_overdue": invoice.is_overdue if hasattr(invoice, 'is_overdue') else False,
    }
    return render(request, "billing/invoice_detail.html", context)


def invoice_create(request):
    if request.method == "POST":
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save()
            invoice.refresh_status()
            messages.success(request, f"Invoice {invoice.invoice_number} created successfully.")
            
            # Show credit application message if credit was used
            if invoice.credit_used > 0:
                messages.info(request, f"R{invoice.credit_used:,.2f} credit was applied to this invoice.")
            
            return redirect("billing:invoice_detail", pk=invoice.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # Pre-fill with today's date and default due date (30 days from now)
        initial = {
            "invoice_date": timezone.localdate(),
            "due_date": timezone.localdate() + timezone.timedelta(days=30),
        }
        form = InvoiceForm(initial=initial)

    return render(request, "billing/invoice_form.html", {
        "form": form,
        "mode": "create",
    })


def invoice_edit(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)

    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            invoice = form.save()
            invoice.refresh_status()
            messages.success(request, f"Invoice {invoice.invoice_number} updated successfully.")
            return redirect("billing:invoice_detail", pk=invoice.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = InvoiceForm(instance=invoice)

    return render(request, "billing/invoice_form.html", {
        "form": form,
        "mode": "edit",
        "invoice": invoice,
    })


def invoice_pdf(request, pk: int):
    invoice = get_object_or_404(Invoice.objects.select_related('company'), pk=pk)
    invoice.refresh_status()

    company = {
        "name": getattr(settings, "INVOICE_COMPANY_NAME", "YG Engineering"),
        "website": getattr(settings, "INVOICE_WEBSITE", "www.ygengineering.co.za"),
        "email": getattr(settings, "INVOICE_EMAIL", "info@ygengineering.co.za"),
        "phone": getattr(settings, "INVOICE_PHONE", ""),
        "address": getattr(settings, "INVOICE_ADDRESS", "South Africa"),
        "logo_path": getattr(settings, "INVOICE_LOGO_PATH", ""),
        "bank_name": getattr(settings, "INVOICE_BANK_NAME", "Capitec Bank"),
        "account_name": getattr(settings, "INVOICE_BANK_ACCOUNT_NAME", "YG Engineering"),
        "account_number": getattr(settings, "INVOICE_BANK_ACCOUNT_NUMBER", "2509492051"),
        "branch_code": getattr(settings, "INVOICE_BANK_BRANCH_CODE", "470010"),
    }

    filename = f"invoice-{invoice.invoice_number}.pdf"
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    draw_invoice_pdf(response, invoice, company)
    return response


def invoice_mark_paid(request, pk: int):
    """Quick action to mark invoice as fully paid"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    if invoice.amount_due > 0:
        # Create a payment record for the full amount
        payment = Payment.objects.create(
            invoice=invoice,
            amount=invoice.amount_due,
            payment_date=timezone.localdate(),
            method=Payment.METHOD_OTHER,
            note="Marked as paid via quick action",
        )
        invoice.refresh_status()
        messages.success(request, f"Invoice {invoice.invoice_number} marked as paid.")
        
        # Show credit message if overpaid
        if invoice.credit_amount > 0:
            messages.info(request, f"Overpayment created credit of R{invoice.credit_amount:,.2f}")
    else:
        messages.warning(request, f"Invoice {invoice.invoice_number} is already paid or has credit.")
    
    return redirect("billing:invoice_detail", pk=invoice.pk)


def invoice_add_payment(request, pk: int):
    """View to add a payment to an invoice"""
    invoice = get_object_or_404(Invoice, pk=pk)
    
    if request.method == "POST":
        amount = Decimal(request.POST.get("amount", "0"))
        payment_date = request.POST.get("payment_date")
        method = request.POST.get("method")
        reference = request.POST.get("reference", "")
        note = request.POST.get("note", "")
        
        try:
            payment = Payment.objects.create(
                invoice=invoice,
                amount=amount,
                payment_date=payment_date or timezone.localdate(),
                method=method,
                reference=reference,
                note=note,
            )
            invoice.refresh_status()
            messages.success(request, f"Payment of R{amount:,.2f} recorded successfully.")
            
            # Show appropriate message based on result
            if invoice.credit_amount > 0:
                months = invoice.months_covered
                messages.info(request, 
                    f"Client now has credit of R{invoice.credit_amount:,.2f} "
                    f"covering approximately {months} months of service."
                )
            elif invoice.amount_due == 0:
                messages.success(request, "Invoice is now fully paid.")
                
        except Exception as e:
            messages.error(request, f"Error recording payment: {e}")
            
        return redirect("billing:invoice_detail", pk=invoice.pk)
    
    # Pass today's date to the template for the date picker
    return render(request, "billing/payment_form.html", {
        "invoice": invoice,
        "today": timezone.localdate(),
    })


def invoice_delete_payment(request, pk: int, payment_pk: int):
    """Delete a payment from an invoice"""
    payment = get_object_or_404(Payment, pk=payment_pk, invoice_id=pk)
    invoice = payment.invoice
    
    if request.method == "POST":
        amount = payment.amount
        payment.delete()
        invoice.refresh_status()
        messages.success(request, f"Payment of R{amount:,.2f} deleted successfully.")
        
        # Show updated credit status
        if invoice.credit_amount > 0:
            messages.info(request, f"Remaining credit: R{invoice.credit_amount:,.2f}")
    
    return redirect("billing:invoice_detail", pk=invoice.pk)


def invoice_overdue(request):
    """View for overdue invoices"""
    overdue_invoices = Invoice.objects.filter(
        status=Invoice.STATUS_OVERDUE
    ).select_related('company').order_by("-due_date")
    
    total_overdue = sum(inv.amount_due for inv in overdue_invoices)
    
    context = {
        "invoices": overdue_invoices,
        "total_overdue": total_overdue,
        "count": overdue_invoices.count(),
    }
    return render(request, "billing/invoice_overdue.html", context)


def invoice_credit_notes(request):
    """View for invoices with credit"""
    credit_invoices = Invoice.objects.filter(
        credit_amount__gt=0
    ).select_related('company').order_by("-invoice_date")
    
    total_credit = sum(inv.credit_amount for inv in credit_invoices)
    total_months = sum(inv.months_covered for inv in credit_invoices)
    
    context = {
        "invoices": credit_invoices,
        "total_credit": total_credit,
        "total_months": total_months.quantize(Decimal("0.01")),
        "count": credit_invoices.count(),
    }
    return render(request, "billing/invoice_credit.html", context)


def company_list(request):
    """View for managing companies/clients"""
    companies = Company.objects.all().order_by("business_name", "name")
    
    context = {
        "companies": companies,
        "total_companies": companies.count(),
        "active_companies": companies.filter(is_active=True).count(),
    }
    return render(request, "billing/company_list.html", context)


def company_detail(request, pk: int):
    """View company details with invoice history"""
    company = get_object_or_404(Company, pk=pk)
    invoices = company.invoices.all().order_by("-invoice_date")
    
    # Get coverage info
    months, until, message = company.get_coverage_info()
    
    context = {
        "company": company,
        "invoices": invoices,
        "coverage_months": months,
        "coverage_until": until,
        "coverage_message": message,
        "total_credit": company.get_credit_balance(),
        "invoice_count": invoices.count(),
        "total_billed": sum(inv.total for inv in invoices),
        "total_paid": sum(inv.amount_paid for inv in invoices),
    }
    return render(request, "billing/company_detail.html", context)


def company_create(request):
    """Create a new company/client"""
    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save()
            messages.success(request, f"Company {company.business_name or company.name} created successfully.")
            return redirect("billing:company_detail", pk=company.pk)
    else:
        form = CompanyForm()
    
    return render(request, "billing/company_form.html", {
        "form": form,
        "mode": "create",
    })


def company_edit(request, pk: int):
    """Edit company details"""
    company = get_object_or_404(Company, pk=pk)
    
    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            company = form.save()
            messages.success(request, f"Company updated successfully.")
            return redirect("billing:company_detail", pk=company.pk)
    else:
        form = CompanyForm(instance=company)
    
    return render(request, "billing/company_form.html", {
        "form": form,
        "mode": "edit",
        "company": company,
    })


def generate_monthly_invoices(request):
    """View to trigger monthly invoice generation"""
    if request.method == "POST":
        form = BulkInvoiceGenerateForm(request.POST)
        if form.is_valid():
            invoice_date = form.cleaned_data['invoice_date']
            due_date = form.cleaned_data['due_date']
            companies = form.cleaned_data['companies']
            apply_credit = form.cleaned_data['apply_credit']
            
            results = {
                "generated": 0,
                "skipped": 0,
                "errors": 0,
                "credit_applied": 0,
            }
            
            for company in companies:
                try:
                    # Check if invoice already exists for this period
                    existing = Invoice.objects.filter(
                        company=company,
                        invoice_date__year=invoice_date.year,
                        invoice_date__month=invoice_date.month
                    ).exists()
                    
                    if existing:
                        results["skipped"] += 1
                        continue
                    
                    # Create invoice
                    invoice = Invoice.objects.create(
                        company=company,
                        invoice_date=invoice_date,
                        due_date=due_date,
                        bill_to_name=company.name,
                        bill_to_company=company.business_name,
                        bill_to_email=company.email,
                        bill_to_phone=company.phone,
                        bill_to_address=company.address,
                        period_start=invoice_date.replace(day=1),
                        notes=f"Monthly subscription - {invoice_date.strftime('%B %Y')}",
                    )
                    
                    # Add invoice item
                    invoice.items.create(
                        description=f"Monthly Website Subscription - {invoice_date.strftime('%B %Y')}",
                        qty=1,
                        unit_price=company.monthly_rate,
                    )
                    
                    # Apply credit if enabled
                    if apply_credit:
                        credit = company.get_credit_balance()
                        if credit > 0 and invoice.amount_due > 0:
                            amount_to_apply = min(credit, invoice.amount_due)
                            Payment.objects.create(
                                invoice=invoice,
                                amount=amount_to_apply,
                                payment_date=invoice_date,
                                method=Payment.METHOD_OTHER,
                                note="Auto-applied credit from previous overpayments",
                            )
                            results["credit_applied"] += 1
                    
                    invoice.refresh_status()
                    results["generated"] += 1
                    
                except Exception as e:
                    results["errors"] += 1
                    messages.error(request, f"Error for {company}: {e}")
            
            messages.success(request, 
                f"Generated {results['generated']} invoices. "
                f"Skipped: {results['skipped']}, "
                f"Credit applied: {results['credit_applied']}"
            )
            
            return redirect("billing:invoice_list")
    else:
        form = BulkInvoiceGenerateForm(initial={
            "invoice_date": timezone.localdate().replace(day=1),
            "due_date": (timezone.localdate().replace(day=1) + timezone.timedelta(days=30)),
        })
    
    return render(request, "billing/bulk_generate.html", {
        "form": form,
    })


def send_reminders(request):
    """Manually trigger payment reminders"""
    if request.method == "POST":
        service = MonthlyInvoiceService()
        results = service.send_payment_reminders()
        messages.success(request, f"Sent {results['reminders_sent']} reminders.")
        return redirect("billing:invoice_list")
    
    # Show preview of invoices needing reminders
    upcoming_invoices = Invoice.objects.filter(
        due_date=timezone.localdate() + timezone.timedelta(days=7),
        amount_due__gt=0
    ).select_related('company')
    
    context = {
        "invoices": upcoming_invoices,
        "count": upcoming_invoices.count(),
        "total_due": sum(inv.amount_due for inv in upcoming_invoices),
    }
    return render(request, "billing/send_reminders.html", context)