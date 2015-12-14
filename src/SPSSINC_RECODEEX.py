from __future__ import with_statement
#/***********************************************************************
# * Licensed Materials - Property of IBM 
# *
# * IBM SPSS Products: Statistics Common
# *
# * (C) Copyright IBM Corp. 1989, 2014
# *
# * US Government Users Restricted Rights - Use, duplication or disclosure
# * restricted by GSA ADP Schedule Contract with IBM Corp. 
# ************************************************************************/
import spss, spssaux

from spssaux import _smartquote
from spssaux import u
import spss, spssaux
from extension import Template, Syntax, processcmd
import locale, os, re, copy, codecs, string

__author__ =  'spss, JKP'
__version__=  '1.1.0'

# history
# 04-jun-2010 original version
# 11-nov-2014 Allow input value labels in generated value labels


helptext = """SPSSINC RECODEEX
inputvarlist = outputvarlist
/RECODES "(input value(s) = recode) ... (else={COPY*|SYSMIS})"
[/OPTIONS [STRINGSIZE=n] [VALUELABELS={YES*|NO}] [COPYVARIABLELABELS={YES*|NO}]
[SUFFIX="value"] [PREFIX="value"]]

Recode variables into other variables with optional variable and value label generation.

Examples:
RECODEEX fatherage motherage = fatheragerc motheragerc
/RECODES "(LO THRU 50=1) (51 thru 75=2) (ELSE=COPY)"
/OPTIONS SUFFIX="rc".

RECODEEX bdate = bdaterc
/RECODES "(LO THRU 1950-12-31=1)(1951-01-01 THRU 1990-12-31=2)".

RECODE duration = durationrc
/RECODES "(LO THRU 10 12:00:00=1)(10 12:00:00 THRU HIGH=2)".


This command extends the built-in RECODE command in several ways.
- Date or time constants are used for variables of these types
- Value labels can be automatically generated for the outputs
- Variable labels can be copied
- Variable types can be changed for the output variables.

inputvarlist specifies the variables to be recoded.  They must all have the same type
(numeric, string, a date format, or a time format).  
MOYR, WKYR and WKDAY formats are not supported.
outputvarlist specifies an equal number of variables for the results.  If STRINGSIZE is specified,
the output variables will all be made strings of that length.  The type of any existing variables will be
changed to match if necessary.  If STRINGSIZE is not specified, no variable types
will be changed, and any new variables will be numeric.
A variable cannot be used as both an input and output variable.

Recode specifications have the same general form as for the RECODE command:
(input-values = output-value)
See the RECODE command for details.
THE ENTIRE RECODE SPECIFICATION must be enclosed in quotes.
Input or output string values must also be quoted.

If the variables have a date format, recode values have the form yyyy-mm-dd.
If the values have a time format, recode values have the form hh:mm, hh:mm:ss.ss
or these forms preceded by days, e.g., 10 08:03.

VALUELABELS specifies whether value labels should be created for the output values.
They will consist of the input values that are mapped to each output with two caveats:
An else specification does not contribute to the labels.
If an input value is mapped to more than one output value, it will appear in each corresponding
value label even though the RECODE command processes from left to right.

If COPYVARIABLELABELS=YES, the variable label, if any, of each input variable
will be copied to the output variable.  PREFIX and SUFFIX can specify text to be
prepended or appended to the label with a separating blank.

/HELP displays this help and does nothing else.
"""

# MOYR, WKYR and WKDAY formats are not supported
datefmts = set(["DATE", "ADATE", "EDATE", "JDATE", "SDATE", "QYR", "DATETIME"])
timefmts = set(["TIME", "DTIME"])
numfmts = set(["F", "N", "E"])
strfmts = set(["A", "AHEX"])

