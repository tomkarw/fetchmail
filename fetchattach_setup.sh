#! /bin/bash

if [[ $# != 3 ]] ; then
    echo 'usage: fetchattach_setup.sh [path to directory] [directory name] [mail from]'
    exit 1
fi

# path to where the directory for storing files should be created
DIR_PATH=$1
# what the directory should be named
DIR_NAME=$2
# whose mails should be checked 
MAIL_FROM=$3

DIR_MAIN="$DIR_PATH/$DIR_NAME"
DIR_PDF="$DIR_PATH/$DIR_NAME/Pdf"
DIR_OTHER="$DIR_PATH/$DIR_NAME/Other"

mkdir $DIR_MAIN
mkdir $DIR_PDF
mkdir $DIR_OTHER

# run python script that sets up labels
$PWD/fetchattach_setup.py $DIR_PATH

# run script to check if it works
#$PWD/fetchattach.py $3

# add main script as a cron job to be run every minute
croncmd="$PWD/fetchattach.py $3"
cronjob="*/1 * * * * $croncmd"
( crontab -l | grep -v -F "$croncmd" ; echo "$cronjob" ) | crontab -
