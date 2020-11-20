import json
import os

from datetime import datetime

from flask import current_app as app
from flask_login import current_user
from sqlalchemy import DateTime, Date

from app import db, current_project

from app.models.config import DATE_FORMAT, DATETIME_FORMAT
from app.models.project_models import Project, ProjectsUsers, ProjectsAdmins, ProjectsReviewers
from app.models.user_models import User
from app.models.data_pool_models import StatusEnum, SplitType, Image, ManualSegmentation, AutomaticSegmentation, AutomaticSegmentationModel, Message, Modality, ContrastType

# USER

def get_all_users_for_project(project_id = None):

    if project_id is None:
        return None

    users = User.query.join(ProjectsUsers, User.id == ProjectsUsers.user_id).filter(ProjectsUsers.project_id == project_id).all() + \
         User.query.join(ProjectsAdmins, User.id == ProjectsAdmins.user_id).filter(ProjectsAdmins.project_id == project_id).all() + \
         User.query.join(ProjectsReviewers, User.id == ProjectsReviewers.user_id).filter(ProjectsReviewers.project_id == project_id).all()
    
    return users

# END USER

# SPLIT_TYPE

def get_all_split_types_for_project(project_id = None):

    if project_id is None:
        return None

    split_types = SplitType.query.filter(SplitType.project_id == project_id).all()

    return split_types

"""
Finds an existing split type object in the database by it's id

If no id is provided, log's error and returns None
"""
def find_split_type(id = None, project_id = None, name = None):

    if id:
        split_type = SplitType.query.get(id)
    elif project_id is not None and name is not None:
        split_type = SplitType.query.filter(SplitType.project_id == project_id).filter(SplitType.name == name).first()
    else:
        app.logger.error("No parameters given for split type search")
        
        return None

    return split_type

"""
Creates a split type object with the given parameters
"""
def create_split_type(name = None, project_id = None):

    split_type = SplitType(name = name, project_id = project_id)

    db.session.add(split_type)
    db.session.commit()

    return split_type

"""
Deletes an existing split type object
"""
def delete_split_type(split_type):

    if split_type:
        db.session.delete(split_type)
        db.session.commit()

    return split_type

# END SPLIT_TYPE

# MODALITY

def get_all_modalities_for_project(project_id = None):

    if project_id is None:
        return None

    modalities = Modality.query.filter(Modality.project_id == project_id).all()

    return modalities

"""
Finds a Modality by it's id

If the id is not provided, logs error and returns None
"""
def find_modality(id = None, project_id = None, name = None):

    if id:
        modality = Modality.query.get(id)
    elif project_id is not None and name is not None:
        modality = Modality.query.filter(Modality.project_id == project_id).filter(Modality.name == name).first()
    else:
        app.logger.error("No parameters given for modality search")
        
        return None

    return modality

"""
Creates a new Modality object in the database with the given parameters
"""
def create_modality(name = None, project_id = None):

    modality = Modality(name = name, project_id = project_id)

    db.session.add(modality)
    db.session.commit()

    return modality

"""
Deletes a modality object
"""
def delete_modality(modality):

    if modality:
        db.session.delete(modality)
        db.session.commit()

    return modality

# END MODALITY

# CONTRAST_TYPE

def get_all_contrast_types_for_project(project_id = None):

    if project_id is None:
        return None

    contrast_types = ContrastType.query.filter(ContrastType.project_id == project_id).all()

    return contrast_types

"""
Finds an existing contrast type object in the database by it's id

If no id is provided, log's error and returns None
"""
def find_contrast_type(id = None, project_id = None, name = None):

    if id:
        contrast_type = ContrastType.query.get(id)
    elif project_id is not None and name is not None:
        contrast_type = ContrastType.query.filter(ContrastType.project_id == project_id).filter(ContrastType.name == name).first()
    else:
        app.logger.error("No parameters given for contrast type search")
        
        return None

    return contrast_type

"""
Creates a contrast type object with the given parameters
"""
def create_contrast_type(name = None, project_id = None):

    contrast_type = ContrastType(name = name, project_id = project_id)

    db.session.add(contrast_type)
    db.session.commit()

    return contrast_type

