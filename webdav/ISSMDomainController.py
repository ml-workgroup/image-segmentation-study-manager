import requests
from datetime import *
from wsgidav.dc.base_dc import BaseDomainController

class ISSMDomainController(BaseDomainController):
    user_list = []    

    def __init__(self, wsgidav_app, config):
        super(ISSMDomainController, self).__init__(wsgidav_app, config)
        return

    def __str__(self):
        print("__str__")
        return "{}()".format(self.__class__.__name__)

    def get_domain_realm(self, path_info, environ):
        """Resolve a relative url to the appropriate realm name."""
        realm = self._calc_realm_from_path_provider(path_info, environ)
        print("Realm: {}".format(realm))
        return realm

    def require_authentication(self, realm, environ):
        """Return True if this realm requires authentication (grant anonymous access otherwise)."""
        print("require_authentication")
       
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

            r = requests.post('http://localhost:5000/api/webdav/user/info', data={"user_name": user_name, "password": password})
            cached_user = r.json()
            cached_user['data']['user']['password'] = password
            cached_user['data']['last_update'] = datetime.now()

            self.user_list.append(cached_user)
        else:
            cached_user = cached_user_list[0]

        return cached_user
    
    def basic_auth_user(self, realm, user_name, password, environ):
        """Returns True if this user_name/password pair is valid for the realm,
        False otherwise. Used for basic authentication."""
        print("basic_auth_user")
        print("User : {} , Password : {}, Realm: {}".format(user_name,password,realm))

        user_data = self.get_user_data_by_password(user_name, password)

        print("{}".format(user_data))
        
        if user_data and user_data['success'] == True:
            return True
        return False

    def supports_http_digest_auth(self):
        # We have access to a plaintext password (or stored hash)
        print("supports_http_digest_auth")
        return False

    def digest_auth_user(self, realm, user_name, environ):
        """Computes digest hash A1 part."""
        print("digest_auth_user")
        return None