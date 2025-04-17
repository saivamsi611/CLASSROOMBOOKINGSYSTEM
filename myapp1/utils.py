from mixpanel import Mixpanel
from django.conf import settings

mp = Mixpanel(settings.MIXPANEL_TOKEN)

def track_event(user, event_name, properties=None):
    """
    Track an event in Mixpanel.
    :param user: User object (optional)
    :param event_name: Event name string
    :param properties: Dictionary of event properties
    """
    try:
        user_id = user.id if user else "Anonymous"
        event_properties = properties or {}
        event_properties["user_id"] = user_id  # Add user ID to the properties
        
        mp.track(user_id, event_name, event_properties)
    except Exception as e:
        print(f"Mixpanel tracking error: {e}")
