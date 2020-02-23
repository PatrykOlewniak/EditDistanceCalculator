# -*- coding: utf-8 -*-

import edlib
import re
import os
import html2text
from files.reportTemplate import template

# TODO: Move huge classes and mmethods into smaller ones.
# TODO:

class Cigar(object):
    """Container for Cigar string based on Edlib output"""

    @staticmethod
    def cigarStringToOperationsList(cigarString):
        """ Transforms cigar to list of separated simple operations (as tuples)
            First tuple element is a action((X-mismatch, D-deletion, =-equals, I-insertion)
            Second one is length of operations
        >>> Cigar.cigarStringToOperationsList("73=3X1D1=1X1D1=2X2D5=")
        [('=', 73), ('X', 3), ('D', 1), ('=', 1), ('X', 1), ('D', 1), ('=', 1), ('X', 2), ('D', 2), ('=', 5)]
        >>> Cigar.cigarStringToOperationsList(34589348)
        -1
        >>> Cigar.cigarStringToOperationsList(['73=', '3X', '1D', '1=', '1X'])
        -1
        """
        if (type(cigarString) == str): # or type(cigarString) == unicode): #TODO: remove it (it's Py3+ now)
            cigarAsList = re.findall('(\d+[XIMD=])', cigarString)
            # cigarAsList example: ['73=', '3X', '1D', '1=', '1X', '1D', '1=', '2X', '2D']
            cigarAsListOfOperations = cigarAsList[:]
            for opIndex in range(0, len(cigarAsListOfOperations)):
                if cigarAsListOfOperations[opIndex][-1] == "D" or "I" or "=" or "X":
                    cigarAsListOfOperations[opIndex] = (str(cigarAsListOfOperations[opIndex][-1]), int(cigarAsListOfOperations[opIndex][:-1]))
            return cigarAsListOfOperations
        else:
            return -1

    @staticmethod
    def getCalculatedOperations(cigarString):
        """
        Calculates indexes for all actions included in CigarString and returns operations log as list
        Returns list of tuples (action, startIndex, endIndex, editLength)  !!!BASED ON FILE2!!!
                about indexes: <startIndex:endIndex) right-open interval!

        >>> Cigar.getCalculatedOperations("73=3X1D1=1X1D")
        [('=', 0, 73, 73), ('X', 73, 76, 3), ('D', 76, 77, 1), ('=', 76, 77, 1), ('X', 77, 78, 1), ('D', 78, 79, 1)]
        >>> Cigar.getCalculatedOperations("34902834")
        []
        """

        cigarAsBasicOperationList = Cigar.cigarStringToOperationsList(cigarString)
        cursor = 0  # loc of cursor of editing file
        operationsLog = []  # operations log list
        lastInsertion = 0  # shift
        for operation in cigarAsBasicOperationList:
            if operation[0] == "D": #DELETION
                operationsLog.append((operation[0], cursor, cursor + operation[1], operation[1]))
            if operation[0] == "=": #EQUALS
                operationsLog.append((operation[0], cursor, cursor + operation[1], operation[1]))
                cursor += operation[1]
            if operation[0] == "I": #INSERTION
                operationsLog.append((operation[0], cursor, cursor + operation[1], operation[1]))
                cursor += operation[1]
                lastInsertion = lastInsertion + operation[1]
            if operation[0] == "X": #MISSMATCH = SUBSTITUTION
                operationsLog.append((operation[0], cursor, cursor + operation[1], operation[1]))
                cursor += operation[1]
        return operationsLog


