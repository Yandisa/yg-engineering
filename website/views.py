import logging
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.urls import reverse
from django.utils.text import slugify
from django.core.paginator import Paginator
from django.db.models import Q

from .forms import ContactForm, CallbackRequestForm
from .models import Project, Technology

logger = logging.getLogger(__name__)

# Service definitions
SERVICES = {
    'websites-online-stores': {
        'title': 'Websites & Online Stores',
        'description': 'Professional websites and e-commerce solutions that drive results.',
        'features': [
            'Responsive design for all devices',
            'SEO optimization',
            'Content management system',
            'E-commerce integration',
            'Payment gateway setup',
            'Analytics and tracking'
        ],
        'starting_price': 'R 8,500',
        'icon': 'globe'
    },
    'custom-web-applications': {
        'title': 'Custom Web Applications',
        'description': 'Tailored web applications built to solve your specific business challenges.',
        'features': [
            'Custom functionality',
            'Database design',
            'User authentication',
            'API integration',
            'Scalable architecture',
            'Ongoing support'
        ],
        'starting_price': 'R 25,000',
        'icon': 'code'
    },
    'business-systems': {
        'title': 'Business Systems',
        'description': 'Streamline operations with custom business management systems.',
        'features': [
            'Inventory management',
            'Customer relationship management',
            'Reporting and analytics',
            'Workflow automation',
            'Multi-user access',
            'Data backup and security'
        ],
        'starting_price': 'R 35,000',
        'icon': 'briefcase'
    },
    'booking-systems': {
        'title': 'Booking & Reservation Systems',
        'description': 'Automated booking systems that work 24/7 for your business.',
        'features': [
            'Online booking calendar',
            'Payment processing',
            'Automated confirmations',
            'Customer management',
            'Reporting dashboard',
            'Mobile-friendly interface'
        ],
        'starting_price': 'R 18,000',
        'icon': 'calendar'
    },
    'data-dashboards': {
        'title': 'Data-Driven Dashboards',
        'description': 'Transform your data into actionable insights with custom dashboards.',
        'features': [
            'Real-time data visualization',
            'Custom charts and graphs',
            'KPI tracking',
            'Automated reports',
            'Data integration',
            'Mobile access'
        ],
        'starting_price': 'R 22,000',
        'icon': 'bar-chart'
    },
    'maintenance-support': {
        'title': 'Website Maintenance & Support',
        'description': 'Keep your website secure, updated, and performing at its best.',
        'features': [
            'Regular security updates',
            'Performance optimization',
            'Content updates',
            'Backup management',
            'Technical support',
            'Monthly reports'
        ],
        'starting_price': 'R 1,200/month',
        'icon': 'settings'
    }
}

# Nice labels for subjects (key=slug, value=human label)
SUBJECTS = [
    "Websites and Online Stores",
    "Website Maintenance & Support",
    "Custom Web Applications",
    "Booking and Reservation Systems",
    "Business Systems",
    "Data-Driven Dashboards",
]
SLUG_TO_LABEL = {slugify(s): s for s in SUBJECTS}

def label_for_subject(slug: str) -> str:
    slug = (slug or "").strip()
    return SLUG_TO_LABEL.get(slug, slug.replace("-", " ").title())

def request_callback(request):
    if request.method != "POST":
        return redirect("home")

    form = CallbackRequestForm(request.POST)
    referer = request.META.get("HTTP_REFERER") or "/"

    if form.is_valid():
        cd = form.cleaned_data
        subject = "New Callback Request — YG Engineering"
        body = (
            "A user requested a callback.\n\n"
            f"Name: {cd['full_name']}\n"
            f"Phone: {cd['phone']}\n"
            f"Best time: {cd.get('best_time') or 'Not specified'}\n"
            f"Notes: {cd.get('notes') or '—'}\n"
            f"From page: {cd.get('page') or referer}\n"
        )
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [settings.CONTACT_RECIPIENT_EMAIL])
            messages.success(request, "Thanks! We'll call you back shortly.")
        except Exception:
            messages.error(request, "We couldn't send your request right now. Please try again or email us.")
    else:
        messages.error(request, "Please check the form and try again.")

    return redirect(referer)

def test_email(request):
    try:
        sent = send_mail(
            "Test email",
            "If you see this, SMTP works.",
            settings.DEFAULT_FROM_EMAIL,
            [settings.CONTACT_RECIPIENT_EMAIL],
            fail_silently=False,
        )
        return HttpResponse(f"Sent={sent}", content_type="text/plain")
    except Exception as e:
        logger.exception("SMTP test failed")
        return HttpResponse(f"Email failed: {e}", status=500, content_type="text/plain")

