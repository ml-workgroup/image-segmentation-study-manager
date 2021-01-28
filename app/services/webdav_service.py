import io
import json
import os
import re
import logging
import traceback

from datetime import datetime
from dateutil.parser import parse as parse_date_string
import zipfile
from gzip import GzipFile

import flask
import nibabel
from functools import wraps
from flask import Blueprint, request, redirect, jsonify, flash
from flask_user import login_required
from flask_login import current_user
from sqlalchemy import or_, asc, desc
from sqlalchemy import DateTime, Date
from nibabel import FileHolder, Nifti1Image
from nibabel.dataobj_images import DataobjImage
from nibabel.filebasedimages import SerializableImage

from app import app, db, current_project
from app.models.config import DATE_FORMAT, DATETIME_FORMAT
from app.models.data_pool_models import StatusEnum, SplitType, Image, ManualSegmentation, AutomaticSegmentationModel, AutomaticSegmentation, Message, Modality, ContrastType

from app.utils import is_project_reviewer, is_project_user, technical_admin_required, project_admin_required, project_reviewer_required, project_user_required

from app.controllers import data_pool_controller, project_controller, user_controller
from flask import current_app


# Define the blueprint: 'webdav_service', set its url prefix: app.url/webdav
webdav_service = Blueprint('webdav_service', __name__, url_prefix='/webdav')

"""
Checks the user authentication.
"""
def webdav_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        
        user_name = request.form.get("user_name")
        password = request.form.get("password")

        if user_name and password:
            # Find user by email
            user = user_controller.find_user(email=user_name)

            # check user password by verifying passwordhash
            if user and current_app.user_manager.password_manager.verify_password(password,user.password):
                kwargs['user'] = user
                return f(*args, **kwargs)
            else:
                return {
                    'success': False,
                    'data': None
                }, 200
        else:
            return {
                'success': False,
                'data': None
            }, 200
    return decorated_function

"""
Check if the project is present
"""
def webdav_project_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'project_id' not in kwargs:
            return {
                'success': False,
                'error': "No valid project id provided", 
                'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
            }, 400
        
        project = project_controller.find_project(id = kwargs['project_id'])

        if project is None:
            return {
                'success': False,
                'error': "No valid project id provided", 
                'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
            }, 400


        kwargs['project'] = project
        return f(*args, **kwargs)
    return decorated_function


"""
Check if the case is present
"""
def webdav_case_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'case_id' not in kwargs or 'project' not in kwargs:
            return {
                'success': False,
                'error': "No image or project provided.", 
                'message': f"No image found for {kwargs['case_id']}, upload an image first."
            }, 400
        
        image = data_pool_controller.find_image(id = kwargs['case_id'])

        if image is None or image.project_id != kwargs['project'].id:
            return {
                'success': False,
                'error': "No image provided.",
                'message': f"No image found for {kwargs['case_id']}, upload an image first."
            }, 400


        kwargs['image'] = image
        return f(*args, **kwargs)
    return decorated_function

"""
Get Functions
"""

"""
Provide some informations about the user and his projects.
"""
@webdav_service.route("/user/info",methods=["POST"])
@webdav_login_required
def webdav_user_info(user):
    # Get all user projects by role
    projects_admin = user.admin_for_project.all()
    projects_reviewer = user.reviewer_for_project.all()
    projects_user = user.user_for_project.all()
    
    return {
        'success': True,
        'data': {
            'user': user.as_dict(),
            'projects_user': [record.as_dict() for record in projects_user],
            'projects_reviewer': [record.as_dict() for record in projects_reviewer],
            'projects_admin': [record.as_dict() for record in projects_admin],
        }
    }, 200

"""
Get filtered Cases for an Project.
"""
@webdav_service.route("/project/<int:project_id>/case/<string:filter_name>",methods=["POST"])
@webdav_login_required
@webdav_project_required
def webdav_project_get_cases(project_id, filter_name, user, project):
    # Build query
    query = db.session.query(Image)

    # only Images to requested project_id
    query = query.filter(Image.project_id == project.id)
    # Database JOIN on Manual Segmentation
    query = query.join(ManualSegmentation, Image.id == ManualSegmentation.image_id, isouter=True)
    # Database Outter JOIN Modality and ContrastType
    query = query.join(Modality, isouter=True).join(ContrastType, isouter=True)

    is_user = user in project.role_users
    is_reviewer = user in project.role_reviewers
    is_admin = user in project.role_admins

    # Check access to the project
    if not is_user or not is_reviewer or not is_admin:
        return {
                'success': False,
                'error': "The user has no access to the project.", 
                'message': "Please specify another project."
            }, 400
    
    #Filter queued Images
    if filter_name == "all":
        query = query
    elif filter_name == "review":
        if not is_reviewer or not is_admin:
            return {
                    'success': False,
                    'error': "The user cannot apply this filter to the project.", 
                    'message': "Please specify another project."
                }, 400

        query = query.filter(Image.status == StatusEnum.submitted)
    elif filter_name == "assign":
        query = query.filter(or_(Image.status == StatusEnum.assigned, Image.status == StatusEnum.rejected)).filter(Image.assignee_id == user.id)
    elif filter_name == "queued":
        query = query.filter(Image.status == StatusEnum.queued)
    else:
        return {
                'success': False,
                'error': "Filter not valid.", 
                'message': "The submitted filter is not valid."
            }, 400

    #Retrieve all images
    records = query.all()
    
    data = [record.as_dict() for record in records]

    return {
        'success': True,
        'data': data
    }, 200



