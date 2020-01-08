import traceback

from django.shortcuts import render
from rest_framework.decorators import permission_classes, api_view
from TourMania.utils import create_unique_object_id, pwd_context
from TourMania.mongo_db import database, auth_collection, fields, jwt_life, jwt_secret, secondary_username_field
import jwt
import datetime
from mongo_auth import messages
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from bson.objectid import ObjectId
from bson.binary import Binary, BINARY_SUBTYPE
import base64
import secrets
from TourMania.permissions import AuthenticationOptional, AuthenticatedOnly
from TourMania.db_collections import *


@api_view(["GET"])
@permission_classes([AuthenticatedOnly])
def get_test(request):
    try:
        print(request.user)
        return Response(status=status.HTTP_200_OK,
                        data={"data": {"msg": "User Authenticated"}})
    except:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def get_hello(request):
    content = {'message': 'Hello, World!'}
    return Response(content)


@api_view(["GET"])
def get_hello_db(request):
    content = {'message': 'Hello, World!'}
    docs = database['users'].find({})
    print(list(docs))
    return Response(content)  # json.dumps(doc, sort_keys=True, indent=4, default=json_util.default)


'''
    Modified version of mango-jwt login api endpoint. Mango-jwt is distributed under MIT license.
'''
@api_view(["POST"])
def login(request):
    try:
        data = request.data if request.data is not None else {}
        username = data['username']
        password = data['password']
        user = database[user_details_collection].find_one({"email": username}, {"_id": 0})
        if user is None:
            user = database[user_details_collection].find_one({secondary_username_field: username}, {"_id": 0})
        if user is not None:
            user_pswd_doc = database[auth_collection].find_one({"id": user["usr_id"]}, {"_id": 0})
            if pwd_context.verify(password, user_pswd_doc["password"]):
                token = jwt.encode({'id': user['usr_id'],
                                    'exp': datetime.datetime.now() + datetime.timedelta(
                                        days=jwt_life)},
                                   jwt_secret, algorithm='HS256').decode('utf-8')
                user_prefs = user['prefs'] if "prefs" in user else {}
                if "subTo" in user:
                    user_subTo = user['subTo']
                    user_subTo['tour_id'] = str(user_subTo['tour_id'])
                else:
                    user_subTo = {}
                return Response(status=status.HTTP_200_OK,
                                data={"data": {"token": token, "prefs": user_prefs, "subTo": user_subTo}})
            else:
                return Response(status=status.HTTP_403_FORBIDDEN,
                                data={"error_msg": messages.incorrect_password})
        else:
            return Response(status=status.HTTP_403_FORBIDDEN,
                            data={"data": {"error_msg": messages.user_not_found}})
    except ValidationError as v_error:
        return Response(status=status.HTTP_400_BAD_REQUEST,
                        data={'success': False, 'message': str(v_error)})
    except Exception as e:
        traceback.print_exc()
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        data={"data": {"error_msg": str(e)}})


