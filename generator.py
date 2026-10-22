import csv
import json
import math
import random
import sys
from datetime import datetime, timedelta


# (7 Wochentage x 24 Stunden) Matrix
def make_random_matrix(logins_per_day, number_of_services):
    probability = logins_per_day / (24 * number_of_services)
    probability = min(probability, 1.0)

    matrix = []
    for weekday in range(7):
        row = []
        for hour in range(24):
            row.append(probability)
        matrix.append(row)
    return matrix


def make_pattern_matrix(hours, weekdays):
    probability_per_hour = [0.0] * 24
    for hour_range, probability in hours.items():
        first_hour, last_hour = read_hour_range(hour_range)
        for hour in range(first_hour, last_hour):
            probability_per_hour[hour] = probability

    matrix = []
    for weekday in range(7):
        row = []
        for hour in range(24):
            value = probability_per_hour[hour] * weekdays[weekday]
            value = min(value, 1.0)
            row.append(value)
        matrix.append(row)
    return matrix


# "x-y" -> (x, y), "x" -> (x, x+1)
def read_hour_range(text):
    if "-" in text:
        parts = text.split("-")
        return int(parts[0]), int(parts[1])
    return int(text), int(text) + 1


def make_matrix(behavior, number_of_services):
    if behavior["type"] == "random":
        return make_random_matrix(behavior["logins_per_day"], number_of_services)

    if behavior["type"] == "pattern":
        weekdays = behavior.get("weekdays", [1, 1, 1, 1, 1, 1, 1])
        return make_pattern_matrix(behavior["hours"], weekdays)

    raise ValueError("Unknown behavior type: " + behavior["type"])



def matrix_login_times(matrix, start, total_hours):
    login_times = []
    for hour_number in range(total_hours):
        hour_start = start + timedelta(hours=hour_number)
        probability = matrix[hour_start.weekday()][hour_start.hour]
        if random.random() < probability:
            login_times.append(hour_start + timedelta(seconds=random.randint(0, 3599)))
    return login_times


def read_clock_time(text):
    parts = text.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def normal_login_times(peaks, weekdays, start, end):
    login_times = []

    day = datetime(start.year, start.month, start.day) - timedelta(days=1)
    while day < end:
        for peak in peaks:
            probability = peak.get("probability", 1.0) * weekdays[day.weekday()]
            if random.random() >= probability:
                continue

            minutes = random.gauss(read_clock_time(peak["mean"]), peak["std_minutes"])
            login_time = day + timedelta(minutes=minutes)
            if start <= login_time < end:
                login_times.append(login_time)
        day = day + timedelta(days=1)

    login_times.sort()
    return login_times


def random_session_minutes(typical_minutes):
    factor = math.exp(random.gauss(0, 0.5))
    return typical_minutes * factor


def generate_events(config):
    start = datetime.fromisoformat(config["start"])
    total_hours = int(config["duration_days"] * 24)
    end = start + timedelta(hours=total_hours)
    users = config["users"]
    services = config["services"]
    allowed_events = config["events"]

    events = []

    for user in users:
        for service in services:
            behavior = config["behavior"].get(user, {}).get(service)
            if behavior is None:
                behavior = {"type": "random", "logins_per_day": 3}

            if behavior["type"] == "normal":
                weekdays = behavior.get("weekdays", [1, 1, 1, 1, 1, 1, 1])
                login_times = normal_login_times(behavior["peaks"], weekdays, start, end)
            else:
                matrix = make_matrix(behavior, len(services))
                login_times = matrix_login_times(matrix, start, total_hours)

            session_minutes = behavior.get("session_minutes", 30)
            fail_probability = behavior.get("fail_probability", 0.02)

            logged_in_until = start

            for login_time in login_times:
                if login_time < logged_in_until:
                    continue

                if "login_failed" in allowed_events and random.random() < fail_probability:
                    events.append((login_time, user, service, "login_failed"))
                    login_time = login_time + timedelta(seconds=random.randint(5, 60))

                events.append((login_time, user, service, "login"))
                logged_in_until = login_time

                if "logout" in allowed_events:
                    minutes = random_session_minutes(session_minutes)
                    logout_time = login_time + timedelta(minutes=minutes)
                    if logout_time < end:
                        events.append((logout_time, user, service, "logout"))
                    logged_in_until = logout_time

    events.sort()
    return events


def write_csv(events, path):
    with open(path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "user", "service", "event"])
        for time, user, service, event in events:
            writer.writerow([time.isoformat(timespec="seconds"), user, service, event])



def main():
    config_path = "config.json"
    output_path = "dataset.csv"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]

    with open(config_path) as file:
        config = json.load(file)

    random.seed(config.get("seed"))

    events = generate_events(config)
    write_csv(events, output_path)
    print("Done!")


if __name__ == "__main__":
    main()
