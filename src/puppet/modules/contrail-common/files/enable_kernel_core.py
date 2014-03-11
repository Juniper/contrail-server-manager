import re
import tempfile


class ExtList (list):

    def findex(self, fun):
        for i, x in enumerate(self):
            if fun(x):
                return i
        raise LookupError('No matching element in list')
    # end def findex
# end class ExtList


def enable_kernel_core():
    '''
        enable_kernel_core:
            update grub file
            install grub2
            enable services
    '''
    gcnf = ''
    _temp_dir_name = tempfile.mkdtemp()
    with open('/etc/default/grub', 'r') as f:
        gcnf = f.read()
        p = re.compile('\s*GRUB_CMDLINE_LINUX')
        el = ExtList(gcnf.split('\n'))
        try:
            i = el.findex(p.match)
            exec (el[i])
            el[i] = 'GRUB_CMDLINE_LINUX="%s crashkernel=128M"' % (
                    ' '.join(filter(lambda x: not x.startswith(
                                    'crashkernel='),
                                    GRUB_CMDLINE_LINUX.split())))
            exec (el[i])
            el[i] = 'GRUB_CMDLINE_LINUX="%s kvm-intel.nested=1"' % (
                    ' '.join(filter(lambda x: not x.startswith(
                                    'kvm-intel.nested='),
                                    GRUB_CMDLINE_LINUX.split())))

            with open('%s/grub' % _temp_dir_name, 'w') as f:
                f.write('\n'.join(el))
                f.flush()
            local('mv %s/grub /etc/default/grub' % (_temp_dir_name))
            local('/usr/sbin/grub2-mkconfig -o /boot/grub2/grub.cfg')
        except LookupError:
            print 'Improper grub file, kernel crash not enabled'
# end enable_kernel_core

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    enable_kernel_core()
