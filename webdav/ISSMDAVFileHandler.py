from datetime import *
import tempfile
import time
import threading
import os

class ISSMDAVFileHandler():
    def __init__(self):
        self.tempfile_list = {}
        print("----------------------------------------------------")
        t1 = threading.Thread(target = self.init_cache_watcher, args=())
        t1.start()
        print("----------------------------------------------------")

    def init_cache_watcher(self):
        while True:
            self.checkCache()
            time.sleep(10)


    def checkCache(self):
        print(f"checkCache -- {len(self.tempfile_list.keys())}")
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        for search_hash, item in self.tempfile_list.copy().items():
            print(f"search_hash: {search_hash}")                
                #check if item expire (after 60s)
            if self.processCacheItem(item) or item['last_change_date'] < one_minute_ago:
                self.clearCacheItem(search_hash)
    
    def processCacheItem(self, cache_item):
        if 'infos' in cache_item:
            print(cache_item['infos'])
            return True
        return False

    def clearCacheItem(self, search_hash):        
        temp_file = '/data/temp/' + search_hash
        os.unlink(temp_file)

        if search_hash in self.tempfile_list:
            del self.tempfile_list[search_hash]

    def calHash(self, path, user):
        return "h_" + str(hash(path + str(user['id'])))

    def getTempFileItem(self, path, user):
        search_hash = self.calHash(path,user)
        print(F"getTempFileItem: {search_hash} -- {len(self.tempfile_list.keys())}")

        temp_file = None

        if search_hash in self.tempfile_list:
            temp_file = self.tempfile_list[search_hash]
        
            return temp_file
        return temp_file

    def getTempFile(self, path, user):
        temp_file = self.getTempFileItem(path, user)
    
        if temp_file is not None:
            return temp_file["temp_file"]
        return temp_file

    def getTempFileName(self, path, user):
        temp_file = self.getTempFileItem(path, user)
    
        if temp_file is not None:
            return temp_file["name"]
        return temp_file

    def setTempFile(self, path, user, temp_file, name):
        search_hash = self.calHash(path,user)
        print(F"setTempFile: {search_hash}")

        result_object = {
            'temp_file': temp_file,
            'last_change_date':  datetime.now(),
            'name': name
        }

        if search_hash in self.tempfile_list:
            self.tempfile_list[search_hash] = result_object
        else:
            self.tempfile_list[search_hash] = result_object
        
        return temp_file

    def newTempFile(self, path, user, name):
        search_hash = self.calHash(path,user)
        temp_file = '/data/temp/' + search_hash

        os.makedirs(os.path.dirname(temp_file), exist_ok=True)
        
        return self.setTempFile(path, user,temp_file, name)
        
    def removeTempFile(self, path, user, name):
        search_hash = self.calHash(path,user)

        return self.clearCacheItem(search_hash)

    def addInformationToTempFile(self, path, user, information):
        temp_file_item = self.getTempFileItem(path, user)
        temp_file_item['infos'] = information

        return temp_file_item
