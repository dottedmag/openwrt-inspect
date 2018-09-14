import requests

session = requests.Session()

def get(url):
    response = session.get(url)
    response.raise_for_status()
    return response
