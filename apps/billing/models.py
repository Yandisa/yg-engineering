from decimal import Decimal
from datetime import timedelta

from django.db import models
from django.db.models import Max, Sum, Q
from django.utils import timezone
from dateutil.relativedelta import relativedelta


class Company(models.Model):
    """
    Companies you bill (your clients).
    Create once, then select when creating invoices.
    """
    name = models.CharField(max_length=255)  # Contact person name
    business_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    # Subscription settings
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("150.00"))
    subscription_start_date = models.DateField(null=True, blank=True)
    auto_generate_invoices = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["business_name", "name"]

    def __str__(self):
        if self.business_name:
            return f"{self.business_name} ({self.name})" if self.name else self.business_name
        return self.name or "Company"
    
    def get_credit_balance(self):
        """Get total credit balance across all invoices"""
        return sum(inv.credit_amount for inv in self.invoices.all())
    
    def get_coverage_info(self):
        """
        Get coverage information based on credit balance
        Returns: (months_covered, coverage_until, message)
        """
        credit = self.get_credit_balance()
        if credit <= 0:
            return Decimal("0.00"), None, "No credit available"
        
        months_covered = (credit / self.monthly_rate).quantize(Decimal("0.01"))
        
        # Calculate coverage end date
        last_invoice = self.invoices.order_by('-invoice_date').first()
        if last_invoice and last_invoice.coverage_until:
            coverage_until = last_invoice.coverage_until
        else:
            # Start from today or last invoice date
            start_date = last_invoice.invoice_date if last_invoice else timezone.localdate()
            months_int = int(months_covered)
            days_extra = int((months_covered - months_int) * 30)
            coverage_until = start_date + relativedelta(months=months_int, days=days_extra)
        
        return months_covered, coverage_until, f"Credit covers {months_covered} months until {coverage_until}"