'''
    Modified version of mango-jwt signup api endpoint. Mango-jwt is distributed under MIT license.
'''
@api_view(["POST"])
def signup(request):
    try:
        data = request.data if request.data is not None else {}
        if "password" not in data:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={"error_msg": "password does not exist."})
        signup_user_id = create_unique_object_id()
        signup_pswd_data = {"id": signup_user_id}
        signup_details_data = {"usr_id": signup_user_id}
        for field in set(fields + ("email",)):
            if field in data:
                signup_details_data[field] = data[field]
            else:
                return Response(status=status.HTTP_400_BAD_REQUEST,
                                data={"error_msg": field.title() + " does not exist."})
        signup_pswd_data["password"] = pwd_context.hash(data["password"])

        if database[user_details_collection].find_one({"email": signup_details_data['email']}) is None:
            if secondary_username_field:
                if database[user_details_collection].find_one({secondary_username_field: signup_details_data[secondary_username_field]}) is None:
                    database[auth_collection].insert_one(signup_pswd_data)
                    database[user_details_collection].insert_one(signup_details_data)
                    res = {k: v for k, v in signup_details_data.items() if k not in ["_id", "password"]}
                    return Response(status=status.HTTP_200_OK,
                                    data={"data": res})
                else:
                    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED,
                                    data={"data": {"error_msg": messages.user_exists_field(secondary_username_field)}})
            else:
                database[auth_collection].insert_one(signup_pswd_data)
                database[user_details_collection].insert_one(signup_details_data)
                res = {k: v for k, v in signup_details_data.items() if k not in ["_id", "password"]}
                return Response(status=status.HTTP_200_OK,
                                data={"data": res})
        else:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED,
                            data={"data": {"error_msg": messages.user_exists}})
    except ValidationError as v_error:
        return Response(status=status.HTTP_400_BAD_REQUEST,
                        data={'success': False, 'message': str(v_error)})
    except Exception as e:
        traceback.print_exc()
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        data={"data": {"error_msg": str(e)}})


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def upsert_tour(request):
    tour_id = request.data["tour"]["trSrvrId"]
    del request.data["tour"]["trSrvrId"]

    if len(request.data["wpsWPics"]) > 0:
        request.data["tour"]["start_loc"] = [request.data["wpsWPics"][0]["tourWp"]["longitude"],
                                             request.data["wpsWPics"][0]["tourWp"]["latitude"]]

    if len(tour_id) == 24:
        result = database[tours_collection].update_one(
            {"_id": ObjectId(tour_id), "usr_id": request.user["id"]},
            {"$set": {"usr_id": request.user["id"],
                      "tour": request.data["tour"],
                      "wpsWPics": request.data["wpsWPics"],
                      "tags": request.data["tags"]}}).upserted_id
        if result is None:
            data = {}
        else:
            data = {"tourServerId": str(result)}

        if "start_loc" in request.data["tour"]:
            database[user_details_collection].update_one({"usr_id": request.user["id"], "tours_locs.tour_id": ObjectId(tour_id)},
                                                         {"$set": {
                                                             "tours_locs.$.loc": request.data["tour"]["start_loc"]}})
    else:
        result = database[tours_collection].insert_one({"usr_id": request.user["id"],
                                                               "tour": request.data["tour"],
                                                               "wpsWPics": request.data["wpsWPics"],
                                                               "tags": request.data["tags"]}).inserted_id
        if result is None:
            data = {}
        else:
            data = {"tourServerId": str(result)}

        if "start_loc" in request.data["tour"]:
            database[user_details_collection].update_one({"usr_id": request.user["id"]},
                                                         {"$push": {
                                                             "tours_locs": {
                                                                 "tour_id": result,
                                                                 "loc": request.data["tour"]["start_loc"]}}},
                                                         upsert=True)
    print("> result : {}".format(result))
    # print(data)
    return Response(status=status.HTTP_200_OK, data=data)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def upsert_tour_images(request):
    # print(request.headers)
    data_dict = dict(request.data)
    tour_id = data_dict["trSrvrId"][0]
    del data_dict["trSrvrId"]
    # print(data_dict)

    imgs_dict = {}
    i = 0
    for (k, v) in data_dict.items():
        if type(v[0]) == str:
            imgs_dict[k.replace(".", "_").replace("$", "_")] = {}
        else:
            imgs_dict[k.replace(".", "_").replace("$", "_")] = {'mime': v[0].content_type,
                                                                'b': Binary(v[0].file.read(), BINARY_SUBTYPE)}
        i += 1

    img_data = {'trSrvrId': tour_id,
                'imgs': imgs_dict
                }
    database[tour_images_collection].update_one({'trSrvrId': tour_id},
                                                {'$set': img_data}, upsert=True)
    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AuthenticationOptional])
