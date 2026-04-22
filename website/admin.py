# core/admin.py
from django.contrib import admin
from .models import Project, Technology, ProjectImage

class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    fields = ("image", "caption", "order")
    ordering = ("order",)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "project_type", "status")
    list_filter = ("status", "technologies")
    search_fields = ("title", "description")
    filter_horizontal = ("technologies",)
    inlines = [ProjectImageInline]

admin.site.register(Technology)
