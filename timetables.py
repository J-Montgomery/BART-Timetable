#! /usr/bin/env python3
from bs4 import BeautifulSoup
import requests
import datetime 
import re

class TablePrinter(object):
    "Print a list of dicts as a table"
    def __init__(self, fmt, sep=' ', ul=None):
        """        
        @param fmt: list of tuple(heading, key, width)
                        heading: str, column label
                        key: dictionary key to value to print
                        width: int, column width in chars
        @param sep: string, separation between columns
        @param ul: string, character to underline column label, or None for no underlining
        """
        super(TablePrinter,self).__init__()
        self.fmt   = str(sep).join('{lb}{0}:{1}{rb}'.format(key, width, lb='{', rb='}') for heading,key,width in fmt)
        self.head  = {key:heading for heading,key,width in fmt}
        self.ul    = {key:str(ul)*width for heading,key,width in fmt} if ul else None
        self.width = {key:width for heading,key,width in fmt}

    def row(self, data):
        return self.fmt.format(**{ k:str(data.get(k,''))[:w] for k,w in self.width.iteritems() })

    def __call__(self, dataList):
        _r = self.row
        res = [_r(data) for data in dataList]
        res.insert(0, _r(self.head))
        if self.ul:
            res.insert(1, _r(self.ul))
        return '\n'.join(res)

def get_current_bart_api_key(use_default=True):
	bart_public_key_url = "https://www.bart.gov/schedules/developers/api"
	default_bart_api_key = "MW9S-E7SL-26DU-VV8V"
	
	if(use_default == True):
		return default_bart_api_key

	r = requests.get(bart_public_key_url)
	soup = BeautifulSoup(r.text, 'html.parser')
	keys = soup.findAll('span', {'face':'Courier New'})
	
	if(len(keys) == 0):
		print("Found no API keys, using default of {}".format(default_bart_api_key))
		return default_bart_api_key
	else:
		groups = [re.search(r"\w+(-\w+){2,}-\w+", str(x)) for x in keys]
		potential_keys = [x for x in groups if x is not None]
		key = potential_keys[0].group(0)
		if(len(potential_keys) > 1):
			print("Found multiple matches {0}, defaulting to {1}".format(potential_keys, key))
		else:
			print("Found API key: {}".format(key))
		return key

def get_station_sched(station, date, key):
	api_url = 'http://api.bart.gov/api/sched.aspx?cmd=stnsched'
	api_url += '&orig=' + station
	api_url += '&date=' + date
	api_url += '&key=' + key
	r = requests.get(api_url)
	soup = BeautifulSoup(r.text, 'lxml')
	trains = [x.attrs for x in soup.find_all('item')]
	return trains

def parse_train_time(minutes):
	try:
		return int(minutes)
	except ValueError as e:
		if(minutes.lower() == 'leaving'):
			return 0
		else:
			print(e)
			return 0

def parse_train_delay(minutes):
	try:
		return int(minutes)
	except ValueError as e:
		print(e)
		return 0

def compute_departure_time(timebase, offset, delay):
	offset = offset + delay
	t = timebase + datetime.timedelta(minutes=offset)
	return t.strftime('%I:%M %p')

def parse_rtd(data):
	for dest in data:
		timebase = datetime.datetime.now()
		sched = {'dest_name' : dest.find('destination').text,
				 'dest' : dest.find('abbreviation').text}
		sched['minutes'] = [parse_train_time(x.text) for x in dest.find_all('minutes')]
		sched['delay'] = [parse_train_delay(x.text) for x in dest.find_all('delay')]

		# Ideally, we'd use the delay time in this calculation,
		# but the data returned by BART's API often includes ridiculous delays >1h
		# Instead we use a delay of 0
		sched['times'] = [compute_departure_time(timebase, m, 0) 
							for m, d in zip(sched['minutes'], sched['delay'])
							]
		yield sched

def get_station_rtd(station, key):
	api_url = 'http://api.bart.gov/api/etd.aspx?cmd=etd'
	api_url += '&orig=' + station
	api_url += '&key=' + key

	r = requests.get(api_url)
	soup = BeautifulSoup(r.text, 'lxml')
	dests = [x.find_parent() for x in soup.find_all('destination')]
	return list(parse_rtd(dests))
	
def get_route_departures(orig_station, dest, key):
	rtd = get_station_rtd(orig_station, key)
	routes = list(filter(lambda x: True if x['dest'].lower() == dest.lower() else None, rtd))
	if(routes is not []):
		dest_rtd = routes[0]
		return [{	'name' : dest_rtd['dest_name'],
					'dest' : dest_rtd['dest'],
					'time' : t,
					'delay': d} for t, d in zip(dest_rtd['times'], dest_rtd['delay'])]

if __name__ == "__main__":
	bart_api_key = get_current_bart_api_key()
	# all_departures = [{	'name': x['trainheadstation'], 'time': x['origtime']} 
	# 					for x in get_station_sched("CIVC", "today", bart_api_key)]
	# dubl_departures = filter(lambda x: x, 
	# 					[	x if x['name'] == 'Dublin/Pleasanton' else None 
	# 					for x in all_departures])

	# fmt = [
	# 	('Destination', 'name', 20),
	# 	('Scheduled Departure',   'time', 20),
	# ]
	# print( TablePrinter(fmt, ul='=')(dubl_departures) )

	departures = get_route_departures("CIVC", "DUBL", bart_api_key)
	fmt = [
		('Destination', 'name', 17),
		('Departure',   'time', 9),
		('Delay',   'delay', 5),
	]
	print( TablePrinter(fmt, ul='=')(departures) )
