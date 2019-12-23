from rest_framework import permissions
from TourMania.utils import login_status


class AuthenticationOptional(permissions.BasePermission):

    def has_permission(self, request, view):
        request.user = None
        try:
            flag, user_obj = login_status(request)
            if flag:
                request.user = user_obj
        except Exception as e:
            pass
        return True


class AuthenticatedOnly(permissions.BasePermission):

    def has_permission(self, request, view):
        try:
            flag, user_obj = login_status(request)
            request.user = None
            if flag:
                request.user = user_obj
                return True
            else:
                return False
        except Exception as e:
            return False
