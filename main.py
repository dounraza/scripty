import time
import threading
from datetime import datetime
import requests
import json
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn

# ===========================
# Configuration
# ===========================

# Background sync thread management
def run_sync_periodically():
    while True:
        sync()
        print("Prochaine synchronisation dans 3 minutes...")
        time.sleep(180)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    thread = threading.Thread(target=run_sync_periodically, daemon=True)
    thread.start()
    print("Background sync thread started.")
    yield
    # Shutdown logic (if needed)
    print("Application shutting down.")

app = FastAPI(lifespan=lifespan)

PARSE_HOST = "https://pay.cpp-system.com"
APP_ID = "CPP-PAY-PROD"
REST_API_KEY = "f7W7tKtJHykYK7bqNnUg"

headers = {
    "X-Parse-Application-Id": APP_ID,
    "X-Parse-REST-API-Key": REST_API_KEY,
}

def sync():
    # Update TODAY dynamically for each run
    today_str = datetime.now().strftime("%Y-%m-%d")
    START_OF_DAY = f"{today_str}T00:00:00.000Z"
    END_OF_DAY = f"{today_str}T23:59:59.999Z"

    print(f"[{datetime.now()}] Début de la synchronisation")
    
    where = {
        "catalogOperation": {
            "__type": "Pointer",
            "className": "CatalogOperation",
            "objectId": "FSQ0ijbut5",
        },
        "company": {
            "__type": "Pointer",
            "className": "Company",
            "objectId": "yKm1BqyB11",
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
    }
    session = requests.Session()
    session.verify = False

    try:
        response = session.get(
            f"{PARSE_HOST}/endpoint/classes/CompanyReservation",
            headers=headers,
            params={
                "where": json.dumps(where),
                "include": "company,customer,transaction,product,product.catalog",
            },
            timeout=300,
        )

        reservations = response.json().get("results", [])

        # Load missing transactions
        for reservation in reservations:
            if "transaction" not in reservation and reservation.get("transactionOuid"):
                trx = session.get(
                    f"{PARSE_HOST}/endpoint/classes/Transaction",
                    headers=headers,
                    params={
                        "where": json.dumps({"oUid": reservation["transactionOuid"]}),
                        "limit": 1,
                    },
                )
                results = trx.json().get("results", [])
                if results:
                    reservation["transaction"] = results
        
        # Define status mapping
        STATUS_MAP = {
            "zrf19PUc4G": "Payé",
            "H3cZgmdylx": "Annulé",
            "UCmT43PVNd": "En attente",
            "NHkzAT4VLR": "Remboursé",
            "z426sJJIuu": "Echoué",
            "FBmNfHRd2P": "Partiel",
            "GS9RUAxrJJ": "P.A",
            "Y7jJjJW8D3": "En attente de paiement"
        }

        # ===========================
        # Summary
        # ===========================

        summary = {}
        processed = set()

        for reservation in reservations:
            object_id = reservation.get("objectId")
            if not object_id or object_id in processed:
                continue
            processed.add(object_id)
            product = reservation.get("product")
            if not product:
                continue

            catalog = (
                product.get("catalog", {}).get("name")
                or product.get("catalog", {}).get("objectId")
                or "Unknown"
            )
            product_name = product.get("name", "Unknown")
            vehicle = reservation.get("guest", "Sans véhicule")
            quantity = reservation.get("quantity", 1)
            transaction = reservation.get("transaction", [])

            reservation_ca = 0
            # Resolve transaction status
            status_id = None
            if isinstance(transaction, list) and len(transaction) > 0:
                status_id = transaction[0].get("status", {}).get("objectId")
            elif isinstance(transaction, dict):
                status_id = transaction.get("status", {}).get("objectId")
            
            readable_status = STATUS_MAP.get(status_id, "Inconnu")

            if isinstance(transaction, list):
                for t in transaction:
                    reservation_ca += t.get("amount_net", 0)
            elif isinstance(transaction, dict):
                if transaction.get("amount_net") is not None:
                    reservation_ca = transaction.get("amount_net", 0)
                elif transaction.get("Items"):
                    for item in transaction["Items"]:
                        reservation_ca += (item.get("price", 0) * item.get("quantity", 1))
            else:
                reservation_ca = quantity * product.get("price", 0)

            summary.setdefault(catalog, {})
            summary[catalog].setdefault(product_name, {"total_quantity": 0, "vehicles": {}})
            summary[catalog][product_name]["vehicles"].setdefault(vehicle, {"total_quantity": 0, "total_ca": 0, "reservations": []})
            summary[catalog][product_name]["vehicles"][vehicle]["reservations"].append({
                "objectId": object_id,
                "createdAt": reservation.get("createdAt"),
                "status": readable_status
            })
            summary[catalog][product_name]["total_quantity"] += quantity
            summary[catalog][product_name]["vehicles"][vehicle]["total_quantity"] += quantity
            summary[catalog][product_name]["vehicles"][vehicle]["total_ca"] += reservation_ca

        # ===========================
        # Departures
        # ===========================

        departures = {}
        processed = set()
        
        # Allowed statuses for departures
        ALLOWED_STATUSES = {"Payé", "P.A", "Partiel"}

        for reservation in reservations:
            object_id = reservation.get("objectId")
            if not object_id or object_id in processed:
                continue
            
            # Get status for filtering
            transaction = reservation.get("transaction", [])
            status_id = None
            if isinstance(transaction, list) and len(transaction) > 0:
                status_id = transaction[0].get("status", {}).get("objectId")
            elif isinstance(transaction, dict):
                status_id = transaction.get("status", {}).get("objectId")
            
            readable_status = STATUS_MAP.get(status_id, "Inconnu")
            
            if readable_status not in ALLOWED_STATUSES:
                continue
                
            processed.add(object_id)
            vehicle = reservation.get("guest", "Sans véhicule")
            line = reservation.get("product", {}).get("name", "N/A")
            departures.setdefault(vehicle, {})
            if line not in departures[vehicle]:
                created = reservation.get("createdAt")
                try:
                    depart = datetime.fromisoformat(created.replace("Z", "+00:00")).strftime("%H:%M")
                except Exception:
                    depart = "--:--"
                departures[vehicle][line] = {
                    "catalog": reservation.get("product", {}).get("catalog", {}).get("name", "Unknown"),
                    "ligne": line,
                    "depart": depart,
                    "passagers": 0,
                    "status": readable_status,
                }
            departures[vehicle][line]["passagers"] += reservation.get("quantity", 0)

        # ===========================
        # Totals
        # ===========================

        unique_vehicles = set()
        total_passengers = 0
        for catalog in summary.values():
            for product in catalog.values():
                total_passengers += product["total_quantity"]
                for vehicle in product["vehicles"]:
                    if vehicle != "Sans véhicule":
                        unique_vehicles.add(vehicle)

        catalog_distribution = []
        for catalog_name, products in summary.items():
            vehicles = set()
            for product in products.values():
                for vehicle in product["vehicles"]:
                    if vehicle != "Sans véhicule":
                        vehicles.add(vehicle)
            catalog_distribution.append({"name": catalog_name, "count": len(vehicles)})

        result = {
            "summary": summary,
            "total_passengers_today": total_passengers,
            "total_vehicles_today": len(unique_vehicles),
            "catalog_distribution": catalog_distribution,
            "departures": departures,
        }

        print(json.dumps(result, indent=4, ensure_ascii=False))
        print(f"[{datetime.now()}] Synchronisation terminée")

    except Exception as e:
        print(f"[{datetime.now()}] Erreur lors de la synchronisation :", e)

@app.get("/")
async def root():
    return {"message": "Service de synchronisation actif"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5005)