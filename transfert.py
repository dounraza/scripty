import requests
import json

# Configuration
PARSE_HOST = "https://pay.cpp-system.com"
APP_ID = "CPP-PAY-PROD"
REST_API_KEY = "f7W7tKtJHykYK7bqNnUg"

headers = {
    "X-Parse-Application-Id": APP_ID,
    "X-Parse-REST-API-Key": REST_API_KEY,
    "Content-Type": "application/json"
}

def transfer_reservations(reservation_object_ids, new_catalog_operation_id):
    """
    Updates the catalogOperation pointer for a list of CompanyReservations.
    """
    session = requests.Session()
    session.verify = False

    update_data = {
        "catalog": {
            "__type": "Pointer",
            "className": "CompanyCatalog",
            "objectId": new_catalog_operation_id,
        }
    }

    for res_id in reservation_object_ids:
        try:
            response = session.put(
                f"{PARSE_HOST}/endpoint/classes/CompanyReservation/{res_id}",
                headers=headers,
                data=json.dumps(update_data),
                timeout=30,
            )

            if response.status_code == 200:
                print(f"Succès: Réservation {res_id} transférée vers le catalogue {new_catalog_operation_id}")
            else:
                print(f"Erreur pour {res_id}: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"Erreur lors de la requête pour {res_id}: {e}")

if __name__ == "__main__":
    # Exemple d'utilisation
    reservation_ids = ["OBJ_ID_1", "OBJ_ID_2", "OBJ_ID_3"]
    destination_catalog_id = "OBJECT_ID_DU_CATALOGUE_DESTINATION"
    transfer_reservations(reservation_ids, destination_catalog_id)
    print("Veuillez modifier le script pour définir la liste reservation_ids et destination_catalog_id.")
