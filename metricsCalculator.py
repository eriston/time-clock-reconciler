import os
import csv
import logging
import pandas as pd
from pprint import pprint

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = logging.FileHandler('debugLog.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('')
logger.info('_')
logger.info('__')
logger.info('running metricsCalculator')


INPUT_FILE_DIRECTORY = '/home/user/Desktop/data'


def read_input_files(input_file_dir):
    # read the input files from the source directory by name and parse

    scheduledShifts = list()
    clockedTime = list()

    logger.info('Reading Files From: ' + input_file_dir)
    file_names = os.listdir(input_file_dir)
    os.chdir(INPUT_FILE_DIRECTORY)
    file_names = [os.path.abspath(x) for x in file_names]
    logger.debug('File Names Found: ' + str(file_names))
    file_names = [x for x in file_names if x.endswith('.csv')]
    logger.debug('File Names Found: ' + str(file_names))
    cribsheet_file_names = [x for x in file_names if ('Report - CribSheets' in x)]
    logger.debug('Cribsheets Found: ' + str(cribsheet_file_names))
    timeclock_file_names = [x for x in file_names if ('Report - TimeClock' in x)]
    logger.debug('Timeclock Files Found: ' + str(timeclock_file_names))

    for cribsheet in cribsheet_file_names:
        fileContents = list()
        with open(cribsheet, 'r') as f:
            headerRow = f.readline()
            headerRow = headerRow.replace("Date", "Start Date")
            headerRow = headerRow.strip().split(',')

            reader = csv.reader(f)
            for row in reader:
                rowContents = {}
                for i in xrange(len(headerRow)):
                    rowContents[headerRow[i]] = row[i]

                rowContents['End Time'] = rowContents['End Time'].replace(":", "")
                rowContents['Start Time'] = rowContents['Start Time'].replace(":", "")
                if int(rowContents['End Time']) < int(rowContents['Start Time']):
                    rowContents['End Date'] = addOneDayToDate(rowContents['Start Date'])
                else:
                    rowContents['End Date'] = rowContents['Start Date']
                fileContents.append(rowContents)

        scheduledShifts.extend(fileContents)


    for timeclock in timeclock_file_names:
        fileContents = []
        with open(timeclock, 'r') as f:
            headerRow = f.readline()
            headerRow = headerRow.replace('","', ';')
            headerRow = headerRow.replace(',"', ';')
            headerRow = headerRow.replace('",', ';')
            headerRow = headerRow.strip().split(';')
            numberOfDays = len(headerRow)-2

            reader = csv.reader(f)
            for row in reader:

                # data provided as csv but some data cells contain commas
                for i in xrange(1,len(row)-1):
                    while len(row[i]) > 0 and "-" in row[i] and "/" not in row[i]:
                        row[i] = row[i]+";"+row[i+1]
                        del row[i+1]
                        row.append('')

                for day in xrange(1, numberOfDays+1):
                    if len(row[day]) > 0:
                        for event in row[day].split(";"):
                            clockEvent = dict()
                            clockEvent['Employee'] = row[0]
                            clockEvent['Start Date'] = headerRow[day]
                            # replace a unicode dash
                            event = event.replace("\xe2\x80\x93", "-")
                            event = event.replace(":", "")
                            # drop the internal hours calculation
                            event = event.split('/')[0].strip()
                            startTime, endTime = event.split(' - ')
                            clockEvent['Start Time'] = startTime
                            clockEvent['End Time'] = endTime
                            if int(endTime) < int(startTime):
                                clockEvent['End Date'] = addOneDayToDate(clockEvent['Start Date'])
                            else:
                                clockEvent['End Date'] = clockEvent['Start Date']
                            clockEvent['Used'] = False
                            fileContents.append(clockEvent)


        clockedTime.extend(fileContents)

        clockedTimeByName = dict()
        for x in clockedTime:
            if x['Employee'] in clockedTimeByName.keys():
                clockedTimeByName[x['Employee']].append(x)
            else:
                newlist = list()
                newlist.append(x)
                clockedTimeByName[x['Employee']] = newlist
                pprint (clockedTimeByName)

        return scheduledShifts, clockedTime, clockedTimeByName

def addOneDayToDate(oldDate):
    newDate = pd.to_datetime(oldDate) + pd.DateOffset(days=1)
    newDate = newDate.strftime('%b %d, %Y')
    return newDate

def calculateTimeOverlap(scheduledStart, scheduledEnd, clockIn, clockOut):
    overlap = 0
    percentOverlap = 0.0
    scheduledStart = pd.to_datetime(scheduledStart)
    scheduledEnd = pd.to_datetime(scheduledEnd)
    clockIn = pd.to_datetime(clockIn)
    clockOut = pd.to_datetime(clockOut)

    if scheduledEnd < clockIn or scheduledStart > clockOut:
        return overlap, percentOverlap

    start = max(scheduledStart, clockIn)
    end = min(scheduledEnd, clockOut)
    overlap = end - start
    overlap = overlap.seconds
    overlapRange = max(scheduledEnd, clockOut) - min(scheduledStart, clockIn)
    overlapRange = overlapRange.seconds
    percentOverlap = overlap / (float(overlapRange) + 0.000001)
    percentOverlap = round(percentOverlap, 2)
    if overlap < 0:
        overlap = 0
        percentOverlap = 0.0
        return overlap, percentOverlap
    else:
        return overlap, percentOverlap


def matchScheduleToClockInTimes(scheduleShifts, clockedTimeByName):
    matchedShifts = []
    totalShiftsMatched = 0
    for shift in scheduledShifts:
        employee = shift['Employee']
        scheduledStart = shift['Start Date']+" "+shift['Start Time']
        scheduledEnd = shift['End Date']+" "+shift['End Time']

        # some people on the schedule never clock in
        if employee in clockedTimeByName.keys():
            employeeClockIns = clockedTimeByName[employee]

            maxOverlap = -1000
            maxOverlapPercent = -1.0
            bestOverlap = -1000
            for i in xrange(len(employeeClockIns)):
                clockIn = employeeClockIns[i]['Start Date']+" "+employeeClockIns[i]['Start Time']
                clockOut = employeeClockIns[i]['End Date']+" "+employeeClockIns[i]['End Time']
                overlap, percentOverlap = calculateTimeOverlap(scheduledStart, scheduledEnd, clockIn, clockOut)
                if percentOverlap > maxOverlapPercent:
                    maxOverlap = overlap
                    maxOverlapPercent = percentOverlap
                    bestOverlap = i

            if maxOverlap > 0:
                clockIn = employeeClockIns[bestOverlap]['Start Date']+" "+employeeClockIns[bestOverlap]['Start Time']
                clockOut = employeeClockIns[bestOverlap]['End Date']+" "+employeeClockIns[bestOverlap]['End Time']
                shift['Clock In'] = clockIn
                shift['Clock Out'] = clockOut
                shift['Seconds Overlap'] = maxOverlap
                shift['Percent Overlap'] = maxOverlapPercent
                del employeeClockIns[bestOverlap]
                clockedTimeByName[employee] = employeeClockIns
            totalShiftsMatched += 1
            print totalShiftsMatched,
            print "-- " + str(maxOverlap) + " " + str(maxOverlapPercent) + " ",
            print " matched shift ",
            print shift
            matchedShifts.append(shift)

    return matchedShifts, clockedTimeByName

if __name__ == '__main__':
    print 'running module'
    scheduledShifts, clockedTime, clockedTimeByName = read_input_files(INPUT_FILE_DIRECTORY)

    matchedShifts, leftoverClockIns = matchScheduleToClockInTimes(scheduledShifts, clockedTimeByName)
    leftoverClockIns_flattened = list()
    for x in leftoverClockIns.keys():
        leftoverClockIns_flattened.extend(leftoverClockIns[x])

    df = pd.DataFrame(matchedShifts)
    df_leftoverClockIns = pd.DataFrame(leftoverClockIns_flattened)

    df.to_csv('matchedClockings.csv')
    df_leftoverClockIns.to_csv('unmatchedClockins.csv')
