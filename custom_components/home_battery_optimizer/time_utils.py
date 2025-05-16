from datetime import datetime, timedelta

def get_next_hour():
    now = datetime.now()
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

def format_time(hour):
    return hour.strftime("%H:%M")

def time_difference(start_time, end_time):
    return (end_time - start_time).total_seconds() / 3600

def is_time_in_range(start_time, end_time, check_time):
    if start_time <= end_time:
        return start_time <= check_time <= end_time
    else:
        return check_time >= start_time or check_time <= end_time
    
def get_schedule_hours(start_hour, duration):
    return [start_hour + timedelta(hours=i) for i in range(duration)]