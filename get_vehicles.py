import requests
import json
import urllib3
import pandas as pd
from datetime import datetime

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PARSE_HOST = "https://pay.cpp-system.com"
APP_ID = "CPP-PAY-PROD"
REST_API_KEY = "f7W7tKtJHykYK7bqNnUg"

headers = {
    "X-Parse-Application-Id": APP_ID,
    "X-Parse-REST-API-Key": REST_API_KEY,
}

def normalize_vehicle(v):
    if not v or v == "Sans véhicule":
        return v
    return v.replace(" ", "").upper()

def get_vehicles():
    session = requests.Session()
    session.verify = False 
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    START_OF_DAY = f"{today_str}T00:00:00.000Z"
    END_OF_DAY = f"{today_str}T23:59:59.999Z"
    
    url = f"{PARSE_HOST}/endpoint/classes/CompanyReservation"
    
    # Using a limit to get a batch. In production, pagination might be needed.
    params = {
        "limit": 1000,
        "where": json.dumps({
            "company": {
                "__type": "Pointer",
                "className": "Company",
                "objectId": "yKm1BqyB11"
            },
            "createdAt": {
                "$gte": {
                    "__type": "Date",
                    "iso": START_OF_DAY,
                },
                "$lte": {
                    "__type": "Date",
                    "iso": END_OF_DAY,
                },
            },
        })
    }
    
    response = session.get(
        url,
        headers=headers,
        params=params,
    )
    
    reservations = response.json().get("results", [])
    
    if not reservations:
        print("No reservations found for this company.")
        return

    vehicles = set()
    print(f"Total reservations found: {len(reservations)}")
    for reservation in reservations:
        # The 'guest' field appears to hold the vehicle identifier
        vehicle = normalize_vehicle(reservation.get("guest"))
        if vehicle and vehicle != "Sans véhicule":
            vehicles.add(vehicle)
          
    print(f"Total unique vehicles found: {len(vehicles)}")
    
    # Create DataFrame and export to Excel
    df = pd.DataFrame(sorted(list(vehicles)), columns=["Vehicle"])
    file_name = f"vehicles_{today_str}.xlsx"
    df.to_excel(file_name, index=False)
    print(f"List of vehicles saved to {file_name}")

if __name__ == "__main__":
    get_vehicles()
