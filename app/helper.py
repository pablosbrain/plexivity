#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import xml.etree.ElementTree as ET
import logging
import datetime

from flask.ext.babel import gettext as _
from apscheduler.schedulers.background import BackgroundScheduler

from app import logger
from app import config, plex, notify

sched_logger = logging.getLogger("apscheduler")
sched_logger.addHandler(logger.rotation)
sched_logger.setLevel(logging.DEBUG)
logger = logger.logger.getChild('helper')


def currentlyPlaying():
    print "job fired"
    logger.info("running job")


def startScheduler():
    try:
        import tzlocal

        tz = tzlocal.get_localzone().zone
        logger.info("local timezone: %s" % tz)
    except:
        logger.error("Unable to find locale timezone useing Europe/Berlin as Fallback!")
        tz = 'Europe/Berlin'
    #in debug mode this is executed twice :(
    #DONT run flask in auto reload mode when testing this!
    scheduler = BackgroundScheduler(logger=sched_logger, timezone=tz)
    scheduler.add_job(notify.task, 'interval', seconds=config.SCAN_INTERVAL, max_instances=1,
                      start_date=datetime.datetime.now() + datetime.timedelta(seconds=2))
    scheduler.start()
    #notify.task()


def calculate_plays(db, models, username):
    to_return = list()
    today = db.session.query(models.Processed).filter(models.Processed.user == username).filter(
        models.Processed.stopped >= datetime.datetime.now() - datetime.timedelta(hours=7))
    week = db.session.query(models.Processed).filter(models.Processed.user == username).filter(
        models.Processed.stopped >= datetime.datetime.now() - datetime.timedelta(days=1))
    month = db.session.query(models.Processed).filter(models.Processed.user == username).filter(
        models.Processed.stopped >= datetime.datetime.now() - datetime.timedelta(days=30))
    alltime = db.session.query(models.Processed).filter(models.Processed.user == username)

    today_time = datetime.timedelta()
    for row in today.all():
        if row.paused_counter:
            today_time += row.stopped - row.time - datetime.timedelta(seconds=row.paused_counter)
        else:
            today_time += row.stopped - row.time

    week_time = datetime.timedelta()
    for row in week.all():
        if row.paused_counter:
            week_time += row.stopped - row.time - datetime.timedelta(seconds=row.paused_counter)
        else:
            week_time += row.stopped - row.time

    month_time = datetime.timedelta()
    for row in month.all():
        if row.paused_counter:
            month_time += row.stopped - row.time - datetime.timedelta(seconds=row.paused_counter)
        else:
            month_time += row.stopped - row.time

    alltime_time = datetime.timedelta()
    for row in alltime.all():
        if row.paused_counter:
            alltime_time += row.stopped - row.time - datetime.timedelta(seconds=row.paused_counter)
        else:
            alltime_time += row.stopped - row.time

    to_return.append({"plays": today.count(), "time": today_time, "name": "Today"})
    to_return.append({"plays": week.count(), "time": week_time, "name": "Last Week"})
    to_return.append({"plays": month.count(), "time": month_time, "name": "Last Month"})
    to_return.append({"plays": alltime.count(), "time": alltime_time, "name": "All Time"})
    # to_return["weekly"] = {"plays": week.count(), "time": week_time}
    # to_return["monthly"] = {"plays": month.count(), "time": month_time}
    # to_return["all"] = {"plays": alltime.count(), "time": alltime_time}
    return to_return


def statistics():
    pass


def date_timestamp(date):
    import time

    return time.mktime(date.timetuple())


def load_xml(string):
    xml = ET.fromstring(string)
    return xml


def xml_to_string(xml):
    try:
        return xml.tostring()
    except:
        return ET.tostring(xml)


def getPercentage(viewed, duration):
    if not viewed or not duration:
        return 0

    percent = "%2d" % ((float(viewed) / float(duration)) * 100)

    if int(percent) >= 90:
        return 100
    return percent


