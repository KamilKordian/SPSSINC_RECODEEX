* Encoding: UTF-8.
* using employee data.
compute jobcat2 = jobcat.  /* No labels */
compute jobcatcopy = jobcat.
APPLY DICTIONARY
  /FROM *
  /SOURCE VARIABLES=jobcat  /TARGET VARIABLES=jobcatcopy
  /VARINFO VALLABELS=REPLACE.

value labels jobcat2 5 "extra".

spssinc recodeex
jobcat = newjobcat
/recodes "(1 2 = 3) (3=10)".

spssinc recodeex
jobcat = newjobcat
/recodes "(1 2 = 3) (3=10)"
/options useinputvallabels=yes.

spssinc recodeex
jobcat = newjobcat
/recodes "(1 2 = 3) (3=10)"
/options useinputvallabels=yes.


spssinc recodeex
gender = gendernew
/recodes "('m' 'm m' 'm''m'= 'mmm')"
/options stringsize=10 useinputvallabels=yes.

spssinc recodeex
educ = educnew
/recodes "(lo thru 12=1) (13 thru 16=2)(else=3)".

spssinc recodeex
educ = educnew2
/recodes "(lo thru 12=1) (13 thru 16=2)(else=3)"
/options useinputvallabels=yes.

spssinc recodeex
educ = educnew2
/recodes "(lo thru 12=1) (13 14 15=copy)(else=3)"
/options useinputvallabels=yes.


spssinc recodeex
educ = educnew
/recodes "(lo thru 12=1) (13 thru 16=copy)(else=3)"
/options useinputvallabels=yes.

spssinc recodeex jobcat = jobcat3
/recodes "(1 = 10)(2=20)".

* generate warning.
spssinc recodeex jobcat JOBCAT2 = jobcat3 jobcat4
/recodes "(1=10)" /options useinputvallabels=yes.

* no warning.
spssinc recodeex jobcat JOBCAT2 = jobcat3 jobcat4
/recodes "(1=10)" /options useinputvallabels=no.

spssinc recodeex jobcat jobcatcopy = jobcat10 jobcat11
/recodes "(1=100)" /options useinputvallabels=yes.

begin program.
import SPSSINC_RECODEEX
reload(SPSSINC_RECODEEX)
end program.

VALUE LABELS gendernew 'mmm' "'m', 'm m', 'm''m'".

value labels jobcat2
2 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
4 '���������������������������������������������������������������������x'
6 'ccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccx'.
spssinc recodeex jobcat2 = jobcat4
/recodes "(2 4 6 = 246)"
/options USEINPUTVALLABELS =yes.


