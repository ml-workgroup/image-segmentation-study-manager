import os
import stat
import shutil
from wsgidav import compat, util
from os.path import isfile, join
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN
from wsgidav.dav_provider import DAVNonCollection
from .ISSMUtils import *

BUFFER_SIZE = 8192

class ISSMDAVNonCollection(DAVNonCollection):
    """Represents a single existing DAV resource instance.
    See also _DAVResource, DAVNonCollection, and FilesystemProvider.
    """

    def __init__(self, path, environ, file_path, display_name, project, case):
        super(ISSMDAVNonCollection, self).__init__(path, environ)
        print(f"ISSMDAVNonCollection {file_path}")
        self._file_path = file_path
        self.project = project
        self.case = case

        if os.path.isfile(self._file_path):
            self.file_stat = os.stat(self._file_path)
        else:
            self.file_stat = None
        self.name = display_name

    # Getter methods for standard live properties
    def get_content_length(self):
        if self.file_stat:
            return self.file_stat[stat.ST_SIZE]
        else:
            return None

    def get_content_type(self):
        if os.path.isfile(self._file_path):
            return util.guess_mime_type(self._file_path)
        else:
            return None

    def get_creation_date(self):
        if self.file_stat:
            return self.file_stat[stat.ST_SIZE]
        else:
            return None
        return self.file_stat[stat.ST_CTIME]

    def get_display_name(self):
        return self.name

    def get_etag(self):
        if os.path.isfile(self._file_path):
            return util.get_etag(self._file_path)
        else:
            return None

    def get_last_modified(self):
        if self.file_stat:
            return self.file_stat[stat.ST_MTIME]
        else:
            return None

    def support_etag(self):
        return True

    def support_ranges(self):
        return True

    def get_content(self):
        """Open content as a stream for reading.
        See DAVResource.get_content()
        """
        print(f"get_content")
        assert not self.is_collection
        # GC issue 28, 57: if we open in text mode, \r\n is converted to one byte.
        # So the file size reported by Windows differs from len(..), thus
        # content-length will be wrong.
        return open(self._file_path, "rb", BUFFER_SIZE)

    def begin_write(self, content_type=None):
        """Open content as a stream for writing.
        See DAVResource.begin_write()
        """
        print(f"begin_write {self.provider.is_readonly()} --- {os.path.isfile(self._file_path)}")
        assert not self.is_collection
        if self.provider.is_readonly():
            raise DAVError(HTTP_FORBIDDEN)
        # _logger.debug("begin_write: {}, {}".format(self._file_path, "wb"))
        # GC issue 57: always store as binary
        return open(self._file_path, "wb", BUFFER_SIZE)

    def end_write(self, with_errors):
        """Called when PUT has finished writing.
        This is only a notification. that MAY be handled.
        """
        print(f"end_write {self._file_path} -- {os.path.getsize(self._file_path)}")
        pass

    def delete(self):
        """Remove this resource or collection (recursive).
        See DAVResource.delete()
        """
        print(f"delete")
        if self.provider.is_readonly():
            raise DAVError(HTTP_FORBIDDEN)
        os.unlink(self._file_path)
        self.remove_all_properties(True)
        self.remove_all_locks(True)

    def copy_move_single(self, dest_path, is_move):
        """See DAVResource.copy_move_single() """
        print(f"copy_move_single")
        if self.provider.is_readonly():
            raise DAVError(HTTP_FORBIDDEN)
        fpDest = self.provider._loc_to_file_path(dest_path, self.environ)
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        # Copy file (overwrite, if exists)
        shutil.copy2(self._file_path, fpDest)
        # (Live properties are copied by copy2 or copystat)
        # Copy dead properties
        propMan = self.provider.prop_manager
        if propMan:
            destRes = self.provider.get_resource_inst(dest_path, self.environ)
            if is_move:
                propMan.move_properties(
                    self.get_ref_url(),
                    destRes.get_ref_url(),
                    with_children=False,
                    environ=self.environ,
                )
            else:
                propMan.copy_properties(
                    self.get_ref_url(), destRes.get_ref_url(), self.environ
                )

    def support_recursive_move(self, dest_path):
        """Return True, if move_recursive() is available (see comments there)."""
        return True

    def move_recursive(self, dest_path):
        """See DAVResource.move_recursive() """
        if self.provider.readonly:
            raise DAVError(HTTP_FORBIDDEN)
        fpDest = self.provider._loc_to_file_path(dest_path, self.environ)
        assert not util.is_equal_or_child_uri(self.path, dest_path)
        assert not os.path.exists(fpDest)
        _logger.debug("move_recursive({}, {})".format(self._file_path, fpDest))
        shutil.move(self._file_path, fpDest)
        # (Live properties are copied by copy2 or copystat)
        # Move dead properties
        if self.provider.prop_manager:
            destRes = self.provider.get_resource_inst(dest_path, self.environ)
            self.provider.prop_manager.move_properties(
                self.get_ref_url(),
                destRes.get_ref_url(),
                with_children=True,
                environ=self.environ,
            )

    def set_last_modified(self, dest_path, time_stamp, dry_run):
        """Set last modified time for destPath to timeStamp on epoch-format"""
        # Translate time from RFC 1123 to seconds since epoch format
        secs = util.parse_time_string(time_stamp)
        if not dry_run:
            os.utime(self._file_path, (secs, secs))
        return True

    def handle_move(self, dest_path):
        path, function_name = os.path.split(dest_path.replace('/' + self.name,""))
        print(f"handle_move: {function_name}")

        return perform_function(function_name, self.project['id'], self.case['id'], self.environ["wsgidav.auth.user"])