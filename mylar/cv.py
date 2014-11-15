#  This file is part of Mylar.
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the 
#  implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public 
#  License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.


import sys
import os
import re
import logger
import string
import urllib
import lib.feedparser
import mylar
from mylar.helpers import cvapi_check

from bs4 import BeautifulSoup as Soup

def pulldetails(comicid,type,issueid=None,offset=1):
    import urllib2

    #import easy to use xml parser called minidom:
    from xml.dom.minidom import parseString

    if mylar.COMICVINE_API == 'None' or mylar.COMICVINE_API is None or mylar.COMICVINE_API == mylar.DEFAULT_CVAPI:
        logger.warn('You have not specified your own ComicVine API key - alot of things will be limited. Get your own @ http://api.comicvine.com.')
        comicapi = mylar.DEFAULT_CVAPI
    else:
        comicapi = mylar.COMICVINE_API

    if type == 'comic':
        if not comicid.startswith('4050-'): comicid = '4050-' + comicid
        PULLURL= mylar.CVURL + 'volume/' + str(comicid) + '/?api_key=' + str(comicapi) + '&format=xml&field_list=name,count_of_issues,issues,start_year,site_detail_url,image,publisher,description,first_issue,deck,aliases'
    elif type == 'issue':
        if mylar.CV_ONLY:
            cv_type = 'issues'
            searchset = 'filter=volume:' + str(comicid) + '&field_list=cover_date,description,id,image,issue_number,name,date_last_updated,store_date'
        else:
            cv_type = 'volume/' + str(comicid)
            searchset = 'name,count_of_issues,issues,start_year,site_detail_url,image,publisher,description,store_date'
        PULLURL = mylar.CVURL + str(cv_type) + '/?api_key=' + str(comicapi) + '&format=xml&' + str(searchset) + '&offset=' + str(offset)
    elif type == 'firstissue':
        #this is used ONLY for CV_ONLY
        PULLURL = mylar.CVURL + 'issues/?api_key=' + str(comicapi) + '&format=xml&filter=id:' + str(issueid) + '&field_list=cover_date'
    elif type == 'storyarc':
       PULLURL =  mylar.CVURL + 'story_arcs/?api_key=' + str(comicapi) + '&format=xml&filter=name:' + str(issueid) + '&field_list=cover_date'

    #CV API Check here.
    if mylar.CVAPI_COUNT == 0 or mylar.CVAPI_COUNT >= mylar.CVAPI_MAX:
        cvapi_check()
    #download the file:
    file = urllib2.urlopen(PULLURL)
    #increment CV API counter.
    mylar.CVAPI_COUNT +=1
    #convert to string:
    data = file.read()
    #close file because we dont need it anymore:
    file.close()
    #parse the xml you downloaded
    dom = parseString(data)

    return dom


def getComic(comicid,type,issueid=None,arc=None):
    if type == 'issue': 
        offset = 1
        issue = {}
        ndic = []
        issuechoice = []
        comicResults = []
        firstdate = '2099-00-00'
        #let's find out how many results we get from the query...
        searched = pulldetails(comicid,'issue',None,0)
        if searched is None: return False
        totalResults = searched.getElementsByTagName('number_of_total_results')[0].firstChild.wholeText
        logger.fdebug("there are " + str(totalResults) + " search results...")
        if not totalResults:
            return False
        countResults = 0
        while (countResults < int(totalResults)):
            logger.fdebug("querying " + str(countResults))
            if countResults > 0:
                #new api - have to change to page # instead of offset count
                offsetcount = countResults
                searched = pulldetails(comicid,'issue',None,offsetcount)
            issuechoice,tmpdate = GetIssuesInfo(comicid,searched)
            if tmpdate < firstdate:
                firstdate = tmpdate
            ndic = ndic + issuechoice
            #search results are limited to 100 and by pagination now...let's account for this.
            countResults = countResults + 100

        issue['issuechoice'] = ndic
        issue['firstdate'] = firstdate

        return issue

    elif type == 'comic':
        dom = pulldetails(comicid,'comic',None,1)
        return GetComicInfo(comicid,dom)
    elif type == 'firstissue': 
        dom = pulldetails(comicid,'firstissue',issueid,1)
        return GetFirstIssue(issueid,dom)
    elif type == 'storyarc':
        dom = pulldetails(arc,'storyarc',None,1)   
        return GetComicInfo(issueid,dom)