class EditDistance(object):
    """
    Main class for EditDistance. Calculations based on edlib

    >>> stringA = "<head><title>What are the socio-economic impacts of genetically...</title></head>"
    >>> stringB = "<head><title>Investigating the effects of mobile bottom fishing...</title></head>"
    >>> ED1 = EditDistance(stringA, stringB)
    >>> ED1.editDistance
    42
    >>> ED1.cigarString
    '13=3X2D1=1X1D1=2X2D5=8X1=2X1=2X1I1=4X1D1=1X1I1=1X1=4X1I1=2X3I18='
    """
    def __init__(self, string1, string2):
        self.string1 = string1
        self.string2 = string2
        self.editDistance = None
        self.cigarString = None  # cigar string (Sequence Alignment/Map format) "73=3X1D1="(edlib output for operations)
        self._setEditDitanceAndCigar()



    def _setEditDitanceAndCigar(self):
        """Private method based on edlib. Sets the editDistance and cigarString (both on first call)"""
        alignment = edlib.align(self.string1, self.string2, task="path")
        self.editDistance = alignment["editDistance"]
        self.cigarString = alignment["cigar"]

    def getRatio(self, stringA=None, stringB=None):
        """
        With default(None) atributes - returns editdistance ratio based on main files.
        With different strings can be helpful for substring comparision (.getRatio(SubS1,Subs2))
        >>> ED1 = EditDistance("testABC1", "testABB2")
        >>> ED1.getRatio()
        0.75
        >>> ED1.getRatio("Ala ma kota", "Alan ma psa")
        0.6363636363636364
        >>> ED1.getRatio(1,"999")
        -1
        >>> ED1.getRatio(3987,4789)
        -1
        """
        if (stringA == None and stringB == None):
            stringA, stringB = self.string1, self.string2
            alignmentEditDistance = self.editDistance
        else:
            if not (type(stringA) == str and type(stringB) == str):
                return -1
            alignmentEditDistance = edlib.align(stringA, stringB, task="path")["editDistance"]
        stringLenMax = max(len(stringA), len(stringB))
        ratioAB = 1 - (float(alignmentEditDistance) / float(stringLenMax))
        return ratioAB

    def getOperationsLog(self):
        """
        Prepare and set log of operations for alignment of String2 to String1
        Returns list with tuples for each operation.
        (action, editLength, (string1Element, startIndexStr1, endIndexStr1), (string1Element, startIndexStr2, endIndexStr2)
        action: "I"-Insert "D"-Deletion "X"-Missmatch=Substitution "="-Equals
        editLength: how long is string in this operation
        startIndexStr1/2, endIndexStr1/2: where begins and ends the changed(or not) substring of document
        returns: list of tuples with operations described above.
        Temp newString after all operations should be the same as String1

        >>> ED1=EditDistance("testABC1", "testABB2")
        >>> ED1.getOperationsLog()
        [('=', 6, ('testAB', 0, 6), ('testAB', 0, 6)), ('X', 2, ('C1', 6, 8), ('B2', 6, 8))]

        """
        fullListOfOperations = Cigar.getCalculatedOperations(self.cigarString) #list with length and indexes (FileStr2)
        string1, string2 = self.string1, self.string2
        newString = ""  # temporary string used in transformations str2->str1
        cursor = 0 # "where are we in the second file"
        editsLength = 0
        insertions = 0
        operationLog = []  # container for extended operations

        for operation in fullListOfOperations: #based on Cigar.getCalculatedOperations generated tuples
            action = operation[0]  # type of operation X/I/D/=
            startIndex, endIndex = operation[1], operation[2]
            actionLength = operation[3]

            if operation[0] == "X":
                newString += string1[cursor: cursor + actionLength]
                operationLog.append((action, actionLength,
                                     (string1[cursor: cursor + actionLength], cursor, cursor + actionLength),
                                     (string2[cursor + editsLength: cursor + actionLength + editsLength],
                                      cursor + editsLength, cursor + actionLength + editsLength)))
                cursor += actionLength
            if operation[0] == "=":
                newString += string1[cursor: cursor + actionLength]
                operationLog.append((action, actionLength,
                                     (string1[cursor: cursor + actionLength], cursor, cursor + actionLength),
                                     (string2[cursor + editsLength: cursor + actionLength + editsLength],
                                      cursor + editsLength, cursor + actionLength + editsLength)))
                cursor += actionLength
            if operation[0] == "I":
                newStringLen = len(newString)
                newString = newString + string1[newStringLen: newStringLen + actionLength]
                operationLog.append((action, actionLength,
                                     ((string1[newStringLen: newStringLen + actionLength], newStringLen,
                                       newStringLen + actionLength)),
                                     ((string1[newStringLen: newStringLen + actionLength], cursor + editsLength,
                                       cursor + actionLength + editsLength))))
                cursor += actionLength
                editsLength -= actionLength
                insertions += actionLength
            if operation[0] == "D":
                newStringLen = len(newString)
                editsLength += actionLength
                operationLog.append((action, actionLength,
                                     ("", cursor + editsLength, cursor + editsLength + actionLength),
                                     (string2[newStringLen - insertions:newStringLen - insertions + actionLength],
                                      cursor + editsLength, cursor + editsLength + actionLength)
                                     ))
                insertions = insertions - actionLength
        if (newString == self.string1): # newFile should be the same as string1 file
            return operationLog
        else:
            return -1


    def getHTMLReport(self, fileName):
        # TODO: change fonts to css instead of not supporting in html5 "<font...>" [not so important for now]
        operations = self.getOperationsLog()        # we are operating on operations list based on this method
        tempReportFile = open("raport.txt", "a+")
        tempReportFile.seek(0)          # if file exist we have to clean this file first
        tempReportFile.truncate()

        # empty elements on begining of for loop
        tempString1Fragment = ""
        tempString2Fragment = ""
        tempString1FragmentSimple = ""
        tempString2FragmentSimple= ""
        tempTheSameElementBefore = ""
        tempTheSameElementAfter = ""


        tempIndexFile1 = 0
        tempIndexFile2 = 0
        blockNumber = 1
        numberOfTheSameElements = 10        #how many the same elements in line are defining new block
        numberOfContentElements = 50

        for k in range(len(operations)):

            if operations[k][0] == '=':    # EQUALS
                if operations[k][1] > numberOfTheSameElements:  # when we find block of 10 matching elements. Output string is cut.
                    tempEndIndexFile1 = operations[k][2][1]
                    tempEndIndexFile2 = operations[k][3][1]
                    print(tempIndexFile1)
                    tempTheSameElementAfter = "<span class='ctx'>" + str(html2text.HTML2Text(operations[k][2][0][:numberOfContentElements])) + '</span>'

                    if (len(tempString1Fragment) > 0 and len(tempString2Fragment) > 0):    # avoid 1st empty elements
                        tempString1Fragment += "  " + tempTheSameElementAfter.replace("  ","").replace("\n"," ")+"<br>"  # newline after string1 element [1]
                        tempString2Fragment += "  " + tempTheSameElementAfter.replace("  ","").replace("\n"," ")
                        tempString1FragmentSimple += "  " + tempTheSameElementAfter.replace("  ", "").replace("\n"," ") + "<br>"
                        tempString2FragmentSimple += "  " + tempTheSameElementAfter.replace("  ", "").replace("\n", " ")
                        # separated end of block

                        tempReportFile.write("<span class='binfo'>BLOCK" + str(blockNumber) +
                                             " [" + str(tempIndexFile1) + ":" + str(tempEndIndexFile1) + "]"
                                             + " in FILE1, " + "[" + str(tempIndexFile2) + ":" + str(tempEndIndexFile2)
                                             + "]</span>"
                                             + str(tempTheSameElementBefore).replace("  ","").replace("\n"," ").replace("\t"," ")
                                             + "  " + tempString1Fragment.replace("\n"," ")
                                             + str(tempTheSameElementBefore).replace("  ","").replace("\n"," ").replace("\t"," ")
                                             + "  " +tempString2Fragment.replace("\n"," ") +"<BR><BR>")
                        tempReportFile.write(str(tempTheSameElementBefore).replace("  ","").replace("\n"," ").replace("\t"," ")
                                             + "  " + tempString1FragmentSimple.replace("\n"," ")
                                             + str(tempTheSameElementBefore).replace("  ","").replace("\n"," ").replace("\t"," ")
                                             + "  " +tempString2FragmentSimple.replace("\n"," ") +"<BR><BR>")

                        blockNumber += 1
                    tempTheSameElementBefore = "<span class='ctx'>" + str(html2text.HTML2Text(operations[k][2][0][-numberOfContentElements:]))+'</span>'
                    tempString1Fragment = ""
                    tempString2Fragment = ""
                    tempString1FragmentSimple = ""
                    tempString2FragmentSimple = ""
                    tempIndexFile1 = operations[k][2][2]
                    tempIndexFile2 = operations[k][3][2]

                else:
                    tempString1Fragment += str(html2text.HTML2Text((operations[k][2][0])))
                    tempString2Fragment += str(html2text.HTML2Text((operations[k][3][0])))
                    tempString1FragmentSimple += str(html2text.HTML2Text((operations[k][2][0])))
                    tempString2FragmentSimple += str(html2text.HTML2Text((operations[k][3][0])))

            if operations[k][0] == "D":  # DELETION
                tempString2Fragment = tempString2Fragment + "<span class='ins'>" + str(html2text.HTML2Text((operations[k][3][0]).replace("\n"," "))) + "</span>"
                tempString1Fragment += "<span class='ins'>" + len(operations[k][3][0]) * "_" + "</span>"
                tempString2FragmentSimple = tempString2FragmentSimple +  "<span class='ins'>" + str(html2text.HTML2Text((operations[k][3][0]).replace("\n"," "))) + "</span>"
            if operations[k][0] == "I":  # INSERTION
                tempString1Fragment += "<span class='ins'>" + str(html2text.HTML2Text((operations[k][2][0]).replace("\n"," "))) + "</span>"
                tempString2Fragment += "<span class='ins'>" + len(operations[k][2][0]) * "_" + "</span>"
                tempString1FragmentSimple +="<span class='ins'>" + str(html2text.HTML2Text((operations[k][2][0]).replace("\n"," "))) + "</span>"
            if operations[k][0] == "X":  # MISMATCH
                tempString1Fragment += "<span class='sbst'>" + str(html2text.HTML2Text((operations[k][2][0]))) + "</span>"
                tempString2Fragment += "<span class='sbst'>" + str(html2text.HTML2Text((operations[k][3][0]))) + "</span>"
                tempString1FragmentSimple += "<span class='sbst'>" + str(html2text.HTML2Text((operations[k][2][0]))) + "</span>"
                tempString2FragmentSimple += "<span class='sbst'>" + str(html2text.HTML2Text((operations[k][3][0]))) + "</span>"
        # Write to main file. If exists it will be overwritten
        htmlRaportFile = open(fileName, "a")
        htmlRaportFile.truncate(1)
        tempReportFile.seek(0)  # going on top of the tempFile (a+ opening method leaves cursor on the end of file)
        htmlRaportFile.write(template%tempReportFile.read())
        tempReportFile.close()
        htmlRaportFile.close()
        os.remove("raport.txt")


if __name__ == "__main__":
    import doctest
    doctest.testmod()