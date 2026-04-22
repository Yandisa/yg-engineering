from django.db import models

class Technology(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    class Meta:
        verbose_name_plural = "Technologies"
    
    def __str__(self): 
        return self.name

class Project(models.Model):
    class Status(models.TextChoices):
        LIVE = "live", "Live"
        DEVELOPMENT = "development", "In Development"
        COMPLETED = "completed", "Completed"

    title = models.CharField(max_length=200)
    project_type = models.CharField(max_length=120)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DEVELOPMENT)
    technologies = models.ManyToManyField(Technology, blank=True)
    link = models.URLField(blank=True)  # optional as requested
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self): 
        return self.title

    @property
    def status_badge_text(self): 
        return self.get_status_display()

    @property
    def status_badge_class(self): 
        return f"status-{self.status}"

class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="projects/screenshots/")
    caption = models.CharField(max_length=120, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.project.title} – {self.caption or self.image.name}"