import requests


ISSM_API_URL = 'http://localhost:5000/api/webdav'

def get_data_from_issm_api(url, user_object):
    # url like /user/info
    if user_object is None or 'email' not in user_object or 'password' not in user_object:
        return None
    print(ISSM_API_URL + url)
    r = requests.post(ISSM_API_URL + url, data={"user_name": user_object['email'], "password": user_object['password']})
    return r.json()

def perform_function(function_name, project_id, case_id, user):
    if function_name == "upload":
        print("upload")
        return False
    elif function_name == "delete_all_operations":
        print("delete_all_operations")
        return False
    elif function_name == "duplicate_item":
        print("duplicate_item")
        return False
    elif function_name == "accept":
        response_data = get_data_from_issm_api('/project/' + str(project_id) + '/case/' + str(case_id) + '/accept', user)
        # response_data['success'] True so the call was successful
        print(f"accept --- {response_data['success']}")
        return response_data['success']
    elif function_name == "reject":
        response_data = get_data_from_issm_api('/project/' + str(project_id) + '/case/' + str(case_id) + '/reject', user)
        # response_data['success'] True so the call was successful
        print(f"reject --- {response_data['success']}")
        return response_data['success']
    elif function_name == "assign_to_myself":
        response_data = get_data_from_issm_api('/project/' + str(project_id) + '/case/' + str(case_id) + '/assign', user)
        # response_data['success'] True so the call was successful
        print(f"assign_to_myself --- {response_data}")
        return response_data['success']
    elif function_name == "submit_segmentation":
        response_data = get_data_from_issm_api('/project/' + str(project_id) + '/case/' + str(case_id) + '/submit', user)
        # response_data['success'] True so the call was successful
        print(f"submit --- {response_data['success']}")
        return response_data['success']
    return False
