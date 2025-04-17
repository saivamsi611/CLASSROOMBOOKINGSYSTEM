from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail, EmailMessage
from datetime import datetime
from django.contrib.auth.signals import user_logged_in
from django.conf import settings
from mixpanel import Mixpanel
import logging
from .models import Room, Booking
from .forms import RoomForm  # Assuming a RoomForm is created for editing rooms
# Initialize Mixpanel with your token
mp = Mixpanel(settings.MIXPANEL_TOKEN)
# ✅ Track User Login
def track_login(sender, request, user, **kwargs):
    user_group = user.groups.values_list("name", flat=True).first() or "Unknown"
    mp.track(user.id, "User Logged In", {
        "Username": user.username,
        "Role": "Admin" if user.is_staff else user_group,
    })
user_logged_in.connect(track_login)
# ✅ Home Page
def home(request):
    if request.user.groups.filter(name='Student').exists():
        return redirect('student_dashboard')
    return render(request, 'home.html')
# ✅ Login View
def login_view(request):
    if request.user.is_authenticated:
        return redirect_based_on_role(request)
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect_based_on_role(request)
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})
# ✅ Redirect Based on Role
def redirect_based_on_role(request):
    user = request.user
    if user.is_staff:
        return redirect('admin_dashboard')
    elif user.groups.filter(name='Teacher').exists():
        return redirect('teacher_dashboard')
    elif user.groups.filter(name='Student').exists():
        return redirect('student_dashboard')
    else:
        return redirect('home')
# ✅ Logout
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('home')
# ✅ Book Room
@login_required
def book_room(request):
    if request.method == "POST":
        room_id = request.POST.get("room_id")
        date = request.POST.get("date")
        start_time = request.POST.get("start_time")
        try:
            room = Room.objects.get(id=room_id)
            time_slot = datetime.strptime(start_time, "%H:%M").time()
            
            existing_booking = Booking.objects.filter(room=room, date=date, time_slot=time_slot).exists()
            if existing_booking:
                messages.error(request, "Room is already booked for the selected time slot.")
            else:
                # Assign teacher to the room if the user is a teacher
                if request.user.groups.filter(name="Teacher").exists():
                    room.teacher = request.user
                    room.save()
                booking = Booking.objects.create(
                    room=room,
                    date=date,
                    time_slot=time_slot,
                    booked_by=request.user.username,
                    user=request.user,
                    email=request.user.email,
                )
                # Tracking Event for Mixpanel
                mp.track(request.user.id, "Room Booked", {
                    "Room": room.name,
                    "Date": date,
                    "Time Slot": start_time,
                    "User": request.user.username,
                })
                booking.send_booking_email()
                messages.success(request, "Room booked successfully!")
                return redirect("home")
        except Room.DoesNotExist:
            messages.error(request, "Room not found.")
    rooms = Room.objects.filter(is_active=True)
    return render(request, "book_room.html", {"rooms": rooms})
# ✅ Cancel Booking
@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if booking.user == request.user:
        booking.delete()
        # Track cancellation event in Mixpanel
        mp.track(request.user.id, "Booking Cancelled", {
            "Room": booking.room.name,
            "Date": booking.date,
            "Time Slot": booking.time_slot.strftime("%H:%M"),
            "User": request.user.username,
        })
        messages.success(request, "Booking cancelled successfully.")
    return redirect("view_schedule")
# ✅ View Schedule (Student & Teacher)
@login_required
def view_schedule(request):
    bookings = Booking.objects.filter(user=request.user)
    return render(request, 'view_schedule.html', {'bookings': bookings})
# ✅ View All Bookings (Admin)
@login_required
def view_all_bookings(request):
    if not request.user.is_staff:
        messages.error(request, "Unauthorized access.")
        return redirect('home')
    bookings = Booking.objects.all()
    return render(request, 'view_all_bookings.html', {'bookings': bookings})
# ✅ Manage Rooms (Admin)
@login_required
def manage_rooms(request):
    rooms = Room.objects.all()
    return render(request, 'manage_rooms.html', {'rooms': rooms})
# ✅ Edit Room (Admin)
@login_required
def edit_room(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    if request.method == "POST":
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, "Room updated successfully.")
            return redirect('manage_rooms')
    else:
        form = RoomForm(instance=room)
    return render(request, 'edit_room.html', {'form': form})
# ✅ Delete Room (Admin)
@login_required
def delete_room(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    room.delete()
    messages.success(request, "Room deleted successfully.")
    return redirect('manage_rooms')
# ✅ Student Dashboard
@login_required
def student_dashboard(request):
    # Ensure only students can access
    if not request.user.groups.filter(name="Student").exists():
        messages.error(request, "Unauthorized access.")
        return redirect("home")
    # 🔍 Track this visit in Mixpanel
    mp.track(request.user.id, "Visited Dashboard", {
        "Username": request.user.username,
        "Role": "Student",  # Since it's already filtered here
    })
    # Fetch bookings made by teachers
    teacher_bookings = Booking.objects.filter(user__groups__name="Teacher")
    # Fetch bookings made by the student
    student_bookings = Booking.objects.filter(user=request.user)
    return render(
        request,
        "student_dashboard.html",
        {
            "teacher_bookings": teacher_bookings,
            "student_bookings": student_bookings,
        },
    )
# ✅ Teacher Dashboard
@login_required
def teacher_dashboard(request):
    return render(request, 'teacher_dashboard.html')
# ✅ Admin Dashboard
@login_required
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')
# ✅ Signup
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        role = request.POST.get('role')
        if form.is_valid():
            user = form.save()
            if role:
                try:
                    group = Group.objects.get(name=role)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    messages.error(request, "Invalid role selected.")
                    return redirect('signup')
            login(request, user)
            return redirect_based_on_role(request)
        else:
            messages.error(request, f'Error creating account: {form.errors}')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})
# ✅ Book Classroom with Mixpanel Tracking
def book_classroom(request):
    if request.method == 'POST':
        classroom = request.POST.get('classroom')
        time = request.POST.get('time')
        # You can save booking to database here (your logic)
        # Example:
        # Booking.objects.create(user=request.user, classroom=classroom, time=time)
        # Track this booking in Mixpanel
        mp.track(request.user.username, 'Booked Classroom', {
            'Classroom': classroom,
            'Time': time,
            'Role': 'Student'  # You can use real role if you have one
        })
        return redirect('view_schedule')  # Go back to schedule page
    return render(request, 'book_classroom.html')
