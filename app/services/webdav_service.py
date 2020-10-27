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
Provide some informations about the user and his projects.
"""
@webdav_service.route("/user/info",methods=["POST"])
def webdav_user_info():
    user_name = request.form.get("user_name")
    password = request.form.get("password")

    if user_name and password:
        # Find user by email
        user = user_controller.find_user(email=user_name)

        # check user password by verifying passwordhash
        if user and current_app.user_manager.password_manager.verify_password(password,user.password):
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
