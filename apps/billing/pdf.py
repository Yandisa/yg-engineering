from decimal import Decimal
import re
from datetime import datetime, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import black, grey


def money(amount: Decimal) -> str:
    return f"R{amount:,.2f}"


def draw_invoice_pdf(response, invoice, company: dict):
    """
    company dict example:
    {
      "name": "YG Engineering",
      "website": "www.ygengineering.co.za",
      "email": "info@ygengineering.co.za",
      "phone": "073...",
      "address": "Johannesburg, South Africa",
      "logo_path": "/abs/path/to/logo.png",
      "bank_name": "Capitec Bank",
      "account_name": "YG Engineering",
      "account_number": "2509492051",
      "branch_code": "470010",
    }
    """
    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    left = 18 * mm
    right = width - 18 * mm
    top = height - 18 * mm

    # ============================================================
    # HEADER
    # ============================================================
    y = top

    # Logo (optional)
    logo_path = company.get("logo_path")
    if logo_path:
        try:
            img = ImageReader(logo_path)
            c.drawImage(img, left, y - 22 * mm, width=32 * mm, height=20 * mm, mask="auto")
        except Exception:
            pass

    # Company name
    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(right, y, company.get("name", "Company"))

    # Company details
    c.setFont("Helvetica", 9)
    y2 = y - 5 * mm
    for line in [
        company.get("address", ""),
        company.get("phone", ""),
        company.get("email", ""),
        company.get("website", ""),
    ]:
        if line:
            c.setFillColor(grey)
            c.drawRightString(right, y2, line)
            c.setFillColor(black)
            y2 -= 4 * mm

    # ============================================================
    # TITLE
    # ============================================================
    y = top - 30 * mm
    c.setFont("Helvetica-Bold", 24)
    c.drawString(left, y, "INVOICE")

    # Simple line under title
    c.setLineWidth(0.5)
    c.setStrokeColor(grey)
    c.line(left, y - 3 * mm, left + 60 * mm, y - 3 * mm)
    c.setStrokeColor(black)

    # ============================================================
    # INVOICE DETAILS
    # ============================================================
    c.setFont("Helvetica", 10)
    meta_y = y - 10 * mm
    c.drawString(left, meta_y, f"Invoice No: {invoice.invoice_number}")
    c.drawString(left, meta_y - 5 * mm, f"Invoice Date: {invoice.invoice_date}")
    
    # Due date
    due_date_text = f"Due Date: {invoice.due_date}"
    c.setFont("Helvetica-Bold", 10)
    
    if hasattr(invoice, 'is_overdue') and invoice.is_overdue:
        c.drawString(left, meta_y - 10 * mm, f"OVERDUE - {due_date_text}")
    else:
        c.drawString(left, meta_y - 10 * mm, due_date_text)
    
    c.setFont("Helvetica", 10)

    # Subscription period
    meta_offset = 0
    if invoice.period_start and invoice.period_end:
        period_text = f"Period: {invoice.period_start.strftime('%d %b %Y')} to {invoice.period_end.strftime('%d %b %Y')}"
        c.setFont("Helvetica", 9)
        c.setFillColor(grey)
        c.drawString(left, meta_y - 15 * mm, period_text)
        c.setFillColor(black)
        c.setFont("Helvetica", 10)
        meta_offset = 5 * mm

    # ============================================================
    # BILL TO
    # ============================================================
    box_top = meta_y - (20 * mm) - meta_offset
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, box_top, "Bill To")

    c.setFont("Helvetica", 10)
    bill_lines = [
        invoice.bill_to_name,
        invoice.bill_to_company,
        invoice.bill_to_email,
        invoice.bill_to_phone,
    ]
    if invoice.bill_to_address:
        bill_lines += invoice.bill_to_address.splitlines()

    by = box_top - 6 * mm
    for line in [x for x in bill_lines if x]:
        c.drawString(left, by, line)
        by -= 5 * mm

    # ============================================================
    # ITEMS TABLE
    # ============================================================
    table_top = by - 10 * mm
    
    # Table headers
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, table_top, "Description")
    c.drawRightString(right - 55 * mm, table_top, "Qty")
    c.drawRightString(right - 25 * mm, table_top, "Unit")
    c.drawRightString(right, table_top, "Total")

    # Header underline
    c.setLineWidth(0.3)
    c.setStrokeColor(grey)
    c.line(left, table_top - 2 * mm, right, table_top - 2 * mm)

    # Items rows
    c.setFont("Helvetica", 10)
    row_y = table_top - 9 * mm

    for item in invoice.items.all():
        c.drawString(left, row_y, item.description[:65])
        c.drawRightString(right - 55 * mm, row_y, f"{item.qty}")
        c.drawRightString(right - 25 * mm, row_y, money(item.unit_price))
        c.drawRightString(right, row_y, money(item.line_total))
        row_y -= 7 * mm

        # New page if needed
        if row_y < 130 * mm:
            c.showPage()
            c.setFont("Helvetica", 10)
            row_y = top - 20 * mm

    # ============================================================
    # TOTALS
    # ============================================================
    totals_y = max(row_y - 6 * mm, 150 * mm)

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(right - 25 * mm, totals_y, "Subtotal:")
    c.drawRightString(right, totals_y, money(invoice.subtotal))

    c.drawRightString(right - 25 * mm, totals_y - 6 * mm, "Paid:")
    c.drawRightString(right, totals_y - 6 * mm, money(invoice.amount_paid))

    # Amount Due or Credit
    c.setFont("Helvetica-Bold", 12)
    if invoice.credit_amount > 0:
        c.drawRightString(right - 25 * mm, totals_y - 14 * mm, "Credit:")
        c.drawRightString(right, totals_y - 14 * mm, money(invoice.credit_amount))
    else:
        c.drawRightString(right - 25 * mm, totals_y - 14 * mm, "Amount Due:")
        c.drawRightString(right, totals_y - 14 * mm, money(invoice.amount_due))

    # ============================================================
    # CREDIT COVERAGE
    # ============================================================
    credit_info_y = totals_y - 26 * mm
    if invoice.credit_amount > 0 and invoice.company:
        monthly_rate = invoice.company.monthly_rate
        months_covered = (invoice.credit_amount / monthly_rate).quantize(Decimal("0.01"))
        
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left, credit_info_y, "Credit Coverage")
        
        c.setFont("Helvetica", 8)
        c.setFillColor(grey)
        c.drawString(left, credit_info_y - 4 * mm, 
                    f"This credit covers approximately {months_covered} months of service")
        
        if invoice.coverage_until:
            c.drawString(left, credit_info_y - 7 * mm,
                        f"Valid until: {invoice.coverage_until.strftime('%d %B %Y')}")
        
        c.setFillColor(black)
        credit_info_offset = 12 * mm
    else:
        credit_info_offset = 0

    # ============================================================
    # STATEMENT
    # ============================================================
    last = getattr(invoice, "last_payment", None)
    statement_y = totals_y - 30 * mm - credit_info_offset

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, statement_y, "Statement")

    c.setFont("Helvetica", 10)
    
    # Last payment line
    if last:
        payment_obj = last() if callable(last) else last
        if payment_obj:
            method_display = ""
            try:
                method_display = payment_obj.get_method_display()
            except Exception:
                method_display = ""

            ref = f" | Ref: {payment_obj.reference}" if getattr(payment_obj, "reference", "") else ""
            meth = f" | {method_display}" if method_display else ""

            c.drawString(
                left,
                statement_y - 6 * mm,
                f"Last payment: {money(payment_obj.amount)} on {payment_obj.payment_date.strftime('%Y-%m-%d')}{meth}{ref}",
            )
            last_payment_y = statement_y - 6 * mm
        else:
            c.drawString(left, statement_y - 6 * mm, "Last payment: None recorded")
            last_payment_y = statement_y - 6 * mm
    else:
        c.drawString(left, statement_y - 6 * mm, "Last payment: None recorded")
        last_payment_y = statement_y - 6 * mm

    # Balance status
    status_y = last_payment_y - 8 * mm
    c.setFont("Helvetica-Bold", 10)
    
    if invoice.credit_amount > 0:
        c.drawString(left, status_y, f"STATUS: CREDIT - R{invoice.credit_amount}")
    elif invoice.amount_due > 0:
        c.drawString(left, status_y, f"STATUS: OWES - R{invoice.amount_due}")
    else:
        c.drawString(left, status_y, "STATUS: PAID")
    
    c.setFont("Helvetica", 10)

    # ============================================================
    # PAID/CREDIT STAMP (very subtle)
    # ============================================================
    if invoice.is_paid and invoice.credit_amount == 0:
        c.saveState()
        c.setFont("Helvetica-Bold", 60)
        c.setFillColor(grey)
        c.setFillAlpha(0.2)
        c.translate(width / 2, height / 2)
        c.rotate(25)
        c.drawCentredString(0, 0, "PAID")
        c.restoreState()
    elif invoice.credit_amount > 0:
        c.saveState()
        c.setFont("Helvetica-Bold", 40)
        c.setFillColor(grey)
        c.setFillAlpha(0.2)
        c.translate(width / 2, height / 2 - 20 * mm)
        c.rotate(25)
        c.drawCentredString(0, 0, "CREDIT NOTE")
        c.restoreState()

    # ============================================================
    # BANKING DETAILS
    # ============================================================
    bank_y = 75 * mm
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, bank_y + 18 * mm, "Banking Details")

    c.setFont("Helvetica", 10)
    
    # Get client name for reference
    client_ref = invoice.bill_to_company or invoice.bill_to_name or "Client"
    client_ref = re.sub(r'[^a-zA-Z0-9]', '', client_ref)[:15]
    
    bank_lines = [
        f"Bank: {company.get('bank_name', 'Capitec Bank')}",
        f"Account Name: {company.get('account_name', 'YG Engineering')}",
        f"Account Number: {company.get('account_number', '2509492051')}",
        f"Branch Code: {company.get('branch_code', '470010')}",
        f"Reference: {client_ref} - {invoice.invoice_number}",
    ]
    
    yy = bank_y + 12 * mm
    for line in bank_lines:
        c.drawString(left, yy, line)
        yy -= 5 * mm

    # ============================================================
    # NOTES
    # ============================================================
    if invoice.notes:
        notes_y = bank_y - 10 * mm
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left, notes_y, "Notes")
        
        c.setFont("Helvetica", 9)
        yy = notes_y - 5 * mm
        for line in invoice.notes.splitlines()[:5]:
            c.drawString(left, yy, line)
            yy -= 4 * mm

        terms_y = yy - 10 * mm
    else:
        terms_y = bank_y - 15 * mm

    # ============================================================
    # SUBSCRIPTION TERMS
    # ============================================================
    # Separator line
    c.setLineWidth(0.3)
    c.setStrokeColor(grey)
    c.line(left, terms_y + 5 * mm, right, terms_y + 5 * mm)
    
    # Terms
    c.setFont("Helvetica", 7)
    c.setFillColor(grey)
    
    monthly_rate = invoice.company.monthly_rate if invoice.company else Decimal("150.00")
    
    terms_lines = [
        f"Monthly subscription: R{monthly_rate:,.2f} due on the 1st of each month.",
        "Reminders: Sent 7 days before due date and on the due date.",
        "Suspension: If payment not received within 7 days after due date, services will be suspended.",
        "Reactivation: 50% reactivation fee + full outstanding amount payable before restoration.",
        f"Support: www.ygengineering.co.za",
    ]
    
    term_y = terms_y
    for line in terms_lines:
        c.drawString(left, term_y, line)
        term_y -= 3.5 * mm
    
    c.setFillColor(black)
    
    c.showPage()
    c.save()