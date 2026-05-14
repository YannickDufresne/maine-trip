#!/usr/bin/env python3
"""
Update weather forecast in index.html from NWS API.
Runs every 4 hours via GitHub Actions until May 18 2026 evening.
Uses only Python standard library (no pip install needed).
"""
import urllib.request
import urllib.error
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Belfast, Maine coordinates
LAT, LON = 44.4258, -69.0269

# Target trip days
TARGET_DATES = ["2026-05-16", "2026-05-17", "2026-05-18"]
DATE_LABELS = {"2026-05-16": "Sam 16", "2026-05-17": "Dim 17", "2026-05-18": "Lun 18"}

# Stop updating after this date (Monday May 18 evening Quebec time = early May 19 UTC)
STOP_AFTER = datetime(2026, 5, 19, 4, 0, tzinfo=timezone.utc)

INDEX_PATH = Path(__file__).resolve().parent.parent / "index.html"

def fetch_json(url, max_retries=3):
    """Fetch URL with retries. NWS sometimes requires retry."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MaineTripBook/1.0 (yannick.dufresne@gmail.com)",
            "Accept": "application/geo+json",
        },
    )
    last_error = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            last_error = e
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # exponential backoff
    raise last_error


def f_to_c(f):
    """Fahrenheit to Celsius, rounded."""
    return round((f - 32) * 5 / 9)


def get_nws_forecast():
    """Get NWS forecast periods for Belfast ME."""
    # Step 1: Get the gridpoint for our coordinates
    points_url = f"https://api.weather.gov/points/{LAT},{LON}"
    points_data = fetch_json(points_url)
    forecast_url = points_data["properties"]["forecast"]

    # Step 2: Get the forecast
    forecast_data = fetch_json(forecast_url)
    return forecast_data["properties"]["periods"]


def parse_periods_for_target_days(periods):
    """Group NWS periods by target date. Returns {date: {day: period, night: period}}."""
    result = {d: {"day": None, "night": None} for d in TARGET_DATES}

    for period in periods:
        # startTime is ISO format like "2026-05-16T08:00:00-04:00"
        start_str = period["startTime"][:10]
        if start_str not in TARGET_DATES:
            continue

        is_daytime = period.get("isDaytime", True)
        if is_daytime and result[start_str]["day"] is None:
            result[start_str]["day"] = period
        elif not is_daytime and result[start_str]["night"] is None:
            result[start_str]["night"] = period

    return result


def emoji_for_condition(short_forecast):
    """Heuristic to pick emoji based on NWS short forecast text."""
    s = short_forecast.lower()
    if "thunderstorm" in s or "storm" in s:
        return "⛈"
    if "rain" in s or "shower" in s:
        return "🌧"
    if "snow" in s:
        return "❄"
    if "cloudy" in s and ("partly" in s or "mostly sunny" in s):
        return "⛅"
    if "cloudy" in s:
        return "☁"
    if "fog" in s:
        return "🌫"
    if "sun" in s or "clear" in s:
        return "☀"
    return "·"


def translate_to_french(short_forecast):
    """Quick translation of common NWS phrases to French."""
    s = short_forecast.lower()
    translations = [
        ("chance of thunderstorms", "orages possibles"),
        ("chance of showers", "averses possibles"),
        ("scattered showers", "averses éparses"),
        ("scattered thunderstorms", "orages épars"),
        ("isolated thunderstorms", "orages isolés"),
        ("light rain", "pluie légère"),
        ("heavy rain", "pluie forte"),
        ("rain showers", "averses"),
        ("rain", "pluie"),
        ("partly sunny", "partiellement ensoleillé"),
        ("partly cloudy", "partiellement nuageux"),
        ("mostly sunny", "majoritairement ensoleillé"),
        ("mostly cloudy", "majoritairement nuageux"),
        ("mostly clear", "majoritairement dégagé"),
        ("sunny", "ensoleillé"),
        ("clear", "ciel dégagé"),
        ("cloudy", "nuageux"),
        ("foggy", "brouillard"),
        ("fog", "brouillard"),
        ("snow", "neige"),
        ("windy", "venteux"),
        ("breezy", "brise"),
        ("then", "puis"),
        ("and", "et"),
    ]
    out = s
    for en, fr in translations:
        out = out.replace(en, fr)
    return out.capitalize()


def estimate_precip_percent(short_forecast, detailed_forecast):
    """Try to find precip % in NWS detailed forecast text."""
    combined = (detailed_forecast or "") + " " + (short_forecast or "")
    match = re.search(r"chance of precipitation is (\d+)%", combined.lower())
    if match:
        return f"{match.group(1)}%"
    match = re.search(r"(\d+) percent chance", combined.lower())
    if match:
        return f"{match.group(1)}%"
    # Heuristic from short forecast
    s = (short_forecast or "").lower()
    if "thunderstorm" in s or "rain" in s or "shower" in s:
        return "élevé"
    if "chance" in s:
        return "modéré"
    return "—"


def compute_implication(periods_by_date):
    """Build a dynamic 'plage vs indoor' recommendation from the forecast."""
    day_names_fr = {"2026-05-16": "samedi", "2026-05-17": "dimanche", "2026-05-18": "lundi"}
    good, bad = [], []
    for d in TARGET_DATES:
        period = periods_by_date[d]["day"]
        if not period:
            continue
        sf = period.get("shortForecast", "").lower()
        precip = estimate_precip_percent(sf, period.get("detailedForecast", ""))
        try:
            precip_num = int(precip.rstrip("%")) if "%" in precip else 0
        except ValueError:
            precip_num = 0
        wet = any(w in sf for w in ["rain", "shower", "storm", "thunder", "drizzle"])
        sunny = any(w in sf for w in ["sunny", "clear"])
        label = day_names_fr.get(d, d)
        if wet or precip_num >= 50:
            bad.append(label)
        elif sunny and precip_num < 30:
            good.append(label)
    if good and bad:
        return f"plage/playground prioritaire {' et '.join(good)}, focus indoor {' et '.join(bad)}."
    if good and not bad:
        return f"plage/playground OK les {len(good)} jours."
    if bad and not good:
        return f"plan B indoor (restos, musees, AllPlay) {' et '.join(bad)} — verifier le matin."
    return "verifier la meteo le matin avant de fixer plage vs indoor."


def build_weather_table(periods_by_date):
    """Build HTML table for our 3 trip days."""
    rows = []
    rows.append('<table>')
    rows.append('<tr><th>Jour</th><th>Conditions</th><th>Jour (°C)</th><th>Nuit (°C)</th><th>Précip</th></tr>')

    color_classes = {
        "2026-05-16": "background: #ffe6e6;",  # Sat — likely rainy
        "2026-05-17": "background: #fff7e6;",
        "2026-05-18": "background: #e8f5e9;",
    }

    for date in TARGET_DATES:
        day_period = periods_by_date[date]["day"]
        night_period = periods_by_date[date]["night"]
        label = DATE_LABELS[date]

        if day_period is None:
            # Fallback if NWS doesn't have data yet
            rows.append(f'<tr><td><strong>{label}</strong></td><td colspan="4"><em>Forecast pas encore disponible</em></td></tr>')
            continue

        day_temp_f = day_period["temperature"]
        day_temp_c = f_to_c(day_temp_f)
        night_temp_c = f_to_c(night_period["temperature"]) if night_period else "—"

        short_forecast = day_period.get("shortForecast", "")
        detailed = day_period.get("detailedForecast", "")
        emoji = emoji_for_condition(short_forecast)
        conditions_fr = translate_to_french(short_forecast)
        precip = estimate_precip_percent(short_forecast, detailed)

        # Update color class based on precip % or conditions
        s_lower = short_forecast.lower()
        if "%" in precip:
            try:
                p = int(precip.rstrip("%"))
                if p >= 60:
                    color = "background: #ffe6e6;"  # red — wet
                elif p >= 30:
                    color = "background: #fff7e6;"  # amber
                else:
                    color = "background: #e8f5e9;"  # green
            except ValueError:
                color = color_classes[date]
        elif "sun" in s_lower or "clear" in s_lower:
            color = "background: #e8f5e9;"  # sunny = green
        elif "rain" in s_lower or "thunder" in s_lower or "shower" in s_lower:
            color = "background: #ffe6e6;"  # rainy = red
        elif "cloudy" in s_lower:
            color = "background: #fff7e6;"  # cloudy = amber
        else:
            color = color_classes[date]

        rows.append(
            f'<tr style="{color}">'
            f'<td><strong>{label}</strong></td>'
            f'<td>{emoji} {conditions_fr}</td>'
            f'<td><strong>{day_temp_c}°C</strong></td>'
            f'<td>{night_temp_c}°C</td>'
            f'<td>{precip}</td>'
            f'</tr>'
        )

    rows.append('</table>')
    return "\n".join(rows)


def update_html(table_html, periods_by_date):
    """Replace weather table and last-update timestamp in index.html."""
    html = INDEX_PATH.read_text(encoding="utf-8")

    # Replace the weather table
    new_html = re.sub(
        r"<!-- WEATHER_TABLE_START -->.*?<!-- WEATHER_TABLE_END -->",
        f"<!-- WEATHER_TABLE_START -->\n{table_html}\n<!-- WEATHER_TABLE_END -->",
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Update the last-update timestamp
    # Use US Eastern Time which is what people care about for Maine forecasts
    eastern = timezone(timedelta(hours=-4))  # EDT
    now = datetime.now(eastern)
    # French day/month names (no locale dependency on CI runner)
    days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    months_fr = ["jan", "fév", "mars", "avr", "mai", "juin",
                 "juil", "août", "sept", "oct", "nov", "déc"]
    update_label = (
        f"Météo mise à jour {days_fr[now.weekday()]} "
        f"{now.day} {months_fr[now.month - 1]} · "
        f"{now.strftime('%Hh%M')} EDT"
    )
    # Replace ALL occurrences (topbar + weather banner)
    new_html = re.sub(
        r"<!-- LAST_UPDATE_START -->.*?<!-- LAST_UPDATE_END -->",
        f"<!-- LAST_UPDATE_START -->{update_label}<!-- LAST_UPDATE_END -->",
        new_html,
        flags=re.DOTALL,
    )

    # Implication concrete (dynamic)
    impl = compute_implication(periods_by_date)
    new_html = re.sub(
        r"<!-- IMPLICATION_START -->.*?<!-- IMPLICATION_END -->",
        f"<!-- IMPLICATION_START -->{impl}<!-- IMPLICATION_END -->",
        new_html,
        flags=re.DOTALL,
    )

    INDEX_PATH.write_text(new_html, encoding="utf-8")
    print(f"Updated index.html with NWS forecast at {update_label}")


def main():
    # Check if we should stop updating
    now_utc = datetime.now(timezone.utc)
    if now_utc > STOP_AFTER:
        print(f"Past stop date ({STOP_AFTER}), skipping update.")
        return

    print(f"Fetching NWS forecast for Belfast, ME ({LAT}, {LON})...")
    try:
        periods = get_nws_forecast()
        print(f"Got {len(periods)} forecast periods.")
        periods_by_date = parse_periods_for_target_days(periods)
        for date in TARGET_DATES:
            day = periods_by_date[date]["day"]
            if day:
                print(f"  {date}: {day['name']} = {day['temperature']}°{day.get('temperatureUnit', 'F')} · {day['shortForecast']}")
            else:
                print(f"  {date}: not yet in NWS 7-day forecast window")
        table_html = build_weather_table(periods_by_date)
        update_html(table_html, periods_by_date)
    except Exception as e:
        print(f"Error fetching weather: {e}")
        # Don't fail the workflow on transient API issues
        # The previous table stays in place


if __name__ == "__main__":
    main()