def Run(args):
    """Execute the SPSSINC RECODEEX extension command"""
    
    # debugging
    # makes debug apply only to the current thread
    #try:
        #import wingdbstub
        #if wingdbstub.debugger != None:
            #import time
            #wingdbstub.debugger.StopDebug()
            #time.sleep(2)
            #wingdbstub.debugger.StartDebug()
        #import thread
        #wingdbstub.debugger.SetDebugThreads({thread.get_ident(): 1}, default_policy=0)
    #except:
        #pass

    args = args[args.keys()[0]]

    oobj = Syntax([
        Template("", subc="",  ktype="literal", var="varlist", islist=True),
        Template("", subc="RECODES", ktype="literal", var="recodes", islist=True),
        
        Template("STRINGSIZE", subc="OPTIONS", ktype="int", var="stringsize", vallist=[1, 32767]),
        Template("VALUELABELS", subc="OPTIONS", ktype="bool", var="makevaluelabels"),
        Template("USEINPUTVALLABELS", subc="OPTIONS", ktype="bool",
            var="useinputvallabels"),
        Template("COPYVARIABLELABELS", subc="OPTIONS", ktype="bool", var="copyvariablelabels"),
        Template("SUFFIX", subc="OPTIONS", ktype="literal", var="suffix"),
        Template("PREFIX", subc="OPTIONS", ktype="literal", var="prefix"),
        
        Template("HELP", subc="", ktype="bool")])
    
    
    #enable localization
    global _
    try:
        _("---")
    except:
        def _(msg):
            return msg
    # A HELP subcommand overrides all else
    if args.has_key("HELP"):
        #print helptext
        helper()
    else:
        processcmd(oobj, args, recode)

def helper():
    """open html help in default browser window
    
    The location is computed from the current module name"""
    
    import webbrowser, os.path
    
    path = os.path.splitext(__file__)[0]
    helpspec = "file://" + path + os.path.sep + \
         "markdown.html"
    
    # webbrowser.open seems not to work well
    browser = webbrowser.get()
    if not browser.open_new(helpspec):
        print("Help file not found:" + helpspec)
try:    #override
    from extension import helper
except:
    pass

def recode(varlist, recodes, stringsize=None, makevaluelabels=True, copyvariablelabels=True, useinputvallabels=False,
    suffix="", prefix=""):

    vardict = spssaux.VariableDict(caseless=True)
    isutf8 = spss.PyInvokeSpss.IsUTF8mode()
    ecutf8 = codecs.getencoder("utf_8")
    inputlist, outputlist, vartype = parsevarlist(varlist, vardict)
    if len(recodes) > 1:
        raise ValueError(_("The RECODES subcommand must consist of a single, quoted specification"))
    # recodespec is a list of textual recode syntax, one item per value set
    # vldefs is a dictionary with keys the target values
    # and values the input codes
    # inputdict is a dictionary with keys the target values 
    # and values a list of the input codes
    recodespec, vldefs, inputdict = parserecodes(recodes[0], vartype, stringsize)
    valuelabelmessage = checklabelconsistency(inputlist, vardict)
    
    if stringsize:
        alter = []
        create = []
        for v in outputlist:
            try:
                if vardict[v].VariableType != stringsize:
                    alter.append(v)
            except:
                create.append(v)
        if create:
            spss.Submit("STRING %s (A%s)." % (" ".join(create), stringsize))
        if alter:
            spss.Submit("ALTER TYPE %s (A%s)" % (" ".join(alter), stringsize))
                
    spss.Submit("""RECODE %s %s INTO %s.""" % (" ".join(inputlist), " ".join(recodespec), " ".join(outputlist)))
    
    # generate variable labels if requested
    if copyvariablelabels:
        if prefix and not prefix.endswith(" "):
            prefix = prefix + " "
        if suffix and not suffix.startswith(" "):
            suffix = " " + suffix
        for vin, vout in zip(inputlist, outputlist):
            spss.Submit("""VARIABLE LABEL %s %s.""" % \
                (vout, _smartquote(prefix + vardict[vin].VariableLabel + suffix, True)))
            
    # generate value labels if requested
    # all values for given target are merged but else clause is omitted
    # VALUE LABELS syntax quotes values regardless of variable type
    # vldefs is a dictionary with keys of the output values and
    # values a string listing the input values.  If copying value labels
    # the first input variable is used as the source.
    if makevaluelabels:
        if useinputvallabels:
            vldefs = makevallabels(vldefs, inputdict, 
                vardict[inputlist[0]].ValueLabels, isutf8, ecutf8)
            
        # ensure that copy as target does not generate a value label
        copyset = set()
        for target in vldefs:
            if target.lower() == "copy":
                copyset.add(target)
        for c in copyset:
            del(vldefs[c])
        
        #spss.Submit(r"""VALUE LABELS %s %s.""" % (" ".join(outputlist), \
            #" ".join([_smartquote(val, vartype == 2) + " " + _smartquote(label, True) for val, label in vldefs.items()])))
        
        spss.Submit(r"""VALUE LABELS %s %s.""" % (" ".join(outputlist), \
            " ".join([val + " " + _smartquote(label, True) for val, label in vldefs.items()])))
    if valuelabelmessage:
        print valuelabelmessage

