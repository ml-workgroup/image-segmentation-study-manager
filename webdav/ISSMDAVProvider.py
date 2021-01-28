import requests
from datetime import *
from pprint import pformat
from wsgidav import compat, util
from wsgidav.dav_provider import DAVCollection, DAVNonCollection, DAVProvider
from wsgidav.util import join_uri
from .ISSMDAVFileHandler import ISSMDAVFileHandler
from .ISSMDAVCollection import ISSMRootCollection

import tempfile
import os

class ISSMDAVProvider(DAVProvider):
    def __init__(self):
        super(ISSMDAVProvider, self).__init__()

        # Init ISSMRootCollection
        self.root = None
        print(f"ISSMDAVProvider init!")
        self.tempfile_handler = ISSMDAVFileHandler()

    def is_readonly(self):
        return False

    def ref_url_to_path(self, ref_url):
        """Convert a refUrl to a path, by stripping the share prefix.
        Used to calculate the <path> from a storage key by inverting get_ref_url().
        """
        print("/" + compat.unquote(util.lstripstr(ref_url, self.share_path)).lstrip(
            "/"))
        return "/" + compat.unquote(util.lstripstr(ref_url, self.share_path)).lstrip(
            "/"
        )

    def set_prop_manager(self, prop_manager):
        assert not prop_manager or hasattr(
            prop_manager, "copy_properties"
        ), "Must be compatible with wsgidav.prop_man.property_manager.PropertyManager"
        self.prop_manager = prop_manager

    def set_mount_path(self, mount_path):
        """Set application root for this resource provider.
        This is the value of SCRIPT_NAME, when WsgiDAVApp is called.
        """
        assert mount_path in ("", "/") or not mount_path.endswith("/")
        self.mount_path = mount_path

    def set_share_path(self, share_path):
        """Set application location for this resource provider.
        @param share_path: a UTF-8 encoded, unquoted byte string.
        """
        
        assert share_path == "" or share_path.startswith("/")
        if share_path == "/":
            share_path = ""  # This allows to code 'absPath = share_path + path'
        assert share_path in ("", "/") or not share_path.endswith("/")
        self.share_path = share_path

    def set_lock_manager(self, lock_manager):
        assert not lock_manager or hasattr(
            lock_manager, "check_write_permission"
        ), "Must be compatible with wsgidav.lock_manager.LockManager"
        self.lock_manager = lock_manager

    def exists(self, path, environ):
        """Return True, if path maps to an existing resource.
        This method should only be used, if no other information is queried
        for <path>. Otherwise a _DAVResource should be created first.
        This method SHOULD be overridden by a more efficient implementation.
        """
        return self.get_resource_inst(path, environ) is not None

    def is_collection(self, path, environ):
        print("is_collection")
        """Return True, if path maps to an existing collection resource.
        This method should only be used, if no other information is queried
        for <path>. Otherwise a _DAVResource should be created first.
        """
        res = self.get_resource_inst(path, environ)
        return res and res.is_collection

    def get_resource_inst(self, path, environ):
        """Return a _DAVResource object for path.
        Should be called only once per request and resource::
            res = provider.get_resource_inst(path, environ)
            if res and not res.is_collection:
                print(res.get_content_type())
        If <path> does not exist, None is returned.
        <environ> may be used by the provider to implement per-request caching.
        See _DAVResource for details.
        This method MUST be implemented.
        """
        #print(f"Path: {path}")
        environ['wsgidav.filehandler'] = self.tempfile_handler
        
        
        if not self.root:
            self.root =  ISSMRootCollection("/", environ, environ["wsgidav.auth.projects"])

        return self.root.resolve("/", path)
