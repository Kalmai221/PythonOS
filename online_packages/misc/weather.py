import requests

def get_location():
    try:
        res = requests.get("https://ipinfo.io/json")
        if res.status_code == 200:
            data = res.json()
            city = data.get("city")
            return city
        else:
            return None
    except Exception:
        return None

def get_weather(city):
    if not city:
        print("Could not determine location.")
        return
    url = f"https://wttr.in/{city}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            print(res.text)
        else:
            print("Failed to get weather.")
    except Exception as e:
        print("Error:", e)

def main():
    city = get_location()
    if city:
        print(f"Detected location: {city}")
        get_weather(city)
    else:
        print("Could not detect location automatically.")

if __name__ == "__main__":
    main()

def execute():
    main()