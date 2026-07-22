import requests
import json
import urllib3
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

def get_today_reservations():
    today_str = datetime.now().strftime("%Y-%m-%d")
    START_OF_DAY = f"{today_str}T00:00:00.000Z"
    END_OF_DAY = f"{today_str}T23:59:59.999Z"

    where = {
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
    }

    session = requests.Session()
    session.verify = False 
    
    url = f"{PARSE_HOST}/endpoint/classes/CompanyReservation"
    
    params = {
        "where": json.dumps(where),
    }
    
    response = session.get(
        url,
        headers=headers,
        params=params,
    )
    
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code} - {response.text}")
        return
        
    reservations = response.json().get("results", [])
    
    # Regroupement par véhicule et calcul de la quantité totale
    vehicules_map = {}
    for res in reservations:
        vehicle = res.get('guest', 'Sans véhicule')
        quantity = res.get('default_quantity', 0) # Assumer 0 si 'quantity' est manquant
        
        if vehicle not in vehicules_map:
            vehicules_map[vehicle] = 0
        vehicules_map[vehicle] += quantity
            
    print(f"Nombre de réservations pour aujourd'hui ({today_str}): {len(reservations)}")
    print(f"Nombre de véhicules uniques: {len(vehicules_map)}\n")
    
    print("Détail par véhicule (Quantité totale):")
    for vehicle, total_quantity in sorted(vehicules_map.items()):
        print(f"- {vehicle}: {total_quantity} unité(s)")
# main  of  get vehicules 
if __name__ == "__main__":
    get_today_reservations()
