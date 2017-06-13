#!/usr/bin/env python3

description = '''
DESCRIPTION:
Outputs a list of all EC2 instances in one or more AWS regions.

The list contains specified attributes for each instance and is sorted by a 
specified tag. If an instance does not contain the specified tag then the value 
will be reported as 'unknown'. 

If there is a problem getting the instances in a particular region then a
warning is displayed and processing moves on to the next region.

ASSUMPTIONS:
* Only the public AWS will be inventoried (not China or Gov).
* Attributes of attributes will not be specified to display in lists.

REQUIREMENTS:
* Python3 installed (https://www.python.org/downloads/)
* Boto3 installed (https://github.com/boto/boto3)
* AWS credentials file configured
  (http://boto3.readthedocs.io/en/latest/guide/configuration.html#shared-credentials-file) 

AUTHOR:
Michael Davies (davies.mike@gmail.com)

usage:
'''


#
# Import required modules
#
import sys
import boto3
from pprint import pprint
from datetime import datetime
import argparse



#
# Create global variables
#
AVAILABLE_REGIONS = []	# List of all EC2 available regions
REGIONS = []			# List of regions to inventory
ATTRIBUTES_TO_SHOW = []	# List of attributes to display
TAG_TO_SHOW = ''		# Name of tag to display and sort by
COLUMN_MARGIN = 2		# Number of blank spaces between columns in table
COLUMNS = []			# List of columns in instances table
COLUMN_WIDTHS = {}		# Hash of column names and necessary width of column
DEFAULT_ATTRIBUTES = 'InstanceId,InstanceType,LaunchTime'


#
# Define and parse optional arguments
#
parser = argparse.ArgumentParser(description)
parser.add_argument('--regions', help='Regions to inventory (comma separated). '
					'Defaults to all available regions if not specified.')
parser.add_argument('--tag', help='Tag to display and sort by. '
					'Defaults to "Owner" if not specified.')
parser.add_argument('--attributes', help='Attributes to display (comma '
					'separated). Defaults to '
					'"' + DEFAULT_ATTRIBUTES + '" if not specified.')
ARGS = parser.parse_args()



# ######################  FUNCTION DEFINITIONS  ################################



#
# Print error message and optional data and then exit
#
def fail(message, *data):
	print('ERROR: ' + message)
	if (data):
		pprint(data)
	sys.exit(1)



#
# Print warning message and optional data
#
def warn(message, *data):
	print('WARNING: ' + message)
	if (data):
		pprint(data)



#
# Validate regions and set global variables
#
def init_regions():
	global AVAILABLE_REGIONS
	global REGIONS
	# Get all available regions
	AVAILABLE_REGIONS = boto3.session.Session().get_available_regions('ec2')
	if (len(AVAILABLE_REGIONS) < 1):
		fail('No available regions were returned.')
	if (ARGS.regions == None):
		# Default to all available regions if not set
		REGIONS = AVAILABLE_REGIONS
	else:
		REGIONS = ARGS.regions.split(',')
	# Make sure at least 1 region specified
	if (len(REGIONS) < 1):
		fail('List of regions is empty.')



#
# Validate attributes and set global variables
#
def init_attributes():
	global ATTRIBUTES_TO_SHOW
	if (ARGS.attributes == None):
		ATTRIBUTES_TO_SHOW = DEFAULT_ATTRIBUTES.split(',')
	else:
		ATTRIBUTES_TO_SHOW = ARGS.attributes.split(',')
	# Make sure at least 1 attribute set
	if (len(ATTRIBUTES_TO_SHOW) == 0):
		fail('List of attributes is empty.')



#
# Set tag global variables	
#
def init_tag():
	global TAG_TO_SHOW
	if (ARGS.tag == None):
		TAG_TO_SHOW = 'Owner'
	else:
		TAG_TO_SHOW = ARGS.tag



#
# Set global variables for instances table columns and column widths
#
def init_columns():
	global COLUMNS
	global COLUMN_WIDTHS
	COLUMNS.append(TAG_TO_SHOW)
	COLUMNS.extend(ATTRIBUTES_TO_SHOW)
	for column in COLUMNS:
		COLUMN_WIDTHS[column] = len(column)




