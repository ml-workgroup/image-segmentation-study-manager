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
from sqlalchemy import or_, and_, asc, desc
from sqlalchemy import DateTime, Date
from nibabel import FileHolder, Nifti1Image
from nibabel.dataobj_images import DataobjImage
from nibabel.filebasedimages import SerializableImage

from app import app, db, current_project
from app.models.config import DATE_FORMAT, DATETIME_FORMAT
from app.models.data_pool_models import StatusEnum, SplitType, Image, ManualSegmentation, AutomaticSegmentationModel, AutomaticSegmentation, Message, Modality, ContrastType
from app.models.user_models import User

from app.utils import is_project_reviewer, is_project_user, technical_admin_required, project_admin_required, project_reviewer_required, project_user_required, db_results_to_searchpanes

from app.controllers import data_pool_controller, project_controller, user_controller

# Define the blueprint: 'data_pool_service', set its url prefix: app.url/data_pool
data_pool_service = Blueprint('data_pool_service', __name__, url_prefix='/data_pool')

"""
Get all Status values for Images
"""
@data_pool_service.route("/statusEnum/all")
@login_required
def get_all_image_status_values():

    data = {
        "status_enum": [statusEnum.as_dict() for statusEnum in StatusEnum]
    }

    return jsonify(data)


"""
Get all User of the project
"""
@data_pool_service.route("/project/<int:project_id>/users")
@login_required
def get_all_project_users(project_id):
    users = data_pool_controller.get_all_users_for_project(project_id = project_id)


    app.logger.info(users)

    data = {
        "users": [user.as_dict() for user in users]
    }

    return jsonify(data)

"""
Get all Split values for Images of a project
"""
@data_pool_service.route("/project/<int:project_id>/split_types")
@login_required
def get_all_image_split_values(project_id):
    split_types = data_pool_controller.get_all_split_types_for_project(project_id = project_id)

    data = {
        "split_types": [split_type.as_dict() for split_type in split_types]
    }

    return jsonify(data)

"""
Get all Modalities of a project
"""
@data_pool_service.route("/project/<int:project_id>/modalities")
@login_required
def get_modalities_of_project(project_id):

    modalities = data_pool_controller.get_all_modalities_for_project(project_id = project_id)

    data = {
        "modalities": [modality.as_dict() for modality in modalities]
    }

    return jsonify(data)

"""
Get all ContrastTypes of a project
"""
@data_pool_service.route("/project/<int:project_id>/contrast_types")
@login_required
def get_contrast_types_of_project(project_id):

    contrast_types = data_pool_controller.get_all_contrast_types_for_project(project_id = project_id)

    data = {
        "contrast_types": [contrast_type.as_dict() for contrast_type in contrast_types]
    }

    return jsonify(data)

