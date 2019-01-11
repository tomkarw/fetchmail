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
import sys # sys.arg
import re # for extracting urls from message body
import urllib.request # for downloading files from urls
import subprocess # for running notify-send

import schedule # for cron like execution of this script
import time
import datetime


# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/gmail.modify'

linkNameRegex = re.compile(r'"(https://usosapps.*?)">(.*?)<')

MAIN_DIRECTORY = '/home/karwowskit/prog/python/fetchmail'
FILES_DIRECTORY = MAIN_DIRECTORY + '/Attachments'
PDF_DIRECTORY = FILES_DIRECTORY + '/Pdf'
OTHER_DIRECTORY = FILES_DIRECTORY + '/Other'

LABEL_SUCC = 'Label_12'
LABEL_NOATTACH = 'Label_14'
LABEL_ERROR = 'Label_13'

def GetGmailServiceObject():
    """Connect to Gmail API
    
    Returns: 
        Gmail API build object 
    """
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    store = file.Storage(MAIN_DIRECTORY+'/token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets(MAIN_DIRECTORY+'/credentials.json', SCOPES)
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
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

def SetLabel(service, user_id, msg_id, label):
    service.users().messages().modify(userId=user_id, id=msg_id, body={"addLabelIds": [label]}).execute()

def DownloadMails(from_user, save_pdf, save_other):
    
    gmail = GetGmailServiceObject()

    messages = ListMessagesMatchingQuery(gmail,'me',f'from:{from_user} has:nouserlabels')
    
    for message_handle in messages:
        msg_id = message_handle['id']
        
        message = GetMessage(gmail,'me',msg_id,'full')

        message_body_data = ''
        
        for message_part in message['payload']['parts']:
            try:
                message_body_data += str(base64.urlsafe_b64decode(message_part['body']['data'].encode('UTF8')),encoding='UTF-8')
            except KeyError:
                GetAttachments(gmail,'me',msg_id,save_pdf+'/')
        
        linksNames = linkNameRegex.findall(message_body_data)
        
        if not linksNames:
            SetLabel(gmail,'me',msg_id,LABEL_NOATTACH)
            print('No attachments found, advised to check manually just in case')
        
        for url,filename in linksNames:
            
            # save files to different directories
            if ".pdf" in filename:
                save_to_filename = save_pdf + '/' + filename
            else:
                save_to_filename = save_other + '/' + filename
            
            try:
                # save file given the url
                urllib.request.urlretrieve(url, save_to_filename)
                
                # set a label signifying that the file has been downloaded
                SetLabel(gmail,'me',msg_id,LABEL_SUCC)
                
                # notify about new file being added
                subprocess.run(['notify-send', 'Nowy plik od  Puczy:\n"'+filename+'"'])
                
            except urllib.error.HTTPError as error:
                print('An error occurred: %s' % error,end=' ')
                print('(Probably means that the url no longer works)')
                SetLabel(gmail,'me',msg_id,LABEL_ERROR)
        

if __name__ == '__main__':
    
    with open("/home/karwowskit/prog/python/fetchmail/fetchcron.log","a") as fh:
        fh.write(str(datetime.datetime.now())+': fetchattach started, as cron job\n')
    
    mail_from = sys.argv[1]
        
    DownloadMails(mail_from,PDF_DIRECTORY,OTHER_DIRECTORY)
    subprocess.run(['notify-send', f"'fetchattach' checked for new mail."])

    with open("/home/karwowskit/prog/python/fetchmail/fetchcron.log","a") as fh:
        fh.write(str(datetime.datetime.now())+': fetch finished, as cron job\n')
