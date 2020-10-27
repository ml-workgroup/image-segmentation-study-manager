from os import listdir
from os.path import isfile, join
from wsgidav import compat, util
from wsgidav.util import join_uri
from wsgidav.dav_provider import DAVCollection
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

        # Retur a ISSMProjectCollection member wich list all case for the given user
        return ISSMProjectCollection(join_uri(self.path, name), self.environ, temp_project)



class ISSMProjectCollection(DAVCollection):
    """A collection, which lists all cases of a project, which are available for the user.
    """

    def __init__(self, path, environ, project):
        super(ISSMProjectCollection, self).__init__(path, environ)
        
        self.display_info = {"type":"Project"}
        self.project = project
        # Set the project path by the short_name 
        self.project_path = join_uri("/data", project['short_name'])
        #List all project case as member
        self.member_name_list = [str(f.replace(".nii.gz", "")).zfill(4)  for f in listdir(join_uri(self.project_path,"images")) if f.endswith("nii.gz") and isfile(join_uri(self.project_path,"images", f))]

    def get_display_info(self):
        return self.display_info

    def get_member_names(self):
        return self.member_name_list

    def prevent_locking(self):
        """Return True, since we don't want to lock virtual collections."""
        return True

    def get_member(self, name):
        # Create a CaseCollection for the given case_id (name)
        if name.isdigit():
            case_id = int(name)
            return CaseCollection(join_uri(self.path, str(case_id)), self.environ, self.project_path, case_id)
        else:
            return None


class CaseCollection(DAVCollection):
    """A collection, which lists all available images for a case."""

    def __init__(self, path, environ, project_path, case_id):
        DAVCollection.__init__(self, path, environ)

        self.display_info = {"type":"Case"}
        self.project_path = project_path
        self.case_id = case_id
        self.member_name_list = []

       
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
        return ISSMDAVNonCollection(join_uri(self.path, name), self.environ, image_path,name)
  