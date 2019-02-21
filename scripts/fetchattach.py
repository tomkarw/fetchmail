#! /usr/bin/python3

# based on Python example from 
# https://developers.google.com/gmail/api/v1/reference/users/messages/attachments/get
# which is licensed under Apache 2.0 License


from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from apiclient import errors

import base64 # decoding message body data

# my additional imports
import re # for extracting urls from message body
import urllib.request # for downloading files from urls
import json # for loading JSON file with settings
import schedule # for cron like execution of this script
import time
import datetime
import os # for getting file path
import gi # for sending notifications
from gi.repository import GObject
gi.require_version('Notify', '0.7')
from gi.repository import Notify
import os # os.listdir

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/gmail.modify'

# getting path to all needed files
PATH = os.path.dirname(os.path.realpath(__file__))+'/..'

# setting display info for notifications
os.environ['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=/run/user/1000/bus'

# regexp for links to download
linkNameRegex = re.compile(r'"(https://usosapps.*?)">(.*?)<')

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
        flow = client.flow_from_clientsecrets(PATH+'/credentials/credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    return build('gmail', 'v1', http=creds.authorize(Http()))

def ListMessagesMatchingQuery(service, user_id, query=''):
  """List all Messages of the user's mailbox matching the query.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    query: String used to filter messages returned.
    Eg.- 'from:user@some_domain.com' for Messages from a particular sender.

  Returns:
    List of Messages that match the criteria of the query. Note that the
    returned list contains Message IDs, you must use get with the
    appropriate ID to get the details of a Message.
  """
  try:
    response = service.users().messages().list(userId=user_id,
                                               q=query).execute()
    messages = []
    if 'messages' in response:
      messages.extend(response['messages'])

    while 'nextPageToken' in response:
      page_token = response['nextPageToken']
      response = service.users().messages().list(userId=user_id, q=query,
                                         pageToken=page_token).execute()
      messages.extend(response['messages'])

    return messages
    
  except errors.HttpError as error:
        print('An error occurred: %s' % error)

def GetMessage(service, user_id, msg_id, chosen_format):
  """Get a Message with given ID.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: The ID of the Message required.

  Returns:
    A Message.
  """
  try:
    message = service.users().messages().get(userId=user_id, id=msg_id, format=chosen_format).execute()
    return message
    
  except errors.HttpError as error:
    print('An error occurred: %s' % error)

def GetAttachments(service, user_id, msg_id, prefix=""):
    """Get and store attachment from Message with given id.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
        can be used to indicate the authenticated user.
    msg_id: ID of Message containing attachment.
    prefix: prefix which is added to the attachment filename on saving
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id).execute()

        for part in message['payload']['parts']:
            if part['filename']:
                if 'data' in part['body']:
                    data=part['body']['data']
                else:
                    att_id=part['body']['attachmentId']
                    att=service.users().messages().attachments().get(userId=user_id, messageId=msg_id,id=att_id).execute()
                    data=att['data']
                file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
                path = prefix+part['filename']

                with open(path, 'wb') as f:
                    f.write(file_data)
                    
                return part['filename']
                
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

def SetLabel(service, user_id, msg_id, label):
    service.users().messages().modify(userId=user_id, id=msg_id, body={"addLabelIds": [label]}).execute()

def loadSettingsFromJSON(json_path):
    
    with open(json_path) as fh:
        json_dict = json.loads(fh.read())
    
    return json_dict

def saveSettingsToJSON(json_dict,json_path):
    
    with open(json_path,'w') as fh:
        json.dump(json_dict, fh, indent=4)

def DownloadMails(gmail, settings_dict, download_all=False, set_labels=True):
    
    # build Gmail API object
    
    
    # set adress from which mails are to be downloaded
    from_user = settings_dict["PersonalSettings"]["MailFrom"]
    
    # mostly for debugging, download mail that was already tagged
    if not download_all:
        messages = ListMessagesMatchingQuery(gmail,'me',f'from:{from_user} has:nouserlabels')
    else:
        messages = ListMessagesMatchingQuery(gmail,'me',f'from:{from_user}')
    
    for message_handle in messages:
        msg_id = message_handle['id']
        
        message = GetMessage(gmail,'me',msg_id,'full')

        message_body_data = ''
        
        for message_part in message['payload']['parts']:
            try:
                message_body_data += str(base64.urlsafe_b64decode(message_part['body']['data'].encode('UTF8')),encoding='UTF-8')
            except KeyError:
                path = settings_dict["PersonalSettings"]["Directories"]["MainStoreDirectory"]["path"]
                main_dir_name = settings_dict["PersonalSettings"]["Directories"]["MainStoreDirectory"]["name"]
                pdf_dir_name = settings_dict["PersonalSettings"]["Directories"]["StoreDirectories"]["pdf"]
                save_to_path =  f"{path}/{main_dir_name}/{pdf_dir_name}/"
                
                filename = GetAttachments(gmail,'me',msg_id,save_to_path)
                
                if set_labels:
                    succ_label_id = settings_dict["PersonalSettings"]["Labels"]["LabelSuccDownload"]["id"]
                    SetLabel(gmail,'me',msg_id,succ_label_id)
                
                text = settings_dict["PersonalSettings"]["Notifications"]["NewFile"]
                Notify.Notification.new("fetch-attach", f'{text}\n"{filename}"', PATH+'/graphics/Gmail_Icon.png').show()
        
        linksNames = linkNameRegex.findall(message_body_data)
        
        if not linksNames:
            noattach_label_id = settings_dict["PersonalSettings"]["Labels"]["LabelNoAttach"]["id"]
            
            if set_labels:
                SetLabel(gmail,'me',msg_id,noattach_label_id)
            
            text = settings_dict["PersonalSettings"]["Notifications"]["NoAttach"]
            Notify.Notification.new("fetch-attach", text, PATH+'/graphics/Gmail_Icon.png').show()
        
        for url,filename in linksNames:
            
            # save files to different directories # DO POPRAWY
            path = settings_dict["PersonalSettings"]["Directories"]["MainStoreDirectory"]["path"]
            main_dir_name = settings_dict["PersonalSettings"]["Directories"]["MainStoreDirectory"]["name"]
            
            ext = filename.split('.')[-1]
            
            if ext in settings_dict["PersonalSettings"]["Directories"]["StoreDirectories"]:
                dir_name = settings_dict["PersonalSettings"]["Directories"]["StoreDirectories"][ext]
                save_to_filename =  f"{path}/{main_dir_name}/{dir_name}/{filename}"
            else:
                other_dir_name = settings_dict["PersonalSettings"]["Directories"]["StoreDirectories"]["*"]
                save_to_filename =  f"{path}/{main_dir_name}/{other_dir_name}/{filename}"
            
            try:
                # save file given the url
                urllib.request.urlretrieve(url, save_to_filename)
                
                # set a label signifying that the file has been downloaded
                if set_labels:
                    succ_label_id = settings_dict["PersonalSettings"]["Labels"]["LabelSuccDownload"]["id"]
                    SetLabel(gmail,'me',msg_id,succ_label_id)
                
                # notify about new file being added
                notif_msg = settings_dict["PersonalSettings"]["Notifications"]["NewFile"]
                Notify.Notification.new("fetch-attach", f'{notif_msg}\n"{filename}"', PATH+'/graphics/Gmail_Icon.png').show()
                
            except urllib.error.HTTPError as error:
                print('An error occurred: %s' % error,end=' ')
                print('(Probably means that the url no longer works)')
                error_label_id = settings_dict["PersonalSettings"]["Labels"]["LabelErrorDownload"]["id"]
                if set_labels:
                    SetLabel(gmail,'me',msg_id,error_label_id)


if __name__ == '__main__':
    
    with open(PATH + "/fetchcron.log","a") as fh:
        fh.write(str(datetime.datetime.now())+': fetchattach started, as cron job\n')
    
    gmail = GetGmailServiceObject()
    
    Notify.init("fetchattach")
    
    for settings_file in os.listdir(PATH + '/settings'):
        
        settings_dict = loadSettingsFromJSON(PATH + '/settings/' + settings_file)
        
        DownloadMails(gmail, settings_dict, download_all=True, set_labels=False)
        
        # send a notification that email was checked periodically (eg. every 30min)
        settings_dict["tick"] += 1
        if settings_dict["tick"] >= settings_dict["notifyEvery"]:
            notif_msg = settings_dict["PersonalSettings"]["Notifications"]["Checked"]
            Notify.Notification.new("fetch-attach", notif_msg, PATH+'/graphics/Gmail_Icon.png').show() # title, text, file_path_to_icon
            settings_dict["tick"] = 0
        
        saveSettingsToJSON(settings_dict,PATH + '/settings/' + settings_file)
    
    with open(PATH + "/fetchcron.log","a") as fh:
        fh.write(str(datetime.datetime.now())+': fetch finished, as cron job\n')
