from django.db import models
from django.contrib.auth.models import User


class SystemSettings(models.Model):
    allow_user_subject_cutoffs = models.BooleanField(
        default=True, 
        help_text="If checked, normal users can edit grade cutoffs for individual subjects."
    )

    def __str__(self):
        return "System Settings"


class MasterCourse(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    credits = models.FloatField(default=3.0)

    def __str__(self):
        return f"{self.code} - {self.name}"


class MasterComponent(models.Model):
    master_course = models.ForeignKey(MasterCourse, on_delete=models.CASCADE, related_name='components')
    name = models.CharField(max_length=50)
    weightage = models.FloatField(help_text="Weightage percentage (e.g., 30 for 30%)")
    max_marks = models.FloatField(default=100.0)

    def __str__(self):
        return f"{self.master_course.code} - {self.name} ({self.weightage}%)"


class MasterGradeCutoff(models.Model):
    master_course = models.ForeignKey(MasterCourse, on_delete=models.CASCADE, related_name='cutoffs')
    grade = models.CharField(max_length=5)
    grade_point = models.FloatField()
    min_marks = models.FloatField(help_text="Minimum total weighted marks required for this grade")

    class Meta:
        ordering = ['-min_marks']

    def __str__(self):
        return f"{self.master_course.code} - Grade {self.grade} (>= {self.min_marks}%)"


class StudentCourse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrolled_courses')
    master_course = models.ForeignKey(MasterCourse, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'master_course')

    def __str__(self):
        return f"{self.user.username} -> {self.master_course.code}"


class StudentComponentMark(models.Model):
    student_course = models.ForeignKey(StudentCourse, on_delete=models.CASCADE, related_name='marks')
    master_component = models.ForeignKey(MasterComponent, on_delete=models.CASCADE)
    obtained_marks = models.FloatField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student_course.user.username} - {self.master_component.name}: {self.obtained_marks}"


class StudentGradeCutoff(models.Model):
    student_course = models.ForeignKey(StudentCourse, on_delete=models.CASCADE, related_name='custom_cutoffs')
    master_cutoff = models.ForeignKey(MasterGradeCutoff, on_delete=models.CASCADE)
    min_marks = models.FloatField()

    class Meta:
        unique_together = ('student_course', 'master_cutoff')

    def __str__(self):
        return f"{self.student_course.user.username} - {self.student_course.master_course.code} - {self.master_cutoff.grade}: {self.min_marks}"
