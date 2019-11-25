from django.test import TestCase

# Create your tests here.

from pymongo import MongoClient
from django.conf import settings
import urllib.parse
from TourManiaBackend.settings import MANGO_JWT_SETTINGS
from bson.objectid import ObjectId

password = urllib.parse.quote(MANGO_JWT_SETTINGS['db_pass'])
username = urllib.parse.quote(MANGO_JWT_SETTINGS['db_user'])
db_name = MANGO_JWT_SETTINGS['db_name']
db_host_mongo = MANGO_JWT_SETTINGS['db_host']
db_port_mongo = MANGO_JWT_SETTINGS['db_port']
mongo_uri = "mongodb://{username}:{password}@{db_host}:{db_port_mongo}/{db_name}".format(
    username=username, password=password, db_host=db_host_mongo,
    db_port_mongo=db_port_mongo, db_name=db_name)
client = MongoClient(mongo_uri)
database = client[db_name]

#database["user_profile"].find_one({"email": "aaa"})

#print(database["tours"].find_one({"_id": ObjectId("5dda260a109ec6ee5c9a3523")}))

print(database["tours"].find_one({"_id": ObjectId("5dda87bc1b772773eb4ecba8")}, {"tour.title": 0}))
