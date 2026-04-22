from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    # Invoice URLs
    path("", views.invoice_list, name="invoice_list"),
    path("create/", views.invoice_create, name="invoice_create"),
    path("<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("<int:pk>/edit/", views.invoice_edit, name="invoice_edit"),
    path("<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path("<int:pk>/mark-paid/", views.invoice_mark_paid, name="invoice_mark_paid"),
    
    # Payment URLs
    path("<int:pk>/add-payment/", views.invoice_add_payment, name="invoice_add_payment"),
    path("<int:pk>/delete-payment/<int:payment_pk>/", views.invoice_delete_payment, name="invoice_delete_payment"),
    
    # Company URLs
    path("companies/", views.company_list, name="company_list"),
    path("companies/create/", views.company_create, name="company_create"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("companies/<int:pk>/edit/", views.company_edit, name="company_edit"),
    
    # Special Views
    path("overdue/", views.invoice_overdue, name="invoice_overdue"),
    path("credit-notes/", views.invoice_credit_notes, name="invoice_credit_notes"),
    path("generate-monthly/", views.generate_monthly_invoices, name="generate_monthly_invoices"),
    path("send-reminders/", views.send_reminders, name="send_reminders"),
]