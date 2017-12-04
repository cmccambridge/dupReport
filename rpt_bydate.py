#####
#
# Module name:  report4.py
# Purpose:      dupReport grouped by date
# 
# Notes:
#
#####

# Import system modules
import datetime
import time
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import re

# Import dupReport modules
import globs
import db
import drdatetime
import report


def runReport(startTime):
    globs.log.write(1, 'report4()')

    # Get header and column info
    nFields = len(report.rptColumns)        # Number of fields used in this report
    fldDefs = report.fldDefs                # Field definitions table
    reportOpts = globs.report.reportOpts    # Report Options
    rptCols = report.rptColumns             # Columns used in this report
    rptTits = globs.report.reportTits       # Titles for columns in report

    # Start HTML and text messages
    # Table border and padding settings
    msgHtml='<html><head></head><body><table border={} cellpadding="{}">'.format(reportOpts['border'], reportOpts['padding'])
    msgText = ''
    msgCsv = ''

    # Report title
    msgHtml += '<tr><td align="center" colspan = "{}" bgcolor="{}"><b>{}</b></td></tr>'.format(nFields, reportOpts['titlebg'], reportOpts['reporttitle'])
    msgText += reportOpts['reporttitle'] + '\n'
    msgCsv += '\"' + reportOpts['reporttitle'] + '\"\n'

    # Column headings - HTML Message
    msgHtml += '<tr>'

    # Remove columns we don't need for this report
    # These are already part of the report logic processing & subheaders
    # We won't need to loop through them for the report fields
    rptCols.remove('date')

    # Now, generate headings for the columns that are left
    # Some may have been removed in the .rc file configuration, [headings] section
    for col in rptCols:
        msgHtml += report.printTitle(col, 'html')
        msgText += report.printTitle(col, 'text')
        msgCsv += report.printTitle(col, 'csv')

    # End of column headings row
    msgHtml += '</tr>'
    msgText += '\n'
    msgCsv += '\n'

    # Get earliest & latest timestamps in the report table
    dbCursor = globs.db.execSqlStmt("SELECT min(timestamp) FROM report")    # Smallest timestamp in the report table
    currentTs = dbCursor.fetchone()[0]
    dbCursor = globs.db.execSqlStmt("SELECT max(timestamp) FROM report")    # Largest timestamp in the report table
    highestTs = dbCursor.fetchone()[0]

    while currentTs <= highestTs:
        currentDate, currentTime = drdatetime.fromTimestamp(currentTs, dfmt='YYYY/MM/DD', tfmt='HH:MM:SS')
        currentDateBeginTs = drdatetime.toTimestamp(currentDate + ' 00:00:00', dfmt='YYYY/MM/DD', tfmt='HH:MM:SS')  # Convert the string into a timestamp
        currentDateEndTs = drdatetime.toTimestamp(currentDate + ' 23:59:59', dfmt='YYYY/MM/DD', tfmt='HH:MM:SS')  # Convert the string into a timestamp
        
        sqlStmt = "SELECT source, destination, timestamp, examinedFiles, examinedFilesDelta, sizeOfExaminedFiles, fileSizeDelta, \
            addedFiles, deletedFiles, modifiedFiles, filesWithError, parsedResult, messages, warnings, errors \
            FROM report WHERE timestamp >= {} AND timestamp <= {}".format(currentDateBeginTs, currentDateEndTs)
        if reportOpts['sortby'] == 'source':
            sqlStmt += ' ORDER BY source, destination'
        elif reportOpts['sortby'] == 'destination':
            sqlStmt += ' ORDER BY destination, source'
        else:
            sqlStmt += ' ORDER BY timestamp'

        dbCursor = globs.db.execSqlStmt(sqlStmt)
        reportRows = dbCursor.fetchall()
        globs.log.write(3, 'reportRows=[{}]'.format(reportRows))

        if len(reportRows) != 0:
            subHead = globs.optionManager.getRcOption('report', 'subheading')
            if subHead is not None:
                    subHead = subHead.replace('#DATE#', currentDate)
            if subHead is None or subHead == '':
                msgHtml += '<tr><td colspan={} align="center" bgcolor="{}"><b>{}:</b> {}</td></tr>'.format(nFields, reportOpts['subheadbg'], rptTits['date'], currentDate)
                msgText += '***** {}: {} *****\n'.format(rptTits['date'], currentDate)
                msgCsv += '\"***** {}: {} *****\"\n'.format(rptTits['date'], currentDate)
            else:
                msgHtml += '<tr><td colspan={} align="center" bgcolor="{}">{}</td></tr>'.format(nFields, reportOpts['subheadbg'], subHead)
                msgText += '***** {} *****\n'.format(subHead)
                msgCsv += '\"***** {} *****\",\n'.format(subHead)

        for source, destination, timestamp, examinedFiles, examinedFilesDelta, sizeOfExaminedFiles, fileSizeDelta, \
            addedFiles, deletedFiles, modifiedFiles, filesWithError, parsedResult, messages, \
            warnings, errors in reportRows:
            
            # Get date and time from timestamp
            dateStr, timeStr = drdatetime.fromTimestamp(timestamp)

            # Print report fields
            # Each field takes up one column/cell in the table
            msgHtml += '<tr>'

            # The full list of possible fields in the report. printField() below will skip a field if it is emoved in the .rc file.
            titles = ['source', 'destination','time', 'files', 'filesplusminus', 'size', 'sizeplusminus', 'added', 'deleted', 'modified', 'errors', 'result']
            fields = [source, destination, timeStr, examinedFiles, examinedFilesDelta, sizeOfExaminedFiles, fileSizeDelta, addedFiles, deletedFiles,  modifiedFiles, filesWithError, parsedResult]

            for ttl, fld in zip(titles, fields):
                msgHtml += report.printField(ttl, fld, 'html')
                msgText += report.printField(ttl, fld, 'text')
                msgCsv += report.printField(ttl, fld, 'csv')

            msgHtml += '</tr>'
            msgText += '\n'
            msgCsv += '\n'

            fields = [messages, warnings, errors ]
            options = ['displaymessages', 'displaywarnings', 'displayerrors']
            backgrounds = ['jobmessagebg', 'jobwarningbg', 'joberrorbg']
            titles = ['jobmessages', 'jobwarnings', 'joberrors']

            # Print message/warning/error fields
            # Each of these spans all the table columns
            for fld, opt, bg, tit in zip(fields, options, backgrounds, titles):
                if ((fld != '') and (reportOpts[opt] == True)):
                    msgHtml += '<tr><td colspan="{}" align="center" bgcolor="{}">{}: {}</td></tr>'.format(nFields, reportOpts[bg], rptTits[tit], fld)
                    msgText += '{}: {}\n'.format(rptTits[tit], fld)
                    msgCsv += '\"{}: {}\",\n'.format(rptTits[tit], fld)


        # Move current timestamp ahead 1 second
        currentTs = currentDateEndTs + 1

    # Now see which systems didn't report in
    dbCursor = globs.db.execSqlStmt("SELECT source, destination, lastTimestamp FROM backupsets ORDER BY source, destination")
    setRows = dbCursor.fetchall()
    globs.log.write(3, 'setRows=[{}]'.format(setRows))

    # Flag to let us know if we need to print a header for missing backupsets
    hdrFlag = 0
    for source, destination, lastTimestamp in setRows:
        dbCursor = globs.db.execSqlStmt("SELECT count(*) FROM report WHERE source = \'{}\' AND destination = \'{}\'".format(source, destination))
        seenRows = dbCursor.fetchone()[0]
        globs.log.write(3, 'seenRows=[{}]'.format(seenRows))
        if seenRows == 0:   # Didn't get any rows for source/Destination pair. Add to report
            if hdrFlag == 0:
                msgHtml += '<tr><td colspan={} align="center" bgcolor="{}"><b>Missing Backup Sets</b></td></tr>'.format(nFields, reportOpts['subheadbg'])
                msgText += 'Missing Back Sets\n'
                msgCsv += '\"Missing Back Sets\"\n'
                hdrFlag = 1

            nowTimestamp = datetime.datetime.now().timestamp()
            now = datetime.datetime.fromtimestamp(nowTimestamp)
            then = datetime.datetime.fromtimestamp(lastTimestamp)
            diff = (now-then).days

            lastDateStr, lastTimeStr = drdatetime.fromTimestamp(lastTimestamp)
            msgHtml += '<tr><td colspan={} align="center">{} to {}: <i>No new activity. Last activity on {} at {} ({} days ago)</i></td></tr>'.format(nFields, source, destination, lastDateStr, lastTimeStr, diff)
            msgText += '{} to {}: No new activity. Last activity on {} at {} ({} days ago)\n'.format(source, destination, lastDateStr, lastTimeStr, diff)
            msgCsv += '\"{} to {}: No new activity. Last activity on {} at {} ({} days ago)\"\n'.format(source, destination, lastDateStr, lastTimeStr, diff)

    # Add final rows & close
    runningTime = 'Running Time: {:.3f} seconds.'.format(time.time() - startTime)
    msgHtml += '<tr><td colspan={} align="center"><b>{}</b></td></tr>'.format(nFields, runningTime)
    msgHtml += '</table></body></html>'
    msgText += runningTime + '\n'
    msgCsv += '\"' + runningTime + '\"\n'

    # Return text & HTML messages to main program. It can decide which one it wants to use.
    return msgHtml, msgText, msgCsv

