#!/usr/bin/env python
# Utility Module to push an app to the App Catalog, regardless of the format of the source file. This is designed to be called by push_new_sumo_app.bash
# Usage:
# python push_app.py -s </full/path/app_source_file.json> -u <access_id>:<access_key>  -m </full/path/app_manifest_file.json>  <API_Endpoint>
# NOTE: API_ENDPOINT for pushing apps is:  https://nite-api.sumologic.net/api/v1/apps/import for new FolderSyncDefinition format, or
# https://nite-api.sumologic.net/api/v1/content/app for older Folder format. Either can be passed to this script and will be automatically converted to the right one depending on
# the source file format

import time
import json
import os
from argparse import ArgumentParser
import logging
from common import make_request, get_endpoint

logging.basicConfig(level=logging.INFO)


def push_app_api(api_url, sourcefile, manifestfile, access_id, access_key):
    # Push apps in old Folder format
    with open(sourcefile, 'rb') as sf:
        with open(manifestfile, 'rb') as mf:
            status, response = make_request(api_url, access_id, access_key, files={'appDef': sf, 'manifest': mf},
                                            method="POST")
            return status, response['message']


def push_app_api_v2(import_app_url, sourcefile, manifestfile, access_id, access_key):
    with open(sourcefile, 'rb') as sf:
        with open(manifestfile, 'rb') as mf:
            status, response = make_request(import_app_url, access_id, access_key,
                                            files={'appDefinition': sf, 'appManifest': mf},
                                            method="POST")
            if status:
                logging.info("Got app push job id: %s" % response['id'])
                job_id = response["id"]
                job_status_url = "%s/%s/status" % (import_app_url, job_id)
                waiting = True
                while waiting:
                    status, response = make_request(job_status_url, access_id, access_key, method="GET")
                    logging.info(response)
                    if response['status'] == "InProgress":
                        waiting = True
                        time.sleep(5)
                    else:
                        break

                if response['status'] == "Success":
                    return True, response["statusMessage"]
                else:
                    return False, response["error"]
            else:
                return status, "Unable to push app %s" % response


def prep_parser():
    parser = ArgumentParser(description='Script to push an app to production.')
    parser.add_argument("-f", dest="scrapplistpath", help="Path to scr_app_list.txt",
                        required=True)
    parser.add_argument("-u", dest="userauth", help="access_id:access_key", required=True)
    parser.add_argument("-d", dest="deployment", help="deployment name", required=True)

    return parser.parse_args()


def is_newformat(filename):
    """
    Check if app is new format (with FolderDefinition as top object)
    :param filename
    :return: True if new format, throws exception otherwise
    """
    with open(filename, 'r') as mf:
        logging.info("Reading file: " + filename)
        content_obj = json.load(mf)
        if ((not ('type' in content_obj)) or not (
                content_obj['type'] == "FolderSyncDefinition" or content_obj['type'] == "Folder")):
            raise Exception("Invalid app file format")
        else:
            if content_obj['type'] == "FolderSyncDefinition":
                return True
            else:
                return False


def get_final_api_endpoint(start_endpoint, is_foldersync_format):
    """
    Take an endpoint and convert to the right endpoint depending file format
    :param start_endpoint:
    :return:
    """
    new_endpoint = False
    if (start_endpoint.__contains__("/api/v1/apps/import")):
        new_endpoint = True
    else:
        if not (start_endpoint.__contains__("/api/v1/content/app")):
            raise Exception(
                "Invalid endpoint to push app, should be: .../api/v1/content/app for old Folder object or ../api/v1/apps/import for new FolderSyncDefinition object")
    if (not new_endpoint and is_foldersync_format):
        # convert to new endpoint when given old endpoint
        return start_endpoint.replace("/api/v1/content/app", "/api/v1/apps/import")
    elif (new_endpoint and not (is_foldersync_format)):
        # rare, shouldn't happen: convert to old endpoint if given new endpoint
        return start_endpoint.replace("/api/v1/apps/import", "/api/v1/content/app")
    return start_endpoint


def deploy_app():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir.endswith("bin"):
        root_dir = os.path.dirname(root_dir)
    parsed_args = vars(prep_parser())
    user_auth = parsed_args['userauth'].split(":")
    with open(parsed_args["scrapplistpath"]) as f:
        for line in f.readlines():
            if line.startswith("//"):
                continue
            sourceappfile, manifestfile = line.strip().split(":")
            sourceappfile = os.path.join(root_dir, sourceappfile)
            manifestfile = os.path.join(root_dir, manifestfile)
            print(sourceappfile, manifestfile)
            newformat = is_newformat(sourceappfile)
            final_api_url = get_final_api_endpoint(get_endpoint(parsed_args['deployment']), newformat)

            if newformat:
                status, response = push_app_api_v2(final_api_url, sourceappfile,
                                                   manifestfile, user_auth[0], user_auth[1])
            else:
                status, response = push_app_api(final_api_url, sourceappfile,
                                                manifestfile, user_auth[0], user_auth[1])
            if status:
                print("App was pushed successfully")
            else:
                print("App failed to be pushed %s" % response)


if __name__ == '__main__':
    deploy_app()
