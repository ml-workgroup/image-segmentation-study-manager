import re
import logging
from functools import wraps

# flask inports
from flask import abort, request
from flask_login import current_user, AnonymousUserMixin

from werkzeug.local import LocalProxy

# own modules
from app import app
from app.models.user_models import User
from app.controllers import user_controller, project_controller

# add current_project globally
def get_current_project():
    app.logger.debug(f"get_current_project: {app}")

    id_finder = re.compile(r'.*?\/project\/(?P<project_id>\d+)')
    matches = id_finder.match(request.path)

    if not matches:  # not a valid project path
        app.logger.debug(f"Path has no project id {request.path}")
        return None

    id_group = matches.group('project_id')
    project_id = int(id_group)
    
    # app.logger.debug(f"{request.path} has project id {id_group} or as int {project_id}")

    current_project = project_controller.find_project(id = project_id)

    return current_project

def is_logged_in():
    if isinstance(current_user, User):
        return True
    # current_user is of type LocalProxy and actually a AnonymousUserMixin if not logged in
    elif isinstance(current_user, LocalProxy):
        return not isinstance(current_user._get_current_object(), AnonymousUserMixin)

def is_technical_admin():
    return is_logged_in() and any(role.name == 'admin' for role in current_user.roles)

def is_project_admin(project):

    if project is not None and is_logged_in():
        return current_user in project.role_admins
    else:
        return False

def is_project_reviewer(project):

    if project is not None and is_logged_in():
        # includes check, if the current_user is admin, 
        # because current_project.role_reviewers includes admins
        return current_user in project.role_reviewers
    else:
        return False

def is_project_user(project):
    
    if project is not None and is_logged_in():
        # includes check, if the current_user is admin or reviewer, 
        # because current_project.role_reviewers includes admins and reviewers
        return current_user in project.role_users
    else:
        return False

def technical_admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if is_technical_admin():
            return func(*args, **kwargs)
        else:
            return abort(403)
            
    return decorated_view

def project_admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        current_project = get_current_project()

        if is_technical_admin() or is_project_admin(current_project):
            return func(*args, **kwargs)
        else:
            return abort(403)
    return decorated_view

def project_reviewer_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        current_project = get_current_project()

        if is_technical_admin() or is_project_reviewer(current_project):
            return func(*args, **kwargs)
        else:
            return abort(403)
    return decorated_view

def project_user_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        current_project = get_current_project()

        if is_technical_admin() or is_project_user(current_project):
            return func(*args, **kwargs)
        else:
            return abort(403)
    return decorated_view


def flat_dict(input_dict):

    new_dict = {}

    for (key, val) in input_dict.items():
        if type(val)==dict:
            flat_dict_val = flat_dict(val)
            
            for (flat_key, val) in flat_dict_val.items():
                #if key not in new_dict:
                new_dict[key + '.' + flat_key] = val
        else:
            new_dict[key] = val

    return new_dict

def db_results_to_searchpanes(records, filtered_records, column_mapping):
    record_meta = None
    
    # Getting Metadata
    if len(records) > 0:
        record_meta = records[0].__table__.columns

    searchpanes = {
            "options":{}
        }

    # first all records
    for record in records:
        record_dict = flat_dict(record.as_dict())

        for col_name in column_mapping:
            if col_name in record_dict:
                col_value = record_dict[col_name]

                # search for option
                if col_name not in searchpanes['options']:
                    searchpanes['options'][col_name] = []

                # search in option for value
                filtered_list = list(filter(lambda item: col_value == item['label'] , searchpanes['options'][col_name]))

                if len(filtered_list) > 0:
                    filtered_list[0]['total'] += 1
                else:
                    searchpanes['options'][col_name].append({
                        "label":col_value,
                        "total": 1,
                        "value":col_value,
                        "count": 0
                    })

    # secondly the filtered records
    for record in filtered_records:
        record_dict = flat_dict(record.as_dict())
        for col_name in column_mapping:
            if col_name in record_dict:
                col_value = record_dict[col_name]

                # search for option
                if col_name not in searchpanes['options']:
                    searchpanes['options'][col_name] = []

                # search in option for value
                filtered_list = list(filter(lambda item: col_value == item['label'] , searchpanes['options'][col_name]))

                if len(filtered_list) > 0:
                    filtered_list[0]['count'] += 1
                else:
                    searchpanes['options'][col_name].append({
                        "label":col_value,
                        "total": 1,
                        "value":col_value,
                        "count": 1
                    })

    return searchpanes

