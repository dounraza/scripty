import time
import threading
from datetime import datetime
import requests
import json
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import mysql.connector

# ===========================
# Configuration
# ===========================

# Database Configuration
DB_CONFIG = {
    'host': 'http://192.168.1.129/',
    'user': 'root',
    'password': '',
    'database': 'cpp_trans_prod'
}

PARSE_HOST = "https://pay.cpp-system.com"
APP_ID = "CPP-PAY-PROD"
REST_API_KEY = "f7W7tKtJHykYK7bqNnUg"

headers = {
    "X-Parse-Application-Id": APP_ID,
    "X-Parse-REST-API-Key": REST_API_KEY,
}

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
    print("Le thread de synchronisation en arrière-plan a démarré.")
    yield
    # Shutdown logic (if needed)
    print("Arrêt de l'application.")

app = FastAPI(lifespan=lifespan)

def normalize_vehicle(v):
    if not v or v == "Sans véhicule":
        return v
    return v.replace(" ", "").upper()

def check_manifold_exists(session, vehicle):
    manifolds_where = {
        "vehiculNumber": normalize_vehicle(vehicle),
    }
   
    try:
        response = session.get(
            f"{PARSE_HOST}/endpoint/classes/CompanyManifold",
            headers=headers,
            params={"where": json.dumps(manifolds_where), "order": "-createdAt", "limit": 1},
            timeout=30,
        )
        
        manifolds = response.json().get("results", [])
        if manifolds:
            return manifolds[0].get("generatedAt", {}).get("iso")
        return None
    except Exception as e:
        print(f"Erreur lors de la vérification du manifold pour {vehicle} :", e)
        return None

def sync():
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
            "$gte": {"__type": "Date", "iso": START_OF_DAY},
            "$lte": {"__type": "Date", "iso": END_OF_DAY},
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
            vehicle = normalize_vehicle(reservation.get("guest", "Sans véhicule"))
            quantity = reservation.get("default_quantity", 0)
            transaction = reservation.get("transaction", [])

            status_id = None
            if isinstance(transaction, list) and len(transaction) > 0:
                status_id = transaction[0].get("status", {}).get("objectId")
            elif isinstance(transaction, dict):
                status_id = transaction.get("status", {}).get("objectId")
            
            readable_status = STATUS_MAP.get(status_id, "Inconnu")

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

        departures = {}
        processed = set()
        
        # Allowed statuses for departures
        ALLOWED_STATUSES = {"Payé", "P.A", "Partiel"}
        
        # Open connection/cursor once
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Charger les IDs existants pour éviter les doublons
        cursor.execute("SELECT objectIdCompanyReservation FROM dashboard_stats WHERE stat_date = %s", (today_str,))
        existing_res_rows = cursor.fetchall()
        existing_res_ids = set()
        for row in existing_res_rows:
            if row[0]:
                existing_res_ids.update(row[0].split(','))

        for reservation in reservations:
            object_id = reservation.get("objectId")
            if not object_id or object_id in processed or object_id in existing_res_ids:
                continue
            
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
            vehicle = normalize_vehicle(reservation.get("guest", "Sans véhicule"))
            line = reservation.get("product", {}).get("name", "N/A")
            
            # Extract IDs
            reservation_id = object_id
            transaction_data = reservation.get("transaction", [])
            transaction_id = None
            if isinstance(transaction_data, list) and len(transaction_data) > 0:
                transaction_id = transaction_data[0].get("objectId")
            elif isinstance(transaction_data, dict):
                transaction_id = transaction_data.get("objectId")

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
                    "reservation_ids": [],
                    "transaction_ids": []
                }
            departures[vehicle][line]["passagers"] += reservation.get("default_quantity", 0)
            departures[vehicle][line]["reservation_ids"].append(reservation_id)
            if transaction_id:
                departures[vehicle][line]["transaction_ids"].append(transaction_id)

        # Process updates and insertions for departures
        for vehicle, lines in departures.items():
            for line, data in lines.items():
                generated_at_iso = check_manifold_exists(session, vehicle)
                status_manifold = 'oui' if generated_at_iso else 'non'
                
                # Update 'depart' with generatedAt if available, else keep existing or default
                if generated_at_iso:
                    try:
                        data['depart'] = datetime.fromisoformat(generated_at_iso.replace("Z", "+00:00")).strftime("%H:%M")
                    except Exception:
                        pass
                
                res_ids = ",".join(data["reservation_ids"])
                trx_ids = ",".join(data["transaction_ids"])

                cursor.execute(
                    "SELECT total_quantity, statusManifold, objectIdCompanyReservation, objectIdTransaction FROM dashboard_stats WHERE stat_date = %s AND vehicle = %s AND ligne = %s",
                    (today_str, vehicle, line)
                )
                existing_record = cursor.fetchone()

                if existing_record:
                    (existing_quantity, existing_status_manifold, existing_res_ids, existing_trx_ids) = existing_record
                    
                    # Vérifier si les données ont changé pour ce véhicule et cette ligne
                    if (existing_quantity != data['passagers'] or 
                        existing_status_manifold != status_manifold or 
                        existing_res_ids != res_ids or 
                        existing_trx_ids != trx_ids):
                        
                        cursor.execute(
                            """UPDATE dashboard_stats 
                               SET total_quantity = %s, statusManifold = %s, status = %s, 
                                   objectIdCompanyReservation = %s, objectIdTransaction = %s, depart = %s 
                               WHERE stat_date = %s AND vehicle = %s AND ligne = %s""",
                            (data['passagers'], status_manifold, status_manifold, res_ids, trx_ids, f"{data['depart']}:00", today_str, vehicle, line)
                        )
                else:
                    # Insertion de nouveaux enregistrements
                    cursor.execute(
                        """INSERT INTO dashboard_stats 
                           (stat_date, catalog, ligne, vehicle, total_quantity, total_ca, depart, status, statusManifold, objectIdCompanyReservation, objectIdTransaction)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (today_str, data['catalog'], line, vehicle, data['passagers'], 0, f"{data['depart']}:00", data['status'], status_manifold, res_ids, trx_ids)
                    )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[{datetime.now()}] Statistiques insérées/mises à jour dans MySQL")


        print(f"[{datetime.now()}] Synchronisation terminée")
    except Exception as e:
        print(f"[{datetime.now()}] Erreur lors de la synchronisation :", e)

@app.get("/")
async def root():
    return {"message": "Service de synchronisation actif"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5005)