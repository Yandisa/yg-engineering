from django.contrib import admin
from django.utils import timezone
from django.db.models import Sum
from .models import Company, Invoice, InvoiceItem, Payment


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "business_name", 
        "name", 
        "email", 
        "phone", 
        "monthly_rate", 
        "credit_balance",
        "coverage_info",
        "is_active"
    )
    list_filter = ("is_active", "auto_generate_invoices")
    search_fields = ("business_name", "name", "email", "phone")
    ordering = ("business_name", "name")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "business_name", "email", "phone", "address")
        }),
        ("Subscription Settings", {
            "fields": ("monthly_rate", "subscription_start_date", "auto_generate_invoices"),
            "description": "Monthly subscription rate and auto-generation settings"
        }),
        ("Status", {
            "fields": ("is_active",),
        }),
    )
    
    def credit_balance(self, obj):
        """Show total credit balance across all invoices"""
        credit = obj.get_credit_balance()
        if credit > 0:
            return f"R{credit:,.2f}"
        return "-"
    credit_balance.short_description = "Credit Balance"
    
    def coverage_info(self, obj):
        """Show coverage information"""
        months, until, message = obj.get_coverage_info()
        if months > 0:
            until_str = until.strftime("%Y-%m-%d") if until else "Unknown"
            return f"{months} months (until {until_str})"
        return "No credit"
    coverage_info.short_description = "Coverage"


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "company",
        "invoice_date",
        "due_date",
        "status",
        "total",
        "amount_paid",
        "amount_due_display",
        "credit_display",
        "months_covered_display",
        "coverage_until_display",
        "last_payment_display",
    )
    list_filter = ("status", "invoice_date", "due_date", "period_start")
    search_fields = (
        "invoice_number",
        "company__business_name",
        "company__name",
        "bill_to_name",
        "bill_to_company",
    )
    ordering = ("-invoice_date",)
    inlines = [InvoiceItemInline, PaymentInline]
    date_hierarchy = "invoice_date"
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("company", "invoice_number", "status", "invoice_date", "due_date")
        }),
        ("Subscription Period", {
            "fields": ("period_start", "period_end"),
            "classes": ("collapse",),
            "description": "The billing period this invoice covers"
        }),
        ("Client Snapshot", {
            "fields": ("bill_to_name", "bill_to_company", "bill_to_email", "bill_to_phone", "bill_to_address"),
            "classes": ("collapse",),
        }),
        ("Credit Tracking", {
            "fields": ("credit_used", "months_covered", "coverage_until", "applied_credit"),
            "classes": ("collapse",),
            "description": "Credit application and coverage information"
        }),
        ("Payment Information", {
            "fields": ("amount_paid", "payment_reference", "notes"),
        }),
    )
    
    readonly_fields = ("invoice_number", "amount_paid", "months_covered", "coverage_until", "credit_used")
    
    actions = ["mark_as_paid", "send_reminder", "apply_credit_to_next"]

    def amount_due_display(self, obj):
        if obj.amount_due > 0:
            return f'<span style="color: #dc3545; font-weight: bold;">R{obj.amount_due:,.2f}</span>'
        return '<span style="color: #28a745;">R0.00</span>'
    amount_due_display.short_description = "Amount Due"
    amount_due_display.admin_order_field = "amount_due"
    amount_due_display.allow_tags = True

    def credit_display(self, obj):
        if obj.credit_amount > 0:
            return f'<span style="color: #fd7e14; font-weight: bold;">R{obj.credit_amount:,.2f}</span>'
        return "-"
    credit_display.short_description = "Credit"
    credit_display.admin_order_field = "credit_amount"
    credit_display.allow_tags = True
    
    def months_covered_display(self, obj):
        if obj.months_covered > 0:
            return f"{obj.months_covered} months"
        return "-"
    months_covered_display.short_description = "Coverage"
    months_covered_display.admin_order_field = "months_covered"
    
    def coverage_until_display(self, obj):
        if obj.coverage_until:
            return obj.coverage_until.strftime("%Y-%m-%d")
        return "-"
    coverage_until_display.short_description = "Covered Until"
    coverage_until_display.admin_order_field = "coverage_until"

    def last_payment_display(self, obj):
        last = obj.last_payment
        if last:
            return f"R{last.amount:,.2f} on {last.payment_date.strftime('%Y-%m-%d')}"
        return "No payments"
    last_payment_display.short_description = "Last Payment"

    def save_model(self, request, obj, form, change):
        """Ensure status is refreshed after saving from admin"""
        super().save_model(request, obj, form, change)
        obj.refresh_status()
    
    def mark_as_paid(self, request, queryset):
        """Mark selected invoices as paid"""
        count = 0
        for invoice in queryset:
            if invoice.amount_due > 0:
                Payment.objects.create(
                    invoice=invoice,
                    amount=invoice.amount_due,
                    payment_date=timezone.localdate(),
                    method=Payment.METHOD_OTHER,
                    note="Marked as paid via admin action",
                )
                invoice.refresh_status()
                count += 1
        self.message_user(request, f"{count} invoices marked as paid.")
    mark_as_paid.short_description = "Mark selected as paid"
    
    def send_reminder(self, request, queryset):
        """Send payment reminders for selected invoices"""
        reminders_sent = 0
        for invoice in queryset:
            if invoice.should_send_reminder:
                # In a real implementation, you'd send an email here
                reminders_sent += 1
        self.message_user(request, f"Reminders would be sent for {reminders_sent} invoices.")
    send_reminder.short_description = "Send payment reminders"
    
    def apply_credit_to_next(self, request, queryset):
        """Apply credit from selected invoices to next invoice"""
        applied = 0
        for invoice in queryset:
            if invoice.credit_amount > 0:
                # Find next invoice for same company
                next_invoice = Invoice.objects.filter(
                    company=invoice.company,
                    invoice_date__gt=invoice.invoice_date
                ).order_by('invoice_date').first()
                
                if next_invoice:
                    # Create a payment record for the credit
                    Payment.objects.create(
                        invoice=next_invoice,
                        amount=min(invoice.credit_amount, next_invoice.amount_due),
                        payment_date=next_invoice.invoice_date,
                        method=Payment.METHOD_OTHER,
                        note=f"Credit applied from invoice {invoice.invoice_number}",
                    )
                    invoice.credit_used = min(invoice.credit_amount, next_invoice.amount_due)
                    invoice.applied_credit = next_invoice
                    invoice.save()
                    next_invoice.refresh_status()
                    applied += 1
        
        self.message_user(request, f"Credit applied to {applied} next invoices.")
    apply_credit_to_next.short_description = "Apply credit to next invoice"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "invoice", 
        "payment_date", 
        "amount", 
        "method", 
        "reference", 
        "balance_after_payment",
        "credit_impact"
    )
    list_filter = ("method", "payment_date")
    search_fields = ("invoice__invoice_number", "reference", "note")
    ordering = ("-payment_date",)
    date_hierarchy = "payment_date"
    
    fieldsets = (
        (None, {
            "fields": ("invoice", "payment_date", "amount", "method", "reference", "note")
        }),
    )
    
    def balance_after_payment(self, obj):
        """Show what the invoice balance was after this payment"""
        balance = obj.invoice.balance
        if balance > 0:
            return f'<span style="color: #dc3545;">Owes: R{balance:,.2f}</span>'
        elif balance < 0:
            credit = abs(balance)
            months = (credit / obj.invoice.company.monthly_rate).quantize(Decimal("0.01")) if obj.invoice.company else 0
            return f'<span style="color: #fd7e14;">Credit: R{credit:,.2f} ({months} months)</span>'
        return '<span style="color: #28a745;">Paid in full</span>'
    balance_after_payment.short_description = "Resulting Balance"
    balance_after_payment.allow_tags = True
    
    def credit_impact(self, obj):
        """Show how this payment affects credit coverage"""
        if obj.invoice.credit_amount > 0:
            months = obj.invoice.months_covered
            if months > 0:
                until = obj.invoice.coverage_until.strftime("%Y-%m-%d") if obj.invoice.coverage_until else "Unknown"
                return f"Covers {months} months (until {until})"
        return "-"
    credit_impact.short_description = "Credit Impact"
    
    def save_model(self, request, obj, form, change):
        """Refresh invoice status after payment is saved"""
        super().save_model(request, obj, form, change)
        obj.invoice.refresh_status()
    
    def delete_model(self, request, obj):
        """Refresh invoice status after payment is deleted"""
        invoice = obj.invoice
        super().delete_model(request, obj)
        invoice.refresh_status()