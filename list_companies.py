import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PARSE_HOST = "https://pay.cpp-system.com"
APP_ID = "CPP-PAY-PROD"
REST_API_KEY = "f7W7tKtJHykYK7bqNnUg"

headers = {
    "X-Parse-Application-Id": APP_ID,
    "X-Parse-REST-API-Key": REST_API_KEY,
}

def list_companies():
    session = requests.Session()
    session.verify = False 
    url = f"{PARSE_HOST}/endpoint/classes/Company"
    response = session.get(url, headers=headers)
    if response.status_code == 200:
        companies = response.json().get("results", [])
        for c in companies:
            print(f"Name: {c.get('name')}, objectId: {c.get('objectId')}")
    else:
        print(f"Error: {response.status_code}")

if __name__ == "__main__":
    list_companies()