"""
Deletes an existing contrast type object
"""
def delete_contrast_type(contrast_type):

    if contrast_type:
        db.session.delete(contrast_type)
        db.session.commit()

    return contrast_type

# END CONTRAST_TYPE

# IMAGE

"""
Finds an Image by it's id

If the (datapool) id is not provided, logs error and returns None
"""
def find_image(id = None):

    if id:
        image = Image.query.get(id)
    else:
        app.logger.error("No parameters given for image search")
        
        return None

    return image

"""
Creates a new image instance in the database
"""
def create_image(project = None, name = None):

    if project is None:
        app.logger.error(f"The project for which the image should be stored is undefined")
        return None

    if name is None:
        name = f"{project.short_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M')}"

    image = Image(project = project, name = name)

    db.session.add(image)
    db.session.commit()

    return image

"""

"""
def update_image(image = None):

    if image:
        db.session.add(image)
        db.session.commit()

    return image

"""

"""
def update_image_from_map(image, meta_data):

    app.logger.info(f"Updating image from map")

    # Update values for image
    for column in Image.__table__.columns:
        column_name = column.name

        if column_name in meta_data:
            value = meta_data[column_name]
            
            # The field status should not be updated via this function
            if 'status' == column_name:
                status_dict = [statusEnum for statusEnum in StatusEnum if statusEnum.value == value]
                if len(status_dict):
                    value = status_dict[0]

            if column.primary_key:
                continue

            # e.g. the column ID is normally not nullable and therefore must not be overriden by None or <empty string>
            if not column.nullable and (value is None or not value):
                continue

            if not value:
                continue

            # Date parsing for date columns
            if type(column.type) == Date:
                value = datetime.strptime(value, DATE_FORMAT)
            elif type(column.type) == DateTime:
                value = datetime.strptime(value, DATETIME_FORMAT)

            setattr(image, column_name, value)
    
    # Contrast type and modality
    if "split_type" in meta_data:
        split_type = find_split_type(id = meta_data["split_type"])
        image.split_type = split_type

    # Contrast type and modality
    if "modality" in meta_data:
        modality = find_modality(id = meta_data["modality"])
        image.modality = modality

    if "contrast_type" in meta_data:
        contrast_type = find_contrast_type(id = meta_data["contrast_type"])
        image.contrast_type = contrast_type
    
    app.logger.info(f"image {image.as_dict()}")
    update_image(image)

    return image

"""

"""
def delete_image(image):

    if image:
        db.session.delete(image)
        db.session.commit()

        return True
    else:
        return False

# END IMAGE

# MANUAL SEGMENTATION

"""

"""
def find_manual_segmentation(id = None, image_id = None, project_id = None):

    if id:
        manual_segmentation = ManualSegmentation.query.get(id)
    elif image_id is not None and project_id is not None:
        manual_segmentation = ManualSegmentation.query.filter(ManualSegmentation.image_id == image_id).filter(ManualSegmentation.project_id == project_id).first()
    else:
        app.logger.error("No parameters given for manual segmentation search")
        return None

    return manual_segmentation

"""

"""
def create_manual_segmentation(project = None, image_id = None):

    if project is None:
        app.logger.error("No project given for which the manual segmentation should be created")
        return None

    if image_id is None:
        app.logger.error("No image id given for which the manual segmentation should be created")
        return None

    manual_segmentation = ManualSegmentation(project = project, image_id = image_id)

    db.session.add(manual_segmentation)
    db.session.commit()

    return manual_segmentation

"""

"""
def update_manual_segmentation(manual_segmentation):

    if manual_segmentation is None:
        app.logger.error("Manual segmentation is none, therefore can't be updated")
        return None

    manual_segmentation.last_updated = datetime.now()

    db.session.add(manual_segmentation)
    db.session.commit()

    return manual_segmentation

