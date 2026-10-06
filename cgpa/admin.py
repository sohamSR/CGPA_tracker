from django.contrib import admin
from .models import MasterCourse, MasterComponent, MasterGradeCutoff, StudentCourse, SystemSettings

class MasterComponentInline(admin.TabularInline):
    model = MasterComponent
    extra = 1

class MasterGradeCutoffInline(admin.TabularInline):
    model = MasterGradeCutoff
    fields = ('grade', 'min_marks', 'grade_point')
    extra = 1

@admin.register(MasterCourse)
class MasterCourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'credits')
    inlines = [MasterComponentInline, MasterGradeCutoffInline]

@admin.register(StudentCourse)
class StudentCourseAdmin(admin.ModelAdmin):
    list_display = ('user', 'master_course')
    list_filter = ('master_course', 'user')

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'allow_user_subject_cutoffs')