def makevallabels(vldefs, inputlabels, valuelabels, 
        isutf8, ecutf8):
    """convert values to value labels where available up to length limit
    
    vldefs is a list of target values
        value is string listing input values
    valuelabels is a dictionary of labels
    inputlabels is a dictionary of input values to the recode
    The input values are a list preceded by the join sequence
    """
    
    for target in vldefs:
        labels = [valuelabels.get(val, val) for val in inputlabels[target]]
        labels = ", ".join(labels)
        vldefs[target] = (truncatestring(labels, isutf8, 120, ecutf8))

    return vldefs

def truncatestring(name, unicodemode, maxlength, ecutf8):
    """Return a name truncated to no more than maxlength BYTES.
    
    name is the candidate string
    unicodemode identifies whether in Unicode mode or not
    maxlength is the maximum byte count allowed.  It must be a positive integer
    ecutf8 is a utf-8 codec
    
    If name is a (code page) string, truncation is straightforward.  If it is Unicode utf-8,
    the utf-8 byte representation must be used to figure this out but still truncate on a character
    boundary."""
    

    if not unicodemode:
        if len(name) > maxlength:
            name = name[:maxlength-3] + "..."
    else:
        newname = []
        nnlen = 0
        
        # In Unicode mode, length must be calculated in terms of utf-8 bytes
        for c in name:
            c8 = ecutf8(c)[0]   # one character in utf-8
            nnlen += len(c8)
            if nnlen <= maxlength:
                newname.append(c)
            else:
                newname = newname[:-4]
                newname.append("...")
                break
        name = "".join(newname)
    return name
    
    
def parsevarlist(varlist, vardict):
    """return input variable list, output variable list, and basic type
    
    varlist is a list whose combined elements have the "var var var  = var var var"
    vardict is a variable dictionary
    
    In return, type is coded as
    1 = numeric
    2 = string
    3 = date
    4 = time
    
    type constraints are enforced here but no attempt is made to check output variable types"""
    
    try:
        sepindex = varlist.index("=")
        inputv = varlist[:sepindex]
        outputv = varlist[sepindex+1:]
    except:
        raise ValueError(_("Variable list must have the form inputvars = outputvars"))
    if len(inputv) != len(outputv):
        raise ValueError(_("The number of input and output variables differ"))
    if set(inputv).intersection(set(outputv)):
        raise ValueError(_("Input and Output variable lists must be distinct"))
    
    fmts = [vardict[v].VariableFormat.rstrip("0123456789.") for v in inputv]
    fmtypes = [f in numfmts and 1 or f in strfmts and 2 or f in datefmts and 3\
        or f in timefmts and 4 for f in fmts or 0]
    if len(set(fmtypes)) > 1:
        raise ValueError(_("All input variables must have the same basic type"))
    if fmtypes[0] == 0:
        raise ValueError(_("Unsupported format type: %s") % fmts[0])
    return inputv, outputv, fmtypes[0]
    
