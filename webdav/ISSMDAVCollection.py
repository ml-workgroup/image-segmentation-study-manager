from os import listdir
import os
from os.path import isfile, join
from wsgidav import compat, util
from wsgidav.util import join_uri
from wsgidav.dav_provider import DAVCollection
from datetime import datetime
from .ISSMUtils import *
from .ISSMDAVNonCollection import ISSMDAVNonCollection


class ISSMRootCollection(DAVCollection):
    """A collection that represents the available projects of a user.
    The class is used as a root collection.
    """

    def __init__(self, path, environ, projects):
        super(ISSMRootCollection, self).__init__(path, environ)
        
        self.display_info = {"type":"Root"}
        self.member_name_list = [f['short_name'] for f in environ["wsgidav.auth.projects"]]
        self.projects = projects
        self.environ = environ
        
    def get_display_info(self):
        return self.display_info

    def get_member_names(self):
        return self.member_name_list

    def prevent_locking(self):
        """Return True, since we don't want to lock virtual collections."""
        return True

    def get_member(self, name):
        # Find all available projects by project_name (should be unique)
        filtered_projects = list(filter(lambda item: item['short_name'] == name,self.environ["wsgidav.auth.projects"]))
        temp_project = None
        if len(filtered_projects) >= 1:
            temp_project = filtered_projects[0]
        else:
            return None

        # Retur a ISSMProjectCollection member wich list all case for the given user
        return ISSMProjectCollection(join_uri(self.path, name), self.environ, temp_project)



class ISSMProjectCollection(DAVCollection):
    """A collection, which lists all roles of a project, which are available for the user.
    """

    def __init__(self, path, environ, project):
        super(ISSMProjectCollection, self).__init__(path, environ)
        self.display_info = {"type":"Project"}
        self.project = project

        #List all available roles for this member
        self.member_name_list = []

        if 'role' in project:
            role = project['role']

            # append current role
            self.member_name_list.append(role)

            if role == 'review':
                self.member_name_list.append('segmentation')
            elif role == 'administration':
                self.member_name_list.append('segmentation')
                self.member_name_list.append('review')
        

    def get_display_info(self):
        return self.display_info

    def get_member_names(self):
        return self.member_name_list

    def prevent_locking(self):
        """Return True, since we don't want to lock virtual collections."""
        return True

    def get_member(self, name):
        # Create a ISSMRoleCollection for the given rolename (name)
        #Check role access
        if name not in self.member_name_list:
            return None
            
        return ISSMRoleCollection(join_uri(self.path, name), self.environ, self.project, name)

class ISSMRoleCollection(DAVCollection):
    """A collection, which lists all case filter of a project, which are available for the user.
    """

    def __init__(self, path, environ, project, role_name):
        super(ISSMRoleCollection, self).__init__(path, environ)
        
        self.display_info = {"type":"Role"}
        self.project = project
        self.role_name = role_name
        #List all available filter for this member
        self.member_name_list = []
        
        if role_name == 'administration':
            self.member_name_list.append('all')
            #Only in Role list
            self.member_name_list.append('upload')
        elif role_name == 'review':
            self.member_name_list.append('all')
            self.member_name_list.append('to_review')
        elif role_name == 'segmentation':
            self.member_name_list.append('all')
            self.member_name_list.append('todo')
            self.member_name_list.append('queued')

    def get_display_info(self):
        return self.display_info

    def get_member_names(self):
        return self.member_name_list

    def prevent_locking(self):
        """Return True, since we don't want to lock virtual collections."""
        return True

    def get_member(self, name):
        # Create a ISSMCaseFilterCollection for the given by name
        #Check filter access
        if name not in self.member_name_list:
            return None

        if name in ['all', 'to_review', 'todo', 'queued']:
            return ISSMCaseFilterCollection(join_uri(self.path, name), self.environ, self.role_name, name, self.project)
        elif name in ['upload']:
            return ISSMFunctionCollection(join_uri(self.path, name), self.environ, self.role_name, name, self.project, None)


