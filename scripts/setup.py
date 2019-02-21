#! /usr/bin/python3

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from apiclient import errors

# additional imports
import re
import json
import os
import subprocess

SCOPES = 'https://www.googleapis.com/auth/gmail.modify'

PATH = os.path.dirname(os.path.realpath(__file__))+'/..'


def GetGmailServiceObject():
    """Connect to Gmail API
    
    Returns: 
        Gmail API build object 
    """
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    store = file.Storage(PATH+'/credentials/token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets(PATH+'credentials/credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
        
    return build('gmail', 'v1', http=creds.authorize(Http()))

def CreateLabel(service, user_id, label_object):
    """Creates a new label within user's mailbox, also prints Label ID.
    
    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
        label_object: label to be added.
        
    Returns:
        Created Label.
    """
    try:
        del label_object["id"]
        label = service.users().labels().create(userId=user_id,
                                            body=label_object).execute()
        return label
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

def DeleteLabel(service, user_id, label_id):
  """Delete a label.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    label_id: string id of the label.
  """
  try:
    service.users().labels().delete(userId=user_id, id=label_id).execute()
    
  except errors.HttpError as error:
    print('An error occurred: %s' % error)

def MakeLabelObject(label_name, mlv='show', llv='labelShow'):
    """Create Label object.

    Args:
        label_name: The name of the Label.
        mlv: Message list visibility, show/hide.
        llv: Label list visibility, labelShow/labelHide.

    Returns:
        Created Label.
  """
    label = {'messageListVisibility': mlv,
            'name': label_name,
            'labelListVisibility': llv}
    return label
    
def ListLabels(service, user_id):
    """Get a list all labels in the user's mailbox.

    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.

    Returns:
        A list all Labels in the user's mailbox.
    """
    try:
        response = service.users().labels().list(userId=user_id).execute()
        labels = response['labels']
        return labels
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

def CreateIfNewLabel(service, user_id, label_object):
    """Create a label if it doesnt already exist and return it
    
    Returns:
        Gmail Label Object - either already existing one or newly created
    """
    
    
    for existing_label in ListLabels(service,user_id):
        if  existing_label["name"] == label_object["name"]:
            if  existing_label["labelListVisibility"] == label_object["labelListVisibility"] and \
                existing_label["messageListVisibility"] == label_object["messageListVisibility"]:
                    return existing_label
            else:
                DeleteLabel(service, user_id, existing_label["id"])
                return CreateLabel(service,'me',label_object)
    return CreateLabel(service,'me',label_object)
    
def CreateNeededLabels(service,user_id, needed_labels):
    """Creates all needed labels and return them
    
    Returns:
        List of Label Objects
    """
    
    created_labels = []
    
    for label_object in needed_labels:
        label = CreateIfNewLabel(service,user_id,label_object)
        if label:
            created_labels += [label]
    
    return created_labels

def loadSettingsFromJSON(json_path):
    
    with open(json_path) as fh:
        json_dict = json.loads(fh.read())
    
    return json_dict
    
def saveSettingsToJSON(json_dict,json_path):
    
    with open(json_path,'w') as fh:
        json.dump(json_dict, fh, indent=4)
    
def SetLabelIdInFile(json_path, json_dict, labels):
    
    save = False
    for label in labels:
        for label_key in json_dict["PersonalSettings"]["Labels"]:
            if label["name"] == json_dict["PersonalSettings"]["Labels"][label_key]["name"]:
                if json_dict["PersonalSettings"]["Labels"][label_key]["id"] != label["id"]:
                    json_dict["PersonalSettings"]["Labels"][label_key]["id"] = label["id"]
                    save = True

    if save:
        saveSettingsToJSON(json_dict,json_path)

def main():
    
    print('Running fetchattach_setup.py')
    
    gmail = GetGmailServiceObject()
    
    for settings_file in os.listdir(PATH + '/settings'):
        settings_dict = loadSettingsFromJSON(PATH + '/settings/' + settings_file)
        
        # dir_path - path to where the directory for storing files should be created
        # dir_name - what the directory should be named
        # mail_from - whose mails should be checked 
        dir_path = settings_dict["PersonalSettings"]["Directories"]["MainStoreDirectory"]["path"]
        dir_name = settings_dict["PersonalSettings"]["Directories"]["MainStoreDirectory"]["name"]
        mail_from = settings_dict["PersonalSettings"]["MailFrom"]
        
        main_dir = dir_path + '/' + dir_name
        
        try:
            os.mkdir(main_dir)
        except FileExistsError as error:
            print('Directory already exists:',main_dir)
        
        for file_dir in settings_dict["PersonalSettings"]["Directories"]["StoreDirectories"]:
            dir_name = settings_dict["PersonalSettings"]["Directories"]["StoreDirectories"][file_dir]
            dir_path = main_dir + '/' + dir_name
            try:
                os.mkdir(dir_path)
            except FileExistsError as error:
                print('Directory already exists:',dir_path)

        settings_labels = [settings_dict["PersonalSettings"]["Labels"][key] for key in settings_dict["PersonalSettings"]["Labels"]]
        
        labels = CreateNeededLabels(gmail,'me',settings_labels) 
        
        SetLabelIdInFile(PATH + '/settings/' + settings_file, settings_dict, labels)

    
    # add main script as a cron job to be run every minute
    croncmd = PATH + "scripts/fetchattach.py"
    cronjob = f'*/1 * * * * {croncmd} >> {PATH+"/fetchcron.log"} 2>&1'
    subprocess.run(f'crontab -l | ( grep -v -F "{croncmd}" ; echo "{cronjob}" ) | crontab -',shell=True)
    
    croncmd = PATH + "scripts/setup.py"
    cronjob = f'* 20 * * * {croncmd} >> {PATH+"/fetchcron.log"} 2>&1'
    subprocess.run(f'crontab -l | ( grep -v -F "{croncmd}" ; echo "{cronjob}" ) | crontab -',shell=True)
    
    print('Setup succesful.')
    
if __name__=="__main__":

    main()