"""

"""
def update_manual_segmentation_from_map(manual_segmentation, meta_data):
    
    app.logger.info(f"Updating manual segmentation from map")

    # Update values for segmentation
    for column in ManualSegmentation.__table__.columns:

        if column.name not in meta_data:
            continue

        # app.logger.info(f"{column.name} of update data is {meta_data[column.name]}")
        
        value = meta_data[column.name]

        if column.primary_key:
            continue

        # e.g. the column ID is normally not nullable and therefore must not be overriden by None or <empty string>
        if not column.nullable and (value is None or not value):
            continue

        if not value:
            value = None

        # Date parsing for date columns
        if type(column.type) == Date:
            value = datetime.strptime(value, DATE_FORMAT)
        if type(column.type) == DateTime:
            value = datetime.strptime(value, DATETIME_FORMAT)

        setattr(manual_segmentation, column.name, value)

    return update_manual_segmentation(manual_segmentation)

def assign_manual_segmentation(image = None, manual_segmentation = None, assignee = None, message = None):
    
    if manual_segmentation is None:
        app.logger.error("No manual segmentation provided")
        return None

    if assignee is None:
        app.logger.error("No assignee provided")
        return None
        
    # Append system message
    sys_message = create_system_message(user = assignee, message = "Assign.", manual_segmentation= manual_segmentation)
    manual_segmentation.messages.append(sys_message)

    image.status = StatusEnum.assigned
    manual_segmentation.assignee = assignee
    manual_segmentation.assignee_date = datetime.now()

    if message is not None:
        manual_segmentation.messages.append(message)

    return update_manual_segmentation(manual_segmentation)

def unclaim_manual_segmentation(image = None, manual_segmentation = None, message = None):

    if manual_segmentation is None:
        app.logger.error("No manual segmentation provided")
        return None

    # Append system message
    status = "Queued."
    message_user = current_user
    if manual_segmentation.assignee is not None:
        status = 'Unclaimed.'
        message_user = manual_segmentation.assignee

    sys_message = create_system_message(user = message_user, message = status, manual_segmentation= manual_segmentation)
    manual_segmentation.messages.append(sys_message)

    image.status = StatusEnum.queued
    manual_segmentation.assignee = None
    manual_segmentation.assignee_date = None

    if message is not None:
        app.logger.info(f"Messages: {manual_segmentation.messages} {message}")
        manual_segmentation.messages.append(message)

    return update_manual_segmentation(manual_segmentation)

def submit_manual_segmentation(image = None, manual_segmentation = None, message = None):
    
    if manual_segmentation is None:
        app.logger.error("No manual segmentation provided")
        return None

    # Append system message
    sys_message = create_system_message(user = current_user, message = "Submit.", manual_segmentation= manual_segmentation)
    manual_segmentation.messages.append(sys_message)

    image.status = StatusEnum.submitted

    if message is not None:
        manual_segmentation.messages.append(message)

    return update_manual_segmentation(manual_segmentation)


def reject_manual_segmentation(image = None, manual_segmentation = None, message = None):
    
    if manual_segmentation is None:
        app.logger.error("No manual segmentation provided")
        return None
    
    # Append system message
    sys_message = create_system_message(user = current_user, message = "Rejected.", manual_segmentation= manual_segmentation)
    manual_segmentation.messages.append(sys_message)

    image.status = StatusEnum.rejected

    if message is not None:
        manual_segmentation.messages.append(message)

    return update_manual_segmentation(manual_segmentation)

def accept_manual_segmentation(image = None, manual_segmentation = None, message = None):
    
    if manual_segmentation is None:
        app.logger.error("No manual segmentation provided")
        return None
        
    # Append system message
    sys_message = create_system_message(user = current_user, message = "Accepted.", manual_segmentation= manual_segmentation)
    manual_segmentation.messages.append(sys_message)

    image.status = StatusEnum.accepted

    if message is not None:
        manual_segmentation.messages.append(message)

    return update_manual_segmentation(manual_segmentation)

# END MANUAL SEGMENTATION

# MESSAGES

def get_all_messages_for_manual_segmentation(manual_segmentation_id = None):

    if manual_segmentation_id is None:
        return None

    messages = Message.query.filter(Message.manual_segmentation_id == manual_segmentation_id).all()

    return messages