def GetComicInfo(comicid,dom):

    #comicvine isn't as up-to-date with issue counts..
    #so this can get really buggered, really fast.
    tracks = dom.getElementsByTagName('issue')
    try:
        cntit = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
    except:
        cntit = len(tracks)
    trackcnt = len(tracks)
    logger.fdebug("number of issues I counted: " + str(trackcnt))
    logger.fdebug("number of issues CV says it has: " + str(cntit))
    # if the two don't match, use trackcnt as count_of_issues might be not upto-date for some reason
    if int(trackcnt) != int(cntit):
        cntit = trackcnt
        vari = "yes"
    else: vari = "no"
    logger.fdebug("vari is set to: " + str(vari))
    #if str(trackcnt) != str(int(cntit)+2):
    #    cntit = int(cntit) + 1
    comic = {}
    comicchoice = []
    cntit = int(cntit)
    #retrieve the first xml tag (<tag>data</tag>)
    #that the parser finds with name tagName:
    # to return the parent name of the <name> node : dom.getElementsByTagName('name')[0].parentNode.nodeName
    # where [0] denotes the number of the name field(s)
    # where nodeName denotes the parentNode : ComicName = results, publisher = publisher, issues = issue
    try:
        names = len( dom.getElementsByTagName('name') )
        n = 0
        while ( n < names ):
            if dom.getElementsByTagName('name')[n].parentNode.nodeName == 'results':
                try:
                    comic['ComicName'] = dom.getElementsByTagName('name')[n].firstChild.wholeText
                    comic['ComicName'] = comic['ComicName'].rstrip() 
                except:
                    logger.error('There was a problem retrieving the given data from ComicVine. Ensure that www.comicvine.com is accessible AND that you have provided your OWN ComicVine API key.')
                    return

            elif dom.getElementsByTagName('name')[n].parentNode.nodeName == 'publisher':
                try:
                    comic['ComicPublisher'] = dom.getElementsByTagName('name')[n].firstChild.wholeText
                except:
                    comic['ComicPublisher'] = "Unknown"

            n+=1  
    except:
        logger.warn('Something went wrong retrieving from ComicVine. Ensure your API is up-to-date and that comicvine is accessible')
        return

    try:
        comic['ComicYear'] = dom.getElementsByTagName('start_year')[0].firstChild.wholeText
    except:
        comic['ComicYear'] = '0000'
    comic['ComicURL'] = dom.getElementsByTagName('site_detail_url')[trackcnt].firstChild.wholeText

    desdeck = 0
    #the description field actually holds the Volume# - so let's grab it
    try:
        descchunk = dom.getElementsByTagName('description')[0].firstChild.wholeText
        comic_desc = drophtml(descchunk)
        desdeck +=1
    except:
        comic_desc = 'None'

    #sometimes the deck has volume labels
    try:
        deckchunk = dom.getElementsByTagName('deck')[0].firstChild.wholeText
        comic_deck = deckchunk
        desdeck +=1
    except:
        comic_deck = 'None'

    try:
        comic['Aliases'] = dom.getElementsByTagName('aliases')[0].firstChild.wholeText
        #logger.fdebug('Aliases: ' + str(aliases))
    except:
        comic['Aliases'] = 'None'

    comic['ComicVersion'] = 'noversion'
    #logger.info('comic_desc:' + comic_desc)
    #logger.info('comic_deck:' + comic_deck)
    #logger.info('desdeck: ' + str(desdeck))
    while (desdeck > 0):
        if desdeck == 1:
            if comic_desc == 'None':
                comicDes = comic_deck[:30]
            else:
                #extract the first 60 characters
                comicDes = comic_desc[:60].replace('New 52', '')
        elif desdeck == 2:
            #extract the characters from the deck
            comicDes = comic_deck[:30].replace('New 52', '')
        else:
            break

        i = 0
        while (i < 2):
            if 'volume' in comicDes.lower():
                #found volume - let's grab it.
                v_find = comicDes.lower().find('volume')
                #arbitrarily grab the next 10 chars (6 for volume + 1 for space + 3 for the actual vol #)
                #increased to 10 to allow for text numbering (+5 max)
                #sometimes it's volume 5 and ocassionally it's fifth volume.
                if i == 0:
                    vfind = comicDes[v_find:v_find+15]   #if it's volume 5 format
                    basenums = {'zero':'0','one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9','ten':'10','i':'1','ii':'2','iii':'3','iv':'4','v':'5'}
                    logger.fdebug('volume X format - ' + str(i) + ': ' + vfind)
                else:
                    vfind = comicDes[:v_find]   # if it's fifth volume format
                    basenums = {'zero':'0','first':'1','second':'2','third':'3','fourth':'4','fifth':'5','sixth':'6','seventh':'7','eighth':'8','nineth':'9','tenth':'10','i':'1','ii':'2','iii':'3','iv':'4','v':'5'}
                    logger.fdebug('X volume format - ' + str(i) + ': ' + vfind)
                volconv = ''
                for nums in basenums:
                    if nums in vfind.lower():
                        sconv = basenums[nums]
                        vfind = re.sub(nums, sconv, vfind.lower())
                        break        
                #logger.info('volconv: ' + str(volconv))

                #now we attempt to find the character position after the word 'volume'
                if i == 0:
                    volthis = vfind.lower().find('volume')
                    volthis = volthis + 6 # add on the actual word to the position so that we can grab the subsequent digit
                    vfind = vfind[volthis:volthis+4] #grab the next 4 characters ;)
                elif i == 1:
                    volthis = vfind.lower().find('volume')
                    vfind = vfind[volthis-4:volthis] #grab the next 4 characters ;)

                if '(' in vfind:
                    #bracket detected in versioning'
                    vfindit = re.findall('[^()]+', vfind)
                    vfind = vfindit[0]
                vf = re.findall('[^<>]+', vfind)
                ledigit = re.sub("[^0-9]", "", vf[0])
                if ledigit != '':
                    comic['ComicVersion'] = ledigit
                    logger.fdebug("Volume information found! Adding to series record : volume " + comic['ComicVersion'])
                    break
                i+=1
            else:
                i+=1

        if comic['ComicVersion'] == 'noversion':
            logger.fdebug('comic[ComicVersion]:' + str(comic['ComicVersion']))
            desdeck -=1
        else:
            break

    if vari == "yes": 
        comic['ComicIssues'] = str(cntit)
    else:
        comic['ComicIssues'] = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText

    comic['ComicImage'] = dom.getElementsByTagName('super_url')[0].firstChild.wholeText
    comic['ComicImageALT'] = dom.getElementsByTagName('small_url')[0].firstChild.wholeText

    comic['FirstIssueID'] = dom.getElementsByTagName('id')[0].firstChild.wholeText

