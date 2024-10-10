import requests
# Application_ID = 663242
Access_key = 'hjDpeKogmpwQco0nZyq3J4NuXPaf5nk7wLtoz1vlfII'
# Secret_key = '0Df4w0YYEsXROiN4cn3mGHMi2UDS-8WDSJDwTYU7avI'

headers = {
    'Authorization': f'Client-ID {Access_key}'
}

parameters = {
    'query': 'nature',
    'orientation': 'landscape',
    'count': 12
}
unsplash_url = 'https://api.unsplash.com/photos/random/'

response = requests.get(unsplash_url, headers=headers, params=parameters)
print(response.status_code)
print(response.json())

for i in range(len(response.json())):
    print(response.json()[i]["urls"]["regular"])
