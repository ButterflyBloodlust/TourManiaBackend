'''
    Modified version of mango-jwt utils.py. Mango-jwt is distributed under MIT license.
'''

import uuid
import jwt
from passlib.context import CryptContext
from TourMania.mongo_db import jwt_secret, auth_collection, database
from TourMania.db_collections import user_details_collection


pwd_context = CryptContext(
    default="django_pbkdf2_sha256",
    schemes=["django_argon2", "django_bcrypt", "django_bcrypt_sha256",
             "django_pbkdf2_sha256", "django_pbkdf2_sha1",
             "django_disabled"])


def create_unique_object_id():
    unique_object_id = "ID_{uuid}".format(uuid=uuid.uuid4())
    return unique_object_id


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