#    print ("fistIss:" + str(comic['FirstIssueID']))
#    comicchoice.append({
#        'ComicName':              comic['ComicName'],
#        'ComicYear':              comic['ComicYear'],
#        'Comicid':                comicid,
#        'ComicURL':               comic['ComicURL'],
#        'ComicIssues':            comic['ComicIssues'],
#        'ComicImage':             comic['ComicImage'],
#        'ComicVolume':            ParseVol,
#        'ComicPublisher':         comic['ComicPublisher']
#        })

#    comic['comicchoice'] = comicchoice
    return comic

def GetIssuesInfo(comicid,dom):
    subtracks = dom.getElementsByTagName('issue')
    if not mylar.CV_ONLY:
        cntiss = dom.getElementsByTagName('count_of_issues')[0].firstChild.wholeText
        logger.fdebug("issues I've counted: " + str(len(subtracks)))
        logger.fdebug("issues CV says it has: " + str(int(cntiss)))

        if int(len(subtracks)) != int(cntiss):
            logger.fdebug("CV's count is wrong, I counted different...going with my count for physicals" + str(len(subtracks)))
            cntiss = len(subtracks) # assume count of issues is wrong, go with ACTUAL physical api count
        cntiss = int(cntiss)
        n = cntiss-1
    else:
        n = int(len(subtracks))
    tempissue = {}
    issuech = []
    firstdate = '2099-00-00'
    for subtrack in subtracks:
        if not mylar.CV_ONLY:
            if (dom.getElementsByTagName('name')[n].firstChild) is not None:
                issue['Issue_Name'] = dom.getElementsByTagName('name')[n].firstChild.wholeText
            else:
                issue['Issue_Name'] = 'None'

            issue['Issue_ID'] = dom.getElementsByTagName('id')[n].firstChild.wholeText
            issue['Issue_Number'] = dom.getElementsByTagName('issue_number')[n].firstChild.wholeText
            
            issuech.append({
                'Issue_ID':                issue['Issue_ID'],
                'Issue_Number':            issue['Issue_Number'],
                'Issue_Name':              issue['Issue_Name']
                })
        else:
            try:
                tempissue['Issue_Name'] = subtrack.getElementsByTagName('name')[0].firstChild.wholeText
            except:
                tempissue['Issue_Name'] = 'None'
            tempissue['Issue_ID'] = subtrack.getElementsByTagName('id')[0].firstChild.wholeText
            try:
                tempissue['CoverDate'] = subtrack.getElementsByTagName('cover_date')[0].firstChild.wholeText
            except:
                tempissue['CoverDate'] = '0000-00-00'
            try:
                tempissue['StoreDate'] = subtrack.getElementsByTagName('store_date')[0].firstChild.wholeText
            except:
                tempissue['StoreDate'] = '0000-00-00'
            try:
                tempissue['Issue_Number'] = subtrack.getElementsByTagName('issue_number')[0].firstChild.wholeText
            except:
                logger.fdebug('No Issue Number available - Trade Paperbacks, Graphic Novels and Compendiums are not supported as of yet.')
            issuech.append({
                'Comic_ID':                comicid,
                'Issue_ID':                tempissue['Issue_ID'],
                'Issue_Number':            tempissue['Issue_Number'],
                'Issue_Date':              tempissue['CoverDate'],
                'Store_Date':              tempissue['StoreDate'],
                'Issue_Name':              tempissue['Issue_Name']
                })

            if tempissue['CoverDate'] < firstdate and tempissue['CoverDate'] != '0000-00-00':
                firstdate = tempissue['CoverDate']
        n-=1

    #issue['firstdate'] = firstdate
    return issuech, firstdate

def GetFirstIssue(issueid,dom):
    #if the Series Year doesn't exist, get the first issue and take the date from that
    try:
        first_year = dom.getElementsByTagName('cover_date')[0].firstChild.wholeText
    except:
        first_year = '0000'
        return first_year

    the_year = first_year[:4]
    the_month = first_year[5:7]
    the_date = the_year + '-' + the_month

    return the_year


def drophtml(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html)

    text_parts = soup.findAll(text=True)
    #print ''.join(text_parts)
    return ''.join(text_parts)