def get_tour_by_tour_id(request, _id):
    if len(_id) == 24:
        doc = database[tours_collection].find_one({'_id': ObjectId(_id)})
        doc['tour']['trSrvrId'] = str(doc['_id'])
        del doc['_id']

        doc['author'] = {}
        user_doc = database[user_details_collection].find_one({'usr_id': doc['usr_id']})
        doc['author']['nickname'] = user_doc['nickname']
        doc['author']['is_guide'] = user_doc['prefs']['is_guide']
        del doc['usr_id']

        if request.user is not None:
            # Check if tour is in given username favourites
            # Get favourite tours
            is_fav_doc = database[user_details_collection].distinct('fav_trs', {'usr_id': request.user['id']})
            print('get_tour_by_tour_id fav : {}'.format(len(is_fav_doc)))

            if len(is_fav_doc) > 0:
                doc['tour']['in_favs'] = True
            else:
                doc['tour']['in_favs'] = False

            # Get personal tour rating
            rating_doc = database[tour_ratings_collection].find_one({"usr_id": request.user['id'], "tour_id": ObjectId(_id)})
            if rating_doc is not None:
                doc['tour']['rating'] = rating_doc['rating']

        print('get_tour_by_id : {}'.format(doc))
        return Response(status=status.HTTP_200_OK, data=doc)
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_tour_images_by_tour_id(request, tour_id):
    # print(request.header)
    # print(request.data)
    if len(tour_id) == 24:
        docs = database[tour_images_collection].find({'trSrvrId': tour_id}, {'_id': 0, 'usr_id': 0})
        resp_list = []
        for doc in docs:
            # print('get_tour_images_by_tour_id : {}'.format(doc['trSrvrId']))
            imgs = doc["imgs"]
            for (k, v) in imgs.items():
                if 'b' in v:
                    v["b"] = base64.b64encode(v["b"])
            resp_list.append(doc)
        # print(resp_list)
        return Response(status=status.HTTP_200_OK, data=resp_list[0])
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def get_full_tours_by_user(request, username):  # excluding given obj ids
    data_dict = dict(request.data)
    skip_obj_ids = []
    if 'owndToursIds' in data_dict:
        for id in data_dict['owndToursIds']:
            if len(id) == 24:
                skip_obj_ids.append(ObjectId(id))
        print('get_full_tours_by_user skip_obj_ids : {}'.format(skip_obj_ids))

    # Get user id based on username
    doc_user = database[user_details_collection].find_one({'nickname': username}, {'usr_id': 1, 'prefs.is_guide': 1})

    # Get user tours based on user id and with skipping _ids from skip_obj_ids
    docs = database[tours_collection].find({'usr_id': doc_user['usr_id'], '_id': {'$nin': skip_obj_ids}}, {'usr_id': 0})

    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = str(doc["_id"])
        del doc["_id"]
        doc['author'] = {}
        doc['author']['is_guide'] = doc_user['prefs']['is_guide']
        doc['author']['nickname'] = username
        #del doc["username"]
    print('get_full_tours_by_user {}'.format(docs))
    return Response(status=status.HTTP_200_OK, data=docs)


@api_view(["POST"])
def get_tour_images_by_tour_ids(request):  # including given obj ids
    # print(request.header)
    # print(request.data)
    incl_wps = True if request.query_params['incl_wps'][0] == 't' else False
    print("incl_wps = {}".format(incl_wps))
    docs = database[tour_images_collection].find({'trSrvrId': {'$in': request.data}}, {'_id': 0, 'usr_id': 0})
    resp_list = []
    for doc in docs:
        # print('get_tour_images_by_tour_ids : {}'.format(doc['trSrvrId']))
        imgs = doc["imgs"]
        for (k, v) in imgs.items():
            if 'b' in v:
                v["b"] = base64.b64encode(v["b"])
        resp_list.append(doc)
    # print(resp_list)
    return Response(status=status.HTTP_200_OK, data=resp_list)


