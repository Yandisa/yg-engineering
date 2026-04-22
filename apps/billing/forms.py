from decimal import Decimal
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Invoice, Company, Payment


class InvoiceForm(forms.ModelForm):
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        required=True,
        empty_label="Select a company...",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    
    # New fields for subscription management
    apply_credit = forms.BooleanField(
        required=False,
        initial=True,
        label="Apply available credit",
        help_text="Automatically apply any credit balance to this invoice",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
    
    period_start = forms.DateField(
        required=False,
        label="Period Start",
        help_text="Start of subscription period (optional)",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    
    period_end = forms.DateField(
        required=False,
        label="Period End",
        help_text="End of subscription period (optional)",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Invoice
        fields = [
            "company",
            "invoice_date",
            "due_date",
            "period_start",
            "period_end",
            "notes",
        ]
        widgets = {
            "invoice_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "due_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "notes": forms.Textarea(
                attrs={"rows": 3, "class": "form-control", "placeholder": "Optional notes..."}
            ),
        }
        labels = {
            "invoice_date": "Invoice Date",
            "due_date": "Due Date",
            "notes": "Additional Notes",
        }
        help_texts = {
            "due_date": "Payment is expected by this date",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing an existing invoice, show credit information
        if self.instance and self.instance.pk:
            company = self.instance.company
            if company:
                credit = company.get_credit_balance()
                if credit > 0:
                    months, until, _ = company.get_coverage_info()
                    until_str = until.strftime("%Y-%m-%d") if until else "Unknown"
                    self.fields['apply_credit'].help_text = (
                        f"Credit available: R{credit:,.2f} ({months} months until {until_str})"
                    )
        
        # Make period fields optional but suggest monthly period
        if not self.instance.pk or not self.instance.period_start:
            invoice_date = self.initial.get('invoice_date') or self.data.get('invoice_date')
            if invoice_date:
                try:
                    from datetime import datetime
                    if isinstance(invoice_date, str):
                        invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    invoice_date = timezone.localdate()
            else:
                invoice_date = timezone.localdate()
                
            if not self.initial.get('period_start'):
                self.initial['period_start'] = invoice_date.replace(day=1)
            if not self.initial.get('period_end'):
                # Calculate last day of the month
                import calendar
                last_day = calendar.monthrange(invoice_date.year, invoice_date.month)[1]
                self.initial['period_end'] = invoice_date.replace(day=last_day)

    def clean_due_date(self):
        """Ensure due date is not before invoice date"""
        due_date = self.cleaned_data.get("due_date")
        invoice_date = self.cleaned_data.get("invoice_date")
        
        if due_date and invoice_date and due_date < invoice_date:
            raise forms.ValidationError("Due date cannot be before invoice date.")
        return due_date
    
    def clean_period_end(self):
        """Ensure period end is after period start"""
        period_start = self.cleaned_data.get("period_start")
        period_end = self.cleaned_data.get("period_end")
        
        if period_start and period_end and period_end < period_start:
            raise forms.ValidationError("Period end cannot be before period start.")
        return period_end

    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        
        # Set default dates if not provided
        if not cleaned_data.get("invoice_date"):
            cleaned_data["invoice_date"] = timezone.localdate()
        
        if not cleaned_data.get("due_date"):
            # Default due date: 30 days from invoice date
            cleaned_data["due_date"] = cleaned_data["invoice_date"] + timezone.timedelta(days=30)
        
        # Auto-set period if not provided
        company = cleaned_data.get("company")
        invoice_date = cleaned_data.get("invoice_date")
        
        if company and not cleaned_data.get("period_start") and invoice_date:
            # Default period to the month of the invoice
            cleaned_data["period_start"] = invoice_date.replace(day=1)
            
            # Calculate period end (last day of the month)
            import calendar
            last_day = calendar.monthrange(invoice_date.year, invoice_date.month)[1]
            cleaned_data["period_end"] = invoice_date.replace(day=last_day)
        
        # Validate that period matches monthly rate if both are provided
        if company and cleaned_data.get("period_start") and cleaned_data.get("period_end"):
            days_in_period = (cleaned_data["period_end"] - cleaned_data["period_start"]).days + 1
            expected_days = 30  # Approximate month
            if days_in_period < 25 or days_in_period > 35:
                # Just a warning, not an error
                self.add_warning(
                    f"Period length ({days_in_period} days) deviates from standard month. "
                    f"Ensure the monthly rate of R{company.monthly_rate} is appropriate."
                )
        
        return cleaned_data
    
    def add_warning(self, message):
        """Add a non-blocking warning message"""
        if not hasattr(self, 'warnings'):
            self.warnings = []
        self.warnings.append(message)
    
    def save(self, commit=True):
        """Save the invoice and handle credit application"""
        invoice = super().save(commit=False)
        
        # Set period if not already set
        if not invoice.period_start and self.cleaned_data.get('period_start'):
            invoice.period_start = self.cleaned_data['period_start']
        if not invoice.period_end and self.cleaned_data.get('period_end'):
            invoice.period_end = self.cleaned_data['period_end']
        
        if commit:
            # First save to get a primary key
            invoice.save()
            self.save_m2m()
            
            # Handle credit application if enabled - do this AFTER saving
            if self.cleaned_data.get('apply_credit', False) and invoice.company:
                credit = invoice.company.get_credit_balance()
                
                # Don't count credit from this invoice if it's being edited
                existing_credit = 0
                if invoice.pk:
                    existing_credit = invoice.credit_amount
                
                available_credit = credit - existing_credit
                
                # Now we can access amount_due safely since invoice has a pk
                if available_credit > 0 and invoice.amount_due > 0:
                    # Apply credit to this invoice
                    amount_to_apply = min(available_credit, invoice.amount_due)
                    
                    payment = Payment.objects.create(
                        invoice=invoice,
                        amount=amount_to_apply,
                        payment_date=invoice.invoice_date,
                        method=Payment.METHOD_OTHER,
                        note=f"Auto-applied credit from previous overpayments",
                    )
                    
                    # Update credit tracking
                    invoice.credit_used = amount_to_apply
                    
                    # Find which invoice provided this credit
                    credit_invoice = Invoice.objects.filter(
                        company=invoice.company,
                        credit_amount__gt=0
                    ).exclude(pk=invoice.pk).order_by('invoice_date').first()
                    
                    if credit_invoice:
                        invoice.applied_credit = credit_invoice
                    
                    # Save again to update credit tracking fields
                    invoice.save()
                    
                    # Refresh status to update all calculations
                    invoice.refresh_status()
        else:
            # If not committing, just return the unsaved instance
            pass
        
        return invoice


class CompanyForm(forms.ModelForm):
    """Form for creating/editing companies with subscription settings"""
    
    class Meta:
        model = Company
        fields = [
            "name",
            "business_name",
            "email",
            "phone",
            "address",
            "monthly_rate",
            "subscription_start_date",
            "auto_generate_invoices",
            "is_active",
        ]
        widgets = {
            "subscription_start_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "address": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "monthly_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }
        labels = {
            "name": "Contact Person Name",
            "business_name": "Company/Business Name",
            "monthly_rate": "Monthly Subscription Rate (R)",
            "subscription_start_date": "Subscription Start Date",
            "auto_generate_invoices": "Auto-generate monthly invoices",
        }
        help_texts = {
            "monthly_rate": "Default: R150.00",
            "subscription_start_date": "When did this client start their subscription?",
            "auto_generate_invoices": "Automatically create invoices on the 1st of each month",
        }
    
    def clean_monthly_rate(self):
        """Ensure monthly rate is positive"""
        rate = self.cleaned_data.get("monthly_rate")
        if rate and rate <= 0:
            raise ValidationError("Monthly rate must be greater than zero.")
        return rate
    
    def clean(self):
        """Additional validation for subscription settings"""
        cleaned_data = super().clean()
        
        # If auto-generate is enabled, ensure we have a start date
        if cleaned_data.get('auto_generate_invoices') and not cleaned_data.get('subscription_start_date'):
            self.add_error('subscription_start_date', 
                ValidationError("Subscription start date is required when auto-generation is enabled.")
            )
        
        return cleaned_data


class BulkInvoiceGenerateForm(forms.Form):
    """Form for bulk generating monthly invoices"""
    
    invoice_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text="Date for the new invoices (usually 1st of month)"
    )
    
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        help_text="Leave blank to use 30 days from invoice date"
    )
    
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.filter(is_active=True, auto_generate_invoices=True),
        widget=forms.SelectMultiple(attrs={"class": "form-control", "size": "10"}),
        help_text="Select companies to generate invoices for"
    )
    
    apply_credit = forms.BooleanField(
        required=False,
        initial=True,
        label="Apply credit balances",
        help_text="Automatically apply any credit balances to new invoices"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add credit balance information to company choices
        if 'companies' in self.fields:
            companies = self.fields['companies'].queryset
            choices = []
            for company in companies:
                credit = company.get_credit_balance()
                if credit > 0:
                    months, until, _ = company.get_coverage_info()
                    until_str = until.strftime("%Y-%m-%d") if until else "Unknown"
                    label = f"{company.business_name or company.name} - Credit: R{credit:,.2f} ({months} months)"
                else:
                    label = f"{company.business_name or company.name}"
                choices.append((company.pk, label))
            self.fields['companies'].choices = choices
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Set default due date if not provided
        if not cleaned_data.get("due_date"):
            invoice_date = cleaned_data.get("invoice_date")
            if invoice_date:
                cleaned_data["due_date"] = invoice_date + timezone.timedelta(days=30)
        
        # Ensure at least one company is selected
        if not cleaned_data.get("companies"):
            raise ValidationError("Please select at least one company.")
        
        return cleaned_data