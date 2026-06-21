from pymongo import MongoClient

uri = "mongodb+srv://shivamdadhich:shivamcc@cc01.hi5oipj.mongodb.net/?retryWrites=true&w=majority&appName=cc01"

client = MongoClient(uri)

db = client["careconnect"]

print(client.list_database_names())

print("Connected Successfully!")