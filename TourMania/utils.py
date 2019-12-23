import jwt
from mongo_auth.db import jwt_secret, auth_collection
from mongo_auth.db import database
from TourMania.db_collections import user_details_collection


def login_status(request):
    token = request.META.get('HTTP_AUTHORIZATION')
    data = jwt.decode(token, jwt_secret, algorithms=['HS256'])
    user_obj = None
    flag = False
    user_obj = database[auth_collection].find_one({"id": data["id"]}, {"_id": 0, "password": 0})
    if user_obj:
        flag = True
        user_details_filter = database[user_details_collection].find_one({"usr_id": data["id"]}, {"_id": 0, "email": 1, "nickname": 1})
        for field in user_details_filter:
            user_obj[field] = user_details_filter[field]
    return flag, user_obj
