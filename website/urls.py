from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('request-callback/', views.request_callback, name='request_callback'),
    path('test-email/', views.test_email, name='test_email'),
    path('services/', views.services, name='services'),
    path('services/<slug:service_slug>/', views.service_detail, name='service_detail'),
    path('projects/', views.projects, name='projects'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path("website-150/", views.website_150, name="website_150"),
]