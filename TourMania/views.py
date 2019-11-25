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
        update_result = database[tours_collection].update_one({"_id": ObjectId(tour_id), "usrId": request.user["id"]},
                                                              {"$set": {"usrId": request.user["id"],
                                                                        "tour": request.data["tour"],
                                                                        "wpsWPics": request.data["wpsWPics"],
                                                                        "tags": request.data["tags"]}}).upserted_id
        if update_result is None:
            data = {}
        else:
            data = {"tourServerId": str(update_result)}
    else:
        insert_result = database[tours_collection].insert_one({"usrId": request.user["id"],
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
    for (k, v) in data_dict.items():
        imgs_dict[k.replace(".", "_").replace("$", "_")] = {'mime': v[0].content_type, 'b': Binary(v[0].file.read(), BINARY_SUBTYPE)}

    img_data = {'trSrvrId': tour_id,
                'usrId': request.user['id'],
                'imgs': imgs_dict
                }
    database[tour_images_collection].update_one({'trSrvrId': tour_id, 'usrId': request.user['id']}, {'$set': img_data}, upsert=True)
    return Response(status=status.HTTP_200_OK)
