#!/usr/bin/python

"""
This script will derive the time of sunset and sunrise at your location from
your external IP address and then set the IR mode on your camera accordingly.

While my camera *tries* to do this on it's own when the IR is enabled, at
twilight in mornings and evenings it switches the IR ON/OFF/ON/OFF/ON...for
several minutes. Changing the IR setting causes a relay to click so this is
super annoying and often wakes up our son.

This service causes the camera to turn IR off *once* in the morning, and
*once* in the evening.
"""

import datetime
import httplib
import json
import os.path
import time
import urllib

import geoip2.database  # from MaxMind
import ephem            # from pip

import foscam           # from https://github.com/drakkhen/pyfoscam

def format_timedelta(td):
    return str(td).split('.')[0]

class FoscamIRService:

    def __init__(self, geolite2_city_path):
        self.geolite2_city_path = geolite2_city_path
        self.foscam = foscam.Foscam()

        self.get_external_ip()
        self.get_geoip(self.external_ip, geolite2_city_path)

        lat = self.geoip.location.latitude
        lng = self.geoip.location.longitude
        city = self.geoip.city.name
        state = self.geoip.subdivisions.most_specific.name

        self.get_elevation(lat, lng)

        print "-" * 70
        print "IP Address:  %s" % self.external_ip
        print "Location:    (%f, %f) [%s, %s]" % (lat, lng, city, state)
        print "Elevation:   %d meters" % self.elevation
        print "-" * 70

    def get_external_ip(self):
        conn = httplib.HTTPConnection('ifconfig.me', 80)
        conn.request('GET', '/', headers={ 'User-Agent': 'curl/7.30.0' })
        resp = conn.getresponse()
        self.external_ip = resp.read().strip()

    def get_geoip(self, ip, geolite2_city_path):
        reader = geoip2.database.Reader(geolite2_city_path)
        self.geoip = reader.city(ip)

    def get_elevation(self, lat, lng):
        params = urllib.urlencode({'locations': '%s,%s' % (lat, lng), 'sensor': 'true'})
        full_path = "/maps/api/elevation/json?%s" % params
        conn = httplib.HTTPConnection('maps.googleapis.com')
        conn.request('GET', full_path)
        resp = conn.getresponse()
        data = json.loads(resp.read())
        self.elevation = data['results'][0]['elevation']

    def is_nighttime(self):
        observer = ephem.Observer()
        observer.lat = str(self.geoip.location.latitude)  # these MUST be a Strings!
        observer.long = str(self.geoip.location.longitude)
        observer.elevation = self.elevation

        sun = ephem.Sun()
        sun.compute(observer)

        nextrise = observer.next_rising(sun).datetime()
        nextset = observer.next_setting(sun).datetime()

        it_is_night = nextrise < nextset

        fmt = '%H:%M:%S'

        # printing some helpful output
        if it_is_night:
            rises_in = nextrise - datetime.datetime.utcnow()
            local_rises_at = (datetime.datetime.now() + rises_in).strftime(fmt)
            print "The sun rises in %s at %s local time" % (format_timedelta(rises_in), local_rises_at)
        else:
            sets_in = nextset - datetime.datetime.utcnow()
            local_sets_at = (datetime.datetime.now() + sets_in).strftime(fmt)
            print "The sun sets in %s at %s local time" % (format_timedelta(sets_in), local_sets_at)

        return it_is_night

    def loop(self):
        while True:
            self.foscam.nightvision(self.is_nighttime())
            time.sleep(60)

if __name__ == "__main__":
    geoip_data = os.path.expanduser('~/data/MaxMind/GeoLite2-City.mmdb')
    service = FoscamIRService(geolite2_city_path=geoip_data)
    service.loop()