def cache_file(filename, plex):
    cache_dir = os.path.join(config.DATA_DIR, "cache")
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)
    cache_file = os.path.join(cache_dir, filename)
    if not os.path.exists(os.path.split(cache_file)[0]):
        os.makedirs(os.path.split(cache_file)[0])
    img_data = plex.get_thumb_data(filename)
    if img_data:
        f = open(cache_file + ".jpg", "wb")
        f.write(img_data)
        f.close()
        return True

    return False


def pretty_date(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    from datetime import datetime

    now = datetime.now()
    if float(time):
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time
    else:
        diff = now - now

    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return _("just now")
        if second_diff < 60:
            return _("%(int)s seconds ago", int=second_diff)
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return _("%(int)s minuten ago", int=second_diff / 60)
        if second_diff < 7200:
            return _("an hour ago")
        if second_diff < 86400:
            return _("%(int)s hours ago", int=second_diff / 3600)
    if day_diff == 1:
        return _("Yesterday")
    if day_diff < 7:
        return _("%(int)s days ago", int=day_diff)
    if day_diff < 31:
        return _("%(int)s weeks ago", int=day_diff / 7)
    if day_diff < 365:
        return _("%(int)s months ago", int=day_diff / 30)
    return _("%(int)s years ago", int=day_diff / 365)


def notifyer():
    ### onyl basic tests here
    # TODO: move this to a extra file and include DB support!
    p = plex.Server(config.PMS_HOST, config.PMS_PORT)
    sessions = p.currentlyPlaying()

    for session in sessions:
        if session.get("type") == "episode":
            title = '%s - "%s"' % (session.get("grandparentTitle"), session.get("title"))
        else:
            title = session.get("title")

        offset = int(session.get("viewOffset")) / 1000 / 60
        username = session.find("User").get("title")
        platform = session.find("Player").get("platform")
        product = session.find("Player").get("product")
        player_title = session.find("Player").get("product")

        if session.find("Player").get("state") == "paused":
            message = config.PAUSE_MESSAGE % {"username": username, "platform": platform, "title": title,
                                              "product": product, "player_title": player_title, "offset": offset}
        elif session.find("Player").get("state") == "playing":
            message = config.START_MESSAGE % {"username": username, "platform": platform, "title": title,
                                              "product": product, "player_title": player_title, "offset": offset}
        else:
            message = config.STOP_MESSAGE % {"username": username, "platform": platform, "title": title,
                                             "product": product, "player_title": player_title, "offset": offset}

        if config.NOTIFY_PUSHOVER and message:
            from app.providers import pushover

            pushover.send_notification(message)


def playerImage(platform):
    if platform == "Roku":
        return "images/platforms/roku.png"
    elif platform == "Apple TV":
        return "images/platforms/appletv.png"
    elif platform == "Firefox":
        return "images/platforms/firefox.png"
    elif platform == "Chromecast":
        return "images/platforms/chromecast.png"
    elif platform == "Chrome":
        return "images/platforms/chrome.png"
    elif platform == "Android":
        return "images/platforms/android.png"
    elif platform == "Nexus":
        return "images/platforms/android.png"
    elif platform == "iPad":
        return "images/platforms/ios.png"
    elif platform == "iPhone":
        return "images/platforms/ios.png"
    elif platform == "iOS":
        return "images/platforms/ios.png"
    elif platform == "Plex Home Theater":
        return "images/platforms/pht.png"
    elif platform == "Linux/RPi-XBMC":
        return "images/platforms/xbmc.png"
    elif platform == "Safari":
        return "images/platforms/safari.png"
    elif platform == "Internet Explorer":
        return "images/platforms/ie.png"
    elif platform == "Unknown Browser":
        return "images/platforms/default.png"
    elif platform == "Windows-XBMC":
        return "images/platforms/xbmc.png"
    else:
        return "images/platforms/default.png"