"""
Get all entries of the DataPool tables according to the project, role and user
"""
@data_pool_service.route('/project/<int:project_id>/datatable', methods = ['POST'])
@project_user_required
def images_datatable(project_id):

    project = project_controller.find_project(id = project_id)
    
    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/case/image is not a valid project id"
        }, 400

    app.logger.info("images_datatable")
    # See https://datatables.net/manual/server-side for all included parameters

    if request.is_json:
        datatable_parameters = request.get_json()
    else:
        datatable_parameters = parse_multi_form(request.form)

    offset = int(datatable_parameters["start"])
    limit = int(datatable_parameters["length"])

    app.logger.info(f"Requested {offset} - {offset + limit}")

    # Build query
    query = db.session.query(Image)

    # only Images to requested project_id
    query = query.filter(Image.project_id == project_id)
    # Database JOIN on Manual Segmentation
    query = query.join(ManualSegmentation, Image.id == ManualSegmentation.image_id, isouter=True)
    # Database Outter JOIN Modality and ContrastType
    filter_query = query = query.join(Modality, isouter=True).join(ContrastType, isouter=True)

    # if the current user is only a user of the project, filter not-queued images and those, which are not assigned to him
    app.logger.info(f"User is at least reviewer in project: {is_project_reviewer(project)}")
     #The reviewer should be able to work as user
    if not is_project_reviewer(project) or 'type' in request.args and request.args.get('type') == "segmentation":
        filter_query = filter_query.filter((Image.status == StatusEnum.queued) | (ManualSegmentation.assignee_id == current_user.id))

    r = request

    # Add sorting
    order_by_directives = datatable_parameters["order"]

    # only take the first column we should order by
    first_order_by = order_by_directives[0]
    first_order_by_column_id = int(first_order_by["column"])
    first_order_by_dir = first_order_by["dir"]

    columns = datatable_parameters["columns"]
    
    first_oder_by_column = columns[first_order_by_column_id]
    first_oder_by_column_name = first_oder_by_column["data"]

    app.logger.info(f"Order by {first_oder_by_column_name} {first_order_by_dir}")

    sorting_direction = asc if first_order_by_dir == "asc" else desc


    fix_header_columns = { 'id': Image.id,'name': Image.name, 'name': Image.name, 'accession_number': Image.accession_number, 'status': Image.status, 'manual_segmentation.assigned_user': User.email, 'split_type': SplitType.name, 'body_region': Image.body_region, 'modality': Modality.name, 'contrast_type': ContrastType.name, 'series_name': Image.series_name, 'series_description': Image.series_description, 'series_number': Image.series_number, 'series_instance_uid': Image.series_instance_uid, 'patient_name':  Image.patient_name, 'patient_dob': Image.patient_dob, 'insert_date': Image.insert_date, 'last_updated': Image.last_updated, 'institution': Image.institution,
        'custom_1': Image.custom_1, 'custom_2': Image.custom_2, 'custom_3': Image.custom_3}
    #Ordering all Columns of fix_header_columns
    if first_oder_by_column_name in fix_header_columns:
        filter_query = filter_query.order_by(sorting_direction(fix_header_columns[first_oder_by_column_name]))

    # Searching
    searchable_columns = [Image.name, Image.patient_name, Modality.name, ContrastType.name, Image.accession_number]
    search_input = datatable_parameters["search"]["value"]
    if search_input != "":
        # Search in all searchable columns
        filters = [column.like(f"%{search_input}%") for column in searchable_columns]
        filter_query = filter_query.filter(or_(*filters))

    # Searching each column if filter set (Column filter head)
    for col_idx in columns:
        col = columns[col_idx]
        search_val = col['search']['value']
        if bool(col['searchable']) and search_val is not None and len(search_val) > 0:
            # Search in all searchable columns
            if col['data'] in fix_header_columns:
                db_col = fix_header_columns[col['data']]
                filters = [db_col.like(f"%{search_val}%")]
                filter_query = filter_query.filter(and_(*filters))
    
    # Searching each column with searchpanes filter (Column filter head)
    if 'searchPanes' in datatable_parameters:
        searchPanes_filter = datatable_parameters['searchPanes']
        for col_idx, col_filter_list in searchPanes_filter.items():
            # Search in all searchable columns
            if col_idx in fix_header_columns:
                db_col = fix_header_columns[col_idx]
                filters = [db_col.like(f"{col_filter_val}") for col_filter_idx,col_filter_val  in col_filter_list.items()]
                filter_query = filter_query.filter(or_(*filters))

    
    # Calculate the searchpanes
    db_searchpanes = db_results_to_searchpanes(query.all(), filter_query.all(), fix_header_columns)

    # Limit records
    records = filter_query.slice(offset, offset + limit).all()
    records_total = query.count()
    records_filtered = filter_query.count()

    # Also attach the project and its users of the project
    project_users = [user.as_dict() for user in current_project.users]

    # uncomment if options should be provided serverside for select fields
    # this has the issue in the edit dialog, that the current value is not preselected
    # see datatable_util.js and cases.html files for the frontend solution to this 
    # (loading select options from server and select the correct value on 'initEdit' call of Editor)

    #contrast_types_dict = [{'label': cm.name, 'value': cm.id} for cm in current_project.contrast_types]
    #modalities_dict = [{'label': m.name, 'value': m.id} for m in current_project.modalities]

    #status_dict = [{'label': s.value, 'value': s.name} for s in StatusEnum]
    #split_dict = [{'label': s.value, 'value': s.name} for s in SplitEnum]

    # TODO add values for these fields
    data = [record.as_dict() for record in records]
    for entry in data:
        # dummy fields for image / mask upload
        entry['upload_image'] = None
        entry['upload_mask'] = None
        entry['new_message'] = None

    response = {
        'draw': datatable_parameters["draw"],
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'project_users': project_users,
        'data': data,
        "searchPanes": db_searchpanes,
        # where is this options defined/documented?
        'options': {
            # 'contrast_type': contrast_types_dict,
            # 'modality': modalities_dict,
            # 'status': status_dict,
            # 'split': split_dict
        }
    }

    return jsonify(response)

"""
Endpoint to upload a new case or update an existing one (a nifti image)
"""
@data_pool_service.route('/project/<int:project_id>/case/image', methods=['POST'])
@login_required
@project_admin_required
def upload_case(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/case/image is not a valid project id"
        }, 400

    # app.logger.info(f"For field {request.__dict__}")

    update_case = False

    # Check if this upload is an update of an existing case
    if 'id' in request.form and request.form['id']:
        update_case = True
        image_id = request.form['id']

    app.logger.info(f"Uploaded files: {request.files}")

    # Make sure file is actually included
    if 'upload' not in request.files:
        flash('No file appended', category='error')
        return {
            'success': False,
            'error': "No image appended", 
            'message': "The HTTP POST Request needs to include a file named image in the appended files"
        }, 400

    # Make sure it is a valid nifti
    image_file = request.files['upload']
    try:
        fh = FileHolder(fileobj=GzipFile(fileobj=image_file, mode='rb'))
        image_nifti = Nifti1Image.from_file_map({'header': fh, 'image': fh})
    except:
        traceback.print_exc()
        flash('File is not a valid nifti', category='error')
        return {
            'success': False,
            'error': "No valid nifti file provided", 
            'message': "The uploaded file is not a valid nifti file"
        }, 400
    
    if update_case:
        image = data_pool_controller.find_image(id = image_id)
    else:
        # Create entry for db (with empty segmentation)
        image = data_pool_controller.create_image(project = project, name = image_file.filename)

    app.logger.info(f"Image: {image}")

    image_path = project.get_image_path(image_type = 'image', image_id = image.id)

    app.logger.info(f"Image path: {image_path}")

    if os.path.exists(image_path):
        # Override file
        os.remove(image_path)

    nibabel.save(image_nifti, image_path)

    # if not update_case:
    #     manual_segmentation = data_pool_controller.create_manual_segmentation(project = project, image_id = image.id)

    if image is not None:
        return {
            'success': True, 
            'upload': {'id': image.id},
            'files': {
                Image.__tablename__: {
                    f"{image.id}": image.as_dict()
                }
            }
        }, 200
    else:
        return {'success': False, 'error': "DB Image entry creation failed"}, 400