"""

"""
def create_message(user = None, message = None, manual_segmentation = None):

    message = Message(user = user, date = datetime.now(), message = message, manual_segmentation = manual_segmentation)

    db.session.add(message)
    db.session.commit()

    return message

def create_system_message(user = None, message = None, manual_segmentation = None):

    message = Message(user = user, date = datetime.now(), message = ("**sys**" + message), manual_segmentation = manual_segmentation)

    db.session.add(message)
    db.session.commit()

    return message

# END MESSAGES

# AUTOMATIC SEGMENTATION MODEL

def get_all_models_for_project(project_id = None):

    if project_id is None:
        return None

    models = AutomaticSegmentationModel.query.filter(AutomaticSegmentationModel.project_id == project_id).all()

    return models


"""

"""
def find_automatic_segmentation_model(id = None):

    if id:
        automatic_segmentation_model = AutomaticSegmentationModel.query.get(id)
    else:
        app.logger.error("No parameters given for automatic segmentation model search")
        return None

    return automatic_segmentation_model

"""

"""
def create_automatic_segmentation_model(project_id = None, name = None):

    if project_id is None:
        app.logger.error("No project id provided for automatic segmentation model")
        return None

    automatic_segmentation_model = AutomaticSegmentationModel(project_id = project_id, name = name)

    db.session.add(automatic_segmentation_model)
    db.session.commit()

    return automatic_segmentation_model

def update_automatic_segmentation_model(automatic_segmentation_model):

    db.session.add(automatic_segmentation_model)
    db.session.commit()

    return automatic_segmentation_model

def delete_automatic_segmentation_model(automatic_segmentation_model):

    if automatic_segmentation_model is None:
        app.logger.error("Provided automatic segmentation model is None. Can't delete.")
        return False

    db.session.delete(automatic_segmentation_model)
    db.session.commit()

    return True

# END AUTOMATIC SEGMENTATION MODEL

# AUTOMATIC SEGMENTATION

"""

"""
def find_automatic_segmentation(id = None, image_id = None, model_id = None, project_id = None):

    if id:
        automatic_segmentation = AutomaticSegmentation.query.get(id)
    elif image_id is not None and model_id is not None and project_id is not None:
        automatic_segmentation = AutomaticSegmentation.query.filter(AutomaticSegmentation.image_id == image_id).filter(AutomaticSegmentation.model_id == model_id).filter(AutomaticSegmentation.project_id == project_id).first()
    elif image_id is not None and project_id is not None:
        automatic_segmentation = AutomaticSegmentation.query.filter(AutomaticSegmentation.image_id == image_id).filter(AutomaticSegmentation.project_id == project_id)
    else:
        app.logger.error("No parameters given for automatic segmentation search")
        
        return None

    return automatic_segmentation

"""

"""
def create_automatic_segmentation(project = None, image_id = None, model_id = None):

    if project is None:
        app.logger.error("No project given for which the manual segmentation should be created")
        return None

    if image_id is None:
        app.logger.error("No image id given for which the automatic segmentation should be created")
        return None

    if model_id is None:
        app.logger.error("No model id given for which the automatic segmentation should be created")
        return None

    automatic_segmentation = AutomaticSegmentation(project = project, image_id = image_id, model_id = model_id)

    db.session.add(automatic_segmentation)
    db.session.commit()

    return automatic_segmentation

"""

"""
def update_automatic_segmentation(automatic_segmentation):

    if automatic_segmentation is None:
        app.logger.error("Automatic segmentation is none, therefore can't be updated")
        return None

    db.session.add(automatic_segmentation)
    db.session.commit()

    return automatic_segmentation

"""

"""
def delete_automatic_segmentation(automatic_segmentation):

    if automatic_segmentation is None:
        app.logger.error("Automatic segmentation is none, therefore can't be deleted")
        return False

    db.session.delete(automatic_segmentation)
    db.session.commit()

    return True

# END AUTOMATIC SEGMENTATION