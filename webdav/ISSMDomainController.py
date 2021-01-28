import requests
import os 
from datetime import *
from .ISSMUtils import *
from wsgidav.dc.base_dc import BaseDomainController

class ISSMDomainController(BaseDomainController):
    # Cached user
    user_list = []

    def __init__(self, wsgidav_app, config):
        super(ISSMDomainController, self).__init__(wsgidav_app, config)
        return

    def __str__(self):
        return "{}()".format(self.__class__.__name__)

    def get_domain_realm(self, path_info, environ):
        """Resolve a relative url to the appropriate realm name."""
        realm = self._calc_realm_from_path_provider(path_info, environ)
        return realm

    def require_authentication(self, realm, environ):
        """Return True if this realm requires authentication (grant anonymous access otherwise)."""       
        return True

    def get_user_data_by_password(self, user_name, password):
        """ First search cached user """
        cached_user = None
        cached_user_list  = list(filter(lambda s: s['data']['user']['email'] == user_name and s['data']['user']['password'] == password, self.user_list))

        """ Load users from Flask app, if not available or outdated """
        if cached_user_list is None or len(cached_user_list) != 1 or cached_user_list[0]['data']['last_update'] + timedelta(minutes = 5) <= datetime.now():
            # Remove user from cache
            for item in cached_user_list:
                self.user_list.remove(item)

            r = requests.post(ISSM_API_URL + '/user/info', data={"user_name": user_name, "password": password})
            cached_user = r.json()
            if  cached_user is not None and cached_user['success']:
                cached_user['data']['user']['password'] = password
                cached_user['data']['last_update'] = datetime.now()

                self.user_list.append(cached_user)
            else:
                cached_user = None
        else:
            cached_user = cached_user_list[0]

        return cached_user
    
    def basic_auth_user(self, realm, user_name, password, environ):
        """Returns True if this user_name/password pair is valid for the realm,
        False otherwise. Used for basic authentication."""
        # Load user by user_name and password from the flask app
        user_data = self.get_user_data_by_password(user_name, password)
        
        # if the user is vaild continue
        if user_data is None or not user_data['success']:
            return False
        
        for project in user_data['data']['projects_admin']:
            project['role'] = 'administration'
        for project in user_data['data']['projects_reviewer']:
            project['role'] = 'review'
        for project in user_data['data']['projects_user']:
            project['role'] = 'segmentation'

        # Save the user item and all user projects to environ
        environ["wsgidav.auth.user"] = user_data['data']['user']
        environ["wsgidav.auth.projects"] = user_data['data']['projects_admin'] + user_data['data']['projects_reviewer'] + user_data['data']['projects_user']

        if environ is None:
            return True  

        # Split the requested path into parts. For checking access
        path = ["/" + part for part in environ.get("PATH_INFO").split("/")]
        
        # Only if root path '/' (allways vaild rout for verified user)
        project_name = path[0]
        if project_name.endswith("/"):
            return True

        # Get current project name and guess users role
        project_name = project_name[1:] 
        project_admin = list(filter(lambda x: 'short_name' in x and x['short_name'] == project_name, user_data['data']['projects_admin']))
        project_reviewer = list(filter(lambda x: 'short_name' in x and x['short_name'] == project_name, user_data['data']['projects_reviewer']))
        project_user = list(filter(lambda x: 'short_name' in x and x['short_name'] == project_name, user_data['data']['projects_user']))
        
        if len(project_admin) == 1:
            environ["wsgidav.auth.role"] = "admin"
            environ["wsgidav.auth.project"] = project_admin[0]
        elif len(project_reviewer) == 1:
            environ["wsgidav.auth.role"] = "reviewer"
            environ["wsgidav.auth.project"] = project_reviewer[0]
        elif len(project_user) == 1:
            environ["wsgidav.auth.role"] = "user"
            environ["wsgidav.auth.project"] = project_user[0]
        else:
            environ["wsgidav.auth.role"] = None
            environ["wsgidav.auth.project"] = None
            return False

        return True

    def supports_http_digest_auth(self):
        # We have access to a plaintext password (or stored hash)
        return False

    def digest_auth_user(self, realm, user_name, environ):
        """Computes digest hash A1 part."""
        return None