"""
Handling creation of metadata for cases/images (assignments etc.)
"""
@data_pool_service.route('/project/<int:project_id>/case', methods=['POST'])
@login_required
@project_admin_required
def create_case_meta_data(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400

    app.logger.info(f"Project {project.short_name}: Creating case meta data")

    case_meta_data = get_case_data_from_request(request)

    if case_meta_data is None:
        app.logger.info(f"Data in json? {request.json}")
        return {'success': False}, 400

    image = None

    # Find or create the image and segmentation object
    if 'upload_image' in case_meta_data and case_meta_data['upload_image']:
        image = data_pool_controller.find_image(id = case_meta_data['upload_image'])
    # else:
    #     image = data_pool_controller.create_image(project = project)
    #     manual_segmentation = data_pool_controller.create_manual_segmentation(project = project, image_id = image.id)

    if image is None:
        app.logger.info(f"Image provide? {request.json}")
        return {'success': False}, 400

    ### Updatew image object ###
    data_pool_controller.update_image_from_map(image, case_meta_data)

    return {
        'success': True,
        'data': image.as_dict()
    }, 200

"""
Handling changes of meta data for cases/images (assignments etc.)
"""
@data_pool_service.route('/project/<int:project_id>/case', methods=['PUT'])
@login_required
@project_user_required
def update_case_meta_data(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400

    case_ids = request.args.get('ids')

    if case_ids is None:
        return {
            'success': False,
            'error': "No valid case id(s) provided", 
            'message': "The case id provided in the url .../case?ids=CASE_ID1,CASE_ID2... is/are not valid case id(s)"
        }, 400


    update_case_meta_data = get_case_data_from_request(request)
    # update all specified cases
    for case_id in case_ids.split(','):

        app.logger.info(f"Project {project.short_name}: Updating case {case_id}")

        # Find the image and segmentation object
        image = data_pool_controller.find_image(id = case_id)
        old_status = image.status
        
        ### Updatew image object ###
        image = data_pool_controller.update_image_from_map(image, update_case_meta_data)

        if image.manual_segmentation is None:
            return {
                'success': False,
                'error': "No manual segmentation provided.", 
                'message': "Before you change the status of case {case_id}, upload a manual segmentation."
            }, 400

        manual_segmentation_old = data_pool_controller.find_manual_segmentation(id = image.manual_segmentation.id)

        ### Update manual segmentation ###
        manual_segmentation = data_pool_controller.update_manual_segmentation_from_map(manual_segmentation_old, update_case_meta_data)

        # Append messages
        if "new_message" in update_case_meta_data and len(update_case_meta_data["new_message"]) > 0:
            message = update_case_meta_data["new_message"]

            message = data_pool_controller.create_message(user = current_user, message = message, manual_segmentation = manual_segmentation)
            manual_segmentation.messages.append(message)

        # Assigned User
        if "assigned_user" in update_case_meta_data and image.status == StatusEnum.assigned:
            user_id = update_case_meta_data["assigned_user"]

            if user_id.isdigit() and not (manual_segmentation.assignee is not None and manual_segmentation.assignee.id == int(user_id)) :
                
                assigned_user = user_controller.find_user(user_id)
                
                # assign case to user
                data_pool_controller.assign_manual_segmentation(image = image, manual_segmentation = manual_segmentation, assignee = assigned_user)
        elif image.status == StatusEnum.created and old_status != StatusEnum.created:
            sys_message = data_pool_controller.create_system_message(user = current_user, message = "Created.", manual_segmentation= manual_segmentation)
            manual_segmentation.messages.append(sys_message)
        elif image.status == StatusEnum.queued and old_status != StatusEnum.queued:#if no user selected
            data_pool_controller.unclaim_manual_segmentation(image = image, manual_segmentation = manual_segmentation)
        elif image.status == StatusEnum.submitted and old_status != StatusEnum.submitted:
            data_pool_controller.submit_manual_segmentation(image = image, manual_segmentation = manual_segmentation)
        elif image.status == StatusEnum.rejected and old_status != StatusEnum.rejected:
            data_pool_controller.reject_manual_segmentation(image = image, manual_segmentation = manual_segmentation)
        elif image.status == StatusEnum.accepted and old_status != StatusEnum.accepted:
            data_pool_controller.accept_manual_segmentation(image = image, manual_segmentation = manual_segmentation)

        ### Commit image object ###
        data_pool_controller.update_manual_segmentation(manual_segmentation)
        ### Update image
        data_pool_controller.update_image(image)

    return {
        'success': True,
        'data': image.as_dict()
    }, 200

"""
Delete a case or multiple cases (delete image and segmentation data in project directory and from database)
"""
@data_pool_service.route('/project/<int:project_id>/case', methods=["DELETE"])
@login_required
@project_admin_required
def delete_case(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400
    
    case_ids = request.args.get('ids')

    if case_ids is None:
        return {
            'success': False,
            'error': "No valid case id(s) provided", 
            'message': "The case id provided in the url .../case?ids=CASE_ID1,CASE_ID2... is/are not valid case id(s)"
        }, 400

    # for all specified images
    for case_id in case_ids.split(','):
        app.logger.info(f"Project {project.short_name}: Deleting case {case_id}")

        image = data_pool_controller.find_image(id = case_id)

        if image is None:
            return {
                'success': False,
                'error': "No valid case id provided", 
                'message': "The case id provided in the url .../case/CASE_ID... is not a valid case id"
            }, 400

        # delete all actual nifti images
        raw_image_path = project.get_image_path(image_type = 'image', image_id = image.id)
        if os.path.exists(raw_image_path):
            os.remove(raw_image_path)

        manual_segmentation_image_path = project.get_image_path(image_type = 'manual_segmentation', image_id = image.id)
        if os.path.exists(manual_segmentation_image_path):
            os.remove(manual_segmentation_image_path)

        for segmentation_model in project.automatic_segmentation_models:
            automatic_segmentation_image_path = project.get_image_path(image_type = 'automatic_segmentation', 
                                                                        model_id = segmentation_model.id, 
                                                                        image_id = image.id)
            if os.path.exists(automatic_segmentation_image_path):
                os.remove(automatic_segmentation_image_path)
        
        # delete database object
        data_pool_controller.delete_image(image)

    return {'success': True}, 200


"""
Endpoint to upload a segmentation for a case (a nifti image)
"""
@data_pool_service.route('/project/<int:project_id>/case/segmentation', methods=['POST'])
@login_required
@project_user_required
def upload_segmentation(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/case/image is not a valid project id"
        }, 400

    image = None

    # Check if id is provided in form data, otherwise deny request
    if 'id' in request.form:
        case_id = request.form['id']
        image = data_pool_controller.find_image(id = case_id)

    if image is None:
        return {
            'success': False,
            'error': "No valid case id provided", 
            'message': "The case id provided in the url .../case/CASE_ID... is not a valid case id"
        }, 400

    app.logger.info(f"Uploaded files: {request.files}")

    # Make sure file is actually included
    if 'upload' not in request.files:
        flash('No file appended', category='error')
        return {
            'success': False,
            'error': "No image appended", 
            'message': "The HTTP POST Request needs to include a file named image in the appended files"
        }, 400

    # Make sure it is a valid nifti
    segmentation_image_file = request.files['upload']
    try:
        fh = FileHolder(fileobj=GzipFile(fileobj=segmentation_image_file, mode='rb'))
        segmentation_nifti = Nifti1Image.from_file_map({'header': fh, 'image': fh})
    except:
        traceback.print_exc()
        flash('File is not a valid nifti', category='error')
        return {
            'success': False,
            'error': "No valid nifti file provided", 
            'message': "The uploaded file is not a valid nifti file"
        }, 400

    # Make sure that sizes match
    image_path = project.get_image_path(image_type = 'image', image_id = image.id)

    image_nifti = nibabel.load(image_path)
    if image_nifti.shape[:-1] != segmentation_nifti.shape[:-1]:
        flash('Image dimensions do not match segmentation dimensions', category="error")
        return {
            'success': False,
            'error': "Dimension mismatch", 
            'message': "The uploaded nifti image dimension does not match the dimension of the case image"
        }, 400

    # Check which kind of segmentation has been uploaded, automatic or manual
    segmentation_type = request.args.get('type')

    if (segmentation_type == 'manual'):

        manual_segmentation = data_pool_controller.find_manual_segmentation(project_id = project.id, image_id = image.id)

        if manual_segmentation is None:
            manual_segmentation = data_pool_controller.create_manual_segmentation(project = project, image_id = image.id)

        image_path = project.get_image_path(image_type = 'manual_segmentation', image_id = manual_segmentation.id)

        if os.path.exists(image_path):
            app.logger.info(f"Old image already exists at {image_path}. Deleting and replacing by new one.")
            os.remove(image_path)

        nibabel.save(segmentation_nifti, image_path)

        data_pool_controller.update_manual_segmentation(manual_segmentation)

        # to display the filename in the frontend
        manual_segmentation_dict = manual_segmentation.as_dict()
        manual_segmentation_dict['name'] = image_path.split('/')[-1]

        return {
            'success': True, 
            'upload': {'id': manual_segmentation.id},
            'files': {
                ManualSegmentation.__tablename__: {
                    f"{manual_segmentation.id}": manual_segmentation_dict
                }
            }
        }, 200

        # SEGMENTATION UPLOAD
        # segmentation = ManualSegmentation(image=image, project=current_project)

    elif (segmentation_type == 'automatic'):
        # if automatic segmentation is uploaded, the model id needs to be given from which the segmentation was created
        model_id = request.args.get('model_id')

        model = None

        if model_id is not None:
            model = data_pool_controller.find_model(id = model_id)

        if model_id is None or model is None:
            return {
                'success': False,
                'error': "Automatic segmentation upload: No valid model id provided", 
                'message': "Via the URL provide the parameter model_id=XY where XY is a valid model id"
            }, 400

        # TODO store image as automatic segmentation

        automatic_segmentation = data_pool_controller.find_automatic_segmentation(image_id = image.id, model_id = model_id, project_id = project.id)

        if automatic_segmentation is None:
            automatic_segmentation = data_pool_controller.create_automatic_segmentation(project = project, image_id = image.id, model_id = model.id)

        image_path = project.get_image_path(image_type = 'automatic_segmentation', model_id = model.id, image_id = automatic_segmentation.id)

        if os.path.exists(image_path):
            app.logger.info(f"Old image already exists at {image_path}. Deleting and replacing by new one.")
            os.remove(image_path)

        nibabel.save(segmentation_nifti, image_path)

        # to display the filename in the frontend
        automatic_segmentation_dict = automatic_segmentation.as_dict()
        automatic_segmentation_dict['name'] = image_path.split('/')[-1]

        return {
            'success': True, 
            'upload': {'id': automatic_segmentation.id},
            'files': {
                AutomaticSegmentation.__tablename__: {
                    f"{automatic_segmentation.id}": automatic_segmentation_dict
                }
            }
        }, 200

    else:
        app.logger.error(f"Segmentation upload: {segmentation_type} is no supported segmentation type")
        return {
                'success': False,
                'error': "No valid segmentation type provided", 
                'message': "Valid segmentation types are 'manual', 'automatic'"
            }, 400



@data_pool_service.route('/project/<int:project_id>/case/<int:case_id>/upload_segmentation', methods=['POST'])
@login_required
def upload_case_segmentation(project_id, case_id):
    """
    Central endpoint to upload segmentations
    """

    # Make sure file is actually included
    if 'upload' not in request.files:
        flash('No file appended', category="error")
        return redirect(request.referrer)

        # Make sure it is a valid nifti
    segmentation_file = request.files["upload"]
    try:
        fh = FileHolder(fileobj=GzipFile(fileobj=segmentation_file, mode='rb'))
        segmentation_nifti = Nifti1Image.from_file_map({'header': fh, 'image': fh})
    except:
        traceback.print_exc()
        flash('File is not a valid nifti', category="error")
        return {'success': False}, 400

    # Make sure corresponding image exists
    image_name = request.headers["image_name"]
    image_path = os.path.join(app.config['DATA_PATH'], current_project.short_name, "images", image_name)

    if not os.path.exists(image_path):
        flash('No corresponding image found', category="error")
        return redirect(request.referrer)

    # Make sure that sizes match
    image_nifti = nibabel.load(image_path)
    if image_nifti.shape[:-1] != segmentation_nifti.shape[:-1]:
        flash('Image dimensions do not match segmentation dimensions', category="error")
        return redirect(request.referrer)

    # Update database
    image = db.session.query(Image).filter(Image.name == segmentation_file.filename).first()
    if image is None:
        flash('No corresponding image found', category="error")
        return redirect(request.referrer)
    segmentation = db.session.query(ManualSegmentation).filter(ManualSegmentation.image == image).first()
    if segmentation is None:
        segmentation = ManualSegmentation(project=current_project, image=image)
        db.session.add(segmentation)

    # Save file
    segmentation_path = os.path.join(app.config['DATA_PATH'], current_project.short_name, "manual_segmentations",
                                     segmentation_file.filename)
    nibabel.save(segmentation_nifti, segmentation_path)

    db.session.commit()
    return {'success': True}, 200

"""
Endpoint to update status, messages and mask of manual segmentation

Needs the post data:
user_id = INT
message = '' (optional)
"""
@data_pool_service.route('/project/<int:project_id>/case/<int:case_id>/review', methods=['PUT','POST'])
@login_required
@project_user_required
def assign_or_submit_or_review(project_id, case_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400

    image = data_pool_controller.find_image(id = case_id)
    manual_segmentation = image.manual_segmentation

    if image is None:
        return {
            'success': False,
            'error': "No valid case id provided", 
            'message': "The case id provided in the url .../case/ID... is not valid case id"
        }, 400

    user = current_user

    other_user_id = None
    message = None
    new_status = None

    # POST Parameter in json
    if request.json is not None:
        other_user_id = request.json['user_id']
        message = request.json['message']
    else:
        data = get_data_from_datatables_form(request)

        if 'status' in data:
            new_status = data['status']
            
        if 'new_message' in data:
            new_message = data['new_message']

            if new_message != '':
                message = new_message

    if other_user_id is not None:
        # check if user has the permission to do so
        if not is_project_reviewer(current_project):
            return {
                'success': False,
                'error': "Not permitted", 
                'message': "You are not permitted to assign the case to another user"
            }, 400
        
        user = user_controller.find_user(id = other_user_id)

        if user is None:
            return {
                'success': False,
                'error': "No valid user id provided",
            }, 400
    else:
        # check if user has the permission to do so
        if not is_project_user(current_project):
            return {
                'success': False,
                'error': "Not permitted", 
                'message': "You are not permitted to assign the case to another user"
            }, 400

    if image.status == StatusEnum.queued:
        # Case is meant to be assigned

        # assign case to user
        data_pool_controller.assign_manual_segmentation(image = image, manual_segmentation = manual_segmentation, assignee = user, message = message)

    elif image.status == StatusEnum.assigned or image.status == StatusEnum.rejected:
        # Case is meant to be submitted or unclaimed
        
        if new_status == StatusEnum.submitted.name:

            if message is not None:
                message = data_pool_controller.create_message(user = user, message = message, manual_segmentation = image.manual_segmentation)

            # submit case to reviewer
            data_pool_controller.submit_manual_segmentation(image = image, manual_segmentation = manual_segmentation, message = message)
            

        elif new_status == StatusEnum.queued.name:

            if message is not None:
                message = data_pool_controller.create_message(user = user, message = message, manual_segmentation = image.manual_segmentation)

            data_pool_controller.unclaim_manual_segmentation(image = image, manual_segmentation = image.manual_segmentation, message = message)
        elif new_status == StatusEnum.assigned.name:

            if message is not None:
                message = data_pool_controller.create_message(user = user, message = message, manual_segmentation = image.manual_segmentation)
                image.manual_segmentation.messages.append(message)

            data_pool_controller.update_manual_segmentation(image.manual_segmentation)

        else:
            return {
                'success': False,
                'error': "No valid action provided", 
                'message': "The manual segmentation is currently assigned, you can specify the actions 'submit' and 'unclaim' with /review?action='...'"
            }, 400
    elif image.status == StatusEnum.submitted:
        # Case is meant to be rejected or accepted

        if new_status == StatusEnum.rejected.name:
            if message is not None:
                message = data_pool_controller.create_message(user = user, message = message, manual_segmentation = image.manual_segmentation)

            # submit case to reviewer
            data_pool_controller.reject_manual_segmentation(image = image, manual_segmentation = manual_segmentation, message = message)
            

        elif new_status == StatusEnum.accepted.name:

            if message is not None:
                message = data_pool_controller.create_message(user = user, message = message, manual_segmentation = image.manual_segmentation)

            data_pool_controller.accept_manual_segmentation(image = image, manual_segmentation = image.manual_segmentation, message = message)
    
    ### Update image
    data_pool_controller.update_image(image)
    return {
        'success': True,
        'data': manual_segmentation.as_dict()
        }, 200

@data_pool_service.route('/project/<int:project_id>/case/<int:case_id>/send_message', methods=['GET'])
@login_required
@project_user_required
def message(project_id, case_id):
    """
    Handle new messages appended to segmentations
    """
    r = request
    manual_segmentation = db.session.query(ManualSegmentation).filter(ManualSegmentation.image_id == case_id).first()
    message = request.values["messageText"]
    message = Message(user=current_user, date=datetime.now(), message=message,
                      manual_segmentation=manual_segmentation, manual_segmentation_id=manual_segmentation.id)
    manual_segmentation.messages.append(message)
    db.session.commit()

    message = jsonify(message.as_dict())
    return message


"""
Central endpoint to download image data and segmentations, if available
"""
@data_pool_service.route('/project/<int:project_id>/case/<int:case_id>/download', methods=['GET'])
@login_required
@project_user_required
def download_case(project_id, case_id):
    # Retrieve image and project data
    
    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400

    image = data_pool_controller.find_image(id = case_id)
    manual_segmentation = image.manual_segmentation

    file_type = request.args.get('select')#image,manual_segmentation, automatic_segmentaion, archive
    
    if image is None:
        return {
            'success': False,
            'error': "No valid case id provided", 
            'message': "The case id provided in the url .../case/ID... is not valid case id"
        }, 400

    if file_type == "image":
        try:
            return flask.send_file(image.__get_fn__(), as_attachment=True)
        except FileNotFoundError:
            flask.abort(404)
    elif file_type == "manual_segmentation":
        try:
            return flask.send_file(image.manual_segmentation.__get_fn__(), as_attachment=True)
        except FileNotFoundError:
            flask.abort(404)
    elif file_type == "automatic_segmentaion":
        model_id = request.args.get('id')
        automatic_segmentation = data_pool_controller.find_automatic_segmentation(image_id = image.id, model_id = model_id, project_id = project.id)

        if automatic_segmentation is None:
            flask.abort(404)

        image_path = project.get_image_path(image_type = 'automatic_segmentation', model_id = model_id, image_id = image.id, create_dir = False)
        
        if not os.path.exists(image_path):
            flask.abort(404)
        try:
            return flask.send_file(image_path, as_attachment=True)
        except FileNotFoundError:
            flask.abort(404)
    elif file_type == "archive":
        # Create zip file
        data = io.BytesIO()
        with zipfile.ZipFile(data, mode='w') as z:
            z.write(image.__get_fn__(), 'image.nii.gz')

            if image.manual_segmentation != None:
                z.write(image.manual_segmentation.__get_fn__(), 'manual_segmentation.nii.gz')
        
            automatic_segmentations = data_pool_controller.find_automatic_segmentation(image_id = image.id, project_id = project.id)
            for automatic_segmentation in automatic_segmentations:
                image_path = project.get_image_path(image_type = 'automatic_segmentation', model_id = automatic_segmentation.model_id, image_id = image.id, create_dir = False)

                if os.path.exists(image_path):
                    z.write(image_path, f'automatic_segmentation_{automatic_segmentation.model_id}.nii.gz')

        data.seek(0)

        # Download file
        return flask.send_file(
            data,
            mimetype='application/zip',
            as_attachment=True,
            attachment_filename=f'{project.short_name}_case_{image.id}.zip'
        )
    else:
        abort(404)


"""
Get all automatic segmentation model of a project
"""
@data_pool_service.route('/project/<int:project_id>/models/datatable', methods = ['POST'])
@project_user_required
def models_datatable(project_id):

    project = project_controller.find_project(id = project_id)
    
    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/case/image is not a valid project id"
        }, 400

    case_id = request.args.get('case')

    # See https://datatables.net/manual/server-side for all included parameters
    if request.is_json:
        datatable_parameters = request.get_json()
    else:
        datatable_parameters = parse_multi_form(request.form)

    offset = int(datatable_parameters["start"])
    limit = int(datatable_parameters["length"])

    app.logger.info(f"Requested {offset} - {offset + limit}")

    # Build query
    query = db.session.query(AutomaticSegmentation).filter(AutomaticSegmentation.image_id == case_id).join(AutomaticSegmentationModel, isouter=True)

    # only Images to requested project_id
    filter_query = query.filter(AutomaticSegmentationModel.project_id == project_id)
    
    r = request
    
    # Add sorting
    order_by_directives = datatable_parameters["order"]

    # only take the first column we should order by
    first_order_by = order_by_directives[0]
    first_order_by_column_id = int(first_order_by["column"])
    first_order_by_dir = first_order_by["dir"]

    columns = datatable_parameters["columns"]

    first_oder_by_column = columns[first_order_by_column_id]
    first_oder_by_column_name = first_oder_by_column["name"]

    sorting_direction = asc if first_order_by_dir == "asc" else desc

    # Ordering only enabled for columns "status" and "name"
    if first_oder_by_column_name == "id":
        filter_query = filter_query.order_by(sorting_direction(AutomaticSegmentationModel.id))
    elif first_oder_by_column_name == "name":
        filter_query = filter_query.order_by(sorting_direction(AutomaticSegmentationModel.name))

    # Searching
    searchable_columns = [AutomaticSegmentationModel.name, AutomaticSegmentationModel.id]
    search_input = datatable_parameters["search"]["value"]
    if search_input != "":
        # Search in all searchable columns
        filters = [column.like(f"%{search_input}%") for column in searchable_columns]
        filter_query = filter_query.filter(or_(*filters))

    # Limit records
    records = filter_query.slice(offset, offset + limit).all()
    records_total = query.count()
    records_filtered = filter_query.count()

    if (len(records) > 0):
        app.logger.info(records[0].as_dict())

    data = [record.as_dict() for record in records]
    response = {
        'draw': datatable_parameters["draw"],
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
        'options': {
        }
    }

    return jsonify(response)

"""
Get all automatic segmentation model of a project
"""
@data_pool_service.route("/project/<int:project_id>/models")
@login_required
def get_automatic_segmentation_model_of_project(project_id):

    models = data_pool_controller.get_all_models_for_project(project_id = project_id)

    data = {
        "models": [model.as_dict() for model in models]
    }

    return jsonify(data)    


"""
Handling creation of metadata for model
"""
@data_pool_service.route('/project/<int:project_id>/model', methods=['POST'])
@login_required
@project_admin_required
def create_automatic_segmentation_model_data(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400

    model_meta_data = get_case_data_from_request(request)

    if model_meta_data is None:
        app.logger.info(f"Data in json? {request.json}")
        return {'success': False}, 400

    model = data_pool_controller.create_automatic_segmentation_model(project_id = project_id, name = model_meta_data['name'] )

    return {
        'success': True,
        'data': model.as_dict()
    }, 200

"""
Handling changes of meta data for model
"""
@data_pool_service.route('/project/<int:project_id>/model', methods=['PUT'])
@login_required
@project_user_required
def update_automatic_segmentation_model_data(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400

    model_ids = request.args.get('ids')

    if model_ids is None:
        return {
            'success': False,
            'error': "No valid model id(s) provided", 
            'message': "The model id provided in the url .../model?ids=MODEL_ID1,MODEL_ID2... is/are not valid model id(s)"
        }, 400

    
    update_model_data = get_case_data_from_request(request)

    # update all specified models
    for model_id in model_ids.split(','):

        # Find the model 
        model = data_pool_controller.find_automatic_segmentation_model(id = model_id)

        model.name = update_model_data['name']

        ### Update model object ###
        data_pool_controller.update_automatic_segmentation_model(model)

    return {
        'success': True,
        'data': model.as_dict()
    }, 200

"""
Delete a model or multiple models 
"""
@data_pool_service.route('/project/<int:project_id>/model', methods=["DELETE"])
@login_required
@project_admin_required
def delete_automatic_segmentation_model(project_id):

    project = project_controller.find_project(id = project_id)

    if project is None:
        return {
            'success': False,
            'error': "No valid project id provided", 
            'message': "The project id provided in the url /project/PROJECT_ID/... is not a valid project id"
        }, 400

    model_ids = request.args.get('ids')

    if model_ids is None:
        return {
            'success': False,
            'error': "No valid model id(s) provided", 
            'message': "The model id provided in the url .../model?ids=MODEL_ID1,MODEL_ID2... is/are not valid model id(s)"
        }, 400

    
    update_model_data = get_case_data_from_request(request)

    # update all specified models
    for model_id in model_ids.split(','):

         # Find the model 
        model = data_pool_controller.find_automatic_segmentation_model(id = model_id)

        # delete database object
        data_pool_controller.delete_automatic_segmentation_model(model)

    return {'success': True}, 200


"""
This should rather be done with accessor functions like here:
https://stackoverflow.com/questions/10434599/get-the-data-received-in-a-flask-request

request.form.get('id')
request.form.get('manual_segmentation') etc. etc.
"""
def get_case_data_from_request(request, id=None):

    # check, if the request is fired by a form or by ajax call
    is_form_request = hasattr(request, 'form')

    app.logger.info(f"From form: {is_form_request}")

    case_meta_data = None

    if (is_form_request):

        app.logger.info(f"Formdata: {request.form}")

        case_meta_data = {}

        # Parsing of the HTML form data into case_meta_data
        field_name_start_with_regex = r'data\[\d+\]'
        
        if id is not None:
            field_name_start_with_regex = r'data\['+id+r'\]'

        for field in request.form:
            matcher = re.search(field_name_start_with_regex, field)
            if matcher:
                start_index = len(matcher.group(0)) + 1
                field_name = field[start_index : -1]
                case_meta_data[field_name] = request.form[field]
        
    else:
        app.logger.info(f"JSON Content: {request.json}")

        # TODO

        case_meta_data = request.json

    app.logger.info(f"Meta Data: {case_meta_data}")

    return case_meta_data


"""
This function may receive a request from a datatables call and is able to retrieve all data and 
pack it into a dictionary 'data'
The request should have the layout:
([data[1232131][id], 2], [data[1232131][manual_segmentation][id], 3], ...)
And the resulting dict is:
{
    id: 2,
    manual_segmentation: {
        id: 3
    }, 
    
    etc.
}
"""
def get_data_from_datatables_form(request):
    # Parsing of the HTML form data into case_meta_data
    field_name_start_with_regex = r'data\[\d+\]'

    data = {}

    for field in request.form:
        # app.logger.info(f"{field}")

        matcher = re.search(field_name_start_with_regex, field)
        if matcher:
            start_index = len(matcher.group(0)) + 1
            field_name = field[start_index : -1]
            keys = field_name.split('][')

            nested = data
            for key in keys[:-1]:
                if key not in nested:
                    app.logger.info(f"{key} is a new Object?")
                    nested[key] = {}
                nested = nested[key]

            nested[keys[-1]] = request.form[field]

    # uncomment to print data formatted
    # app.logger.info(json.dumps(data, indent=4))

    return data

"""
This function receive the form data from a request and 
pack it into a dictionary
"""
def parse_multi_form(form):
    data = {}
    for url_k in form:
        v = form[url_k]
        ks = []
        while url_k:
            if '[' in url_k:
                k, r = url_k.split('[', 1)
                ks.append(k)
                if r[0] == ']':
                    ks.append('')
                url_k = r.replace(']', '', 1)
            else:
                ks.append(url_k)
                break
        sub_data = data
        for i, k in enumerate(ks):
            if k.isdigit():
                k = int(k)
            if i+1 < len(ks):
                if not isinstance(sub_data, dict):
                    break
                if k in sub_data:
                    sub_data = sub_data[k]
                else:
                    sub_data[k] = {}
                    sub_data = sub_data[k]
            else:
                if isinstance(sub_data, dict):
                    sub_data[k] = v

    return data