#
# Returns width of a specified column name
#
def get_width(column_name):

	if (column_name == None):
		fail('Must specify column name for width.')

	width = COLUMN_WIDTHS.get(column_name)
	
	if (width == None):
		fail('Can\'t get width of column "' + column_name + '"')
		
	return width



#
# Print a pretty instances table from a list of dictionaries
#
def print_table(dict_list):

	# Do nothing if empty list
	if (len(dict_list) == 0):
		return
		
	# Print headings
	heading = ''
	for column in COLUMNS:
		heading = heading + column.ljust(get_width(column) + COLUMN_MARGIN)
	print(heading)
	print('-' * (len(heading) - COLUMN_MARGIN))	

	# Print rows
	for dict in dict_list:
		line = ''
		for column in COLUMNS:
			line = line + dict.get(column, '').ljust(get_width(column) + \
				COLUMN_MARGIN)
		print(line)



#
# Takes a raw instance dictionary and returns a dictionary with only the
# needed data
#
def get_instance_data(instance):

	# Do nothing if no instance specified
	if (instance == None):
		return

	item = {}

	# Get all specified attribute values and update column widths
	for attribute in ATTRIBUTES_TO_SHOW:
		item[attribute] = instance.get(attribute, '(no attribute key)')
		# Convert datetime object to human readable date
		if type(item[attribute]) is datetime:
			item[attribute] = item[attribute].ctime()
		if (len(item[attribute]) > get_width(attribute)):
			COLUMN_WIDTHS[attribute] = len(item[attribute])

	# Get specified tag and update column width
	for tag in instance.get('Tags', []):
		if (tag.get('Key') == TAG_TO_SHOW):
			item[TAG_TO_SHOW] = tag.get('Value', '(no value key)')
	# If specified tag doesn't exist set value to 'unknown'
	if (item.get(TAG_TO_SHOW) == None):
		item[TAG_TO_SHOW] = 'unknown'
	if (len(item[TAG_TO_SHOW]) > get_width(TAG_TO_SHOW)):
		COLUMN_WIDTHS[TAG_TO_SHOW] = len(item[TAG_TO_SHOW])

	return item
		


#
# Returns a list of instance dictionaries in a region. Instance data is based on
# defined tag and attributes.
#
def get_instances(region):

	# Do nothing if no region specified
	if (region == None):
		return

	results = []		# List of dictionaries to return
	next_token = ''		# The token for getting the next group of instances

	# Make sure specified region is available
	if (region not in AVAILABLE_REGIONS):
		warn('Region "' + region + '" is not one of the available regions.')
		return
	
	# Create a client for the region
	try:
		client = boto3.client('ec2', region_name=region)		
	except Exception as e:
		warn('There was a problem creating a client for this region ' + \
				region + '.')
		print(str(e))
		return
		
	# Keep getting instances until there are no more
	while True:

		# Get all the reservations and instances in the region
		try:
			response = client.describe_instances(NextToken=next_token)
		except Exception as e:
			warn('There was a problem getting the instances in the region ' + \
				region + '.')
			print(str(e))
			return
				
		# Get instances from each reservation
		for reservation in response.get('Reservations', []):
			for instance in reservation.get('Instances', []):
		
				# Get important data from instance and add to list of results
				results.append(get_instance_data(instance))

		# Get the token for the next search. Exit the while loop if no results.			
		next_token = response.get('NextToken')
		if (next_token == None):
			break

	# Sort instances by tag
	results = sorted(results, key=lambda k: k[TAG_TO_SHOW])
	
	return results
	
	

#
# Print lists of instances in regions
#
def main():

	# Initialize global variables
	init_regions()
	init_tag()
	init_attributes()
	init_columns()

	# Print list of instances for each region specified
	for region in REGIONS:

		# Print region header
		print('*' * 80)	
		print('REGION: ' + region)
		
		# Get instances in the region
		instances = get_instances(region)

		# If instances were found then print list as table
		if (instances != None):
			print('Instances: ' + str(len(instances)))
			print_table(instances)



# #######################  CALL MAIN FUNCTION  #################################



#
# Call main function
#
if (__name__ == "__main__"):
	main()		
