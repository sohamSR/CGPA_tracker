from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from .models import (
    MasterCourse, 
    MasterGradeCutoff, 
    StudentCourse, 
    StudentComponentMark, 
    StudentGradeCutoff,
    SystemSettings
)

# --- AUTHENTICATION VIEWS ---

def register_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'cgpa/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'cgpa/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# --- COURSE ENROLMENT VIEWS ---

@login_required(login_url='login')
def enroll_course_view(request):
    if request.method == "POST":
        master_id = request.POST.get('course_id')
        if master_id:
            master_course = get_object_or_404(MasterCourse, id=master_id)
            student_course, created = StudentCourse.objects.get_or_create(
                user=request.user, master_course=master_course
            )
            for comp in master_course.components.all():
                StudentComponentMark.objects.get_or_create(
                    student_course=student_course, master_component=comp
                )
    return redirect('index')


@login_required(login_url='login')
def unenroll_course_view(request, course_id):
    if request.method == "POST":
        student_course = get_object_or_404(StudentCourse, id=course_id, user=request.user)
        student_course.delete()
    return redirect('index')


# --- MAIN DASHBOARD VIEW ---

@login_required(login_url='login')
def index(request):
    settings_obj, _ = SystemSettings.objects.get_or_create(id=1)
    can_edit_cutoffs = request.user.is_staff or settings_obj.allow_user_subject_cutoffs

    if request.method == "POST":
        # 1. Save User-Specific Personal Cutoffs
        if "save_subject_cutoffs" in request.POST and can_edit_cutoffs:
            for key, value in request.POST.items():
                if key.startswith("cutoff_") and value.strip() != "":
                    # Input format: cutoff_<student_course_id>_<master_cutoff_id>
                    parts = key.split("_")
                    if len(parts) == 3:
                        sc_id, master_cutoff_id = parts[1], parts[2]
                        try:
                            sc = StudentCourse.objects.get(id=sc_id, user=request.user)
                            master_cutoff = MasterGradeCutoff.objects.get(
                                id=master_cutoff_id, master_course=sc.master_course
                            )
                            
                            # Saves custom cutoff strictly bound to this user's StudentCourse
                            StudentGradeCutoff.objects.update_or_create(
                                student_course=sc,
                                master_cutoff=master_cutoff,
                                defaults={'min_marks': float(value)}
                            )
                        except (StudentCourse.DoesNotExist, MasterGradeCutoff.DoesNotExist, ValueError):
                            pass
            return redirect('index')

        # 2. Save Student Marks & Targets
        for key, value in request.POST.items():
            if key.startswith("marks_"):
                mark_id = key.split("_")[1]
                try:
                    mark_obj = StudentComponentMark.objects.get(id=mark_id, student_course__user=request.user)
                    if value.strip() != "":
                        mark_obj.obtained_marks = float(value)
                        mark_obj.is_completed = True
                    else:
                        mark_obj.obtained_marks = None
                        mark_obj.is_completed = False
                    mark_obj.save()
                except (StudentComponentMark.DoesNotExist, ValueError):
                    pass

            elif key.startswith("target_course_"):
                course_id = key.split("_")[2]
                request.session[f"target_course_{course_id}"] = value

        return redirect('index')

    enrolled_courses = StudentCourse.objects.filter(user=request.user).select_related('master_course')
    enrolled_master_ids = enrolled_courses.values_list('master_course_id', flat=True)
    available_courses = MasterCourse.objects.exclude(id__in=enrolled_master_ids)

    course_data = []
    total_credits = 0.0
    total_weighted_points = 0.0

    for sc in enrolled_courses:
        master = sc.master_course
        marks = StudentComponentMark.objects.filter(student_course=sc).select_related('master_component')
        
        # Build Cutoffs List (Prefers user's personal custom cutoffs; falls back to master course cutoffs)
        master_cutoffs = master.cutoffs.all().order_by('-min_marks')
        custom_cutoffs_map = {c.master_cutoff_id: c.min_marks for c in sc.custom_cutoffs.all()}

        cutoffs = []
        for mc in master_cutoffs:
            user_min_marks = custom_cutoffs_map.get(mc.id, mc.min_marks)
            cutoffs.append({
                'master_cutoff_id': mc.id,
                'grade': mc.grade,
                'grade_point': mc.grade_point,
                'min_marks': user_min_marks,
            })
        
        cutoffs.sort(key=lambda x: x['min_marks'], reverse=True)

        completed = [m for m in marks if m.is_completed and m.obtained_marks is not None]
        pending = [m for m in marks if not m.is_completed or m.obtained_marks is None]

        secured_weight = sum(
            (m.obtained_marks / m.master_component.max_marks) * m.master_component.weightage
            for m in completed if m.master_component.max_marks > 0
        )
        remaining_weight = sum(m.master_component.weightage for m in pending)
        max_possible_weight = secured_weight + remaining_weight

        max_achievable_cutoff = None
        for c in cutoffs:
            if max_possible_weight >= c['min_marks']:
                max_achievable_cutoff = c
                break

        max_achievable_grade = max_achievable_cutoff['grade'] if max_achievable_cutoff else "F"
        max_achievable_points = max_achievable_cutoff['grade_point'] if max_achievable_cutoff else 0.0

        all_completed = len(pending) == 0 and len(marks) > 0
        is_unattainable = False
        can_achieve_better = False
        higher_req_percentage = 0

        if all_completed:
            selected_grade = max_achievable_grade
            grade_points = max_achievable_points
            target_cutoff = max_achievable_cutoff['min_marks'] if max_achievable_cutoff else 0.0
            req_percentage = 0
            pending_targets = []
        else:
            session_key = f"target_course_{sc.id}"
            default_grade = cutoffs[0]['grade'] if cutoffs else "A"
            selected_grade = request.session.get(session_key, default_grade)

            target_cutoff_obj = next((c for c in cutoffs if c['grade'] == selected_grade), None)
            target_cutoff = target_cutoff_obj['min_marks'] if target_cutoff_obj else 80.0
            
            needed_weight = target_cutoff - secured_weight
            req_percentage = (needed_weight / remaining_weight * 100) if remaining_weight > 0 else 0

            if req_percentage > 100:
                is_unattainable = True
                grade_points = max_achievable_points
            else:
                grade_points = target_cutoff_obj['grade_point'] if target_cutoff_obj else 0.0
                if max_achievable_cutoff and target_cutoff_obj:
                    if max_achievable_cutoff['grade_point'] > target_cutoff_obj['grade_point']:
                        can_achieve_better = True
                        higher_needed = max_achievable_cutoff['min_marks'] - secured_weight
                        higher_req_percentage = round((higher_needed / remaining_weight * 100), 1) if remaining_weight > 0 else 0

            pending_targets = []
            for m in pending:
                comp = m.master_component
                needed_marks = (req_percentage / 100) * comp.max_marks
                pending_targets.append({
                    'name': comp.name,
                    'weightage': comp.weightage,
                    'max_marks': comp.max_marks,
                    'needed_marks': round(needed_marks, 2),
                })

        course_credits = master.credits
        total_credits += course_credits
        total_weighted_points += (grade_points * course_credits)

        course_data.append({
            'student_course': sc,
            'master': master,
            'marks': marks,
            'pending_targets': pending_targets,
            'cutoffs': cutoffs,
            'secured_weight': round(secured_weight, 2),
            'req_percentage': round(req_percentage, 1),
            'selected_grade': selected_grade,
            'target_cutoff': target_cutoff,
            'grade_points': grade_points,
            'all_completed': all_completed,
            'is_unattainable': is_unattainable,
            'can_achieve_better': can_achieve_better,
            'higher_req_percentage': higher_req_percentage,
            'max_achievable_grade': max_achievable_grade,
            'max_achievable_points': max_achievable_points,
        })

    target_sgpa = round(total_weighted_points / total_credits, 2) if total_credits > 0 else 0.0

    context = {
        'course_data': course_data,
        'available_courses': available_courses,
        'can_edit_cutoffs': can_edit_cutoffs,
        'total_credits': total_credits,
        'target_sgpa': target_sgpa,
    }
    return render(request, 'cgpa/index.html', context)
