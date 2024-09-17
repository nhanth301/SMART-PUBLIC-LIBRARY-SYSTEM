import requests

response = requests.post('https://zep.hcmute.fit/7561/transform', json={'texts': ["Hi, this is my project"]})
print(response.json()['embeddings'])
