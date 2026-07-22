import requests
import json
from datetime import datetime

# Configuration
PARSE_HOST = "https://pay.cpp-system.com"
APP_ID = "CPP-PAY-PROD"
REST_API_KEY = "f7W7tKtJHykYK7bqNnUg"

headers = {
    "X-Parse-Application-Id": APP_ID,
    "X-Parse-REST-API-Key": REST_API_KEY,
    "Content-Type": "application/json"
}

def update_reservations():
    today_str = datetime.now().strftime("%Y-%m-%d")
    START_OF_DAY = f"{today_str}T00:00:00.000Z"
    END_OF_DAY = f"{today_str}T23:59:59.999Z"

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
        "quantity": 0,
        "status": {
            "__type": "Pointer",
            "className": "Status",
            "objectId": "H3cZgmdylx",
        }
    }

    session = requests.Session()
    session.verify = False

    try:
        # Fetch reservations
        response = session.get(
            f"{PARSE_HOST}/endpoint/classes/CompanyReservation",
            headers=headers,
            params={
                "where": json.dumps(where),
                "include": "product",
            },
            timeout=300,
        )

        reservations = response.json().get("results", [])
        
        print(f"--- {len(reservations)} reservations trouvées pour mise à jour ---")
        
        for res in reservations:
            object_id = res.get("objectId")
            transaction_ouid = res.get("transactionOuid")
            product = res.get("product", {})
            default_quantity = product.get("default_quantity", 1)
            
            if not transaction_ouid:
                print(f"Ignoré: Reservation {object_id} n'a pas de transactionOuid")
                continue

            # 1. Update CompanyReservation
            update_data_res = {
                "status": {
                    "__type": "Pointer",
                    "className": "Status",
                    "objectId": "i4HoHEpySk",
                },
                "quantity": default_quantity
            }
            
            update_res_response = session.put(
                f"{PARSE_HOST}/endpoint/classes/CompanyReservation/{object_id}",
                headers=headers,
                data=json.dumps(update_data_res),
                timeout=300,
            )
            
            if update_res_response.status_code != 200:
                print(f"Erreur CompanyReservation {object_id}: {update_res_response.text}")
                continue

            # 2. Get Transaction
            trx_response = session.get(
                f"{PARSE_HOST}/endpoint/classes/Transaction",
                headers=headers,
                params={"where": json.dumps({"oUid": transaction_ouid}), "limit": 1},
                timeout=300,
            )
            
            trx_results = trx_response.json().get("results", [])
            if not trx_results:
                print(f"Erreur: Transaction {transaction_ouid} non trouvée")
                continue
            
            trx_object_id = trx_results[0].get("objectId")
            
            # 3. Update Transaction Status
            update_data_trx = {
                "status": {
                    "__type": "Pointer",
                    "className": "Status",
                    "objectId": "zrf19PUc4G",
                }
            }
            
            update_trx_response = session.put(
                f"{PARSE_HOST}/endpoint/classes/Transaction/{trx_object_id}",
                headers=headers,
                data=json.dumps(update_data_trx),
                timeout=300,
            )
            
            if update_trx_response.status_code == 200:
                print(f"Succès: Reservation {object_id} et Transaction {trx_object_id} mises à jour")
            else:
                print(f"Erreur Transaction {trx_object_id}: {update_trx_response.text}")

    except Exception as e:
        print(f"Erreur lors du traitement : {e}")

if __name__ == "__main__":
    update_reservations()