class ISSMCaseFilterCollection(DAVCollection):
    """A collection, which lists all cases of a project, which are available for the user.
    """

    def __init__(self, path, environ, role_name, name, project):
        super(ISSMCaseFilterCollection, self).__init__(path, environ)
        
        # Download the case for this collection depending on the collection name.
        filtername = name
        if filtername == 'to_review':
            filtername = "review"
        elif filtername == 'todo':
            filtername = "assign"

        self.display_info = {"type":"Filter"}
        self.project = project
        self.role_name = role_name
        self.members = None
        self.filter_name = filtername

        # Set the project path by the short_name 
        self.project_path = join_uri("/data", project['short_name'])

    def load_members(self):
        if self.members is None:
            response_data = get_data_from_issm_api('/project/' + str(self.project['id']) + '/case/' + self.filter_name, self.environ["wsgidav.auth.user"])

            if response_data['success']:
                self.members = response_data['data']
        return self.members

    def get_display_info(self):
        return self.display_info

    def get_member_names(self):
        # List all project case as member
        self.load_members()
        
        if self.members is not None:
            return [case['name']  for case in self.members]
        else:
            return None
    
    def prevent_locking(self):
        """Return True, since we don't want to lock virtual collections."""

        return True

    def get_member(self, name):
        self.load_members()
        
        if self.members is None:
            return None

        # Find the case to the image
        target_case = None
        for case in self.members:
            if case['name'] == name:
                target_case = case
                break

        # Create a ISSMCaseCollection for the given case_id (name)
        if target_case is not None:
            return ISSMCaseCollection(join_uri(self.path, target_case['name']), self.environ, self.role_name, self.project_path, self.project, target_case)
        else:
            return None