"""
END Get Functions
"""
"""
Set Functions
"""

"""
Accepts manual segmentation of a case of a specified project.
"""
@webdav_service.route("/project/<int:project_id>/case/<int:case_id>/accept",methods=["POST"])
@webdav_login_required
@webdav_project_required
@webdav_case_required
def webdav_project_accept_manual_segmentation(project_id, case_id, user, project, image):
    
    # Check if the user is reviewer
    if user not in project.role_reviewers:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You are not permitted to accept this case."
        }, 400

    # Check image state
    if not image.status == StatusEnum.submitted:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You can not change the state of the case."
        }, 400
    
    if image.manual_segmentation is None:
        return {
            'success': False,
            'error': "No manual segmentation provided.", 
            'message': f"Before you change the status of case {case_id}, upload a manual segmentation."
        }, 400

    data_pool_controller.accept_manual_segmentation(image = image, manual_segmentation = image.manual_segmentation, message = None, target_user = user)

    return {
        'success': True,
        'data': image.as_dict()
    }, 200

"""
Rejects manual segmentation of a case of a specified project.
"""
@webdav_service.route("/project/<int:project_id>/case/<int:case_id>/reject",methods=["POST"])
@webdav_login_required
@webdav_project_required
@webdav_case_required
def webdav_project_reject_manual_segmentation(project_id, case_id, user, project, image):
    # Check if the user is reviewer
    if user not in project.role_reviewers:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You are not permitted to reject this case."
        }, 400

    # Check image state
    if not image.status == StatusEnum.submitted:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You can not change the state of the case."
        }, 400

    if image.manual_segmentation is None:
        return {
            'success': False,
            'error': "No manual segmentation provided.", 
            'message': f"Before you change the status of case {case_id}, upload a manual segmentation."
        }, 400

    data_pool_controller.reject_manual_segmentation(image = image, manual_segmentation = image.manual_segmentation, message = None, target_user = user)

    return {
        'success': True,
        'data': image.as_dict()
    }, 200

"""
Submits manual segmentation of a case of a specified project.
"""
@webdav_service.route("/project/<int:project_id>/case/<int:case_id>/submit",methods=["POST"])
@webdav_login_required
@webdav_project_required
@webdav_case_required
def webdav_project_submit_manual_segmentation(project_id, case_id, user, project, image):
    # Check if the user is project users
    if user not in project.role_users:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You are not permitted to submit this case."
        }, 400
    
    # Check image state
    if not (image.status == StatusEnum.assigned or image.status == StatusEnum.rejected) or image.status == StatusEnum.submitted:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You can not change the state of the case."
        }, 400

    if image.manual_segmentation is None:
        return {
            'success': False,
            'error': "No manual segmentation provided.", 
            'message': f"Before you change the status of case {case_id}, upload a manual segmentation."
        }, 400

    data_pool_controller.submit_manual_segmentation(image = image, manual_segmentation = image.manual_segmentation, message = None, target_user = user)

    return {
        'success': True,
        'data': image.as_dict()
    }, 200  


"""
Assign a case of a specified project to myself.
"""
@webdav_service.route("/project/<int:project_id>/case/<int:case_id>/assign",methods=["POST", "GET"])
@webdav_login_required
@webdav_project_required
@webdav_case_required
def webdav_project_assign_manual_segmentation(project_id, case_id, user, project, image):
    # Check if the user is project users
    if user not in project.role_users:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You are not permitted to assign this case."
        }, 400
    
    # Check image state
    if not (image.status == StatusEnum.queued or image.status == StatusEnum.assign and image.assignee_id != user.id):
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You can not change the state of the case."
        }, 400

    data_pool_controller.assign_manual_segmentation(image = image, assignee = user, message = None)

    return {
        'success': True,
        'data': image.as_dict()
    }, 200  

"""
Upload a case of a specified project.
"""
@webdav_service.route("/project/<int:project_id>/case/upload/<string:name>",methods=["POST"])
@webdav_login_required
@webdav_project_required
def webdav_project_upload_case(project_id, name, user, project): 
     # Check if the user is project users
    if user not in project.role_users:
        return {
            'success': False,
            'error': "Not permitted", 
            'message': "You are not permitted to submit this case."
        }, 400

    image = data_pool_controller.create_image(project = project, name = name)

    return {
        'success': True,
        'data': image.as_dict()
    }, 200
        
"""
END SET Functions
"""