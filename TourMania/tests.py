from django.test import TestCase
from pymongo import MongoClient
from django.conf import settings
import urllib.parse
from TourManiaBackend.settings import MANGO_JWT_SETTINGS
from bson.objectid import ObjectId
import base64
import pprint

tours_collection = "tours"
tour_images_collection = "tour_images"
user_details_collection = "user_details"
test_collection = "test_collection"


def connect_to_db():
    password = urllib.parse.quote(MANGO_JWT_SETTINGS['db_pass'])
    username = urllib.parse.quote(MANGO_JWT_SETTINGS['db_user'])
    db_name = MANGO_JWT_SETTINGS['db_name']
    db_host_mongo = MANGO_JWT_SETTINGS['db_host']
    db_port_mongo = MANGO_JWT_SETTINGS['db_port']
    mongo_uri = "mongodb://{username}:{password}@{db_host}:{db_port_mongo}/{db_name}".format(
        username=username, password=password, db_host=db_host_mongo,
        db_port_mongo=db_port_mongo, db_name=db_name)
    client = MongoClient(mongo_uri)
    db = client[db_name]
    return db


def db_query_exclude_var():
    print(database[tours_collection].find_one({"_id": ObjectId("5dda87bc1b772773eb4ecba8")}, {"tour.title": 0}))


def db_get_to_response():
    username = 'asd'
    docs = database[tours_collection].find({'username': username})
    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = 23
        print(doc)
    print(docs)


def db_binary_img_to_base64():
    docs = database[tour_images_collection].find({'trSrvrId': {'$in': ['5ddc007bf5e8a300230a36f0']}}, {'_id': 0})
    #print(list(docs))
    resp_list = []
    for doc in docs:
        imgs = doc["imgs"]
        for (k, v) in imgs.items():
            print(type(v["b"]))
            v["b"] = base64.b64encode(v["b"])
            print(v["b"])
            print(type(v["b"]))
            #for (prop_k, prop_v) in v.items():
            #    print(prop_k)


def db_text_search(phrase):
    docs = database[tours_collection].find(
        {'$text': {'$search': phrase}}, {'score': {'$meta': "textScore"}, 'wpsWPics': 0, 'tags': 0}).sort(
        [('score', {'$meta': "textScore"})])
    resp_list = []
    for doc in docs:
        doc['_id'] = str(doc['_id'])
        resp_list.append(doc)
    print(resp_list)


def db_join_user_details_with_tours():
    docs = database[user_details_collection].aggregate([
        {
            "$match": {
                "$and": [{"prefs.is_guide": True}]
            }
        },

        # Join with user_info table
        {
            "$lookup": {
                "from": tours_collection,  # other table name
                "localField": "usr_id",  # name of users table field
                "foreignField": "usr_id",  # name of other table field
                "as": "tours"  # alias for other table
            }
        },
        # {"$unwind": "$tours"},  # "$unwind" used for getting data in object or for one record only
    ])

    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


def db_nearby_tour_guides_using_aggregation():
    docs = database[user_details_collection].aggregate([
        # $geoNear has to be first stage in aggregation pipeline
        {
            "$geoNear": {
                "query": {"prefs.is_guide": True},
                "near": [0.0, 0.0],
                "distanceField": "dist.calculated"
            }
        }
    ])

    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


def db_nearby_tour_guides():
    docs = database[user_details_collection].find({"prefs.is_guide": True, "tours_locs.loc": {"$near": [0.0, 0.0]}},
                                                  {"_id": 0, "name": 1})

    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


if __name__ == "__main__":
    database = connect_to_db()
    db_nearby_tour_guides()

