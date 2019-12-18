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
user_details_collection = "user_details"
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
                user_prefs = database[user_details_collection].find_one({"usr_id": user['id']}, {"_id": 0, "prefs": 1})
                user_prefs = user_prefs['prefs'] if user_prefs is not None and "prefs" in user_prefs else {}
                return Response(status=status.HTTP_200_OK,
                                data={"data": {"token": token, "prefs": user_prefs}})
            else:
                return Response(status=status.HTTP_403_FORBIDDEN,
                                data={"error_msg": messages.incorrect_password})
        else:
            return Response(status=status.HTTP_403_FORBIDDEN,
                            data={"data": {"error_msg": messages.user_not_found}})
    except ValidationError as v_error:
        return Response(status=status.HTTP_400_BAD_REQUEST,
                        data={'success': False, 'message': str(v_error)})
    #except Exception as e:
    #    return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #                    data={"data": {"error_msg": str(e)}})


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
                'username': request.user['nickname'],
                'imgs': imgs_dict
                }
    database[tour_images_collection].update_one({'trSrvrId': tour_id},
                                                {'$set': img_data}, upsert=True)
    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
def get_tour_by_tour_id(request, _id):
    if len(_id) == 24:
        doc = database[tours_collection].find_one({'_id': ObjectId(_id)}, {'usr_id': 0})
        doc['tour']['trSrvrId'] = str(doc['_id'])
        del doc['_id']

        if 'username' in request.query_params:
            username = request.query_params['username']
            print('get_tour_by_tour_id username : {}'.format(username))

            # Get user id based on username
            user_id_doc = database[user_profile_collection].find_one({'nickname': username}, {'id': 1})
            print('get_tour_by_tour_id user id : {}'.format(user_id_doc['id']))

            # Get favourite tours
            is_fav_doc = database[user_details_collection].distinct('fav_trs', {'usr_id': user_id_doc['id']})
            print('get_tour_by_tour_id fav : {}'.format(len(is_fav_doc)))

            if len(is_fav_doc) > 0:
                doc['tour']['in_favs'] = True
            else:
                doc['tour']['in_favs'] = False

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
        print('get_tours_by_user skip_obj_ids : {}'.format(skip_obj_ids))

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
    docs = database[tours_collection].find(
        {'$text': {'$search': phrase}}, {'score': {'$meta': "textScore"}, 'wpsWPics': 0, 'tags': 0, 'usr_id': 0}).sort(
        [('score', {'$meta': "textScore"})]).skip(((page_num - 1) * page_size) if page_num > 0 else 0).limit(page_size)
    resp_list = []
    for doc in docs:
        doc['tour']['trSrvrId'] = str(doc['_id'])
        del doc['score']
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

    # Get user id based on username
    docs = database[user_profile_collection].find_one({'nickname': username}, {'id': 1})
    print('favs user id : {}'.format(docs['id']))

    # Get favourite tours
    docs = database[user_details_collection].distinct('fav_trs', {'usr_id': docs['id'], 'fav_trs': {'$nin': skip_obj_ids}})
    print('favs : {}'.format(docs))

    docs = database[tours_collection].find({'_id': {'$in': docs}}, {'usr_id': 0})
    docs = list(docs)
    for doc in docs:
        doc["tour"]["trSrvrId"] = str(doc["_id"])
        del doc["_id"]
    print('get_fav_tours_by_user {}'.format(docs))
    return Response(status=status.HTTP_200_OK, data=docs)


@api_view(["GET"])
def get_nearby_tours(request):
    print('get_nearby_tours input : {}'.format(float(request.query_params.get('long'))))
    page_size = 10
    page_num = int(request.query_params['page_num'])

    docs = database[tours_collection].find({"tour.start_loc": {"$near": [float(request.query_params.get('long')),
                                                                         float(request.query_params.get('lat'))]}},
                                           {'wpsWPics': 0, 'tags': 0, 'usr_id': 0})\
        .skip(((page_num - 1) * page_size) if page_num > 0 else 0).limit(page_size)

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
    print("add_tour_to_favourites : {}".format(request.data))
    prefs_dict = {"name": request.user['nickname']}
    if 'is_guide' in request.data:
        is_guide = True if request.data.get('is_guide')[0] == 't' else False
        prefs_dict["prefs.is_guide"] = is_guide
    if 'phone_num' in request.data:
        prefs_dict["prefs.phone_num"] = request.data.get('phone_num')
    if 'share_loc' in request.data:
        share_loc = True if request.data.get('share_loc')[0] == 't' else False
        prefs_dict["prefs.share_loc"] = share_loc
    update_result = database[user_details_collection].update_one({"usr_id": request.user['id']},
                                                                 {"$set": prefs_dict}, upsert=True)
    return Response(status=status.HTTP_200_OK)


@api_view(["POST"])
def get_nearby_tour_guides(request):
    docs = database[user_details_collection].find({"prefs.is_guide": True, "tours_locs.loc": {"$near": [0.0, 0.0]}},
                                                  {"_id": 0, "name": 1})
    return Response(status=status.HTTP_200_OK)