def home(request):
    # Get featured projects
    featured_projects = Project.objects.filter(status=Project.Status.LIVE).order_by("-id")[:6]

    # Get recent projects for showcase
    recent_projects = Project.objects.all().order_by("-id")[:3]

    # Get technologies for showcase
    technologies = Technology.objects.all()[:8]

    if request.method == "POST":
        form = ContactForm(request.POST, allowed_subjects=SLUG_TO_LABEL)
        if form.is_valid():
            cd = form.cleaned_data
            subject_label = label_for_subject(cd["subject"])
            site_name = getattr(settings, "SITE_NAME", "YG Engineering")
            ctx = {
                "first_name": cd["first_name"],
                "last_name": cd["last_name"],
                "email": cd["email"],
                "company": cd.get("company") or "Not provided",
                "subject": subject_label,
                "subject_slug": cd["subject"],
                "message": cd["message"],
                "site_name": site_name,
            }

            try:
                try:
                    admin_body = render_to_string("emails/contact_admin.txt", ctx)
                except TemplateDoesNotExist:
                    admin_body = (
                        f"Name: {ctx['first_name']} {ctx['last_name']}\n"
                        f"Email: {ctx['email']}\nCompany: {ctx['company']}\n"
                        f"Subject: {ctx['subject']} ({ctx['subject_slug']})\n\n{ctx['message']}"
                    )
                try:
                    user_body = render_to_string("emails/contact_user.txt", ctx)
                except TemplateDoesNotExist:
                    user_body = (
                        f"Hi {ctx['first_name']},\n\nThanks for contacting {site_name}.\n\n"
                        f"Subject: {ctx['subject']}\nMessage: {ctx['message']}\n"
                        f"We'll get back to you soon."
                    )

                send_mail(
                    subject=f"New Contact: {subject_label}",
                    message=admin_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_RECIPIENT_EMAIL],
                    fail_silently=False,
                )
                send_mail(
                    subject=f"Thank you for contacting {site_name}",
                    message=user_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[ctx["email"]],
                    fail_silently=False,
                )

                messages.success(request, "Your message has been sent successfully! We'll contact you soon.")
                return redirect(f"{reverse('home')}#contact")

            except Exception:
                logger.exception("Contact email send failed")
                messages.error(request, "We couldn't send your message. Please try again later.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        preselect = (request.GET.get("subject") or "").strip()
        form = ContactForm(initial={"subject": preselect}, allowed_subjects=SLUG_TO_LABEL)

    return render(request, "index.html", {
        "featured_projects": featured_projects,
        "recent_projects": recent_projects,
        "technologies": technologies,
        "form": form,
        "subjects": SLUG_TO_LABEL,
        "services": SERVICES,
    })

def services(request):
    """Services overview page"""
    return render(request, "services.html", {
        "services": SERVICES,
    })

def service_detail(request, service_slug):
    """Individual service detail page"""
    if service_slug not in SERVICES:
        raise Http404("Service not found")

    service = SERVICES[service_slug]
    related_projects = Project.objects.filter(
        project_type__icontains=service['title'].split()[0]
    )[:3]

    return render(request, "service_detail.html", {
        "service": service,
        "service_slug": service_slug,
        "related_projects": related_projects,
    })

def projects(request):
    """Projects showcase page with filtering"""
    projects_list = Project.objects.all().order_by("-id")

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter and status_filter in [choice[0] for choice in Project.Status.choices]:
        projects_list = projects_list.filter(status=status_filter)

    # Filter by technology
    tech_filter = request.GET.get('technology')
    if tech_filter:
        projects_list = projects_list.filter(technologies__name__icontains=tech_filter)

    # Search
    search_query = request.GET.get('search')
    if search_query:
        projects_list = projects_list.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(project_type__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(projects_list, 9)
    page_number = request.GET.get('page')
    projects_page = paginator.get_page(page_number)

    # Get all technologies for filter dropdown
    technologies = Technology.objects.all()

    return render(request, "projects.html", {
        "projects": projects_page,
        "technologies": technologies,
        "current_status": status_filter,
        "current_tech": tech_filter,
        "search_query": search_query,
        "status_choices": Project.Status.choices,
    })

def about(request):
    """About page"""
    team_stats = {
        'projects_completed': Project.objects.filter(status=Project.Status.COMPLETED).count(),
        'projects_live': Project.objects.filter(status=Project.Status.LIVE).count(),
        'technologies_used': Technology.objects.count(),
        'years_experience': 5,  # Update as needed
    }

    return render(request, "about.html", {
        "team_stats": team_stats,
    })


def website_150(request):
    return render(request, "website_150.html")


def contact(request):
    """Dedicated contact page"""
    if request.method == "POST":
        form = ContactForm(request.POST, allowed_subjects=SLUG_TO_LABEL)
        if form.is_valid():
            # Same logic as in home view
            cd = form.cleaned_data
            subject_label = label_for_subject(cd["subject"])
            site_name = getattr(settings, "SITE_NAME", "YG Engineering")
            ctx = {
                "first_name": cd["first_name"],
                "last_name": cd["last_name"],
                "email": cd["email"],
                "company": cd.get("company") or "Not provided",
                "subject": subject_label,
                "subject_slug": cd["subject"],
                "message": cd["message"],
                "site_name": site_name,
            }

            try:
                try:
                    admin_body = render_to_string("emails/contact_admin.txt", ctx)
                except TemplateDoesNotExist:
                    admin_body = (
                        f"Name: {ctx['first_name']} {ctx['last_name']}\n"
                        f"Email: {ctx['email']}\nCompany: {ctx['company']}\n"
                        f"Subject: {ctx['subject']} ({ctx['subject_slug']})\n\n{ctx['message']}"
                    )

                send_mail(
                    subject=f"New Contact: {subject_label}",
                    message=admin_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_RECIPIENT_EMAIL],
                    fail_silently=False,
                )

                messages.success(request, "Your message has been sent successfully! We'll contact you soon.")
                return redirect("contact")

            except Exception:
                logger.exception("Contact email send failed")
                messages.error(request, "We couldn't send your message. Please try again later.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ContactForm(allowed_subjects=SLUG_TO_LABEL)

    return render(request, "contact.html", {
        "form": form,
        "subjects": SLUG_TO_LABEL,
    })

def terms(request):
    """Terms and Conditions page"""
    return render(request, "terms.html")

def privacy(request):
    """Privacy Policy page"""
    return render(request, "privacy.html")

# -----------------------------------------------------------------------------
# Admin dashboard (login required)
# -----------------------------------------------------------------------------
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    return render(request, 'dashboard.html')