def parserecodes(recodes, vartype, stringsize):
    """Return list of recode specs for values
    
    recodes is the text of the RECODES subcommand.  Expected form is
    (input values = outputvalue) ...
    where input values could be a list of values, including THRU , HIGH, HIGHEST etc
    For dates, expected form is yyyy-mm-dd
    For times, expected form is hh:mm:ss.fraction where all parts after hh are optional
    Else spec is returned as is (RECODE will check it)
    vartype is 1 - 4 as above"""
    
    # first, process out all ( and ) characters embedded inside a literal (only matters for string variables)
    recodes = protected(recodes)
    allmappings = re.findall(r"\(.+?\)", recodes)     # find all parenthesized mappings
    if not allmappings:
        raise ValueError(_("The recode specification did not include any parenthesized specifications."))
    recodespec = []
    recodetargets = {}
    inputlist = {}
    for item in allmappings:
        itemcopy = copy.copy(item)
        if vartype == 3:
            item, count = re.subn(r"\d+-\d+-\d+(\s+\d+:\d+(:[.0-9]+)*)*", yrmodamo, item) # convert date or date/time expressions
            if count == 0:
                raise ValueError(_("A date variable recode specification did not include a date value: %s") % item)
        elif vartype == 2:
            item = re.sub(r"\02", "(", item)
            item = re.sub(r"\03", ")", item)
            itemcopy = copy.copy(item)
        elif vartype == 4:
            item, count = re.subn(r"(\d+\s+)*\d+:\d+(:[0-9.]+)*", timemo, item)
            if count == 0:
                raise ValueError(_("A time variable recode specification did not include a time value: %s") % item)
        recodespec.append(item)
        parts = mapdef(itemcopy)   # get input, target for recode target value
        if not parts[0] == "else":
            try:
                recodetargets[parts[1]] = recodetargets[parts[1]] + "," + parts[0]
            except:   # new target value
                recodetargets[parts[1]] = parts[0]
            inputlist[parts[1]] = splitter(parts[0])
            
    return recodespec, recodetargets, inputlist

# characters legal in recode spec keywords
# string.letters is affected by local setting so need to subset
letters = string.letters[:52]
def splitter(pplus):
    """split string according to SPSS Statistics rules and return as list
    
    pplus is the string to split
    If the recode spec contains RECODE keywords, 
    return the expression as a list of length 1"""
    
    quo = None
    pplus = list(pplus +" ")
    i = 0
    pplusout = []
    recodekeyword = False
    while i < len(pplus) -1:
        ch = pplus[i]
        if ch == quo:
            if pplus[i+1] == quo:
                i+=1
                pplusout.append(ch)
            else:
                quo = None
        else:
            if ch in ['"', "'"]:
                quo = ch
            else:
                pplusout.append(ch)
        if quo and ch == " ":
            #pplus[i] = "\a"
            pplusout[-1] = "\a"
        if not quo and ch in letters:   # plain alphabetics
            recodekeyword = True
        i += 1
    inputs = "".join(pplusout).split()
    inputs = [item.replace("\a", " ") for item in inputs]
    if recodekeyword:
        inputs = [" ".join(inputs)]  # Can't find a label for this
    return inputs

def checklabelconsistency(varnames, vardict):
    """Print warning message if value labels for varnames are inconsistent
    
    varnames is a list of variable names to check
    vardict is a VariableDict object"""
    
    if len(varnames) <= 1:
        return
    clashes = []
    for i,var in enumerate(varnames):
        vallabels = set([(k.lower(), v) for k, v in vardict[var].ValueLabels.items()])
        if i == 0:
            refset = copy.copy(vallabels)
        else:
            if refset and not vallabels.issubset(refset):
                clashes.append(var)
    if clashes:
        return _("""Warning: The following variables have value labels sets inconsistent with the 
first variable being recoded (%s).  The coding may be inconsistent.

If generating labels from the input value labels, the labels from 
the first input variable are used to label the output values 
for all the output variables.
%s""") % (varnames[0], " ".join(clashes))
    else:
        return None

def mapdef(spec):
    """return target value and inputs as a duple
    
    spec has form (inputs = target)"""
    
    # can't simply look for = not surrounded by quotes because ('x'='y') is legit :-(
    litranges = []
    for ch in ["'", '"']:  #single quote or double quote
        pat = """%(ch)s[^%(ch)s]*%(ch)s"""  % locals()  # quote non-quote-of-same-type* quote
        moit = re.finditer(pat, spec)
        # for each literal found, replace ( and )
        for m in moit:
            litranges.append(m.span())
    for i in range(len(spec), 0, -1):
        pos = i-1
        if spec[pos] == "=":
            inlit = False
            for r in litranges:
                if r[0] <= pos < r[1]:
                    inlit = True
                    break
            if inlit:
                continue
            return (spec[1:pos].strip(), spec[pos+1:-1].strip())
    else:
        raise ValueError(_("Invalid recode specification: %s") % spec)
    
    # break expression into input and target separated by unquoted =
    ###return (parts[0][1:].strip(), parts[1][:-1].strip())