class Invoice(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CREDIT = "credit"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
        (STATUS_PARTIAL, "Partially Paid"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_CREDIT, "Credit"),
    ]

    # Link invoice to a company
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="invoices",
        null=True,
        blank=True,
    )

    invoice_number = models.CharField(max_length=40, unique=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    invoice_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()

    # Snapshot fields (auto-copied from Company)
    bill_to_name = models.CharField(max_length=255, blank=True)
    bill_to_company = models.CharField(max_length=255, blank=True)
    bill_to_email = models.EmailField(blank=True)
    bill_to_phone = models.CharField(max_length=50, blank=True)
    bill_to_address = models.TextField(blank=True)

    notes = models.TextField(blank=True)
    payment_reference = models.CharField(max_length=60, blank=True)

    # Derived from payments, but kept as a cached total for quick display
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Credit tracking fields
    credit_used = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    months_covered = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    coverage_until = models.DateField(null=True, blank=True)
    applied_credit = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='applied_to_invoices'
    )
    
    # Subscription period
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _generate_invoice_number(self) -> str:
        year = timezone.now().year
        prefix = f"YG-{year}-"

        last = Invoice.objects.filter(invoice_number__startswith=prefix).aggregate(Max("invoice_number"))
        last_number = last["invoice_number__max"]

        if last_number:
            last_seq = int(last_number.split("-")[-1])
            new_seq = last_seq + 1
        else:
            new_seq = 1

        return f"{prefix}{new_seq:04d}"

    def _copy_company_snapshot(self):
        """
        Copy details from Company into the snapshot fields if they are blank.
        """
        if not self.company:
            return

        if not self.bill_to_name:
            self.bill_to_name = self.company.name
        if not self.bill_to_company:
            self.bill_to_company = self.company.business_name
        if not self.bill_to_email:
            self.bill_to_email = self.company.email
        if not self.bill_to_phone:
            self.bill_to_phone = self.company.phone
        if not self.bill_to_address:
            self.bill_to_address = self.company.address

    def update_amount_paid_from_payments(self):
        """
        Recalculate amount_paid from linked Payment records.
        """
        total = self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        self.amount_paid = total
        self.save(update_fields=["amount_paid", "updated_at"])

    @property
    def last_payment(self):
        """
        Returns the most recent payment (or None).
        """
        return self.payments.order_by("-payment_date", "-created_at").first()

    def calculate_coverage(self):
        """Calculate how many months the credit covers"""
        if self.credit_amount > 0 and self.company:
            monthly_rate = self.company.monthly_rate
            self.months_covered = (self.credit_amount / monthly_rate).quantize(Decimal("0.01"))
            
            # Calculate coverage end date
            months_int = int(self.months_covered)
            days_extra = int((self.months_covered - months_int) * 30)
            self.coverage_until = self.invoice_date + relativedelta(months=months_int, days=days_extra)
            
            return self.months_covered
        return Decimal("0.00")

    def save(self, *args, **kwargs):
        # Auto invoice number
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()

        # Auto-fill bill-to fields from company
        self._copy_company_snapshot()

        # If payment reference is still empty, use invoice number
        if not self.payment_reference:
            self.payment_reference = self.invoice_number

        # Calculate coverage if there's credit
        if self.credit_amount > 0:
            self.calculate_coverage()

        super().save(*args, **kwargs)

    @property
    def subtotal(self) -> Decimal:
        """Calculate subtotal from items, return 0 if no items or no pk"""
        total = Decimal("0.00")
        if self.pk:  # Only try to access items if the invoice has been saved
            for item in self.items.all():
                total += item.line_total
        return total

    @property
    def total(self) -> Decimal:
        """Total amount (same as subtotal for now)"""
        return self.subtotal

    @property
    def balance(self) -> Decimal:
        """
        Real balance (can be negative if customer overpaid).
        > 0  => customer owes
        = 0  => settled
        < 0  => customer has credit
        """
        return (self.total - self.amount_paid).quantize(Decimal("0.01"))

    @property
    def amount_due(self) -> Decimal:
        """
        What the customer still needs to pay (never negative).
        """
        return self.balance if self.balance > 0 else Decimal("0.00")

    @property
    def credit_amount(self) -> Decimal:
        """
        Customer credit (never negative).
        """
        return (-self.balance) if self.balance < 0 else Decimal("0.00")

    @property
    def is_paid(self) -> bool:
        return self.amount_due == Decimal("0.00")

    @property
    def days_until_due(self) -> int:
        """Days until invoice is due"""
        if self.due_date:
            return (self.due_date - timezone.localdate()).days
        return 0

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue"""
        return self.due_date and self.due_date < timezone.localdate() and self.amount_due > 0

    @property
    def should_send_reminder(self) -> bool:
        """Check if reminder should be sent (7 days before due date)"""
        if self.due_date and self.amount_due > 0:
            days_until = self.days_until_due
            return days_until == 7  # 7 days before due date
        return False

    def refresh_status(self):
        """
        Refresh status based on totals and due date.
        Also keeps amount_paid synced from Payment records.
        """
        # keep amount_paid accurate
        total_paid = self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        if total_paid != self.amount_paid:
            self.amount_paid = total_paid

        today = timezone.localdate()

        if self.credit_amount > 0:
            self.status = self.STATUS_CREDIT
            self.calculate_coverage()
        elif self.amount_due == Decimal("0.00") and self.total > 0:
            self.status = self.STATUS_PAID
        elif self.amount_paid > 0:
            self.status = self.STATUS_PARTIAL
        elif self.due_date and self.due_date < today:
            self.status = self.STATUS_OVERDUE
        else:
            if self.status == self.STATUS_DRAFT:
                self.status = self.STATUS_SENT

        self.save(update_fields=["status", "amount_paid", "months_covered", "coverage_until", "updated_at"])

    def get_next_invoice_preview(self):
        """
        Preview the next invoice with credit applied
        """
        if not self.company:
            return None
        
        monthly_rate = self.company.monthly_rate
        credit = self.credit_amount
        
        if credit > 0:
            months_covered = (credit / monthly_rate).quantize(Decimal("0.01"))
            remaining_credit = credit - monthly_rate if months_covered >= 1 else credit
            
            return {
                "monthly_rate": monthly_rate,
                "credit_available": credit,
                "months_covered": months_covered,
                "next_amount_due": max(Decimal("0.00"), monthly_rate - credit),
                "credit_remaining": max(Decimal("0.00"), remaining_credit),
                "will_be_covered": credit >= monthly_rate,
            }
        return None

    def __str__(self):
        return self.invoice_number


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    @property
    def line_total(self) -> Decimal:
        return (self.qty * self.unit_price).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"


class Payment(models.Model):
    METHOD_CASH = "cash"
    METHOD_EFT = "eft"
    METHOD_CARD = "card"
    METHOD_OTHER = "other"

    METHOD_CHOICES = [
        (METHOD_CASH, "Cash"),
        (METHOD_EFT, "EFT"),
        (METHOD_CARD, "Card"),
        (METHOD_OTHER, "Other"),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    payment_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default=METHOD_EFT)
    reference = models.CharField(max_length=80, blank=True)
    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Refresh invoice status to update credit calculations
        self.invoice.refresh_status()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.refresh_status()

    def __str__(self):
        return f"{self.invoice.invoice_number} - R{self.amount} ({self.payment_date})"