class ISSMFunctionCollection(DAVCollection):
    """A collection, which lists all cases of a project, which are available for the user.
    """
    

    def __init__(self, path, environ, role_name, name, project, case):
        super(ISSMFunctionCollection, self).__init__(path, environ)

        self.display_info = {"type":"Function"}
        self.name = name
        self.project = project
        self.case = case
        self.member_name_list = []
        self.function_path =  "/data/"

        tempfile_item = self.environ['wsgidav.filehandler'].getTempFileItem(self.path, self.environ['wsgidav.auth.user'])
        
        if tempfile_item is not None:
            self.member_name_list = [tempfile_item['name']]
        # if self.name == "upload":
        #     self.member_name_list = [f for f in listdir(self.function_path) if isfile(join(self.function_path, f))]

    def getCurrentFile(self):
        cur_path = self.path
        cfile_path = self.environ['wsgidav.filehandler'].getTempFile(cur_path, self.environ['wsgidav.auth.user'])
        if cfile_path is None:
            cfile_path = self.environ['wsgidav.filehandler'].newTempFile(cur_path, self.environ['wsgidav.auth.user'])
        return cfile_path

    def getContentLanguage(self):
        return None

    def get_display_info(self):
        return self.display_info

    def get_member_names(self):
        return self.member_name_list

    def prevent_locking(self):
        """Return True, since we don't want to lock virtual collections."""
        return True

    def get_member(self, name):
        if name not in self.member_name_list:
            return None

        tempfile_path = self.environ['wsgidav.filehandler'].getTempFile(self.path, self.environ['wsgidav.auth.user'])

        if tempfile_path is None:
            return None

        return ISSMDAVNonCollection(join_uri(self.path, name), self.environ, tempfile_path, name, self.project, self.case)    
        
    def create_empty_resource(self, name):
        """Create and return an empty (length-0) resource as member of self.
        Called for LOCK requests on unmapped URLs.
        Preconditions (to be ensured by caller):
          - this must be a collection
          - <self.path + name> must not exist
          - there must be no conflicting locks
        Returns a DAVResuource.
        This method MUST be implemented by all providers that support write
        access.
        This default implementation simply raises HTTP_FORBIDDEN.
        """

        print(f"create_empty_resource")

        cur_path = self.path
        cfile_path = self.environ['wsgidav.filehandler'].getTempFile(cur_path,self.environ['wsgidav.auth.user'])
        
        if cfile_path is not None:
            return ISSMDAVNonCollection(join_uri(self.path, name), self.environ, cfile_path, name, self.project, self.case)

        if (self.name == "upload" or self.name == "submit_segmentation") and cfile_path is None:
            if cfile_path is None:
                cfile_path = self.environ['wsgidav.filehandler'].newTempFile(cur_path,self.environ['wsgidav.auth.user'], name)
            
            self.environ['wsgidav.filehandler'].addInformationToTempFile(cur_path,self.environ['wsgidav.auth.user'],{
                'project_id':  self.project['id'],
                'case_id': self.case['id'],
                'user': self.environ['wsgidav.auth.user']
            })

            return ISSMDAVNonCollection(join_uri(self.path, name), self.environ, cfile_path, name, self.project, self.case)
        elif self.case is not None:
            result_state = perform_function(self.name, self.project['id'], self.case['id'], self.environ["wsgidav.auth.user"])

            if result_state:
                if cfile_path is None:
                    cfile_path = self.environ['wsgidav.filehandler'].newTempFile(cur_path,self.environ['wsgidav.auth.user'], name)
                return ISSMDAVNonCollection(join_uri(self.path, name), self.environ, cfile_path, name, self.project, self.case)
            
        raise DAVError(HTTP_FORBIDDEN)

    # def handle_delete(self):
    #     print(f"handle_delete")
    #     return False
    #     """Change semantic of DELETE to remove resource tags."""
    #     # DELETE is only supported for the '/by_tag/' collection
    #     if "/by_tag/" not in self.path:
    #         raise DAVError(HTTP_FORBIDDEN)
    #     # path must be '/by_tag/<tag>/<resname>'
    #     catType, tag, _rest = util.save_split(self.path.strip("/"), "/", 2)
    #     assert catType == "by_tag"
    #     assert tag in self.data["tags"]
    #     self.data["tags"].remove(tag)
    #     return True  # OK

    # def handle_copy(self, dest_path, depth_infinity):
    #     print(f"handle_copy")
    #     return False
    #     """Change semantic of COPY to add resource tags."""
    #     # destPath must be '/by_tag/<tag>/<resname>'
    #     if "/by_tag/" not in dest_path:
    #         raise DAVError(HTTP_FORBIDDEN)
    #     catType, tag, _rest = util.save_split(dest_path.strip("/"), "/", 2)
    #     assert catType == "by_tag"
    #     if tag not in self.data["tags"]:
    #         self.data["tags"].append(tag)
    #     return True  # OK

    # def handle_move(self, dest_path):
    #     print(f"handle_move")
    #     return False
    #     """Change semantic of MOVE to change resource tags."""
    #     # path and destPath must be '/by_tag/<tag>/<resname>'
    #     if "/by_tag/" not in self.path:
    #         raise DAVError(HTTP_FORBIDDEN)
    #     if "/by_tag/" not in dest_path:
    #         raise DAVError(HTTP_FORBIDDEN)
    #     catType, tag, _rest = util.save_split(self.path.strip("/"), "/", 2)
    #     assert catType == "by_tag"
    #     assert tag in self.data["tags"]
    #     self.data["tags"].remove(tag)
    #     catType, tag, _rest = util.save_split(dest_path.strip("/"), "/", 2)
    #     assert catType == "by_tag"
    #     if tag not in self.data["tags"]:
    #         self.data["tags"].append(tag)
    #     return True  # OK


    # def set_property_value(self, name, value, dry_run=False):
    #     print(f"set_property_value")
    #     return None
    #     """Set or remove property value.
    #     See DAVResource.set_property_value()
    #     """
    #     if value is None:
    #         # We can never remove properties
    #         raise DAVError(HTTP_FORBIDDEN)
    #     if name == "{virtres:}tags":
    #         # value is of type etree.Element
    #         self.data["tags"] = value.text.split(",")
    #     elif name == "{virtres:}description":
    #         # value is of type etree.Element
    #         self.data["description"] = value.text
    #     elif name in VirtualResource._supportedProps:
    #         # Supported property, but read-only
    #         raise DAVError(
    #             HTTP_FORBIDDEN, err_condition=PRECONDITION_CODE_ProtectedProperty
    #         )
    #     else:
    #         # Unsupported property
    #         raise DAVError(HTTP_FORBIDDEN)
    #     # Write OK
    #     return

    # def create_collection(self, name):
    #     """Create a new collection as member of self.
    #     Preconditions (to be ensured by caller):
    #       - this must be a collection
    #       - <self.path + name> must not exist
    #       - there must be no conflicting locks
    #     This method MUST be implemented by all providers that support write
    #     access.
    #     This default implementation raises HTTP_FORBIDDEN.
    #     """
        
    #     print(f"create_collection")
    #     assert self.is_collection
    #     raise DAVError(HTTP_FORBIDDEN)

