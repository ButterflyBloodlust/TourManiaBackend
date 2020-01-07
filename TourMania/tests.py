from django.test import TestCase
from pymongo import MongoClient
from django.conf import settings
import urllib.parse
from TourManiaBackend.settings import MANGO_JWT_SETTINGS
from bson.objectid import ObjectId
import base64
import pprint
import time
import datetime
import jwt
import secrets

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
                "distanceField": "dist.calculated",
                "key": "tours_locs.loc"
            }
        },
        {
            "$project": {"_id": 0, "nickname": 1, "phone_num": "$prefs.phone_num"}
        }
    ])

    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


def db_nearby_tour_guides():
    docs = database[user_details_collection].find({"prefs.is_guide": True, "tours_locs.loc": {"$near": [0.0, 0.0]}},
                                                  {"_id": 0, "nickname": 1, "prefs.phone_num": 1})

    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


def db_get_tour_guide_info():
    tour_guide_nickname = "asd"
    docs = database[user_details_collection].aggregate([
        {"$match": {'nickname': tour_guide_nickname}},
        {"$limit": 1},
        {"$project": {"_id": 0, "email": 1, "phone_num": "$prefs.phone_num"}}
    ])
    pp = pprint.PrettyPrinter()
    pp.pprint(docs.next())


def get_favs():
    skip_obj_ids = [ObjectId('5e09624fe30e565874d8751c')]
    docs = database[user_details_collection].distinct('fav_trs', {'usr_id': 'ID_5fa9bda9-6bf0-4a6e-84f2-ed174a47199b'})
    print(docs)
    docs = database[tours_collection].find({'_id': {'$nin': skip_obj_ids, '$in': docs}}, {'usr_id': 0})
    print('favs : {}'.format(list(docs)))


def generate_token():
    token = secrets.token_urlsafe()
    exp = datetime.datetime.now() + datetime.timedelta(hours=8)
    print("token : {}".format(token))
    print("exp : {}".format(exp))
    print(datetime.datetime.now() < exp)


def db_nearby_tours_joined_with_tour_guides_old():
    docs = database[tours_collection].aggregate([
        # $geoNear has to be first stage in aggregation pipeline
        {
            "$geoNear": {
                "near": [0.0, 0.0],
                "distanceField": "dist.calculated",
                "key": "tour.start_loc"
            }
        },
        {
            "$project": {'wpsWPics': 0, 'tags': 0}
        },
        # Join with user_info table
        {
            "$lookup": {
                "from": user_details_collection,  # other table name
                "localField": "usr_id",  # name of base table field
                "foreignField": "usr_id",  # name of other table field
                "as": "tour_guide"  # alias for other table
            }
        },
        # {"$unwind": "$tours"},  # "$unwind" used for getting data in object or for one record only
        {
            "$project": {'usr_id': 0}
        },
    ])

    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


def db_nearby_tours_inner_joined_with_tour_guides():
    docs = database[tours_collection].aggregate([
        # $geoNear has to be first stage in aggregation pipeline
        {
            "$geoNear": {
                "near": [0.0, 0.0],
                "distanceField": "dist.calculated",
                "key": "tour.start_loc"
            }
        },
        {"$project": {'wpsWPics': 0, 'tags': 0, 'dist': 0}},
        # Left join with user_info table
        {
            "$lookup": {
                "from": user_details_collection,  # other table name
                "let": {"uid": "$usr_id"},  # aliases for fields from main table
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$usr_id", "$$uid"]},   # main join condition (i.e. which fields are used for join)
                                    {"$eq": ["$prefs.is_guide", True]}  # "$eq": ["$prefs.is_guide", True]
                                ]
                            }
                        }
                    },
                    {"$project": {'_id': 0, 'prefs.is_guide': 1}}
                ],
                "as": "is_guide"  # alias for other table
            }
        },
        # Match only documents with right side join present (this results in inner join when combined with previous lookup query).
        # Not needed since {"$unwind": "$is_guide"} removes entire docs with 'is_guide' empty.
        #{
        #    "$match": {
        #        "is_guide": {"$ne": []}
        #    }
        #},
        # "$unwind" used for flattening parts of result structure.
        # preserveNullAndEmptyArrays: False effectively makes this also an inner join in this context.
        {"$unwind": {
            "path": "$is_guide",
            "preserveNullAndEmptyArrays": False
        }},
        {"$project": {"usr_id": 0, }},
        # Flatten field
        {"$addFields": {"is_guide": "$is_guide.prefs.is_guide"}},
        #{"$count": "doc_count"}
    ])
    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


def db_nearby_tours_left_joined_with_tour_guides():
    docs = database[tours_collection].aggregate([
        # $geoNear has to be first stage in aggregation pipeline
        {
            "$geoNear": {
                "near": [0.0, 0.0],
                "distanceField": "dist.calculated",
                "key": "tour.start_loc"
            }
        },
        {"$project": {'wpsWPics': 0, 'tags': 0, 'dist': 0}},
        # Left join with user_info table
        {
            "$lookup": {
                "from": user_details_collection,  # other table name
                "let": {"uid": "$usr_id"},  # aliases for fields from main table
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$eq": ["$usr_id", "$$uid"]   # main join condition (i.e. which fields are used for join)
                            }
                        }
                    },
                    {"$project": {'_id': 0, 'prefs.is_guide': 1}}
                ],
                "as": "author.is_guide"  # alias for other table
            }
        },
        # "$unwind" used for flattening parts of result structure
        {"$unwind": {
            "path": "$author.is_guide",
            "preserveNullAndEmptyArrays": True
        }},
        {"$project": {"usr_id": 0, }},
        # Flatten field
        {"$addFields": {"author.is_guide": "$author.is_guide.prefs.is_guide"}},
        #{"$count": "doc_count"}
    ])
    pp = pprint.PrettyPrinter()
    for doc in docs:
        pp.pprint(doc)


def db_migrate():
    database[tour_images_collection].update_many({}, {"$unset": {"username": 1}})


if __name__ == "__main__":
    database = connect_to_db()

    #start = time.clock()
    db_migrate()
    #end = time.clock()
    #print("Operation time: {} s".format(end - start))

