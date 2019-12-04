from django.shortcuts import render
from mongo_auth.permissions import AuthenticatedOnly
from rest_framework.decorators import permission_classes, api_view
from mongo_auth.utils import create_unique_object_id, pwd_context
from mongo_auth.db import database, auth_collection, fields, jwt_life, jwt_secret, secondary_username_field
import jwt
import datetime
from mongo_auth import messages
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from bson.objectid import ObjectId
from bson.binary import Binary, BINARY_SUBTYPE
import base64

tours_collection = "tours"
tour_images_collection = "tour_images"
user_prefs_collection = "user_prefs"
user_profile_collection = "user_profile"


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
    doc = database['users'].find({})
    print(doc)
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
        user = database[auth_collection].find_one({"email": username}, {"_id": 0})
        if user is None:
            user = database[auth_collection].find_one({secondary_username_field: username}, {"_id": 0})
        if user is not None:
            if pwd_context.verify(password, user["password"]):
                token = jwt.encode({'id': user['id'],
                                    'exp': datetime.datetime.now() + datetime.timedelta(
                                        days=jwt_life)},
                                   jwt_secret, algorithm='HS256').decode('utf-8')
                return Response(status=status.HTTP_200_OK,
                                data={"data": {"token": token}})
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
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        data={"data": {"error_msg": str(e)}})


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def upsert_tour(request):
    # print(request.headers)
    # print(request.data)
    # print(request.user)
    tour_id = request.data["tour"]["trSrvrId"]
    del request.data["tour"]["trSrvrId"]
    # tours_collection
    # 'text_search_test'
    if len(tour_id) == 24:
        update_result = database[tours_collection].update_one(
            {"_id": ObjectId(tour_id), "username": request.user["nickname"]},
            {"$set": {"username": request.user["nickname"],
                      "tour": request.data["tour"],
                      "wpsWPics": request.data["wpsWPics"],
                      "tags": request.data["tags"]}}).upserted_id
        if update_result is None:
            data = {}
        else:
            data = {"tourServerId": str(update_result)}
    else:
        insert_result = database[tours_collection].insert_one({"usr_id": request.user["id"],
                                                               "tour": request.data["tour"],
                                                               "wpsWPics": request.data["wpsWPics"],
                                                               "tags": request.data["tags"]}).inserted_id
        if insert_result is None:
            data = {}
        else:
            data = {"tourServerId": str(insert_result)}
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
                'username': request.user['nickname'],
                'imgs': imgs_dict
                }
    database[tour_images_collection].update_one({'trSrvrId': tour_id},
                                                {'$set': img_data}, upsert=True)
    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
def get_tour_by_tour_id(request, _id):
    if len(_id) == 24:
        docs = database[tours_collection].find({'_id': ObjectId(_id)}, {'usr_id': 0})
        resp_list = []
        for doc in docs:
            doc['tour']['trSrvrId'] = str(doc['_id'])
            del doc['_id']
            resp_list.append(doc)
        print('get_tour_by_id : {}'.format(resp_list))
        return Response(status=status.HTTP_200_OK, data=resp_list[0])
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
            print('get_tour_images_by_tour_ids : {}'.format(doc['trSrvrId']))
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
def get_tours_by_user(request, username):  # excluding given obj ids
    data_dict = dict(request.data)
    skip_obj_ids = []
    if 'owndToursIds' in data_dict:
        for id in data_dict['owndToursIds']:
            if len(id) == 24:
                skip_obj_ids.append(ObjectId(id))
        print(skip_obj_ids)

    # Get user id based on username
    docs = database[user_profile_collection].find_one({'nickname': username}, {'id': 1})

    # Get user tours based on user id and with skipping _ids from skip_obj_ids
    docs = database[tours_collection].find({'usr_id': docs['id'], '_id': {'$nin': skip_obj_ids}}, {'usr_id': 0})

    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = str(doc["_id"])
        del doc["_id"]
        #del doc["username"]
    print('get_tours_by_user {}'.format(docs))
    return Response(status=status.HTTP_200_OK, data=docs)


@api_view(["POST"])
def get_tour_images_by_tour_ids(request):  # including given obj ids
    # print(request.header)
    # print(request.data)
    incl_wps = True if request.query_params['incl_wps'][0] == 't' else False
    print(request.data)
    print("incl_wps = {}".format(incl_wps))
    docs = database[tour_images_collection].find({'trSrvrId': {'$in': request.data}}, {'_id': 0, 'usr_id': 0})
    resp_list = []
    for doc in docs:
        print('get_tour_images_by_tour_ids : {}'.format(doc['trSrvrId']))
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
            return Response(status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def search_tours_by_phrase(request, phrase):
    page_size = 10
    page_num = int(request.query_params['page_num'])
    print("page_num = {}".format(page_num))
    docs = database[tours_collection].find(
        {'$text': {'$search': phrase}}, {'score': {'$meta': "textScore"}, 'wpsWPics': 0, 'tags': 0, 'usr_id': 0}).sort(
        [('score', {'$meta': "textScore"})]).skip(((page_num - 1) * page_size) if page_num > 0 else 0).limit(page_size)
    resp_list = []
    for doc in docs:
        doc['tour']['trSrvrId'] = str(doc['_id'])
        del doc['score']
        del doc['_id']
        resp_list.append(doc)
    print(resp_list)
    return Response(status=status.HTTP_200_OK, data=resp_list)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def add_tour_to_favourites(request):
    tour_id = request.data.get('trSrvrId')
    print(type(request.data.get('trSrvrId')))
    print("add_tour_to_favourites : {}".format(request.data.get('trSrvrId')))
    print(request.user['id'])
    if len(tour_id) == 24:
        update_result = database[user_prefs_collection].update_one({"usr_id": request.user['id']},
                                                                   {"$addToSet": {"fav_trs": ObjectId(tour_id)}}, upsert=True)
        return Response(status=status.HTTP_200_OK)
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([AuthenticatedOnly])
def delete_tour_from_favourites(request, tour_id):
    print(tour_id)
    print(request.data)
    if len(tour_id) == 24:
        update_result = database[user_prefs_collection].update_one({"usr_id": request.user['id']},
                                                                   {"$pull": {"fav_trs": tour_id}})
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

    # Get user id based on username
    docs = database[user_profile_collection].find_one({'nickname': username}, {'id': 1})
    print('favs user id : {}'.format(docs['id']))

    # Get favourite tours
    docs = database[user_prefs_collection].distinct('fav_trs', {'usr_id': docs['id'], '_id': {'$nin': skip_obj_ids}})
    print('favs : {}'.format(docs))

    docs = database[tours_collection].find({'_id': {'$in': docs}}, {'usr_id': 0})
    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = str(doc["_id"])
        del doc["_id"]
    print('get_fav_tours_by_user {}'.format(docs))
    return Response(status=status.HTTP_200_OK, data=docs)