class ISSMCaseCollection(DAVCollection):
    """A collection, which lists all available images for a case."""

    def __init__(self, path, environ, role_name, project_path, project, case):
        super(ISSMCaseCollection, self).__init__(path, environ)

        self.display_info = {"type":"Case"}
        self.project_path = project_path
        self.role_name = role_name
        self.project = project
        self.case = case
        self.case_id = case['id']
        self.member_name_list = []

        
        if role_name == 'administration':
            #Only in all
            self.member_name_list.append('delete_all_operations')
            self.member_name_list.append('duplicate_item')
        elif role_name == 'review':
            #Only for cases to review
            self.member_name_list.append('accept')
            self.member_name_list.append('reject')
        elif role_name == 'segmentation':
            #Only for queued
            if case['status'] == "Queued" and case['assignee_id'] != self.environ["wsgidav.auth.user"]['id']:
                self.member_name_list.append('assign_to_myself')
                
            #Only for todo
            if case['assignee_id']  == self.environ["wsgidav.auth.user"]['id']:
                self.member_name_list.append('submit_segmentation')

       
        #Search all stored images for the given case id
        if isfile(join_uri(self.project_path, "images","{}.nii.gz".format(self.case_id))):
            self.member_name_list.append("Image.nii.gz")
        if isfile(join_uri(self.project_path, "manual_segmentations","{}.nii.gz".format(self.case_id))):
            self.member_name_list.append("Manual Segmentation.nii.gz")
        
        # Search for stored auttomatic segementaion models
        for model in listdir(join_uri(self.project_path,"automatic_segmentation")):
            model_id = model.replace("model_", "")
            if str(model_id).isdigit() and isfile(join_uri(self.project_path, "automatic_segmentation","{}/{}.nii.gz".format(model, self.case_id))):
                self.member_name_list.append("Automatic Segmentation {}.nii.gz".format(model_id))

    def get_display_info(self):
        return self.display_info

    def get_member_names(self):
        return self.member_name_list

    def get_member(self, name):
        #Check filter access
        if name not in self.member_name_list:
            return None
        if name in ['delete_all_operations', 'duplicate_item', 'accept', 'reject', 'assign_to_myself', 'submit_segmentation']:
            return ISSMFunctionCollection(join_uri(self.path, name), self.environ, self.role_name, name, self.project, self.case)

        image_path = None
        temp_name = name.replace(".nii.gz", "")

        # Find the type of the member (images, manual_segmentations or automatic_segmentation)
        if temp_name.startswith("Image"):
            image_path = "images"
        elif temp_name.startswith("Manual Segmentation"):
            image_path = "manual_segmentations"
        elif temp_name.startswith("Automatic Segmentation"):
            model_id = temp_name.replace("Automatic Segmentation", "")
            image_path = "automatic_segmentation/model_{}".format(int(model_id))


        if image_path is None:
            return None
        
        # Build the dest image path
        image_path = join_uri(self.project_path, image_path, "{}.nii.gz".format(self.case_id))
        
        # Create a non collection item wich represents the image.
        return ISSMDAVNonCollection(join_uri(self.path, name), self.environ, image_path, name, self.project, self.case)
  