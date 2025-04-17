# myapp1/forms.py
from django import forms
from .models import Room, Booking
from datetime import time

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'capacity', 'teacher', 'is_active']  # Include the fields you need

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['room', 'date', 'time_slot', 'booked_by', 'user']

    time_slot = forms.TimeField(required=True)  # Make it mandatory to catch errors
