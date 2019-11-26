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
    #print(request.headers)
    #print(request.data)
    #print(request.user)
    tour_id = request.data["tour"]["trSrvrId"]
    del request.data["tour"]["trSrvrId"]
    if len(tour_id) == 24:
        update_result = database[tours_collection].update_one({"_id": ObjectId(tour_id), "username": request.user["nickname"]},
                                                              {"$set": {"username": request.user["nickname"],
                                                                        "tour": request.data["tour"],
                                                                        "wpsWPics": request.data["wpsWPics"],
                                                                        "tags": request.data["tags"]}}).upserted_id
        if update_result is None:
            data = {}
        else:
            data = {"tourServerId": str(update_result)}
    else:
        insert_result = database[tours_collection].insert_one({"username": request.user["nickname"],
                                                               "tour": request.data["tour"],
                                                               "wpsWPics": request.data["wpsWPics"],
                                                               "tags": request.data["tags"]}).inserted_id
        if insert_result is None:
            data = {}
        else:
            data = {"tourServerId": str(insert_result)}
    #print(data)
    return Response(status=status.HTTP_200_OK, data=data)


@api_view(["POST"])
@permission_classes([AuthenticatedOnly])
def upsert_tour_images(request):
    #print(request.headers)
    data_dict = dict(request.data)
    tour_id = data_dict["trSrvrId"][0]
    del data_dict["trSrvrId"]
    #print(data_dict)

    imgs_dict = {}
    i = 0
    for (k, v) in data_dict.items():
        if type(v[0]) == str:
            imgs_dict[k.replace(".", "_").replace("$", "_")] = {}
        else:
            imgs_dict[k.replace(".", "_").replace("$", "_")] = {'mime': v[0].content_type, 'b': Binary(v[0].file.read(), BINARY_SUBTYPE)}
        i += 1

    img_data = {'trSrvrId': tour_id,
                'username': request.user['nickname'],
                'imgs': imgs_dict
                }
    database[tour_images_collection].update_one({'trSrvrId': tour_id, 'username': request.user['nickname']},
                                                {'$set': img_data}, upsert=True)
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
def get_tours_by_user(request, username):
    data_dict = dict(request.data)
    skip_obj_ids = []
    if 'owndToursIds' in data_dict:
        for id in data_dict['owndToursIds']:
            if len(id) == 24:
                skip_obj_ids.append(ObjectId(id))
        #print(skip_obj_ids)
    docs = database[tours_collection].find({'username': username, '_id': {'$nin': skip_obj_ids}})
    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = str(doc["_id"])
        del doc["_id"]
        del doc["username"]
    return Response(status=status.HTTP_200_OK, data=docs)


@api_view(["POST"])
def get_tour_images_by_tour_ids(request):
    #print(request.header)
    #print(request.data)
    docs = database[tour_images_collection].find({'trSrvrId': {'$in': request.data}}, {'_id': 0})
    resp_list = []
    for doc in docs:
        imgs = doc["imgs"]
        for (k, v) in imgs.items():
            if 'b' in v:
                v["b"] = base64.b64encode(v["b"])
        resp_list.append(doc)
    #print(resp_list)
    return Response(status=status.HTTP_200_OK, data=resp_list)


@api_view(["DELETE"])
@permission_classes([AuthenticatedOnly])
def delete_tour_by_id(request, _id):
    if len(_id) == 24:
        delete_result = database[tours_collection].delete_one({'_id': ObjectId(_id), 'username': request.user["nickname"]})
        if delete_result.deleted_count > 0:
            database[tour_images_collection].remove({'trSrvrId': _id})
        return Response(status=status.HTTP_200_OK)
    else:
        return Response(status=status.HTTP_400_BAD_REQUEST)