@api_view(["DELETE"])
@permission_classes([AuthenticatedOnly])
def delete_tour_by_id(request, _id):
    if len(_id) == 24:
        delete_result = database[tours_collection].delete_one(
            {'_id': ObjectId(_id), 'usr_id': request.user["id"]})
        print('deleted records: {}'.format(delete_result.deleted_count))
        if delete_result.deleted_count > 0:
            database[tour_images_collection].remove({'trSrvrId': _id})
            database[user_details_collection].update_one({"usr_id": request.user["id"]},
                                                         {"$pull": {
                                                             "tours_locs": {
                                                                 "tour_id": ObjectId(_id)
                                                             }
                                                         }})
            return Response(status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def search_tours_by_phrase(request, phrase):
    page_size = 10
    page_num = int(request.query_params['page_num'])
    print("search_tours_by_phrase page_num = {}".format(page_num))

    docs = database[tours_collection].aggregate([
        # $geoNear has to be first stage in aggregation pipeline
        {"$match": {'$text': {'$search': phrase}}},
        {"$project": {'score': {'$meta': "textScore"}, 'tour': 1, 'usr_id': 1}},
        {"$sort": {"score": {"$meta": "textScore"}}},
        {"$skip": (((page_num - 1) * page_size) if page_num > 0 else 0)},
        {"$limit": page_size},
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
        {"$project": {"usr_id": 0, "score": 0}},
        # Flatten field
        {"$addFields": {"author.is_guide": "$author.is_guide.prefs.is_guide"}},
        #{"$count": "doc_count"}
    ])

    resp_list = []
    for doc in docs:
        doc['tour']['trSrvrId'] = str(doc['_id'])
        del doc['_id']
        resp_list.append(doc)
    return Response(status=status.HTTP_200_OK, data=resp_list)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def add_tour_to_favourites(request):
    tour_id = request.data.get('trSrvrId')
    print("add_tour_to_favourites : {}".format(request.data.get('trSrvrId')))
    if len(tour_id) == 24:
        update_result = database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                                     {"$addToSet": {"fav_trs": ObjectId(tour_id)}}, upsert=True)
        return Response(status=status.HTTP_200_OK)
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([AuthenticatedOnly])
def delete_tour_from_favourites(request, tour_id):
    print("delete_tour_from_favourites tour_id : {}".format(tour_id))
    print("delete_tour_from_favourites request.data : {}".format(request.data))
    if len(tour_id) == 24:
        update_result = database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                                     {"$pull": {"fav_trs": ObjectId(tour_id)}})
        return Response(status=status.HTTP_200_OK)
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def get_fav_tours_by_user(request, username):  # excluding given obj ids
    data_dict = dict(request.data)
    skip_obj_ids = []
    if 'owndToursIds' in data_dict:
        for id in data_dict['owndToursIds']:
            if len(id) == 24:
                skip_obj_ids.append(ObjectId(id))
        print('favs skip_obj_ids : {}'.format(skip_obj_ids))

    # Get favourite tours
    doc_user = database[user_details_collection].find_one({'nickname': username}, {'fav_trs': 1, 'usr_id': 1})
    print('favs : {}'.format(doc_user))

    docs = database[tours_collection].aggregate([
        {"$match": {'_id': {'$nin': skip_obj_ids, '$in': doc_user['fav_trs']}}},
        # Left join with tour_ratings_collection
        {
            "$lookup": {
                "from": tour_ratings_collection,  # other table name
                "let": {"uid": "$usr_id", "tr_id": "$_id"},  # aliases for fields from main table
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$usr_id", doc_user['usr_id']]},  # main join condition (i.e. which fields are used for join)
                                    {"$eq": ["$tour_id", "$$tr_id"]}
                                ]
                            }
                        }
                    },
                    {"$project": {'_id': 0, 'rating': 1}}
                ],
                "as": "tour_rating"  # alias for other table
            }
        },
        {"$unwind": {
            "path": "$tour_rating",
            "preserveNullAndEmptyArrays": True
        }},
        {"$addFields": {"tour.rating": "$tour_rating.rating"}},
        {"$project": {'tour_rating': 0}},
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
                    {"$project": {'_id': 0, 'nickname': '$nickname', 'is_guide': '$prefs.is_guide'}}
                ],
                "as": "author"  # alias for other table
            }
        },
        {"$project": {"usr_id": 0}},
        {"$unwind": {
            "path": "$author",
            "preserveNullAndEmptyArrays": True
        }},
        #{"$count": "doc_count"}
    ])

    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = str(doc["_id"])
        del doc["_id"]
    print('get_fav_tours_by_user {}'.format(docs))
    return Response(status=status.HTTP_200_OK, data=docs)


