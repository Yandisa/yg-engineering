from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from website.sitemaps import StaticViewSitemap
from website import views as website_views

sitemaps = {
    "static": StaticViewSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # Admin dashboard
    path('dashboard/', website_views.dashboard, name='dashboard'),

    # Invoice / billing app
    path('invoices/', include('apps.billing.urls')),

    # Public website
    path('', include('website.urls')),

    # Sitemap & robots
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
