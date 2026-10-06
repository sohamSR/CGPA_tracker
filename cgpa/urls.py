from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('enroll/', views.enroll_course_view, name='enroll_course'),
    path('unenroll/<int:course_id>/', views.unenroll_course_view, name='unenroll_course'),
]
