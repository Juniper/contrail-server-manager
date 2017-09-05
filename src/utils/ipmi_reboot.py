import time
import sys
from subprocess import Popen,PIPE,check_output,check_call

ipmi_addresses = ['1.1.1.1']
total_address = len(ipmi_addresses)
i=0


def progress(count, total, suffix='', prefix = ''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    prefix_len = len(prefix)
    prefix_fill = ' ' * (15-prefix_len)

    percents = round(100.0 * count / float(total), 1)
    bar = '#' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write('%s%s [ %s ] %s%s ...%s\r' % (prefix,prefix_fill,bar, percents, '%', suffix))
    sys.stdout.flush()  # As suggested by Rom Ruben



#def update_progress(progress):
    #print '\r[{0}] {1}%'.format('#'*(progress/10), progress)

def hilite(string, status, bold):
    attr = []
    if status:
        # green
        attr.append('32')
    else:
        # red
        attr.append('31')
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), string)


failed_address = []
for address in ipmi_addresses:
  i+=1
  status = " TRYING"
  #print address
  progress(10, 100, prefix=address, suffix=status )
  cmd=['/usr/bin/ipmitool -U ADMIN -P ADMIN -H '+ address+ ' mc info']
  try:
    ipmi_output=check_call(cmd,shell=True,stdout=PIPE, stderr=PIPE)
    status = " PASSED "
    status = hilite(status, 1, 0)
  except:
    failed_address.append(address)
    status = " FAILED "
    status = hilite(status, 0, 0)
    pass

  progress(100, 100, prefix=address, suffix=status )
  print ""
  

print ""
print failed_address
