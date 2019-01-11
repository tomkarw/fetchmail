#! /usr/bin/python3

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from apiclient import errors

# additional imports
import re
import sys

def GetGmailServiceObject():
    """Connect to Gmail API
    
    Returns: 
        Gmail API build object 
    """
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    store = file.Storage('token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
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
        label = service.users().labels().create(userId=user_id,
                                            body=label_object).execute()
        #print(label['id'])
        return label
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

def MakeLabel(label_name, mlv='show', llv='labelShow'):
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
        #for label in labels:
        #    print('Label id: %s - Label name: %s' % (label['id'], label['name']))
        return labels
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

def CreateIfNewLabel(service, user_id, label_name, mlv, llv):
    """Create a label if it doesnt already exist and return it
    
    Returns:
        Label Object - either already existing one or newly created
    """
    
    for existing_label in ListLabels(service,user_id):
        if existing_label['name'] == label_name:
            return existing_label
    else:
        label_object = MakeLabel(label_name, mlv, llv)
        created_label =  CreateLabel(service,'me',label_object)
        return created_label
    
def CreateNeededLabels(service,user_id, needed_labels):
    """Creates all needed labels and return them
    
    Returns:
        List of Label Objects
    """
    
    created_labels = []
    
    for label in needed_labels:
        label = CreateIfNewLabel(service,user_id,*label)
        created_labels += [label]
            
    return created_labels

def ZipLabelVariableNamesAndIds(label_variables,label_objects):
    return zip(label_variables,[label['id'] for label in label_objects])
    
def SetLabelsInFetchFile(zipedLabels, fetchfile):
    
    with open(fetchfile,'r') as fh:
        filebody = fh.read()
    
    for var,id in zipedLabels:
        filebody = re.sub(f"{var} = (None|'.*?')",f"{var} = '{id}'",filebody,count=1)
    
    with open(fetchfile,'w') as fh:
        fh.write(filebody)
        
def SetSaveDirectories(fetchfile,dir,path):
    
    with open(fetchfile,'r') as fh:
        filebody = fh.read()
    
    filebody = re.sub(f"{dir} = (None|'.*?')",f"{dir} = '{path}'",filebody)
        
    with open(fetchfile,'w') as fh:
        fh.write(filebody)


FETCH_LABELS = ('LABEL_SUCC', 'LABEL_ERROR', 'LABEL_NOATTACH')

LABELS = ('Pobrane','show','labelShow'), ('Błąd pobrania','show','labelShow'), ('Brak załączników','hide','labelHide')

def main():
    
    print('Running fetchattach_setup.py')
    
    
    #try:
    gmail = GetGmailServiceObject()
    #except Exception as e:
    #    print(e)
    #    exit(-1)
    
    #try:
    labels = CreateNeededLabels(gmail,'me',LABELS)
    #except Exception as e:
    #    print(e)
    #    exit(-1)
    
    
    #try:
    zipedLabels = ZipLabelVariableNamesAndIds(FETCH_LABELS,labels)
    SetLabelsInFetchFile(zipedLabels,'./fetchattach.py')
    #except Exception as e:
    #    print(e)
    #    exit(-1)
    
    #try:
    path_path = sys.argv[1]
    SetSaveDirectories('./fetchattach.py','MAIN_DIRECTORY',path_path)
    #except Exception as e:
    #    print(e)
    #    exit(-1)
    
    print('Setup succesful.')
    
    
    
if __name__=="__main__":
    main()