def protected(astr):
    """Return a string where all ( or ) characters embedded in quotes are converted to x02 or x03
    astr is the text to search"""
    
    # astr will always be pretty short in practice
    
    for ch in ["'", '"']:  #single quote or double quote
        pat = """%(ch)s[^%(ch)s]*%(ch)s"""  % locals()  # quote non-quote-of-same-type* quote
        moit = re.finditer(pat, astr)
        # for each literal found, replace ( and )
        for m in moit:
            st, end = m.start(), m.end()
            astr = astr[:st] + re.sub(r"\(", "\x02", astr[st:end]) + astr[end:]
            astr = astr[:st] + re.sub(r"\)", "\x03", astr[st:end]) + astr[end:]
    return astr

def yrmodamo(mo):
    """convert a date expression with an optional time portion to a number for recode
    
    mo is the match object"""
    
    # input like
    #2005-03-31 or
    #2005-03-31 8:30 or
    #2005-03-31 8:30:05.2
    parts = mo.group().split()   # break up date and time portions on white space
    
    date = parts[0].split("-")
    timeseconds = 0.
    dateval = yrmoda(date)
    
    # time portion, if any.  hours and minutes are required; seconds are optional.
    if len(parts) ==2:
        timeparts = parts[1].split(":")   # either 2 or 3 parts
        timeparts = [float(t) for t in timeparts]
        timeseconds = (timeparts[0] * 60. + timeparts(1)) * 60.
        if len(timeparts) == 3:
            timeseconds = timeseconds + timeparts[2]
    return str(dateval + timeseconds)

def timemo(mo):
    """convert a time expression to a number for recode
    
    mo is the match object"""
    
    # input like
    #d hh:mm
    #d hh:mm:ss.ss
    #hh:mm
    #hh:mm:ss.ss
    
    parts = mo.group().split()  # days and time
    # time portion
    t = [float(v) for v in parts[-1].split(":")]
    t0 = (t[0] * 60. + t[1]) * 60.    # hours and minutes
    if len(t) == 3:
        t0 = t0 + t[2]   # and seconds
    if len(parts) == 2:  # day portion?
        t0 = t0 + float(parts[0]) * 86400.
    return str(t0)

def _smartquote(s, quoteit=True, qchar='"'):
    """ smartquote a string so that internal quotes are distinguished from surrounding
    quotes for SPSS and return that string with the surrounding quotes.  qchar is the
    character to use for surrounding quotes.
    if quoteit is True, s is a string that needs quoting; otherwise it does not
    """
    if quoteit:
        return qchar + s.replace(qchar, qchar+qchar) + qchar
    else:
        return s
            

def yrmoda(ymd):
    """compute SPSS internal date value from four digit year, month, and day.
    ymd is a list of numbers in that order.  The parts will be truncated to integers.
    The result is equivalent to the SPSS subroutine yrmoda result converted to seconds"""
    
    if len(ymd) != 3:
        raise ValueError, "date specification must have the form yyyy-mm-dd"
    year = int(ymd[0])
    month = int(ymd[1])
    day = int(ymd[2])
    
    if year < 1582 or month < 1 or month > 13 or day <0 or day > 31:
        raise ValueError, (_("Invalid date value: %d %d %d")) % (year, month, day)
    yrmo = year * 365 + (year+3)//4 - (year+99)//100 + (year + 399)//400 \
         + 3055 *(month+2)//100 - 578192
    if month > 2:
        yrmo-= 2
        if (year%4 == 0 and (year%100 != 0 or year%400 ==0)):
            yrmo+= 1
    return (yrmo + day) * 86400   #24 * 60 * 60