@api_view(["GET"])
def get_nearby_tours(request):  # uses aggregation to join results with user details collection, allowing for marking tour guide created tours
    print('get_nearby_tours input : {}'.format(float(request.query_params.get('long'))))
    page_size = 10
    page_num = int(request.query_params['page_num'])

    docs = database[tours_collection].aggregate([
        # $geoNear has to be first stage in aggregation pipeline
        {
            "$geoNear": {
                "near": [float(request.query_params.get('long')), float(request.query_params.get('lat'))],
                "distanceField": "dist.calculated",
                "key": "tour.start_loc"
            }
        },
        {"$skip": (((page_num - 1) * page_size) if page_num > 0 else 0)},
        {"$limit": page_size},
        {"$project": {'wpsWPics': 0, 'tags': 0}},
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

    resp_list = []
    for doc in docs:
        doc['tour']['trSrvrId'] = str(doc['_id'])
        del doc['_id']
        resp_list.append(doc)
        # print('get_nearby_tours tour : {}'.format(doc['tour']['title']))

    print('get_nearby_tours response : {}'.format(resp_list))
    return Response(status=status.HTTP_200_OK, data=resp_list)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def update_user_settings(request):
    print("update_user_settings : {}".format(request.data))
    prefs_dict = {}
    if 'is_guide' in request.data:
        is_guide = True if request.data.get('is_guide')[0] == 't' else False
        prefs_dict["prefs.is_guide"] = is_guide
    if 'phone_num' in request.data:
        prefs_dict["prefs.phone_num"] = request.data.get('phone_num')
    if 'share_loc' in request.data:
        share_loc = True if request.data.get('share_loc')[0] == 't' else False
        prefs_dict["prefs.share_loc"] = share_loc
    if 'share_loc_token_ttl' in request.data:
        prefs_dict["prefs.loc_ttl"] = int(request.data.get('share_loc_token_ttl'))
    update_result = database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                                 {"$set": prefs_dict}, upsert=True)
    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
def get_nearby_tour_guides(request):
    page_size = 10
    page_num = int(request.query_params['page_num'])
    docs = database[user_details_collection].aggregate([
        # $geoNear has to be first stage in aggregation pipeline
        {
            "$geoNear": {
                "query": {"prefs.is_guide": True},
                "near": [float(request.query_params.get('long')), float(request.query_params.get('lat'))],
                "distanceField": "dist.calculated",
                "key": "tours_locs.loc"
            }
        },
        {"$skip": ((page_num - 1) * page_size) if page_num > 0 else 0},
        {"$limit": page_size},
        {
            "$project": {"_id": 0, "nickname": 1, "rateVal": 1, "rateCount": 1}  # "email": 1, "phone_num": "$prefs.phone_num"
        }
    ])
    return Response(status=status.HTTP_200_OK, data=list(docs))


@api_view(["GET"])
@permission_classes([AuthenticationOptional])
def get_tour_guide_info(request):
    tour_guide_nickname = request.query_params['nickname']
    docs = database[user_details_collection].aggregate([
        {"$match": {'nickname': tour_guide_nickname}},
        {"$limit": 1},
        {"$project": {"_id": 0, "usr_id": 1, "email": 1, "phone_num": "$prefs.phone_num", "rateVal": 1, "rateCount": 1}}
    ])

    response_list = list(docs)
    data = (response_list[0] if len(response_list) > 0 else {})

    if request.user is not None and data:
        # Get personal tour rating
        rating_doc = database[tour_guide_ratings_collection].find_one({"usr_id": request.user['id'], "rtd_usr_id": data["usr_id"]})
        if rating_doc is not None:
            data['rating'] = rating_doc['rating']

    return Response(status=status.HTTP_200_OK, data=data)


@api_view(["GET"])
def get_nearby_tours_overviews_by_user(request, username):  # with pagination
    page_size = 10
    page_num = int(request.query_params['page_num'])

    # Get user id based on username
    docs = database[user_details_collection].find_one({'nickname': username}, {'usr_id': 1})

    docs = database[tours_collection].find({'usr_id': docs['usr_id'],
                                            "tour.start_loc": {"$near": [float(request.query_params.get('long')),
                                                                         float(request.query_params.get('lat'))]}},
                                           {'wpsWPics': 0, 'tags': 0, 'usr_id': 0})\
        .skip(((page_num - 1) * page_size) if page_num > 0 else 0).limit(page_size)

    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = str(doc["_id"])
        del doc["_id"]

    print('get_nearby_tours_overviews_by_user {}'.format(docs))
    return Response(status=status.HTTP_200_OK, data=docs)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def rate_tour(request, tour_id):
    is_owner = (database[tours_collection].count_documents({"_id": ObjectId(tour_id), "usr_id": request.user['id']}, limit=1) != 0)
    if is_owner:
        return Response(status=status.HTTP_403_FORBIDDEN)

    rated_before = database[tour_ratings_collection].find_one({"usr_id": request.user['id'], "tour_id": ObjectId(tour_id)})
    new_rating = float(request.data.get("rating"))
    if rated_before is None:
        database[tours_collection].update_one({"_id": ObjectId(tour_id)},
                                              {"$inc": {"tour.rateCount": 1, "tour.rateVal": new_rating}})
    else:
        old_rating = rated_before['rating']
        database[tours_collection].update_one({"_id": ObjectId(tour_id)},
                                              {"$inc": {"tour.rateVal": new_rating - old_rating}})

    database[tour_ratings_collection].update_one({"usr_id": request.user['id'], "tour_id": ObjectId(tour_id)},
                                                 {"$set": {"rating": new_rating}}, upsert=True)

    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def rate_tour_guide(request, tour_guide_username):
    rates_self = (tour_guide_username == request.user['nickname'])
    if rates_self:
        return Response(status=status.HTTP_403_FORBIDDEN)

    rated_user_id = database[user_details_collection].find_one({"nickname": tour_guide_username}, {"usr_id": 1})
    rated_before = database[tour_guide_ratings_collection].find_one({"usr_id": request.user['id'], "rtd_usr_id": rated_user_id['usr_id']})
    new_rating = float(request.data.get("rating"))
    if rated_before is None:
        database[user_details_collection].update_one({"usr_id": rated_user_id['usr_id']},
                                                     {"$inc": {"rateCount": 1, "rateVal": new_rating}}, upsert=True)
    else:
        old_rating = rated_before['rating']
        database[user_details_collection].update_one({"usr_id": rated_user_id['usr_id']},
                                                     {"$inc": {"rateVal": new_rating - old_rating}}, upsert=True)

    database[tour_guide_ratings_collection].update_one({"usr_id": request.user['id'], "rtd_usr_id": rated_user_id['usr_id']},
                                                       {"$set": {"rating": new_rating}}, upsert=True)

    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
def search_tour_guides_by_phrase(request, phrase):
    page_size = 10
    page_num = int(request.query_params['page_num'])
    print("search_tour_guides_by_phrase page_num = {}".format(page_num))
    docs = database[user_details_collection].find(
        {'$text': {'$search': phrase}}, {'score': {'$meta': "textScore"}, "_id": 0, "nickname": 1,
                                         "rateVal": 1, "rateCount": 1}).sort([('score', {'$meta': "textScore"})])\
        .skip(((page_num - 1) * page_size) if page_num > 0 else 0).limit(page_size)
    resp_list = []
    for doc in docs:
        del doc['score']
        resp_list.append(doc)
    return Response(status=status.HTTP_200_OK, data=resp_list)


### Location sharing components ###

@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def update_tour_guide_location(request):
    docs = database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                        {"$set": {"loc.val": [request.data["long"], request.data["lat"]]}})
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def get_tour_guide_location(request):
    docs = database[user_details_collection].find_one({"loc.token": request.data['token'], 'loc.subs': request.user['id']},
                                                      {"loc.val": 1, "loc.exp": 1, "prefs.share_loc": 1})
    if docs is None or docs["loc"]["exp"] < datetime.datetime.now() or not docs["prefs"]["share_loc"]:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    else:
        return Response(status=status.HTTP_200_OK, data={"long": docs["loc"]["val"][0], "lat": docs["loc"]["val"][1]})


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def subscribe_to_tour_guide_location(request):
    docs = database[user_details_collection].find_one_and_update({"loc.token": request.data["token"]},
                                                                 {"$addToSet": {"loc.subs": request.user['id']}},
                                                                 {"loc.tour_id": 1})
    print("subscribe_to_tour_guide_location docs : {}".format(docs))
    if docs is None:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    else:
        database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                     {"$set": {"subTo.token": request.data["token"],
                                                               "subTo.tour_id": docs["loc"]["tour_id"]}})
        return Response(status=status.HTTP_200_OK, data={"tour_id": str(docs["loc"]["tour_id"])})


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def revoke_sharing_location_token(request):
    database[user_details_collection].update_one({"usr_id": request.user['id']}, {"$unset": {"loc": ""}})
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def get_location_sharing_token(request):
    DEFAULT_TTL = 6
    docs = database[user_details_collection].find_one({"usr_id": request.user['id']},
                                                      {"loc.token": 1, "loc.exp": 1, "prefs.loc_ttl": 1})
    print("get_location_sharing_token docs = {}".format(docs))
    if "loc" in docs and "token" in docs["loc"] and docs["loc"]["exp"] > datetime.datetime.now():
        data = {"token": docs["loc"]["token"]}
    else:
        loc_token = secrets.token_urlsafe()
        if "prefs" in docs and "loc_ttl" in docs["prefs"]:
            ttl = docs["prefs"]["loc_ttl"]
        else:
            ttl = DEFAULT_TTL
        exp = datetime.datetime.now() + datetime.timedelta(hours=ttl)
        database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                     {"$set": {"loc.token": loc_token, "loc.exp": exp,
                                                               "loc.tour_id": ObjectId(request.data['tour_id'])}})
        data = {"token": loc_token}
    return Response(status=status.HTTP_200_OK, data=data)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def update_user_image(request):
    print("update_user_image : {}".format(request.data))
    if 'tg_img' not in request.data:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    tg_img = request.data.get('tg_img')
    img_dict = {'mime': tg_img.content_type, 'b': Binary(tg_img.file.read(), BINARY_SUBTYPE)}
    update_result = database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                                 {"$set": {'img': img_dict}}, upsert=True)
    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AuthenticatedOnly])
def get_tour_guide_image(request):
    # print(request.header)
    # print(request.data)
    doc = database[user_details_collection].find_one({"usr_id": request.user['id']}, {'_id': 0, 'img': 1})
    doc['img']['b'] = base64.b64encode(doc['img']['b'])
    print(doc)
    # print(resp_list)
    return Response(status=status.HTTP_200_OK, data=doc['img'])


@api_view(["POST"])
def get_tour_guides_images_by_nicknames(request):  # including given obj ids
    # print(request.header)
    # print(request.data)
    docs = database[user_details_collection].find({'nickname': {'$in': request.data}}, {'_id': 0, 'nickname': 1, 'img': 1})
    resp_list = []
    for doc in docs:
        print('get_tour_guides_images_by_nicknames : {}'.format(doc))
        if 'img' in doc:
            img = doc["img"]
            if 'b' in img:
                img["b"] = base64.b64encode(img["b"])
        resp_list.append(doc)
    # print(resp_list)
    return Response(status=status.HTTP_200_OK, data=resp_list)
